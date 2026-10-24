from uuid import NAMESPACE_URL, uuid5

from app.modules.courses.application import Courses
from app.modules.identity.domain import Fault, require, role
from app.modules.identity.ports import Effects, Record, Repository

from .domain import VERDICTS, checksum, public_version
from .ports import FeedbackSubmissions

SEEDS = {
    "CE": dict(
        title="编译错误",
        explanation="程序未能完成编译。请结合可见的编译诊断检查语法与语言设置。",
        checklist=["确认提交语言与源码一致。", "检查括号、标点、名称和所需声明。"],
    ),
    "WA": dict(
        title="答案错误",
        explanation="程序完成运行，但输出与题目要求不一致。样例通过并不代表覆盖全部边界。",
        checklist=[
            "核对输入输出格式及空白要求。",
            "检查最小值、最大值、重复值和特殊情况。",
            "用小规模自编数据手工核算。",
        ],
    ),
    "TLE": dict(
        title="超出时间限制",
        explanation="本次运行超出题目规定的时间限制。",
        checklist=["检查循环是否能结束、是否等待不存在的输入。", "根据数据范围估算算法复杂度。"],
    ),
    "RE": dict(
        title="运行错误",
        explanation="程序运行过程中异常终止。",
        checklist=["检查数组边界、空值和除零。", "检查递归深度、内存使用及输入读取。"],
    ),
    "SE": dict(
        title="平台故障",
        explanation="本次评测遇到平台或执行环境故障，不能据此判定代码是否正确。请保留提交编号并查看平台通知，必要时联系教师。",
        checklist=["等待平台恢复或教师处理，避免反复创建相同提交。"],
    ),
}


def seed_global_feedback(repo: Repository, author_id: str) -> dict[str, str]:
    """Explicit, idempotent bootstrap after the real administrator exists.

    No startup side effects. Caller owns transaction; never overwrite newer versions.
    """
    repo.guard()
    author = repo.get("users", author_id)
    require(
        author is not None and author["role"] == "ADMIN" and author["status"] == "ACTIVE",
        "SEED_AUTHOR_REQUIRED",
        "种子发布需要已有的有效管理员。",
        422,
    )
    result = {}
    for verdict, body in SEEDS.items():
        digest = checksum(body)
        cid = str(uuid5(NAMESPACE_URL, f"astra/feedback/GLOBAL/{verdict}/ALL"))
        vid = str(uuid5(NAMESPACE_URL, f"astra/feedback/GLOBAL/{verdict}/ALL/1"))
        existing = repo.get("feedback_versions", vid)
        if existing:
            require(
                existing["checksum"] == digest,
                "SEED_CONFLICT",
                "既有种子与当前版本不一致，请发布新版本。",
            )
        else:
            require(
                repo.get("feedback_catalogs", cid) is None,
                "SEED_CONFLICT",
                "种子目录已存在但缺少初始版本。",
            )
            repo.add(
                "feedback_catalogs",
                dict(
                    catalog_id=cid,
                    scope_key="GLOBAL",
                    verdict=verdict,
                    language_key="ALL",
                    draft_payload=body,
                    draft_revision=1,
                    active_version_id=None,
                ),
            )
            repo.add(
                "feedback_versions",
                dict(
                    version_id=vid,
                    catalog_id=cid,
                    version_no=1,
                    **body,
                    author_id=author_id,
                    published_at=repo.now(),
                    checksum=digest,
                ),
            )
            repo.change("feedback_catalogs", cid, active_version_id=vid)
        result[verdict] = vid
    return result


class Learning:
    def __init__(
        self, repo: Repository, effects: Effects, submissions: FeedbackSubmissions | None = None
    ):
        self.repo, self.courses, self.submissions = repo, Courses(repo, effects), submissions

    def resolve(self, course_id: str, language: str, verdict: str) -> str | None:
        """Internal terminalization query; caller already authorized and owns locks/UoW."""
        if verdict not in VERDICTS:
            return None
        for scope, lang in [
            ("COURSE:" + course_id, language),
            ("COURSE:" + course_id, "ALL"),
            ("GLOBAL", "ALL"),
        ]:
            catalogs = self.repo.rows(
                "feedback_catalogs", scope_key=scope, language_key=lang, verdict=verdict
            )
            if catalogs and catalogs[0]["active_version_id"]:
                return catalogs[0]["active_version_id"]
        raise Fault(503, "FEEDBACK_UNAVAILABLE", "固定帮助尚未初始化。", retry=5)

    def catalog_access(self, actor: Record, catalog: Record):
        role(actor, ("STUDENT", "TEACHER", "ADMIN"))
        if catalog["scope_key"] != "GLOBAL":
            self.courses.access(actor, catalog["scope_key"].removeprefix("COURSE:"))

    def version(self, actor: Record, catalog_id: str, number: str) -> Record:
        require(
            number.isascii() and number.isdigit() and 0 < int(number) <= 2147483647,
            "VALIDATION_ERROR",
            "版本号必须为正整数。",
            422,
        )
        catalog = self.repo.get("feedback_catalogs", catalog_id)
        require(catalog is not None, "NOT_FOUND", "帮助不存在或无权读取。", 404)
        assert catalog
        self.catalog_access(actor, catalog)
        rows = self.repo.rows("feedback_versions", catalog_id=catalog_id, version_no=int(number))
        require(bool(rows), "NOT_FOUND", "帮助版本不存在。", 404)
        return public_version(rows[0])

    def submission(self, actor: Record, submission_id: str) -> Record:
        role(actor, ("STUDENT", "TEACHER"))
        if self.submissions is None:
            raise Fault(503, "INTEGRATION_UNAVAILABLE", "提交帮助查询尚未接入。", retry=5)
        item = self.submissions.feedback(self.repo, actor, submission_id)
        require(item is not None, "NOT_FOUND", "提交不存在或无权读取。", 404)
        assert item
        require(
            actor["role"] != "STUDENT" or actor["user_id"] == item["user_id"],
            "NOT_FOUND",
            "提交不存在或无权读取。",
            404,
        )
        self.courses.access(actor, item["course_id"])
        require(
            item["state"] == "FINISHED" and item["verdict"] in VERDICTS,
            "FEEDBACK_NOT_APPLICABLE",
            "当前评测状态没有固定错误帮助。",
        )
        row = (
            self.repo.get("feedback_versions", item["feedback_version_id"])
            if item["feedback_version_id"]
            else None
        )
        require(row is not None, "FEEDBACK_UNAVAILABLE", "该轮次尚无冻结的帮助版本。", 503)
        assert row
        catalog = self.repo.get("feedback_catalogs", row["catalog_id"])
        require(
            catalog is not None
            and catalog["verdict"] == item["verdict"]
            and catalog["scope_key"] in ("GLOBAL", "COURSE:" + item["course_id"]),
            "FEEDBACK_UNAVAILABLE",
            "帮助引用与评测不一致。",
            503,
        )
        return public_version(row)
