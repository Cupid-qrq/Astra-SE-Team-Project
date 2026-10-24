import hmac
import secrets
from datetime import timedelta
from hashlib import sha256
from uuid import uuid4

from .domain import Fault, live_session, require, revision, role, utc
from .ports import Effects, Passwords, Record, Repository

USER_FIELDS = (
    "user_id",
    "login_name",
    "display_name",
    "role",
    "status",
    "must_change_password",
    "revision",
)


def public_user(user: Record) -> Record:
    return {key: user[key] for key in USER_FIELDS}


def digest(value: str) -> str:
    return sha256(value.encode()).hexdigest()


class Identity:
    def __init__(self, repo: Repository, passwords: Passwords, effects: Effects, secret: bytes):
        self.repo, self.passwords, self.effects, self.secret = repo, passwords, effects, secret

    def csrf(self, token: str) -> str:
        return hmac.new(self.secret, token.encode(), "sha256").hexdigest()

    def session_row(self, token: str | None) -> Record | None:
        rows = self.repo.rows("sessions", token_hash=digest(token or ""))
        if not rows or not live_session(rows[0], self.repo.now()):
            return None
        row = rows[0]
        if row["user_id"]:
            user = self.repo.get("users", row["user_id"])
            if not user or user["status"] != "ACTIVE":
                return None
        return row

    def issue(self, user_id: str | None) -> tuple[str, Record]:
        token = secrets.token_urlsafe(32)
        now = self.repo.now()
        row = self.repo.add(
            "sessions",
            dict(
                session_id=str(uuid4()),
                user_id=user_id,
                token_hash=digest(token),
                csrf_hash=digest(self.csrf(token)),
                created_at=now,
                last_seen_at=now,
                expires_at=now + timedelta(hours=8),
                revoked_at=None,
            ),
        )
        return token, row

    def session(self, token: str | None) -> tuple[Record, str | None]:
        row = self.session_row(token)
        new_token = None
        if row is None:
            new_token, row = self.issue(None)
            token = new_token
        else:
            self.repo.change("sessions", row["session_id"], last_seen_at=self.repo.now())
        user = self.repo.get("users", row["user_id"]) if row["user_id"] else None
        return dict(
            authenticated=user is not None,
            user=public_user(user) if user else None,
            csrf_token=self.csrf(token or ""),
            server_time=utc(self.repo.now()),
        ), new_token

    def actor(self, token: str | None, *, allow_password: bool = False) -> Record:
        row = self.session_row(token)
        require(bool(row and row["user_id"]), "UNAUTHENTICATED", "会话已失效，请重新登录。", 401)
        assert row
        user = self.repo.get("users", row["user_id"])
        assert user
        require(
            allow_password or not user["must_change_password"],
            "PASSWORD_CHANGE_REQUIRED",
            "请先修改初始密码。",
            403,
        )
        self.repo.change("sessions", row["session_id"], last_seen_at=self.repo.now())
        return user

    def check_csrf(
        self, token: str | None, supplied: str | None, origin: str | None, expected_origin: str
    ) -> None:
        row = self.session_row(token)
        require(
            origin == expected_origin
            and bool(supplied)
            and row is not None
            and hmac.compare_digest(row["csrf_hash"], digest(supplied or "")),
            "CSRF_FAILED",
            "请求校验失败，请刷新页面后重试。",
            403,
        )

    def login(self, token: str, body: Record, source: str) -> tuple[Record, str]:
        now = self.repo.now()
        login_digest = digest(body["login_name"])
        attempts = self.repo.rows("login_attempts", login_digest=login_digest)
        failures = sorted(
            (
                a
                for a in attempts
                if not a["succeeded"] and a["attempted_at"] > now - timedelta(minutes=20)
            ),
            key=lambda a: a["attempted_at"],
        )
        for i in range(4, len(failures)):
            fifth = failures[i]["attempted_at"]
            if fifth - failures[i - 4]["attempted_at"] < timedelta(
                minutes=10
            ) and now < fifth + timedelta(minutes=10):
                remaining = max(1, int((fifth + timedelta(minutes=10) - now).total_seconds()))
                raise Fault(429, "LOGIN_COOLDOWN", "登录尝试过多，请稍后重试。", retry=remaining)
        rows = self.repo.rows("users", login_name=body["login_name"])
        user = rows[0] if rows else None
        correct = self.passwords.verify(body["password"], user["password_hash"] if user else None)
        success = bool(correct and user and user["status"] == "ACTIVE")
        self.repo.add(
            "login_attempts",
            dict(
                attempt_id=str(uuid4()),
                login_digest=login_digest,
                source_digest=digest(source),
                succeeded=success,
                attempted_at=now,
            ),
        )
        if not success:
            raise Fault(401, "INVALID_CREDENTIALS", "账号或密码错误。", commit=True)
        assert user
        old = self.session_row(token)
        if old:
            self.repo.change("sessions", old["session_id"], revoked_at=now)
        for failure in failures:
            self.repo.remove("login_attempts", failure["attempt_id"])
        new_token, _ = self.issue(user["user_id"])
        return {"user": public_user(user)}, new_token

    def revoke(self, user_id: str) -> None:
        for row in self.repo.rows("sessions", user_id=user_id):
            self.repo.change("sessions", row["session_id"], revoked_at=self.repo.now())

    def logout(self, token: str) -> None:
        row = self.session_row(token)
        if row:
            self.repo.change("sessions", row["session_id"], revoked_at=self.repo.now())

    def password(self, actor: Record, body: Record) -> None:
        require(
            self.passwords.verify(body["current_password"], actor["password_hash"]),
            "INVALID_CREDENTIALS",
            "当前密码不正确。",
            403,
        )
        require(
            body["new_password"] != body["current_password"],
            "VALIDATION_ERROR",
            "新密码不能与当前密码相同。",
            422,
        )
        self.repo.change(
            "users",
            actor["user_id"],
            password_hash=self.passwords.hash(body["new_password"]),
            must_change_password=False,
            revision=actor["revision"] + 1,
            updated_at=self.repo.now(),
        )
        self.revoke(actor["user_id"])
        self.effects.record(self.repo, actor["user_id"], "PASSWORD_CHANGED", actor["user_id"])

    def create_user(self, actor: Record, body: Record) -> Record:
        role(actor, ("ADMIN",))
        require(
            not self.repo.rows("users", login_name=body["login_name"]),
            "LOGIN_NAME_EXISTS",
            "登录名已存在。",
        )
        now = self.repo.now()
        user = self.repo.add(
            "users",
            dict(
                user_id=str(uuid4()),
                login_name=body["login_name"],
                display_name=body["display_name"],
                role=body["role"],
                status="ACTIVE",
                password_hash=self.passwords.hash(body["initial_password"]),
                must_change_password=True,
                revision=1,
                created_at=now,
                updated_at=now,
            ),
        )
        self.effects.record(
            self.repo, actor["user_id"], "USER_CREATED", user["user_id"], body["reason"]
        )
        return public_user(user)

    def update_user(
        self, actor: Record, user_id: str, body: Record, *, reset: bool = False
    ) -> Record:
        role(actor, ("ADMIN",))
        user = self.repo.get("users", user_id, lock=True)
        require(user is not None, "NOT_FOUND", "账号不存在。", 404)
        assert user
        revision(user, body["expected_revision"])
        changes: Record = dict(revision=user["revision"] + 1, updated_at=self.repo.now())
        if reset:
            changes.update(
                password_hash=self.passwords.hash(body["one_time_password"]),
                must_change_password=True,
            )
        else:
            require(
                not (user_id == actor["user_id"] and body.get("status") == "DISABLED"),
                "SELF_DISABLE",
                "不能停用当前管理员账号。",
            )
            changes.update({k: body[k] for k in ("display_name", "status") if k in body})
        if reset or body.get("status") == "DISABLED":
            self.revoke(user_id)
        if body.get("status") == "DISABLED" and user["status"] != "DISABLED":
            self.effects.account_disabled(self.repo, user_id)
        result = self.repo.change("users", user_id, **changes)
        self.effects.record(
            self.repo,
            actor["user_id"],
            "PASSWORD_RESET" if reset else "USER_UPDATED",
            user_id,
            body["reason"],
        )
        return public_user(result)
