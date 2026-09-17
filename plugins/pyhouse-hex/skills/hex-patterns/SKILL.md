---
name: hex-patterns
description: Use when a handler needs compensation — undo or roll back an externally visible side effect when a later step fails — or a unit of work making writes atomic across two or more repositories, plus a framework-free run function. Provides the try/undo/re-raise body and `IUnitOfWork`. The default handler shape, with no `try/except`, is `hex-application`'s; this is the earned exception.
paths: ["**/application/**", "**/infrastructure/**"]
---

# Hexagonal Patterns — compensation, unit of work and run function

Three patterns that span layers rather than owning one layer's artifact, which is why none belongs to a
single artifact skill.

- **Compensating transaction** — produces no new file. It shapes a command handler's `execute` body when
  the handler has already done something the outside world can see before a later step can still fail.
- **Unit of work** — produces three artifacts: a domain protocol, an infrastructure implementation, and
  the handler form that consumes it.
- **Run function** — gives a CLI, worker or scheduled entrypoint a plain async call into an existing
  application handler.

The transaction patterns compose in one direction only: **compensation wraps the unit of work.** try → `async with uow` →
commit → except → undo → raise.

## When to use vs. neighbours

Compensating transaction:

- The handler creates an external side effect — blob upload, third-party POST, file write — **before** a
  database write that can still fail, and the side effect must be undone on failure → **compensation**.
- The side effect is harmless if left behind (a cache warm-up), is the *last* step with nothing after it
  to fail, or can simply be reordered after the database write → neither pattern; drop the `try/except`.

Unit of work:

- The handler writes to **two or more repositories in one transaction** — a write plus an audit append,
  an aggregate plus an outbox row → **unit of work**.
- Only one repository participates → neither pattern; the standalone repository form in
  `hex-persistence`, which owns its own transaction, is simpler.
- The only motivation is keeping objects readable after the commit → neither; that is the store's
  post-commit refresh policy, not a transaction boundary (`expire_on_commit=False` under the binding
  below).
- The atomic group spans two backends (a relational store plus object storage, or plus a cache) →
  **compensation**, not a unit of work; and if it spans two *unrelated* backends both ways it is a saga
  and out of scope here.

Elsewhere:

- A CLI, worker or schedule needs to invoke a hexagonal use case → the run-function template below.
- The command or query and its handler, and its default shape with no `try/except` at all → `hex-application`.
- A flat service's run function and trigger wrappers → `flat-entrypoint`, in the `pyhouse-flat` plugin.
- Layer boundaries and the injection site → `hex-architecture`.
- The repository that joins a unit of work → `hex-persistence`.
- The `*_best_effort` cleanup method a compensation calls → its contract is stated here, declared on a port by `hex-domain-ports`, implemented in `hex-capability-adapter` or `hex-store-repository`.
- The composition-root declarations both patterns need — the `IUnitOfWork` binding and its scope → `hex-wiring`.
- What the handler may log → `python-style`.

## Template — compensation, a single side effect

```python
async def execute(self, cmd: UpsertFooCommand) -> uuid.UUID:
    # validation that doesn't depend on the side effect goes BEFORE the upload
    ...

    storage_key = await self._storage.put(cmd.data, ...)

    try:
        await self._repo.create(Foo(..., storage_key=storage_key))
    except Exception:
        await self._storage.delete_many_best_effort([storage_key])
        raise

    # caller_id is logged only when the command carries it (the authenticated form);
    # an auth-less command has no caller_id field — drop it.
    logger.info("foo_created", foo_id=str(foo.id), caller_id=str(cmd.caller_id))
    return foo.id
```

## Template — compensation, multi-step side effects

Accumulate the work-to-undo in a list so partial progress is cleaned too:

```python
uploaded_keys: list[str] = []
try:
    items = await self._upload_items(uploads, foo_id, uploaded_keys)
    foo = _build_foo(cmd, items)
    await self._repo.create(foo)
except Exception:
    await self._storage.delete_many_best_effort(uploaded_keys)
    raise
```

The helper appends to `uploaded_keys` after each successful upload, so a failure mid-loop still rolls
back what already landed.

### Successful-path cleanup is **not** compensation

When an upsert *replaces* a previous resource, the old one is cleaned **after** the database commit:

