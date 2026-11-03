"""Explicit independent hint worker. No default B Sources or synthetic submissions.

Bootstrap: python -m app.modules.learning.hint_worker --profile FILE --bootstrap
Run:       python -m app.modules.learning.hint_worker --profile FILE --sources module:factory
The trusted factory receives the database Engine and returns the B Sources implementation.
No provider call is retried; each committed permit is consumed only once.
"""

import argparse
import asyncio
import importlib
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass, field

import httpx
from sqlalchemy.engine import Engine

from app.modules.identity.ports import Record
from app.shared.database import create_database_engine
from app.shared.effects import TransactionalEffects
from app.shared.repository import SqlRepository
from app.shared.uow import UnitOfWork

from .hint_runner import run_one
from .hint_service import HintService, Sources
from .model_activation import activate_template
from .model_runtime import RuntimeProfile, content_gate
from .model_worker import FrozenModel, ModelNotDispatched, ModelReply


def bootstrap(engine: Engine, profile: RuntimeProfile) -> None:
    with UnitOfWork(engine) as connection:
        profile.bootstrap(SqlRepository(connection))


@dataclass(frozen=True)
class HintWorker:
    engine: Engine = field(repr=False)
    profile: RuntimeProfile
    sources: Sources | None = field(repr=False)
    http_transport: httpx.AsyncBaseTransport | None = field(default=None, repr=False)

    @property
    def configuration(self) -> str:
        return self.profile.config_id

    @contextmanager
    def transaction(self) -> Iterator[HintService]:
        with UnitOfWork(self.engine) as connection:
            yield HintService(
                SqlRepository(connection),
                self.sources,
                self.configuration,
                self.profile.project_budget_cny,
            )

    async def generate(self, context: Record, model: FrozenModel) -> ModelReply:
        # Resolve the accepted immutable template, then close the read transaction before
        # credentials are loaded or a client is constructed. Never use today's active template.
        if model != self.profile.frozen_model(model.template_version_id):
            raise ModelNotDispatched("MODEL_VERSION_CHANGED")
        with UnitOfWork(self.engine) as connection:
            repo = SqlRepository(connection)
            config = repo.get("model_configs", self.configuration)
            template = repo.get("template_versions", model.template_version_id)
        if config != self.profile.record() or template is None:
            raise ModelNotDispatched("MODEL_VERSION_CHANGED")
        transport = None
        try:
            transport = self.profile.transport(
                model.template_version_id,
                template,
                http_transport=self.http_transport,
            )
        except ValueError:
            pass
        if transport is None:
            raise ModelNotDispatched("MODEL_LOCAL_CONFIG_UNAVAILABLE")
        return await transport.generate(context, model)

    async def run_once(self) -> bool:
        if self.sources is None or not self.profile.enabled:
            return False
        return await run_one(self.transaction, self, content_gate)


def build_worker(
    engine: Engine,
    profile: RuntimeProfile,
    *,
    sources: Sources | None = None,
    http_transport: httpx.AsyncBaseTransport | None = None,
) -> HintWorker:
    return HintWorker(engine, profile, sources, http_transport)


def main() -> None:
    import os
    from uuid import uuid4

    parser = argparse.ArgumentParser(description="Explicit official Flash hint worker")
    parser.add_argument("--profile", required=True)
    parser.add_argument("--bootstrap", action="store_true")
    parser.add_argument("--sources", help="Trusted B adapter factory module:attribute")
    parser.add_argument("--once", action="store_true")
    parser.add_argument("--activate-template", help="Explicit template catalogue UUID")
    parser.add_argument("--version", help="Explicit immutable version UUID")
    parser.add_argument("--checksum", help="Expected SHA-256 of the reviewed version")
    parser.add_argument("--actor", help="Existing administrator or owning teacher UUID")
    parser.add_argument("--reason", help="Deployment reason, 10-500 characters")
    args = parser.parse_args()
    if args.activate_template and (
        args.bootstrap
        or args.sources
        or args.once
        or not all((args.version, args.checksum, args.actor, args.reason))
    ):
        parser.error("Activation requires --version --checksum --actor --reason only.")
    if not args.activate_template and any((args.version, args.checksum, args.actor, args.reason)):
        parser.error("Template arguments require --activate-template.")
    profile = RuntimeProfile.from_file(args.profile)
    engine = create_database_engine(os.environ["ASTRA_DATABASE_URL"])
    try:
        if args.activate_template:
            with UnitOfWork(engine) as connection:
                repo = SqlRepository(connection)
                activate_template(
                    repo,
                    TransactionalEffects(repo, str(uuid4())),
                    actor_id=args.actor,
                    template_id=args.activate_template,
                    version_id=args.version,
                    checksum=args.checksum,
                    reason=args.reason,
                )
            return
        if args.bootstrap:
            bootstrap(engine, profile)
            return
        if not args.sources:
            parser.error(
                "A trusted --sources factory is required; production sources are unavailable."
            )
        module, name = args.sources.split(":", 1)
        sources = getattr(importlib.import_module(module), name)(engine)
        worker = build_worker(engine, profile, sources=sources)

        async def loop() -> None:
            while True:
                worked = await worker.run_once()
                if args.once:
                    return
                if not worked:
                    await asyncio.sleep(0.5)

        asyncio.run(loop())
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
