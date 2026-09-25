---
name: hex-test-repository-contract
description: Use when testing an aggregate's repository adapter — an `IFooRepository` implementation — against the real backend rather than a fake, in both halves of that contract, relational over Postgres through the `sf` rollback fixture (constraints on insert and on update, cascades, the pinned constraint name) and client-store (vector, cache, document) isolated by a fresh per-test namespace. Not a flat-layered service's storage-package write path, which is `flat-test-persistence`, in the `pyhouse-flat` plugin, not a capability port's adapter, which is `hex-test-capability-adapter`, and not the fixtures it consumes — containers, the migration run and `sf` are `hex-test-integration-setup`'s.
---

# Hex Test — Repository Contract

Consult `test-principles` for the testing constitution. Where this skill contradicts `test-principles`, the constitution wins.

One integration-test file per repository adapter, driven against the **real** backend. This layer catches
what unit coverage cannot.

## When to use vs. neighbours

- A repository adapter on a relational store, under `infrastructure/postgres/repositories/` → the **relational** half of this skill.
- A repository adapter on a client-style store (vector, cache, document), under `infrastructure/<store-kind>/repositories/` → the **client-style** half of this skill.
- An adapter behind an `ICan<Verb>` capability port rather than an `IFooRepository` → `hex-test-capability-adapter`, not this skill — even when it is driven against a container.
- Schema-only checks (an index exists, a migration carries data correctly) → separate flat files under `tests/integration/postgres/` (`test_indexes.py`, `test_<NNNN>_migration.py`) that take the `run_alembic` fixture (`hex-test-integration-setup`), not `sf`.
- HTTP-layer integration (route, OpenAPI) → `hex-test-restapi-endpoint`; the authenticated and role-gated variants of those tests → `hex-test-restapi-auth`.
- The rollback `conftest.py`, the session containers and the migration run themselves — including "add a testcontainer fixture for Postgres" → `hex-test-integration-setup`. This skill consumes `sf`; it never defines it.
- A pure domain test, with no backend at all → `hex-test-domain`.
- The repository being tested → `hex-persistence` (relational, with `REPOSITORY.md` and `TABLE.md`) or `hex-store-repository` (client store).
- An in-memory fake of the same protocol, for handler unit tests → `hex-test-application-handler`.
- The exceptions the adapter translates integrity errors and SDK errors into → `exception-catalog`.
- Speed targets, fixture placement and the substitution ladder → `test-principles`.
- The write path is a flat-layered service's own storage package rather than a hexagonal `IFooRepository` adapter → `flat-test-persistence`, in the `pyhouse-flat` plugin; it consumes `flat-test-integration-setup`'s fixtures there, not `sf`.

## Template(s) — pytest, testcontainers, SQLAlchemy async over Postgres, Qdrant via qdrant-client

- **Relational** — real `UNIQUE` and `FK` violations, real `ON DELETE CASCADE` semantics, the
  `IntegrityError`-to-domain-exception translator's constraint-name map, and the `updated_at` the
  repository writes on update.
- **Client-style** (vector, cache, document) — the entity-record mapping round-trip and the
  SDK-error-to-domain-exception translation the adapter performs at its boundary. There is no SQL
  transaction and no constraint map here, so both the isolation mechanism and the load-bearing assertion
  are different.

The two halves share their purpose and their shape; they differ in isolation, and that difference is the
first thing to get right.

### Isolation — the one thing that differs

**Relational: transaction rollback.** Every test takes `sf: async_sessionmaker[AsyncSession]`, the fixture from
`hex-test-integration-setup`. The database is empty at test start and everything the test wrote is
discarded at teardown. No marker, no other DB fixture.

