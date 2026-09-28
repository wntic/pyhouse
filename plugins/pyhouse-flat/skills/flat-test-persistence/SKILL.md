---
name: flat-test-persistence
description: Use when testing a flat-layered service's data-access package against the real datastore — its tables and the repository class that owns its transactions — pinning the generated constraint name where the translator branches on it, the catalogue exception a driver error is translated into on each write and read the class has, and each write's conditional contract where it has one — an upsert's update set from both sides, an ordering-stamp guard from both directions, an empty update set, a chunk boundary, two inputs with one key in a batch, a paged read's tied edge, a multi-statement write's atomicity. Consumes the container and isolation fixtures rather than laying them (`flat-test-integration-setup`). Not the function a trigger calls that reaches this write path, which is `flat-test-run-function`, and not a hexagonal `IFooRepository` adapter, which is `hex-test-repository-contract`, in the `pyhouse-hex` plugin.
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

**The isolation fixture follows the declared transaction owner** (`test-principles` reliability
rule 2): `conn` for every assertion query and for a callable that accepts a connection; the `engine`
fixture handed to the repository class's constructor, with `truncate_all` cleaning up, for one that
opens its own — asserting through a fresh connection only where its own rollback is under test
(rule 10).

## When to use vs. neighbours

- A pure function in the data-access package — a connection-string builder, the row mapper → not this
  skill; it is a unit test with no fixtures at all.
- The container, migration and isolation fixtures themselves → `flat-test-integration-setup`; this skill
  consumes `conn`, `engine` and `truncate_all` and lays none of its own.
- Writing the tables, repository class and migrations under test → `flat-persistence`.
- The work a trigger calls reaching this write path as part of a run → `flat-test-run-function`; this skill tests
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

_DAY_1 = datetime(2024, 1, 1, tzinfo=UTC)
_DAY_2 = datetime(2024, 1, 2, tzinfo=UTC)


def _a_foo(reference: str = "alpha", name: str = "first", observed_at: datetime = _DAY_1) -> Foo:
    return Foo(reference=FooReference(reference), name=name, observed_at=observed_at)


# only where a write updates on conflict
async def test_a_second_write_of_one_reference_updates_the_set_and_keeps_the_rest(
    engine: AsyncEngine,
    conn: AsyncConnection,
) -> None:
    repository = FooRepository(engine)
    await repository.record_batch([_a_foo(name="first")])
    first_id = (await conn.execute(select(foo_table.c.id))).scalar_one()

    await repository.record_batch([_a_foo(name="second", observed_at=_DAY_2)])

    rows = (await conn.execute(select(foo_table.c.id, foo_table.c.name, foo_table.c.observed_at))).all()
    assert [tuple(row) for row in rows] == [(first_id, "second", _DAY_2)]


# only where a method takes a batch
async def test_a_batch_crossing_chunk_boundaries_lands_every_foo(engine: AsyncEngine, conn: AsyncConnection) -> None:
    await FooRepository(engine, chunk_size=2).record_batch([_a_foo(f"ref-{i}") for i in range(5)])

    count = (await conn.execute(select(func.count()).select_from(foo_table))).scalar_one()
    assert count == 5


# only where a method takes a batch
async def test_two_foos_sharing_a_key_in_one_batch_land_once_as_the_newer(
    engine: AsyncEngine,
    conn: AsyncConnection,
) -> None:
    await FooRepository(engine).record_batch([_a_foo(name="newer", observed_at=_DAY_2), _a_foo(name="older")])

    names = (await conn.execute(select(foo_table.c.name))).scalars().all()
    assert names == ["newer"]


async def test_a_value_the_store_refuses_arrives_as_the_catalogue_error(engine: AsyncEngine) -> None:
    with pytest.raises(StorageWriteRejectedError) as exc_info:
        await FooRepository(engine).record_batch([_a_foo(name="nul\x00")])

    assert exc_info.value.context == {"sqlstate": "22021", "constraint": None}
