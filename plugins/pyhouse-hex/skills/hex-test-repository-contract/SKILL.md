---
name: hex-test-repository-contract
description: Use when testing an aggregate's repository adapter — an `IFooRepository` implementation — against the real backend rather than a fake, in both halves of that contract, relational over Postgres through the `sf` rollback fixture (constraints on insert and on update, cascades, the pinned constraint name) and client-store (key-value, document) isolated by a fresh per-test namespace. Not a flat-layered service's storage-package write path, which is `flat-test-persistence`, in the `pyhouse-flat` plugin, not a capability port's adapter, which is `hex-test-capability-adapter`, and not the fixtures it consumes — containers, the migration run and `sf` are `hex-test-integration-setup`'s.
---

# Hex Test — Repository Contract

Consult `test-principles` for the testing constitution. Where this skill contradicts `test-principles`, the constitution wins.

One integration-test file per repository adapter, driven against the **real** backend. This layer catches
what unit coverage cannot.

## When to use vs. neighbours

- A repository adapter on a relational store, under `infrastructure/postgres/repositories/` → the **relational** half of this skill.
- A repository adapter on a client-style store (key-value, document), under `infrastructure/<store-kind>/repositories/` → the **client-style** half of this skill.
- An adapter behind an `ICan<Verb>` capability port rather than an `IFooRepository` → `hex-test-capability-adapter`, not this skill — even when it is driven against a container.
- Schema-only checks (an index exists, a migration carries data correctly) → separate flat files under `tests/integration/postgres/` (`test_indexes.py`, `test_<NNNN>_migration.py`) that take the `run_alembic` fixture (`hex-test-integration-setup`), not `sf`.
- HTTP-layer integration (route, OpenAPI) → `hex-test-restapi-endpoint`; the authenticated and role-gated variants of those tests → `hex-test-restapi-auth`.
- The rollback `conftest.py`, the session containers and the migration run themselves — including "add a testcontainer fixture for Postgres" → `hex-test-integration-setup`. This skill consumes `sf`; it never defines it.
- A pure domain test, with no backend at all → `hex-test-domain`.
- The repository being tested → `hex-persistence` (relational, with `REPOSITORY.md` and `TABLE.md`) or `hex-store-repository` (client store).
- An in-memory fake of the same protocol, for handler unit tests → `hex-test-application-handler`.
- The exceptions the adapter translates integrity errors and SDK errors into → `exception-catalog`.
- Speed targets, fixture placement and the substitution ladder → `test-principles`.
- The write path is a flat-layered service's own data-access package rather than a hexagonal `IFooRepository` adapter → `flat-test-persistence`, in the `pyhouse-flat` plugin; it consumes `flat-test-integration-setup`'s fixtures there, not `sf`.

## Template(s) — pytest, testcontainers, SQLAlchemy async over Postgres, redis-py

- **Relational** — real `UNIQUE` and `FK` violations, real `ON DELETE CASCADE` semantics, the
  `IntegrityError`-to-domain-exception translator's constraint-name map, and the `updated_at` the
  repository writes on update.
- **Client-style** (key-value, document) — the entity-record mapping round-trip and the
  SDK-error-to-domain-exception translation the adapter performs at its boundary. There is no SQL
  transaction and no constraint map here, so both the isolation mechanism and the load-bearing assertion
  are different.

The two halves share their purpose and their shape; they differ in isolation, and that difference is the
first thing to get right.

### Isolation — the one thing that differs

**Relational: transaction rollback.** Every test takes `sf: async_sessionmaker[AsyncSession]`, the fixture from
`hex-test-integration-setup`. The database is empty at test start and everything the test wrote is
discarded at teardown. No marker, no other DB fixture.

**Client-style: a fresh namespace.** A client store has no nested transaction, so the `sf`-rollback model does not apply (the rollback fixture is relational-only). **Each test owns a namespace** — a unique key-prefix, collection or database name, or, where the adapter fixes its namespace in code, a store the suite itself started — created or emptied in a fixture and dropped or emptied at teardown. Which conftest holds that fixture and which holds the session-scoped container is `hex-test-integration-setup`'s scope split, not this skill's.

### Relational

```
tests/integration/postgres/
└── test_<aggregate_snake>_repository.py
```

Default is one file per repository. **Concern-split when the single file stops being navigable** — when finding the test for one method means scrolling past several unrelated concerns, or when a change to one concern keeps forcing rereads of the others. The trigger is that loss of navigability, not a line count: a flat file of twenty near-identical `create` cases stays readable far longer than a short one mixing create, update and filter semantics. When it splits, **the filename names the concern** (`test_<aggregate>_repository_create.py`, `test_<aggregate>_repository_filters.py`), so the split is navigable in the directory listing and not just inside the file.

