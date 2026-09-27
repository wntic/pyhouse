---
name: flat-test-persistence
description: Use when testing a flat-layered service's data-access package against the real datastore — its tables and the repository class that owns its transactions — pinning the declared update set from both sides, the generated constraint name where the translator branches on it, an empty update set resolving to a no-op where a write declares one, a crossed chunk boundary where a write chunks, the catalogue exception a driver error is translated into on a write and, where the class has one, on a read, a cursor page edge splitting rows that share one timestamp where a run pages, two inputs with one key where a method takes a batch, and, where one write spans statements, its atomicity. Consumes the container and isolation fixtures rather than laying them (`flat-test-integration-setup`). Not the run function that calls this write path, which is `flat-test-run-function`, and not a hexagonal `IFooRepository` adapter, which is `hex-test-repository-contract`, in the `pyhouse-hex` plugin.
---

# Flat Test — Data-Access Contract

Consult `test-principles` for the testing constitution. Where this skill contradicts `test-principles`,
the constitution wins.

One integration-test file per repository class, under the distribution's own `tests/integration/`,
driven against the **real** datastore from `flat-test-integration-setup`. This is the only level that
can catch what the data-access package exists to guarantee: that a batch write is a handful of round
trips, that a conflict updates the columns it claims to, and that a driver error arrives as the service's
own exception.

Where several distributions share one data-access library, the files sit with that library's own tests
instead — `myschema/tests/integration/` — and nothing else changes.

**Which isolation fixture applies follows from the declared transaction owner** (`flat-persistence`
rule 3), never from a guess:

- Every assertion query, and any callable that **accepts** a connection → the **`conn`** fixture.
  Rolled back, nothing reaches disk.
- The callable under test **opens and owns** its transaction — a repository class → pass the **`engine`**
  fixture to its constructor and let `truncate_all` clean up. Assertions read through `conn`, **except
  where the subject's own rollback is what is under test**: there the assertion opens a fresh connection,
  because `conn` sits in a transaction of its own and cannot observe another connection's rollback.

## When to use vs. neighbours

- A pure function in the data-access package — a connection-string builder, the row mapper → not this
  skill; it is a unit test with no fixtures at all.
- The container, migration and isolation fixtures themselves → `flat-test-integration-setup`; this skill
  consumes `conn`, `engine` and `truncate_all` and lays none of its own.
- Writing the tables, repository class and migrations under test → `flat-persistence`.
- A run function calling this write path as part of a run → `flat-test-run-function`; this skill tests
  the write path, that one tests the wiring above it.
- The client feeding these rows → `flat-test-service-client`.
- A static "no package outside the data-access package constructs a statement" rule →
  `test-architecture-rule`.
- The shared groundwork — fixture placement, assertion strength, reliability → `test-principles`.
- The adapter sits behind a domain repository protocol → `hex-test-repository-contract`, in the
  `pyhouse-hex` plugin.

## Template — the repository class's contract (pytest, SQLAlchemy async over Postgres)

`tests/integration/test_foo_repository.py`:

```python
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from myapp.exceptions import StorageWriteRejectedError
from myapp.postgres import FooRepository
from myapp.postgres.foo_table import foo_table
from myapp.schemas import Foo, FooReference


def _a_foo(reference: str = "alpha", name: str = "first") -> Foo:
    return Foo(reference=FooReference(reference), name=name, observed_at=datetime(2024, 1, 1, tzinfo=UTC))


async def test_a_second_write_of_one_reference_updates_the_set_and_keeps_the_rest(
    engine: AsyncEngine,
    conn: AsyncConnection,
) -> None:
    repository = FooRepository(engine)
    await repository.record_batch([_a_foo(name="first")])
    first_id = (await conn.execute(select(foo_table.c.id))).scalar_one()

    await repository.record_batch([_a_foo(name="second")])

    rows = (await conn.execute(select(foo_table.c.id, foo_table.c.name))).all()
    assert [tuple(row) for row in rows] == [(first_id, "second")]


# only where a method takes a batch
async def test_a_batch_crossing_chunk_boundaries_lands_every_foo(engine: AsyncEngine, conn: AsyncConnection) -> None:
    await FooRepository(engine, chunk_size=2).record_batch([_a_foo(f"ref-{i}") for i in range(5)])

    count = (await conn.execute(select(func.count()).select_from(foo_table))).scalar_one()
    assert count == 5


# only where a method takes a batch
async def test_two_foos_sharing_a_key_in_one_batch_land_once_as_the_later(
    engine: AsyncEngine,
    conn: AsyncConnection,
) -> None:
    await FooRepository(engine).record_batch([_a_foo(name="first"), _a_foo(name="second")])

    names = (await conn.execute(select(foo_table.c.name))).scalars().all()
    assert names == ["second"]


async def test_a_value_the_store_refuses_arrives_as_the_catalogue_error(engine: AsyncEngine) -> None:
    with pytest.raises(StorageWriteRejectedError) as exc_info:
        await FooRepository(engine).record_batch([_a_foo(name="nul\x00")])

    assert exc_info.value.context == {"sqlstate": "22021", "constraint": None}
```

The tests drive the class a caller uses and assert through `conn`, a query against the store.

The first test pins the declared update set from both sides in one comparison: one row, not two; the
name the set covers changed; the id it does not cover kept the value the first write minted. Where the
translator branches on a constraint's name, a test pins that name on a plain insert and one exercises
the conflict clause against the same constraint (rules 2 and 3).

