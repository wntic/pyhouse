# hex-wiring — the composition root

Topic file of `hex-wiring`. The mechanism-free obligations are `## Rules` in `SKILL.md`; what follows
is the **dishka** binding that satisfies them.

This is the **base** every project extends: the settings, the relational store (engine, session
factory, the `Foo` repository), the tunable value object and the handlers. It binds no optional
adapter. Each of those — a blob store, an HTTP gateway, a canonicalizer, a key-value store, a token
verifier — ships its own binding beside the adapter, in the skill that owns it: the S3 storage, the
HTTP gateway and the idna canonicalizer in `hex-capability-adapter`, the Redis repository in
`hex-store-repository`, the token verifier in `hex-restapi-auth`. A project merges the ones it has into
the providers below, each line into the provider class of the same name, in declaration order; a
provider class a binding adds (a second subdomain's) joins the `create_container` list.

```python
from collections.abc import AsyncIterator

from dishka import AsyncContainer, Provider, Scope, make_async_container, provide
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from myapp.application.foos import (
    CreateFooHandler,
    DeleteFooHandler,
    GetFooHandler,
    ListFoosHandler,
    UpdateFooHandler,
)
from myapp.domain.foos import FooExportTunable, FooUniquenessService, IFooRepository
from myapp.infrastructure.export import ExportSettings
from myapp.infrastructure.postgres import DbSettings, create_engine, create_session_factory
from myapp.infrastructure.postgres.repositories import FooRepository

__all__ = ["create_container"]


class SettingsProvider(Provider):
    """1. Settings — process lifetime; everything else may depend on them."""

    scope = Scope.APP

    @provide
    def db_settings(self) -> DbSettings:
        return DbSettings()

    @provide
    def export_settings(self) -> ExportSettings:
        return ExportSettings()


class InfrastructureProvider(Provider):
    """2. Long-lived handles, each released after its yield, and 3. cross-cutting adapters,
    which the binding beside each adapter adds here."""

    scope = Scope.APP

    @provide
    async def engine(self, settings: DbSettings) -> AsyncIterator[AsyncEngine]:
        engine = create_engine(settings=settings)
        yield engine
        await engine.dispose()

    @provide
    def session_factory(self, engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
        return create_session_factory(engine=engine)


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
        FoosProvider(),
        *overrides,
    )
```

Every add-on binding has the same parts, each in the place the declaration order gives it: a settings
factory in `SettingsProvider`; in `InfrastructureProvider`, the client it needs — built by a factory that
releases it after its yield when it holds connections — and a capability adapter bound to its port; and
a repository bound to its port in its subdomain's per-operation provider. One adapter satisfying two
ports is bound once, to both (`AnyOf`), so the two ports share the one instance — the S3 binding is the
worked case. An aggregate has one authoritative store (`hex-store-repository` rule 1), so no add-on binds
a second repository for `Foo`; the key-value one binds `Baz`'s.

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
    def uow_factory(self, session_factory: async_sessionmaker[AsyncSession]) -> Callable[[], IUnitOfWork]:
        return partial(SqlAlchemyUnitOfWork, session_factory=session_factory)
```

The closure is stateless, so it is process-lifetime. The unit of work it builds is owned by the
handler's `async with`, which commits or rolls it back — not by the composition root, which never sees
it. There is for the same reason **no per-request session binding**: a session's lifetime belongs either
to the repository call that opened it or to the unit of work, never to the composition root
(`hex-persistence`).