### Standard CRUD test file — SQLAlchemy async session factory

```python
import datetime as dt
import uuid
from dataclasses import asdict

import pytest
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from myapp.domain.exceptions import FooConflictError, NotFoundError
from myapp.domain.foos import Foo, FooListFilter, FooSort
from myapp.infrastructure.postgres.repositories import FooRepository
from myapp.infrastructure.postgres.tables.foos import foos_table

_PLANTED = dt.datetime(2000, 1, 1, tzinfo=dt.UTC)


def _foo(name: str = "alpha") -> Foo:
    return Foo(id=uuid.uuid4(), name=name, note="a note")


async def test_create_then_get_returns_every_field(sf: async_sessionmaker[AsyncSession]) -> None:
    repo = FooRepository(session_factory=sf)
    foo = _foo()

    await repo.create(foo)

    assert asdict(await repo.get_by_id(foo.id)) == asdict(foo)


async def test_update_persists_the_new_values(sf: async_sessionmaker[AsyncSession]) -> None:
    repo = FooRepository(session_factory=sf)
    foo = _foo("alpha")
    await repo.create(foo)
    foo.name = "beta"

    await repo.update(foo)

    assert asdict(await repo.get_by_id(foo.id)) == asdict(foo)


async def test_delete_removes_the_row(sf: async_sessionmaker[AsyncSession]) -> None:
    repo = FooRepository(session_factory=sf)
    foo = _foo()
    await repo.create(foo)

    await repo.delete(foo.id)

    with pytest.raises(NotFoundError) as exc:
        await repo.get_by_id(foo.id)

    assert exc.value.context["id"] == str(foo.id)


async def test_duplicate_name_on_insert_raises_conflict(sf: async_sessionmaker[AsyncSession]) -> None:
    repo = FooRepository(session_factory=sf)
    await repo.create(_foo("alpha"))

    with pytest.raises(FooConflictError) as exc:
        await repo.create(_foo("alpha"))

    assert exc.value.context["constraint"] == "uq_foos_name"


async def test_duplicate_name_on_update_raises_conflict(sf: async_sessionmaker[AsyncSession]) -> None:
    repo = FooRepository(session_factory=sf)
    await repo.create(_foo("alpha"))
    second = _foo("beta")
    await repo.create(second)

    second.name = "alpha"
    with pytest.raises(FooConflictError) as exc:
        await repo.update(second)

    assert exc.value.context["constraint"] == "uq_foos_name"


async def test_update_writes_updated_at(sf: async_sessionmaker[AsyncSession]) -> None:
    repo = FooRepository(session_factory=sf)
    foo = _foo()
    await repo.create(foo)
    async with sf() as session:
        await session.execute(update(foos_table).where(foos_table.c.id == foo.id).values(updated_at=_PLANTED))
        await session.commit()
    foo.name = "beta"

    await repo.update(foo)

    async with sf() as session:
        written: dt.datetime = (
            await session.execute(select(foos_table.c.updated_at).where(foos_table.c.id == foo.id))
        ).scalar_one()
    assert written > _PLANTED


async def test_get_by_name_returns_match(sf: async_sessionmaker[AsyncSession]) -> None:
    repo = FooRepository(session_factory=sf)
    await repo.create(_foo("alpha"))

    loaded = await repo.get_by_name("alpha")
    assert loaded is not None
    assert loaded.name == "alpha"


async def test_get_by_name_returns_none_when_absent(
    sf: async_sessionmaker[AsyncSession],
) -> None:
    repo = FooRepository(session_factory=sf)

    assert await repo.get_by_name("alpha") is None


async def test_list_respects_pagination_and_sort(sf: async_sessionmaker[AsyncSession]) -> None:
    repo = FooRepository(session_factory=sf)
    await repo.create(_foo("c"))
    await repo.create(_foo("a"))
    await repo.create(_foo("b"))

    page = await repo.list(filter=FooListFilter(sort=FooSort.NAME_ASC, limit=2, offset=0))
    assert [f.name for f in page] == ["a", "b"]
```

**Compare every field, never the entity.** An entity's equality is by id (`hex-domain-model`), so
`loaded == foo` passes a repository that maps the id and drops or swaps every other column;
`asdict(...)` on both sides compares what the row actually carried back.

