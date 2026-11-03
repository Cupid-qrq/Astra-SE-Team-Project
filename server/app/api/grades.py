from app.api.teaching import Registrar


def register(add: Registrar) -> None:
    add("GET", "/assignments/{id}/grades", lambda c: c["grades"].read(c["actor"], c["path"]["id"]))
    add("GET", "/grades/{id}", lambda c: c["grades"].snapshot(c["actor"], c["path"]["id"]))
    add(
        "POST",
        "/assignments/{id}/grades/publish",
        lambda c: c["grades"].publish(c["actor"], c["path"]["id"], c["body"]),
    )
    add(
        "GET",
        "/assignments/{id}/grades.csv",
        lambda c: c["grades"].export(c["actor"], c["path"]["id"], c["query"]["grade_version"]),
    )
