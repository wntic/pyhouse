---
name: flat-test-persistence
description: Use when testing a flat-layered service's storage package against the real datastore — its tables, its bulk helpers and the class that owns a multi-statement write — pinning the generated constraint name rather than only the exception type, the declared update set from both sides, an empty update set resolving to a no-op, the rows a read-back returns, a deliberately crossed chunk boundary, the catalogue exception a driver error is translated into, and the atomicity of a write whose last statement fails. Consumes the container and isolation fixtures rather than laying them (`flat-test-integration-setup`). Not the run function that calls this write path, which is `flat-test-run-function`, and not a hexagonal `IFooRepository` adapter, which is `hex-test-repository-contract`, in the `pyhouse-hex` plugin.
paths: ["**/tests/**"]
---

# Flat Test — Storage Contract

Consult `test-principles` for the testing constitution. Where this skill contradicts `test-principles`, the constitution wins.

One integration-test file per table or per storage class, under the service's own
`tests/integration/`, driven against the **real** datastore from `flat-test-integration-setup`. This is
the only level that can catch what the storage package exists to guarantee: that a batch write is a
handful of round trips, that a conflict updates the columns it claims to, that a driver error arrives as
the service's own exception, and that a multi-statement write is one transaction.

Where several services share one storage package, the files sit with that package's own tests instead —
`packages/myschema/tests/integration/` — and nothing else changes.

**Which isolation fixture applies follows from the declared transaction owner** (`flat-persistence`
rule 3), never from a guess:

- The callable under test **accepts** a connection — the bulk helpers, and every assertion query → use
  the **`conn`** fixture and pass it in. Rolled back, nothing reaches disk.
- The callable under test **opens and owns** its transaction — a storage class → pass the **`engine`**
  fixture to its constructor and let `truncate_all` clean up. Assertions read through `conn`, **except
  where the subject's own rollback is what is under test**: there the assertion opens a fresh connection,
  because `conn` sits in a transaction of its own and cannot observe another connection's rollback.

## When to use vs. neighbours

- A pure function in the storage package — a connection-string builder, the natural-key normalizer → not
  this skill; it is a unit test with no fixtures at all.
- The container, migration and isolation fixtures themselves → `flat-test-integration-setup`; this skill
  consumes `conn`, `engine` and `truncate_all` and lays none of its own.
- Writing the tables, helpers, storage class and migrations under test → `flat-persistence`.
- A run function calling this write path as part of a run → `flat-test-run-function`; this skill tests
  the write path, that one tests the wiring above it.
- The client feeding these rows → `flat-test-service-client`.
- A static "no package outside storage constructs a statement" rule → `test-architecture-rule`.
- The shared groundwork — fixture placement, assertion strength, reliability → `test-principles`.
- The adapter sits behind a domain repository protocol → `hex-test-repository-contract`, in the
  `pyhouse-hex` plugin.

## Template — one table's contract (pytest, SQLAlchemy Core over Postgres)

`tests/integration/test_foo_table.py`:

```python
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from myapp.storage.engine import bulk_upsert
from myapp.storage.foo_table import bar_table, foo_table


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
    await bulk_upsert(
        conn, foo_table, [_foo()],
        conflict_columns=["reference"], update_columns=["name"],
    )

    await bulk_upsert(
        conn, foo_table, [_foo(name="second")],
        conflict_columns=["reference"], update_columns=["name"],
    )

    names = (await conn.execute(select(foo_table.c.name))).scalars().all()
    assert names == ["second"]


async def test_a_second_write_leaves_columns_outside_the_update_set_alone(
    conn: AsyncConnection,
) -> None:
    await bulk_upsert(
        conn, foo_table, [_foo()],
        conflict_columns=["reference"], update_columns=["name"],
    )
    first_created_at = (await conn.execute(select(foo_table.c.created_at))).scalar_one()

    await bulk_upsert(
        conn, foo_table, [_foo(name="second")],
        conflict_columns=["reference"], update_columns=["name"],
    )

    assert (
        await conn.execute(select(foo_table.c.created_at))
    ).scalar_one() == first_created_at


async def test_the_reference_is_unique_on_a_plain_insert(conn: AsyncConnection) -> None:
    await conn.execute(foo_table.insert().values(**_foo()))

    with pytest.raises(IntegrityError) as exc_info:
        await conn.execute(foo_table.insert().values(**_foo()))

    assert "uq_foos_reference" in str(exc_info.value.orig)


async def test_an_empty_update_set_is_a_no_op_rather_than_an_error(
    conn: AsyncConnection,
) -> None:
    await conn.execute(foo_table.insert().values(**_foo()))
    foo_id = (await conn.execute(select(foo_table.c.id))).scalar_one()
    row: dict[str, object] = {"foo_id": foo_id, "label": "amber"}
    await bulk_upsert(
        conn, bar_table, [row], conflict_columns=["foo_id", "label"], update_columns=[]
    )

    await bulk_upsert(
        conn, bar_table, [row], conflict_columns=["foo_id", "label"], update_columns=[]
    )

    count = (await conn.execute(select(func.count()).select_from(bar_table))).scalar_one()
    assert count == 1


async def test_a_write_crossing_chunk_boundaries_lands_every_row(
    conn: AsyncConnection,
) -> None:
    rows = [_foo(reference=f"ref-{i}") for i in range(5)]

    await bulk_upsert(
        conn, foo_table, rows,
        conflict_columns=["reference"], update_columns=["name"], chunk_size=2,
    )

    count = (await conn.execute(select(func.count()).select_from(foo_table))).scalar_one()
    assert count == 5


async def test_empty_input_is_a_no_op(conn: AsyncConnection) -> None:
    await bulk_upsert(
        conn, foo_table, [], conflict_columns=["reference"], update_columns=["name"]
    )

    count = (await conn.execute(select(func.count()).select_from(foo_table))).scalar_one()
    assert count == 0
```

