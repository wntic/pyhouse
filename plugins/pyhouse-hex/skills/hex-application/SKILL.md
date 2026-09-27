---
name: hex-application
description: Use when writing a use case — a CQRS command handler, a query handler, or its frozen input DTO. Owns the command/query split and the read-model versus write-model rule deciding whether a query returns the entity or a row-projected read-model. Not the entity (`hex-domain-model`) nor the wire model (`hex-restapi-schema`); undo-on-failure or a two-repository commit is `hex-patterns`.
paths: ["**/application/**"]
---

# Hex — Application

The use-case layer, split by CQRS: **commands** mutate and return an id, **queries** read and return
data. Both are thin — a frozen DTO plus a handler class whose only public method is `execute`.

## When to use vs. neighbours

Command or query, an undo-on-failure body or a unit of work → Command or query, at the head of Rules;
whether a query returns the entity or a read-model → Read models, beside it. Outside it:

- The entity, value object or filter record the DTOs mention → `hex-domain-model`.
- The `IFooRepository` a handler depends on → `hex-domain-ports`.
- A rule needing another aggregate's state, which the handler calls rather than inlines → `hex-domain-service`.
- Turning the return value into JSON → `hex-restapi-schema`. A handler never returns a Pydantic model.
- The route that calls this handler and resolves it from the container → `hex-restapi-endpoint`.
- Where the caller's identity comes from under the HTTP binding, and the route dependency that supplies it → `hex-restapi-auth`.
- Binding the handler in the composition root → `hex-wiring`.
- Unit-testing the handler against in-memory fakes → `hex-test-application-handler`.
- The path these files land on and the names they take → `hex-conventions` and `naming`.

## Template(s) — stdlib dataclasses, structlog logging

### File layout

```
src/myapp/application/foos/
├── create_foo_command.py   # CreateFooCommand
├── create_foo_handler.py   # CreateFooHandler
├── update_foo_command.py   # UpdateFooCommand
├── update_foo_handler.py   # UpdateFooHandler
├── delete_foo_command.py   # DeleteFooCommand
├── delete_foo_handler.py   # DeleteFooHandler
├── get_foo_query.py        # GetFooQuery
├── get_foo_handler.py      # GetFooHandler
├── list_foos_query.py      # ListFoosQuery
├── list_foos_handler.py    # ListFoosHandler
└── list_foos_result.py     # ListFoosResult  (only when the read returns more than one entity)
```

### Command DTO

The caller's identity and scope, where the caller is authenticated, are fields the entrypoint adds —
Caller-derived fields, under Rules. The templates show a service whose caller is not authenticated.

```python
from dataclasses import dataclass

__all__ = ["CreateFooCommand"]


@dataclass(frozen=True)
class CreateFooCommand:
    name: str
    note: str | None = None
```

### Command handler — create (returns `UUID`)

```python
import uuid

import structlog

from myapp.domain.foos import Foo, IFooRepository

from .create_foo_command import CreateFooCommand

__all__ = ["CreateFooHandler"]

logger = structlog.get_logger()


class CreateFooHandler:
    def __init__(self, repo: IFooRepository) -> None:
        self._repo = repo

    async def execute(self, cmd: CreateFooCommand) -> uuid.UUID:
        foo = Foo(id=uuid.uuid4(), name=cmd.name, note=cmd.note)
        await self._repo.create(foo)
        logger.info("foo_created", foo_id=str(foo.id))
        return foo.id
```

### Command DTO and handler — update (returns `None`)

A partial update: `None` on a field means "leave it unchanged", the same contract as the PATCH body
(`hex-restapi-schema`).

```python
from dataclasses import dataclass
from uuid import UUID

__all__ = ["UpdateFooCommand"]


@dataclass(frozen=True)
class UpdateFooCommand:
    id: UUID
    name: str | None = None
    note: str | None = None
```

```python
from dataclasses import replace

import structlog

from myapp.domain.foos import IFooRepository

from .update_foo_command import UpdateFooCommand

__all__ = ["UpdateFooHandler"]

logger = structlog.get_logger()


class UpdateFooHandler:
    def __init__(self, repo: IFooRepository) -> None:
        self._repo = repo

    async def execute(self, cmd: UpdateFooCommand) -> None:
        foo = await self._repo.get_by_id(cmd.id)
        changed = replace(
            foo,
            name=foo.name if cmd.name is None else cmd.name,
            note=foo.note if cmd.note is None else cmd.note,
        )
        await self._repo.update(changed)
        logger.info("foo_updated", foo_id=str(cmd.id))
```

