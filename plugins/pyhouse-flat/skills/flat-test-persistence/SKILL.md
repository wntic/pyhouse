---
name: flat-test-persistence
description: Use when testing a flat-layered service's data-access package against the real datastore — its tables, its bulk write helper and the repository class that owns its transactions — pinning the generated constraint name rather than only the exception type, the declared update set from both sides, an empty update set resolving to a no-op, a deliberately crossed chunk boundary, the catalogue exception a driver error is translated into on a write and, where the class has one, on a read, a cursor page edge splitting rows that share one timestamp where a run pages, a batch holding two inputs with one key, and, where one write spans statements, its atomicity. Consumes the container and isolation fixtures rather than laying them (`flat-test-integration-setup`). Not the run function that calls this write path, which is `flat-test-run-function`, and not a hexagonal `IFooRepository` adapter, which is `hex-test-repository-contract`, in the `pyhouse-hex` plugin.
---

# Flat Test — Data-Access Contract

Consult `test-principles` for the testing constitution. Where this skill contradicts `test-principles`,
the constitution wins.

One integration-test file per table or per repository class, under the distribution's own
`tests/integration/`, driven against the **real** datastore from `flat-test-integration-setup`. This is
the only level that can catch what the data-access package exists to guarantee: that a batch write is a
handful of round trips, that a conflict updates the columns it claims to, and that a driver error
arrives as the service's own exception.

Where several distributions share one data-access library, the files sit with that library's own tests
instead — `myschema/tests/integration/` — and nothing else changes.

**Which isolation fixture applies follows from the declared transaction owner** (`flat-persistence`
rule 3), never from a guess:

- The callable under test **accepts** a connection — the bulk helper, and every assertion query → use
  the **`conn`** fixture and pass it in. Rolled back, nothing reaches disk.
- The callable under test **opens and owns** its transaction — a repository class → pass the **`engine`**
  fixture to its constructor and let `truncate_all` clean up. Assertions read through `conn`, **except
  where the subject's own rollback is what is under test**: there the assertion opens a fresh connection,
  because `conn` sits in a transaction of its own and cannot observe another connection's rollback.

## When to use vs. neighbours

- A pure function in the data-access package — a connection-string builder, the row mapper → not this
  skill; it is a unit test with no fixtures at all.
- The container, migration and isolation fixtures themselves → `flat-test-integration-setup`; this skill
  consumes `conn`, `engine` and `truncate_all` and lays none of its own.
- Writing the tables, helpers, repository class and migrations under test → `flat-persistence`.
- A run function calling this write path as part of a run → `flat-test-run-function`; this skill tests
  the write path, that one tests the wiring above it.
- The client feeding these rows → `flat-test-service-client`.
- A static "no package outside the data-access package constructs a statement" rule →
  `test-architecture-rule`.
- The shared groundwork — fixture placement, assertion strength, reliability → `test-principles`.
- The adapter sits behind a domain repository protocol → `hex-test-repository-contract`, in the
  `pyhouse-hex` plugin.

## Template — one table's contract (pytest, SQLAlchemy Core over Postgres)

`tests/integration/test_foo_table.py` — only for a table the service writes:

```python
from collections.abc import Sequence
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from myapp.postgres import bulk_upsert
from myapp.postgres.foo_table import foo_table


def _foo(reference: str = "alpha", **overrides: object) -> dict[str, object]:
    return {
        "reference": reference,
        "name": "first",
        "observed_at": datetime(2024, 1, 1, tzinfo=UTC),
        **overrides,
    }


async def test_a_second_write_of_one_reference_updates_rather_than_duplicates(
    conn: AsyncConnection,
) -> None:
    await bulk_upsert(conn, foo_table, [_foo()], conflict_columns=["reference"], update_columns=["name"])

    await bulk_upsert(
        conn,
        foo_table,
        [_foo(name="second")],
        conflict_columns=["reference"],
        update_columns=["name"],
    )

    names: Sequence[str] = (await conn.execute(select(foo_table.c.name))).scalars().all()
    assert names == ["second"]


async def test_a_second_write_leaves_columns_outside_the_update_set_alone(
    conn: AsyncConnection,
) -> None:
    await bulk_upsert(conn, foo_table, [_foo()], conflict_columns=["reference"], update_columns=["name"])

    await bulk_upsert(
        conn,
        foo_table,
        [_foo(observed_at=datetime(2024, 1, 2, tzinfo=UTC))],
        conflict_columns=["reference"],
        update_columns=["name"],
    )

    observed_at: datetime = (await conn.execute(select(foo_table.c.observed_at))).scalar_one()
    assert observed_at == datetime(2024, 1, 1, tzinfo=UTC)


async def test_the_reference_is_unique_on_a_plain_insert(conn: AsyncConnection) -> None:
    await conn.execute(foo_table.insert().values(**_foo()))

    with pytest.raises(IntegrityError) as exc_info:
        await conn.execute(foo_table.insert().values(**_foo()))

    assert "uq_foos_reference" in str(exc_info.value.orig)


async def test_an_empty_update_set_is_a_no_op_rather_than_an_error(
    conn: AsyncConnection,
) -> None:
    await bulk_upsert(conn, foo_table, [_foo()], conflict_columns=["reference"], update_columns=[])

    await bulk_upsert(conn, foo_table, [_foo(name="second")], conflict_columns=["reference"], update_columns=[])

    names: Sequence[str] = (await conn.execute(select(foo_table.c.name))).scalars().all()
    assert names == ["first"]


async def test_a_write_crossing_chunk_boundaries_lands_every_row(
    conn: AsyncConnection,
) -> None:
    rows = [_foo(reference=f"ref-{i}") for i in range(5)]

    await bulk_upsert(
        conn,
        foo_table,
        rows,
        conflict_columns=["reference"],
        update_columns=["name"],
        chunk_size=2,
    )

    count = (await conn.execute(select(func.count()).select_from(foo_table))).scalar_one()
    assert count == 5


async def test_empty_input_is_a_no_op(conn: AsyncConnection) -> None:
    await bulk_upsert(conn, foo_table, [], conflict_columns=["reference"], update_columns=["name"])

    count = (await conn.execute(select(func.count()).select_from(foo_table))).scalar_one()
    assert count == 0
```

