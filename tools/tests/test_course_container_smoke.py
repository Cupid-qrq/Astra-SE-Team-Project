"""Offline controller boundaries; real containers are tested separately on Linux."""

import importlib.util
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location(
    "course_smoke", ROOT / "tools/course_container_smoke.py"
)
smoke = importlib.util.module_from_spec(spec)
spec.loader.exec_module(smoke)
IMAGE = "sha256:" + "a" * 64
NAME = "astra-course-" + "a" * 32 + "-run"
VOLUME = "astra-course-" + "a" * 32 + "-work"


class ContainerPolicyTests(unittest.TestCase):
    def test_requires_pinned_image_and_owned_names(self):
        for image, name, volume in [
            ("latest", NAME, VOLUME),
            (IMAGE, "other", VOLUME),
            (IMAGE, NAME, "/etc"),
        ]:
            with (
                self.subTest(image=image, name=name, volume=volume),
                self.assertRaises(ValueError),
            ):
                smoke.restricted_args(image, name, volume, "run", "cpp17")

    def test_phase_and_language_limits(self):
        for phase, lang, memory, pids, cpu in [
            ("compile", "cpp17", 536870912, 30, 20),
            ("run", "cpp17", 268435456, 1, 2),
            ("run", "python3", 268435456, 1, 4),
        ]:
            with self.subTest(phase=phase, lang=lang):
                args = smoke.restricted_args(IMAGE, NAME, VOLUME, phase, lang)
                for expected in [
                    "--network=none",
                    "--read-only",
                    "--read-only-tmpfs=false",
                    "--ipc=none",
                    "--user=65534:65534",
                    "--cap-drop=ALL",
                    "--security-opt=no-new-privileges",
                    "--pull=never",
                    "--log-driver=none",
                    "--memory=" + str(memory),
                    "--memory-swap=" + str(memory),
                    "--pids-limit=" + str(pids),
                    f"--ulimit=cpu={cpu}:{cpu}",
                    "--ulimit=fsize=1048576:1048576",
                ]:
                    self.assertIn(expected, args)
                self.assertNotIn(
                    "--dns=none", args
                )  # Podman rejects DNS flags with network=none.
                self.assertNotIn("--privileged", args)
                self.assertNotIn("--init", args)
                self.assertEqual(args[-1], IMAGE)
                self.assertIn(VOLUME + ":/work:rw,nocopy", args)
                self.assertFalse(any("/var/run" in a or "type=bind" in a for a in args))

    def test_inspection_rejects_weakened_limits(self):
        config = smoke.expected_config("run", "cpp17")
        smoke.verify_config(config, "run", "cpp17", VOLUME)
        for key, value in [
            ("Memory", 0),
            ("PidsLimit", 30),
            ("NetworkMode", "host"),
            ("ReadonlyRootfs", False),
        ]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                smoke.verify_config(
                    dict(config, **{key: value}), "run", "cpp17", VOLUME
                )

    def test_expanded_cap_drop_all_is_accepted_but_partial_drop_or_add_is_rejected(
        self,
    ):
        expanded = [
            "CAP_CHOWN",
            "CAP_DAC_OVERRIDE",
            "CAP_FOWNER",
            "CAP_FSETID",
            "CAP_KILL",
            "CAP_NET_BIND_SERVICE",
            "CAP_NET_RAW",
            "CAP_SETFCAP",
            "CAP_SETGID",
            "CAP_SETPCAP",
            "CAP_SETUID",
            "CAP_SYS_CHROOT",
        ]
        config = dict(smoke.expected_config("run", "cpp17"), CapDrop=expanded)
        smoke.verify_config(config, "run", "cpp17", VOLUME)
        for mutation in [{"CapDrop": expanded[1:]}, {"CapAdd": ["CAP_SYS_ADMIN"]}]:
            with self.subTest(patch=mutation), self.assertRaises(ValueError):
                smoke.verify_config(dict(config, **mutation), "run", "cpp17", VOLUME)

    def test_volume_accepts_engine_metadata_but_never_weaker_quota(self):
        options = {
            "type": "tmpfs",
            "device": "tmpfs",
            "o": "size=33554432,uid=65534,gid=65534,mode=0700,nodev,nosuid",
            "UID": "65534",
            "GID": "65534",
            "SIZE": "33554432",
        }
        volume = {"Driver": "local", "UID": 65534, "GID": 65534, "Options": options}
        smoke.verify_volume(volume)
        with self.assertRaises(ValueError):
            smoke.verify_volume(dict(volume, Options=dict(options, o="size=67108864")))

    def test_cleanup_failure_is_never_pass(self):
        events = []

        def execute(image, prefix):
            events.append("execute")
            return [{"passed": True}]

        def cleanup(prefix):
            events.append("cleanup")
            return False

        result = smoke.run_smoke(IMAGE, "b" * 40, execute=execute, cleanup=cleanup)
        self.assertFalse(result["passed"])
        self.assertFalse(result["cleanup_confirmed"])
        self.assertEqual(events, ["execute", "cleanup"])

    def test_cleanup_never_removes_a_foreign_resource_or_volume_after_unknown_exit(
        self,
    ):
        exists = smoke.Result(0, b"", b"", False, False, 1)
        foreign = {
            "Config": {"Labels": {smoke.LABEL: "other"}},
            "State": {"Running": True},
        }
        with (
            patch.object(smoke, "bounded_process", return_value=exists),
            patch.object(smoke, "inspect_container", return_value=foreign),
            patch.object(smoke, "control") as control,
        ):
            self.assertFalse(smoke.cleanup_resources(NAME.rsplit("-", 1)[0]))
            control.assert_not_called()

    def test_configuration_checks_require_a_single_named_work_volume(self):
        item = {
            "HostConfig": smoke.expected_config("run", "cpp17"),
            "Config": {"User": "65534:65534"},
            "Mounts": [{"Type": "bind", "Name": VOLUME, "Destination": "/work"}],
        }
        with self.assertRaises(ValueError):
            smoke.verify_inspection(item, "run", "cpp17", VOLUME)

    def test_time_budget_applies_to_entire_round(self):
        self.assertEqual(smoke.ROUND_SECONDS, 360)
        with patch.object(smoke.time, "monotonic", return_value=500):
            self.assertEqual(smoke.remaining_timeout(15, 505), 5)
            with self.assertRaises(ValueError):
                smoke.remaining_timeout(15, 499)

    def test_report_binds_the_controller_content_and_has_no_fake_metrics(self):
        import hashlib

        cases = [
            {"passed": True, "cpu_ms": None, "memory_bytes": None} for _ in range(6)
        ]
        report = smoke.run_smoke(
            IMAGE, "b" * 40, execute=lambda *a: cases, cleanup=lambda p: True
        )
        self.assertTrue(report["passed"])
        self.assertEqual(
            report["controller_sha256"],
            hashlib.sha256(
                (ROOT / "tools/course_container_smoke.py").read_bytes()
            ).hexdigest(),
        )
        self.assertIsNone(report["cases"][0]["cpu_ms"])

    def _execute_with_states(self, case, compile_state, run_state=None):
        prefix = NAME.rsplit("-", 1)[0]
        states = {
            prefix + "-hold": {"Running": True},
            prefix + "-compile": compile_state,
            prefix + "-run": run_state,
        }

        def inspect(name):
            return {"State": states[name]}

        def control(args, *unused, **kwargs):
            return b"[{}]" if args[:2] == ["volume", "inspect"] else b""

        compiled = smoke.Result(1 if case == "error" else 0, b"", b"", False, False, 1)
        ran = smoke.Result(0, b"3", b"", False, False, 1)
        with (
            patch.object(smoke, "control", side_effect=control),
            patch.object(smoke, "verify_volume"),
            patch.object(smoke, "verify_inspection"),
            patch.object(smoke, "inspect_container", side_effect=inspect),
            patch.object(smoke, "bounded_process", side_effect=[compiled, ran]),
        ):
            return smoke.execute_case(IMAGE, prefix, "cpp17", case)

    def test_compile_error_requires_container_terminal_state(self):
        state = {"Running": True, "StartedAt": "2026-11-02T00:00:00Z", "ExitCode": 1}
        with self.assertRaises(ValueError):
            self._execute_with_states("error", state)

    def test_normal_output_requires_container_terminal_success(self):
        compiled = {
            "Running": False,
            "StartedAt": "2026-11-02T00:00:00Z",
            "ExitCode": 0,
        }
        running = {"Running": True, "StartedAt": "2026-11-02T00:00:00Z", "ExitCode": 0}
        with self.assertRaises(ValueError):
            self._execute_with_states("normal", compiled, running)
        failed = dict(running, Running=False, ExitCode=1)
        with self.assertRaises(ValueError):
            self._execute_with_states("normal", compiled, failed)

    def test_terminal_compilation_and_execution_still_pass(self):
        state = {"Running": False, "StartedAt": "2026-11-02T00:00:00Z", "ExitCode": 0}
        self.assertTrue(self._execute_with_states("normal", state, state)["passed"])
        self.assertTrue(
            self._execute_with_states("error", dict(state, ExitCode=1))["passed"]
        )

    def test_interrupted_controller_residue_blocks_next_slot(self):
        for residual in [(b"old-container", b""), (b"", b"old-volume")]:
            with (
                self.subTest(residual=residual),
                patch.object(smoke, "control", side_effect=residual),
                self.assertRaises(ValueError),
            ):
                smoke.require_clean_slot()
        with (
            patch.object(smoke, "control", side_effect=ValueError("unknown")),
            self.assertRaises(ValueError),
        ):
            smoke.require_clean_slot()
        with patch.object(smoke, "control", return_value=b""):
            smoke.require_clean_slot()

    def test_control_failure_reports_only_a_fixed_diagnostic_code(self):
        def execute(image, prefix):
            raise smoke.SmokeFailure("CONTAINER_CONFIG_DRIFT")

        result = smoke.run_smoke(
            IMAGE, "b" * 40, execute=execute, cleanup=lambda p: True
        )
        self.assertEqual(result["error"], "CONTAINER_CONFIG_DRIFT")

    def test_execution_error_still_cleans_and_does_not_disclose_exception(self):
        events = []

        def execute(image, prefix):
            raise ValueError("PRIVATE SOURCE OR CREDENTIAL")

        result = smoke.run_smoke(
            IMAGE, "b" * 40, execute=execute, cleanup=lambda p: events.append(p) or True
        )
        self.assertFalse(result["passed"])
        self.assertEqual(len(events), 1)
        self.assertNotIn("PRIVATE", str(result))
        self.assertNotIn("stdout", result)


class BoundedProcessTests(unittest.TestCase):
    def test_captures_success_in_memory(self):
        result = smoke.bounded_process(
            [sys.executable, "-c", "import sys; print(sys.stdin.read())"],
            b"public",
            5,
            1024,
        )
        self.assertEqual(result.returncode, 0)
        self.assertEqual(result.stdout.strip(), b"public")
        self.assertFalse(result.timed_out)
        self.assertFalse(result.overflow)

    def test_wall_timeout_stops_client(self):
        result = smoke.bounded_process(
            [sys.executable, "-c", "import time; time.sleep(30)"], b"", 0.1, 1024
        )
        self.assertTrue(result.timed_out)
        self.assertLess(result.duration_ms, 4000)
        self.assertIsNotNone(result.returncode)

    def test_combined_output_is_bounded(self):
        result = smoke.bounded_process(
            [
                sys.executable,
                "-c",
                "import os; os.write(1,b'x'*100000); os.write(2,b'y'*100000)",
            ],
            b"",
            5,
            4096,
        )
        self.assertTrue(result.overflow)
        self.assertLessEqual(len(result.stdout) + len(result.stderr), 4096)
        self.assertIsNotNone(result.returncode)


if __name__ == "__main__":
    unittest.main()
