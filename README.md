# boundary-check

![Tests](https://github.com/rahmankhanjohn/boundary-check/actions/workflows/test.yml/badge.svg)
![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)
![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)
![Dependencies: 0](https://img.shields.io/badge/dependencies-0-brightgreen.svg)
![Tests: 8](https://img.shields.io/badge/tests-8%20passing-brightgreen.svg)
![GitHub stars](https://img.shields.io/github/stars/rahmankhanjohn/boundary-check?style=social)
![Last commit](https://img.shields.io/github/last-commit/rahmankhanjohn/boundary-check)


Analyze service dependency graphs and flag services that should not exist separately.

Microservices fail at boundaries. This tool reads a service dependency file (JSON or CSV) and checks for co-deploy pairs, circular dependencies, orphan services, and low-frequency services that are candidates for consolidation.

## What it checks

- **Co-deploy pairs** — two services that always deploy together (likely should be one)
- **Circular dependencies** — A depends on B depends on C depends on A
- **Orphan services** — services with no dependents and low deploy count
- **Low-frequency services** — services with 0-1 deploys (candidates for removal)

## Usage

```bash
python boundary_check.py services.json
python boundary_check.py services.csv
python boundary_check.py services.json --report
python boundary_check.py services.json --json
```

## Input formats

**JSON:**
```json
{"services": [{"name": "order", "depends_on": ["payment"], "deploy_count": 10}]}
```

**CSV:**
```csv
service,depends_on,deploy_count
order,payment,10
payment,,8
```

## Exit codes

- 0: no errors
- 1: errors found (circular dependencies)
- 2: bad path

## Requirements

Python 3.9+, no dependencies.

## License

MIT
