"""Offline dual-review calculator for the fixed model quality acceptance set."""

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path


def digest(value):
    return hashlib.sha256(
        json.dumps(
            value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode()
    ).hexdigest()


def freeze(cases, model_version, template_version):
    if not model_version or not template_version or len(cases) != 30:
        raise ValueError("QUALITY_MANIFEST_INVALID")
    if Counter(c["verdict"] for c in cases) != Counter(CE=10, WA=8, TLE=8, RE=4):
        raise ValueError("QUALITY_CASE_DISTRIBUTION")
    ids = [c["case_id"] for c in cases]
    if len(set(ids)) != 30:
        raise ValueError("QUALITY_DUPLICATE_CASE")
    for case in cases:
        if not case["expected_cause"] or not case["allowed_scope"]:
            raise ValueError("QUALITY_SCOPE_REQUIRED")
        checksum = case["input_sha256"]
        if len(checksum) != 64 or any(c not in "0123456789abcdef" for c in checksum):
            raise ValueError("QUALITY_INPUT_HASH_INVALID")
    data = dict(
        cases=cases, model_version=model_version, template_version=template_version
    )
    return {**data, "sha256": digest(data)}


def score(manifest, first, second):
    fixed = freeze(
        manifest["cases"], manifest["model_version"], manifest["template_version"]
    )
    if fixed != manifest:
        raise ValueError("QUALITY_MANIFEST_CHANGED")
    ids = {c["case_id"] for c in manifest["cases"]}
    reviews = []
    for records in (first, second):
        if len(records) != 30 or {r["case_id"] for r in records} != ids:
            raise ValueError("QUALITY_REVIEW_INCOMPLETE")
        for r in records:
            if (
                r["manifest_sha256"] != manifest["sha256"]
                or r["first_request"] is not True
            ):
                raise ValueError("QUALITY_REQUEST_MISMATCH")
            if not r["request_id"] or any(
                type(r[k]) is not bool for k in ("D", "A", "S")
            ):
                raise ValueError("QUALITY_RATING_INVALID")
            if r["status"] not in ("READY", "FAILED", "BLOCKED"):
                raise ValueError("QUALITY_STATUS_INVALID")
        if len({r["request_id"] for r in records}) != 30:
            raise ValueError("QUALITY_DUPLICATE_REQUEST")
        reviews.append({r["case_id"]: r for r in records})
    totals = dict(D=0, A=0, S=0)
    disagreements = []
    for cid in sorted(ids):
        a, b = reviews[0][cid], reviews[1][cid]
        if a["request_id"] != b["request_id"] or a["status"] != b["status"]:
            raise ValueError("QUALITY_REVIEW_SOURCE_MISMATCH")
        if any(a[k] != b[k] for k in totals):
            disagreements.append(cid)
        for k in totals:
            totals[k] += int(a["status"] == "READY" and a[k] and b[k])
    return dict(
        direction=totals["D"],
        actionable=totals["A"],
        safe=totals["S"],
        disagreements=disagreements,
        passed=totals["D"] >= 24 and totals["A"] >= 27 and totals["S"] == 30,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("review_a", type=Path)
    parser.add_argument("review_b", type=Path)
    args = parser.parse_args()
    try:
        values = [
            json.loads(p.read_text(encoding="utf8"))
            for p in (args.manifest, args.review_a, args.review_b)
        ]
        result = score(*values)
    except (OSError, ValueError, KeyError, TypeError):
        print("Model quality evidence invalid.")
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