```

The tests drive the class a caller uses and assert through `conn`, a query against the store.

The first test pins the declared update set from both sides in one comparison: one row, not two; the
name and stamp the set covers changed; the id it does not cover kept the value the first write minted.
The second write carries the later stamp, so the test holds with an ordering guard on the write and
without one.

Where a write chunks, the chunk-boundary test constructs the class with `chunk_size=2` against five foos
deliberately: it crosses the boundary three times with an uneven last chunk, which is where an off-by-one
in the slice shows up. Proving the same thing at the production chunk size would need thousands of rows
on every run.

Where a method takes a batch, the in-batch duplicate test hands one call two foos with one reference,
the newer first, so a collapse that keeps the last input by position fails with a guard or without. One
statement touching one row twice is refused by Postgres (SQLSTATE `21000`), and the translator would
report it as the store being unavailable; one row carrying the name of the foo the collapse keeps is
what collapsing the batch by its key first guarantees (`persistence` rule 17).

The translation test forces the write through the public method a caller uses, refused by the store
itself — a NUL character, which a Postgres text value cannot hold, is SQLSTATE `22021` in the
data-exception class — so no constraint had to be invented for the test.

Where a write resolves a conflict by doing nothing, the file gains the no-op test of rule 5; where it
is guarded on an ordering stamp, the out-of-order test of rule 14; where it spans statements, the
atomicity test of rule 10.

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

1. **This level runs against the real store, substitutes nothing below the repository class, and
   asserts through a query against the store** — `test-principles`, *Datastore contract* rule 1.
2. **Where the translator branches on a constraint's name, pin that name** — `test-principles`,
   *Datastore contract* rule 2.
3. **A unique constraint the translator branches on is tested on the plain insert *and*, where the
   class has one, on the conflict-resolution path** — `test-principles`, *Datastore contract* rule 3.
4. **Where a write updates on conflict, test its declared update set from both sides.** The second write must change what the set names
   *and* leave every column outside it alone — that is the whole contract of an upsert, and both are
   pinned, whether in one comparison or two.
5. **An empty update set means "do nothing on conflict".** Where a write declares one, test it as a
   no-op that raises nothing and changes nothing; a write that meets a key already recorded and must
   leave it alone relies on exactly that.
6. **Where a write chunks, cross a chunk boundary with a deliberately small chunk size and an uneven
   last chunk**, never with production-sized input. Five rows at a chunk size of two crosses it three
   times; proving the same thing at the production size costs thousands of rows on every run.
7. **A forced driver error asserts the catalogue exception the data-access package produces, on each
   write and read the class has** — `test-principles`, *Datastore contract* rule 4. A read
   with no input the store can refuse takes reliability rule 6's one exception.
8. **Where the store assigns a timestamp, assert it as `test-principles` reliability rule 4 states.**
9. **Ordering is asserted only where the query guarantees it.** Add an explicit order clause to any
   query whose result is compared to a list; a relational store promises no insertion order, and a test
   that passes on two rows fails on two hundred.
10. **Where one write spans statements, it has an atomicity test** that forces its last statement to fail
    through a constraint the schema declares, expects the narrowest catalogue exception that constraint
    produces, and asserts through a fresh connection that the earlier statements left nothing behind —
    never through `conn`, whose own transaction cannot observe another connection's rollback. Without it
    a refactor splitting the statements into two transactions passes every test.
11. **Where a run walks a table in pages, a test crosses a page edge where the ordering column ties.**
12. **Where a method takes a batch, it is tested with two inputs that share one key, in one call** —
    `test-principles`, *Datastore contract* rule 7. The store may refuse to resolve one row twice in a
    statement. The newer stamp goes to the first input, so a collapse that keeps the last input fails.
13. **A test arranges every row it asserts on as `test-principles` *Datastore contract* rule 5 states** —
    the service's declared type written through the repository class, or through the schema's own table
    object where the class has no write for it — and, where the subject opens its own connection,
    committed before it runs (`flat-test-integration-setup`).
14. **Where writes for one key can arrive out of order, the newer record is written and then the older**
    — `test-principles`, *Datastore contract* rule 6; the builder takes the stamp, so each write carries
    its own.

## Hard stops

- The constraint under test does not exist in a migration yet → stop, add the revision first
  (`flat-persistence`); a test asserting a constraint the schema never had passes for the wrong reason.
- The adapter sits behind a domain repository protocol → stop, use `hex-test-repository-contract`, in
  the `pyhouse-hex` plugin.
