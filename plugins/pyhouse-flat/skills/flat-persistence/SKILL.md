---
name: flat-persistence
description: Use when a flat-layered service reads or writes a relational store — its table definitions, its bulk write helpers, and the class that owns a multi-statement write. Owns the constraint-naming convention, the single declared transaction owner per callable, driver-error translation into the service's catalogue with a mandatory fallback, the pure row-to-service-type mapping, chunked writes sized from the driver's bind-parameter cap, explicit conflict resolution, and application-minted time-ordered keys. A hexagonal service's repository adapter behind a port is `hex-persistence`, in the `pyhouse-hex` plugin; the workspace hosting a storage package several services share is `flat-monorepo`.
when_to_use: Also when asked for a bulk upsert, an `ON CONFLICT` clause, a chunk size, a storage or repository class in a flat service, a constraint naming convention, a migration for a flat service, or where a service's SQL is allowed to live.
paths: ["**/storage/**", "**/persistence/**", "**/alembic/**", "**/migrations/**"]
---

# Flat Persistence — one package owns the data access

The package a `flat-layered` service keeps its data access in — `storage/` in that skill's worked
example, whatever this service calls the role. It holds the table definitions, the write path, the
mapping from stored rows back to the service's own types, and the migration history. **No other package
in the service constructs a statement or opens a connection.**

The default subject is **one service with its own store**. Where several services share one store, the
same package is shared between them and one rule below says what that changes.

## When to use vs. neighbours

- The service's own role packages around this one — cross-cutting setup, clients, run functions →
  `flat-layered`, which owns the import contract this package sits inside and the no-`Protocol` rule
  this skill applies to the datastore.
- Several services sharing one repository, and where a shared storage package sits inside it →
  `flat-monorepo`.
- What triggers a run and hands this package its connection handle → `flat-entrypoint`.
- Testing these tables, helpers and the storage class against the real datastore →
  `flat-test-persistence`.
- The container, migration and isolation fixtures those tests run on → `flat-test-integration-setup`.
- The exception classes the translator produces, and what context they carry → `exception-catalog`.
- Module layout, `__all__`, and the `__init__.py` re-exports every table module needs →
  `python-packaging`.
- The declared type a row is mapped into before it leaves this package → `python-style` owns the rule
  that a record crossing a boundary is a declared type; `flat-layered` says which package declares it.
- The service enforces business invariants that must outlive a change of datastore → not this skill, and
  not this family: that is `hex-persistence`, in the `pyhouse-hex` plugin, where the repository sits
  behind a port. `architecture-choice` settles which family applies before either.

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
wants to reference another. **The naming convention is load-bearing**: it is what lets a migration, a
translator branch and a test refer to the same constraint by a name none of them invented. Left to the
backend, names differ by engine and change under an upsert.

For a `CheckConstraint`, `name=` is the **suffix** — the convention prepends `ck_<table>_`. Passing a
full name yields `ck_foos_ck_foos_name_non_empty`.

## Engine and write helpers — SQLAlchemy async, asyncpg

The engine is built by a **factory taking the connection string**, never as a module-level object: the
process definition reads settings once and hands the value down (`flat-layered` rules 7 and 8), and
`import myapp.storage.engine` must not fail in an environment that has set nothing.

`myapp/storage/engine.py` — two write primitives: a plain chunked bulk write, and a `RETURNING` variant
for when a later step needs the rows just written:

```python
from collections.abc import Iterable, Mapping, Sequence
from functools import lru_cache
from typing import Any

from sqlalchemy import Table
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

_CHUNK_SIZE = 2000  # see below: chunk_size * columns-per-row stays under the driver's bind limit


@lru_cache
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

The chunk size is a **named module constant, not a literal at the call site**, and the rule it encodes
is *chunk below the driver's bind-parameter limit*: one statement binds `chunk_size * columns-per-row`
parameters, and a batch crossing the driver's cap fails at execute time on size alone, whatever the data
says. `2000` is one project's worked value against its widest table; a project computes its own from
that table's column count and its driver's cap, and writes the answer here once.

An empty `update_columns` list must become `ON CONFLICT DO NOTHING`, not an `UPDATE` with an empty
`SET` — the latter is a syntax error, and "the row already exists and that is fine" is a real case.

## The table — SQLAlchemy Core on Postgres

Every primary key is a **UUIDv7**, minted client-side through the `uuid6` package's `uuid7()` — never
`uuid.uuid4()` and never a database-side `server_default`. UUIDv7 is time-ordered, so ids inserted
together sort and index together; `uuid.uuid4()`'s randomness scatters otherwise-related rows across a
b-tree index for no benefit, and a database-side default means the writer cannot know the id it just
created without reading it back. `uuid6.uuid7()` returns a `uuid.UUID` subclass, so it drops straight
into `Column(..., default=uuid7)`.

`myapp/storage/foo_table.py`:

```python
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    String,
    Table,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from uuid6 import uuid7

