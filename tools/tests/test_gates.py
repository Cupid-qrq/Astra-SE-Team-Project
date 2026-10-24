import os
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]

class PushDestinationTests(unittest.TestCase):
    def test_independent_pushurl_is_rejected_before_other_checks(self):
        env = os.environ.copy()
        env.update(GIT_CONFIG_COUNT='1', GIT_CONFIG_KEY_0='remote.origin.pushurl',
                   GIT_CONFIG_VALUE_0='https://example.invalid/other.git')
        result = subprocess.run(['pwsh', '-NoProfile', '-File', str(ROOT / 'tools/pre_push.ps1')],
                                cwd=ROOT, env=env, capture_output=True, text=True, encoding='utf-8')
        self.assertNotEqual(result.returncode, 0)
        self.assertIn('push URL', result.stdout + result.stderr)

class RuntimeGateTests(unittest.TestCase):
    def test_runtime_walk_prunes_dependencies_and_generated_artifacts(self):
        import tempfile
        from unittest.mock import patch
        module = self.runtime_module()
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            for name in ('apps/web/src/main.tsx', 'apps/web/node_modules/dep/README.md',
                         'apps/web/dist/index.html', 'apps/web/test-results/run/error.md'):
                path = root / name
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text('sample', encoding='utf-8')
            with patch.object(module, 'ROOT', root):
                self.assertEqual(list(module.runtime_files()), ['apps/web/src/main.tsx'])

    def test_planning_checkout_skips_runtime_without_error(self):
        from unittest.mock import patch
        module = self.runtime_module()
        with patch.object(module, 'runtime_files', return_value=[]):
            self.assertEqual(module.main(), 0)

    def runtime_module(self):
        import importlib.util
        path = ROOT / 'tools/check_runtime.py'
        self.assertTrue(path.is_file(), 'missing executable runtime gate')
        spec = importlib.util.spec_from_file_location('check_runtime', path)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def test_failed_runtime_command_propagates_nonzero(self):
        module = self.runtime_module()
        self.assertEqual(module.run_runtime_check(ROOT / 'tools/tests/fixtures/fail.ps1'), 7)

    def test_successful_runtime_command_is_actually_executed(self):
        module = self.runtime_module()
        self.assertEqual(module.run_runtime_check(ROOT / 'tools/tests/fixtures/pass.ps1'), 0)

    def test_business_files_require_checks_but_cache_and_readmes_do_not(self):
        module = self.runtime_module()
        self.assertFalse(module.requires_runtime(['server/README.md', 'apps/web/node_modules/x.js', 'server/.venv/a.py', 'tools/tests/test_gates.py']))
        for path in ['server/app/main.py', 'apps/web/package.json', 'tests/e2e/start.spec.ts', 'infra/compose.yaml']:
            with self.subTest(path=path):
                self.assertTrue(module.requires_runtime([path]))

    def test_missing_runtime_entry_fails_closed(self):
        module = self.runtime_module()
        self.assertNotEqual(module.run_runtime_check(ROOT / 'tools/tests/fixtures/missing.ps1'), 0)

class TraceabilityTests(unittest.TestCase):
    def run_mutation(self, change):
        import contextlib
        import io
        import json
        from unittest.mock import patch
        sys.path.insert(0, str(ROOT / 'tools'))
        import check_repository
        original_read = Path.read_text
        trace_path = ROOT / 'specs/traceability.json'
        trace = json.loads(original_read(trace_path, encoding='utf-8'))
        change(trace)
        def read(path, *args, **kwargs):
            if path.resolve() == trace_path.resolve():
                return json.dumps(trace)
            return original_read(path, *args, **kwargs)
        with patch.object(Path, 'read_text', read), contextlib.redirect_stdout(io.StringIO()) as out:
            code = check_repository.main()
        return code, out.getvalue()

    def test_dependency_cycle_is_rejected(self):
        def change(trace):
            for task in trace['tasks']:
                if task['id'] == 'P1-B2':
                    task['depends_on'] = ['P1-B3']
        code, output = self.run_mutation(change)
        self.assertNotEqual(code, 0, output)

    def test_nonexistent_api_mapping_is_rejected(self):
        code, output = self.run_mutation(lambda t: t['FR'][0].update(api=['POST /missing-route']))
        self.assertNotEqual(code, 0, output)

    def test_requirement_scheduled_before_its_task_is_rejected(self):
        code, output = self.run_mutation(lambda t: t['FR'][0].update(tasks=['P3-A1']))
        self.assertNotEqual(code, 0, output)

if __name__ == '__main__':
    unittest.main()
