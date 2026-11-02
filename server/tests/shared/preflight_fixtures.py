"""Synthetic drafts and private sentinels. No execution or real evidence."""

from copy import deepcopy
from pathlib import Path
from uuid import uuid4

from http_fixtures import profile
from teaching_fixtures import seed

from app.adapters.judge_profiles import ProfileCatalog, RuntimeProfile
from app.modules.problems.application import Problems
from app.shared.effects import TransactionalEffects
from app.shared.repository import SqlRepository
from app.shared.uow import UnitOfWork


def sample_snapshot():
    return dict(
        version_id=str(uuid4()),
        revision=1,
        title="test",
        statement="test",
        tags=[],
        samples=[dict(input="1", output="1")],
        profile=profile(),
        source_ref="synthetic",
        testcases=[dict(order=1, input_text="SECRET_INPUT\x00", answer_text="SECRET_ANSWER")],
        references=[
            dict(language_key=key, code="SECRET_SOURCE\x00") for key in ("cpp17", "python3")
        ],
    )


def catalog(snapshot):
    ids = {"cpp17": 912, "python3": 733}
    return ProfileCatalog(
        [
            RuntimeProfile.from_public(
                snapshot["profile"],
                {
                    row["language_key"]: ids[row["language_key"]]
                    for row in snapshot["profile"]["languages"]
                },
            )
        ]
    )


def draft(engine, *, one_language=False):
    snapshot = sample_snapshot()
    if one_language:
        snapshot["profile"]["languages"] = snapshot["profile"]["languages"][:1]
        snapshot["references"] = snapshot["references"][:1]
    ids = seed(engine, Path(__file__).parents[2] / "alembic.ini", profile=snapshot["profile"])
    with UnitOfWork(engine) as conn:
        repo = SqlRepository(conn)
        repo.guard()
        actor = repo.get("users", ids["teacher"])
        service = Problems(repo, TransactionalEffects(repo, str(uuid4())))
        created = service.create_version(
            actor,
            {
                **{
                    k: snapshot[k]
                    for k in ("title", "statement", "samples", "tags", "profile", "source_ref")
                },
                "problem_id": ids["problem"],
            },
        )
        vid = created["version_id"]
        revision = 1
        for case in snapshot["testcases"]:
            result = service.put_case(
                actor,
                vid,
                case["order"],
                dict(
                    input_text=case["input_text"],
                    answer_text=case["answer_text"],
                    expected_revision=revision,
                ),
            )
            revision = result["revision"]
        for ref in snapshot["references"]:
            result = service.put_reference(
                actor, vid, ref["language_key"], dict(code=ref["code"], expected_revision=revision)
            )
            revision = result["revision"]
        snapshot = deepcopy(service.snapshot(vid))
        ids["draft"] = vid
    return ids, snapshot