**The update timestamp is read from the row, off a value the test planted.** It is not an entity field
(`hex-domain-model`, Entity rule 6), so the repository never returns it; the test reads the column
through its own session handle. Planting a value far in the past first is what lets the test fail:
inside the one rollback transaction the store's clock can stand still — Postgres `now()` returns the
transaction's start time — so the value written at create and the one written at update can be
identical, and comparing those two proves nothing. Against the planted value, a repository that never
writes the column leaves it in place and the assertion reds. The planting `UPDATE` is not seed data
(rule 10): no repository method can set the column, which is the point.

**Seed 3, page 2.** The page size must be *smaller* than the seeded set or the test proves nothing: at
`limit=3` the page holds every row, so the same assertion passes a repository that ignores the bound
entirely. 3 and 2 are the smallest pair that fails on a missing `LIMIT` and, because the rows are seeded
out of order (`c`, `a`, `b`) and asserted in order, on a missing `ORDER BY` as well.

### `test_migration_round_trip.py` — every revision undoes and redoes

```python
import subprocess
from collections.abc import Callable


def test_migrations_round_trip(
    run_alembic: Callable[..., subprocess.CompletedProcess[str]],
) -> None:
    down = run_alembic("downgrade", "base")
    assert down.returncode == 0, down.stderr

    up = run_alembic("upgrade", "head")
    assert up.returncode == 0, up.stderr
```

The session starts at head, so this is head → base → head against the real database: a `downgrade()`
that fails, or leaves behind an object the next `upgrade()` trips over, reds here. It ends at head, so
the tests that assume head still find it; a suite run in parallel gives it a database of its own.

### Cascade — an owned child collection

For an aggregate that owns a child collection in a table that cascades from its own, rule 7's test
creates the parent, adds a child through the repository, deletes the parent and asserts through the
repository that the parent's child count is zero; a child looked up under the wrong parent raises the
not-found exception. An aggregate with no owned children has neither test.

### Client-style store — redis-py

```
tests/integration/
├── conftest.py                         # + redis_url (session), redis_client (per test, emptied after)
│                                       #   — hex-test-integration-setup's
└── redis/
    └── test_baz_repository.py
```

A client store gives the test an **SDK client** and a **namespace** the test owns. Redis is the worked
binding — `hex-store-repository`'s own — whose adapter fixes its key prefix in code, so the namespace
a test owns is the suite's own container, emptied after each test. The
adapter is `hex-store-repository`'s `BazRepository`, whose `IBazRepository` declares three verbs, so the
contract is those three: create, fetch by id and delete, each with its absent-record case, plus the
translation of a store failure.

The fixtures — the Redis container for the run (`redis_url`) and the per-test client whose teardown
empties it (`redis_client`) — are `hex-test-integration-setup`'s, in its `CONFTEST.md`: the client sits
up-tree beside the session half because `container` binds it too. This skill writes only the test
module below.

### `test_baz_repository.py`

```python
import uuid
from dataclasses import asdict

import pytest
from redis.asyncio import Redis

from myapp.domain.bazs import Baz
from myapp.domain.exceptions import NotFoundError, UpstreamError
from myapp.infrastructure.redis.repositories import BazRepository


def _baz(name: str = "alpha") -> Baz:
    return Baz(id=uuid.uuid4(), name=name)


async def test_create_then_get_returns_every_field(redis_client: Redis) -> None:
    repo = BazRepository(client=redis_client)
    baz = _baz()

    await repo.create(baz)

    assert asdict(await repo.get_by_id(baz.id)) == asdict(baz)


async def test_create_writes_under_the_documented_key(redis_client: Redis) -> None:
    repo = BazRepository(client=redis_client)
    baz = _baz()

    await repo.create(baz)

    assert await redis_client.exists(f"bazs:{baz.id}") == 1


async def test_get_by_id_of_absent_record_raises_not_found(redis_client: Redis) -> None:
    repo = BazRepository(client=redis_client)
    missing = uuid.uuid4()

    with pytest.raises(NotFoundError) as exc:
        await repo.get_by_id(missing)

    assert exc.value.context["id"] == str(missing)


async def test_delete_removes_the_record(redis_client: Redis) -> None:
    repo = BazRepository(client=redis_client)
    baz = _baz()
    await repo.create(baz)

    await repo.delete(baz.id)

    with pytest.raises(NotFoundError) as exc:
        await repo.get_by_id(baz.id)

    assert exc.value.context["id"] == str(baz.id)


async def test_delete_of_absent_record_raises_not_found(redis_client: Redis) -> None:
    repo = BazRepository(client=redis_client)
    missing = uuid.uuid4()

    with pytest.raises(NotFoundError) as exc:
        await repo.delete(missing)

    assert exc.value.context["id"] == str(missing)


async def test_get_against_unreachable_store_raises_upstream_error() -> None:
    dead = Redis.from_url("redis://127.0.0.1:1/0")  # nothing listening
    missing = uuid.uuid4()
    try:
        repo = BazRepository(client=dead)

        with pytest.raises(UpstreamError) as exc:
            await repo.get_by_id(missing)
    finally:
        await dead.aclose()

    assert exc.value.context["key"] == f"bazs:{missing}"
```

