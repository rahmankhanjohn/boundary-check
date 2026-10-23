#!/usr/bin/env python3
"""boundary-check: analyze service dependency graph and flag services that always deploy together.

Reads a dependency file (JSON or CSV) and checks:
- Services that always deploy together (likely should be one service)
- Services with no dependents (candidates for consolidation)
- Circular dependencies
- Deployment frequency per service

Zero dependencies. Single file. MIT license.
"""

import os
import sys
import json
import csv

VERSION = "1.0.0"


def load_dependencies(filepath):
    """Load service dependencies from JSON or CSV.

    JSON format: {"services": [{"name": "svc-a", "depends_on": ["svc-b"], "deploy_count": 5}]}
    CSV format: service,depends_on,deploy_count
    """
    ext = os.path.splitext(filepath)[1].lower()
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except (OSError, IOError):
        return None

    if ext == '.json':
        try:
            data = json.loads(content)
            return data.get('services', data if isinstance(data, list) else [])
        except json.JSONDecodeError:
            return None
    elif ext == '.csv':
        services = []
        reader = csv.DictReader(content.splitlines())
        for row in reader:
            svc = {
                'name': row.get('service', row.get('name', '')),
                'depends_on': [d.strip() for d in row.get('depends_on', '').split(',') if d.strip()],
                'deploy_count': int(row.get('deploy_count', row.get('deploys', 0)) or 0),
            }
            services.append(svc)
        return services
    return None


def analyze(services):
    """Analyze service dependencies. Returns findings and metrics."""
    if not services:
        return {'services': 0, 'findings': [], 'co_deploy_pairs': [], 'orphans': [], 'cycles': [], 'score': 100, 'report_line': 'Boundary check: services=0, issues=0, co-deploy pairs=0, circular=0, score=100/100', 'errors': 0, 'warnings': 0}

    name_set = {s['name'] for s in services}
    svc_map = {s['name']: s for s in services}

    findings = []
    co_deploy_pairs = []
    orphans = []
    cycles = []

    # Check for services that always deploy together
    # (heuristic: if two services have identical deploy counts and depend on each other, flag them)
    for i, a in enumerate(services):
        for b in services[i+1:]:
            # Check mutual dependency
            a_deps = set(a.get('depends_on', []))
            b_deps = set(b.get('depends_on', []))
            if a['name'] in b_deps and b['name'] in a_deps:
                co_deploy_pairs.append((a['name'], b['name']))
                findings.append({
                    'type': 'CO_DEPLOY',
                    'services': [a['name'], b['name']],
                    'severity': 'WARNING',
                    'issue': f'{a["name"]} and {b["name"]} depend on each other. Consider merging.',
                })

    # Check for orphans (no dependents)
    dependents = set()
    for s in services:
        for dep in s.get('depends_on', []):
            dependents.add(dep)
    for s in services:
        if s['name'] not in dependents and s.get('deploy_count', 0) > 0:
            # Only flag if it has no dependents and low deploy count
            if s.get('deploy_count', 0) <= 2:
                orphans.append(s['name'])
                findings.append({
                    'type': 'ORPHAN',
                    'services': [s['name']],
                    'severity': 'INFO',
                    'issue': f'{s["name"]} has no dependents and low deploy count. Candidate for consolidation.',
                })

    # Check for circular dependencies (3+ cycle)
    for start in services:
        visited = set()
        stack = [(start['name'], [start['name']])]
        while stack:
            current, path = stack.pop()
            if current in visited:
                continue
            visited.add(current)
            svc = svc_map.get(current)
            if not svc:
                continue
            for dep in svc.get('depends_on', []):
                if dep == start['name'] and len(path) > 2:
                    cycle = path + [dep]
                    if cycle not in cycles:
                        cycles.append(cycle)
                        findings.append({
                            'type': 'CIRCULAR',
                            'services': path,
                            'severity': 'ERROR',
                            'issue': f'Circular dependency: {" -> ".join(path + [dep])}',
                        })
                elif dep not in path:
                    stack.append((dep, path + [dep]))

    # Check for services that always deploy together (same deploy count, high)
    deploy_groups = {}
    for s in services:
        dc = s.get('deploy_count', 0)
        deploy_groups.setdefault(dc, []).append(s['name'])
    for dc, names in deploy_groups.items():
        if len(names) >= 2 and dc > 0:
            # Check if they also depend on each other
            pair = (names[0], names[1])
            if pair not in [(p[0], p[1]) for p in co_deploy_pairs] and (names[1], names[0]) not in [(p[0], p[1]) for p in co_deploy_pairs]:
                # Only flag if they have a dependency relationship
                has_rel = False
                for a in names:
                    for b in names:
                        if a != b and a in svc_map.get(b, {}).get('depends_on', []):
                            has_rel = True
                if has_rel:
                    co_deploy_pairs.append((names[0], names[1]))
                    findings.append({
                        'type': 'CO_DEPLOY',
                        'services': names[:2],
                        'severity': 'WARNING',
                        'issue': f'{names[0]} and {names[1]} always deploy together ({dc} deploys). Consider merging.',
                    })

    # Deployment frequency analysis
    total_deploys = sum(s.get('deploy_count', 0) for s in services)
    low_freq = [s['name'] for s in services if s.get('deploy_count', 0) <= 1 and s.get('deploy_count', 0) >= 0]
    # Only flag if there are multiple services with very low frequency
    if len(low_freq) >= 2 and total_deploys > 0:
        findings.append({
            'type': 'LOW_FREQ',
            'services': low_freq,
            'severity': 'INFO',
            'issue': f'{len(low_freq)} service(s) have 0-1 deploys. Candidates for consolidation or removal.',
        })

    # Score: 100 - (errors * 25 + warnings * 10 + info * 3)
    errors = sum(1 for f in findings if f['severity'] == 'ERROR')
    warnings = sum(1 for f in findings if f['severity'] == 'WARNING')
    infos = sum(1 for f in findings if f['severity'] == 'INFO')
    score = max(0, 100 - errors * 25 - warnings * 10 - infos * 3)

    # Report line
    real_issues = [f for f in findings if f['severity'] in ('ERROR', 'WARNING')]
    report_line = (
        f"Boundary check: services={len(services)}, issues={len(real_issues)}, "
        f"co-deploy pairs={len(co_deploy_pairs)}, circular={len(cycles)}, score={score}/100"
    )

    return {
        'services': len(services),
        'findings': findings,
        'co_deploy_pairs': co_deploy_pairs,
        'orphans': orphans,
        'cycles': cycles,
        'score': score,
        'report_line': report_line,
        'errors': errors,
        'warnings': warnings,
    }