```python
previous_key = await self._repo.upsert_foo(...)
# ... the try/except wraps only the upsert above ...

if previous_key is not None:
    await self._storage.delete_many_best_effort([previous_key])
```

That trailing call is ordinary cleanup: it runs only on success and disposes of the *old* resource. Do
not conflate the two.

## Template — unit of work, the protocol

```python
# src/myapp/domain/i_unit_of_work.py
from typing import Protocol

from .audit import IAuditRepository
from .foos import IFooRepository

__all__ = ["IUnitOfWork"]


class IUnitOfWork(Protocol):
    foos: IFooRepository
    audit: IAuditRepository

    async def __aenter__(self) -> "IUnitOfWork": ...
    async def __aexit__(self, *args: object) -> None: ...
    async def commit(self) -> None: ...
```

Repository attributes are typed by their **domain protocols**, never by concrete adapters.

## Template — unit of work, the implementation (SQLAlchemy async session)

```python
# src/myapp/infrastructure/postgres/sqlalchemy_unit_of_work.py
from types import TracebackType

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from myapp.infrastructure.postgres.repositories import AuditRepository, FooRepository

__all__ = ["SqlAlchemyUnitOfWork"]


class SqlAlchemyUnitOfWork:
    foos: FooRepository
    audit: AuditRepository

    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory
        self._session: AsyncSession | None = None

    async def __aenter__(self) -> "SqlAlchemyUnitOfWork":
        session = self._sf()
        await session.__aenter__()
        self._session = session
        self.foos = FooRepository(session)
        self.audit = AuditRepository(session)
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        session = self._session
        if session is None:
            return
        try:
            if exc_type is not None:
                await session.rollback()
        finally:
            await session.__aexit__(exc_type, exc, tb)
            self._session = None

    async def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("commit() called outside an active unit of work")
        await self._session.commit()
```

Three details are load-bearing under a strict type checker, and all three are ordinary correctness too:

- `_session` is `AsyncSession | None`, so **every** use narrows it through a local first — dereferencing
  the attribute directly fails the checker and would crash if the object were reused after exit.
- `foos` and `audit` are **declared as class-level annotations**. Assigning them only inside `__aenter__`
  leaves the checker with no attribute to find at the injection site.
- The session is closed in a `finally`, so a failing `rollback()` cannot leak the connection.

The session begins its transaction lazily on first use, so there is no explicit `begin()` — calling one
on a session that already has an implicit transaction raises.

The implementation does **not** inherit from `IUnitOfWork` — satisfaction is structural
(`hex-architecture`).

## Template — unit of work, handler integration

The handler receives `uow_factory: Callable[[], IUnitOfWork]` and opens a fresh unit of work per
`execute`:

```python
from collections.abc import Callable

import structlog

from myapp.domain import IUnitOfWork

__all__ = ["CreateFooHandler"]

logger = structlog.get_logger()


class CreateFooHandler:
    def __init__(self, uow_factory: Callable[[], IUnitOfWork]) -> None:
        self._uow_factory = uow_factory

    async def execute(self, cmd: CreateFooCommand) -> uuid.UUID:
        async with self._uow_factory() as uow:
            await uow.foos.create(foo)
            await uow.audit.append(AuditEvent(...))
            await uow.commit()
        logger.info("foo_created", foo_id=str(foo.id), caller_id=str(cmd.caller_id))
        return foo.id
```

## Template — both patterns together

Compensation outside, unit of work inside:

```python
storage_key = await self._storage.put(...)
try:
    async with self._uow_factory() as uow:
        ...
        await uow.commit()
except Exception:
    await self._storage.delete_many_best_effort([storage_key])
    raise
```

## Template — session-injected repository, SQLAlchemy (required when joining a unit of work)

A repository joining the unit of work takes a live `session: AsyncSession`, not a factory. One class
cannot be both unit-of-work-managed and standalone — pick one form.

```python
class FooRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, foo: Foo) -> None:
        try:
            await self._session.execute(...)
        except IntegrityError as exc:
            raise _map_integrity_error(exc) from exc
```

Methods use `self._session.execute(...)` directly, and **never `commit()` or `rollback()`** — the unit of
work owns those. Committing inside a repository breaks atomicity.

## Template — run function

The entrypoint resolves the handler through `hex-wiring` and builds the command using
`hex-application`. Its run function passes that command to the handler; the handler retains the use
case, including any compensation or unit of work above.

