---
name: flat-test-schema-package
description: Use when testing the shared `packages/myschema` write path against real Postgres — tables, bulk helpers and repositories — pinning constraint names, upsert update sets, returned rows, chunk boundaries and atomicity. Consumes the container and isolation fixtures rather than laying them (`flat-test-integration-setup`). Not a producer's run wiring — `flat-test-run-function`.
paths: ["**/tests/**"]
---

# Flat Test — Schema Contract

Consult `test-principles` for the testing constitution. Where this skill contradicts `test-principles`, the constitution wins.

One integration-test file per table pair or repository class, under
`packages/myschema/tests/integration/`, driven against the **real** Postgres from
`flat-test-integration-setup`. This is the only level that can catch what the schema package
exists to guarantee: that a batch write is one round trip, that `ON CONFLICT` updates the columns it
claims to, and that two producers discovering the same identity end up as one row with two kinds.

Which isolation fixture applies follows from what is under test:

- The helpers take an `AsyncConnection` → use the **`conn`** fixture and pass it in. Rolled back.
- A repository class opens `engine.begin()` itself → pass the **`engine`** fixture to its constructor,
  and let the package's autouse `truncate_all` clean up. Assertions read through `conn` — **except where
  the subject owns the transaction under test**, as the rollback case below does; there the assertion
  opens a fresh connection, because `conn` sits in a transaction of its own and cannot observe another
  connection's rollback.

## When to use vs. neighbours

- A pure function in the schema package — a DSN builder, an identity normalizer → not this skill; it is
  a unit test under `packages/myschema/tests/unit/` with no fixtures at all.
- The container, migration and isolation fixtures themselves → `flat-test-integration-setup`; this skill
  consumes `conn`, `engine` and `truncate_all` and lays none of its own.
- Writing the tables, bulk helpers, repositories and migrations under test → `flat-schema-package`.
- A producer calling `record_batch` as part of a run → `flat-test-run-function`; this skill tests the
  write path, that one tests the wiring.
- The service-side HTTP client feeding these rows → `flat-test-service-client`.
- A static "no service defines a Table" rule → `test-architecture-rule`.
- The shared groundwork — fixture placement, assertion strength, reliability → `test-principles`.

## Template — a producer's table pair (pytest, SQLAlchemy Core over Postgres)

`packages/myschema/tests/integration/test_foo_tables.py`:

```python
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from myschema.engine import bulk_upsert
from myschema.tables.foo import foo_filtered_table, foo_raw_table


def _raw(external_id: str = "e1", **overrides: object) -> dict:
    return {"external_id": external_id, "raw": {"n": 1}, **overrides}


async def test_raw_insert_round_trips_the_payload(conn: AsyncConnection) -> None:
    await bulk_upsert(
        conn, foo_raw_table, [_raw()], conflict_columns=["external_id"], update_columns=["raw"]
    )

    stored = (await conn.execute(select(foo_raw_table.c.raw))).scalar_one()
    assert stored == {"n": 1}


async def test_second_write_of_same_external_id_updates_rather_than_duplicates(
    conn: AsyncConnection,
) -> None:
    await bulk_upsert(
        conn, foo_raw_table, [_raw()], conflict_columns=["external_id"], update_columns=["raw"]
    )

    await bulk_upsert(
        conn,
        foo_raw_table,
        [_raw(raw={"n": 2})],
        conflict_columns=["external_id"],
        update_columns=["raw"],
    )

    rows = (await conn.execute(select(foo_raw_table.c.raw))).scalars().all()
    assert rows == [{"n": 2}]


async def test_second_write_leaves_columns_outside_the_update_set_alone(
    conn: AsyncConnection,
) -> None:
    await bulk_upsert(
        conn, foo_raw_table, [_raw()], conflict_columns=["external_id"], update_columns=["raw"]
    )
    first_fetched_at = (await conn.execute(select(foo_raw_table.c.fetched_at))).scalar_one()

    await bulk_upsert(
        conn,
        foo_raw_table,
        [_raw(raw={"n": 2})],
        conflict_columns=["external_id"],
        update_columns=["raw"],
    )

    assert (
        await conn.execute(select(foo_raw_table.c.fetched_at))
    ).scalar_one() == first_fetched_at


async def test_filtered_identity_is_unique_on_insert(conn: AsyncConnection) -> None:
    await conn.execute(foo_filtered_table.insert().values(identity="alpha"))

    with pytest.raises(IntegrityError) as exc_info:
        await conn.execute(foo_filtered_table.insert().values(identity="alpha"))

    assert "uq_foo_filtered_identity" in str(exc_info.value.orig)
```

The constraint name asserted there is the one the shared metadata's naming convention generates
(`flat-schema-package`). Asserting the *name* rather than the exception type is what catches a
migration that dropped the intended unique index and let some other constraint fire instead.

## Template — the bulk helpers (pytest, SQLAlchemy Core over Postgres)

`packages/myschema/tests/integration/test_bulk_helpers.py`:

