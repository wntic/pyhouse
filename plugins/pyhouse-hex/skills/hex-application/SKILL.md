---
name: hex-application
description: Use when writing a use case — a CQRS command handler, a query handler, or its frozen input DTO — including a command that needs compensation, undoing an external write such as an upload when a later store write fails. Owns the command/query split, the read-model versus write-model rule deciding whether a query returns the entity or a row-projected read-model, the try/undo/re-raise compensation body, and a clearable field a partial update carries with its presence. Not the entity (`hex-domain-model`) nor the wire model (`hex-restapi-schema`); a unit of work making two repositories commit together is `hex-persistence`.
paths: ["**/application/**"]
---

# Hex — Application

The use-case layer, split by CQRS: **commands** mutate and return an id, **queries** read and return
data. Both are thin — a frozen DTO plus a handler class whose only public method is `execute`.

## When to use vs. neighbours

Command or query → Command or query, at the head of Rules; whether a query returns the entity or a
read-model → Read models, beside it; an undo-on-failure body → Compensation, under Rules, and its template in `COMPENSATION.md`. Outside it:

- A handler writing two or more repositories in one transaction — the unit of work, its protocol and
  the handler form that opens it → `hex-persistence` (`UNIT_OF_WORK.md`).
- The reversing method a compensation calls → declared beside its forward operation by
  `hex-domain-ports`, implemented in `hex-capability-adapter` or `hex-store-repository`.
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

Where the command makes an externally visible write before a store write that can still fail, this
body gains the try/undo/re-raise form — **read `COMPENSATION.md`**, in this skill's directory, before
writing it; the obligations are Compensation, under Rules.

### Command DTO and handler — update (returns `None`)

A partial update, the same contract as the PATCH body (`hex-restapi-schema`): `None` on `name` leaves it
unchanged; `note` may be cleared, so it carries `sets_note` (Command DTO rule 4).

```python
from dataclasses import dataclass
from uuid import UUID

__all__ = ["UpdateFooCommand"]


@dataclass(frozen=True)
class UpdateFooCommand:
    id: UUID
    sets_note: bool
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
            note=cmd.note if cmd.sets_note else foo.note,
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

`get_foo_query.py`, then `get_foo_handler.py`.

```python
from dataclasses import dataclass
from uuid import UUID

__all__ = ["GetFooQuery"]


@dataclass(frozen=True)
class GetFooQuery:
    id: UUID
```

```python
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

`list_foos_handler.py`, then `list_foos_result.py`.