```python
# src/myapp/worker/run_foo.py
from uuid import UUID

from myapp.application.foos import CreateFooCommand, CreateFooHandler

__all__ = ["run_once"]


async def run_once(handler: CreateFooHandler, command: CreateFooCommand) -> UUID:
    return await handler.execute(command)
```

The function has no scheduler or framework dependency. A CLI or worker supplies the resolved handler
and command, awaits `run_once`, and translates its result at the entrypoint boundary. A query uses the
corresponding query handler and result type from `hex-application`.

## Naming (unit of work)

- One `IUnitOfWork` per transactional **scope**, not per aggregate. The default name is `IUnitOfWork` in
  `i_unit_of_work.py`.
- Several units of work are justified only for genuinely different scopes: different backends →
  `IPostgresUnitOfWork`, `IRedisUnitOfWork` in `i_<backend>_unit_of_work.py`; a read/write split, which is
  rare → `IReadUnitOfWork`, `IWriteUnitOfWork` in `i_<scope>_unit_of_work.py`.
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
  may log is `python-style`'s rule, not this skill's.

## Rules

### Compensating transaction

1. **This `try/except Exception` is the only `try/except` allowed in a handler**, alongside the
   failure-state transition. Needing another means the design is wrong — push the catch into
   infrastructure or remove it.
2. **Catch `Exception`, not specific exceptions.** Compensation must run regardless of the cause.
3. **The undo must never let its own failure mask the original error.** It is best-effort, in one of two
   sanctioned shapes — the choice is the author's, do not assume one:
   - a dedicated **`*_best_effort` method** on the protocol (`delete_many_best_effort`) that swallows its
     internal errors, called directly as the templates show; **or**
   - the **plain protocol method** (`delete` / `revert`) wrapped in a nested swallow at the call site when
     no `*_best_effort` variant exists:
     ```python
     except Exception:
         try:
             await self._storage.delete(storage_key)
         except Exception:
             pass  # best-effort — the undo's own failure must not mask the original error
         raise
     ```
   Never call a raising `delete` / `revert` *unguarded* inside `except` — if it raises, the original error
   is lost. When the undo is called often enough to deserve a first-class name, model a `*_best_effort`
   method; until then the call-site swallow is correct and needs no new protocol method.
4. **Bare `raise` at the end of `except`.** Never `raise NewException(...)`, never `raise ... from exc`.
   The original exception propagates unchanged.
5. **No logging inside `except`.** The central error handler logs once.
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

### Run function

1. Pass the resolved handler and input as arguments; the run function does not construct adapters or
   reach into the composition root. Composition remains in `hex-wiring`.
2. Keep the use case in the command or query handler from `hex-application`; trigger-specific setup
   belongs to the calling entrypoint under `hex-architecture`.
3. Let the handler's result and exceptions propagate to the calling entrypoint; use `exception-catalog`
   for boundary translation and `python-style` for logging.

## Hard stops

- A run function constructs a concrete adapter or reaches into the composition root → stop, use `hex-wiring`.
- A run function starts implementing the use case → stop, use `hex-application` for the handler.
- A flat service needs its run-function template → stop, use `flat-entrypoint` (`pyhouse-flat`).

- The capability protocol has no cleanup method to call in the undo → stop, add it to the protocol first.
- The undo method can itself raise non-trivially — it calls a flaky third-party DELETE, say → stop, the
  protocol contract is wrong; the method must swallow its own errors internally.
- Compensation would span two unrelated backends in both directions → stop, that is a saga, not a
  compensating transaction, and it is out of scope here.
- Only one repository participates in the "atomic group" → stop, this is not a unit-of-work case; keep
  the handler on the standalone repository form in `hex-persistence`, which owns its own transaction.
- The atomic group spans two backends → stop, that is compensation, not a unit of work.
- A unit of work is being named per aggregate (`IFooUnitOfWork`) → stop, wrong shape; one shared unit of
  work for the scope.
- The implementation dereferences its transactional-handle attribute without narrowing → stop, it is
  optional outside `__aenter__`/`__aexit__`; bind a local first, or a reuse after exit crashes at the
  call site.
- The implementation assigns its repository attributes only inside `__aenter__` with no class-level
  declaration → stop, nothing reading the class can see the attributes, so the injection site has no
  contract to check against.