```python
async def test_writes_more_rows_than_one_chunk(conn: AsyncConnection) -> None:
    rows = [{"identity": f"id-{i}"} for i in range(5)]

    await bulk_upsert(
        conn,
        foo_filtered_table,
        rows,
        conflict_columns=["identity"],
        update_columns=["raw_id"],
        chunk_size=2,
    )

    count = (await conn.execute(select(func.count()).select_from(foo_filtered_table))).scalar_one()
    assert count == 5


async def test_returning_hands_back_one_row_per_input_across_chunks(
    conn: AsyncConnection,
) -> None:
    rows = [{"identity": f"id-{i}"} for i in range(5)]

    returned = await bulk_upsert_returning(
        conn,
        entities_table,
        rows,
        conflict_columns=["identity"],
        update_columns=["last_seen_at"],
        returning_columns=["id", "identity"],
        chunk_size=2,
    )

    assert sorted(r["identity"] for r in returned) == [f"id-{i}" for i in range(5)]


async def test_an_empty_update_set_is_a_no_op_rather_than_an_error(
    conn: AsyncConnection,
) -> None:
    row = {"entity_id": _an_entity_id, "kind": "foo"}
    await bulk_upsert(
        conn, entity_kinds_table, [row], conflict_columns=["entity_id", "kind"], update_columns=[]
    )

    await bulk_upsert(
        conn, entity_kinds_table, [row], conflict_columns=["entity_id", "kind"], update_columns=[]
    )

    count = (await conn.execute(select(func.count()).select_from(entity_kinds_table))).scalar_one()
    assert count == 1


async def test_empty_input_is_a_no_op(conn: AsyncConnection) -> None:
    await bulk_upsert(
        conn, foo_filtered_table, [], conflict_columns=["identity"], update_columns=["raw_id"]
    )

    count = (await conn.execute(select(func.count()).select_from(foo_filtered_table))).scalar_one()
    assert count == 0
```

The chunk-boundary test uses `chunk_size=2` against five rows deliberately: it crosses the boundary
three times with an uneven last chunk, which is where an off-by-one in the slice shows up. Testing with
the production chunk size would need thousands of rows to prove the same thing and would cost a second
per run.

## Template — a repository class, multi-table and atomic (pytest, SQLAlchemy Core over Postgres)

`packages/myschema/tests/integration/test_entities_repository.py`:

```python
import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import DataError
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from myschema.repositories.entities import EntitiesRepository
from myschema.tables.bar import bar_filtered_table
from myschema.tables.foo import foo_filtered_table
from myschema.tables.registry import entities_table, entity_kinds_table


def _row(identity: str = "alpha") -> dict:
    return {"identity": identity}


async def test_records_the_kind_that_discovered_the_identity(
    engine: AsyncEngine, conn: AsyncConnection
) -> None:
    repo = EntitiesRepository(engine)

    await repo.record_batch(foo_filtered_table, "foo", [_row()])

    kinds = (await conn.execute(select(entity_kinds_table.c.kind))).scalars().all()
    assert kinds == ["foo"]


async def test_two_producers_finding_one_identity_share_a_single_entity(
    engine: AsyncEngine, conn: AsyncConnection
) -> None:
    repo = EntitiesRepository(engine)
    await repo.record_batch(foo_filtered_table, "foo", [_row()])

    await repo.record_batch(bar_filtered_table, "bar", [_row()])

    entities = (await conn.execute(select(entities_table.c.identity))).scalars().all()
    kinds = (
        await conn.execute(select(entity_kinds_table.c.kind).order_by(entity_kinds_table.c.kind))
    ).scalars().all()
    assert entities == ["alpha"]
    assert kinds == ["bar", "foo"]


async def test_rediscovery_advances_last_seen_but_not_first_seen(
    engine: AsyncEngine, conn: AsyncConnection
) -> None:
    repo = EntitiesRepository(engine)
    await repo.record_batch(foo_filtered_table, "foo", [_row()])
    before = (
        await conn.execute(select(entities_table.c.first_seen_at, entities_table.c.last_seen_at))
    ).one()

    await repo.record_batch(foo_filtered_table, "foo", [_row()])

    after = (
        await conn.execute(select(entities_table.c.first_seen_at, entities_table.c.last_seen_at))
    ).one()
    assert after.first_seen_at == before.first_seen_at
    assert after.last_seen_at >= before.last_seen_at


async def test_recording_the_same_kind_twice_is_not_an_error(
    engine: AsyncEngine, conn: AsyncConnection
) -> None:
    repo = EntitiesRepository(engine)
    await repo.record_batch(foo_filtered_table, "foo", [_row()])

    await repo.record_batch(foo_filtered_table, "foo", [_row()])

    kinds = (await conn.execute(select(entity_kinds_table.c.kind))).scalars().all()
    assert kinds == ["foo"]


async def test_a_failing_third_write_leaves_no_entity_behind(engine: AsyncEngine) -> None:
    """The three writes are one transaction — a failure in the last must undo the first two."""
    repo = EntitiesRepository(engine)
    kind_width = entity_kinds_table.c.kind.type.length
    over_long_kind = "k" * (kind_width + 1)

    with pytest.raises(DataError):
        await repo.record_batch(foo_filtered_table, over_long_kind, [_row()])

    async with engine.connect() as check:
        count = (await check.execute(select(func.count()).select_from(entities_table))).scalar_one()
    assert count == 0
```