from myapp.storage.metadata import metadata

foo_table = Table(
    "foos",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid7),
    Column("reference", String, nullable=False, unique=True),  # the normalized natural key
    Column("name", String, nullable=False),
    Column("observed_at", DateTime(timezone=True), nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)

bar_table = Table(
    "bars",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid7),
    Column("foo_id", UUID(as_uuid=True), ForeignKey("foos.id"), nullable=False),
    Column("label", String(64), nullable=False),  # declared width — labels are short
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    UniqueConstraint("foo_id", "label"),
)
```

The declared width on `label` is a schema fact a test can read off the column to force a failure the
schema itself defines, rather than inventing a value that only happens to be rejected
(`flat-test-persistence`).

`storage/__init__.py` re-exports every table module and the metadata, so migration autogenerate sees the
whole schema from one import.

## The storage class — SQLAlchemy async (one declared transaction owner)

`myapp/storage/foo_storage.py` — a concrete class, no `Protocol` (rule 2). **Every public method opens
and owns its transaction**, which is this class's declared half of rule 3; the helpers it calls accept
the connection and never commit.

```python
from collections.abc import Sequence
from datetime import UTC

from sqlalchemy import select
from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine

from myapp.exceptions import FooAlreadyRecorded, FooNotFound, MyappError, StorageWriteRejected
from myapp.schemas.foo import Foo
from myapp.storage.engine import bulk_upsert, bulk_upsert_returning
from myapp.storage.foo_table import bar_table, foo_table


def normalize_reference(reference: str) -> str:
    """The one normalized form of the natural key, used on the way in and on the way out."""
    return reference.strip().lower()


def _to_row(foo: Foo) -> dict[str, object]:
    return {
        "reference": normalize_reference(foo.reference),
        "name": foo.name,
        "observed_at": foo.observed_at,
    }


def _to_foo(rows: Sequence[RowMapping]) -> Foo:
    head = rows[0]
    observed_at = head["observed_at"]
    return Foo(
        id=head["id"],
        reference=normalize_reference(head["reference"]),
        name=head["name"],
        observed_at=observed_at if observed_at.tzinfo else observed_at.replace(tzinfo=UTC),
        labels=tuple(sorted(row["label"] for row in rows if row["label"] is not None)),
    )


def _translate(exc: DBAPIError) -> MyappError:
    constraint = getattr(exc.orig, "constraint_name", None) or str(exc.orig)
    if "uq_foos_reference" in constraint:
        return FooAlreadyRecorded(
            "a foo with this reference is already recorded",
            context={"field": "reference", "constraint": "uq_foos_reference"},
        )
    return StorageWriteRejected(
        "the datastore rejected the write", context={"constraint": constraint}
    )


class FooStorage:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def record_batch(self, foos: Sequence[Foo]) -> None:
        """Owns the transaction: the foos and their labels land together or not at all."""
        if not foos:
            return
        async with self._engine.begin() as conn:
            try:
                written = await bulk_upsert_returning(
                    conn,
                    foo_table,
                    [_to_row(foo) for foo in foos],
                    conflict_columns=["reference"],
                    update_columns=["name", "observed_at"],
                    returning_columns=["id", "reference"],
                )
                foo_id_by_reference = {row["reference"]: row["id"] for row in written}
                await bulk_upsert(
                    conn,
                    bar_table,
                    [
                        {
                            "foo_id": foo_id_by_reference[normalize_reference(foo.reference)],
                            "label": label,
                        }
                        for foo in foos
                        for label in foo.labels
                    ],
                    conflict_columns=["foo_id", "label"],
                    update_columns=[],
                )
            except DBAPIError as exc:
                raise _translate(exc) from exc

    async def get_by_reference(self, reference: str) -> Foo:
        async with self._engine.connect() as conn:
            result = await conn.execute(
                select(foo_table, bar_table.c.label)
                .join(bar_table, bar_table.c.foo_id == foo_table.c.id, isouter=True)
                .where(foo_table.c.reference == normalize_reference(reference))
            )
            rows = result.mappings().all()
        if not rows:
            raise FooNotFound("no foo with this reference", context={"reference": reference})
        return _to_foo(rows)
