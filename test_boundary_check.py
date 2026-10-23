import os
import tempfile
import json
import unittest
from boundary_check import analyze, load_dependencies


class TestBoundaryCheck(unittest.TestCase):

    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        import shutil
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _write_json(self, data):
        path = os.path.join(self.tmpdir, 'deps.json')
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f)
        return path

    def test_load_json(self):
        data = {"services": [{"name": "svc-a", "depends_on": ["svc-b"], "deploy_count": 5}]}
        path = self._write_json(data)
        services = load_dependencies(path)
        self.assertEqual(len(services), 1)
        self.assertEqual(services[0]['name'], 'svc-a')

    def test_load_csv(self):
        path = os.path.join(self.tmpdir, 'deps.csv')
        with open(path, 'w', encoding='utf-8') as f:
            f.write('service,depends_on,deploy_count\nsvc-a,svc-b,5\nsvc-b,,3\n')
        services = load_dependencies(path)
        self.assertEqual(len(services), 2)
        self.assertEqual(services[0]['name'], 'svc-a')
        self.assertEqual(services[0]['depends_on'], ['svc-b'])

    def test_co_deploy_pair(self):
        data = {"services": [
            {"name": "svc-a", "depends_on": ["svc-b"], "deploy_count": 5},
            {"name": "svc-b", "depends_on": ["svc-a"], "deploy_count": 5},
        ]}
        path = self._write_json(data)
        services = load_dependencies(path)
        result = analyze(services)
        self.assertTrue(len(result['co_deploy_pairs']) > 0)

    def test_circular_dependency(self):
        data = {"services": [
            {"name": "svc-a", "depends_on": ["svc-b"], "deploy_count": 5},
            {"name": "svc-b", "depends_on": ["svc-c"], "deploy_count": 5},
            {"name": "svc-c", "depends_on": ["svc-a"], "deploy_count": 5},
        ]}
        path = self._write_json(data)
        services = load_dependencies(path)
        result = analyze(services)
        self.assertTrue(len(result['cycles']) > 0)

    def test_no_issues(self):
        data = {"services": [
            {"name": "order", "depends_on": [], "deploy_count": 10},
            {"name": "payment", "depends_on": ["order"], "deploy_count": 8},
            {"name": "inventory", "depends_on": ["order"], "deploy_count": 6},
        ]}
        path = self._write_json(data)
        services = load_dependencies(path)
        result = analyze(services)
        self.assertEqual(result['errors'], 0)

    def test_orphan_detection(self):
        data = {"services": [
            {"name": "order", "depends_on": [], "deploy_count": 10},
            {"name": "legacy", "depends_on": [], "deploy_count": 1},
        ]}
        path = self._write_json(data)
        services = load_dependencies(path)
        result = analyze(services)
        self.assertIn('legacy', result['orphans'])

    def test_report_line(self):
        data = {"services": [
            {"name": "svc-a", "depends_on": ["svc-b"], "deploy_count": 5},
            {"name": "svc-b", "depends_on": ["svc-a"], "deploy_count": 5},
        ]}
        path = self._write_json(data)
        services = load_dependencies(path)
        result = analyze(services)
        self.assertIn('Boundary check:', result['report_line'])
        self.assertIn('score=', result['report_line'])

    def test_empty_services(self):
        result = analyze([])
        self.assertEqual(result['services'], 0)
        self.assertEqual(result['score'], 100)


if __name__ == '__main__':
    unittest.main()
