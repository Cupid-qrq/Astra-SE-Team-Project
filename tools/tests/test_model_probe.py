"""P0 offline tests: schema/transport boundaries, not model quality acceptance."""
import importlib.util
import json
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("model_probe", ROOT / "tools/model_probe.py")
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


class ModelBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.context = json.loads((ROOT / "specs/model/sample-input.json").read_text(encoding="utf-8"))

    def test_public_context_accepts_authored_example_and_rejects_hidden_fields(self):
        probe.validate_context(self.context)
        for key in ("hidden_tests", "reference_code", "api_key", "student_id"):
            with self.subTest(key=key), self.assertRaises(ValueError):
                probe.validate_context({**self.context, key: "PRIVATE"})

    def test_byte_limit_is_not_codepoint_limit(self):
        with self.assertRaises(ValueError):
            probe.validate_context({**self.context, "student_code": "中" * 9000})

    def test_empty_wrong_type_and_nested_extra_fields_are_rejected(self):
        for patch in ({"verdict": "SE"}, {"question": 5}, {"student_code": "   "}, {"public_samples": [{"input": "1", "output": "2", "hidden": True}]}):
            with self.subTest(patch=patch), self.assertRaises(ValueError):
                probe.validate_context({**self.context, **patch})

    def test_output_requires_four_sections_and_dual_size_limits(self):
        sections = {key: "建议需自行验证。" for key in ("error_category", "location_clues", "checks", "learning_advice")}
        self.assertEqual(probe.validate_output(json.dumps(sections, ensure_ascii=False)), sections)
        for value in ({}, {**sections, "tool_calls": []}, {**sections, "checks": "x" * 2001}, {**sections, "checks": []}):
            with self.subTest(value_type=type(value)), self.assertRaises(ValueError):
                probe.validate_output(json.dumps(value))

    def test_config_disabled_by_default_and_no_secret_required_offline(self):
        config = json.loads((ROOT / "specs/model/config.example.json").read_text(encoding="utf-8"))
        probe.validate_config(config)
        self.assertFalse(config["enabled"])
        self.assertEqual(config["daily_budget_cny"], "20.00")
        self.assertEqual(config["project_budget_cny"], "500.00")
        with self.assertRaises(ValueError):
            probe.validate_config({**config, "enabled": True})

    def test_no_network_path_is_available_in_p0_offline_probe(self):
        result = probe.offline_check(self.context)
        self.assertEqual(result["mode"], "offline")
        self.assertFalse(result["network_called"])
        self.assertIsNone(result["actual_cost_cny"])
        self.assertNotIn("student_code", json.dumps(result))


if __name__ == "__main__":
    unittest.main()