The constraint name asserted there is the one the metadata's naming convention generates
(`flat-persistence`). Asserting the **name** rather than only the exception type is what catches a
migration that dropped the intended unique index and let some other constraint fire instead.

The chunk-boundary test uses `chunk_size=2` against five rows deliberately: it crosses the boundary three
times with an uneven last chunk, which is where an off-by-one in the slice shows up. Proving the same
thing at the production chunk size would need thousands of rows and cost a second per run.

**The row builders return mappings, not a declared type, and that is deliberate.** `bulk_upsert` is
parameterised by the `Table`, so at *that* boundary the keys are data — the same helper takes every
table's columns, and there is no fixed set of named fields for a type to declare. What still binds is the
annotation: `dict[str, object]`, never a bare `dict`, because the test surface is type-checked at parity
with source (`python-style`). A builder that constructs the service's **own** type — a `Foo` handed to
the storage class — returns that type, not a mapping.

## Template — the storage class's contract (pytest, SQLAlchemy async over Postgres)

`tests/integration/test_foo_storage.py`:

```python
from datetime import UTC, datetime

import pytest
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from myapp.exceptions import StorageWriteRejected
from myapp.schemas.foo import Foo
from myapp.storage.foo_storage import FooStorage
from myapp.storage.foo_table import bar_table, foo_table


def _a_foo(reference: str = "alpha", labels: tuple[str, ...] = ("amber",)) -> Foo:
    return Foo(
        id=None,
        reference=reference,
        name="first",
        observed_at=datetime(2024, 1, 1, tzinfo=UTC),
        labels=labels,
    )


async def test_a_batch_lands_its_foos_and_their_labels(
    engine: AsyncEngine, conn: AsyncConnection
) -> None:
    await FooStorage(engine).record_batch([_a_foo()])

    labels = (await conn.execute(select(bar_table.c.label))).scalars().all()
    assert labels == ["amber"]


async def test_a_reference_is_normalized_once_on_the_way_in_and_out(
    engine: AsyncEngine
) -> None:
    storage = FooStorage(engine)
    await storage.record_batch([_a_foo(reference="  ALPHA ")])

    assert (await storage.get_by_reference("alpha")).reference == "alpha"


async def test_a_failing_second_write_leaves_no_foo_behind(engine: AsyncEngine) -> None:
    """The two writes are one transaction — a failure in the last must undo the first."""
    label_width = bar_table.c.label.type.length
    over_long_label = "l" * (label_width + 1)

    with pytest.raises(StorageWriteRejected):
        await FooStorage(engine).record_batch([_a_foo(labels=(over_long_label,))])

    async with engine.connect() as check:
        count = (await check.execute(select(func.count()).select_from(foo_table))).scalar_one()
    assert count == 0
```

The atomicity test is the one that justifies the storage class existing at all — without it, nothing pins
the "one transaction, not two" decision, and a refactor splitting the writes into separate connection
blocks passes every other test in the file.

The failure is forced through **a constraint the schema itself declares** — one character past the
declared width of `bars.label` — and the width is read off the column, never written as a literal. A
number large enough to fail today fails for an undeclared reason, and stops failing the day the column
changes; deriving it means the test follows the schema. Where the failing column declares no width, force
the failure through whatever constraint that table does declare — a check, a foreign key, a `NOT NULL` —
never through a value that only happens to be rejected.

