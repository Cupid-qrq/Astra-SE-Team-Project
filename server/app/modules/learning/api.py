def register(add):
    add(
        "GET",
        "/ai-hints",
        lambda c: c["student_learning"].hint_history(c["actor"], c["learning_pager"]),
    )
    add("POST", "/ai-hints", lambda c: c["hints"].create(c["actor"], c["body"]))
    add("GET", "/ai-hints/{hint_id}", lambda c: c["hints"].read(c["actor"], c["path"]["hint_id"]))
    add(
        "POST",
        "/ai-hints/{id}/feedback",
        lambda c: c["hints"].rate(c["actor"], c["path"]["id"], c["body"]),
    )
    add(
        "GET",
        "/feedback-catalogs",
        lambda c: c["page"](
            c["learning"].catalogs(c["actor"], c["query"].get("course_id")), "catalog_id"
        ),
    )
    add("POST", "/feedback-catalogs", lambda c: c["learning"].create_catalog(c["actor"], c["body"]))
    add(
        "GET",
        "/feedback-catalogs/{id}/draft",
        lambda c: c["learning"].draft(c["actor"], c["path"]["id"]),
    )
    add(
        "PUT",
        "/feedback-catalogs/{id}/draft",
        lambda c: c["learning"].save_draft(c["actor"], c["path"]["id"], c["body"]),
    )
    add(
        "POST",
        "/feedback-catalogs/{id}/publish",
        lambda c: c["learning"].publish(c["actor"], c["path"]["id"], c["body"]),
    )
    add(
        "GET",
        "/feedback-catalogs/{id}/versions",
        lambda c: c["page"](c["learning"].history(c["actor"], c["path"]["id"]), "version_id"),
    )
    add(
        "GET",
        "/feedback-catalogs/{id}/versions/{version}",
        lambda c: c["learning"].version(c["actor"], c["path"]["id"], c["path"]["version"]),
    )
    add(
        "GET",
        "/submissions/{id}/feedback",
        lambda c: c["learning"].submission(c["actor"], c["path"]["id"]),
    )
    add(
        "GET",
        "/hint-templates",
        lambda c: c["page"](
            c["learning"].templates.catalogs(c["actor"], c["query"].get("course_id")), "template_id"
        ),
    )
    add(
        "POST",
        "/hint-templates",
        lambda c: c["learning"].templates.create_catalog(c["actor"], c["body"]),
    )
    add(
        "GET",
        "/hint-templates/{id}/draft",
        lambda c: c["learning"].templates.draft(c["actor"], c["path"]["id"]),
    )
    add(
        "PUT",
        "/hint-templates/{id}/draft",
        lambda c: c["learning"].templates.save_draft(c["actor"], c["path"]["id"], c["body"]),
    )
    add(
        "POST",
        "/hint-templates/{id}/publish",
        lambda c: c["learning"].templates.publish(c["actor"], c["path"]["id"], c["body"]),
    )
    add(
        "GET",
        "/hint-templates/{id}/versions",
        lambda c: c["page"](
            c["learning"].templates.history(c["actor"], c["path"]["id"]), "version_id"
        ),
    )
    add(
        "GET",
        "/hint-templates/{id}/versions/{version}",
        lambda c: c["learning"].templates.version(
            c["actor"], c["path"]["id"], c["path"]["version"]
        ),
    )

    add(
        "GET",
        "/review-items",
        lambda c: c["student_learning"].review(c["actor"], c["query"], c["learning_pager"]),
    )
    add(
        "GET",
        "/recommendations",
        lambda c: c["student_learning"].recommendations(c["actor"], c["query"].get("course_id")),
    )
