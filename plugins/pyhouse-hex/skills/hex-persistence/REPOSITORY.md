# hex-persistence — the repository adapter

Topic file of `hex-persistence`. The mechanism-free obligations are rules 6–11 and 13 in `SKILL.md`, and
`python-settings` for the settings class at the end; what follows is the **SQLAlchemy Core + asyncpg**
binding that satisfies them.

One class adapting a domain repository protocol to SQLAlchemy Core. The adapter does not inherit from the
protocol — structural subtyping at the injection site is the contract.

## Pick the constructor style

- **Standalone (`session_factory`-injected).** The default. CRUD on a single aggregate: opens its own
  session, commits per call.
- **Unit-of-work-managed (`session`-injected).** Joins a unit of work for multi-repository atomicity.
  Receives a live session and **never commits** (`hex-patterns`).

The two forms are mutually exclusive for one class. If both call styles are genuinely needed, write two
adapters.

## Template — standalone form

```python
from collections.abc import Sequence
from typing import Any, cast
from uuid import UUID

from sqlalchemy import CursorResult, RowMapping, Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from myapp.domain.exceptions import (
    ConflictError,
    FooConflictError,
    NotFoundError,
    ValidationError,
)
from myapp.domain.foos import Foo, FooListFilter, FooSort

from ..tables.foos import foos_table

__all__ = ["FooRepository"]

# One entry per FooSort member; the member encodes column and direction.
_SORT_COLUMNS = {
    FooSort.CREATED_AT_DESC: foos_table.c.created_at.desc(),
    FooSort.CREATED_AT_ASC: foos_table.c.created_at.asc(),
    FooSort.NAME_ASC: foos_table.c.name.asc(),
}


class FooRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    def _row_to_entity(self, row: RowMapping) -> Foo:
        return Foo(id=row["id"], name=row["name"], note=row["note"])

    async def get_by_id(self, id: UUID) -> Foo:
        async with self._sf() as session:
            row = (await session.execute(select(foos_table).where(foos_table.c.id == id))).mappings().one_or_none()
        if row is None:
            raise NotFoundError("Foo not found", {"id": str(id)})
        return self._row_to_entity(row)

    async def get_by_name(self, name: str) -> Foo | None:
        async with self._sf() as session:
            row = (await session.execute(select(foos_table).where(foos_table.c.name == name))).mappings().one_or_none()
        return self._row_to_entity(row) if row is not None else None

    async def list(self, *, filter: FooListFilter) -> Sequence[Foo]:
        stmt = _apply_filter(select(foos_table), filter).order_by(_SORT_COLUMNS[filter.sort])
        stmt = stmt.limit(filter.limit).offset(filter.offset)
        async with self._sf() as session:
            rows = (await session.execute(stmt)).mappings().all()
        return [self._row_to_entity(r) for r in rows]

    async def count(self, *, filter: FooListFilter) -> int:
        stmt = _apply_filter(select(func.count()).select_from(foos_table), filter)
        async with self._sf() as session:
            total: int = (await session.execute(stmt)).scalar_one()
        return total

    async def create(self, foo: Foo) -> None:
        try:
            async with self._sf() as session:
                await session.execute(foos_table.insert().values(id=foo.id, name=foo.name, note=foo.note))
                await session.commit()
        except IntegrityError as exc:
            raise _map_integrity_error(exc) from exc

    async def update(self, foo: Foo) -> None:
        try:
            async with self._sf() as session:
                result = cast(  # execute() is typed Result[Any], which has no rowcount
                    CursorResult[object],
                    await session.execute(
                        foos_table.update()
                        .where(foos_table.c.id == foo.id)
                        .values(name=foo.name, note=foo.note, updated_at=func.now())
                    ),
                )
                if result.rowcount == 0:
                    raise NotFoundError("Foo not found", {"id": str(foo.id)})
                await session.commit()
        except IntegrityError as exc:
            raise _map_integrity_error(exc) from exc

    async def delete(self, id: UUID) -> None:
        async with self._sf() as session:
            result = cast(
                CursorResult[object],
                await session.execute(foos_table.delete().where(foos_table.c.id == id)),
            )
            if result.rowcount == 0:
                raise NotFoundError("Foo not found", {"id": str(id)})
            await session.commit()


def _map_integrity_error(exc: IntegrityError) -> Exception:
    cause = exc.orig.__cause__ if exc.orig else None
    constraint = getattr(cause, "constraint_name", None) if cause else None
    pgcode = getattr(exc.orig, "pgcode", None) or getattr(exc.orig, "sqlstate", None)

    if constraint == "uq_foos_name":
        return FooConflictError("foo name already exists", {"field": "name", "constraint": constraint})
    if pgcode == "23514" and constraint and "name_non_empty" in constraint:
        return ValidationError("name cannot be empty", {"field": "name", "constraint": constraint})

    return ConflictError(
        "integrity violation",
        {"constraint": constraint or "unknown", "pgcode": pgcode or "unknown"},
    )


def _apply_filter[S: Select[Any]](stmt: S, filter: FooListFilter) -> S:
    if filter.name is not None:
        stmt = stmt.where(foos_table.c.name == filter.name)
    return stmt
```