**Client-style: a fresh namespace.** A client store has no nested transaction, so the `sf`-rollback model does not apply (the rollback fixture is relational-only). Isolate exactly as the per-test bucket does for blobs: **each test owns a fresh namespace** — a unique collection name (qdrant/chroma), key-prefix (redis), or database/bucket — created in a fixture and dropped at teardown. Bring the real store up once per session via testcontainers; create/destroy the per-test namespace per test. **The split is by scope, not by store kind.** `hex-test-integration-setup` owns every **session-scoped** container, engine and client fixture, whatever the store — that is what guarantees one container per session. The sibling `tests/integration/<store-kind>/conftest.py` owns only the **per-test** namespace fixture and its teardown, which is this skill's concern. The per-test bucket is the one per-test fixture up-tree, because `real_app` binds it as well as the tests that use it.

### Relational

```
tests/integration/postgres/
└── test_<aggregate_snake>_repository.py
```

Default is one file per repository. **Concern-split when the single file stops being navigable** — when finding the test for one method means scrolling past several unrelated concerns, or when a change to one concern keeps forcing rereads of the others. The trigger is that loss of navigability, not a line count: a flat file of twenty near-identical `create` cases stays readable far longer than a short one mixing create, update and filter semantics. When it splits, **the filename names the concern** (`test_<aggregate>_repository_create.py`, `test_<aggregate>_repository_filters.py`), so the split is navigable in the directory listing and not just inside the file.

### `tests/integration/postgres/conftest.py` — the referenced row

`Foo` references a `Bar`, so every test needs one to exist. It is seeded raw — rule 10's
cross-aggregate allowance — because the subject here is `FooRepository`, not `BarRepository`.

```python
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from myapp.infrastructure.postgres.tables.bars import bars_table


@pytest.fixture
async def bar_id(sf: async_sessionmaker[AsyncSession]) -> uuid.UUID:
    new_id = uuid.uuid4()
    async with sf() as session:
        await session.execute(bars_table.insert().values(id=new_id, name="bar"))
        await session.commit()
    return new_id
```

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

def _foo(bar_id: uuid.UUID, name: str = "alpha") -> Foo:
    return Foo(id=uuid.uuid4(), name=name, bar_id=bar_id)

async def test_create_then_get_returns_every_field(
    sf: async_sessionmaker[AsyncSession], bar_id: uuid.UUID
) -> None:
    repo = FooRepository(session_factory=sf)
    foo = _foo(bar_id)

    await repo.create(foo)

    assert asdict(await repo.get_by_id(foo.id)) == asdict(foo)

async def test_update_persists_the_new_values(
    sf: async_sessionmaker[AsyncSession], bar_id: uuid.UUID
) -> None:
    repo = FooRepository(session_factory=sf)
    foo = _foo(bar_id, "alpha")
    await repo.create(foo)
    foo.name = "beta"

    await repo.update(foo)

    assert asdict(await repo.get_by_id(foo.id)) == asdict(foo)

async def test_delete_removes_the_row(
    sf: async_sessionmaker[AsyncSession], bar_id: uuid.UUID
) -> None:
    repo = FooRepository(session_factory=sf)
    foo = _foo(bar_id)
    await repo.create(foo)

    await repo.delete(foo.id)

    with pytest.raises(NotFoundError):
        await repo.get_by_id(foo.id)

async def test_duplicate_name_on_insert_raises_conflict(
    sf: async_sessionmaker[AsyncSession], bar_id: uuid.UUID
) -> None:
    repo = FooRepository(session_factory=sf)
    await repo.create(_foo(bar_id, "alpha"))

    with pytest.raises(FooConflictError) as exc:
        await repo.create(_foo(bar_id, "alpha"))

    assert exc.value.context["constraint"] == "uq_foos_name"

async def test_duplicate_name_on_update_raises_conflict(
    sf: async_sessionmaker[AsyncSession], bar_id: uuid.UUID
) -> None:
    repo = FooRepository(session_factory=sf)
    await repo.create(_foo(bar_id, "alpha"))
    second = _foo(bar_id, "beta")
    await repo.create(second)

    second.name = "alpha"
    with pytest.raises(FooConflictError) as exc:
        await repo.update(second)

    assert exc.value.context["constraint"] == "uq_foos_name"

