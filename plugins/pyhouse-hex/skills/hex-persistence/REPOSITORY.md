# hex-persistence — the repository adapter

Topic file of `hex-persistence`. The mechanism-free obligations are rules 1–3 in `SKILL.md`,
`persistence` rules 1, 4–8 and 18, and `python-settings` for the settings class at the end; what follows
is the **SQLAlchemy Core + asyncpg** binding that satisfies them.

## Pick the constructor style

- **Standalone (`session_factory`-injected).** The default. CRUD on a single aggregate: opens its own
  session, commits per call.
- **Unit-of-work-managed (`session`-injected).** Joins a unit of work for multi-repository atomicity.
  Receives a live session and **never commits** (`UNIT_OF_WORK.md`).

The constructor follows the transaction's owner: `FooRepository` takes the session factory because it
owns its transaction and opens one per call, and `FooSessionRepository` takes a live session because the
unit of work owns the transaction and every member must run inside that one — handed a factory, it
would open a second (`persistence` rule 1).

## Template — standalone form

The template is a CRUD service's full set, as the port in `hex-domain-ports` is (its rule 4): an adapter
implements the methods its own port declares and no others, and `_SORT_COLUMNS`, `_apply_filter` and the
`FooListFilter`/`FooSort` imports exist only with `list` and `count`. `_SORT_COLUMNS` holds one entry per
`FooSort` member; the member encodes column and direction.

```python
from collections.abc import Sequence
from typing import Any, cast
from uuid import UUID

from sqlalchemy import CursorResult, RowMapping, Select, func, select
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.exc import TimeoutError as PoolTimeoutError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from myapp.domain.exceptions import (
    ConflictError,
    FooConflictError,
    NotFoundError,
    UpstreamError,
    ValidationError,
)
from myapp.domain.foos import Foo, FooListFilter, FooSort

from ..tables.foos import foos_table

__all__ = ["FooRepository"]

_DRIVER_ERRORS = (DBAPIError, OSError, PoolTimeoutError)

_SORT_COLUMNS = {
    FooSort.CREATED_AT_DESC: foos_table.c.created_at.desc(),
    FooSort.CREATED_AT_ASC: foos_table.c.created_at.asc(),
    FooSort.NAME_ASC: foos_table.c.name.asc(),
}


class FooRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._session_factory = session_factory

    async def get_by_id(self, id: UUID) -> Foo:
        try:
            async with self._session_factory() as session:
                row = (await session.execute(select(foos_table).where(foos_table.c.id == id))).mappings().one_or_none()
        except _DRIVER_ERRORS as exc:
            raise _translate(exc, {"id": str(id)}) from exc
        if row is None:
            raise NotFoundError("Foo not found", {"id": str(id)})
        return _row_to_entity(row)

    async def get_by_name(self, name: str) -> Foo | None:
        try:
            async with self._session_factory() as session:
                statement = select(foos_table).where(foos_table.c.name == name)
                row = (await session.execute(statement)).mappings().one_or_none()
        except _DRIVER_ERRORS as exc:
            raise _translate(exc, {"name": name}) from exc
        return _row_to_entity(row) if row is not None else None

    async def list(self, *, filter: FooListFilter) -> Sequence[Foo]:
        statement = _apply_filter(select(foos_table), filter).order_by(_SORT_COLUMNS[filter.sort], foos_table.c.id)
        statement = statement.limit(filter.limit).offset(filter.offset)
        try:
            async with self._session_factory() as session:
                rows = (await session.execute(statement)).mappings().all()
        except _DRIVER_ERRORS as exc:
            raise _translate(exc, {}) from exc
        return [_row_to_entity(row) for row in rows]

    async def count(self, *, filter: FooListFilter) -> int:
        statement = _apply_filter(select(func.count()).select_from(foos_table), filter)
        try:
            async with self._session_factory() as session:
                total: int = (await session.execute(statement)).scalar_one()
        except _DRIVER_ERRORS as exc:
            raise _translate(exc, {}) from exc
        return total

    async def create(self, foo: Foo) -> None:
        try:
            async with self._session_factory() as session:
                await session.execute(foos_table.insert().values(id=foo.id, name=foo.name, note=foo.note))
                await session.commit()
        except _DRIVER_ERRORS as exc:
            raise _translate(exc, {"id": str(foo.id)}) from exc

    async def update(self, foo: Foo) -> None:
        try:
            async with self._session_factory() as session:
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
        except _DRIVER_ERRORS as exc:
            raise _translate(exc, {"id": str(foo.id)}) from exc

    async def delete(self, id: UUID) -> None:
        try:
            async with self._session_factory() as session:
                result = cast(
                    CursorResult[object],
                    await session.execute(foos_table.delete().where(foos_table.c.id == id)),
                )
                if result.rowcount == 0:
                    raise NotFoundError("Foo not found", {"id": str(id)})
                await session.commit()
        except _DRIVER_ERRORS as exc:
            raise _translate(exc, {"id": str(id)}) from exc


def _row_to_entity(row: RowMapping) -> Foo:
    return Foo(id=row["id"], name=row["name"], note=row["note"])


def _translate(exc: DBAPIError | OSError | PoolTimeoutError, context: dict[str, object]) -> Exception:
    if isinstance(exc, IntegrityError):
        return _map_integrity_error(exc)
    return UpstreamError("the datastore could not complete the operation", context)


def _map_integrity_error(exc: IntegrityError) -> Exception:
    cause = exc.orig.__cause__ if exc.orig else None
    constraint = getattr(cause, "constraint_name", None) if cause else None
    sqlstate = getattr(exc.orig, "pgcode", None) or getattr(exc.orig, "sqlstate", None)

    if constraint == "uq_foos_name":
        return FooConflictError("foo name already exists", {"field": "name", "constraint": constraint})
    if constraint == "ck_foos_name_non_empty":
        return ValidationError("name cannot be empty", {"field": "name", "constraint": constraint})

    return ConflictError(
        "integrity violation",
        {"constraint": constraint or "unknown", "sqlstate": sqlstate or "unknown"},
    )


def _apply_filter[S: Select[Any]](statement: S, filter: FooListFilter) -> S:
    if filter.name is not None:
        statement = statement.where(foos_table.c.name == filter.name)
    return statement
```

