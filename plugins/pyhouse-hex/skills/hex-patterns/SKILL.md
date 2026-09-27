---
name: hex-patterns
description: Use when a handler needs compensation — undo or roll back an externally visible side effect when a later step fails — or a unit of work making writes atomic across two or more repositories. Provides the try/undo/re-raise body and `IUnitOfWork`. The default handler shape, with no `try/except`, is `hex-application`'s; this is the earned exception.
paths: ["**/application/**", "**/infrastructure/**"]
---

# Hexagonal Patterns — compensation and unit of work

Two patterns that span layers rather than owning one layer's artifact, which is why neither belongs to a
single artifact skill.

- **Compensating transaction** — produces no new file. It shapes a command handler's `execute` body when
  the handler has already done something the outside world can see before a later step can still fail.
- **Unit of work** — produces three artifacts: a domain protocol, an infrastructure implementation, and
  the handler form that consumes it.

The two compose in one direction only: **compensation wraps the unit of work.** try → `async with uow` →
commit → except → undo → raise.

## When to use vs. neighbours

Compensating transaction:

- The handler creates an external side effect — blob upload, third-party POST, file write — **before** a
  database write that can still fail, and the side effect must be undone on failure → **compensation**.
- The side effect is harmless if left behind (a cache warm-up), is the *last* step with nothing after it
  to fail, or can simply be reordered after the database write → neither pattern; drop the `try/except`.

Unit of work:

- The handler writes to **two or more repositories in one transaction** — two aggregates changed
  together, an aggregate plus an outbox row → **unit of work**.
- Only one repository participates → neither pattern; the standalone repository form in
  `hex-persistence`, which owns its own transaction, is simpler.
- The only motivation is keeping objects readable after the commit → neither; that is the store's
  post-commit refresh policy, not a transaction boundary (`expire_on_commit=False` under the binding
  below).
- The atomic group spans two backends (a relational store plus object storage, or plus a cache) →
  **compensation**, not a unit of work; and if it spans two *unrelated* backends both ways it is a saga
  and out of scope here.

Elsewhere:

- A CLI, worker or schedule invoking a hexagonal use case → no pattern of its own: it resolves the handler
  from the container (`hex-wiring`) and awaits `execute`, exactly as a route does.
- The command or query and its handler, and its default shape with no `try/except` at all → `hex-application`.
- A flat service's run function and trigger wrappers → `flat-entrypoint`, in the `pyhouse-flat` plugin.
- Layer boundaries and the injection site → `hex-architecture`.
- The repository that joins a unit of work → `hex-persistence`.
- The reversing method a compensation calls (`delete`, `retract`) → declared on a port beside its forward operation by `hex-domain-ports`, implemented in `hex-capability-adapter` or `hex-store-repository`; the guard that lets the handler stop its failure is stated here, as `exception-catalog`'s best-effort compensation exception.
- The lifetime and declaration-order rules the unit-of-work binding follows, and the base composition root it merges into → `hex-wiring`; the binding itself is shown here.
- What the handler may log → `hex-architecture`; the event's shape → `python-logging`.

## Template — compensation, a single side effect

The command is `hex-application`'s `CreateFooCommand` with the uploaded bytes added — one class, whose
file this replaces, never a second `CreateFooCommand` beside it:

```python
from dataclasses import dataclass

__all__ = ["CreateFooCommand"]


@dataclass(frozen=True)
class CreateFooCommand:
    name: str
    data: bytes
    note: str | None = None
```

```python
import uuid

import structlog

from myapp.domain.foos import Foo, ICanStoreFoos, IFooRepository

from .create_foo_command import CreateFooCommand

__all__ = ["CreateFooHandler"]

logger = structlog.get_logger()


class CreateFooHandler:
    def __init__(self, repo: IFooRepository, storage: ICanStoreFoos) -> None:
        self._repo = repo
        self._storage = storage

    async def execute(self, cmd: CreateFooCommand) -> uuid.UUID:
        foo = Foo(id=uuid.uuid4(), name=cmd.name, note=cmd.note)
        storage_key = f"foos/{foo.id}"

        await self._storage.upload(storage_key, cmd.data)
        try:
            await self._repo.create(foo)
        except Exception:
            try:
                await self._storage.delete(storage_key)
            except Exception as undo_exc:
                logger.warning("foo_upload_undo_failed", storage_key=storage_key, exc_info=undo_exc)
            raise

        logger.info("foo_created", foo_id=str(foo.id))
        return foo.id
```