## Template — unit-of-work-managed form

A class of its own, `FooSessionRepository` in `foo_session_repository.py`, when the aggregate needs the
standalone form too. Only the constructor and the method bodies differ: methods use
`self._session.execute(...)` directly and **never call `commit()`** — the unit of work owns the
transaction. The module-level helpers (`_SORT_COLUMNS`, `_map_integrity_error`, `_apply_filter`) are
shared, not copied: once both forms exist they move to one module both adapters import, so the
constraint-name map stays single.

```python
class FooSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, foo: Foo) -> None:
        try:
            await self._session.execute(foos_table.insert().values(id=foo.id, name=foo.name, note=foo.note))
        except IntegrityError as exc:
            raise _map_integrity_error(exc) from exc
```

`BarSessionRepository`, which the unit of work in `hex-patterns` also constructs, is this same joining
form for `Bar` — a second aggregate written in the same transaction, not a second template.

## Rules — form

1. **One class per module.** File `<aggregate_snake>_repository.py`, class `<Aggregate>Repository`.
2. **No explicit protocol inheritance.** Structural subtyping.
3. **Method signatures match the protocol exactly**, keyword-only markers included
   (`*, filter: FooListFilter`). Every public method is `async`.

## Rules — session

4. **Standalone:** each method opens its own session (`async with self._sf() as session:`); a mutation
   `await session.commit()`, a read does not.
5. **Unit-of-work-managed:** the session arrives in `__init__` and is used directly; **never** call
   `commit()` or `rollback()`.
6. **No instance state holding a session.** Do not pass one across methods — a multi-statement read shares
   a single `async with` block instead.

## Rules — reads

7. `get_by_id(id)` raises `NotFoundError` when absent, never returns `None`.
8. `get_by_<other>(value)` returns `Entity | None` via `one_or_none()`.
9. `list(*, filter)` returns `Sequence[Entity]`, always with an `order_by` derived from `filter.sort` — a
   module-level `_SORT_COLUMNS` map from each sort-enum member to its ordered column. Never hardcode one
   default order that ignores the caller's chosen sort.
10. `count(*, filter)` returns `int` from `select(func.count()).select_from(table)`.
11. Multi-field filter logic extracts to a module-level `_apply_filter(stmt, filter)`, generic over the
    statement type so the list query and the count query each keep their own `Select` type.

## Rules — mutations

12. `create(entity)` returns `None`; the handler generated the id. Wrap in `try/except IntegrityError`.
13. `update(entity)` returns `None`. `rowcount == 0` → `NotFoundError`. Use `func.now()` for
    `updated_at`.
14. `delete(id)` returns `None`. `rowcount == 0` → `NotFoundError`. Where another table references this
    one, the FK integrity error on delete → the catalogue's in-use class.
15. **Reading `rowcount` is type-clean only via a cast.** `execute()` is typed `Result[Any]`, which has no
    `rowcount`. Wrap the DML execute exactly once:
    `result = cast(CursorResult[object], await session.execute(...))`. One canonical form — never an
    ignore comment instead.

## Rules — `IntegrityError` translation

16. **Every `IntegrityError` is translated** before it escapes the repository —
    `raise _map_integrity_error(exc) from exc`, or an inline mapping for one or two cases (`exception-catalog`
    rule 8).
17. **The mapper's fallback is mandatory** — `exception-catalog` rule 10; the `ConflictError` return at the
    end of `_map_integrity_error` is it.
18. **The most specific class wins** — `exception-catalog` rule 9. Where another table references this
    one, the FK integrity error on delete → the catalogue's in-use class.
19. **Populate `context` with the offending field and the constraint name.** Always include
    `"constraint": constraint` — the full conventional name — so the entrypoint and the tests can assert
    on it.
20. **The full constraint names are load-bearing** and must match what the `Table` declared. A rename is a
    breaking change touching this file and `TABLE.md` together.