## Template — unit-of-work-managed form

A class of its own, `FooSessionRepository` in `foo_session_repository.py`, when the aggregate needs the
standalone form too. Only the constructor and the method bodies differ: methods use
`self._session.execute(...)` directly and **never call `commit()`** — the unit of work owns the
transaction. The module-level helpers (`_DRIVER_ERRORS`, `_SORT_COLUMNS`, `_row_to_entity`,
`_translate`, `_map_integrity_error`, `_apply_filter`) are shared, not copied: once both forms exist they
move to one module both adapters import, so the constraint-name map stays single.

```python
class FooSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, foo: Foo) -> None:
        try:
            await self._session.execute(foos_table.insert().values(id=foo.id, name=foo.name, note=foo.note))
        except _DRIVER_ERRORS as exc:
            raise _translate(exc, {"id": str(foo.id)}) from exc
```

`BarSessionRepository`, which the unit of work in `UNIT_OF_WORK.md` also constructs, is this same joining
form for `Bar` — a second aggregate written in the same transaction, not a second template.

## Rules — form

1. **One class per module.** File `<aggregate_snake>_repository.py`, class `<Aggregate>Repository`.
   Every public method is `async`.
2. **A multi-statement read shares a single `async with` block** — never a session passed across methods
   or held on the instance (`persistence` rule 1).

## Rules — reads

3. `get_by_id(id)` raises `NotFoundError` when absent, never returns `None`.
4. `get_by_<other>(value)` returns `Entity | None` via `one_or_none()`.
5. `list(*, filter)` returns `Sequence[Entity]`, always with an `order_by` derived from `filter.sort` — a
   module-level `_SORT_COLUMNS` map from each sort-enum member to its ordered column — plus the id as a
   tiebreaker, so every page is a total order (`persistence` rule 18). Never hardcode one default order
   that ignores the caller's chosen sort.
6. `count(*, filter)` returns `int` from `select(func.count()).select_from(table)`.
7. Multi-field filter logic extracts to a module-level `_apply_filter(statement, filter)`, generic over the
   statement type so the list query and the count query each keep their own `Select` type.

## Rules — mutations