async def test_update_writes_updated_at(
    sf: async_sessionmaker[AsyncSession], bar_id: uuid.UUID
) -> None:
    repo = FooRepository(session_factory=sf)
    foo = _foo(bar_id)
    await repo.create(foo)
    async with sf() as session:
        await session.execute(
            update(foos_table).where(foos_table.c.id == foo.id).values(updated_at=_PLANTED)
        )
        await session.commit()
    foo.name = "beta"

    await repo.update(foo)

    async with sf() as session:
        written: dt.datetime = (
            await session.execute(
                select(foos_table.c.updated_at).where(foos_table.c.id == foo.id)
            )
        ).scalar_one()
    assert written > _PLANTED

async def test_get_by_name_returns_match(
    sf: async_sessionmaker[AsyncSession], bar_id: uuid.UUID
) -> None:
    repo = FooRepository(session_factory=sf)
    await repo.create(_foo(bar_id, "alpha"))

    loaded = await repo.get_by_name("alpha")
    assert loaded is not None
    assert loaded.name == "alpha"

async def test_get_by_name_returns_none_when_absent(
    sf: async_sessionmaker[AsyncSession],
) -> None:
    repo = FooRepository(session_factory=sf)

    assert await repo.get_by_name("alpha") is None

async def test_list_respects_pagination_and_sort(
    sf: async_sessionmaker[AsyncSession], bar_id: uuid.UUID
) -> None:
    repo = FooRepository(session_factory=sf)
    await repo.create(_foo(bar_id, "c"))
    await repo.create(_foo(bar_id, "a"))
    await repo.create(_foo(bar_id, "b"))

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

### Cascade — parent + sub-collection

For an aggregate that owns a child collection — `FooAttachment` rows in a table that cascades from
`foos`. The repository methods `add_attachment`, `get_attachment` and `count_attachments` and the
`_attachment(foo_id)` builder belong to that aggregate's own repository and test module; an aggregate
with no owned children has neither them nor this test.

```python
async def test_cascade_delete_removes_attachments(
    sf: async_sessionmaker[AsyncSession], bar_id: uuid.UUID
) -> None:
    repo = FooRepository(session_factory=sf)
    foo = _foo(bar_id)
    await repo.create(foo)
    await repo.add_attachment(foo.id, _attachment(foo.id))

    await repo.delete(foo.id)

    assert await repo.count_attachments(foo.id) == 0

async def test_attachment_with_wrong_parent_raises_not_found(
    sf: async_sessionmaker[AsyncSession], bar_id: uuid.UUID
) -> None:
    repo = FooRepository(session_factory=sf)
    foo = _foo(bar_id)
    await repo.create(foo)
    att = _attachment(foo.id)
    await repo.add_attachment(foo.id, att)

    with pytest.raises(NotFoundError):
        await repo.get_attachment(uuid.uuid4(), att.id)
```

### Client-style store — Qdrant via `qdrant-client`

```
tests/integration/
├── conftest.py                         # + qdrant_url, qdrant_client (session) — hex-test-integration-setup's
└── qdrant/
    ├── conftest.py                     # qdrant_settings — the per-test collection
    └── test_<aggregate_snake>_repository.py
```

A client store gives the test three things and only three: an **SDK client**, a **namespace handle**
(collection, key prefix, index, database or bucket name) and a **settings object** carrying that handle.
Qdrant is the worked binding — `hex-store-repository`'s own — and its namespace is a collection. The
worked semantics are a scored search, because that is the client-store contract with the most to prove;
a cache's round-trip is the same template with fewer assertions.

The session half — the Qdrant container and one `AsyncQdrantClient` for the run (`qdrant_url`,
`qdrant_client`) — is `hex-test-integration-setup`'s, in its `CONFTEST.md`; this skill writes only the
per-test half below.

### Per-test half — `tests/integration/qdrant/conftest.py`

