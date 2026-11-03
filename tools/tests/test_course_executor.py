"""Controller protocol tests use public fixtures, never real student material."""

import base64
import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("course_executor", ROOT / "tools/course_executor.py")
executor = importlib.util.module_from_spec(spec)
spec.loader.exec_module(executor)


def request():
    return {
        "operation": "execute",
        "execution_id": "a" * 64,
        "request_hash": "b" * 64,
        "image": "sha256:" + "c" * 64,
        "language": "python3",
        "code": base64.b64encode(b"print(input())").decode(),
        "stdin": base64.b64encode(b"public").decode(),
    }


class ProtocolTests(unittest.TestCase):
    def test_validated_request_decodes_private_fields_without_repr_leak(self):
        value = executor.validate_request(request())
        self.assertEqual(value.code, b"print(input())")
        self.assertEqual(value.stdin, b"public")
        self.assertNotIn("print(input())", repr(value))

    def test_unknown_fields_tags_and_oversized_code_rejected(self):
        for change in (
            {"shell": "sh"},
            {"image": "latest"},
            {"execution_id": "../other"},
            {"language": "bash"},
            {"code": base64.b64encode(b"a" * 65537).decode()},
        ):
            with self.subTest(change=list(change)), self.assertRaises(ValueError):
                executor.validate_request(dict(request(), **change))

    def test_invalid_encoding_does_not_preserve_secret_exception_context(self):
        with self.assertRaises(ValueError) as failure:
            executor.validate_request(
                dict(request(), code=base64.b64encode(b"SECRET\xff").decode())
            )
        self.assertIsNone(failure.exception.__context__)
        self.assertIsNone(failure.exception.__cause__)
        self.assertNotIn("SECRET", str(failure.exception))

    def test_completed_request_replays_without_executing_again(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".local") as folder:
            calls = []

            def run(value):
                calls.append(value.execution_id)
                return {
                    "diagnosis": None,
                    "exit_code": 0,
                    "stdout": "Mw==",
                    "cleanup_confirmed": True,
                }

            first = executor.dispatch(request(), folder, run)
            self.assertEqual(executor.dispatch(request(), folder, run), first)
            self.assertEqual(len(calls), 1)

    def test_cancel_tombstone_rejects_late_create(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".local") as folder:
            value = request()
            executor.dispatch(
                {"operation": "cancel", "execution_id": value["execution_id"]},
                folder,
                lambda r: None,
            )
            with self.assertRaises(ValueError):
                executor.dispatch(value, folder, lambda r: self.fail("late creation"))

    def test_changed_request_with_same_execution_identity_is_rejected(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".local") as folder:
            value = request()
            executor.dispatch(value, folder, lambda r: {"cleanup_confirmed": True})
            with self.assertRaises(ValueError):
                executor.dispatch(
                    dict(value, stdin=base64.b64encode(b"changed").decode()),
                    folder,
                    lambda r: self.fail("duplicate"),
                )

    def test_started_journal_never_reexecutes_after_controller_failure(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".local") as folder:

            def crash(value):
                raise RuntimeError("synthetic interruption")

            with self.assertRaises(RuntimeError):
                executor.dispatch(request(), folder, crash)
            with self.assertRaises(ValueError):
                executor.dispatch(request(), folder, lambda r: self.fail("re-executed"))

    def test_unconfirmed_cleanup_never_becomes_completed(self):
        with tempfile.TemporaryDirectory(dir=ROOT / ".local") as folder:
            with self.assertRaises(ValueError):
                executor.dispatch(request(), folder, lambda r: {"cleanup_confirmed": False})
            with self.assertRaises(ValueError):
                executor.dispatch(request(), folder, lambda r: self.fail("re-executed"))

    def test_diagnosis_uses_container_stage_not_client_status(self):
        self.assertEqual(executor.diagnose("compile", 1, False, False, False, None), "CE")
        self.assertEqual(executor.diagnose("run", 1, False, False, False, None), "RE")
        self.assertEqual(executor.diagnose("run", 0, True, False, False, None), "TLE")
        self.assertEqual(executor.diagnose("run", 0, False, True, False, None), "RE")
        self.assertEqual(executor.diagnose("run", 137, False, False, True, None), "RE")
        self.assertEqual(executor.diagnose("run", 137, False, False, False, None), "SE")
        self.assertIsNone(executor.diagnose("run", 0, False, False, False, None))

    def test_runtime_finally_always_cleans_and_discloses_no_exception_text(self):
        calls = []

        def broken(value):
            raise RuntimeError("SECRET_CONTAINER_OUTPUT")

        result = executor.execute_safely(
            validate_request_for_test(), broken, lambda identity: calls.append(identity) or True
        )
        self.assertEqual(result["diagnosis"], "SE")
        self.assertTrue(result["cleanup_confirmed"])
        self.assertEqual(calls, ["a" * 64])
        self.assertNotIn("SECRET", str(result))

    def test_cleanup_failure_overrides_success(self):
        result = executor.execute_safely(
            validate_request_for_test(),
            lambda r: {"diagnosis": None, "stdout": "Mw=="},
            lambda identity: False,
        )
        self.assertEqual(result["diagnosis"], "SE")
        self.assertFalse(result["cleanup_confirmed"])
        self.assertNotIn("stdout", result)

    def test_cpu_limit_requires_measured_budget_not_just_signal9(self):
        self.assertTrue(executor.cpu_exceeded(2004311460, 2000))
        self.assertFalse(executor.cpu_exceeded(1000000000, 2000))
        self.assertFalse(executor.cpu_exceeded(None, 2000))
        self.assertEqual(
            executor.diagnose(
                "run", 137, False, False, False, executor.cpu_exceeded(2004311460, 2000)
            ),
            "TLE",
        )

    def test_runtime_uses_separate_retained_accounting_group_without_conmon(self):
        sys.path.insert(0, str(ROOT / "tools"))
        try:
            import course_runtime

            args = course_runtime.run_args(
                validate_request_for_test(), "astra-course-" + "a" * 32 + "-work"
            )
        finally:
            sys.path.pop(0)
        self.assertIn("--cgroups=no-conmon", args)
        self.assertIn("--cgroup-parent=/astra-exec-" + "a" * 64, args)
        self.assertIn("--ulimit=cpu=4:4", args)


def validate_request_for_test():
    return executor.validate_request(request())


if __name__ == "__main__":
    unittest.main()