The expected error is the **catalogue exception the storage package produces**, not the driver's own
type: translation is mandatory (`flat-persistence` rule 5), so a test expecting the driver's class would
be asserting the one thing the package promises never to let out. And never a bare `Exception`, which is
satisfied by an import error, a typo in a table name or a dropped connection — the test would then stay
green while proving nothing about the rollback.

The last assertion reads through a **fresh connection**, not the `conn` fixture: `conn` holds an open
transaction of its own and could not observe another connection's rollback either way, so reading through
it would make the assertion pass for the wrong reason.

## Other bindings

- **The ORM in place of Core.** Mapped classes replace the table objects and the session replaces the
  connection; every rule below is unchanged, because each pins a property of the stored data rather than
  of the statement that wrote it. Assertions still read the store back (rule 1) — through a fresh query,
  not through the session's identity map, which can hand back the object just written without it ever
  having reached the datastore.
- **Another engine or dialect.** The upsert spelling, the generated constraint names and the driver
  errors a violation raises change together; the contract questions — idempotence, the update set from
  both sides, the chunk boundary, the translated exception, atomicity — do not. Where the dialect has no
  single-statement upsert, the helper's *contract* is still the subject and the test pins whatever the
  helper does instead.
- **How the datastore is provisioned** — a disposable container, a pre-provisioned throwaway database, an
  in-process engine. That choice belongs to `flat-test-integration-setup`, which names its trade-offs;
  nothing in these files changes with it except that an in-process engine of a different dialect
  invalidates rules 2 and 3.

## Rules

1. **Assert through a query against the store, never through the helper's return value alone.** The
   plain bulk write returns nothing; the read-back variant returns what the statement said, which is the
   thing under test. What the datastore holds afterwards is the fact.
2. **Pin the constraint name, not just the exception type.** The name comes from the metadata naming
   convention, and asserting it catches a migration that dropped the intended index.
3. **Every unique constraint is tested on the plain insert *and* on the conflict-resolution path.** A
   partial or expression index can be honoured by an insert and silently not matched by the conflict
   clause; only exercising both paths separates those two outcomes.
4. **Test the declared update set from both sides.** The second write must change what the set names
   *and* leave every column outside it alone — that is the whole contract of an upsert, and it is two
   assertions, not one.
5. **An empty update set means "do nothing on conflict".** Test it as a no-op that raises nothing; a
   join table that records the same pair twice relies on exactly that.
6. **Cross a chunk boundary with a deliberately small chunk size and an uneven last chunk**, never with
   production-sized input. Five rows at a chunk size of two crosses it three times; proving the same
   thing at the production size costs thousands of rows and a second per run.
7. **A test that forces a driver error asserts the catalogue exception the storage package produces, not
   the driver's own type.** Translation is mandatory, so the driver's class is precisely what must never
   escape — a test expecting it pins the defect instead of the contract.
8. **Never assert a timestamp advanced with a strict inequality** where the store's clock is
   transaction-fixed — two writes inside one transaction then produce identical values and the strict
   comparison flakes. Under Postgres `now()` that means `>=`, not `>`.
9. **A storage-class test constructs the class with the `engine` fixture**, never with the production
   engine factory — that one reads the placeholder connection string (`flat-persistence`).
10. **Ordering is asserted only where the query guarantees it.** Add an explicit order clause to any
    query whose result is compared to a list; a relational store promises no insertion order, and a test
    that passes on two rows fails on two hundred.
11. **The atomicity test forces the failure through a constraint the schema declares, and expects the
    narrowest error that constraint actually produces.** A bare `Exception` passes on an import error, a
    typo or a dropped connection, so the test would stay green while proving nothing about the rollback.

## Hard stops

- A storage-class test asserts a rollback through the `conn` fixture → stop, `conn` sits in its own
  transaction and cannot observe another connection's rollback; open a fresh connection for that
  assertion.
- A test for a multi-statement write only checks the happy path → stop, the atomicity case is the reason
  the storage class exists; add the failing-last-write test.
- The atomicity test expects a bare `Exception`, or the driver's own exception class → stop; name the
  catalogue exception the translator produces, or the test pins nothing the package promises.
- The constraint under test does not exist in a migration yet → stop, add the revision first; a test
  asserting a constraint the schema never had passes for the wrong reason.
- A test asserts on rows written by a *different* test → stop, isolation wipes everything between tests;
  construct the rows this test needs.
- A test reaches for a mock to avoid starting the container → stop, this whole level exists because the
  real backend is the only thing that can answer these questions.
- A test writes raw SQL to set up state a `Table` object could express → stop, use the `Table`;
  hand-written SQL in a test drifts from the schema silently.
- A row builder is annotated with a bare `-> dict` → stop, give it its type parameters; the test surface
  is type-checked at parity with source (`python-style`).
