from datetime import datetime, timedelta
from uuid import uuid4

from app.modules.assignments.application import Assignments
from app.modules.identity.domain import require, revision, utc
from app.shared.effects import TransactionalEffects
from app.shared.repository import SqlRepository


def has_uncovered_interval(start, end, segments):
    cursor = start
    for left, right in sorted(segments):
        if right < cursor:
            continue
        if left > cursor:
            return True
        cursor = max(cursor, right)
        if cursor >= end:
            return False
    return True


class Fairness:
    def __init__(self, repo: SqlRepository, effects: TransactionalEffects):
        self.repo, self.effects = repo, effects
        self.assignments = Assignments(repo, effects)

    def create(self, actor, body):
        require(actor["role"] == "ADMIN", "FORBIDDEN", "仅管理员可登记平台事件。", 403)
        self.repo.guard()
        started = datetime.fromisoformat(body["started_at"].replace("Z", "+00:00"))
        now = self.repo.now()
        require(started <= now, "VALIDATION_ERROR", "故障开始时间不能晚于当前时间。", 422)
        incident_id = str(uuid4())
        self.repo.add(
            "fairness_incidents",
            dict(
                incident_id=incident_id,
                started_at=started,
                recovered_at=None,
                reason_code=body["reason_code"],
                rejected_count=0,
                evidence_refs=body.get("evidence_refs", []),
                evidence_incomplete=body.get("evidence_incomplete", True),
                detected_at=now,
                displayed_at=now,
                persisted_at=now,
                recovery_started_at=None,
                revision=1,
            ),
        )
        for aid in sorted(set(body["assignment_ids"])):
            assignment = self.repo.required("assignments", aid, lock=True)
            require(assignment is not None, "NOT_FOUND", "影响作业不存在。", 404)
            require(
                self.repo.required("courses", assignment["course_id"])["status"] == "ACTIVE",
                "COURSE_ARCHIVED",
                "归档课程不能新增事件。",
            )
            self.repo.add(
                "incident_assignments",
                dict(
                    incident_id=incident_id,
                    assignment_id=aid,
                    decision="PENDING",
                    old_due=assignment["due_at"],
                ),
            )
            self.repo.change(
                "assignments", aid, fairness_review="PENDING", revision=assignment["revision"] + 1
            )
        self.effects.record(
            self.repo, actor["user_id"], "INCIDENT_CREATED", incident_id, reason=body["reason"]
        )
        return dict(incident_id=incident_id, revision=1)

    def recovery(self, actor, incident_id, body):
        require(actor["role"] == "ADMIN", "FORBIDDEN", "仅管理员可登记恢复。", 403)
        self.repo.guard()
        incident = self.repo.required("fairness_incidents", incident_id, lock=True)
        require(incident is not None, "NOT_FOUND", "事件不存在。", 404)
        revision(incident, body["expected_revision"])
        recovered = datetime.fromisoformat(body["recovered_at"].replace("Z", "+00:00"))
        now = self.repo.now()
        require(
            incident["started_at"] <= recovered <= now,
            "VALIDATION_ERROR",
            "恢复时间必须在开始与当前时间之间。",
            422,
        )
        require(incident["recovered_at"] is None, "REVISION_CONFLICT", "恢复时间已登记。")
        self.repo.change(
            "fairness_incidents",
            incident_id,
            recovered_at=recovered,
            recovery_started_at=now,
            revision=incident["revision"] + 1,
        )
        self.effects.record(
            self.repo, actor["user_id"], "INCIDENT_RECOVERED", incident_id, reason=body["reason"]
        )
        return dict(revision=incident["revision"] + 1)

    def read(self, actor, incident_id):
        incident = self.repo.required("fairness_incidents", incident_id)
        require(incident is not None, "NOT_FOUND", "事件不存在。", 404)
        rows = self.repo.rows("incident_assignments", incident_id=incident_id)
        if actor["role"] != "ADMIN":
            visible = []
            for row in rows:
                assignment = self.repo.required("assignments", row["assignment_id"])
                course = self.repo.required("courses", assignment["course_id"])
                if actor["role"] == "TEACHER" and course["teacher_id"] == actor["user_id"]:
                    visible.append(row)
            require(bool(visible), "NOT_FOUND", "事件不存在或无权访问。", 404)
            rows = visible
        return dict(
            incident_id=incident_id,
            started_at=utc(incident["started_at"]),
            recovered_at=utc(incident["recovered_at"]) if incident["recovered_at"] else None,
            reason_code=incident["reason_code"],
            revision=incident["revision"],
            evidence_incomplete=incident["evidence_incomplete"],
            assignments=[
                dict(
                    assignment_id=row["assignment_id"],
                    decision=row["decision"],
                    new_due_at=utc(row["new_due"]) if row["new_due"] else None,
                )
                for row in rows
            ],
        )

    def list(self, actor, pager):
        require(
            actor["role"] in ("ADMIN", "TEACHER"), "FORBIDDEN", "仅教师或管理员可查看事件。", 403
        )
        from app.modules.identity.domain import Fault

        values = []
        for event in self.repo.rows("fairness_incidents"):
            try:
                values.append(self.read(actor, event["incident_id"]))
            except Fault as error:
                if error.status != 404:
                    raise
        return pager.bounded(values, "incident_id")

    def decide(self, actor, assignment_id, body):
        self.repo.guard()
        assignment, _ = self.assignments.access(actor, assignment_id, teacher=True, write=True)
        revision(assignment, body["expected_revision"])
        incident = self.repo.required("fairness_incidents", body["incident_id"], lock=True)
        link = self.repo.required(
            "incident_assignments", (body["incident_id"], assignment_id), lock=True
        )
        require(
            incident is not None and link is not None, "NOT_FOUND", "作业不在该事件范围内。", 404
        )
        require(link["decision"] == "PENDING", "REVISION_CONFLICT", "该事件已裁决。")
        require(incident["recovered_at"] is not None, "NOT_READY", "请先登记故障恢复。")
        if body["decision"] == "EXTEND":
            require(
                assignment["active_rejudge_batch_id"] is None,
                "ACTIVE_REJUDGE",
                "延期前请先取消重评。",
            )
        require(
            body["decision"] in ("EXTEND", "NO_IMPACT"), "VALIDATION_ERROR", "裁决类型无效。", 422
        )
        now = self.repo.now()
        old_due = assignment["due_at"]
        overlap = max(
            timedelta(),
            min(incident["recovered_at"], old_due)
            - max(incident["started_at"], assignment["open_at"]),
        )
        new_due = None
        if body["decision"] == "EXTEND":
            start, end = incident["started_at"], incident["recovered_at"]
            previous = []
            for row in self.repo.rows("incident_assignments", assignment_id=assignment_id):
                if row["decision"] == "EXTEND":
                    prior = self.repo.required("fairness_incidents", row["incident_id"])
                    previous.append((row, prior))
            credited = timedelta()
            merged = set()
            expanded = True
            while expanded:
                expanded = False
                for row, prior in previous:
                    if (
                        row["incident_id"] in merged
                        or prior["started_at"] > end
                        or prior["recovered_at"] < start
                    ):
                        continue
                    merged.add(row["incident_id"])
                    start = min(start, prior["started_at"])
                    end = max(end, prior["recovered_at"])
                    credited += max(
                        timedelta(),
                        row["new_due"]
                        - max(row["old_due"], prior["recovered_at"], row["approved_at"]),
                    )
                    expanded = True
            overlap = max(timedelta(), min(end, old_due) - max(start, assignment["open_at"]))
            segments = [
                (prior["started_at"], prior["recovered_at"])
                for row, prior in previous
                if row["incident_id"] in merged
            ]
            if not has_uncovered_interval(
                incident["started_at"], incident["recovered_at"], segments
            ):
                new_due = old_due
            else:
                additional = max(timedelta(), max(overlap, timedelta(minutes=10)) - credited)
                new_due = (
                    max(old_due, incident["recovered_at"], now) + additional
                    if additional
                    else old_due
                )
                # A continuing outage must not consume the entire previously granted window.
                new_due = max(new_due, max(incident["recovered_at"], now) + timedelta(minutes=10))
        self.repo.change(
            "incident_assignments",
            (body["incident_id"], assignment_id),
            decision=body["decision"],
            old_due=old_due,
            new_due=new_due,
            approved_by=actor["user_id"],
            approved_at=now,
            overlap_ms=int(overlap.total_seconds() * 1000),
            reason=body["reason"],
        )
        pending = any(
            row["decision"] == "PENDING"
            for row in self.repo.rows("incident_assignments", assignment_id=assignment_id)
        )
        values = dict(
            fairness_review="PENDING" if pending else "RESOLVED",
            revision=assignment["revision"] + 1,
            updated_at=now,
        )
        if new_due is not None and new_due != old_due:
            values.update(due_at=new_due, grade_epoch=assignment["grade_epoch"] + 1)
        self.repo.change("assignments", assignment_id, **values)
        self.effects.record(
            self.repo,
            actor["user_id"],
            "FAIRNESS_DECIDED",
            assignment_id,
            reason=body["reason"],
            summary={"incident_id": body["incident_id"], "decision": body["decision"]},
        )
        return dict(
            old_due_at=utc(old_due),
            new_due_at=utc(new_due) if new_due else None,
            revision=values["revision"],
            fairness_review=values["fairness_review"],
        )


