from uuid import uuid4

from sqlalchemy import column, select, table, text
from test_http import http_env as http_env
from test_http import login

from app.main import create_app
from app.shared.repository import SqlRepository

REVIEW = "/api/v1/review-items"
RECOMMEND = "/api/v1/recommendations"


def test_student_learning_without_results_returns_dependency_error(http_env):
    _, _, _, app = http_env
    client = login(app, "student")
    assert client.get("/api/v1/ai-hints").json() == {"items": [], "next_cursor": None}
    assert login(app, "teacher").get("/api/v1/ai-hints").status_code == 403
    for path in [REVIEW + "?context=FORMAL", RECOMMEND]:
        response = client.get(path)
        assert response.status_code == 503 and response.json()["code"] == "INTEGRATION_UNAVAILABLE"
        assert login(app, "teacher").get(path).status_code == 403


class ResultSource:
    def projection(self, repo, actor):
        fields = "user_id submission_id assignment_id problem_id version_id accepted_at context verdict effective"
        return select(table("test_learning_results", *(column(name) for name in fields.split())))


def setup_source(http_env):
    engine, ids, settings, _ = http_env
    with engine.begin() as conn:
        conn.exec_driver_sql("""CREATE TABLE test_learning_results(user_id uuid, submission_id uuid,
            assignment_id uuid, problem_id uuid, version_id uuid, accepted_at timestamptz,
            context text, verdict text, effective boolean)""")
    return (
        engine,
        ids,
        login(create_app(settings, engine=engine, learning_results=ResultSource()), "student"),
    )


def record(conn, ids, context, verdict, effective=True, **overrides):
    row = dict(
        user_id=ids["student"],
        submission_id=str(uuid4()),
        assignment_id=ids["assignment"],
        problem_id=ids["problem"],
        version_id=ids["version"],
        context=context,
        verdict=verdict,
        effective=effective,
    )
    row.update(overrides)
    conn.execute(
        text("""INSERT INTO test_learning_results VALUES (:user_id,:submission_id,:assignment_id,
        :problem_id,:version_id,clock_timestamp(),:context,:verdict,:effective)"""),
        row,
    )
    return row["submission_id"]


def test_wrong_items_separate_context_and_use_effective_ac(http_env):
    engine, ids, client = setup_source(http_env)
    with engine.begin() as conn:
        record(conn, ids, "FORMAL", "WA")
        record(conn, ids, "FORMAL", "AC", False)
        record(conn, ids, "FORMAL", "AC", user_id=ids["teacher"])
        record(conn, ids, "PRACTICE", "AC")
        record(conn, ids, "PRACTICE", "RE")
        newest = record(conn, ids, "FORMAL", "TLE")
        record(conn, ids, "FORMAL", "SE")
    result = client.get(REVIEW, params={"context": "FORMAL", "course_id": ids["course"]})
    assert result.status_code == 200, result.text
    assert [(r["submission_id"], r["verdict"]) for r in result.json()["items"]] == [(newest, "TLE")]
    assert client.get(REVIEW, params={"context": "PRACTICE"}).json()["items"] == []
    with engine.begin() as conn:
        record(conn, ids, "FORMAL", "AC")
    assert client.get(REVIEW, params={"context": "FORMAL"}).json()["items"] == []
    with engine.begin() as conn:
        conn.execute(text("UPDATE course_members SET status='DISABLED'"))
    assert (
        client.get(REVIEW, params={"context": "FORMAL", "course_id": ids["course"]}).status_code
        == 404
    )


def test_rule_recommendations_filter_families_before_ranking_and_limit(http_env):
    engine, ids, client = setup_source(http_env)
    assert client.get(RECOMMEND).json() == {"items": []}
    with engine.begin() as conn:
        repo = SqlRepository(conn)
        source = repo.get("problem_versions", ids["version"])
        # Create immutable versions with ranked labels; use a newly published source revision.
        weak_vid = str(uuid4())
        repo.add(
            "problem_versions",
            {**source, "version_id": weak_vid, "version_no": 2, "tags": ["循环", "边界"]},
        )
        record(conn, ids, "FORMAL", "WA", version_id=weak_vid)
        candidates = []
        for i in range(9):
            pid, vid, family = str(uuid4()), str(uuid4()), str(uuid4())
            if i == 0:
                family = ids["family"]
            else:
                repo.add(
                    "problem_families",
                    dict(canonical_problem_id=family, owner_teacher_id=ids["teacher"], label="new"),
                )
            repo.add(
                "problems",
                {
                    **repo.get("problems", ids["problem"]),
                    "problem_id": pid,
                    "canonical_problem_id": family,
                },
            )
            tags = ["循环", "边界"] if i < 4 else ["循环"]
            repo.add(
                "problem_versions", {**source, "version_id": vid, "problem_id": pid, "tags": tags}
            )
            repo.change("problems", pid, practice_released=True, practice_version_id=vid)
            if i:
                candidates.append((len(tags), pid))
            else:
                blocked = pid
    response = client.get(RECOMMEND)
    assert response.status_code == 200, response.text
    assert [r["problem_id"] for r in response.json()["items"]] == [
        p for _, p in sorted(candidates, key=lambda t: (-t[0], t[1]))[:5]
    ]
    assert client.get("/api/v1/practice-problems/" + blocked).status_code == 404


def test_recommendations_keep_zero_matches_and_untagged_candidates(http_env):
    engine, ids, client = setup_source(http_env)
    candidates = []
    with engine.begin() as conn:
        repo = SqlRepository(conn)
        source = repo.get("problem_versions", ids["version"])
        weak_vid = str(uuid4())
        repo.add(
            "problem_versions",
            {**source, "version_id": weak_vid, "version_no": 2, "tags": ["循环"]},
        )
        for tags in [[], ["其他"], ["循环"]]:
            pid, vid, family = str(uuid4()), str(uuid4()), str(uuid4())
            repo.add(
                "problem_families",
                dict(
                    canonical_problem_id=family, owner_teacher_id=ids["teacher"], label="candidate"
                ),
            )
            repo.add(
                "problems",
                {
                    **repo.get("problems", ids["problem"]),
                    "problem_id": pid,
                    "canonical_problem_id": family,
                },
            )
            repo.add(
                "problem_versions", {**source, "problem_id": pid, "version_id": vid, "tags": tags}
            )
            repo.change("problems", pid, practice_released=True, practice_version_id=vid)
            candidates.append((pid, tags))
    without_history = client.get(RECOMMEND).json()["items"]
    assert [row["problem_id"] for row in without_history] == sorted(pid for pid, _ in candidates)
    assert all(row["tags"] == [] for row in without_history)
    with engine.begin() as conn:
        record(conn, ids, "FORMAL", "WA", version_id=weak_vid)
    ranked = client.get(RECOMMEND).json()["items"]
    assert [row["problem_id"] for row in ranked] == [
        pid for pid, tags in sorted(candidates, key=lambda pair: (-int("循环" in pair[1]), pair[0]))
    ]
    assert ranked[0]["tags"] == ["循环"]
    assert all(row["tags"] == [] for row in ranked[1:])