```python
import uuid
from collections.abc import AsyncIterator

import pytest
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import Distance, VectorParams

from myapp.infrastructure.qdrant import QdrantSettings

_DIM = 3  # the test vectors' dimension — the production one lives in settings

@pytest.fixture
async def qdrant_settings(
    qdrant_url: str, qdrant_client: AsyncQdrantClient
) -> AsyncIterator[QdrantSettings]:
    """A fresh collection per test — namespace isolation, since a client store
    has no transaction to roll back. Created before the test, dropped after."""
    settings = QdrantSettings(url=qdrant_url, foos_collection=f"test_{uuid.uuid4().hex}")
    await qdrant_client.create_collection(
        settings.foos_collection, vectors_config=VectorParams(size=_DIM, distance=Distance.COSINE)
    )
    try:
        yield settings
    finally:
        await qdrant_client.delete_collection(settings.foos_collection)
```

### `test_<aggregate_snake>_repository.py`

```python
import uuid

import pytest
from qdrant_client import AsyncQdrantClient

from myapp.domain.exceptions import UpstreamError
from myapp.domain.foos import Foo
from myapp.infrastructure.qdrant import QdrantSettings
from myapp.infrastructure.qdrant.repositories import FooRepository


def _foo(name: str = "alpha", *, bar_id: uuid.UUID | None = None) -> Foo:
    return Foo(id=uuid.uuid4(), name=name, bar_id=bar_id or uuid.uuid4())

async def test_add_many_then_search_roundtrip(
    qdrant_client: AsyncQdrantClient, qdrant_settings: QdrantSettings
) -> None:
    repo = FooRepository(client=qdrant_client, settings=qdrant_settings)
    foo = _foo()
    await repo.add_many([(foo, (0.1, 0.2, 0.3)), (_foo("other"), (0.9, 0.0, 0.1))])

    hits = await repo.search(query_vector=(0.1, 0.2, 0.3), k=1)
    assert len(hits) == 1
    found, score = hits[0]
    assert (found.id, found.name, found.bar_id) == (foo.id, foo.name, foo.bar_id)
    assert isinstance(score, float)

async def test_search_returns_nearest_first(
    qdrant_client: AsyncQdrantClient, qdrant_settings: QdrantSettings
) -> None:
    repo = FooRepository(client=qdrant_client, settings=qdrant_settings)
    await repo.add_many([(_foo("near"), (0.1, 0.0, 0.0)), (_foo("far"), (0.9, 0.9, 0.9))])

    hits = await repo.search(query_vector=(0.1, 0.0, 0.0), k=2)
    assert [f.name for f, _ in hits] == ["near", "far"]

async def test_delete_by_bar_removes_only_that_bars_points(
    qdrant_client: AsyncQdrantClient, qdrant_settings: QdrantSettings
) -> None:
    repo = FooRepository(client=qdrant_client, settings=qdrant_settings)
    keep, drop = uuid.uuid4(), uuid.uuid4()
    await repo.add_many([
        (_foo("keep", bar_id=keep), (0.1, 0.0, 0.0)),
        (_foo("drop", bar_id=drop), (0.0, 0.1, 0.0)),
    ])

    await repo.delete_by_bar(drop)

    remaining = await repo.search(query_vector=(0.1, 0.1, 0.1), k=10)
    assert {f.bar_id for f, _ in remaining} == {keep}

async def test_search_against_unreachable_store_raises_upstream_error() -> None:
    dead_url = "http://127.0.0.1:1"  # nothing listening
    dead = AsyncQdrantClient(url=dead_url, check_compatibility=False)
    try:
        repo = FooRepository(client=dead, settings=QdrantSettings(url=dead_url, foos_collection="x"))

        with pytest.raises(UpstreamError) as exc:
            await repo.search(query_vector=(0.0, 0.0, 0.0), k=1)
    finally:
        await dead.close()

    assert exc.value.context["collection"] == "x"
```