The unique constraint appears twice: `uq_foos_reference` on a plain insert, and under the upserts that
resolve against it — with an update set and with an empty one (rule 3). The name asserted is the one the
metadata's naming convention generates (`flat-persistence`). Asserting the **name** rather than only the
exception type is what catches a migration that dropped the intended unique index and let some other
constraint fire instead.

The chunk-boundary test uses `chunk_size=2` against five rows deliberately: it crosses the boundary three
times with an uneven last chunk, which is where an off-by-one in the slice shows up. Proving the same
thing at the production chunk size would need thousands of rows on every run.

**The row builder returns a mapping, not a declared type, and that is deliberate.** `bulk_upsert` is
parameterised by the `Table`, so at *that* boundary the keys are data — the same helper takes every
table's columns, and there is no fixed set of named fields for a type to declare. What still binds is the
annotation: `dict[str, object]`, never a bare `dict`, because the test surface is type-checked at parity
with source (`python-style`). A builder that constructs the service's **own** type — a `Foo` handed to
the repository class — returns that type, not a mapping.

## Template — the repository class's contract (pytest, SQLAlchemy async over Postgres)

`tests/integration/test_foo_repository.py`:

```python
from collections.abc import Sequence
from datetime import UTC, datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from myapp.exceptions import StorageWriteRejectedError
from myapp.postgres import FooRepository
from myapp.postgres.foo_table import foo_table
from myapp.schemas import Foo, FooReference


def _a_foo(reference: str = "alpha", name: str = "first") -> Foo:
    return Foo(reference=FooReference(reference), name=name, observed_at=datetime(2024, 1, 1, tzinfo=UTC))


async def test_two_foos_sharing_a_key_in_one_batch_land_once_as_the_later(
    engine: AsyncEngine,
    conn: AsyncConnection,
) -> None:
    await FooRepository(engine).record_batch([_a_foo(name="first"), _a_foo(name="second")])

    names: Sequence[str] = (await conn.execute(select(foo_table.c.name))).scalars().all()
    assert names == ["second"]


async def test_a_value_the_store_refuses_arrives_as_the_catalogue_error(engine: AsyncEngine) -> None:
    with pytest.raises(StorageWriteRejectedError) as exc_info:
        await FooRepository(engine).record_batch([_a_foo(name="nul\x00")])

    assert exc_info.value.context == {"sqlstate": "22021", "constraint": None}
```

The in-batch duplicate test hands one call two foos with one reference. One statement touching one row
twice is refused by Postgres (SQLSTATE `21000`), and the translator would report it as the store being
unavailable; one row carrying the later foo's name is what collapsing the batch by its key first
guarantees (`flat-persistence` rule 18).

The translation test forces the write through the public method a caller uses, refused by the store
itself — a NUL character, which a Postgres text value cannot hold, is SQLSTATE `22021` in the
data-exception class — so no constraint had to be invented for the test. Where the class has a read,
one test forces that read to fail, and the error it raises is the catalogue's.

The expected error is the **catalogue exception the data-access package produces**, not the driver's own
type: translation is mandatory (`flat-persistence` rule 5), so a test expecting the driver's class would
be asserting the one thing the package promises never to let out. And never a bare `Exception`, which is
satisfied by an import error, a typo in a table name or a dropped connection.

Where a write spans statements, the file gains the atomicity test of rule 11 — its last statement forced
to fail through a constraint the schema declares, and the absence of the earlier statements' rows
asserted through a **fresh connection**, never through `conn`, which holds an open transaction of its
own and could not observe another connection's rollback either way.

## Other bindings