The atomicity test is the one that justifies the repository class existing at all — without it, nothing
pins the "one `engine.begin()`, not three" decision, and a refactor splitting the writes into separate
transactions passes every other test in the file.

The failure is forced through **a constraint the schema itself declares** — one character past the
declared width of `entity_kinds.kind` — and the length is read off the column, never written as a
literal. The expected error is the narrowest class that constraint actually raises, never a bare
`Exception`: a bare `Exception` is satisfied by an import error, a typo in the table name or a dropped
connection, and the test then proves nothing about atomicity. A number large enough to fail today fails for an undeclared reason, and stops failing the day
the column changes; deriving it means the test follows the schema. Where the failing column declares no
width, force the failure through whatever constraint that table does declare — a check, a foreign key,
a `NOT NULL` — never through a value that only happens to be rejected.

Its assertion reads through a **fresh connection**, not the `conn` fixture: `conn` holds an open
transaction of its own and could not observe another connection's rollback either way, so reading
through it would make the assertion pass for the wrong reason.

## Other bindings

- **The ORM in place of Core.** Mapped classes replace the table objects and the session replaces the
  connection; every rule below is unchanged, because each pins a property of the stored data rather than
  of the statement that wrote it. Assertions still read the store back (rule 1) — through a fresh query,
  not through the session's identity map, which can hand back the object just written without it ever
  having reached the database.
- **Another engine or dialect.** The upsert spelling, the generated constraint names and the error
  classes a violation raises change together; the contract questions — idempotence, the update set from
  both sides, the chunk boundary, atomicity — do not. Where the dialect has no single-statement upsert,
  the helper's *contract* is still the subject and the test pins whatever the helper does instead.
- **How the datastore is provisioned** — a disposable container, a pre-provisioned throwaway database,
  an in-process engine. That choice belongs to `flat-test-integration-setup`, which names its
  trade-offs; nothing in this file changes with it except that an in-process engine of a different
  dialect invalidates rules 2 and 3.

## Rules

1. **Assert through a query against the store, never through the helper's return value alone.**
   `bulk_upsert` returns nothing; `bulk_upsert_returning` returns what the statement said, which is the
   thing under test. What the datastore holds afterwards is the fact.
2. **Pin the constraint name, not just the exception type.** The name comes from the metadata naming
   convention, and asserting it catches a migration that dropped the intended index.
3. **Every unique constraint is tested on the plain insert *and* on the conflict-resolution path.** A
   partial or expression index can be honoured by `INSERT` and silently not matched by
   `ON CONFLICT DO UPDATE`; only exercising both paths separates those two outcomes.
4. **Test the declared update set from both sides.** The second write must change what the set names
   *and* leave every column outside it alone — that is the whole contract of an upsert, and it is two
   assertions, not one.
5. **An empty update set means "do nothing on conflict".** Test it as a no-op that raises nothing; a
   junction table that records the same pair twice relies on exactly that.
6. **Cross a chunk boundary with a deliberately small chunk size and an uneven last chunk**, never with
   production-sized input. Five rows at a chunk size of two crosses it three times; proving the same
   thing at the production size costs thousands of rows and a second per run.
7. **Never assert a timestamp advanced with a strict inequality** where the store's clock is
   transaction-fixed — two writes inside one transaction then produce identical values and the strict
   comparison flakes. Under Postgres `now()` that means `>=`, not `>`.
8. **A repository test constructs the repository with the `engine` fixture**, never with the production
   engine factory — that one points at the placeholder DSN.
9. **Ordering is asserted only where the query guarantees it.** Add an explicit order clause to any
   query whose result is compared to a list; a relational store promises no insertion order, and a test
   that passes on two rows fails on two hundred.
10. **The atomicity test expects the narrowest error the forced constraint actually raises.** A bare
    `Exception` passes on an import error, a typo or a dropped connection, so the test would stay green
    while proving nothing about the rollback. Where the code under test translates driver errors, assert
    the catalogue exception it produces instead.

## Hard stops

- A repository test asserts a rollback through the `conn` fixture → stop, `conn` sits in its own
  transaction and cannot observe another connection's rollback; open a fresh connection for that
  assertion.
- A test for a multi-table write only checks the happy path → stop, the atomicity case is the reason the
  repository class exists; add the failing-last-write test.
- The atomicity test expects a bare `Exception` → stop, name the class the forced constraint actually
  raises; a bare `Exception` is also satisfied by an import error and the test proves nothing.
- The constraint under test does not exist in a migration yet → stop, add the Alembic revision first; a
  test asserting a constraint the schema never had passes for the wrong reason.
- A test asserts on rows written by a *different* test → stop, isolation wipes everything between tests;
  construct the rows this test needs.
- A test reaches for a mock to avoid starting the container → stop, this whole level exists because the
  real backend is the only thing that can answer these questions.
- A test writes raw SQL to set up state a `Table` object could express → stop, use the `Table`;
  hand-written SQL in a test drifts from the schema silently.