The round trip seeds two points and asks for one, so a `search` that ignores `k` returns both and reds.
The vector goes in beside the entity and is not read back: it is the store's index, not a field of
`Foo`, so what round-trips is the entity's own fields plus the score the store computed.

## Other bindings

- **A pre-provisioned database instead of a disposable container.** A CI service or a compose stack
  works: the fixture reads a URL from a dedicated opt-in variable rather than starting anything, and the
  guard that refuses to run against a database it did not create (`hex-test-integration-setup`) stops
  being a formality. Every rule below is unchanged.
- **An in-process engine (SQLite) for speed.** The rollback shape survives; the contract does not.
  Constraint names, cascade semantics and the error the driver raises all differ, so rules 4, 5 and 7 —
  the assertions this layer exists for — would be pinning a database the service never runs on. A smoke
  suite, never the repository contract.
- **Another engine or driver.** The constraint names, the error code and the attribute the adapter's
  translator reads off it change together (`hex-persistence`); what the test must cover — insert *and*
  update on every unique field, one test per cascade, found and not-found per lookup — does not.
- **Another client store** — another vector store, a search index, a cache or a document store. The
  SDK client, its testcontainer and the namespace token change (an index, a key prefix, a database);
  the session/per-test split, the per-test namespace with teardown, the round-trip, ordering and
  translation assertions do not. Where no testcontainers module exists for the store, a pinned
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
10. **No raw INSERTs for seed data on the table under test.** Drive setup through the repository's own `create`. **The ban is scoped to the repository under test** — a contract test that seeds behind its own subject proves nothing about the subject. A test whose subject is not the repository (an endpoint test, say — see `hex-test-restapi-endpoint`) may seed with a raw INSERT; that is legitimate setup, not a bypass. Cross-aggregate seed rows (a referenced `Bar` for a `Foo` test) may use raw INSERT when no `BarRepository.create` is in scope — or inject the bar's repo and use it.
11. **No web framework, no HTTP client, no DI container in this file.** The test imports the repository class, takes the session factory, calls methods and asserts. Reaching the adapter through a route tests the route as well, and a failure no longer says which of the two is broken; the HTTP surface is `hex-test-restapi-endpoint`'s.
12. **A test that moves the schema cannot share the fixture that assumes the schema is already at head.** Migration regressions live in their own flat files (`tests/integration/postgres/test_<NNNN>_migration.py`), take the migration runner (`run_alembic`, `hex-test-integration-setup`) and drive it directly, so they are free to downgrade and upgrade. An ordinary repository test is not: it assumes head, and a downgrade underneath it takes the rest of the file with it. One of those files is always present: **the migration round trip** — upgrade to head, downgrade to base, upgrade to head again, against the real database — which is what proves every revision's `downgrade()` runs (`hex-persistence` relies on it) and that the chain rebuilds what it tore down.

### Client-style store

