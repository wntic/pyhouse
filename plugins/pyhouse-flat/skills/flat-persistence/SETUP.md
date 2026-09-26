# flat-persistence — the shared plumbing

Topic file of `flat-persistence`. The mechanism-free obligations are rules 8, 9, 10, 11, 12, 14, 15 and 16
in `SKILL.md`; what follows is the **SQLAlchemy Core + asyncpg + Alembic** binding that satisfies them.

These are the modules written once per package and then left alone — the one `MetaData`, the component's
own settings class, and the engine factory with the bulk write helpers every storage class calls — plus
the per-change migration revision that reads the metadata back.

## The metadata module — SQLAlchemy Core (once)

One `MetaData`, in a module of its own, carrying a naming convention. Both halves matter.

`src/myapp/storage/metadata.py`:

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

`src/myapp/storage/settings.py`:

```python
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["StorageSettings", "get_storage_settings"]


class StorageSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MYAPP_STORAGE_",
        env_file=".env",
        extra="ignore",
    )

    dsn: SecretStr


def get_storage_settings() -> StorageSettings:
    return StorageSettings()
```

**The connection string is a secret-typed field**, because it carries the password: a secret type keeps
it out of the settings object's `repr` and out of any log line or error that renders one. It is unwrapped
with `.get_secret_value()` at the one place the engine is built, and nowhere else.

**The prefix is this component's own and claims no variable another component's fields could claim** —
the same terms where the package is shared between distributions, and the `## Other bindings` bullet in
`SKILL.md` says what else changes there. **The process definition is the only caller of this factory**: declaring the
class here does not let a module in this package call it. The process definition calls it, unwraps `dsn`,
and hands the value to the engine factory (`flat-layered` rule 7, and rule 14 in `SKILL.md`); the
migration environment is the migration run's process definition and does the same (`flat-project-setup`).

**No `@lru_cache` on either factory here.** With one caller by construction there is nothing to collapse,
and memoising an engine keyed by its connection string pins a live pool for the life of the process,
outliving the shutdown path and the test that wanted to dispose of it. Needing one is a sign that
something below the process definition is building its own connection instead of being handed one.

## Engine and write helpers — SQLAlchemy async, asyncpg

The engine is built by a **factory taking the connection string**, never as a module-level object: the
process definition reads this package's settings once and hands the value down (`flat-layered` rules 7
and 8), and `import myapp.storage.engine` must not fail in an environment that has set nothing.

`src/myapp/storage/engine.py` — two write primitives: a plain chunked bulk write, and a `RETURNING` variant
for when a later step needs the rows just written:

```python
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from sqlalchemy import Table
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

__all__ = ["bulk_upsert", "bulk_upsert_returning", "get_engine"]

_BIND_PARAMETER_CAP = 32767  # asyncpg: the wire protocol counts parameters in an int16
_WIDEST_TABLE_COLUMNS = 5  # foos
_CHUNK_SIZE = _BIND_PARAMETER_CAP // _WIDEST_TABLE_COLUMNS


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
        ins = pg_insert(table).values(rows[start : start + chunk_size])
        if update_columns:
            stmt = ins.on_conflict_do_update(
                index_elements=conflict_columns,
                set_={col: ins.excluded[col] for col in update_columns},
            )
        else:
            stmt = ins.on_conflict_do_nothing(index_elements=conflict_columns)
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
    """Like bulk_upsert, but hands back the columns a later write step needs.

    Under an empty update set a conflicting row is left alone and is not returned.
    """
    rows = list(rows)
    returning = [table.c[col] for col in returning_columns]
    results: list[dict[str, Any]] = []
    for start in range(0, len(rows), chunk_size):
        ins = pg_insert(table).values(rows[start : start + chunk_size])
        if update_columns:
            stmt = ins.on_conflict_do_update(
                index_elements=conflict_columns,
                set_={col: ins.excluded[col] for col in update_columns},
            ).returning(*returning)
        else:
            stmt = ins.on_conflict_do_nothing(index_elements=conflict_columns).returning(*returning)
        results.extend(dict(row._mapping) for row in await conn.execute(stmt))
    return results
```

Both helpers take an **already-open `AsyncConnection`** and never commit: they are the
connection-accepting half of rule 3, which is what lets one caller run several tables' writes inside one
transaction, and what makes them testable inside a rolled-back one.

Each chunk builds its insert once and derives the conflict clause from that same statement's `excluded`
row, so the update set names the incoming values of the row that conflicted.

The chunk size is **computed once, from two named constants, not written as a literal at the call site**
(rule 10): the driver's bind-parameter cap — 32,767 under asyncpg, because the Postgres wire protocol
carries the parameter count in a 16-bit field — divided by the column count of the widest table the
helpers write. A table wider than `foos` means updating `_WIDEST_TABLE_COLUMNS`, and the chunk size follows.

An empty `update_columns` list must become `ON CONFLICT DO NOTHING`, not an `UPDATE` with an empty
`SET` — the latter is a syntax error, and "the row already exists and that is fine" is a real case. Under
`DO NOTHING` the database returns no row for the conflict it skipped, so a caller of the read-back that
needs every row's identity passes a non-empty update set.

## Migrations — Alembic

The migration environment, the revision template and the baseline revision are laid once, with the
project (`flat-project-setup`). What recurs is one revision per schema change, authored from the metadata
above and reviewed before it is committed:

```bash
alembic revision --autogenerate -m "create foos"
alembic upgrade head
```

Both run from the directory holding `alembic.ini` — the distribution's own root, or the owning library's
where several distributions share the store (rule 15). Autogenerate compares tables, columns, types,
nullability, indexes, unique and foreign-key constraints; it does not compare a `CheckConstraint`, so a
change to one is written into the revision by hand. Every revision carries a `downgrade()` that reverses
its `upgrade()`, and the migration round trip the integration suite replays once per session is what
proves it (`flat-test-integration-setup`). Rule 16 in `SKILL.md` states what a deploy obliges.