`replace` builds a new entity through the constructor, so the entity's invariants run on the changed
values exactly as they did at creation.

### Command DTO and handler — delete (returns `None`)

```python
from dataclasses import dataclass
from uuid import UUID

__all__ = ["DeleteFooCommand"]


@dataclass(frozen=True)
class DeleteFooCommand:
    id: UUID
```

```python
import structlog

from myapp.domain.foos import IFooRepository

from .delete_foo_command import DeleteFooCommand

__all__ = ["DeleteFooHandler"]

logger = structlog.get_logger()


class DeleteFooHandler:
    def __init__(self, repo: IFooRepository) -> None:
        self._repo = repo

    async def execute(self, cmd: DeleteFooCommand) -> None:
        await self._repo.delete(cmd.id)
        logger.info("foo_deleted", foo_id=str(cmd.id))
```

### Query DTO

```python
from dataclasses import dataclass

from myapp.domain.foos import FooListFilter

__all__ = ["ListFoosQuery"]


@dataclass(frozen=True)
class ListFoosQuery:
    filter: FooListFilter
```

### Query handler — single entity

```python
# get_foo_query.py
from dataclasses import dataclass
from uuid import UUID

__all__ = ["GetFooQuery"]


@dataclass(frozen=True)
class GetFooQuery:
    id: UUID
```

```python
# get_foo_handler.py
from myapp.domain.foos import Foo, IFooRepository

from .get_foo_query import GetFooQuery

__all__ = ["GetFooHandler"]


class GetFooHandler:
    def __init__(self, repo: IFooRepository) -> None:
        self._repo = repo

    async def execute(self, query: GetFooQuery) -> Foo:
        return await self._repo.get_by_id(query.id)
```

For an entity-or-none read the annotation is `Foo | None` and the repository method is the one returning
`Foo | None`, such as `get_by_name`.

### Query handler — list, plus its Result DTO

```python
# list_foos_handler.py
from myapp.domain.foos import IFooRepository

from .list_foos_query import ListFoosQuery
from .list_foos_result import ListFoosResult

__all__ = ["ListFoosHandler"]


class ListFoosHandler:
    def __init__(self, repo: IFooRepository) -> None:
        self._repo = repo

    async def execute(self, query: ListFoosQuery) -> ListFoosResult:
        items = await self._repo.list(filter=query.filter)
        total = await self._repo.count(filter=query.filter)
        return ListFoosResult(items=items, total=total)
```

```python
# list_foos_result.py
from collections.abc import Sequence
from dataclasses import dataclass

from myapp.domain.foos import Foo

__all__ = ["ListFoosResult"]


@dataclass(frozen=True)
class ListFoosResult:
    items: Sequence[Foo]
    total: int
```

## Other bindings

- **Another logging facade** — the stdlib logger behind a structured adapter, or a third-party one. What
  changes is the two lines that obtain the logger and the call form that carries the fields. What does
  not is the allocation (a command handler emits exactly one success event *after* the write; a query
  handler emits none and imports no logger at all) or the event name as a stable contract
  (`python-logging`).
- **Another identity scheme** — a time-ordered UUID, a ULID, or a key the store mints. What changes is
  the single expression that mints the id. What does not is that the id exists before the write and that
  the command returns it; a store-minted key is the one case that moves the mint into the repository, and
  the handler then returns what the write handed back. Pick one scheme and apply it to every template at
  once (Command handler rule 8).

## Rules

Files land in `application/<subdomain>/`, where the subdomain is derived rather than chosen
(`hex-conventions` block A).

Artifact names follow `naming`; module boundaries follow `python-packaging`.

### Command or query

- A mutation — create, update, delete, rename, move → **command**.
- A read — get, list, count, search, detect → **query**.
- The mutation performs an external IO step before the DB write and must undo it on failure → still a
  command, but the handler body follows `hex-patterns` (the compensating-transaction form).
- Two or more repositories must commit atomically → still a command, with a unit-of-work factory
  injected that the handler opens itself; see `hex-patterns`.
- A handler never returns a transport model. The use case must be callable from a second entrypoint —
  a CLI, a consumer — which has no web framework in it.

