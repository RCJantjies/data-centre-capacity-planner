# Data Centre Capacity & Resilience Planner

**Version 1.0 — portfolio release**

A Python command-line decision-support tool that evaluates proposed data-centre workloads against rack, power, and cooling capacity while preserving a configurable operational reserve.

## Business Problem

Capacity decisions are constrained by more than free rack units. A deployment that physically fits may still exceed available power, cooling, or an organisation's resilience reserve. Spreadsheet reviews can also make assumptions difficult to audit consistently.

This project demonstrates a consulting-style assessment workflow: establish a baseline, model a proposed deployment, apply a capacity-reserve policy, identify constraints, and issue an explainable `GO`, `CONDITIONAL`, or `NO-GO` recommendation.

## Features

- Loads current zone capacity and proposed workloads from CSV
- Evaluates rack space, power, and cooling independently
- Applies a configurable reserve policy to protect operational headroom
- Supports workload quantities and multi-zone scenarios
- Classifies each constraint as `OK`, `WATCH`, or `BREACH`
- Produces an executive recommendation and identifies the tightest constraint
- Exports a machine-readable JSON assessment for reporting or integration
- Validates malformed, negative, duplicate, overallocated, and unknown-zone inputs
- Uses only the Python standard library
- Runs automated tests across three Python versions in GitHub Actions

## Decision Model

For each resource and zone:

```text
effective capacity = installed capacity × (1 − reserve percentage)
projected usage    = current usage + proposed workload demand
utilization        = projected usage ÷ effective capacity
```

| Utilization of effective capacity | Classification |
| ---: | --- |
| Below 85% | `OK` |
| 85% to 100% | `WATCH` |
| Above 100% | `BREACH` |

The overall recommendation is `NO-GO` if any constraint breaches policy, `CONDITIONAL` if at least one item requires watching, and `GO` otherwise. These are illustrative portfolio rules, not universal engineering standards. Real thresholds should be approved against site design, redundancy topology, safety requirements, growth forecasts, and organisational risk appetite.

## Repository Structure

```text
data-centre-capacity-planner/
├── .github/workflows/tests.yml
├── data/
│   ├── zones.csv
│   └── proposed_workloads.csv
├── tests/test_capacity_planner.py
├── capacity_planner.py
├── .gitignore
├── LICENSE
└── README.md
```

## Usage

Requires Python 3.10 or later and no third-party packages.

Run the included scenario with a 20% policy reserve:

```bash
python capacity_planner.py
```

Change the reserve and export a structured report:

```bash
python capacity_planner.py --reserve-percent 25 --json-output capacity-report.json
```

Use alternative input files:

```bash
python capacity_planner.py --zones current-capacity.csv --workloads migration-plan.csv
```

## Example Outcome

The included synthetic scenario highlights `Hall-A` power as a capacity-policy breach. The recommendation is therefore `NO-GO` until the deployment is resized, redistributed, or supported by an approved capacity upgrade. The result demonstrates that apparently available rack space alone is not a sufficient deployment decision.

## Testing

Run the complete test suite:

```bash
python -m unittest discover -s tests -v
```

Tests cover reserve calculations, workload quantities, threshold classification, executive recommendations, CSV ingestion, JSON export, invalid reserve values, unknown zones, invalid quantities, and overallocated baseline data.

GitHub Actions runs the tests automatically on pushes and pull requests to `main` using Python 3.10, 3.12, and 3.13, then executes the sample scenario as an integration check.

## Data Ethics and Scope

All zones, capacities, workloads, and operational scenarios are synthetic. The repository contains no employer, client, production, confidential, or site-identifying data.

This tool is a transparent portfolio demonstration, not a substitute for a professional data-centre design review. It does not model electrical phase balance, circuit paths, UPS or generator topology, N+1 component failures, thermal hotspots, network-port capacity, floor loading, fire controls, or regulatory compliance.

## Portfolio Fit

This project complements the existing portfolio by combining facilities and data-centre domain knowledge with data validation, scenario modelling, explainable business rules, automated testing, CI, and structured reporting. It is designed to support conversations about operational consulting as well as technical delivery.

## Future Development

- N, N+1, and 2N topology-aware derating
- Growth forecasting and time-to-exhaustion analysis
- Scenario comparison and workload-placement optimisation
- Cost and energy-efficiency modelling
- Dashboard visualisation and PDF executive reports
- Integration with DCIM or telemetry platforms

## License

Released under the MIT License.
