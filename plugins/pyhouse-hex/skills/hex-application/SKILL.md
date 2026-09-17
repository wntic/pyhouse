---
name: hex-application
description: Use when writing a use case — a CQRS command handler, a query handler, or its frozen input DTO. Owns the command/query split and the read-model versus write-model rule deciding whether a query returns the entity or a row-projected read-model. Not the entity (`hex-domain-model`) nor the wire model (`hex-restapi-schema`); undo-on-failure or a two-repository commit is `hex-patterns`.
paths: ["**/application/**"]
---

# Hex — Application

The use-case layer, split by CQRS: **commands** mutate and return an id, **queries** read and return
data. Both are thin — a frozen DTO plus a handler class whose only public method is `execute`.

## When to use vs. neighbours

Inside this skill, pick by what the change does:

- A mutation — create, update, delete, rename, move → **command**, a frozen command DTO plus its handler.
- A read — get, list, count, search, detect → **query**, a frozen query DTO plus its handler, and a `*Result` DTO when the response is more than one entity.
- An authorization-scoped read ("things I can see") → **query**, whose DTO carries `caller_id`.
- A read needing audit timestamps, a computed or denormalized value, or a join the entity does not carry → still a query, returning a **read-model** projected directly from the row; see the read/write split under Rules.

Outside it:

- The mutation performs an external IO step before the DB write and must undo it on failure → still a command, but the handler body follows `hex-patterns` (the compensating-transaction form).
- Two or more repositories must commit atomically → still a command, with an `IUnitOfWork` injected; see `hex-patterns`.
- The entity, value object or filter record the DTOs mention → `hex-domain-model`.
- The `IFooRepository` a handler depends on → `hex-domain-ports`.
- A rule needing another aggregate's state, which the handler calls rather than inlines → `hex-domain-service`.
- Turning the return value into JSON → `hex-restapi-schema`. A handler never returns a Pydantic model.
- The route that calls this handler and resolves it from the container → `hex-restapi-endpoint`.
- Where `caller_id` comes from, and the route dependency that supplies it → `hex-restapi-auth`.
- Binding the handler in the composition root → `hex-wiring`.
- Unit-testing the handler against in-memory fakes → `hex-test-application-handler`.
- The path these files land on and the names they take → `hex-conventions` and `naming`.

## Template(s) — stdlib dataclasses, structlog logging

### File layout

```
src/myapp/application/foos/
├── create_foo_command.py   # CreateFooCommand
├── create_foo_handler.py   # CreateFooHandler
├── list_foos_query.py      # ListFoosQuery
├── list_foos_handler.py    # ListFoosHandler
└── list_foos_result.py     # ListFoosResult  (only when the read returns more than one entity)
```

### Command DTO

The authenticated form, carrying `caller_id`. A command reached only by anonymous routes, or any command
in an app with no auth, drops the field entirely — see the auth-derived-fields rule.

```python
from dataclasses import dataclass
from uuid import UUID

from myapp.domain.foos import FooCategory

__all__ = ["CreateFooCommand"]

@dataclass(frozen=True)
class CreateFooCommand:
    caller_id: UUID
    name: str
    category: FooCategory
    sort_order: int = 0
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
        foo = Foo(
            id=uuid.uuid4(),
            name=cmd.name,
            category=cmd.category,
            sort_order=cmd.sort_order,
        )
        await self._repo.create(foo)
        logger.info("foo_created", foo_id=str(foo.id), caller_id=str(cmd.caller_id))
        return foo.id
```

### Command handler — update or delete (returns `None`)

```python
class DeleteFooHandler:
    def __init__(self, repo: IFooRepository) -> None:
        self._repo = repo

    async def execute(self, cmd: DeleteFooCommand) -> None:
        await self._repo.delete(cmd.id)
        logger.info("foo_deleted", foo_id=str(cmd.id), caller_id=str(cmd.caller_id))
```

### Query DTO — not authorization-scoped

```python
from dataclasses import dataclass

from myapp.domain.foos import FooListFilter

__all__ = ["ListFoosQuery"]

@dataclass(frozen=True)
class ListFoosQuery:
    filter: FooListFilter
```

### Query DTO — authorization-scoped

```python
from dataclasses import dataclass
from uuid import UUID

from myapp.domain.foos import FooListFilter

__all__ = ["ListFoosQuery"]

@dataclass(frozen=True)
class ListFoosQuery:
    caller_id: UUID
    filter: FooListFilter
```

### Query handler — single entity

