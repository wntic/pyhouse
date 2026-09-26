# hex-wiring — the composition root

Topic file of `hex-wiring`. The mechanism-free obligations are `## Rules` in `SKILL.md`; what follows
is the **dishka** binding that satisfies them.

```python
from collections.abc import AsyncIterator

import aioboto3
import httpx
from dishka import AnyOf, AsyncContainer, Provider, Scope, make_async_container, provide
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from myapp.application.foos import (
    CreateFooHandler,
    DeleteFooHandler,
    GetFooHandler,
    ListFoosHandler,
    UpdateFooHandler,
)
from myapp.domain.bars import IBarRepository, ICanCanonicalizeBarUrl, ICanFetchBarToken
from myapp.domain.foos import (
    FooExportTunable,
    FooUniquenessService,
    ICanFetchFoos,
    ICanStoreFoos,
    IFooRepository,
)
from myapp.infrastructure.export import ExportSettings
from myapp.infrastructure.http import BarGatewaySettings, HttpBarGateway
from myapp.infrastructure.idna import IdnaBarUrlCanonicalizer, IdnaSettings
from myapp.infrastructure.postgres import DbSettings, create_engine, create_session_factory
from myapp.infrastructure.postgres.repositories import FooRepository
from myapp.infrastructure.redis import RedisSettings, create_archive_client
from myapp.infrastructure.redis.repositories import BarRepository
from myapp.infrastructure.s3 import S3FooStorage, S3Settings

__all__ = ["create_container"]


class SettingsProvider(Provider):
    """1. Settings — process lifetime; everything else may depend on them."""

    scope = Scope.APP

    @provide
    def db_settings(self) -> DbSettings:
        return DbSettings()

    @provide
    def s3_settings(self) -> S3Settings:
        return S3Settings()

    @provide
    def redis_settings(self) -> RedisSettings:
        return RedisSettings()

    @provide
    def bar_gateway_settings(self) -> BarGatewaySettings:
        return BarGatewaySettings()

    @provide
    def idna_settings(self) -> IdnaSettings:
        return IdnaSettings()

    @provide
    def export_settings(self) -> ExportSettings:
        return ExportSettings()


class InfrastructureProvider(Provider):
    """2. Long-lived handles, each released after its yield, and 3. cross-cutting adapters."""

    scope = Scope.APP

    @provide
    async def engine(self, settings: DbSettings) -> AsyncIterator[AsyncEngine]:
        engine = create_engine(settings=settings)
        yield engine
        await engine.dispose()

    @provide
    def session_factory(self, engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
        return create_session_factory(engine=engine)

    @provide
    def s3_session(self, settings: S3Settings) -> aioboto3.Session:
        # A session holds credentials, not connections; the adapter opens a client per call.
        return aioboto3.Session(
            aws_access_key_id=settings.access_key,
            aws_secret_access_key=settings.secret_key.get_secret_value(),
        )

    @provide
    async def archive_client(self, settings: RedisSettings) -> AsyncIterator[Redis]:
        client = create_archive_client(settings)
        yield client
        await client.aclose()

    @provide
    async def http_client(self, settings: BarGatewaySettings) -> AsyncIterator[httpx.AsyncClient]:
        async with httpx.AsyncClient(timeout=settings.timeout_seconds) as client:
            yield client

    foo_storage = provide(S3FooStorage, provides=AnyOf[ICanStoreFoos, ICanFetchFoos])
    bar_gateway = provide(HttpBarGateway, provides=ICanFetchBarToken)
    bar_url_canonicalizer = provide(IdnaBarUrlCanonicalizer, provides=ICanCanonicalizeBarUrl)


class BarsProvider(Provider):
    scope = Scope.REQUEST

    bar_repository = provide(BarRepository, provides=IBarRepository)


class FoosProvider(Provider):
    """4. One provider class per subdomain: repository, then the services that use it,
    then the handlers that use them. `provides=` is what binds the adapter to the port;
    every constructor argument is resolved from its annotation, so nothing is passed here.
    """

    scope = Scope.REQUEST

    foo_repository = provide(FooRepository, provides=IFooRepository)
    foo_uniqueness_service = provide(FooUniquenessService)

    create_foo_handler = provide(CreateFooHandler)
    get_foo_handler = provide(GetFooHandler)
    list_foos_handler = provide(ListFoosHandler)
    update_foo_handler = provide(UpdateFooHandler)
    delete_foo_handler = provide(DeleteFooHandler)

    # 5. A tunable value object is process-lifetime and takes single settings fields.
    @provide(scope=Scope.APP)
    def foo_export_tunable(self, settings: ExportSettings) -> FooExportTunable:
        return FooExportTunable(max_rows=settings.max_rows)


def create_container(*overrides: Provider) -> AsyncContainer:
    """The composition root. `overrides` is the test seam and nothing else appends to it
    (`hex-test-integration-setup`)."""
    return make_async_container(
        SettingsProvider(),
        InfrastructureProvider(),
        BarsProvider(),
        FoosProvider(),
        *overrides,
    )
```

The template binds every adapter the catalogue defines, so it binds `Bar`'s key-value repository
beside `Foo`'s relational one — each aggregate on its one authoritative store (`hex-store-repository`
rule 1). One adapter satisfying two ports is bound once, to both (`AnyOf`), so the two ports share the
one instance. A client-style store is bound in three steps, the Redis repository (`hex-store-repository`)
being the worked one: a settings factory, a client factory that closes the client after its yield, and
the repository bound to its port.

Add `FastapiProvider()` to that list **only** when a factory takes `fastapi.Request` or
`fastapi.WebSocket` as a parameter; the default composition root above takes neither and stays free of
transport imports.

`ExportSettings` has no adapter behind it — its one consumer is the tunable's factory above, which reads
its single field (`hex-domain-model`) — so it sits in a package named for itself
(`infrastructure/export/settings.py`, `hex-conventions`) and is shown here, beside that consumer:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["ExportSettings"]

class ExportSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MYAPP_EXPORT_",
        env_file=".env",
        extra="ignore",
    )

    max_rows: int
```

## The unit-of-work factory

A handler that uses a unit of work receives `Callable[[], IUnitOfWork]` and opens a fresh one per
`execute` (`hex-patterns`). **Bind the callable, not the unit of work.** Per-operation lifetime would
hand the handler one shared instance for the whole request, which is a different contract.

```python
from collections.abc import Callable
from functools import partial

from myapp.domain.uow import IUnitOfWork
from myapp.infrastructure.postgres import SqlAlchemyUnitOfWork


class FoosProvider(Provider):
    @provide(scope=Scope.APP)
    def uow_factory(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> Callable[[], IUnitOfWork]:
        return partial(SqlAlchemyUnitOfWork, session_factory=session_factory)
```

The closure is stateless, so it is process-lifetime. The unit of work it builds is owned by the
handler's `async with`, which commits or rolls it back — not by the composition root, which never sees
it. There is for the same reason **no per-request session binding**: a session's lifetime belongs either
to the repository call that opened it or to the unit of work, never to the composition root
(`hex-persistence`).