```

The class takes its engine as a **constructor argument**, never reaching for the factory itself — that is
what lets a test point it at a container without touching the environment.

`record_batch` is the worked case of rule 4: the second write needs an id the first one produced, so the
two statements sit inside **one** `engine.begin()`. Split across two connection blocks, a failure in the
second leaves parentless rows behind, and the whole class stops being worth having.

`update_columns=[]` on the second write resolves to *do nothing*: a label already recorded for that foo is
not an error, and an update with an empty assignment list is a syntax error.

`_translate` **ends by returning a catalogue exception**: the last statement is the fallback, not a
re-raise of the driver's type. Without it an unrecognised constraint escapes as a driver exception and
every caller's `except` clause is written against a library it was supposed never to import.

`_to_foo` is a **pure function**: no IO, no logging. It normalizes what the driver hands back — the
natural key's one form, and a naive timestamp's offset — so a single unit test pins both for the whole
service, and nothing above this package ever sees a column name.

The conflict column is excluded from `update_columns`: writing back the key you matched on is a no-op at
best and, on a partial index, a way to make the statement fail.

## Migration bootstrap — Alembic (once)

`myapp/alembic/env.py` points `target_metadata` at the one `MetaData`, importing the storage package so
every `Table` is registered on it first:

```python
import myapp.storage  # noqa: F401  — registers every Table on the shared metadata

from myapp.storage.metadata import metadata