### Read models — the read/write split that decides a query's return type

The domain entity is the **write** model: commands load and mutate it, and it carries the invariants.

A read that needs more than the entity exposes — **row timestamps** (`created_at` / `updated_at`,
which are deliberately *not* entity fields), denormalized or computed values, a join across
aggregates — returns a **read-model DTO** that the repository projects **directly from the
row**, bypassing the entity.

So "the screen shows a creation date" is satisfied by a read-model, **never** by pulling the timestamp
onto the aggregate — that would make the write model carry display-only state.

The read-model is a `@dataclass(frozen=True)` in `domain/<subdomain>/` (`FooSummary`, `FooListRow`),
carrying the displayed columns including the timestamps, and the repository protocol method returns
it. It stays a *domain* type so the repository can return it without importing `application` — a
repository may never return an application or Pydantic DTO. Do not reach for a heavyweight value object
per read, and do not bolt timestamps onto the entity to make a read easier.

### Caller-derived fields

1. **Where the caller is authenticated, the entrypoint sets `caller_id: str` — the issuer's opaque
   subject — as the first field of the command or query, from whatever authenticated the caller, never
   from caller input; a tenant or scope field likewise, and the handler scopes every repository call by
   it, so a row outside the caller's scope is not found — the not-found error, never a forbidden one.** An unauthenticated caller has
   neither field; how the HTTP binding supplies them is `hex-restapi-auth`.
2. **`caller_id` is logged on the success event; it is persisted, or used to scope reads, only where the
   aggregate records who owns or acted on it** — then it is an entity field and a column like any other.

### Command DTO

1. **`@dataclass(frozen=True)`.** Always frozen.
2. **No methods, no behaviour.** Just data.
3. **Optional fields:** follow `python-style`.

### Query DTO

1. **`@dataclass(frozen=True)`.** Always frozen.
2. **No methods.** Just data.
3. **Domain filter records are passed by reference, not flattened.** Carry `filter: FooListFilter`, not
   its fields copied loose onto the query.

### Result DTO (when present)

1. **`@dataclass(frozen=True)`, no methods.**
2. **Holds domain types only** — never a transport model, never a row object from the persistence
   library. Either one hands the entrypoint's or the store's vocabulary to every caller of the use case.
3. **Read-only collection typing:** follow `python-style`. Pagination metadata (`total`, `next_cursor`) lives here
   too.
4. **A read that must expose a row timestamp returns a read-model, not the entity** — see the read/write
   split above.

### Command handler

1. **One public method.**
   `async def execute(self, cmd: <CommandClass>) -> <ReturnType>`. Nothing else public — a second public
   method is a second use case, reachable in a half-finished state.
2. **Constructor takes only ports, domain services, a unit-of-work factory, or tunable value objects.** A
   concrete infrastructure handle in the signature — a database session, an HTTP client — means the
   handler cannot run in a test or under a second entrypoint without that infrastructure present. Follow
   `python-style` for annotations.
3. **Return type:** the created aggregate's **identity** for a create, `None` for everything else.
   `UUID` when that identity is surrogate — the common case, and what the templates show. When the
   aggregate's key is **natural** — a code, a slug, a handle minted by the domain or supplied by the
   client, with no surrogate column in the schema — the handler returns that key, typed as the key is
   typed, because it *is* the identity. Do not add a surrogate id to an aggregate that has none just to
   satisfy the letter of this rule. Never return the entity. A "do the work, then show the result" use
   case is still a command returning the affected id — the caller re-reads through the matching query
   (`ProcessFoo` returns the foo id; the READY view comes from `GetFoo`). One
   mutate-and-return-a-view operation would straddle the command/query split.
4. **No business logic in the handler.** Build and mutate domain entities; let `__post_init__` and domain
   services enforce the rules. The handler orchestrates: load, mutate, call the repository.
   **Normalization — strip, lowercase, reformat — is a domain concern** living in the entity's
   `__post_init__` or a value object. Pass `cmd.name`, not `cmd.name.strip()`.
