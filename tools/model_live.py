"""Explicit, resumable synthetic model evaluation with a durable 20 CNY ceiling.

Run with server/.venv Python. Default is offline; --live authorizes one first
attempt per frozen case. Never delete/reset the ledger to retry an unknown call.
"""

import argparse
import asyncio
import json
import sqlite3
import sys
import time
from contextlib import contextmanager
from dataclasses import asdict
from datetime import UTC, datetime
from decimal import ROUND_CEILING, Decimal
from pathlib import Path
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.model_quality import digest, freeze  # noqa: E402


def _micros(value, *, positive=False):
    amount = Decimal(value)
    if not amount.is_finite() or amount < 0 or (positive and amount == 0):
        raise ValueError("INVALID_BUDGET")
    return int((amount * 1_000_000).to_integral_value(rounding=ROUND_CEILING))


def _cny(micros):
    return str(Decimal(micros) / 1_000_000)


class LiveLedger:
    """Integer micro-CNY reservations, serialized across processes by SQLite.

    Interrupted calls remain held. A supplied larger cap never raises a saved cap.
    Estimates are informational; only authoritative settlement releases the hold.
    """

    def __init__(self, path, cap=Decimal("20")):
        limit = _micros(cap, positive=True)
        if limit > 20_000_000:
            raise ValueError("UNAUTHORIZED_BUDGET")
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute(
                "CREATE TABLE IF NOT EXISTS budget (id INTEGER PRIMARY KEY CHECK(id=1), cap INTEGER NOT NULL)"
            )
            db.execute(
                "CREATE TABLE IF NOT EXISTS attempts (id TEXT PRIMARY KEY, manifest TEXT NOT NULL, case_id TEXT NOT NULL, upper INTEGER NOT NULL, held INTEGER NOT NULL, result TEXT, created TEXT NOT NULL, UNIQUE(manifest,case_id))"
            )
            db.execute(
                "INSERT INTO budget VALUES(1,?) ON CONFLICT(id) DO UPDATE SET cap=min(cap,excluded.cap)",
                (limit,),
            )

    @contextmanager
    def _connect(self):
        db = sqlite3.connect(self.path, timeout=10)
        try:
            db.row_factory = sqlite3.Row
            db.execute("PRAGMA synchronous=FULL")
            with db:
                yield db
        finally:
            db.close()

    def reserve(self, manifest, case_id, upper):
        amount = _micros(upper, positive=True)
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            if db.execute(
                "SELECT 1 FROM attempts WHERE manifest=? AND case_id=?",
                (manifest, case_id),
            ).fetchone():
                return None
            used = db.execute("SELECT COALESCE(sum(held),0) FROM attempts").fetchone()[0]
            cap = db.execute("SELECT cap FROM budget WHERE id=1").fetchone()[0]
            if used + amount > cap:
                raise ValueError("MODEL_BUDGET_EXHAUSTED")
            attempt = str(uuid4())
            db.execute(
                "INSERT INTO attempts VALUES(?,?,?,?,?,NULL,?)",
                (
                    attempt,
                    manifest,
                    case_id,
                    amount,
                    amount,
                    datetime.now(UTC).isoformat(),
                ),
            )
            return attempt

    def finish(self, attempt, result):
        billing = result.get("billing")
        if billing not in ("SETTLED", "RELEASED", "UNCERTAIN"):
            raise ValueError("INVALID_RECEIPT")
        if billing == "RELEASED" and result.get("reason_code") not in (
            "MODEL_NOT_DISPATCHED",
            "MODEL_DISABLED",
            "MODEL_CONFIG_INVALID",
            "INVALID_MODEL_CONTEXT",
        ):
            raise ValueError("INVALID_RECEIPT")
        with self._connect() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute("SELECT * FROM attempts WHERE id=?", (attempt,)).fetchone()
            if not row or row["result"] is not None:
                raise ValueError("ALREADY_FINISHED")
            held = row["upper"]
            if billing == "RELEASED":
                held = 0
            elif billing == "SETTLED":
                held = _micros(result["actual_cost_cny"])
            db.execute(
                "UPDATE attempts SET held=?,result=? WHERE id=?",
                (
                    held,
                    json.dumps(result, ensure_ascii=False, allow_nan=False),
                    attempt,
                ),
            )

    def finalize_interrupted(self, attempt):
        """Operator confirms the process stopped; never release money or retry the call."""
        self.finish(
            attempt, dict(status="FAILED", billing="UNCERTAIN", reason_code="INTERRUPTED_FINALIZED")
        )

    def results(self, manifest):
        with self._connect() as db:
            rows = db.execute(
                "SELECT * FROM attempts WHERE manifest=? ORDER BY case_id", (manifest,)
            ).fetchall()
        return [
            dict(
                case_id=r["case_id"],
                attempt_id=r["id"],
                first_request=True,
                manifest_sha256=manifest,
                created_at=r["created"],
                reserved_upper_cny=_cny(r["upper"]),
                **(
                    json.loads(r["result"])
                    if r["result"]
                    else {
                        "status": "FAILED",
                        "billing": "UNCERTAIN",
                        "reason_code": "INTERRUPTED_OR_RUNNING",
                    }
                ),
            )
            for r in rows
        ]

    def summary(self):
        with self._connect() as db:
            cap = db.execute("SELECT cap FROM budget WHERE id=1").fetchone()[0]
            rows = db.execute("SELECT held,result FROM attempts").fetchall()
        estimates = [json.loads(r["result"]).get("estimated_cost_cny") for r in rows if r["result"]]
        return dict(
            cap_cny=_cny(cap),
            held_cny=_cny(sum(r["held"] for r in rows)),
            estimated_cny=str(sum((Decimal(v) for v in estimates if v is not None), Decimal(0))),
            attempts=len(rows),
            supplier_invoice_verified=False,
        )


