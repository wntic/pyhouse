---
name: flat-schema-package
description: Use when changing the one shared `packages/myschema/` library that several uv-workspace services import — its raw and filtered table pairs, chunked bulk upserts, the `entities`/`entity_kinds` identity registry deduplicating what more than one producer discovers, and its Alembic revisions. Not one hexagonal service's own tables and repository adapters (`hex-persistence`), and not the workspace root or its members (`flat-monorepo`).
paths: ["**/packages/**"]
---

# Flat Schema Package — shared schema package

Covers `packages/myschema/` in a `flat-monorepo`: one raw/filtered table pair per producer,
a shared registry that deduplicates an identity several producers can independently discover, and the
bulk/repository write path. No producer service defines a `Table`, writes SQL, or touches the registry
directly.

"Producer" here means any service that discovers records and writes them — a parser, a crawler, a
feed consumer. The vocabulary is deliberately generic: each producer owns a `kind` string and a table
pair, and nothing in this package knows what the kinds mean.

## When to use vs. neighbours

- Creating the workspace root and the empty `packages/myschema/` shell → not this skill, use
  `flat-monorepo` first.
- A producer's own internal role-package layout — cross-cutting setup, clients, run functions;
  `core/`, `services/`, `ingest/`, `jobs/` in `flat-layered`'s worked example → not this skill, use
  `flat-layered`.
- One service's *own* private `Table`, repository adapter and Alembic revision, rather than the library
  every producer imports → the other family's `hex-persistence`, in the `pyhouse-hex` plugin.
- The producer needs real business invariants protected from storage choices → not this skill; that is
  a signal for ports-and-adapters (`hex-persistence`, in `pyhouse-hex`), not flat-layered at all.
- Which family a new service belongs to before any of this is decided → `architecture-choice`.
- Testing the shared tables, the bulk helpers or the repository class against real Postgres →
  `flat-test-schema-package`.
- The container, migration and rollback fixtures those tests run on → `flat-test-integration-setup`.
- Module layout, `__all__`, and the `tables/__init__.py` re-exports every table module needs →
  `python-packaging`.
- Every producer's output is independent — nothing is ever discovered by more than one producer → the
  registry/junction pair is unneeded; a plain per-producer `*_filtered` table plus a `UNION ALL` view
  is enough (drop `entities`/`entity_kinds`, keep the rest of this skill).

## The shared metadata — SQLAlchemy Core (once)

One `MetaData`, in a module of its own, carrying a naming convention. Both halves matter.

`packages/myschema/src/myschema/metadata.py`:

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

**Its own module, not a table module.** Every table module imports `metadata`, so hosting it inside
one of them makes that table the accidental root of the import graph and creates a cycle the first
time it wants to reference another. **The naming convention is load-bearing**: it is what lets a
migration and an error-handling branch refer to the same constraint by a name neither of them
invented. Without it Postgres assigns names like `foo_filtered_identity_key`, which differ by backend
and change under `ON CONFLICT`.

For a `CheckConstraint`, `name=` is the **suffix** — the convention prepends `ck_<table>_`. Passing a
full name yields `ck_foos_ck_foos_name_non_empty`.

## Engine and settings — SQLAlchemy async, asyncpg, pydantic-settings (once)

`myschema` is imported by every producer, by Alembic, and by anything that merely wants to type-check
against it — none of which necessarily have `MYSCHEMA_*` in their environment yet. Settings and the
engine are therefore built **lazily**, behind an `lru_cache`-wrapped factory, never as a bare
module-level object constructed at import time: `import myschema.engine` must never fail on its own,
only an actual call to `get_settings()`/`get_engine()` should.

**One prefix per settings class, named after the component that owns it** — `MYSCHEMA_` here, `MYAPP_`
in the service that depends on it. The prefixes must be disjoint: a service and the shared schema
package are separate deployables reading the same environment, and a shared prefix makes one component's
variable silently satisfy the other's field.

`packages/myschema/src/myschema/settings.py`:

```python
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MYSCHEMA_")

    dsn: str  # postgresql+asyncpg://user:pass@host:5432/myrepo


@lru_cache
def get_settings() -> Settings:
    return Settings()
```

`packages/myschema/src/myschema/engine.py` — two write primitives: a plain chunked bulk write, and a
`RETURNING` variant for when a later step needs the ids just written:

