# flat-persistence — the shared plumbing

Topic file of `flat-persistence`. The mechanism-free obligations are rules 8, 9, 10, 11, 12, 14 and 15
in `SKILL.md`; what follows is the **SQLAlchemy Core + asyncpg + Alembic** binding that satisfies them.

These are the modules written once per package and then left alone — the one `MetaData`, the component's
own settings class, the engine factory with the bulk write helpers every storage class calls, and the
migration environment that reads the metadata back.

## The metadata module — SQLAlchemy Core (once)

One `MetaData`, in a module of its own, carrying a naming convention. Both halves matter.

`myapp/storage/metadata.py`:

```python
from sqlalchemy import MetaData

metadata = MetaData(
    naming_convention={
        "ix": "ix_%(table_name)s_%(column_0_name)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
)
```

**Its own module, not a table module.** Every table module imports `metadata`, so hosting it inside one
of them makes that table the accidental root of the import graph and creates a cycle the first time it
references another. **The naming convention is load-bearing**: it lets a migration, a translator branch
and a test name the same constraint without inventing it. Left to the backend, names differ by engine and
change under an upsert.

For a `CheckConstraint`, `name=` is the **suffix** — the convention prepends `ck_<table>_`, so passing a
full name yields `ck_foos_ck_foos_name_non_empty`.

## The settings module — pydantic-settings

This package is a component with configuration of its own, so it declares that configuration here rather
than borrowing a field from the service's class (`flat-layered` rule 8).

`myapp/storage/settings.py`:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class StorageSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MYAPP_STORAGE_")

    dsn: str


def get_storage_settings() -> StorageSettings:
    return StorageSettings()
```

**The prefix is this component's own and claims no variable another component's fields could claim** —
the same terms where the package is shared between distributions, and the `## Other bindings` bullet in
`SKILL.md` says what else changes there. **The process definition is the only caller of this factory**: declaring the
class here does not let a module in this package call it. The process definition calls it, reads `dsn`,
and hands the value to the engine factory (`flat-layered` rule 7, and rule 14 in `SKILL.md`).

**No `@lru_cache` on either factory here.** With one caller by construction there is nothing to collapse,
and memoising an engine keyed by its connection string pins a live pool for the life of the process,
outliving the shutdown path and the test that wanted to dispose of it. Needing one is a sign that
something below the process definition is building its own connection instead of being handed one.

## Engine and write helpers — SQLAlchemy async, asyncpg

The engine is built by a **factory taking the connection string**, never as a module-level object: the
process definition reads this package's settings once and hands the value down (`flat-layered` rules 7
and 8), and `import myapp.storage.engine` must not fail in an environment that has set nothing.

`myapp/storage/engine.py` — two write primitives: a plain chunked bulk write, and a `RETURNING` variant
for when a later step needs the rows just written:

```python
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from sqlalchemy import Table
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

_CHUNK_SIZE = 2000  # see below: chunk_size * columns-per-row stays under the driver's bind limit


def get_engine(dsn: str) -> AsyncEngine:
    return create_async_engine(dsn, pool_pre_ping=True)


async def bulk_upsert(
    conn: AsyncConnection,
    table: Table,
    rows: Iterable[Mapping[str, Any]],
    *,
    conflict_columns: Sequence[str],
    update_columns: Sequence[str],
    chunk_size: int = _CHUNK_SIZE,
) -> None:
    rows = list(rows)
    for start in range(0, len(rows), chunk_size):
        chunk = rows[start : start + chunk_size]
        stmt = pg_insert(table).values(chunk)
        if update_columns:
            stmt = stmt.on_conflict_do_update(
                index_elements=conflict_columns,
                set_={col: getattr(stmt.excluded, col) for col in update_columns},
            )
        else:
            stmt = stmt.on_conflict_do_nothing(index_elements=conflict_columns)
        await conn.execute(stmt)


async def bulk_upsert_returning(
    conn: AsyncConnection,
    table: Table,
    rows: Iterable[Mapping[str, Any]],
    *,
    conflict_columns: Sequence[str],
    update_columns: Sequence[str],
    returning_columns: Sequence[str],
    chunk_size: int = _CHUNK_SIZE,
) -> list[dict[str, Any]]:
    """Like bulk_upsert, but hands back the row identity a later write step needs."""
    rows = list(rows)
    results: list[dict[str, Any]] = []
    for start in range(0, len(rows), chunk_size):
        chunk = rows[start : start + chunk_size]
        stmt = (
            pg_insert(table)
            .values(chunk)
            .on_conflict_do_update(
                index_elements=conflict_columns,
                set_={col: getattr(stmt.excluded, col) for col in update_columns},
            )
            .returning(*[table.c[col] for col in returning_columns])
        )
        results.extend(dict(row._mapping) for row in (await conn.execute(stmt)).all())
    return results
```

Both helpers take an **already-open `AsyncConnection`** and never commit: they are the
connection-accepting half of rule 3, which is what lets one caller run several tables' writes inside one
transaction, and what makes them testable inside a rolled-back one.

The chunk size is a **named module constant, not a literal at the call site** (rule 10). `2000` is one
project's worked value against its widest table; a project computes its own from that table's column
count and its driver's bind-parameter cap, and writes the answer here once.

An empty `update_columns` list must become `ON CONFLICT DO NOTHING`, not an `UPDATE` with an empty
`SET` — the latter is a syntax error, and "the row already exists and that is fine" is a real case.

## Migration bootstrap — Alembic (once)

`myapp/alembic/env.py` points `target_metadata` at the one `MetaData`, importing the package first so
every `Table` is registered on it:

```python
import myapp.storage  # noqa: F401  — registers every Table on the shared metadata

from myapp.storage.metadata import metadata

target_metadata = metadata
```

Every schema change is one revision generated from where the schema is defined, and one command applies
it, run from that same place.
