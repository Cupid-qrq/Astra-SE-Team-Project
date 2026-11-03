import json
from copy import deepcopy

import pytest
from preflight_fixtures import catalog, sample_snapshot

from app.modules.identity.domain import Fault
from app.modules.judging.domain import freeze_snapshot
from app.modules.problems.domain import content_digest, profile_digest


def test_plan_binds_exact_a_hash_and_deep_frozen_private_bytes():
    snapshot = sample_snapshot()
    plan = freeze_snapshot(snapshot, catalog(snapshot))
    assert plan.content_digest == content_digest(snapshot)
    assert plan.profile_hash == profile_digest(snapshot["profile"])
    assert len(plan.cases) == 4
    assert "SECRET" not in repr(plan)
    assert json.loads(plan.blob)["testcases"][0]["input_text"] == "SECRET_INPUT\x00"
    snapshot["references"][0]["code"] = "changed"
    assert "changed" not in plan.blob.decode()


def test_plan_covers_all_languages_and_maximum_sample_hidden_points():
    snapshot = sample_snapshot()
    snapshot["samples"] = [dict(input="", output="") for _ in range(3)]
    snapshot["testcases"] = [dict(order=i, input_text="", answer_text="") for i in range(1, 11)]
    assert len(freeze_snapshot(snapshot, catalog(snapshot)).cases) == 26


@pytest.mark.parametrize(
    "kind",
    [
        "zero_samples",
        "four_samples",
        "zero_hidden",
        "eleven_hidden",
        "gap",
        "bool_order",
        "duplicate_ref",
        "missing_ref",
        "blank_ref",
        "large_ref",
        "large_hidden",
        "bad_utf8",
        "revision_bool",
        "profile_drift",
    ],
)
def test_plan_rejects_incomplete_or_unsafe_snapshot_without_chain(kind):
    snapshot = sample_snapshot()
    allowed = catalog(snapshot)
    if kind == "zero_samples":
        snapshot["samples"] = []
    if kind == "four_samples":
        snapshot["samples"] *= 4
    if kind == "zero_hidden":
        snapshot["testcases"] = []
    if kind == "eleven_hidden":
        snapshot["testcases"] *= 11
    if kind == "gap":
        snapshot["testcases"][0]["order"] = 2
    if kind == "bool_order":
        snapshot["testcases"][0]["order"] = True
    if kind == "duplicate_ref":
        snapshot["references"].append(deepcopy(snapshot["references"][0]))
    if kind == "missing_ref":
        snapshot["references"].pop()
    if kind == "blank_ref":
        snapshot["references"][0]["code"] = " \n"
    if kind == "large_ref":
        snapshot["references"][0]["code"] = "x" * 65537
    if kind == "large_hidden":
        snapshot["testcases"][0]["input_text"] = "x" * 65537
    if kind == "bad_utf8":
        snapshot["testcases"][0]["input_text"] = "SECRET_\ud800"
    if kind == "revision_bool":
        snapshot["revision"] = True
    if kind == "profile_drift":
        snapshot["profile"]["languages"][0]["image_digest"] = "sha256:" + "f" * 64
    with pytest.raises(Fault) as error:
        freeze_snapshot(snapshot, allowed)
    assert "SECRET" not in str(error.value)
    assert error.value.__context__ is None and error.value.__cause__ is None


def test_public_snapshot_catalog_binds_without_inventing_execution_ids():
    from app.adapters.judge_profiles import SnapshotCatalog

    snapshot = sample_snapshot()
    public = SnapshotCatalog([snapshot["profile"]])
    bound = public.bind(snapshot["profile"])
    assert bound.profile_hash == profile_digest(snapshot["profile"])
    assert all(not hasattr(language, "language_id") for language in bound.languages)
    assert freeze_snapshot(snapshot, public) == freeze_snapshot(snapshot, catalog(snapshot))
    snapshot["profile"]["languages"][0]["version"] = "CHANGED"
    from app.shared.judge import ExecutionError

    with pytest.raises(ExecutionError):
        public.bind(snapshot["profile"])


@pytest.mark.parametrize(
    "change", [{"memory_bytes": 1}, {"run_entities": 2}, {"compile_timeout_ms": 1}]
)
def test_public_snapshot_catalog_requires_exact_business_limits(change):
    from app.adapters.judge_profiles import SnapshotCatalog
    from app.shared.judge import ExecutionError

    value = sample_snapshot()["profile"] | change
    with pytest.raises(ExecutionError):
        SnapshotCatalog([value])
