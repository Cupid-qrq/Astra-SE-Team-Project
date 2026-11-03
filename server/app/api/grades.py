from app.api.teaching import Registrar
from app.modules.identity.ports import Record


def register(add: Registrar) -> None:
    def current(c: Record) -> Record:
        value = c["grades"].read(c["actor"], c["path"]["id"])
        page = c["learning_pager"].bounded(value["students"], "student_id")
        return dict(value, students=page["items"], next_cursor=page["next_cursor"])

    add("GET", "/assignments/{id}/grades", current)
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