21. **Driver assumption:** the mapper reads `exc.orig.__cause__.constraint_name` and `exc.orig.pgcode`.
    The project is locked to one async driver plus Postgres; changing driver means changing this access
    path.

## Rules — row-to-entity mapper

22. Pure functions: no IO, no logging. Convert a naive database datetime to UTC-aware —
    `dt.replace(tzinfo=UTC) if dt.tzinfo is None else dt`.
23. **Module level when more than one method or helper uses it; a private method when exactly one
    does.** A simple aggregate (one row → one entity) is read by `get_by_id`, `get_by_<other>` and
    `list`, but through one `_row_to_entity` private method. A composite aggregate (several rows → one
    entity) needs per-child helpers as well as the assembler, so `_rows_to_entity(row, child_rows_a,
    child_rows_b)` and each helper go to module level.

## Evolution — when to extract a shared integrity-error mapper

The per-repository `_map_integrity_error` is the default. When **three or more**
repositories carry overlapping pgcode handlers (`23503` / `23505` / `23514`), extract
`src/myapp/infrastructure/postgres/integrity_error_mapper.py`, which:

- owns the pgcode-to-exception-family defaults (`23503 → NotFoundError`, `23505 → ConflictError`,
  `23514 → ValidationError`) plus the mandatory fallback;
- exposes `map_integrity_error(exc, *, constraint_map: Mapping[str, ConstraintRule]) -> Exception`, where
  each repository registers only its own constraint-name overrides;
- defines `ConstraintRule` as `(MyappError subclass, message, context_fn)` so per-repository customization
  stays declarative.

Do not introduce it preemptively. Add it the first time a third repository forces the same boilerplate,
and migrate every existing repository in that one commit — partial adoption causes drift.

## The store's settings, engine and binding — pydantic-settings, SQLAlchemy, dishka

`src/myapp/infrastructure/postgres/settings.py` — the settings class the engine factory below reads. It
follows `python-settings`:

```python
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["DbSettings"]


class DbSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MYAPP_DB_",
        env_file=".env",  # only where the project keeps a dotenv file for development
        extra="ignore",
    )

    host: str
    port: int = 5432
    user: str
    password: SecretStr
    name: str

    @property
    def dsn(self) -> str:
        return (
            f"postgresql+asyncpg://{self.user}:{self.password.get_secret_value()}@{self.host}:{self.port}/{self.name}"
        )
```

`dsn` is the derived value every consumer reads and the one place the password is unwrapped
(`python-settings` rules 9 and 10); `port` defaults to the driver's well-known port. The class carries no
pool-sizing field, because a deployment's number never ships as a default: pool-sizing fields are added,
required, when the deployment sizes the pool. Pre-ping is not a setting — the engine factory passes
`pool_pre_ping=True` literally, since one cheap round trip buys immunity to connections the server
closed underneath the pool.

`src/myapp/infrastructure/postgres/engine.py` — the engine and session factories, complete glue: they
carry no judgment, so they are written in full, never left as a stub (`hex-conventions` rule 7).

```python
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from .settings import DbSettings

__all__ = ["create_engine", "create_session_factory"]


def create_engine(settings: DbSettings) -> AsyncEngine:
    return create_async_engine(settings.dsn, pool_pre_ping=True)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
```

The engine reads the DSN the settings object derives rather than reassembling it from parts
(`python-settings` rule 10), and passes `pool_pre_ping=True` literally. A pool-sizing argument
(`pool_size`, `max_overflow`) appears only when the deployment sizes the pool, and then beside the
required settings field it reads — never as a default. `expire_on_commit=False` keeps a row's values
readable after the commit that wrote it, which an async session cannot lazily reload.

The binding is an add-on to the base composition root in `hex-wiring`'s `CONTAINER.md`, which binds no
store. A project whose aggregates are relational merges each class below into the base's provider of the
same name, the repository line first in its subdomain's provider, ahead of the services that use it:

```python
from collections.abc import AsyncIterator

from dishka import Provider, Scope, provide
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from myapp.domain.foos import IFooRepository
from myapp.infrastructure.postgres import DbSettings, create_engine, create_session_factory
from myapp.infrastructure.postgres.repositories import FooRepository


class SettingsProvider(Provider):
    scope = Scope.APP

    @provide
    def db_settings(self) -> DbSettings:
        return DbSettings()


class InfrastructureProvider(Provider):
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
    scope = Scope.REQUEST

    foo_repository = provide(FooRepository, provides=IFooRepository)
```

