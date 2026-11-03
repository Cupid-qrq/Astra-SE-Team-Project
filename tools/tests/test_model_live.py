import asyncio
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from decimal import Decimal
from pathlib import Path

from tools.model_live import LiveLedger, execute_case, export_evidence


class LiveBudgetTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / "budget.sqlite3"

    def test_concurrent_reservations_and_restart_preserve_total_cap(self):
        ledger = LiveLedger(self.path, Decimal("0.10"))

        def reserve(i):
            try:
                return ledger.reserve("manifest", str(i), Decimal("0.06"))
            except ValueError:
                return None

        with ThreadPoolExecutor(max_workers=2) as pool:
            values = list(pool.map(reserve, range(2)))
        self.assertEqual(sum(v is not None for v in values), 1)
        reopened = LiveLedger(self.path, Decimal("20"))
        self.assertEqual(reopened.summary()["cap_cny"], "0.1")
        self.assertEqual(reopened.summary()["held_cny"], "0.06")
        with self.assertRaisesRegex(ValueError, "BUDGET"):
            reopened.reserve("different-run", "case", Decimal("0.05"))

    def test_interrupted_attempt_is_not_replayed_and_unknown_holds_full_amount(self):
        ledger = LiveLedger(self.path)
        ledger.reserve("m", "case", Decimal("0.07"))
        self.assertIsNone(LiveLedger(self.path).reserve("m", "case", Decimal("0.07")))
        self.assertEqual(ledger.results("m")[0]["billing"], "UNCERTAIN")
        self.assertEqual(ledger.summary()["held_cny"], "0.07")

    def test_release_requires_explicit_pre_dispatch_proof_and_settlement_is_once(self):
        ledger = LiveLedger(self.path)
        attempt = ledger.reserve("m", "c", Decimal("0.07"))
        result = {
            "status": "FAILED",
            "billing": "RELEASED",
            "reason_code": "MODEL_NOT_DISPATCHED",
        }
        ledger.finish(attempt, result)
        self.assertEqual(ledger.summary()["held_cny"], "0")
        with self.assertRaisesRegex(ValueError, "ALREADY"):
            ledger.finish(attempt, result)
        attempt2 = ledger.reserve("m", "d", Decimal("0.07"))
        with self.assertRaisesRegex(ValueError, "RECEIPT"):
            ledger.finish(attempt2, {"billing": "RELEASED", "reason_code": "MODEL_TIMEOUT"})
        self.assertEqual(ledger.summary()["held_cny"], "0.07")

    def test_execute_does_not_send_expected_answers_and_skips_saved_first_result(self):
        ledger = LiveLedger(self.path)
        calls = []

        async def generate(context):
            calls.append(context)
            return {
                "status": "READY",
                "billing": "UNCERTAIN",
                "estimated_cost_cny": "0.003",
                "sections": {"checks": "inspect boundary"},
            }

        case = {
            "case_id": "a",
            "context": {"public_problem": "public"},
            "expected_cause": "secret-answer",
            "allowed_scope": "grading-only",
        }
        asyncio.run(execute_case(ledger, "m", case, Decimal("0.07"), generate))
        asyncio.run(execute_case(ledger, "m", case, Decimal("0.07"), generate))
        self.assertEqual(calls, [case["context"]])
        self.assertEqual(ledger.summary()["held_cny"], "0.07")
        self.assertEqual(ledger.summary()["estimated_cny"], "0.003")

    def test_exception_after_dispatch_is_generic_and_persists_unknown(self):
        ledger = LiveLedger(self.path)

        async def fail(context):
            raise RuntimeError("sensitive-token-do-not-save")

        asyncio.run(
            execute_case(ledger, "m", {"case_id": "a", "context": {}}, Decimal("0.07"), fail)
        )
        saved = ledger.results("m")
        self.assertNotIn("sensitive-token", str(saved))
        self.assertEqual(saved[0]["reason_code"], "MODEL_CALL_FAILED")
        self.assertEqual(ledger.summary()["held_cny"], "0.07")

    def test_nonfinite_negative_and_above_authorized_budget_are_rejected(self):
        for cap in ("NaN", "Infinity", "-1", "0", "20.01"):
            with self.assertRaises(ValueError):
                LiveLedger(self.path, Decimal(cap))
        ledger = LiveLedger(self.path)
        for amount in ("NaN", "Infinity", "-1", "0"):
            with self.assertRaises(ValueError):
                ledger.reserve("m", "c", Decimal(amount))

    def test_concurrent_exports_are_consistent_and_preserve_existing_ratings(self):
        import json

        ledger = LiveLedger(self.path)
        directory = Path(self.directory.name)
        for i in range(30):
            attempt = ledger.reserve("m", str(i), Decimal("0.01"))
            ledger.finish(attempt, {"status": "READY", "billing": "UNCERTAIN"})
        manifest = {"sha256": "m"}
        with ThreadPoolExecutor(max_workers=6) as pool:
            list(pool.map(lambda _: export_evidence(directory, manifest, ledger), range(20)))
        self.assertEqual(
            len(json.loads((directory / "results.json").read_text(encoding="utf8"))), 30
        )
        ratings = directory / "review-a.template.json"
        ratings.write_text("human-progress", encoding="utf8")
        export_evidence(directory, manifest, ledger)
        self.assertEqual(ratings.read_text(encoding="utf8"), "human-progress")

    def test_review_templates_wait_for_last_persisted_terminal_result(self):
        import json

        ledger = LiveLedger(self.path)
        directory = Path(self.directory.name)
        for i in range(30):
            attempt = ledger.reserve("m", str(i), Decimal("0.01"))
            if i != 29:
                ledger.finish(attempt, {"status": "READY", "billing": "UNCERTAIN"})
        export_evidence(directory, {"sha256": "m"}, ledger)
        self.assertFalse((directory / "review-a.template.json").exists())
        ledger.finish(attempt, {"status": "READY", "billing": "UNCERTAIN"})
        export_evidence(directory, {"sha256": "m"}, ledger)
        ratings = json.loads((directory / "review-a.template.json").read_text(encoding="utf8"))
        self.assertTrue(all(r["status"] == "READY" for r in ratings))

    def test_explicit_interruption_finalization_keeps_liability_and_cannot_repeat(self):
        ledger = LiveLedger(self.path)
        attempt = ledger.reserve("m", "c", Decimal("0.07"))
        ledger.finalize_interrupted(attempt)
        self.assertEqual(ledger.results("m")[0]["reason_code"], "INTERRUPTED_FINALIZED")
        self.assertEqual(ledger.summary()["held_cny"], "0.07")
        self.assertIsNone(ledger.reserve("m", "c", Decimal("0.07")))
        with self.assertRaisesRegex(ValueError, "ALREADY"):
            ledger.finalize_interrupted(attempt)
