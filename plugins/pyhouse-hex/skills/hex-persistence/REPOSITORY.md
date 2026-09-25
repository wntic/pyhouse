# hex-persistence — the repository adapter

Topic file of `hex-persistence`. The mechanism-free obligations are rules 6–11 and 13 in `SKILL.md`;
what follows is the **SQLAlchemy Core + asyncpg** binding that satisfies them.

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
from datetime import UTC, date, datetime, time, timedelta
from typing import Any, cast
from uuid import UUID

from sqlalchemy import CursorResult, RowMapping, Select, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from myapp.domain.exceptions import (
    ConflictError,
    FooConflictError,
    InUseError,
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

# Only an aggregate with a foreign key carries this map and the 23503 branch.
_FK_FIELD_MAP = {
    "fk_foos_bar_id_bars": "bar_id",
}


def _map_integrity_error(exc: IntegrityError) -> Exception:
    cause = exc.orig.__cause__ if exc.orig else None
    constraint = getattr(cause, "constraint_name", None) if cause else None
    pgcode = getattr(exc.orig, "pgcode", None) or getattr(exc.orig, "sqlstate", None)

    if constraint == "uq_foos_name":
        return FooConflictError("foo name already exists", {"field": "name", "constraint": constraint})
    if pgcode == "23503" and constraint:
        field = _FK_FIELD_MAP.get(constraint, constraint)
        return NotFoundError(f"Referenced {field} not found", {"field": field, "constraint": constraint})
    if pgcode == "23514" and constraint and "name_non_empty" in constraint:
        return ValidationError("name cannot be empty", {"field": "name", "constraint": constraint})

    return ConflictError(
        "integrity violation",
        {"constraint": constraint or "unknown", "pgcode": pgcode or "unknown"},
    )


class FooRepository:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]) -> None:
        self._sf = session_factory

    def _row_to_entity(self, row: RowMapping) -> Foo:
        return Foo(id=row["id"], name=row["name"], bar_id=row["bar_id"])

    async def get_by_id(self, id: UUID) -> Foo:
        async with self._sf() as session:
            row = (
                await session.execute(select(foos_table).where(foos_table.c.id == id))
            ).mappings().one_or_none()
        if row is None:
            raise NotFoundError("Foo not found", {"id": str(id)})
        return self._row_to_entity(row)

    async def get_by_name(self, name: str) -> Foo | None:
        async with self._sf() as session:
            row = (
                await session.execute(select(foos_table).where(foos_table.c.name == name))
            ).mappings().one_or_none()
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
                await session.execute(
                    foos_table.insert().values(id=foo.id, name=foo.name, bar_id=foo.bar_id)
                )
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
                        .values(name=foo.name, bar_id=foo.bar_id, updated_at=func.now())
                    ),
                )
                if result.rowcount == 0:
                    raise NotFoundError("Foo not found", {"id": str(foo.id)})
                await session.commit()
        except IntegrityError as exc:
            raise _map_integrity_error(exc) from exc

    async def delete(self, id: UUID) -> None:
        try:
            async with self._sf() as session:
                result = cast(
                    CursorResult[object],
                    await session.execute(
                        foos_table.delete().where(foos_table.c.id == id)
                    ),
                )
                if result.rowcount == 0:
                    raise NotFoundError("Foo not found", {"id": str(id)})
                await session.commit()
        except IntegrityError as exc:
            raise InUseError("Foo is referenced", {"id": str(id)}) from exc


def _apply_filter[S: Select[Any]](stmt: S, filter: FooListFilter) -> S:
    if filter.bar_ids:
        stmt = stmt.where(foos_table.c.bar_id.in_(filter.bar_ids))
    if filter.created_from is not None:
        stmt = stmt.where(foos_table.c.created_at >= _start_of(filter.created_from))
    if filter.created_to is not None:
        stmt = stmt.where(foos_table.c.created_at < _start_of(filter.created_to + timedelta(days=1)))
    return stmt


def _start_of(day: date) -> datetime:
    return datetime.combine(day, time.min, tzinfo=UTC)
```

Both date bounds are inclusive and read as UTC days: `created_to` admits every instant of that day, so
the upper bound is the start of the next one.

## Template — unit-of-work-managed form

A class of its own, `FooSessionRepository` in `foo_session_repository.py`, when the aggregate needs the
standalone form too. Only the constructor and the method bodies differ: methods use
`self._session.execute(...)` directly and **never call `commit()`** — the unit of work owns the
transaction. The module-level helpers (`_SORT_COLUMNS`, `_FK_FIELD_MAP`, `_map_integrity_error`,
`_apply_filter`) are shared, not copied: once both forms exist they move to one module both adapters
import, so the constraint-name map stays single.

```python
class FooSessionRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, foo: Foo) -> None:
        try:
            await self._session.execute(
                foos_table.insert().values(id=foo.id, name=foo.name, bar_id=foo.bar_id)
            )
        except IntegrityError as exc:
            raise _map_integrity_error(exc) from exc
```

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
14. `delete(id)` returns `None`, or a list of related keys when compensation needs them. `rowcount == 0`
    → `NotFoundError`. An FK `IntegrityError` → `InUseError`, not a generic `ConflictError`.
15. **Reading `rowcount` is type-clean only via a cast.** `execute()` is typed `Result[Any]`, which has no
    `rowcount`. Wrap the DML execute exactly once:
    `result = cast(CursorResult[object], await session.execute(...))`. One canonical form — never an
    ignore comment instead.

## Rules — `IntegrityError` translation

16. **Every `IntegrityError` is translated** before it escapes the repository:
    `raise _map_integrity_error(exc) from exc`, or an inline mapping for one or two cases.
17. **The mapper's fallback is mandatory.** It ends by returning a domain exception when no specific case
    matches. **Never `return exc`**: letting `IntegrityError` leak breaks the
    no-framework-exceptions-across-layers rule and produces a 500 where the entrypoint should give a 409.
18. **Pick the most specific exception.** A domain subclass beats `ConflictError`; `InUseError` beats
    `ConflictError` for an FK on delete.
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

The per-repository `_map_integrity_error` plus `_FK_FIELD_MAP` is the default. When **three or more**
repositories carry overlapping pgcode handlers (`23503` / `23505` / `23514`), extract
`src/myapp/infrastructure/postgres/integrity_error_mapper.py`, which:

- owns the pgcode-to-exception-family defaults (`23503 → NotFoundError`, `23505 → ConflictError`,
  `23514 → ValidationError`) plus the mandatory fallback;
- exposes `map_integrity_error(exc, *, constraint_map: Mapping[str, ConstraintRule]) -> Exception`, where
  each repository registers only its own constraint-name overrides;
- defines `ConstraintRule` as `(DomainErrorClass, message, context_fn)` so per-repository customization
  stays declarative.

Do not introduce it preemptively. Add it the first time a third repository forces the same boilerplate,
and migrate every existing repository in that one commit — partial adoption causes drift.