The key test reads the raw key through the test's client: an adapter whose key layout drifted would
still round-trip through its own `get_by_id`, and only a read that goes around it proves where the
record landed — which is what every record already stored depends on.

## Other bindings

- **A pre-provisioned database instead of a disposable container.** Provisioning is
  `hex-test-integration-setup`'s (`## Other bindings`); every rule below is unchanged.
- **An in-process engine (SQLite) for speed.** The rollback shape survives; the contract does not.
  Constraint names, cascade semantics and the error the driver raises all differ, so rules 4, 5 and 7 —
  the assertions this layer exists for — would be pinning a database the service never runs on. A smoke
  suite, never the repository contract.
- **Another engine or driver.** The constraint names, the error code and the attribute the adapter's
  translator reads off it change together (`hex-persistence`); what the test must cover — insert *and*
  update on every unique field, one test per cascade, found and not-found per lookup — does not.
- **Another client store** — a document store, a wide-column store, or an index kept beside the
  authoritative store. The SDK client, its testcontainer and the namespace token change (a collection,
  an index, a database); the session/per-test split, the per-test namespace with teardown, the
  round-trip, ordering and translation assertions do not. Where no testcontainers module exists for the store, a pinned
  `DockerContainer` with an explicit wait strategy is the same fixture.

## Rules

Follow `test-principles` for the testing constitution. Follow `naming` for names and `exception-catalog` for the error catalogue and boundary translation.

### Relational

1. **Every test takes the session handle the integration setup provides — the one whose writes are discarded when the test ends — and opens nothing of its own.** That handle is what makes the database empty at test start and undoes every write at teardown; `sf`, the rollback-scoped session factory, is its name under this catalogue's binding (`hex-test-integration-setup`), and what this rule requires is the property, not the name. A test that builds its own session factory, connection or engine writes outside that boundary, so its rows survive into the next test and the failure surfaces somewhere else entirely. No marker, no second database fixture.
2. Follow `test-principles` for the `_<aggregate>()` builder form. Defaults must be valid; no-override construction succeeds.
3. Follow `test-principles` for natural-key test values. Rollback isolation guarantees an empty DB; `name="alpha"` is safe across tests.
4. **`assert exc.value.context["constraint"] == "<constraint_name>"` on every conflict** — the `ConflictError` subclass the translator raises for that constraint (`FooConflictError` for `uq_foos_name`). This is the only place the `IntegrityError`-to-domain-exception translator's name map is exercised end-to-end — the fake-based unit-test path can't verify it.
5. **Insert AND update paths for every unique field.** The bug class "translator handles INSERT but not UPDATE" only surfaces when both are tested.
6. **The update timestamp is read from the row and compared with a value the test planted before the act.** It is not an entity field (`hex-domain-model`, Entity rule 6), so it is read through the test's own session handle. Where the store's clock is transaction-scoped — Postgres `now()` is — the create and the update inside one rollback transaction carry the identical value, so comparing those two can never fail; a value planted far in the past can, and a repository that never writes the column leaves it there.
7. **Every cascade gets its own test.** Follow `naming`; the test form is `test_cascade_delete_removes_<child>`. Test the count after parent-delete is zero — only this proves the schema's `ON DELETE CASCADE` works.
8. **Every `get_by_<field>` gets both a found and a not-found test.** For case-sensitivity-sensitive fields, add a mixed-case test that asserts the documented behavior.
9. Follow `test-principles` for collection assertion strength. The rollback fixture gives this repository test an empty DB.
10. **No raw INSERTs for seed data on the table under test.** Drive setup through the repository's own `create`. **The ban is scoped to the repository under test** — a contract test that seeds behind its own subject proves nothing about the subject. A test whose subject is not the repository (an endpoint test, say — see `hex-test-restapi-endpoint`) may seed with a raw INSERT; that is legitimate setup, not a bypass. Where `Foo` references another aggregate, seed the referenced row raw — it is not the subject.
11. **No web framework, no HTTP client, no DI container in this file.** The test imports the repository class, takes the session factory, calls methods and asserts. Reaching the adapter through a route tests the route as well, and a failure no longer says which of the two is broken; the HTTP surface is `hex-test-restapi-endpoint`'s.
12. **A test that moves the schema cannot share the fixture that assumes the schema is already at head.** Migration regressions live in their own flat files (`tests/integration/postgres/test_<NNNN>_migration.py`), take the migration runner (`run_alembic`, `hex-test-integration-setup`) and drive it directly, so they are free to downgrade and upgrade. An ordinary repository test is not: it assumes head, and a downgrade underneath it takes the rest of the file with it. One of those files is always present: **the migration round trip** — upgrade to head, downgrade to base, upgrade to head again, against the real database — which is what proves every revision's `downgrade()` runs (`hex-persistence` relies on it) and that the chain rebuilds what it tore down.

