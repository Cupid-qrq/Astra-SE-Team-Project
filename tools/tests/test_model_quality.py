import unittest
from tools.model_quality import score


class QualityEvidenceTests(unittest.TestCase):
    def test_duplicate_case_rejected_and_disagreements_are_conservative(self):
        verdicts = ["CE"] * 10 + ["WA"] * 8 + ["TLE"] * 8 + ["RE"] * 4
        from tools.model_quality import freeze

        cases = [
            dict(
                case_id=str(i),
                input_sha256=f"{i:064x}",
                verdict=v,
                expected_cause="原因",
                allowed_scope="检查边界",
            )
            for i, v in enumerate(verdicts)
        ]
        frozen = freeze(cases, "v1", "t1")

        def rating(i):
            return dict(
                case_id=str(i),
                request_id=str(i),
                first_request=True,
                status="READY",
                manifest_sha256=frozen["sha256"],
                D=True,
                A=True,
                S=True,
            )

        a = [rating(i) for i in range(30)]
        b = [rating(i) for i in range(30)]
        b[1]["S"] = False
        self.assertFalse(score(frozen, a, b)["passed"])
        self.assertEqual(score(frozen, a, b)["disagreements"], ["1"])
        with self.assertRaises(ValueError):
            score(frozen, a[:-1] + [a[0]], b)
        a[0]["status"] = b[0]["status"] = "BLOCKED"
        self.assertEqual(score(frozen, a, b)["direction"], 29)
