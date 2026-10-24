"""Route binding consumed by the host HTTP/UoW adapter (no standalone imports)."""

from app.modules.identity.domain import Fault


def register(add):
    add(
        "GET",
        "/courses/{id}/problems",
        lambda c: c["page"](
            c["problems"].visible(c["actor"], c["path"]["id"], c["query"].get("tag")), "problem_id"
        ),
    )
    add("POST", "/problems", lambda c: c["problems"].create(c["actor"], c["body"]))
    add(
        "GET",
        "/problems/{id}/versions",
        lambda c: c["page"](c["problems"].version_list(c["actor"], c["path"]["id"]), "version_id"),
    )
    add("POST", "/problem-versions", lambda c: c["problems"].create_version(c["actor"], c["body"]))
    add(
        "GET",
        "/problem-versions/{id}",
        lambda c: c["problems"].view(c["problems"].version(c["actor"], c["path"]["id"])),
    )
    add(
        "PATCH",
        "/problem-versions/{id}",
        lambda c: c["problems"].update(c["actor"], c["path"]["id"], c["body"]),
    )
    add(
        "DELETE",
        "/problem-versions/{id}",
        lambda c: c["problems"].delete(c["actor"], c["path"]["id"], c["body"]),
    )

    def materials(c, references=False):
        c["problems"].version(c["actor"], c["path"]["id"])
        values = (
            c["problems"].references(c["path"]["id"])
            if references
            else c["problems"].cases(c["path"]["id"])
        )
        return c["page"](values, "language_key" if references else "order")

    add("GET", "/problem-versions/{id}/testcases", materials)
    add("GET", "/problem-versions/{id}/references", lambda c: materials(c, True))

    def testcase(c, delete=False):
        try:
            order = int(c["path"]["order"])
        except ValueError:
            raise Fault(422, "VALIDATION_ERROR", "测试编号无效。") from None
        return c["problems"].put_case(c["actor"], c["path"]["id"], order, c["body"], delete=delete)

    add("PUT", "/problem-versions/{id}/testcases/{order}", testcase)
    add("DELETE", "/problem-versions/{id}/testcases/{order}", lambda c: testcase(c, True))
    add(
        "PUT",
        "/problem-versions/{id}/references/{language_key}",
        lambda c: c["problems"].put_reference(
            c["actor"], c["path"]["id"], c["path"]["language_key"], c["body"]
        ),
    )
    add(
        "POST",
        "/problem-versions/{id}/publish",
        lambda c: c["problems"].publish(c["actor"], c["path"]["id"], c["body"]),
    )