### Client-style store

13. **Each test runs against the real store via testcontainers** — never a fake, never a mock. The fake (`hex-test-application-handler`) is for handler unit tests; this layer exists to prove the adapter against the actual backend, which is the only place the SDK call shape and error mapping are exercised. As in the relational half, the file holds no web framework, HTTP client or DI container (rule 11): import the repository class, construct it with the real client the fixture hands over, call methods, assert.
14. **Isolate by a per-test namespace, not rollback.** A fresh key-prefix / collection / database per test, or — where the adapter's namespace is fixed in code — the suite's own container emptied after each test (`redis_client`'s teardown). There is no transaction to roll back; do not reach for `sf`. The empty namespace is what makes natural-key values safe here, as rollback does in rule 3.
15. **The container is session-scoped; the namespace is function-scoped** — `hex-test-integration-setup` obligation 3. A store the environment supplies instead is opted into as `test-principles` reliability rules 1 and 7 state.
16. **Exercise the full protocol**, CRUD verbs and non-CRUD alike — `create`/`get_by_id`/`delete` with their absent-record cases AND any verb of the port's own (`delete_by_<field>`, range/scan). A verb that promises an order asserts that order, not just membership.
17. **Assert the entity↔record mapping round-trips.** What was written comes back as the same entity — every field the record carries, compared field by field, since entity equality is by id. A compound return asserts every element it carries, not just the entity.
18. **Assert the SDK-error → domain-exception translation end-to-end.** This is the load-bearing contract (the client-store analogue of the relational `context["constraint"]` assertion): point the repository at an unreachable/closed client, or trigger a store rejection, and assert the boundary raises the domain exception the adapter promises — `UpstreamError` for a network / store failure, `NotFoundError` for an absent record — never the raw SDK exception, and never the relational `ConflictError` + `context["constraint"]` contract of rule 4, which a client store has no integrity error to produce. These are the domain exceptions `hex-store-repository` translates into at its boundary (shown here as placeholders); assert whichever ones that adapter actually raises, not a frozen literal. Assert the `context` keys the adapter promises.
19. **Assert where the record landed.** The key layout is the adapter's persisted contract (`hex-store-repository`), and an adapter that changes it still round-trips through its own reads; one test reads the raw record through the client, under the key the adapter documents, to prove the layout is the one used.
20. **No assertions on global store contents.** Assert only within this test's namespace — exactly the per-test bucket's discipline, because cleanup is namespace-scoped, not transactional.

## Inlined typing / import rules

- `pytest`, `sqlalchemy.ext.asyncio`, stdlib `uuid`, `myapp.domain.*`, `myapp.infrastructure.postgres.repositories.*`. No `myapp.application.*`, no `myapp.restapi.*`.
- Full annotations on every test signature including `sf: async_sessionmaker[AsyncSession]`.
- Builder `_<aggregate>()` returns the entity type; overrides keyword-only.
- No `from __future__ import annotations`.

For a client-style store, the store's own SDK (`redis.asyncio`) and `myapp.infrastructure.<store-kind>`
replace the SQLAlchemy and Postgres imports. Where a test needs the client and a settings object both,
they arrive as two fixtures, each annotated with its own type — never a bare tuple (`python-style`) —
and a yielding fixture uses `AsyncIterator[T]` / `Iterator[T]`.

## Hard stops

- Nothing up-tree provides a session handle whose writes are discarded when the test ends (`sf` under this catalogue's binding) → stop, use `hex-test-integration-setup`; what is missing is the isolation guarantee, not a fixture name.
- A test references FastAPI, `httpx` or the DI container → stop, use `hex-test-restapi-endpoint`.
- Asked to mock the store SDK or assert against a fake → stop, use `hex-test-application-handler` at the handler-unit layer; this layer drives the real backend.