def note_platform_failure(
    repo: SqlRepository, assignment_id: str, reason_code: str, request_id: str
) -> None:
    """Aggregate platform evidence after rollback or in terminalization's transaction."""
    repo.guard()
    if repo.rows("incident_requests", request_id=request_id):
        return
    assignment = repo.required("assignments", assignment_id, lock=True)
    if repo.required("courses", assignment["course_id"])["status"] != "ACTIVE":
        return
    events = repo.rows("fairness_incidents", reason_code=reason_code, recovered_at=None)
    now = repo.now()
    if events:
        event = events[0]
        incident_id = event["incident_id"]
        repo.change("fairness_incidents", incident_id, rejected_count=event["rejected_count"] + 1)
    else:
        incident_id = str(uuid4())
        repo.add(
            "fairness_incidents",
            dict(
                incident_id=incident_id,
                started_at=now,
                recovered_at=None,
                reason_code=reason_code,
                rejected_count=1,
                evidence_refs=[],
                evidence_incomplete=False,
                detected_at=now,
                displayed_at=now,
                persisted_at=now,
                recovery_started_at=None,
                revision=1,
            ),
        )
    repo.add(
        "incident_requests",
        dict(
            incident_id=incident_id,
            request_id=request_id,
            assignment_id=assignment_id,
            reason_code=reason_code,
            observed_at=now,
        ),
    )
    if repo.get("incident_assignments", (incident_id, assignment_id)) is None:
        repo.add(
            "incident_assignments",
            dict(
                incident_id=incident_id,
                assignment_id=assignment_id,
                decision="PENDING",
                old_due=assignment["due_at"],
            ),
        )
        repo.change(
            "assignments",
            assignment_id,
            fairness_review="PENDING",
            revision=assignment["revision"] + 1,
        )
        TransactionalEffects(repo, request_id).record(
            repo, None, "INCIDENT_DETECTED", incident_id, reason=reason_code
        )
