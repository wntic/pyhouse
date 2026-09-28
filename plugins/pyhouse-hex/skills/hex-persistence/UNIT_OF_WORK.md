# hex-persistence — the unit of work

Topic file of `hex-persistence`, read only when one command writes **two or more repositories that must
commit together** — two aggregates changed at once, an aggregate plus an outbox row. The
mechanism-free obligations are rules 2 and 5–7 in `SKILL.md`, and `persistence` rules 1 and 4; what follows is
the **SQLAlchemy async session + dishka** binding that satisfies them: the domain protocol, its
implementation, its binding, and the handler form that opens it.

Not a unit of work: one repository per command (the standalone form in `REPOSITORY.md` owns its own
transaction); keeping rows readable after the commit (the session factory's post-commit refresh policy
in `REPOSITORY.md`); a group spanning two backends, such as a table plus object storage (compensation,
in `hex-application`).

## Template — the protocol

In `src/myapp/domain/uow/i_unit_of_work.py`:

```python
from types import TracebackType
from typing import Protocol, Self

from ..bars import IBarRepository
from ..foos import IFooRepository

__all__ = ["IUnitOfWork"]


class IUnitOfWork(Protocol):
    @property
    def foos(self) -> IFooRepository: ...
    @property
    def bars(self) -> IBarRepository: ...

    async def __aenter__(self) -> Self: ...
    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None: ...
    async def commit(self) -> None: ...
```

The unit of work spans subdomains, so it gets a cross-cutting subdomain package of its own,
`domain/uow/`, the way `hex-domain-ports` places auth in `domain/auth/` — a port still sits in a
subdomain package (`hex-architecture` rule 5), never at the domain root. A second unit of work, only for
a genuinely different scope, is named for that scope's role, never for its backend or an aggregate
(`ICacheUnitOfWork`, never `IRedisUnitOfWork` or `IFooUnitOfWork`), in `domain/uow/i_<scope>_unit_of_work.py`.

## Template — the implementation (SQLAlchemy async session)

In `src/myapp/infrastructure/postgres/sqlalchemy_unit_of_work.py`:

```python
from types import TracebackType
from typing import Self

from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from myapp.domain.exceptions import UpstreamError

from .repositories import BarSessionRepository, FooSessionRepository

__all__ = ["SqlAlchemyUnitOfWork"]


class SqlAlchemyUnitOfWork:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session = session_factory()
        self._foos = FooSessionRepository(self._session)
        self._bars = BarSessionRepository(self._session)

    @property
    def foos(self) -> FooSessionRepository:
        return self._foos

    @property
    def bars(self) -> BarSessionRepository:
        return self._bars

    async def __aenter__(self) -> Self:
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        try:
            if exc_type is not None:
                await self._session.rollback()
        finally:
            await self._session.close()

    async def commit(self) -> None:
        try:
            await self._session.commit()
        except (DBAPIError, OSError) as exc:
            raise UpstreamError("the datastore could not commit the unit of work", {}) from exc
```

Each member is `REPOSITORY.md`'s unit-of-work-managed form, and the class does not inherit from
`IUnitOfWork` (`hex-architecture`). Three details are load-bearing under a strict type checker, and
ordinary correctness too:

- Repository members are **read-only properties** on both sides. A settable protocol member is
  invariant, so a concrete `FooSessionRepository` would not satisfy `foos: IFooRepository`; a read-only
  one is covariant and does.
- `__aexit__` has the protocol's **exact three-parameter signature**; a near-match fails the structural
  check where the factory is bound.
- The session is closed in a `finally`, so a failing `rollback()` cannot leak the connection.

`commit()` is a public method like any repository's, and the commit is where a deferred failure or a
dropped connection surfaces, so it translates the driver's error too (`persistence` rule 4).

The session and its repositories are built in the constructor, since the factory makes a fresh instance
per `execute`. Creating a session opens no connection and begins its transaction lazily, so there is no
explicit `begin()` — calling one on a session already in an implicit transaction raises.

The binding merges into the subdomain's provider in `hex-wiring`'s base composition root, and is the
factory callable (`hex-wiring`) — process-lifetime, because the closure is stateless:

```python
from collections.abc import Callable
from functools import partial

from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from myapp.domain.uow import IUnitOfWork
from myapp.infrastructure.postgres import SqlAlchemyUnitOfWork


class FoosProvider(Provider):
    @provide(scope=Scope.APP)
    def uow_factory(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> Callable[[], IUnitOfWork]:
        return partial(SqlAlchemyUnitOfWork, session_factory=session_factory)
```

## Template — the handler that opens it

`hex-application`'s `CreateFooHandler`, with the factory in place of the repository — the one handler
form that opens a transaction itself, the earned exception to `hex-application` command handler rule 7:

```python
import uuid
from collections.abc import Callable

import structlog

from myapp.domain.bars import Bar
from myapp.domain.foos import Foo
from myapp.domain.uow import IUnitOfWork

from .create_foo_command import CreateFooCommand

__all__ = ["CreateFooHandler"]

logger = structlog.get_logger()


class CreateFooHandler:
    def __init__(self, uow_factory: Callable[[], IUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    async def execute(self, cmd: CreateFooCommand) -> uuid.UUID:
        foo = Foo(id=uuid.uuid4(), name=cmd.name, note=cmd.note)
        bar = Bar(id=uuid.uuid4(), name=cmd.name)
        async with self._uow_factory() as uow:
            await uow.foos.create(foo)
            await uow.bars.create(bar)
            await uow.commit()
        logger.info("foo_created", foo_id=str(foo.id))
        return foo.id
```

Where the handler also compensates an external write, the compensation's `try` wraps this `async with`
(`hex-application`).

## Other bindings

- **A different transactional handle** — a raw connection plus its transaction object, a document
  store's session, a client exposing `begin`/`commit`. Unchanged: the protocol, the per-`execute`
  lifetime, the factory binding, and a joining repository that never commits. Changed: where rollback
  is issued, and whether the handle needs an explicit `begin`.
- **A store with no multi-statement transaction.** There is no unit of work to write: the atomic group
  becomes compensation (`hex-application`).
