"""Validate synthetic quality inputs; this does not execute or judge programs."""

import json
import re
import unittest
from collections import Counter
from pathlib import Path

from tools.model_probe import canonical, unique_object, validate_context
from tools.model_quality import digest, freeze

MODEL = Path(__file__).resolve().parents[2] / "specs" / "model"


class FixedQualityCasesTests(unittest.TestCase):
    def artifact(self, filename):
        path = MODEL / filename
        self.assertTrue(path.is_file(), f"Missing fixed quality artifact: {filename}")
        return json.loads(path.read_text(encoding="utf-8"), object_pairs_hook=unique_object)

    def test_fixed_set_has_unique_ids_and_required_verdict_language_distribution(self):
        cases = self.artifact("quality-cases.json")
        self.assertIsInstance(cases, list)
        self.assertEqual(len(cases), 30)
        self.assertEqual(len({case["case_id"] for case in cases}), 30)
        self.assertEqual(len({case["context"]["student_code"] for case in cases}), 30)
        self.assertEqual(
            Counter(case["context"]["verdict"] for case in cases),
            Counter(CE=10, WA=8, TLE=8, RE=4),
        )
        for language in ("cpp17", "python3"):
            self.assertEqual(
                Counter(
                    case["context"]["verdict"]
                    for case in cases
                    if case["context"]["language_key"] == language
                ),
                Counter(CE=5, WA=4, TLE=4, RE=2),
            )
        for case in cases:
            with self.subTest(case=case["case_id"]):
                self.assertRegex(case["case_id"], r"^Q-(CE|WA|TLE|RE)-[0-9]{2}$")
                self.assertEqual(case["case_id"].split("-")[1], case["context"]["verdict"])

    def test_every_provider_context_satisfies_input_schema_and_byte_caps(self):
        for case in self.artifact("quality-cases.json"):
            with self.subTest(case=case["case_id"]):
                context = case["context"]
                self.assertEqual(validate_context(context), context)
                self.assertLessEqual(len(canonical(context).encode("utf-8")), 24 * 1024)
                for sample in context["public_samples"]:
                    for part in sample.values():
                        self.assertLessEqual(len(part.encode("utf-8")), 4096)
                self.assertTrue(context["public_problem"].strip())
                self.assertTrue(context["question"].strip())
                self.assertNotRegex(
                    context["sanitized_diagnostic"],
                    r"(?:[A-Za-z]:\\|/home/|/Users/|sk-[A-Za-z0-9])",
                )

    def test_review_annotations_are_required_and_outside_provider_context(self):
        for case in self.artifact("quality-cases.json"):
            with self.subTest(case=case["case_id"]):
                self.assertEqual(
                    set(case), {"case_id", "context", "expected_cause", "allowed_scope"}
                )
                for key in ("expected_cause", "allowed_scope"):
                    self.assertIsInstance(case[key], str)
                    self.assertTrue(case[key].strip())
                    self.assertNotIn(key, case["context"])

    def test_case_metadata_can_freeze_with_the_existing_acceptance_calculator(self):
        cases = self.artifact("quality-cases.json")
        manifest_cases = [
            dict(
                case_id=case["case_id"],
                verdict=case["context"]["verdict"],
                input_sha256=digest(case["context"]),
                expected_cause=case["expected_cause"],
                allowed_scope=case["allowed_scope"],
            )
            for case in cases
        ]
        manifest = freeze(manifest_cases, "offline-test-model", "offline-test-template")
        self.assertEqual(len(manifest["cases"]), 30)
        self.assertRegex(manifest["sha256"], r"^[0-9a-f]{64}$")

    def test_quality_template_matches_learning_template_contract(self):
        template = self.artifact("quality-template.json")
        self.assertEqual(set(template), {"schema_version", "body", "allowed_placeholders"})
        self.assertEqual(template["schema_version"], "1")
        body = template["body"]
        self.assertIsInstance(body, str)
        self.assertTrue(body.strip())
        self.assertNotIn("\x00", body)
        self.assertLessEqual(len(body.encode("utf-8")), 8192)
        allowed = template["allowed_placeholders"]
        self.assertIsInstance(allowed, list)
        self.assertEqual(len(allowed), len(set(allowed)))
        self.assertEqual(
            set(allowed),
            {
                "public_problem",
                "public_samples",
                "student_code",
                "sanitized_diagnostic",
                "verdict",
                "question",
            },
        )
        token = re.compile(r"\{([a-z_]+)\}")
        self.assertEqual(set(token.findall(body)), set(allowed))
        self.assertNotRegex(token.sub("", body), r"[{}]")


if __name__ == "__main__":
    unittest.main()