The entity is built — and its invariants checked — before the upload, so a malformed command fails
with nothing to undo (compensation rule 7). The storage key is derived from the entity's id, so the
entity carries no field for it and the key can be rebuilt wherever it is needed.

Where several side effects land before the fallible step, the handler records each one as it lands and,
on failure, undoes every recorded one, each behind its own guard — so a failure part-way still cleans
what already landed.

**Cleanup on the successful path is not compensation.** When a write replaces a resource, disposing of
the old one after the commit runs only on success and no failure is propagating, so the best-effort
guard does not apply: its failure propagates like any other step's.

## Template — unit of work, the protocol

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
subdomain package (`hex-architecture` rule 5), never at the domain root.

Repository members are typed by their **domain protocols**, never by concrete adapters, and are
**read-only properties**: a settable protocol attribute is invariant, so an implementation exposing a
concrete `FooSessionRepository` would not satisfy `foos: IFooRepository`; a read-only one is covariant and does.

## Template — unit of work, the implementation (SQLAlchemy async session)

In `src/myapp/infrastructure/postgres/sqlalchemy_unit_of_work.py`:

```python
from types import TracebackType
from typing import Self

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

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
        await self._session.commit()
```

Three details are load-bearing under a strict type checker, and all three are ordinary correctness too:

- The repository members are **read-only properties** returning the concrete adapters, which is what
  satisfies the protocol's read-only members.
- `__aexit__` has the protocol's **exact three-parameter signature**; a looser one on either side fails
  the structural check where the factory is bound.
- The session is closed in a `finally`, so a failing `rollback()` cannot leak the connection.

The factory builds a fresh instance per `execute`, so the session and the repositories sharing it are
created in the constructor and nothing is optional. Creating a session opens no connection: it begins
its transaction lazily on first use, so there is no explicit `begin()` — calling one on a session that
already has an implicit transaction raises.

The implementation does **not** inherit from `IUnitOfWork` — satisfaction is structural
(`hex-architecture`). Each member is a repository in `hex-persistence`'s joining form (`REPOSITORY.md`,
the unit-of-work-managed form): it takes the live session, never a factory, and never commits — commit
and rollback belong to the unit of work.

The binding, an add-on merged into the subdomain's provider in `hex-wiring`'s base composition root,
is the factory callable (unit-of-work rule 8) — process-lifetime, because the closure is stateless.

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

## Template — unit of work, handler integration

The handler receives `uow_factory: Callable[[], IUnitOfWork]` and opens a fresh unit of work per
`execute`:

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

This is the one handler form that opens a transaction itself — the earned exception to
`hex-application`'s no-transaction-code rule, and the only one.

## Template — both patterns together

Compensation outside, unit of work inside:

```python
await self._storage.upload(storage_key, cmd.data)
try:
    async with self._uow_factory() as uow:
        ...
        await uow.commit()
except Exception:
    try:
        await self._storage.delete(storage_key)
    except Exception as undo_exc:
        logger.warning("foo_upload_undo_failed", storage_key=storage_key, exc_info=undo_exc)
    raise
```

## Naming (unit of work)

- One `IUnitOfWork` per transactional **scope**, not per aggregate. The default name is `IUnitOfWork` in
  `domain/uow/i_unit_of_work.py`.
- Several units of work are justified only for genuinely different scopes, and each is named for the
  scope, never for the backend that implements it: two stores that each hold their own transactions →
  named for the store's role (`ICacheUnitOfWork` beside `IUnitOfWork`, never `IRedisUnitOfWork`), because
  a port is domain vocabulary and a vendor name in `domain/` is an infrastructure fact leaking inward;
  a read/write split, which is rare → `IReadUnitOfWork`, `IWriteUnitOfWork`. All of them in
  `domain/uow/i_<scope>_unit_of_work.py`.
- **Never name one after an aggregate.** `IFooUnitOfWork` conflates "what is inside the transaction" with
  "what kind of transaction it is".

## Other bindings

- **A different transactional handle.** The implementation wraps whatever the store gives you to hold one
  transaction open — a raw connection plus its transaction object, a document store's session, a client
  exposing `begin`/`commit`. Unchanged: the domain protocol, the per-`execute` lifetime, the
  factory-not-instance injection, and the rule that a joining repository never commits. Changed: where
  rollback is issued, and whether the handle needs an explicit `begin` — the primary binding starts its
  transaction lazily, so calling one there raises.