target_metadata = metadata
```

Every schema change is one revision generated from where the schema is defined, and one command applies
it, run from that same place.

## Other bindings

- **The ORM (declarative mapping plus a session).** Mapped classes replace the table objects and the
  session replaces the connection; the declared transaction owner, the driver-error translation with its
  mandatory fallback, the row mapping, the constraint-name contract and the factory-built engine are all
  unchanged. What you give up is the thing the primary binding is chosen for: with Core the SQL that runs
  is the SQL in the file, so a bulk write's cost is readable at the call site and lazy loading cannot
  appear behind an attribute access. Rule 9 is where this bites — an ORM project writes the bulk path as
  the session's own bulk-insert API, never as mapped objects saved in a loop.
- **Another engine or driver.** Every rule holds; the conflict-resolution clause, the dialect-specific
  column types, the bind-parameter cap the chunk size is computed against, the driver exception the
  translator matches on and the read-back clause all change together. Conflict resolution is the one that
  is not mechanical: a backend without `ON CONFLICT` carries rule 12 as a `MERGE` or as a lock-and-check,
  and "nothing to update" must still become a no-op there rather than an error.
- **This package as a separate distribution, shared by several services.** The templates are unchanged;
  what changes is that it becomes its own component — its own settings class with its own environment
  prefix disjoint from every service's (`flat-layered` rule 8 owns the prefix rule), its own migration
  command run from its own directory, and a standing restriction that the services importing it define no
  table of their own (`flat-monorepo`).

## Rules

1. **One package owns a service's data access, and nothing outside it constructs a statement or opens a
   connection.** A service's SQL is findable in one place or it is everywhere. This is the positive form
   of `flat-layered` rule 4.
2. **No `Protocol` over the datastore, and that is a decision rather than an omission.** The main
   datastore is a sticky dependency with no nameable alternative the business would plausibly adopt, so
   it never qualifies for an interface however generic it looks (`flat-layered` rule 5). Test doubles come
   from the real backend or from subclassing the concrete class (`test-principles`).
3. **Transaction ownership is one declared decision per callable.** A callable either *accepts* a live
   connection and never commits, or *opens and owns* one for the whole of its work. The two forms are
   mutually exclusive for one callable, and no connection is held in instance state between calls. Which
   form a callable takes is part of its contract: it decides how a caller composes it and which isolation
   fixture its test needs (`flat-test-integration-setup`).
4. **A write spanning more than one statement is one transaction, owned by the callable that spans
   them.** Splitting it across two connection blocks reopens the partial-write race the owning callable
   exists to close, and makes the write untestable inside a rolled-back transaction.
5. **Every driver error is translated before it escapes this package, and the fallback is mandatory.**
   The translator ends by returning a catalogue exception when no case matched; it never returns or
   re-raises the driver's own type. Letting one leak means every caller's `except` clause is written
   against a library it was supposed never to import. The catalogue and its shape are `exception-catalog`'s.
6. **Pick the most specific catalogue exception and give it identifying context** — the offending field
   and the full constraint name. The caller and the tests both assert on them, and a generic failure
   turns a recoverable conflict into an outage.
7. **Rows cross this package's boundary as the service's own declared types, and the mapping is a pure
   function this package owns.** No IO, no logging. It normalizes what the driver hands back, including
   giving a naive timestamp its offset, and it is where a natural key is normalized once so one unit test
   can pin the form. Normalize in Python, never inside SQL. The declared-type obligation itself is
   `python-style`'s.
8. **Constraint names are a contract, generated from one convention declared once.** A migration, a
   translator branch and a test must be able to name the same constraint without any of them inventing
   it. This rule and rule 5 are paired: the translator can only match on a name the convention makes
   predictable.
9. **Bulk writes go through one helper, never a per-row statement in a loop** — that is what keeps a
   ten-thousand-row batch to a handful of round trips instead of ten thousand.
10. **Chunk below the driver's bind-parameter limit, and hold the chunk size as a named constant.** One
    statement binds chunk size × columns-per-row parameters, and a batch that crosses the cap fails at
    execute time on size alone, whatever the data says. The number is computed once, from the widest
    table's column count and the driver's cap, and written where the helpers read it — never sprinkled as
    a literal at each call site.
11. **Exactly one helper reads back the rows it wrote, and it does so as one multi-row statement per
    chunk.** A driver's batched-parameter path discards returned rows, so a read-back written any other
    way silently hands back nothing for most of the batch. Every other write returns nothing, and its
    caller does not ask.
12. **A conflicting row is resolved explicitly, the key matched on is never among the columns updated,
    and an empty update set resolves to *do nothing*.** The caller names the conflict columns and the
    update columns; writing back the key you matched on is a no-op at best and a statement failure on a
    partial index. "Nothing to update" is a real case and must not become an update with an empty
    assignment list, which is a syntax error.
13. **Every key is a time-ordered identifier minted application-side by one function every table
    shares.** A random identifier scatters rows inserted together across the index for no benefit, and a
    database-side default means the writer cannot know the id it just created without reading it back.
    One table diverging onto a different scheme splits the schema's id policy in two.
14. **Engines, sessions and connection settings are reached through factories and passed as arguments
    below the process definition.** Nothing here builds them at import time — an object constructed at
    module scope makes merely importing the package fail wherever the environment is incomplete — and
    nothing in this package reads settings itself.
15. **Where several services share a store, exactly one package owns its schema and its migration
    history, and every other service depends on that package.** Two packages defining tables in one
    database means two migration histories over one schema, and the second one to run decides what the
    first one's tables look like.

## Hard stops

- A statement is being built or a connection opened outside this package → stop, the call belongs behind
  a method here; that is what makes the service's SQL findable and its writes testable.
- One callable both accepts a connection and opens its own → stop, pick one; a caller cannot compose it
  and a test cannot isolate it.
- A multi-statement write is being split across two separate transactions → stop, that reopens the
  partial-write race; keep it inside one.
- A driver exception is allowed to escape this package, or the translator ends by re-raising it → stop,
  the fallback is mandatory: return a catalogue exception when no case matched.
- A row leaves this package as a bare mapping → stop, map it to the service's declared type here; the
  mapping is this package's, and nothing above it should learn column names.
- A single-row insert path is being written for a batch known to exceed a few hundred rows → stop, use
  the bulk helper.
- A new primary key uses a random UUID or a database-side default → stop, mint a time-ordered identifier
  application-side.
- The `MetaData` is being declared inside a table module → stop, it belongs in its own module; hosting it
  in a table module makes that table the root of the import graph.
- A `MetaData` is created without the naming convention → stop, the constraint names are a contract
  shared by migrations, error handling and tests; backend-assigned names break all three.
- A module-level `engine = create_async_engine(...)` is being added → stop, use the factory; the bare
  object makes importing the module fail wherever the environment is incomplete, and it is the object
  every test skill forbids importing.
- The service has business invariants that must outlive a change of datastore → stop, this family is the
  wrong one; `architecture-choice` decides, and the repository goes behind a port (`hex-persistence`, in
  the `pyhouse-hex` plugin).