```python
from collections.abc import Iterable, Mapping, Sequence
from functools import lru_cache
from typing import Any

from sqlalchemy import Table
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from myschema.settings import get_settings

_CHUNK_SIZE = 2000  # see below: chunk_size * columns-per-row stays under the driver's bind limit


@lru_cache
def get_engine() -> AsyncEngine:
    return create_async_engine(get_settings().dsn, pool_pre_ping=True)


@lru_cache
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


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
    """Like bulk_upsert, but hands back the row identity a later write step needs (e.g. generated ids)."""
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

The chunk size is a **named module constant, not a literal at the call site**, and the rule it encodes
is *chunk below the driver's bind-parameter limit*: one statement binds `chunk_size * columns-per-row`
parameters, and a batch that crosses the driver's cap fails at execute time on size alone, whatever the
data says. `2000` is one workspace's worked value against its widest table; a project computes its own
from that table's column count and its driver's cap, and writes the answer here once.

`bulk_upsert` takes an **already-open `AsyncConnection`** rather than owning the transaction itself,
so a repository method can run several tables' writes in one `engine.begin()` block. That parameter
is also what makes it testable inside a rolled-back transaction.

An empty `update_columns` list must become `ON CONFLICT DO NOTHING`, not an `UPDATE` with an empty
`SET` — the latter is a syntax error, and "the row already exists and that is fine" is a real case the
registry's junction relies on.

## Per-producer tables — SQLAlchemy Core on Postgres (one pair per producer)

Every primary key is a **UUIDv7**, generated client-side via the `uuid6` package's `uuid7()` — never
`uuid.uuid4()` and never a Postgres-side `server_default`. UUIDv7 is time-ordered, so ids inserted
together sort and index together; `uuid.uuid4()`'s randomness scatters otherwise-related rows across a
b-tree index for no benefit. `uuid6.uuid7()` returns a `uuid.UUID` subclass, so it drops straight into
`Column(..., default=uuid7)` and every `UUID(as_uuid=True)` column type unchanged.

`packages/myschema/src/myschema/tables/foo.py`:

```python
from sqlalchemy import Column, DateTime, ForeignKey, String, Table
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import func
from uuid6 import uuid7

from myschema.metadata import metadata

foo_raw_table = Table(
    "foo_raw",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid7),
    Column("external_id", String, nullable=False, unique=True),
    Column("fetched_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column("raw", JSONB, nullable=False),
)

foo_filtered_table = Table(
    "foo_filtered",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid7),
    Column("raw_id", UUID(as_uuid=True), ForeignKey("foo_raw.id"), nullable=True),
    Column("identity", String, nullable=False, unique=True),  # normalized natural key
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    # producer-specific typed columns follow
)
```

`tables/__init__.py` re-exports every table module and the metadata, so Alembic autogenerate sees the
whole schema from one import.

## The shared entity registry — SQLAlchemy Core (dedup across producers)

Use this pair only when the same real-world identity — whatever a producer's `identity` column holds —
can legitimately be discovered independently by more than one producer, and a single deduplicated
record carrying every kind that found it is required.

`packages/myschema/src/myschema/tables/registry.py`:

```python
from sqlalchemy import Column, DateTime, ForeignKey, PrimaryKeyConstraint, String, Table
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from uuid6 import uuid7

from myschema.metadata import metadata

entities_table = Table(
    "entities",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid7),
    Column("identity", String, nullable=False, unique=True),
    Column("first_seen_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    Column("last_seen_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)

