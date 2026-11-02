# ruff: noqa: E402
"""Verify registration/evidence locally; --probe adds GET requests only, never execution."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "server"))

from app.adapters.judge_inventory import load_inventory, probe_inventory, verify_evidence
from app.shared.judge import ExecutionError


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registration", type=Path, required=True)
    parser.add_argument("--evidence", type=Path)
    parser.add_argument("--probe", action="store_true", help="显式对登记端只读GET，不执行程序")
    args = parser.parse_args(argv)
    try:
        inventory = load_inventory(args.registration)
        issues = (
            list(verify_evidence(inventory, args.evidence))
            if args.evidence
            else ["S5_EVIDENCE_NOT_SUPPLIED"]
        )
        observed: dict[str, str] = {}
        if args.probe:
            probe = probe_inventory(inventory)
            observed = dict(probe.observed_hashes)
            if not probe.matched:
                issues.append("PROBE_CONFIG_OR_CAPABILITIES_MISMATCH")
        print(
            json.dumps(
                dict(
                    state="BLOCKED" if issues else "RECORDED_REQUIRES_MEMBER_REVIEW",
                    execution_enabled=False,
                    fingerprint=inventory.fingerprint,
                    network_called=args.probe,
                    issues=issues,
                    observed_hashes=observed,
                ),
                ensure_ascii=False,
            )
        )
        return 2 if issues else 0
    except ExecutionError as error:
        print(
            json.dumps(
                dict(state="UNVERIFIED", execution_enabled=False, error=str(error)),
                ensure_ascii=False,
            )
        )
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