- **The ORM in place of Core.** Mapped classes replace the table objects and the session replaces the
  connection; every rule below is unchanged, because each pins a property of the stored data rather than
  of the statement that wrote it. Assertions still read the store back (rule 1) — through a fresh query,
  not through the session's identity map, which can hand back the object just written without it ever
  having reached the datastore.
- **Another engine or dialect.** The upsert spelling, the generated constraint names and the driver
  errors a violation raises change together; the contract questions — idempotence, the update set from
  both sides, the chunk boundary, the translated exception — do not. Where the dialect has no
  single-statement upsert, the helper's *contract* is still the subject and the test pins whatever the
  helper does instead.
- **How the datastore is provisioned** — a disposable container, a pre-provisioned throwaway database, an
  in-process engine. That choice belongs to `flat-test-integration-setup`, which names its trade-offs;
  nothing in these files changes with it except that an in-process engine of a different dialect
  invalidates rules 2 and 3.

## Rules

1. **Assert through a query against the store, never through the helper's return value alone.** A bulk
   write returns nothing, and where a read-back helper exists its return value is what the statement
   said, which is the thing under test. What the datastore holds afterwards is the fact.
2. **Pin the constraint name, not just the exception type.** The name comes from the metadata naming
   convention, and asserting it catches a migration that dropped the intended index.
3. **Every unique constraint is tested on the plain insert *and* on the conflict-resolution path.** A
   partial or expression index can be honoured by an insert and silently not matched by the conflict
   clause; only exercising both paths separates those two outcomes.
4. **Test the declared update set from both sides.** The second write must change what the set names
   *and* leave every column outside it alone — that is the whole contract of an upsert, and it is two
   assertions, not one.
5. **An empty update set means "do nothing on conflict".** Test it as a no-op that raises nothing and
   changes nothing; a write that meets a key already recorded and must leave it alone relies on exactly
   that.
6. **Cross a chunk boundary with a deliberately small chunk size and an uneven last chunk**, never with
   production-sized input. Five rows at a chunk size of two crosses it three times; proving the same
   thing at the production size costs thousands of rows on every run.
7. **A test that forces a driver error asserts the catalogue exception the data-access package produces,
   not the driver's own type.** Translation is mandatory, so the driver's class is precisely what must
   never escape — a test expecting it pins the defect instead of the contract. Where the class has a
   read, it is forced to fail once too: a translation written only around the writes leaves every read
   leaking the driver's type, and no write test notices. The failure is forced through something the store itself refuses, never
   through a value that only happens to be rejected today.
8. **A timestamp the store assigns is asserted as `test-principles`' reliability rules state**, never
   by equality and never with a strict inequality; under the rollback-scoped `conn` every write shares
   one transaction, and so one transaction-fixed clock.
9. **A repository-class test constructs the class with the `engine` fixture**, never with the production
   engine factory — that builds a second pool the suite never disposes (`flat-test-integration-setup`).
10. **Ordering is asserted only where the query guarantees it.** Add an explicit order clause to any
    query whose result is compared to a list; a relational store promises no insertion order, and a test
    that passes on two rows fails on two hundred.
11. **Where one write spans statements, it has an atomicity test** that forces its last statement to fail
    through a constraint the schema declares, expects the narrowest catalogue exception that constraint
    produces, and asserts through a fresh connection that the earlier statements left nothing behind.
12. **Where a run walks a table in pages, a test crosses a page edge where the ordering column ties.**
13. **A batch write is tested with two inputs that share one key, in one call.** The store may refuse to
    resolve one row twice in a statement; assert one row holding the later input's values.

## Hard stops

- A repository-class test asserts a rollback through the `conn` fixture → stop, `conn` sits in its own
  transaction and cannot observe another connection's rollback; open a fresh connection for that
  assertion.
- A write spanning statements has only happy-path tests → stop, add the failing-last-statement test
  (rule 11); without it a refactor splitting the statements into two transactions passes every test.
- A test forcing a driver error expects a bare `Exception`, or the driver's own exception class → stop;
  name the catalogue exception the translator produces, or the test pins nothing the package promises.
- The constraint under test does not exist in a migration yet → stop, add the revision first; a test
  asserting a constraint the schema never had passes for the wrong reason.
- A test asserts on rows written by a *different* test → stop, isolation wipes everything between tests;
  construct the rows this test needs.
- A test reaches for a mock to avoid starting the container → stop, this whole level exists because the
  real backend is the only thing that can answer these questions.
- A test writes raw SQL to set up state a `Table` object could express → stop, use the `Table`;
  hand-written SQL in a test drifts from the schema silently.
- A read resumed from a cursor has no test whose page edge falls inside rows sharing the ordering value
  → stop, write one; a cursor missing its tiebreaker passes every other test (rule 12).
- A batch write has no test handing it two inputs with one key → stop, write one; the failure only
  appears when a real batch repeats a key (rule 13).
- A row builder is annotated with a bare `-> dict` → stop, give it its type parameters; the test surface
  is type-checked at parity with source (`python-style`).
