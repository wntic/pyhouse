# flat-persistence — the shared plumbing

Topic file of `flat-persistence`. The mechanism-free obligations are rules 8, 9, 10, 11, 12, 14, 15,
16, 17, 18 and 20 in `SKILL.md`; what follows is the **SQLAlchemy Core + asyncpg + Alembic** binding
that satisfies them.

These are the modules written once per package and then left alone — the one `MetaData`, the component's
own settings class, and the engine factory with the bulk write helper every repository class calls — plus
the per-change migration revision that reads the metadata back.

## The metadata module — SQLAlchemy Core (once)

One `MetaData`, in a module of its own, carrying a naming convention. Both halves matter.

`src/myapp/postgres/metadata.py`:

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

`src/myapp/postgres/settings.py`:

```python
from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["PostgresSettings"]


class PostgresSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MYAPP_POSTGRES_",
        env_file=".env",  # only where the project keeps a dotenv file for development
        extra="ignore",
    )

    dsn: SecretStr

    @field_validator("dsn")
    @classmethod
    def _use_async_driver(cls, dsn: SecretStr) -> SecretStr:
        scheme, separator, rest = dsn.get_secret_value().partition("://")
        return SecretStr(f"postgresql+asyncpg{separator}{rest}") if scheme in {"postgres", "postgresql"} else dsn
```

The variable holds the platform's connection string; the class normalizes its scheme to the async
driver's (`postgresql+asyncpg://`) in a validator (`python-settings` rule 12), so the deployment never
spells a driver. The connection string carries the password, so it is secret-typed and unwrapped only where the engine
is built (`python-settings` rules 7 and 9). `MYAPP_POSTGRES_` nests under the process's `MYAPP_`, so
`postgres` is a reserved segment there (`naming`); where the package is shared between distributions its
prefix is the shared package's own, and the `## Other bindings` bullet in `SKILL.md` says what else
changes. A second store's package declares its own `<Store>Settings` under `MYAPP_<STORE>_` and never
adds its fields to this one (rule 17). The process definition constructs `PostgresSettings()`, unwraps
`dsn` and hands the value to the engine factory (`flat-layered` rule 7, and rule 14 in `SKILL.md`); the migration
environment is the migration run's process definition and does the same (`flat-project-setup`).

**No `@lru_cache` on the engine factory.** Memoising an engine keyed by its connection string pins a live
pool for the life of the process, outliving the shutdown path and the test that wanted to dispose of it;
with one caller there is nothing for a cache to collapse.

## Engine and bulk write — SQLAlchemy async, asyncpg

The engine is built by a **factory taking the connection string**, never as a module-level object: the
process definition reads this package's settings once and hands the value down (`flat-layered` rule 7),
and `import myapp.postgres.engine` must not fail in an environment that has set nothing
(`python-packaging` rule 8).

`src/myapp/postgres/engine.py` — the engine factory and one chunked bulk write, the helper only where the
service writes:

```python
from collections.abc import Iterable, Mapping, Sequence
from typing import Any

from sqlalchemy import Table
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

__all__ = ["bulk_upsert", "get_engine"]

_BIND_PARAMETER_CAP = 32767
_WIDEST_TABLE_COLUMNS = 4  # foos
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
```

The helper takes an **already-open `AsyncConnection`** and never commits: it is the connection-accepting
half of rule 3, which is what lets one caller run several statements inside one transaction, and what
makes it testable inside a rolled-back one.

Each chunk builds its insert once and derives the conflict clause from that same statement's `excluded`
row, so the update set names the incoming values of the row that conflicted.

**The rows handed to it are already distinct on the conflict columns.** Postgres refuses a `DO UPDATE`
that touches one row twice in one statement (SQLSTATE `21000`), so the caller collapses its batch by key
first — `record_batch` in `REPOSITORY.md` is the worked case (rule 18).

**Where a later statement needs keys an earlier one resolved** (rule 11), one second helper beside this
one appends `.returning(...)` to the same chunked statement and collects each chunk's rows. Under an
empty update set `DO NOTHING` returns no row for the conflict it skipped, so a caller that needs every
row's key passes a non-empty update set.

The chunk size is **computed once, from two named constants, not written as a literal at the call site**
(rule 10): the driver's bind-parameter cap — 32,767 under asyncpg, because the Postgres wire protocol
carries the parameter count in a 16-bit field — divided by the column count of the widest table the
helper writes. A table wider than `foos` means updating `_WIDEST_TABLE_COLUMNS`, and the chunk size
follows.

An empty `update_columns` list must become `ON CONFLICT DO NOTHING`, not an `UPDATE` with an empty
`SET` — the latter is a syntax error, and "the row already exists and that is fine" is a real case.

## Migrations — Alembic

The migration environment and the revision template are laid once, with the project, under
`migrations/postgres/` at the distribution root (`flat-project-setup`); `alembic.ini` beside
`pyproject.toml` points its `script_location` there. What recurs is one revision per schema change,
authored from the metadata above and reviewed before it is committed:

```bash
alembic revision --autogenerate -m "create foos"
alembic upgrade head
```

Both run from the directory holding `alembic.ini` — the distribution's own root, or the owning library's
where several distributions share the store (rule 15) — so whatever runs the upgrade at deploy carries
`alembic.ini` and `migrations/` with it: a built wheel holds only the package, so an image copies both
beside it, or the migration job runs from the source tree (rule 20). Alembic takes no lock of its own,
so the upgrade runs as one job per deploy, never from each replica as it starts. The revision lands in
`migrations/postgres/versions/`. On a greenfield schema the first of them, the one that creates the first
table, is the root of the chain; there is no empty revision ahead of it. Autogenerate compares tables,
columns, types, nullability, indexes, unique and foreign-key constraints; it does not compare a
`CheckConstraint`, so a change to one is written into the revision by hand. Every revision carries a
`downgrade()` that reverses its `upgrade()`, and the migration round trip the integration suite replays
once per session is what proves it (`flat-test-integration-setup`). Rule 16 in `SKILL.md` states what a
deploy obliges.

A second store's history sits beside this one in `migrations/<store>/`, in whatever format that store's
migration tool reads, and is applied by that tool as its own deploy step (rule 20). It never goes into
`migrations/postgres/`, and never into the package under `src/`.