async def execute_case(ledger, manifest, case, upper, generate):
    attempt = ledger.reserve(manifest, case["case_id"], upper)
    if attempt is None:
        return False
    started = time.monotonic()
    try:
        # Only public context crosses the provider boundary, never scoring metadata.
        result = await generate(case["context"])
    except Exception:
        result = {
            "status": "FAILED",
            "billing": "UNCERTAIN",
            "reason_code": "MODEL_CALL_FAILED",
        }
    result["elapsed_seconds"] = round(time.monotonic() - started, 3)
    ledger.finish(attempt, result)
    return True


def save_frozen(path, value):
    payload = json.dumps(value, ensure_ascii=False, indent=2) + "\n"
    try:
        with path.open("x", encoding="utf8") as stream:
            stream.write(payload)
    except FileExistsError:
        if path.read_text(encoding="utf8") != payload:
            raise ValueError("FROZEN_EVIDENCE_CHANGED")


def export_evidence(directory, manifest, ledger):
    # Serialize snapshot + replace with reservation/settlement, including across processes.
    with ledger._connect() as db:
        db.execute("BEGIN IMMEDIATE")
        _export_locked(directory, manifest, ledger)


def _export_locked(directory, manifest, ledger):
    results = ledger.results(manifest["sha256"])
    temporary = directory / "results.tmp"
    temporary.write_text(json.dumps(results, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    temporary.replace(directory / "results.json")
    if len(results) == 30 and all(
        r.get("reason_code") != "INTERRUPTED_OR_RUNNING" for r in results
    ):
        reviews = [
            dict(
                case_id=r["case_id"],
                request_id=r["attempt_id"],
                first_request=True,
                manifest_sha256=manifest["sha256"],
                status=r["status"],
                D=None,
                A=None,
                S=None,
                notes="待真实评审填写，不得将结构检查当成质量评分。",
            )
            for r in results
        ]
        for name in ("review-a.template.json", "review-b.template.json"):
            # Never overwrite completed human ratings.
            path = directory / name
            if not path.exists():
                save_frozen(path, reviews)


async def run(args):
    sys.path.insert(0, str(ROOT / "server"))
    from app.modules.learning.model_runtime import RuntimeProfile, content_gate
    from app.modules.learning.model_worker import evaluate_candidate, prepare_context
    from app.modules.learning.templates import validate_template

    profile = RuntimeProfile.from_file(args.profile)
    cases = json.loads(args.cases.read_text(encoding="utf8"))
    template = json.loads(args.template.read_text(encoding="utf8"))
    validate_template(template)
    for case in cases:
        if (
            prepare_context(case["context"], question=case["context"]["question"])
            != case["context"]
        ):
            raise ValueError("QUALITY_CONTEXT_CHANGED")
    template_id = digest(template)
    manifest = freeze(
        [
            dict(
                case_id=c["case_id"],
                verdict=c["context"]["verdict"],
                input_sha256=digest(c["context"]),
                expected_cause=c["expected_cause"],
                allowed_scope=c["allowed_scope"],
            )
            for c in cases
        ],
        profile.version_label + ":" + profile.config_id,
        template_id,
    )
    directory = ROOT / ".local/model-live" / manifest["sha256"]
    directory.mkdir(parents=True, exist_ok=True)
    for name, value in (
        ("manifest.json", manifest),
        ("cases.json", cases),
        ("template.json", template),
        ("profile.snapshot.json", json.loads(json.dumps(asdict(profile), default=str))),
    ):
        save_frozen(directory / name, value)
    ledger = LiveLedger(ROOT / ".local/model-live/budget.sqlite3", profile.project_budget_cny)
    for attempt in args.finalize_interrupted:
        ledger.finalize_interrupted(attempt)
    if args.live:
        transport = profile.transport(template_id, template)
        model = profile.frozen_model(template_id)

        async def generate(context):
            observed = []

            class ObservedTransport:
                async def generate(self, public_context, frozen_model):
                    reply = await transport.generate(public_context, frozen_model)
                    observed.append(reply.raw)
                    return reply

            candidate = await evaluate_candidate(
                context, model, transport=ObservedTransport(), content_check=content_gate
            )
            return dict(
                status="READY" if candidate.sections else "FAILED",
                billing=candidate.billing,
                reason_code=candidate.reason_code,
                sections=candidate.sections,
                actual_cost_cny=str(candidate.actual_cost_cny)
                if candidate.actual_cost_cny is not None
                else None,
                estimated_cost_cny=str(candidate.estimated_cost_cny)
                if candidate.estimated_cost_cny is not None
                else None,
                usage=candidate.usage,
                provider_request_id=candidate.provider_request_id,
                provider_model=candidate.provider_model,
                # Synthetic evaluation evidence only; never exposed through HintView.
                raw_candidate=observed[0][:8192] if observed else None,
                raw_candidate_truncated=bool(observed and len(observed[0]) > 8192),
            )

        performed = 0
        for case in cases:
            if performed >= args.limit:
                break
            if await execute_case(
                ledger, manifest["sha256"], case, profile.cost_upper_cny, generate
            ):
                performed += 1
                export_evidence(directory, manifest, ledger)
                print(
                    json.dumps(
                        {
                            "case_id": case["case_id"],
                            "completed": performed,
                            **ledger.summary(),
                        }
                    ),
                    flush=True,
                )
    export_evidence(directory, manifest, ledger)
    print(
        json.dumps(
            {"live": args.live, "evidence": str(directory), **ledger.summary()},
            ensure_ascii=False,
        )
    )
    return 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--profile", type=Path, default=ROOT / "specs/model/runtime.example.json")
    parser.add_argument("--cases", type=Path, default=ROOT / "specs/model/quality-cases.json")
    parser.add_argument("--template", type=Path, default=ROOT / "specs/model/quality-template.json")
    parser.add_argument("--live", action="store_true")
    parser.add_argument(
        "--finalize-interrupted",
        action="append",
        default=[],
        metavar="ATTEMPT_ID",
        help="After confirming its process stopped: mark an abandoned attempt FAILED, retaining full liability; never retry.",
    )
    parser.add_argument("--limit", type=int, choices=range(1, 31), default=1)
    args = parser.parse_args()
    if args.live and args.finalize_interrupted:
        parser.error("Finalizing stopped attempts cannot be combined with --live.")
    failed = False
    try:
        return asyncio.run(run(args))
    except (Exception, KeyboardInterrupt):
        failed = True
    if failed:
        print(
            "MODEL_EVALUATION_STOPPED: check configuration and saved ledger; unknown fees remain held. No automatic retry.",
            file=sys.stderr,
        )
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
