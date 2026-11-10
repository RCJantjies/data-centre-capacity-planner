import csv
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path

from capacity_planner import Assessment, Workload, Zone, assess_capacity, load_workloads, load_zones, main, summary


class CapacityPlannerTests(unittest.TestCase):
    def setUp(self):
        self.zone = Zone("A", 100, 50, 100, 50, 100, 50)

    def test_assessment_applies_reserve_and_workload_quantity(self):
        workload = Workload("Compute", "A", 5, 10, 8, quantity=2)
        results = assess_capacity([self.zone], [workload], reserve_percent=20)
        by_resource = {item.resource: item for item in results}
        self.assertEqual(by_resource["power_kw"].effective_capacity, 80)
        self.assertEqual(by_resource["power_kw"].projected_usage, 70)
        self.assertEqual(by_resource["power_kw"].status, "WATCH")

    def test_breach_when_projected_usage_exceeds_effective_capacity(self):
        results = assess_capacity([self.zone], [Workload("Dense", "A", 0, 31, 0)])
        self.assertEqual(results[1].status, "BREACH")
        self.assertLess(results[1].headroom, 0)

    def test_unknown_zone_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "unknown zone"):
            assess_capacity([self.zone], [Workload("X", "Missing", 1, 1, 1)])

    def test_invalid_reserve_is_rejected(self):
        for value in (-1, 100):
            with self.subTest(value=value), self.assertRaises(ValueError):
                assess_capacity([self.zone], [], value)

    def test_summary_decisions(self):
        base = dict(zone="A", resource="power_kw", effective_capacity=10, projected_usage=5, utilization_percent=50, headroom=5)
        self.assertEqual(summary([Assessment(**base, status="OK")])["decision"], "GO")
        self.assertEqual(summary([Assessment(**base, status="WATCH")])["decision"], "CONDITIONAL")
        self.assertEqual(summary([Assessment(**base, status="BREACH")])["decision"], "NO-GO")

    def test_csv_loading_and_json_export(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            zones = root / "zones.csv"
            workloads = root / "workloads.csv"
            output = root / "report.json"
            zones.write_text("zone,total_rack_units,used_rack_units,total_power_kw,used_power_kw,total_cooling_kw,used_cooling_kw\nA,100,50,100,50,100,50\n", encoding="utf-8")
            workloads.write_text("workload,zone,quantity,rack_units,power_kw,cooling_kw\nWeb,A,2,5,10,8\n", encoding="utf-8")
            with redirect_stdout(StringIO()):
                self.assertEqual(main(["--zones", str(zones), "--workloads", str(workloads), "--json-output", str(output)]), 0)
            payload = json.loads(output.read_text(encoding="utf-8"))
            self.assertEqual(payload["summary"]["decision"], "CONDITIONAL")
            self.assertEqual(len(load_zones(zones)), 1)
            self.assertEqual(load_workloads(workloads)[0].quantity, 2)

    def test_duplicate_zone_and_overallocated_baseline_are_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "zones.csv"
            header = "zone,total_rack_units,used_rack_units,total_power_kw,used_power_kw,total_cooling_kw,used_cooling_kw\n"
            path.write_text(header + "A,10,11,10,1,10,1\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "invalid rack_units"):
                load_zones(path)

    def test_invalid_workload_quantity_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "workloads.csv"
            path.write_text("workload,zone,quantity,rack_units,power_kw,cooling_kw\nX,A,1.5,1,1,1\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "positive integer"):
                load_workloads(path)


if __name__ == "__main__":
    unittest.main()