```python
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
  command, whose body follows Compensation, below.
- Two or more repositories must commit atomically → still a command, opening a unit of work
  (Command handler rule 7).
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
4. **A field the caller may clear carries whether the caller gave it, apart from its value**, so
   "absent" and "cleared" stay distinct and a value the caller gave is never ignored — one `None`
   cannot mean both. A field that cannot be cleared carries no such distinction; `None` on it
   means "leave it unchanged".

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
4. **A `*Result` that grows past about three fields and starts reading as a concept of its own is
   modelled as a domain value object or a read-model, and the query returns that instead.**

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
   satisfy the letter of this rule. Never return the entity, a list or a `*Result`. A "do the work, then show the result" use
   case is still a command returning the affected id — the caller re-reads through the matching query
   (`ProcessFoo` returns the foo id; the READY view comes from `GetFoo`). One
   mutate-and-return-a-view operation would straddle the command/query split.
4. **No business logic in the handler.** Build and mutate domain entities; let `__post_init__` and domain
   services enforce the rules. The handler orchestrates: load, mutate, call the repository.
   **Normalization — strip, lowercase, reformat — is a domain concern** living in the entity's
   `__post_init__` or a value object. Pass `cmd.name`, not `cmd.name.strip()`.
5. **No `try/except`, with two sanctioned exceptions.** (a) Compensation, below — its `try/except
   Exception` and the guard around its undo. (b) A **failure-state transition then re-raise**: when the contract requires the aggregate
   to record that it failed before the error propagates — a pipeline that must persist `status=FAILED` so
   a later read or retry sees it — the handler may
   `try: <pipeline> except <Err>: <load-or-mutate>; entity.status = FAILED; await repo.update(entity); raise`.
   The `except` writes the caller-visible state and **re-raises**. Follow `python-logging`
   for logging and `exception-catalog` for exception propagation and boundary translation. Anything beyond
   these two stays forbidden.
6. **Command success logging:** the application layer logs successes only, after the write
   (`hex-architecture`), in `python-logging`'s event shape; include the caller's identity **only when the
   command carries one**.
7. **No transaction management inside the handler — the default.** A handler that writes through one
   repository leaves the transaction to it: the standalone repository form opens and commits its own
   (`hex-persistence`). The one earned exception is a handler that writes through **two or more**
   repositories atomically: it opens a unit of work itself, one per `execute`, from an injected factory —
   `hex-persistence` owns that form (`UNIT_OF_WORK.md`).
8. **Entity ids are `uuid.uuid4()`, minted by the handler before the write, unless the command carries
   an identity its caller supplied** — one scheme across every
   template, production and test alike. Stdlib only, on the interpreter floor `python-style` sets;
   `uuid.uuid7()` is standard library only from **Python 3.14**. Time-ordered v7 ids index better when
   rows created together are read together, and a project that wants them takes a third-party generator
   and applies it everywhere at once — never in half the templates.

### Compensation — when a command handler undoes an external write

1. **Compensate only an externally visible write — a blob upload, a third-party POST, a file write —
   that lands before a store write that can still fail.** A side effect harmless if left behind, the last
   step with nothing after it, or one that can be reordered after the store write needs no `try/except`.
2. **The side effect runs outside the `try`, and only the fallible next step inside it.** Validation —
   building the entity, whose invariants run in its constructor — comes before the side effect, so a
   malformed command fails with nothing to undo.
3. **Catch `Exception`, not specific classes**, so the undo runs whatever the cause.
4. **The undo is the port's plain reversing method (`delete`, `retract`), which raises like any other
   call, wrapped in its own guard inside the `except`** — `exception-catalog`'s best-effort
   compensation, logging its one warning in `python-logging`'s shape — never a dedicated
   `*_best_effort` method, never swallowed without its warning.
5. **The original failure is re-raised unchanged with a bare `raise` and not logged here** — a
   re-raising scope stays silent (`python-logging`).
6. **Several side effects are recorded as each lands, and on failure each recorded one is undone behind
   its own guard**, so a failure part-way still cleans what already landed.
7. **Compensation wraps a unit of work, never the reverse.**
8. **Disposing of a replaced resource after a successful commit is not compensation** — no failure is
   propagating, so its failure propagates like any other step's.

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
5. **Reads never log business events and never mutate** — a mutation is a command handler of its own. A read is not an event, and a log line per
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
- A command handler's logger follows `python-logging` rule 1. A query handler imports no logger at
  all — queries do not log.
- No `from __future__ import annotations`.
- No comments unless a non-obvious *why*; one short line at most.

## Package wiring

Follow `python-packaging` for subpackage re-exports and `hex-architecture` for layer placement. The DI
provider that constructs a handler is `hex-wiring`.

## Hard stops

- A handler is asked to catch a `MyappError` and translate it → stop, use `exception-catalog` and `hex-restapi-app`.
- A handler is asked to validate cross-aggregate state inline → stop, use `hex-domain-service` and inject it.
- Several repository writes must be atomic → stop, read `hex-persistence`'s `UNIT_OF_WORK.md` for the
  factory the handler opens.
- The undo a compensation needs has no reversing method on the port → stop, declare it beside the
  forward operation first (`hex-domain-ports`).
- Compensation would span two unrelated backends in both directions → stop, that is a saga, and out of
  scope.
- Asked for a Pydantic model in a response → stop, use `hex-restapi-schema` for the entrypoint translation.