Where a write chunks, the chunk-boundary test constructs the class with `chunk_size=2` against five foos
deliberately: it crosses the boundary three times with an uneven last chunk, which is where an off-by-one
in the slice shows up. Proving the same thing at the production chunk size would need thousands of rows
on every run.

Where a method takes a batch, the in-batch duplicate test hands one call two foos with one reference. One
statement touching one row twice is refused by Postgres (SQLSTATE `21000`), and the translator would
report it as the store being unavailable; one row carrying the later foo's name is what collapsing the
batch by its key first guarantees (`flat-persistence` rule 18).

The translation test forces the write through the public method a caller uses, refused by the store
itself — a NUL character, which a Postgres text value cannot hold, is SQLSTATE `22021` in the
data-exception class — so no constraint had to be invented for the test. Where the class has a read,
one test forces that read to fail, and the error it raises is the catalogue's.

Where a write resolves a conflict by doing nothing, the file gains the no-op test of rule 5. Where a
write spans statements, it gains the atomicity test of rule 11 — its last statement forced to fail
through a constraint the schema declares, and the absence of the earlier statements' rows asserted
through a **fresh connection**, never through `conn`, which holds an open transaction of its own and
could not observe another connection's rollback either way.

## Other bindings

- **The ORM in place of Core.** Mapped classes replace the table objects and the session replaces the
  connection; every rule below is unchanged, because each pins a property of the stored data rather than
  of the statement that wrote it. Assertions still read the store back (rule 1) — through a fresh query,
  not through the session's identity map, which can hand back the object just written without it ever
  having reached the datastore.
- **Another engine or dialect.** The upsert spelling, the generated constraint names and the driver
  errors a violation raises change together; the contract questions — idempotence, the update set from
  both sides, the chunk boundary, the translated exception — do not. Where the dialect has no
  single-statement upsert, the repository's *contract* is still the subject and the test pins whatever
  its write does instead.
- **How the datastore is provisioned** — a disposable container, a pre-provisioned throwaway database, an
  in-process engine. That choice belongs to `flat-test-integration-setup`, which names its trade-offs;
  nothing in these files changes with it except that an in-process engine of a different dialect
  invalidates rules 2 and 3.

## Rules

1. **Assert through a query against the store, never through the write's return value alone.** A bulk
   write returns nothing, and where a write reads keys back its return value is what the statement
   said, which is the thing under test. What the datastore holds afterwards is the fact.
2. **Where the translator branches on a constraint's name, pin that name, not just the exception
   type.** The name comes from the metadata naming convention, and asserting it catches a migration that
   dropped the intended index.
3. **A unique constraint the translator branches on is tested on the plain insert *and* on the
   conflict-resolution path.** A partial or expression index can be honoured by an insert and silently
   not matched by the conflict clause; only exercising both paths separates those two outcomes.
4. **Test the declared update set from both sides.** The second write must change what the set names
   *and* leave every column outside it alone — that is the whole contract of an upsert, and both are
   pinned, whether in one comparison or two.
5. **An empty update set means "do nothing on conflict".** Where a write declares one, test it as a
   no-op that raises nothing and changes nothing; a write that meets a key already recorded and must
   leave it alone relies on exactly that.
6. **Where a write chunks, cross a chunk boundary with a deliberately small chunk size and an uneven
   last chunk**, never with production-sized input. Five rows at a chunk size of two crosses it three times; proving the same
   thing at the production size costs thousands of rows on every run.
7. **A test that forces a driver error asserts the catalogue exception the data-access package produces,
   not the driver's own type.** Translation is mandatory, so the driver's class is precisely what must
   never escape — a test expecting it pins the defect instead of the contract. Where the class has a
   read, it is forced to fail once too: a translation written only around the writes leaves every read
   leaking the driver's type, and no write test notices. The failure is forced through something the store itself refuses, never
   through a value that only happens to be rejected today.
8. **A timestamp the store assigns is asserted as `test-principles` reliability rule 5 states**; under the
   rollback-scoped `conn` every write shares one transaction, and so one fixed clock.
9. **A repository-class test constructs the class with the `engine` fixture**, never with the production
   engine factory — that builds a second pool the suite never disposes (`flat-test-integration-setup`).
10. **Ordering is asserted only where the query guarantees it.** Add an explicit order clause to any
    query whose result is compared to a list; a relational store promises no insertion order, and a test
    that passes on two rows fails on two hundred.
11. **Where one write spans statements, it has an atomicity test** that forces its last statement to fail
    through a constraint the schema declares, expects the narrowest catalogue exception that constraint
    produces, and asserts through a fresh connection that the earlier statements left nothing behind.
12. **Where a run walks a table in pages, a test crosses a page edge where the ordering column ties.**
13. **Where a method takes a batch, it is tested with two inputs that share one key, in one call.** The store may refuse to
    resolve one row twice in a statement; assert one row holding the later input's values.

## Hard stops

- A repository-class test asserts a rollback through the `conn` fixture → stop, `conn` sits in its own
  transaction and cannot observe another connection's rollback; open a fresh connection for that
  assertion.
- A write spanning statements has only happy-path tests → stop, add the failing-last-statement test
  (rule 11); without it a refactor splitting the statements into two transactions passes every test.
- A test forcing a driver error expects the driver's own exception class → stop, expect the translated
  catalogue class (rule 7).
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
- A builder returns a mapping of column values → stop, build the service's declared type and write it
  through the repository class (`python-style`).
