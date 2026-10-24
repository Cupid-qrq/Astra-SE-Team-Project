def register(add):
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
