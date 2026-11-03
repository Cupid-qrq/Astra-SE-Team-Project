from app.api.teaching import Registrar


def register(add: Registrar) -> None:
    add(
        "POST",
        "/assignments/{id}/rejudge-preview",
        lambda c: c["rejudges"].preview(c["actor"], c["path"]["id"], c["body"]),
    )
    add(
        "POST",
        "/assignments/{id}/rejudge",
        lambda c: c["rejudges"].create(c["actor"], c["path"]["id"], c["body"]),
    )
    add("GET", "/rejudge-batches/{id}", lambda c: c["rejudges"].read(c["actor"], c["path"]["id"]))
    add(
        "POST",
        "/rejudge-batches/{id}/activate",
        lambda c: c["rejudges"].activate(c["actor"], c["path"]["id"], c["body"]),
    )
    add(
        "POST",
        "/rejudge-batches/{id}/cancel",
        lambda c: c["rejudges"].cancel(c["actor"], c["path"]["id"], c["body"]),
    )
    add(
        "POST",
        "/rejudge-batches/{id}/retry",
        lambda c: c["rejudges"].retry(c["actor"], c["path"]["id"], c["body"]),
    )
    add(
        "POST",
        "/submissions/{id}/retry",
        lambda c: c["operations"].retry(c["actor"], c["path"]["id"], c["body"]),
    )
    add("GET", "/admin/health", lambda c: c["operations"].health(c["actor"]))
    add("GET", "/admin/jobs", lambda c: c["operations"].queue(c["actor"], c["learning_pager"]))
    add(
        "GET",
        "/admin/audit-events",
        lambda c: c["operations"].audit(c["actor"], c["learning_pager"]),
    )
    add("POST", "/admin/incidents", lambda c: c["fairness"].create(c["actor"], c["body"]))
    add(
        "PATCH",
        "/admin/incidents/{id}/recovery",
        lambda c: c["fairness"].recovery(c["actor"], c["path"]["id"], c["body"]),
    )
    add("GET", "/incidents", lambda c: c["fairness"].list(c["actor"], c["learning_pager"]))
    add("GET", "/incidents/{id}", lambda c: c["fairness"].read(c["actor"], c["path"]["id"]))
    add(
        "POST",
        "/assignments/{id}/fairness-decisions",
        lambda c: c["fairness"].decide(c["actor"], c["path"]["id"], c["body"]),
    )
    add(
        "GET",
        "/notifications",
        lambda c: c["operations"].list_notifications(c["actor"], c["learning_pager"]),
    )
    add(
        "POST",
        "/notifications/{id}/read",
        lambda c: c["operations"].mark_read(c["actor"], c["path"]["id"]),
    )

    add(
        "POST",
        "/courses/{id}/archive",
        lambda c: c["retention"].archive(c["actor"], c["path"]["id"], c["body"]),
    )
    add(
        "POST", "/admin/retention/previews", lambda c: c["retention"].preview(c["actor"], c["body"])
    )
    add("GET", "/admin/retention/{id}", lambda c: c["retention"].read(c["actor"], c["path"]["id"]))
    add(
        "POST",
        "/retention/{id}/confirm",
        lambda c: c["retention"].confirm(c["actor"], c["path"]["id"], c["body"]),
    )
    add(
        "POST",
        "/admin/retention/{id}/execute",
        lambda c: c["retention"].execute(c["actor"], c["path"]["id"], c["body"]),
    )
    add("POST", "/admin/holds", lambda c: c["retention"].hold(c["actor"], c["body"]))
    add(
        "POST",
        "/admin/holds/{id}/close",
        lambda c: c["retention"].close_hold(c["actor"], c["path"]["id"], c["body"]),
    )
    add("GET", "/admin/runtime-config", lambda c: c["controls"].config(c["actor"]))
    add("PATCH", "/admin/runtime-config", lambda c: c["controls"].update(c["actor"], c["body"]))
    add("POST", "/admin/emergency-access", lambda c: c["controls"].grant(c["actor"], c["body"]))
    add(
        "POST",
        "/admin/emergency-access/{id}/revoke",
        lambda c: c["controls"].revoke(c["actor"], c["path"]["id"], c["body"]),
    )
    add(
        "GET",
        "/admin/emergency-access/{id}/submission",
        lambda c: c["controls"].read_submission(
            c["actor"], c["path"]["id"], c["query"]["submission_id"]
        ),
    )