def run_check(filepath, report=False, json_output=False):
    services = load_dependencies(filepath)
    if services is None:
        print(f"Error: could not parse {filepath}", file=sys.stderr)
        sys.exit(2)

    result = analyze(services)

    if json_output:
        import json as j
        print(j.dumps(result, indent=2))
    elif report:
        print(result['report_line'])
    else:
        print(f"Boundary Check: {filepath}")
        print(f"  Services: {result['services']}")
        print(f"  Score: {result['score']}/100")
        if result['findings']:
            print("  Findings:")
            for f in result['findings']:
                print(f"    [{f['severity']}] {f['issue']}")
        if result['co_deploy_pairs']:
            print(f"  Co-deploy pairs: {result['co_deploy_pairs']}")
        if result['cycles']:
            print(f"  Circular dependencies: {result['cycles']}")
        print(f"  Report line: {result['report_line']}")

    errors = result['errors']
    return 0 if errors == 0 else 1


def main():
    if len(sys.argv) < 2 or sys.argv[1] in ('-h', '--help'):
        print("Usage: boundary-check <file.json|file.csv> [--report] [--json]")
        print("  Analyzes service dependency graph for co-deploy pairs and circular deps.")
        print("  Exit code 0 if no errors, 1 otherwise.")
        sys.exit(0)

    filepath = sys.argv[1]
    report = '--report' in sys.argv
    json_output = '--json' in sys.argv

    if not os.path.isfile(filepath):
        print(f"Error: {filepath} is not a file", file=sys.stderr)
        sys.exit(2)

    exit_code = run_check(filepath, report=report, json_output=json_output)
    sys.exit(exit_code)


if __name__ == '__main__':
    main()
