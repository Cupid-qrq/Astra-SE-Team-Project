"""Offline P0 schema probe. No credentials, network transport or paid-call path.

This does not prove provenance, authorization, semantic safety, model quality or
budget enforcement. The P2 application must implement those gates separately.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sys

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "specs/model"


def canonical(value):
    return json.dumps(value, ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def validate_schema(value, name):
    schema = json.loads((MODEL / name).read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    if next(Draft202012Validator(schema).iter_errors(value), None) is not None:
        # Never include the rejected value or validator's repr in logs.
        raise ValueError("SCHEMA_REJECTED")


def validate_context(value):
    validate_schema(value, "input.schema.json")
    if len(canonical(value).encode("utf-8")) > 24 * 1024:
        raise ValueError("CONTEXT_TOO_LARGE")
    for sample in value["public_samples"]:
        if any(len(part.encode("utf-8")) > 4096 for part in sample.values()):
            raise ValueError("SAMPLE_TOO_LARGE")
    return value


def validate_output(raw):
    if not isinstance(raw, str) or len(raw) > 2000 or len(raw.encode("utf-8")) > 8192:
        raise ValueError("OUTPUT_TOO_LARGE")
    try:
        value = json.loads(raw, object_pairs_hook=unique_object)
    except (ValueError, TypeError):
        raise ValueError("INVALID_JSON") from None
    validate_schema(value, "output.schema.json")
    return value


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("DUPLICATE_KEY")
        result[key] = value
    return result


def validate_config(value):
    # In this P0 scope the only accepted configuration is the disabled template.
    # Activation requires a separately reviewed real integration, not a flag flip.
    validate_schema(value, "config.schema.json")
    return value


def offline_check(value):
    validate_context(value)
    return {"mode": "offline", "schema_version": "1", "network_called": False,
            "input_sha256": hashlib.sha256(canonical(value).encode("utf-8")).hexdigest(),
            "actual_cost_cny": None, "quality_verified": False}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=MODEL / "sample-input.json")
    parser.add_argument("--config", type=Path, default=MODEL / "config.example.json")
    args = parser.parse_args()
    try:
        validate_config(json.loads(args.config.read_text(encoding="utf-8")))
        result = offline_check(json.loads(args.input.read_text(encoding="utf-8"), object_pairs_hook=unique_object))
    except (OSError, ValueError, UnicodeError):
        print("Offline schema check failed; no input or secret values logged.", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
