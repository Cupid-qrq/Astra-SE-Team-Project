from dataclasses import replace
from datetime import UTC, datetime, timedelta

import pytest
from app.modules.identity.domain import Fault
from app.modules.learning.policy_rules import HintPolicy, HintSource


class PolicyRepo:
    def __init__(self):
        self.time = datetime(2026, 11, 2, tzinfo=UTC)
        self.guarded = False
        self.data = dict(
            users=[
                dict(user_id=u, status="ACTIVE", role=r)
                for u, r in [("student", "STUDENT"), ("teacher", "TEACHER")]
            ],
            courses=[dict(course_id=c, status="ACTIVE", teacher_id="teacher") for c in ("a", "b")],
            course_members=[
                dict(user_id="student", course_id=c, status="ACTIVE") for c in ("a", "b")
            ],
            problems=[
                dict(problem_id=p, canonical_problem_id="family") for p in ("original", "copy")
            ],
            assignments=[
                dict(
                    assignment_id="exam",
                    course_id="b",
                    published_at=self.time,
                    open_at=self.time + timedelta(seconds=1),
                    due_at=self.time + timedelta(hours=1),
                    revision=1,
                    ai_policy="DISABLED",
                )
            ],
            assignment_items=[dict(assignment_id="exam", problem_id="copy")],
        )
        self.source = HintSource("submission", "student", "a", "original", "FINISHED", "WA")

    def guard(self):
        self.guarded = True

    def now(self):
        assert self.guarded
        return self.time

    def get(self, table, key):
        field = {"users": "user_id", "courses": "course_id", "problems": "problem_id"}[table]
        return next(iter(self.rows(table, **{field: key})), None)

    def rows(self, table, **filters):
        assert self.guarded
        return [
            r
            for r in self.data[table]
            if all(r[k] in (v if isinstance(v, list) else [v]) for k, v in filters.items())
        ]

    def hint_source(self, repo, student_id, submission_id):
        assert repo.guarded
        return self.source


def test_scheduled_cross_course_copy_blocks_all_phases_and_redacts_teacher_read():
    repo = PolicyRepo()
    policy = HintPolicy(repo, repo)
    args = ("student", "submission")
    assert policy.authorize(*args, consent=True).source == repo.source
    repo.time += timedelta(seconds=1)
    for phase in ("accept", "dispatch", "ready"):
        with pytest.raises(Fault, match="同族"):
            policy.authorize(*args, consent=True, phase=phase)
    assert not policy.can_read_sections("teacher", *args, course_id="a", consent=True)
    repo.time += timedelta(hours=1)
    assert policy.can_read_sections("student", *args, course_id="a", consent=True)
    with pytest.raises(Fault) as denied:
        policy.can_read_sections("stranger", *args, course_id="a", consent=True)
    assert denied.value.status == 404


def test_consent_owner_source_and_member_revalidated():
    repo = PolicyRepo()
    policy = HintPolicy(repo, repo)
    for changes in (
        dict(state="RUNNING"),
        dict(verdict="SE"),
        dict(student_id="other"),
        dict(submission_id="other"),
    ):
        repo.source = replace(PolicyRepo().source, **changes)
        with pytest.raises(Fault):
            policy.authorize("student", "submission", consent=True)
    repo.source = PolicyRepo().source
    with pytest.raises(Fault):
        policy.authorize("student", "submission", consent=False)
    repo.data["course_members"][0]["status"] = "DISABLED"
    assert not policy.can_read_sections(
        "teacher", "student", "submission", course_id="a", consent=True
    )
    with pytest.raises(Fault) as denied:
        policy.can_read_sections("student", "student", "submission", course_id="a", consent=True)
    assert denied.value.status == 404
    with pytest.raises(Fault) as missing:
        HintPolicy(repo, None).authorize("student", "submission", consent=True)
    assert missing.value.status == 503


def test_read_projection_never_leaks_internal_or_restricted_fields():
    repo = PolicyRepo()
    policy = HintPolicy(repo, repo)
    hint = dict(
        hint_id="h",
        submission_id="submission",
        user_id="student",
        course_id="a",
        status="READY",
        reason_code=None,
        model_version="model",
        template_version_id="t",
        sections={"checks": "secret historical result"},
        created_at="now",
        actual_cost="private",
        consented_at=repo.time,
        request_key="private",
    )
    fallback = dict(
        feedback_version_id="help", title="帮助", explanation="说明", checklist=["检查边界"]
    )
    assert policy.read_projection("teacher", hint, fallback)["sections"] == hint["sections"]
    repo.time += timedelta(seconds=1)
    projection = policy.read_projection("teacher", hint, fallback)
    assert projection["status"] == "BLOCKED" and projection["sections"] is None
    assert projection["fallback_feedback"] == fallback
    assert "private" not in repr(projection)
    assert hint["status"] == "READY" and hint["sections"]["checks"] == "secret historical result"
