"""Data-centre capacity and resilience scenario planner."""

from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


RESOURCE_FIELDS = ("rack_units", "power_kw", "cooling_kw")


@dataclass(frozen=True)
class Zone:
    name: str
    total_rack_units: float
    used_rack_units: float
    total_power_kw: float
    used_power_kw: float
    total_cooling_kw: float
    used_cooling_kw: float


@dataclass(frozen=True)
class Workload:
    name: str
    zone: str
    rack_units: float
    power_kw: float
    cooling_kw: float
    quantity: int = 1


@dataclass(frozen=True)
class Assessment:
    zone: str
    resource: str
    effective_capacity: float
    projected_usage: float
    utilization_percent: float
    headroom: float
    status: str


def _number(row: dict[str, str], field: str, source: Path) -> float:
    try:
        value = float(row[field])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"{source}: invalid {field!r}") from exc
    if value < 0 or not math.isfinite(value):
        raise ValueError(f"{source}: {field!r} must be a finite non-negative number")
    return value


def load_zones(path: Path) -> list[Zone]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"{path}: no zone records found")
    zones: list[Zone] = []
    names: set[str] = set()
    for row in rows:
        name = (row.get("zone") or "").strip()
        if not name or name in names:
            raise ValueError(f"{path}: zone names must be present and unique")
        names.add(name)
        values = {field: _number(row, field, path) for field in (
            "total_rack_units", "used_rack_units", "total_power_kw",
            "used_power_kw", "total_cooling_kw", "used_cooling_kw"
        )}
        for resource in RESOURCE_FIELDS:
            total = values[f"total_{resource}"]
            used = values[f"used_{resource}"]
            if total <= 0 or used > total:
                raise ValueError(f"{path}: invalid {resource} capacity for {name}")
        zones.append(Zone(name=name, **values))
    return zones


def load_workloads(path: Path) -> list[Workload]:
    with path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    workloads: list[Workload] = []
    for row in rows:
        name, zone = (row.get("workload") or "").strip(), (row.get("zone") or "").strip()
        if not name or not zone:
            raise ValueError(f"{path}: workload and zone are required")
        quantity = _number(row, "quantity", path)
        if not quantity.is_integer() or quantity < 1:
            raise ValueError(f"{path}: quantity must be a positive integer")
        workloads.append(Workload(
            name=name, zone=zone, quantity=int(quantity),
            rack_units=_number(row, "rack_units", path),
            power_kw=_number(row, "power_kw", path),
            cooling_kw=_number(row, "cooling_kw", path),
        ))
    return workloads


def assess_capacity(
    zones: Iterable[Zone], workloads: Iterable[Workload], reserve_percent: float = 20.0
) -> list[Assessment]:
    if not 0 <= reserve_percent < 100:
        raise ValueError("reserve_percent must be between 0 (inclusive) and 100 (exclusive)")
    zone_list = list(zones)
    additions = {zone.name: {field: 0.0 for field in RESOURCE_FIELDS} for zone in zone_list}
    for workload in workloads:
        if workload.zone not in additions:
            raise ValueError(f"workload {workload.name!r} references unknown zone {workload.zone!r}")
        for field in RESOURCE_FIELDS:
            additions[workload.zone][field] += getattr(workload, field) * workload.quantity

    results: list[Assessment] = []
    for zone in zone_list:
        for field in RESOURCE_FIELDS:
            capacity = getattr(zone, f"total_{field}") * (1 - reserve_percent / 100)
            usage = getattr(zone, f"used_{field}") + additions[zone.name][field]
            utilization = usage / capacity * 100
            status = "BREACH" if utilization > 100 else "WATCH" if utilization >= 85 else "OK"
            results.append(Assessment(
                zone=zone.name, resource=field, effective_capacity=round(capacity, 2),
                projected_usage=round(usage, 2), utilization_percent=round(utilization, 2),
                headroom=round(capacity - usage, 2), status=status,
            ))
    return results


def summary(results: Iterable[Assessment]) -> dict[str, object]:
    items = list(results)
    breaches = [item for item in items if item.status == "BREACH"]
    watches = [item for item in items if item.status == "WATCH"]
    return {
        "decision": "NO-GO" if breaches else "CONDITIONAL" if watches else "GO",
        "breaches": len(breaches), "watch_items": len(watches),
        "most_constrained": asdict(max(items, key=lambda item: item.utilization_percent)) if items else None,
    }


def render_report(results: list[Assessment], reserve_percent: float) -> str:
    decision = summary(results)
    lines = [
        "Data Centre Capacity & Resilience Assessment",
        f"Policy reserve: {reserve_percent:.1f}% | Recommendation: {decision['decision']}",
        "-" * 86,
        f"{'Zone':<16}{'Resource':<16}{'Effective':>12}{'Projected':>12}{'Use %':>10}{'Headroom':>12}{'Status':>8}",
        "-" * 86,
    ]
    for item in results:
        lines.append(
            f"{item.zone:<16}{item.resource:<16}{item.effective_capacity:>12.2f}"
            f"{item.projected_usage:>12.2f}{item.utilization_percent:>10.2f}"
            f"{item.headroom:>12.2f}{item.status:>8}"
        )
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--zones", type=Path, default=Path("data/zones.csv"))
    parser.add_argument("--workloads", type=Path, default=Path("data/proposed_workloads.csv"))
    parser.add_argument("--reserve-percent", type=float, default=20.0)
    parser.add_argument("--json-output", type=Path)
    args = parser.parse_args(argv)
    try:
        results = assess_capacity(load_zones(args.zones), load_workloads(args.workloads), args.reserve_percent)
    except (OSError, ValueError) as exc:
        parser.error(str(exc))
    print(render_report(results, args.reserve_percent))
    if args.json_output:
        payload = {"policy_reserve_percent": args.reserve_percent, "summary": summary(results),
                   "assessments": [asdict(item) for item in results]}
        args.json_output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