8. `create(entity)` returns `None`; the handler generated the id.
9. `update(entity)` returns `None`. `rowcount == 0` → `NotFoundError`. Use `func.now()` for
   `updated_at`.
10. `delete(id)` returns `None`. `rowcount == 0` → `NotFoundError`. Where another table references this
    one, the FK integrity error on delete → the catalogue's in-use class.
11. **Reading `rowcount` is type-clean only via a cast.** `execute()` is typed `Result[Any]`, which has no
    `rowcount`. Wrap the DML execute exactly once:
    `result = cast(CursorResult[object], await session.execute(...))`. One canonical form — never an
    ignore comment instead.

## Rules — translation

12. **Every driver error is translated on every public method, a read included** (`persistence`
    rule 4): the whole session block sits inside the `try`, catching `DBAPIError`, `OSError` — asyncpg
    reports a refused connection as the socket's `OSError`, which SQLAlchemy lets through unwrapped —
    and the pool's own `TimeoutError`, raised when no connection frees within the pool's timeout, which
    is neither. An `IntegrityError` goes through `_map_integrity_error`; anything else becomes the
    catalogue's unavailable class with the key it was addressing. `_map_integrity_error`'s closing
    return is the fallback `exception-catalog` rule 10 requires. A second repository on this store moves
    `_DRIVER_ERRORS`, `_translate` and `_map_integrity_error`'s closing fallback into one module both
    import, `repositories/errors.py`; only an adapter's own constraint branches stay with it
    (`persistence` rule 5).
13. **`context` carries `"field"` and `"constraint": constraint`**, the name the driver reports, which is
    the full conventional one (`persistence` rule 6).
14. **A branch compares `constraint` with the full name the `Table`'s convention generates — `==`, never
    `in`** (`persistence` rule 7).
15. **Driver assumption:** the mapper reads `exc.orig.__cause__.constraint_name` and `exc.orig.pgcode`.
    The project is locked to one async driver plus Postgres; changing driver means changing this access
    path.

## Rules — row-to-entity mapper

16. **A naive database datetime becomes UTC-aware in the mapper** —
    `stored.replace(tzinfo=UTC) if stored.tzinfo is None else stored` — this binding's half of `persistence` rule 8.
17. **A private module function after the class, never a private method** — it reads no instance
    state (`python-packaging`). A simple aggregate (one row → one entity) has one `_row_to_entity(row)`;
    a composite aggregate (several rows → one entity) has an assembler,
    `_rows_to_entity(row, child_rows_a, child_rows_b)`, plus one helper per child.

## The store's settings, engine and binding — pydantic-settings, SQLAlchemy, dishka

`src/myapp/infrastructure/postgres/postgres_settings.py` — the settings class the engine factory below
reads. It follows `python-settings`:

```python
from urllib.parse import quote

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["PostgresSettings"]


class PostgresSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MYAPP_POSTGRES_",
        env_file=".env",  # only where the project keeps a dotenv file for development
        extra="ignore",
        hide_input_in_errors=True,
    )

    host: str
    port: int = 5432
    user: str
    password: SecretStr
    name: str

    @property
    def dsn(self) -> str:
        user = quote(self.user, safe="")
        password = quote(self.password.get_secret_value(), safe="")
        return f"postgresql+asyncpg://{user}:{password}@{self.host}:{self.port}/{self.name}"
```

`dsn` is the derived value every consumer reads and the one place the password is unwrapped
(`python-settings` rules 9 and 10), each credential percent-encoded so a password carrying URL
delimiters still connects; `port` defaults to the driver's well-known port. The class carries no
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

from .postgres_settings import PostgresSettings

__all__ = ["create_engine", "create_session_factory"]


def create_engine(settings: PostgresSettings) -> AsyncEngine:
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
from myapp.infrastructure.postgres import PostgresSettings, create_engine, create_session_factory
from myapp.infrastructure.postgres.repositories import FooRepository


class SettingsProvider(Provider):
    scope = Scope.APP

    @provide
    def postgres_settings(self) -> PostgresSettings:
        return PostgresSettings()


class InfrastructureProvider(Provider):
    scope = Scope.APP

    @provide
    async def engine(self, settings: PostgresSettings) -> AsyncIterator[AsyncEngine]:
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

