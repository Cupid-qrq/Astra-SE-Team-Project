def register(add):
    add(
        "GET",
        "/courses/{id}/assignments",
        lambda c: c["page"](c["assignments"].visible(c["actor"], c["path"]["id"]), "assignment_id"),
    )
    add("POST", "/assignments", lambda c: c["assignments"].create(c["actor"], c["body"]))
    add("GET", "/assignments/{id}", lambda c: c["assignments"].view(c["actor"], c["path"]["id"]))
    add(
        "PATCH",
        "/assignments/{id}",
        lambda c: c["assignments"].update(c["actor"], c["path"]["id"], c["body"]),
    )
    add(
        "POST",
        "/assignments/{id}/publish",
        lambda c: c["assignments"].publish(c["actor"], c["path"]["id"], c["body"]),
    )
    add(
        "GET",
        "/assignments/{id}/problems/{problem_id}",
        lambda c: c["assignments"].problem(c["actor"], c["path"]["id"], c["path"]["problem_id"]),
    )
    add(
        "PATCH",
        "/assignments/{id}/deadline",
        lambda c: c["assignments"].controlled(
            c["actor"], c["path"]["id"], c["body"], "DEADLINE_EXTENDED"
        ),
    )
    add(
        "PATCH",
        "/assignments/{id}/ai-policy",
        lambda c: c["assignments"].controlled(
            c["actor"], c["path"]["id"], c["body"], "POLICY_CHANGED"
        ),
    )