```python
from uuid import UUID

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
  (`python-style`).
- **Another identity scheme** — a time-ordered UUID, a ULID, or a key the store mints. What changes is
  the single expression that mints the id. What does not is that the id exists before the write and that
  the command returns it; a store-minted key is the one case that moves the mint into the repository, and
  the handler then returns what the write handed back. Pick one scheme and apply it to every template at
  once (`hex-conventions`).

## Rules

Files land in `application/<subdomain>/`, where the subdomain is derived rather than chosen
(`hex-conventions` block A).

Artifact names follow `naming`; module boundaries follow `python-packaging`.

### Command or query

- A mutation — create, update, delete, rename, move → **command**.
- A read — get, list, count, search, detect → **query**.
- An authorization-scoped read ("things I can see") → **query**, whose DTO carries `caller_id`.
- The mutation performs an external IO step before the DB write and must undo it on failure → still a
  command, but the handler body follows `hex-patterns` (the compensating-transaction form).
- Two or more repositories must commit atomically → still a command, with an `IUnitOfWork` injected; see
  `hex-patterns`.
- A handler never returns a transport model. The use case must be callable from a second entrypoint —
  a CLI, a consumer — which has no web framework in it.

### Read models — the read/write split that decides a query's return type

The domain entity is the **write** model: commands load and mutate it, and it carries the invariants.

A read that needs more than the entity exposes — **audit timestamps** (`created_at` / `updated_at`,
which are deliberately *not* entity fields), denormalized or computed values, a join across aggregates,
date-range filtering — returns a **read-model DTO** that the repository projects **directly from the
row**, bypassing the entity.

So "the screen shows a creation date" or "filter by `updated_at`" is satisfied by a read-model plus a
repository filter, **never** by pulling the timestamp onto the aggregate — that would make the write
model carry display-only state.

The read-model is a `@dataclass(frozen=True)` in `domain/<subdomain>/` (`FooSummary`, `FooListRow`),
carrying the displayed columns including the audit fields, and the repository protocol method returns
it. It stays a *domain* type so the repository can return it without importing `application` — a
repository may never return an application or Pydantic DTO. Do not reach for a heavyweight value object
per read, and do not bolt audit fields onto the entity to make a read easier.

### Auth-derived fields (both sides)

1. **`caller_id: UUID` is the first field of a command DTO — when the command runs behind an
   authenticated route.** Whether an app has auth at all is a property of its routes
   (`hex-restapi-route-contracts`), so the actor is conditional: a command reached only by anonymous routes,
   or any command in an app with no auth, has no caller to thread and **omits `caller_id`** entirely.
   The templates show the authenticated form. On a query DTO the same field appears **only when the read
   is authorization-scoped**; a non-scoped read omits it.
2. **Every auth-derived field is stamped by the endpoint from the token, never read from the request.**
   A multi-tenant app threads more than the actor: the tenant or scope identifier the credential carries
   — `tenant_id` here, whatever the project calls it — is a field on the DTO set by the endpoint from
   `CurrentUser` (`tenant_id=user.tenant_id`), exactly like `caller_id=user.id` — never from the body or
   path, because a client must not choose its own tenant or read another's data. The handler then scopes
   every repository call by it. Auth-derived inputs come from the token; request-derived inputs from the
   body or path.

### Command DTO

1. **`@dataclass(frozen=True)`.** Always frozen.
2. **No methods, no behaviour.** Just data.
3. **Optional fields:** follow `python-style`.

### Query DTO

1. **`@dataclass(frozen=True)`.** Always frozen.
2. **No methods.** Just data.
3. **Domain filter records are passed by reference, not flattened.** Carry `filter: FooListFilter`, not
   loose `parent_ids` / `created_from` fields.

### Result DTO (when present)

1. **`@dataclass(frozen=True)`, no methods.**
2. **Holds domain types only** — never a transport model, never a row object from the persistence
   library. Either one hands the entrypoint's or the store's vocabulary to every caller of the use case.
3. **Read-only collection typing:** follow `python-style`. Pagination metadata (`total`, `next_cursor`) lives here
   too.
4. **A read that must expose an audit column returns a read-model, not the entity** — see the read/write
   split above.

### Command handler

1. **One public method.**
   `async def execute(self, cmd: <CommandClass>) -> <ReturnType>`. Nothing else public — a second public
   method is a second use case, reachable in a half-finished state.
2. **Constructor takes only ports, domain services, a unit of work, or tunable value objects.** A
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
   **Normalization — strip, lowercase, canonicalize — is a domain concern** living in the entity's
   `__post_init__` or a value object. Pass `cmd.name`, not `cmd.name.strip()`.
5. **No `try/except`, with two sanctioned exceptions.** (a) The compensating-transaction pattern, see
   `hex-patterns`. (b) A **failure-state transition then re-raise**: when the contract requires the aggregate
   to record that it failed before the error propagates — a pipeline that must persist `status=FAILED` so
   a later read or retry sees it — the handler may
   `try: <pipeline> except <Err>: <load-or-mutate>; entity.status = FAILED; await repo.update(entity); raise`.
   The `except` writes the caller-visible state and **re-raises**. Follow `python-style`
   for logging and `exception-catalog` for exception propagation and boundary translation. Anything beyond
   these two stays forbidden.
6. **Command success logging:** follow `python-style`; include
   `caller_id=str(cmd.caller_id)` **only when the command carries it**.
7. **No transaction management inside the handler.** The transaction lifecycle is wired at the entrypoint
   through DI, typically an `IUnitOfWork` when several writes must be atomic.

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
   read buries the events that are; who-read-what is an audit concern the entrypoint owns
   (`python-style`).
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

- Spec asks a command handler to return a list, a `Result`, or the entity → stop, re-read the spec,
  because mutations do not return data; use `hex-application` for a query.
- Spec asks a query handler to mutate state → stop, use `hex-application` to write a command.
- Spec asks a handler to catch a `DomainError` and translate it → stop, use `exception-catalog` and `hex-restapi-app`.
- Spec asks a handler to validate cross-aggregate state inline → stop, use `hex-domain-service` and inject it.
- Spec implies several writes must be atomic → stop, use `hex-patterns` for an `IUnitOfWork` dependency.
- Spec implies an external IO step before the DB write → stop, use `hex-patterns` for the command
  body's compensating-transaction form.
- Spec asks for a Pydantic model in a response → stop, use `hex-restapi-schema` for the entrypoint translation.
- A `*Result` grows past about three fields and starts looking like a different concept → stop, model the
  response as a domain value object or a read-model and return that.
- Spec asks a query handler to log a read event → stop, use `python-style` for audit logging at the entrypoint.