- **A store with no multi-statement transaction.** Then there is no unit of work to write at all: the
  atomic group becomes compensation, under the same composition rule — compensation wraps the
  transaction, never the reverse.
- **A different structured logger.** Only the log call in the handler templates changes; what a handler
  may log is `hex-architecture`'s rule, not this skill's.

## Rules

### Compensating transaction

1. **This `try/except Exception`, with the guard around its undo call (rule 3), is the only
   `try/except` allowed in a handler**, alongside the failure-state transition. Needing another means
   the design is wrong — push the catch into infrastructure or remove it.
2. **Catch `Exception`, not specific exceptions.** Compensation must run regardless of the cause.
3. **The undo is guarded** — the port's plain reversing method (`delete`, `retract`), wrapped in its own
   `try` inside the `except`, is `exception-catalog`'s best-effort compensation; the one warning event it
   logs takes `python-logging`'s shape.
4. **The original failure is re-raised unchanged** with a bare `raise` — `exception-catalog`'s
   best-effort compensation.
5. **The original failure is not logged here** — a re-raising scope stays silent (`python-logging`).
6. **The side effect runs *outside* the `try`.** Only the fallible *next* step goes inside.
7. **Pre-side-effect validation runs *before* the side effect.** Fail fast without compensation whenever
   possible.

### Unit of work

1. **One per scope, not per aggregate.** Every repository that may ever join a transaction is an
   attribute on the same protocol.
2. **`commit()` is the last statement** inside the `async with`. Anything after it must be idempotent —
   logging, returning the new id.
3. **Exiting without `commit()` rolls back.** Treat success as opt-in: an early return or a raised
   exception inside the block leaves the transaction unfinished, and the exit path discards it rather
   than guessing what the handler meant.
4. **Do not catch exceptions inside the block** unless implementing compensation. Let them propagate so
   `__aexit__` rolls back.
5. **One unit of work per `execute`.** Never shared across calls, never pooled — a shared one merges
   two callers' writes into one transaction, so one caller's failure rolls the other's work back.
6. **A joining repository is handed the open transactional handle, never a factory.** A repository
   that opens its own connection is in a different transaction from the one it was meant to join, and
   the defect shows up as a partial write rather than an error. One class cannot serve both the
   standalone and the joining form; split into two adapters if both are genuinely needed.
7. **Do not retry a failing unit of work in the handler.** The transaction is already unusable once a
   statement in it has failed, so a retry inside the block runs against a dead handle. Let the failure
   propagate to the central error handler, which is where a retry policy belongs.
8. **The composition root binds the zero-argument callable itself**, matching
   `Callable[[], IUnitOfWork]` — never a unit-of-work instance, however short its lifetime is set to.
   An instance handed to the handler is shared across every `execute` on it, which breaks rule 5. The
   unit of work's lifetime is this `async with`, owned by the handler, not by the composition root
   (`hex-wiring`).

## Hard stops

- The capability protocol has no cleanup method to call in the undo → stop, add it to the protocol first.
- The undo is called unguarded inside `except`, or its failure is swallowed with no event logged → stop,
  route it through the handler's guard (compensation rule 3).
- The undo's failure is being stopped inside a dedicated `*_best_effort` method → stop, the undo
  raises like any other call; only the handler's `except` that caught the original may stop it, and
  it logs the one warning (`exception-catalog`).
- Compensation would span two unrelated backends in both directions → stop, that is a saga, not a
  compensating transaction, and it is out of scope here.
- Only one repository participates in the "atomic group" → stop, this is not a unit-of-work case; keep
  the handler on the standalone repository form in `hex-persistence`, which owns its own transaction.
- The atomic group spans two backends → stop, that is compensation, not a unit of work.
- A unit of work is being named per aggregate (`IFooUnitOfWork`) → stop, wrong shape; one shared unit of
  work for the scope.
- The protocol declares a repository member as a settable attribute → stop, make it a read-only
  property; a settable protocol member is invariant, so no implementation exposing a concrete
  repository satisfies it.
- The implementation's `__aexit__` signature differs from the protocol's → stop, match the three
  parameters exactly; a near-match fails where the factory is bound.