entity_kinds_table = Table(
    "entity_kinds",
    metadata,
    Column("entity_id", UUID(as_uuid=True), ForeignKey("entities.id"), nullable=False),
    Column("kind", String(64), nullable=False),  # declared width — kinds are short producer names
    Column("discovered_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    PrimaryKeyConstraint("entity_id", "kind"),
)
```

Dump view — one row per entity, kinds folded into an array, regenerated with `DROP VIEW` +
`CREATE VIEW` in an Alembic migration whenever the view's shape changes. Adding a producer does **not**
require touching this view, unlike a plain-UNION design: a new producer just starts writing rows with
its own `kind`.

```sql
CREATE VIEW entities_with_kinds AS
  SELECT e.id, e.identity, e.first_seen_at, e.last_seen_at,
         array_agg(ek.kind ORDER BY ek.kind) AS kinds
  FROM entities e
  JOIN entity_kinds ek ON ek.entity_id = e.id
  GROUP BY e.id, e.identity, e.first_seen_at, e.last_seen_at;
```

## Repository class — SQLAlchemy async (multi-table atomic write)

`packages/myschema/src/myschema/repositories/entities.py` — a concrete class, no `Protocol` (rule 3 of
`flat-layered`: one implementation). It exists specifically because this write spans three tables and
the second step's output (`entity.id`) feeds the third step's input:

```python
from typing import Any

from sqlalchemy import Table
from sqlalchemy.ext.asyncio import AsyncEngine

from myschema.engine import bulk_upsert, bulk_upsert_returning
from myschema.tables.registry import entities_table, entity_kinds_table


class EntitiesRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def record_batch(
        self, filtered_table: Table, kind: str, rows: list[dict[str, Any]]
    ) -> None:
        """rows must each carry the `identity` column filtered_table and entities share."""
        if not rows:
            return
        update_columns = [c for c in rows[0] if c != "identity"]
        async with self._engine.begin() as conn:
            await bulk_upsert(
                conn,
                filtered_table,
                rows,
                conflict_columns=["identity"],
                update_columns=update_columns,
            )
            entity_rows = await bulk_upsert_returning(
                conn,
                entities_table,
                [{"identity": r["identity"]} for r in rows],
                conflict_columns=["identity"],
                update_columns=["last_seen_at"],
                returning_columns=["id", "identity"],
            )
            id_by_identity = {r["identity"]: r["id"] for r in entity_rows}
            kind_rows = [
                {"entity_id": id_by_identity[r["identity"]], "kind": kind} for r in rows
            ]
            await bulk_upsert(
                conn,
                entity_kinds_table,
                kind_rows,
                conflict_columns=["entity_id", "kind"],
                update_columns=[],
            )
```

The repository takes its engine as a **constructor argument**, never reaching for `get_engine()`
itself. That is what lets a test point it at a container without touching the environment.

The conflict column is excluded from `update_columns`: writing the key you matched on is a no-op at
best and, on a partial index, a way to make the statement fail.

`update_columns=[]` on the last write becomes `ON CONFLICT DO NOTHING` — the pair already existing is
not an error, just a no-op.

## Migration bootstrap — Alembic (once)

`packages/myschema/alembic/env.py` points `target_metadata` at the one shared `MetaData`, importing the
table package so every `Table` is registered on it first:

```python
import myschema.tables  # noqa: F401  — registers every Table on the shared metadata

from myschema.metadata import metadata

target_metadata = metadata
```

Every schema change — a new producer's raw/filtered pair, a registry column, or a view update — is one
Alembic revision generated from `packages/myschema/`, and `make migrate` at the workspace root is the
only way it is applied (`flat-monorepo` rule 4).

## Other bindings

- **The ORM (declarative mapping plus a session).** Mapped classes replace the table objects and the
  session's identity map replaces explicit statements; the raw/filtered split, the `identity` dedup
  key, the registry's atomicity guarantee, the one-transaction rule and the factory-built engine are
  all unchanged. What you give up is the thing the primary binding is chosen for: with Core the SQL
  that runs is the SQL in the file, so a bulk write's cost is readable at the call site and lazy
  loading cannot appear behind an attribute access. Rule 8 is where this bites — an ORM workspace
  writes the bulk path as the session's own bulk-insert API, never as mapped objects saved in a loop.
- **Another engine or driver.** Rules 1–14 hold; the conflict-resolution clause, the dialect-specific
  column types, the bind-parameter cap the chunk size is computed against and the read-back clause all
  change together. Conflict resolution is the one that is not mechanical: a backend without
  `ON CONFLICT` carries rule 10 as a `MERGE` or as a lock-and-check, and the "nothing to update" case
  must still become a no-op there rather than an error.

## Rules

1. **Constraint names are a contract, generated from one convention declared once.** A migration, an
   error-handling branch and a test must be able to name the same constraint without any of them
   inventing the name. Left to the backend, names differ by engine and change under an upsert, so
   nothing downstream can match on them.
2. **Raw is append-only, filtered is the queryable surface.** `*_raw` stores exactly what the producer
   fetched; `*_filtered` stores the typed, post-filter columns, keyed on the same `identity` the
   registry dedups on. Never skip straight to `*_filtered` — raw is what makes a bad filter run
   recoverable without re-fetching from upstream.
3. **`identity` is the dedup key everywhere it appears** — one normalized form used identically in
   every `*_filtered` table and in `entities`. Normalize in Python before the row reaches any
   bulk-write call, never inside SQL, so one function defines the form and one unit test pins it.
4. **The registry is written to, not just read from, whenever an identity can come from more than one
   producer.** This is the difference from a plain per-producer schema: `entities`/`entity_kinds` are
   physical tables with real unique constraints, not a view — a view cannot atomically answer "does
   this identity already exist" across concurrent producers.
5. **A write spanning more than one table goes through a repository class, not a bare function.** Use
   the bulk helpers directly for a single-table write; wrap them in a class the moment a later step
   needs a value an earlier one produced, or the write must be one transaction across tables. The
   class still carries no `Protocol` — it is one concrete implementation.
6. **One transaction spans the whole multi-table write.** The helpers take an already-open connection
   rather than owning a transaction each, so splitting the write across two connection blocks reopens
   exactly the partial-write race the repository class exists to close — and makes the write untestable
   inside a rolled-back transaction.
7. **Exactly one helper reads back the rows it wrote, and it does so as one multi-row statement per
   chunk.** A driver's batched-parameter path discards returned rows, so a read-back written any other
   way silently hands back nothing for most of the batch. Every other write returns nothing, and its
   caller does not ask.
8. **Bulk writes go through the helpers, never a per-row statement in a loop** — that is what keeps a
   ten-thousand-row batch to a handful of round trips instead of ten thousand.
9. **Chunk below the driver's bind-parameter limit, and keep the chunk size a named constant.** One
   statement binds chunk size × columns-per-row parameters, and a batch that crosses the driver's cap
   fails at execute time on size alone, whatever the data says. The number is computed once, from the
   widest table's column count and the driver's cap, and written where the helpers read it — not
   sprinkled as a literal at each call site.
10. **A conflicting row is resolved explicitly, and the key matched on is never among the columns
    updated.** The caller names the conflict columns and the update columns; writing back the key you
    matched on is a no-op at best and a statement failure on a partial index. "Nothing to update" is a
    real case — the registry's junction relies on it — and it must resolve to *do nothing*, not to an
    update with an empty assignment list, which is a syntax error.
11. **A producer's package never imports another producer's `*_filtered` table**, and never imports
    `entities`/`entity_kinds` directly — it goes through `EntitiesRepository.record_batch`, passing its
    own `filtered_table` and `kind`.
12. **Every primary key is a time-ordered UUID minted application-side by one function every table
    shares.** A random UUID scatters rows inserted together across the index for no benefit, and a
    database-side default means the writer cannot know the id it just created without reading it back.
    One producer's tables diverging onto a different scheme splits the schema's id policy in two.
13. **Engines, sessions and settings are reached through the `get_*` factories, and passed as
    arguments below the entrypoint.** Nothing in this package builds them at import time — an object
    constructed at module scope makes merely importing the package fail wherever the environment is
    incomplete — and nothing outside an entrypoint calls the factories.
14. **One environment prefix per settings class, named after the component that owns it and disjoint
    from every sibling's.** `MYSCHEMA_` here, a service's own stem in the service. The shared schema
    package and the services that depend on it are separate deployables reading one environment: share
    a prefix and one component's variable silently satisfies the other's field.

## Hard stops

- No identity in the data can plausibly be produced by more than one producer → stop, the registry and
  its repository class are unneeded; a per-producer `*_filtered` table plus a plain `UNION ALL` view is
  enough.
- A single-row insert path is being written for a batch known to exceed a few hundred rows → stop, use
  `bulk_upsert`/`bulk_upsert_returning`.
- A new primary key uses `uuid.uuid4()` or a Postgres-side default → stop, use
  `Column(..., default=uuid7)` from `uuid6`.
- A multi-table write is being split across two separate `engine.begin()` blocks → stop, that reopens
  the partial-write race the repository class exists to close; keep it inside one transaction.
- The shared `MetaData` is being declared inside a table module → stop, it belongs in `metadata.py`;
  hosting it in a table module makes that table the root of the import graph.
- A `MetaData` is created without the naming convention → stop, the constraint names are a contract
  shared by migrations, error handling and tests; backend-assigned names break all three.
- A module-level `engine = create_async_engine(...)` is being added → stop, use `get_engine()`; the
  bare object makes `import myschema.engine` fail wherever the environment is incomplete, and it is the
  object every test skill forbids importing.