13. **Each test runs against the real store via testcontainers** — never a fake, never a mock. The fake (`hex-test-application-handler`) is for handler unit tests; this layer exists to prove the adapter against the actual backend, which is the only place the SDK call shape and error mapping are exercised.
14. **Isolate by a per-test namespace, not rollback.** A fresh collection / key-prefix / database per test, created in the per-test settings fixture (`qdrant_settings`) and dropped at teardown. There is no transaction to roll back; do not reach for `sf`.
15. **The container is session-scoped; the namespace is function-scoped.** One store per run, because starting it is expensive; one namespace per test, because that is what gives each test sole ownership. Where the environment supplies the store instead of the fixture starting one, the endpoint is read from a **dedicated opt-in variable**, never an ambient one like `CI` — `test-principles` reliability rules.
16. **Exercise the full protocol**, CRUD verbs and non-CRUD alike — `add_many`/`get`/`delete` AND the store's own verbs (`search`, `delete_by_<field>`, range/scan). A `search` test asserts ordering (nearest-first / score-ordered), not just membership.
17. **Assert the entity↔record mapping round-trips.** What was written comes back as the same entity — every field the record carries, compared field by field, since entity equality is by id. A returned scored pair asserts both the entity and that the score is a real `float`, not a placeholder.
18. **Assert the SDK-error → domain-exception translation end-to-end.** This is the load-bearing contract (the client-store analogue of the relational `context["constraint"]` assertion): point the repository at an unreachable/closed client, or trigger a store rejection, and assert the boundary raises the domain exception the adapter promises — `UpstreamError` for a network / store failure, `NotFoundError` for an absent record — never the raw SDK exception. These are the domain exceptions `hex-store-repository` translates into at its boundary (shown here as placeholders); assert whichever ones that adapter actually raises, not a frozen literal. Assert the `context` keys the adapter promises.
19. Follow `test-principles` for natural-key test values. Namespace isolation gives each test an empty store at start (same as the relational contract's rollback guarantee).
20. **Small test vectors.** Use a tiny dimension (e.g. 3) created on the per-test collection; the production embedding dimension is a settings concern, not the contract's.
21. **No web framework, no HTTP client, no DI container in this file either** (rule 11). Import the repository class, construct it with the real client and a settings object scoped to the per-test namespace, call methods, assert.
22. **No assertions on global store contents.** Assert only within this test's namespace — exactly the per-test bucket's discipline, because cleanup is namespace-scoped, not transactional.

## Inlined typing / import rules

- `pytest`, `sqlalchemy.ext.asyncio`, stdlib `uuid`, `myapp.domain.*`, `myapp.infrastructure.postgres.repositories.*`. No `myapp.application.*`, no `myapp.restapi.*`.
- Full annotations on every test signature including `sf: async_sessionmaker[AsyncSession]`.
- Builder `_<aggregate>()` returns the entity type; overrides keyword-only.
- No `from __future__ import annotations`.

For a client-style store, the store's own SDK (`qdrant_client`) and `myapp.infrastructure.<store-kind>`
replace the SQLAlchemy and Postgres imports. The client and the per-test settings arrive as two
fixtures, each annotated with its own type — never a bare tuple (`python-style`) — and a yielding
fixture uses `AsyncIterator[T]` / `Iterator[T]`.

## Hard stops

- Nothing up-tree provides a session handle whose writes are discarded when the test ends (`sf` under this catalogue's binding) → stop, use `hex-test-integration-setup`; what is missing is the isolation guarantee, not a fixture name.
- Asked for `@pytest.mark.integration` or `@pytest.mark.asyncio` → stop, use `test-principles`.
- A test disposes the engine, starts its own connection / instantiate `async_sessionmaker(bind=engine)` directly → stop, that bypasses rollback; use `sf`.
- Asked to assert on `len(items) == N + 1` or use `any(...)` defensively → stop, use `test-principles`.
- Asked to assert on `ConflictError` without checking `context["constraint"]` → stop, the constraint-name map is the load-bearing contract this test exists to pin.
- A test seeds with a raw INSERT on the table under test, **in a test of that repository** → stop, drive setup through `repo.create`; seeding behind the subject proves nothing about it.
- A test references FastAPI, `httpx` or the DI container → stop, use `hex-test-restapi-endpoint`.
- Asked to run Alembic from this test → stop, that's a migration regression test in a separate flat file.
- A test uses `uuid4().hex[:8]` suffixes "to avoid duplicate-key flakes" → stop, use `test-principles`; rollback removes the need.
- Asked to use `sf` / transaction rollback for a client store → stop, there is no nested transaction; isolate by per-test namespace + teardown.
- Asked to mock the store SDK or assert against a fake → stop, use `hex-test-application-handler` at the handler-unit layer; this layer drives the real backend.
- A client-store test asserts on `ConflictError` + `context["constraint"]` → stop, that is the relational `IntegrityError` contract; a client store asserts the domain exceptions its adapter translates SDK errors into (`UpstreamError` / `NotFoundError`) instead.
- A test asserts on store contents outside the test's own namespace → stop, assert only within the per-test collection/prefix.
