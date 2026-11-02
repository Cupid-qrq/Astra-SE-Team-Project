"""All operations run behind the shared policy guard in the caller-owned transaction."""

from datetime import date
from decimal import Decimal

from app.modules.identity.domain import Fault, require
from app.modules.identity.ports import Record, Repository


class HintLedger:
    def __init__(self, repo: Repository):
        self.repo = repo

    def _accounts(self, day: date) -> list[Record]:
        accounts = []
        for key, cap in (("PROJECT", 500), ("DAY:" + day.isoformat(), 20)):
            account = self.repo.get("budget_accounts", key, lock=True)
            if account is None:
                account = self.repo.add(
                    "budget_accounts",
                    dict(
                        scope_key=key,
                        limit_amount=cap,
                        settled_amount=0,
                        reserved_amount=0,
                        uncertain_amount=0,
                        revision=1,
                    ),
                )
            accounts.append(account)
        return accounts

    def reserve(self, hint: Record, upper: Decimal) -> None:
        user, day = hint["user_id"], hint["accepted_date"]
        key = user, day
        quota = self.repo.get("quota_ledger", key, lock=True)
        if quota is None:
            quota = self.repo.add(
                "quota_ledger", dict(user_id=user, accepted_date=day, ready=0, reserved=0)
            )
        require(
            quota["ready"] + quota["reserved"] < 20, "HINT_DAILY_LIMIT", "今日提示次数已用完。", 429
        )
        accounts = self._accounts(day)
        for a in accounts:
            if (
                a["settled_amount"] + a["reserved_amount"] + a["uncertain_amount"] + upper
                > a["limit_amount"]
            ):
                raise Fault(503, "MODEL_BUDGET_EXHAUSTED", "模型预算不足。", retry=60)
        self.repo.change("quota_ledger", key, reserved=quota["reserved"] + 1)
        for a in accounts:
            self.repo.change(
                "budget_accounts",
                a["scope_key"],
                reserved_amount=a["reserved_amount"] + upper,
                revision=a["revision"] + 1,
            )
        self.repo.add(
            "budget_reservations",
            dict(
                hint_id=hint["hint_id"],
                accepted_date=day,
                cost_upper=upper,
                actual=None,
                state="RESERVED",
            ),
        )

    def settle(
        self, hint: Record, state: str, actual: Decimal | None, *, ready: bool = False
    ) -> bool:
        reservation = self.repo.get("budget_reservations", hint["hint_id"], lock=True)
        assert reservation
        prior = reservation["state"]
        if prior not in ("UNCERTAIN", "RESERVED") or (prior == "UNCERTAIN" and state != "SETTLED"):
            return False
        require(
            state in ("RELEASED", "UNCERTAIN", "SETTLED")
            and (
                (isinstance(actual, Decimal) and actual.is_finite() and actual >= 0)
                if state == "SETTLED"
                else actual is None
            ),
            "INVALID_SETTLEMENT",
            "费用记录无效。",
            422,
        )
        day = hint["accepted_date"]
        if prior == "RESERVED":
            key = hint["user_id"], day
            quota = self.repo.get("quota_ledger", key, lock=True)
            assert quota
            self.repo.change(
                "quota_ledger",
                key,
                reserved=quota["reserved"] - 1,
                ready=quota["ready"] + int(ready),
            )
        upper = reservation["cost_upper"]
        for a in self._accounts(day):
            self.repo.change(
                "budget_accounts",
                a["scope_key"],
                reserved_amount=a["reserved_amount"] - (upper if prior == "RESERVED" else 0),
                uncertain_amount=a["uncertain_amount"]
                + (upper if state == "UNCERTAIN" else 0)
                - (upper if prior == "UNCERTAIN" else 0),
                settled_amount=a["settled_amount"] + (actual or 0),
                revision=a["revision"] + 1,
            )
        self.repo.change("budget_reservations", hint["hint_id"], actual=actual, state=state)
        return True