5. **No `try/except`, with two sanctioned exceptions.** (a) The compensating-transaction pattern, see
   `hex-patterns`. (b) A **failure-state transition then re-raise**: when the contract requires the aggregate
   to record that it failed before the error propagates — a pipeline that must persist `status=FAILED` so
   a later read or retry sees it — the handler may
   `try: <pipeline> except <Err>: <load-or-mutate>; entity.status = FAILED; await repo.update(entity); raise`.
   The `except` writes the caller-visible state and **re-raises**. Follow `python-logging`
   for logging and `exception-catalog` for exception propagation and boundary translation. Anything beyond
   these two stays forbidden.
6. **Command success logging:** follow `python-logging`; include the caller's identity **only when the
   command carries one**.
7. **No transaction management inside the handler — the default.** A handler that writes through one
   repository leaves the transaction to it: the standalone repository form opens and commits its own
   (`hex-persistence`). The one earned exception is a handler that writes through **two or more**
   repositories atomically: it opens a unit of work itself, one per `execute`, from an injected factory —
   `hex-patterns` owns that form.
8. **Entity ids are `uuid.uuid4()`, minted by the handler before the write, unless the command carries
   an identity its caller supplied** — one scheme across every
   template, production and test alike. Stdlib only, on the interpreter floor `python-style` sets;
   `uuid.uuid7()` is standard library only from **Python 3.14**. Time-ordered v7 ids index better when
   rows created together are read together, and a project that wants them takes a third-party generator
   and applies it everywhere at once — never in half the templates.

### Query handler

1. **One public method.**
   `async def execute(self, query: <QueryClass>) -> <ReturnType>`.
2. **Constructor takes only ports and domain services** — no concrete infrastructure handle, for the
   same reason as a command handler's.
3. **Return type follows the read shape:**
   - a single entity → the entity; the repository fails when missing, using `exception-catalog` for the error.
   - an optional single entity → `Entity | None`; the repository returns `None` when missing.
   - more than one entity, or entities plus pagination metadata → the `*Result` DTO.
   - fields the entity does not carry → a read-model (see above).
4. **No business logic.** A read passes parameters to the repository, optionally consults a domain
   service for "can this caller see this?", and returns.
5. **Reads never log business events and never mutate.** A read is not an event, and a log line per
   read buries the events that are. Who-read-what is a different concern with a different retention and
   a different reader, and it belongs to the entrypoint that served the request; this catalogue states
   no rule for it.
6. **No `try/except`.** Follow `exception-catalog` for exception propagation.
7. **No transaction management.** Reads do not open transactions.

## Inlined typing / import rules

- `X | None`, never `Optional[X]`. Full annotations on `__init__`, `execute` and every parameter.
- `Sequence[T]` from `collections.abc` for read-only views in `*Result` DTOs — never `list[T]`.
- Every value entering or leaving a handler is a declared type — a DTO, a domain type, a read-model —
  never a bare `dict` or tuple (`python-style`).
- Cross-subdomain imports are absolute through the subpackage:
  `from myapp.domain.foos import Foo, IFooRepository`. Same-module imports are relative:
  `from .create_foo_command import CreateFooCommand`.
- A command handler obtains its logger at module top, never inside the class (`import structlog` plus
  `logger = structlog.get_logger()` under the primary binding). A query handler imports no logger at
  all — queries do not log.
- No `from __future__ import annotations`.
- No comments unless a non-obvious *why*; one short line at most.

## Package wiring

Follow `python-packaging` for subpackage re-exports and `hex-architecture` for layer placement. The DI
provider that constructs a handler is `hex-wiring`.

## Hard stops

- A command handler is asked to return a list, a `Result`, or the entity → stop, a mutation returns
  the affected id or nothing; write a query handler beside it and let the caller re-read.
- A query handler is asked to mutate state → stop, split the mutation out into a command handler.
- A handler is asked to catch a `MyappError` and translate it → stop, use `exception-catalog` and `hex-restapi-app`.
- A handler is asked to validate cross-aggregate state inline → stop, use `hex-domain-service` and inject it.
- Several writes must be atomic → stop, use `hex-patterns` for the unit-of-work factory the handler opens.
- An external IO step comes before the DB write → stop, use `hex-patterns` for the command
  body's compensating-transaction form.
- Asked for a Pydantic model in a response → stop, use `hex-restapi-schema` for the entrypoint translation.
- A `*Result` grows past about three fields and starts looking like a different concept → stop, model the
  response as a domain value object or a read-model and return that.
- A query handler is asked to log a read event → stop, a read is not a business event; a record of who read what belongs to the entrypoint, not to the handler.
