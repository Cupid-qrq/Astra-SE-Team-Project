def register(add):
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
