---
name: hex-test-repository-contract
description: Use when testing an aggregate's repository adapter — an `IFooRepository` implementation — against the real backend rather than a fake, in both halves of that contract, relational over Postgres through the `sf` rollback fixture (constraints on insert and on update, cascades, the pinned constraint name) and client-store (vector, cache, document) isolated by a fresh per-test namespace. Not a uv workspace's shared `packages/myschema` write path, which is `flat-test-schema-package`, not a capability port's adapter, which is `hex-test-capability-adapter`, and not the fixtures it consumes — containers, the migration run and `sf` are `hex-test-integration-setup`'s.
paths: ["**/tests/**"]
---

# Hex Test — Repository Contract

Consult `test-principles` for the testing constitution. Where this skill contradicts `test-principles`, the constitution wins.

One integration-test file per repository adapter, driven against the **real** backend. This layer catches
what unit coverage cannot.

## When to use vs. neighbours

- A repository adapter on a relational store, under `infrastructure/postgres/repositories/` → the **relational** half of this skill.
- A repository adapter on a client-style store (vector, cache, document), under `infrastructure/<store-kind>/repositories/` → the **client-style** half of this skill.
- An adapter behind an `ICan<Verb>` capability port rather than an `IFooRepository` → `hex-test-capability-adapter`, not this skill — even when it is driven against a container.
- Schema-only checks (an index exists, a migration carries data correctly) → separate flat files under `tests/integration/postgres/` (`test_indexes.py`, `test_<NNNN>_migration.py`) that use `db_settings` and `run_alembic`, not `sf`.
- HTTP-layer integration (route, OpenAPI) → `hex-test-restapi-endpoint`; the authenticated and role-gated variants of those tests → `hex-test-restapi-auth`.
- The rollback `conftest.py`, the session containers and the migration run themselves — including "add a testcontainer fixture for Postgres" → `hex-test-integration-setup`. This skill consumes `sf`; it never defines it.
- A pure domain test, with no backend at all → `hex-test-domain`.
- The repository being tested → `hex-persistence` (relational, with `REPOSITORY.md` and `TABLE.md`) or `hex-store-repository` (client store).
- An in-memory fake of the same protocol, for handler unit tests → `hex-test-application-handler`.
- The exceptions the adapter translates integrity errors and SDK errors into → `exception-catalog`.
- Speed targets, fixture placement and the substitution ladder → `test-principles`.
- The repository is a flat workspace's shared `packages/myschema` helper rather than a hexagonal `IFooRepository` adapter → `flat-test-schema-package`, in the `pyhouse-flat` plugin; it consumes `flat-test-integration-setup`'s fixtures there, not `sf`.

## Template(s) — pytest, SQLAlchemy async over Postgres, testcontainers

- **Relational** — real `UNIQUE` and `FK` violations, real `ON DELETE CASCADE` semantics, the
  `IntegrityError`-to-domain-exception translator's constraint-name map, and the `onupdate=` clause on
  `updated_at`.
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

**Client-style: a fresh namespace.** A client store has no nested transaction, so the `sf`-rollback model does not apply (the rollback fixture is relational-only). Isolate exactly as the `s3_prefix` pattern does: **each test owns a fresh namespace** — a unique collection name (qdrant/chroma), key-prefix (redis), or database/bucket — created in a fixture and dropped at teardown. Bring the real store up once per session via testcontainers; create/destroy the per-test namespace per test. **The split is by scope, not by store kind.** `hex-test-integration-setup` owns every **session-scoped** container, engine and client fixture, whatever the store — that is what guarantees one container per session. The sibling `tests/integration/<store-kind>/conftest.py` owns only the **per-test** namespace fixture and its teardown, which is this skill's concern. The blob fixtures sit in the outer conftest for the same reason and no other: `s3_prefix` is per-test and lives beside the tests that use it, the bucket and its session-end cleanup are session-scoped and live up-tree.

### Relational

```
tests/integration/postgres/
└── test_<aggregate_snake>_repository.py
```

Default is one file per repository. **Concern-split when the single file stops being navigable** — when finding the test for one method means scrolling past several unrelated concerns, or when a change to one concern keeps forcing rereads of the others. The trigger is that loss of navigability, not a line count: a flat file of twenty near-identical `create` cases stays readable far longer than a short one mixing create, update and filter semantics. When it splits, **the filename names the concern** (`test_<aggregate>_repository_create.py`, `test_<aggregate>_repository_filters.py`), so the split is navigable in the directory listing and not just inside the file.

### Standard CRUD test file — SQLAlchemy async session factory

```python
import uuid

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from myapp.domain.exceptions import ConflictError, NotFoundError
from myapp.domain.foos import Foo, FooListFilter
from myapp.infrastructure.postgres.repositories import FooRepository

def _foo(name: str = "alpha") -> Foo:
    return Foo(id=uuid.uuid4(), name=name)

async def test_crud_roundtrip(sf: async_sessionmaker[AsyncSession]) -> None:
    repo = FooRepository(session_factory=sf)
    foo = _foo()

    await repo.create(foo)
    loaded = await repo.get_by_id(foo.id)
    assert loaded == foo

    foo.name = "beta"
    await repo.update(foo)
    assert (await repo.get_by_id(foo.id)).name == "beta"

    await repo.delete(foo.id)
    with pytest.raises(NotFoundError):
        await repo.get_by_id(foo.id)

async def test_duplicate_name_on_insert_raises_conflict(
    sf: async_sessionmaker[AsyncSession],
) -> None:
    repo = FooRepository(session_factory=sf)
    await repo.create(_foo("alpha"))

    with pytest.raises(ConflictError) as exc:
        await repo.create(_foo("alpha"))

    assert exc.value.context["constraint"] == "uq_foos_name"

async def test_duplicate_name_on_update_raises_conflict(
    sf: async_sessionmaker[AsyncSession],
) -> None:
    repo = FooRepository(session_factory=sf)
    await repo.create(_foo("alpha"))
    second = _foo("beta")
    await repo.create(second)

    second.name = "alpha"
    with pytest.raises(ConflictError) as exc:
        await repo.update(second)

    assert exc.value.context["constraint"] == "uq_foos_name"

async def test_updated_at_advances_on_update(
    sf: async_sessionmaker[AsyncSession],
) -> None:
    repo = FooRepository(session_factory=sf)
    foo = _foo()
    await repo.create(foo)
    before = (await repo.get_by_id(foo.id)).updated_at

    foo.name = "beta"
    await repo.update(foo)
    after = (await repo.get_by_id(foo.id)).updated_at

    assert after >= before

async def test_get_by_name_returns_match(
    sf: async_sessionmaker[AsyncSession],
) -> None:
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

async def test_list_respects_pagination_and_sort(
    sf: async_sessionmaker[AsyncSession],
) -> None:
    repo = FooRepository(session_factory=sf)
    for name in ("c", "a", "b"):
        await repo.create(_foo(name))

    page = await repo.list(filter=FooListFilter(limit=2, offset=0))
    assert [f.name for f in page] == ["a", "b"]
```

**Seed 3, page 2.** The page size must be *smaller* than the seeded set or the test proves nothing: at
`limit=3` the page holds every row, so the same assertion passes a repository that ignores the bound
entirely. 3 and 2 are the smallest pair that fails on a missing `LIMIT` and, because the rows are seeded
out of order (`c`, `a`, `b`) and asserted in order, on a missing `ORDER BY` as well.

### Cascade — parent + sub-collection

```python
async def test_cascade_delete_removes_attachments(
    sf: async_sessionmaker[AsyncSession],
) -> None:
    repo = FooRepository(session_factory=sf)
    foo = _foo()
    await repo.create(foo)
    await repo.add_attachment(foo.id, _attachment(foo.id))

    await repo.delete(foo.id)

    assert await repo.count_attachments(foo.id) == 0

async def test_attachment_with_wrong_parent_raises_not_found(
    sf: async_sessionmaker[AsyncSession],
) -> None:
    repo = FooRepository(session_factory=sf)
    foo = _foo()
    await repo.create(foo)
    att = _attachment(foo.id)
    await repo.add_attachment(foo.id, att)

    with pytest.raises(NotFoundError):
        await repo.get_attachment(uuid.uuid4(), att.id)
```

### Client-style store

```
tests/integration/<store-kind>/
├── conftest.py                         # session container + per-test namespace fixture
└── test_<aggregate_snake>_repository.py
```

### `conftest.py` — real store + per-test namespace (client-store profile)

**The profile, not the vendor, is what this template teaches.** A client store gives the test three
things and only three: an **SDK client**, a **namespace handle** (collection, key prefix, index,
database or bucket name) and a **settings object** carrying that handle. `store_sdk` and
`StoreContainer` below stand for whichever library and testcontainer the project's store profile names
(`hex-conventions` block B) — a vector store, a cache, a document store or a search index all fill the
same three slots. The worked semantics are a scored search, because that is the client-store contract
with the most to prove; a cache's round-trip is the same template with fewer assertions.

```python
import os
import uuid
from collections.abc import AsyncIterator, Iterator

import pytest
from store_sdk import AsyncStoreClient
from store_sdk.models import Distance, VectorParams

_DIM = 3  # the test vectors' dimension — small; production dimension lives in settings

@pytest.fixture(scope="session")
def store_url() -> Iterator[str]:
    provided = os.getenv("MYAPP_STORE_URL")  # a dedicated opt-in variable, never ambient `CI`
    if provided:
        yield provided
        return
    from testcontainers.community.store import StoreContainer

    # Pin the image tag — never float on :latest or a moving alias (the same pin rule
    # as hex-test-integration-setup's images; :latest makes the suite non-reproducible,
    # since the same commit meets a different server on a rerun). Fill
    # <store-image>:<pinned-tag> from your own stack. The specific pin is a
    # per-deployment choice, bumped deliberately, not a frozen constant.
    with StoreContainer("<store-image>:<pinned-tag>") as q:
        yield f"http://{q.get_container_host_ip()}:{q.get_exposed_port(6333)}"

@pytest.fixture
async def store(store_url: str) -> AsyncIterator[tuple[AsyncStoreClient, str]]:
    """A fresh collection per test = namespace isolation (no transaction rollback
    for a client store). Create it, hand out (client, collection), drop at teardown."""
    client = AsyncStoreClient(url=store_url)
    collection = f"test_{uuid.uuid4().hex}"
    await client.create_collection(
        collection, vectors_config=VectorParams(size=_DIM, distance=Distance.COSINE)
    )
    try:
        yield client, collection
    finally:
        await client.delete_collection(collection)
        await client.close()
```

### `test_<aggregate_snake>_repository.py`

```python
import uuid

import pytest
from store_sdk import AsyncStoreClient

from myapp.domain.exceptions import UpstreamError
from myapp.domain.foos import Foo
from myapp.infrastructure.store.repositories import FooRepository
from myapp.infrastructure.store.settings import FoosVectorSettings

def _foo(text: str = "alpha", *, vector: list[float] | None = None, bar_id: uuid.UUID | None = None) -> Foo:
    return Foo(
        id=uuid.uuid4(),
        bar_id=bar_id or uuid.uuid4(),
        text=text,
        vector=vector or [0.1, 0.2, 0.3],
    )

def _repo(store: tuple[AsyncStoreClient, str]) -> FooRepository:
    client, collection = store
    return FooRepository(client=client, settings=FoosVectorSettings(collection=collection))

async def test_add_many_then_search_roundtrip(store: tuple[AsyncStoreClient, str]) -> None:
    repo = _repo(store)
    foo = _foo()
    await repo.add_many((foo,))

    hits = await repo.search(query_vector=foo.vector, k=1)
    assert len(hits) == 1
    found, score = hits[0]
    assert found.id == foo.id
    assert found.text == "alpha"
    assert isinstance(score, float)

async def test_search_returns_nearest_first(store: tuple[AsyncStoreClient, str]) -> None:
    repo = _repo(store)
    near = _foo("near", vector=[0.1, 0.0, 0.0])
    far = _foo("far", vector=[0.9, 0.9, 0.9])
    await repo.add_many((near, far))

    hits = await repo.search(query_vector=[0.1, 0.0, 0.0], k=2)
    assert [f.text for f, _ in hits] == ["near", "far"]

async def test_delete_by_bar_removes_only_that_bars_points(
    store: tuple[AsyncStoreClient, str],
) -> None:
    repo = _repo(store)
    keep, drop = uuid.uuid4(), uuid.uuid4()
    await repo.add_many((
        _foo("keep", vector=[0.1, 0.0, 0.0], bar_id=keep),
        _foo("drop", vector=[0.0, 0.1, 0.0], bar_id=drop),
    ))

    await repo.delete_by_bar(drop)

    remaining = await repo.search(query_vector=[0.1, 0.1, 0.1], k=10)
    assert {f.bar_id for f, _ in remaining} == {keep}

async def test_search_against_unreachable_store_raises_upstream_error() -> None:
    dead = AsyncStoreClient(url="http://127.0.0.1:1")  # nothing listening
    repo = FooRepository(client=dead, settings=FoosVectorSettings(collection="x"))

    with pytest.raises(UpstreamError):
        await repo.search(query_vector=[0.0, 0.0, 0.0], k=1)
```

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

## Rules

Follow `test-principles` for the testing constitution. Follow `naming` for names and `exception-catalog` for the error catalogue and boundary translation.

### Relational

1. **Every test takes the rollback-scoped session factory the integration setup owns (`sf`) and opens nothing of its own.** That fixture is what makes the database empty at test start and discards every write at teardown. A test that builds its own session factory, connection or engine writes outside the outer transaction, so its rows survive into the next test and the failure surfaces somewhere else entirely. No marker, no second database fixture.
2. Follow `test-principles` for the `_<aggregate>()` builder form. Defaults must be valid; no-override construction succeeds.
3. Follow `test-principles` for natural-key test values. Rollback isolation guarantees an empty DB; `name="alpha"` is safe across tests.
4. **`assert exc.value.context["constraint"] == "<constraint_name>"` on every `ConflictError`.** This is the only place the `IntegrityError`-to-domain-exception translator's name map is exercised end-to-end — the fake-based unit-test path can't verify it.
5. **Insert AND update paths for every unique field.** The bug class "translator handles INSERT but not UPDATE" only surfaces when both are tested. Skipping the update test is the most common gap in repository contracts.
6. **Assert the update timestamp did not go backwards, not that it strictly advanced.** Where the store's clock is transaction-scoped — Postgres `now()` is — two writes inside one test can carry the identical value, so `>` flakes against a correct implementation. `>=` still reds a column that is never written at all, which is the defect the test is for.
7. **Every cascade gets its own test.** Follow `naming`; the test form is `test_cascade_delete_removes_<child>`. Test the count after parent-delete is zero — only this proves the schema's `ON DELETE CASCADE` works.
8. **Every `get_by_<field>` gets both a found and a not-found test.** For case-sensitivity-sensitive fields, add a mixed-case test that asserts the documented behavior.
9. Follow `test-principles` for collection assertion strength. The rollback fixture gives this repository test an empty DB.
10. **No raw INSERTs for seed data on the table under test.** Drive setup through the repository's own `create`. **The ban is scoped to the repository under test** — a contract test that seeds behind its own subject proves nothing about the subject. A test whose subject is not the repository (an endpoint test, say — see `hex-test-restapi-endpoint`) may seed with a raw INSERT; that is legitimate setup, not a bypass. Cross-aggregate seed rows (a referenced `Bar` for a `Foo` test) may use raw INSERT when no `BarRepository.create` is in scope — or inject the bar's repo and use it.
11. **No web framework, no HTTP client, no DI container in this file.** The test imports the repository class, takes the session factory, calls methods and asserts. Reaching the adapter through a route tests the route as well, and a failure no longer says which of the two is broken; the HTTP surface is `hex-test-restapi-endpoint`'s.
12. **A test that moves the schema cannot share the fixture that assumes the schema is already at head.** Migration regressions live in their own flat files (`tests/integration/postgres/test_<NNNN>_migration.py`), take the database settings and drive the migration runner (`run_alembic`) directly, so they are free to downgrade and upgrade. An ordinary repository test is not: it assumes head, and a downgrade underneath it takes the rest of the file with it.

### Client-style store

13. **Each test runs against the real store via testcontainers** — never a fake, never a mock. The fake (`hex-test-application-handler`) is for handler unit tests; this layer exists to prove the adapter against the actual backend, which is the only place the SDK call shape and error mapping are exercised.
14. **Isolate by a per-test namespace, not rollback.** A fresh collection / key-prefix / database per test, created in the `store` (or equivalently-named) fixture and dropped at teardown. There is no transaction to roll back; do not reach for `sf`.
15. **The container is session-scoped; the namespace is function-scoped.** One store per run, because starting it is expensive; one namespace per test, because that is what gives each test sole ownership. Where the environment supplies the store instead of the fixture starting one, the endpoint is read from a **dedicated opt-in variable**, never an ambient one like `CI` — `test-principles` reliability rules.
16. **Exercise the full protocol**, CRUD verbs and non-CRUD alike — `add_many`/`get`/`delete` AND the store's own verbs (`search`, `delete_by_<field>`, range/scan). A `search` test asserts ordering (nearest-first / score-ordered), not just membership.
17. **Assert the entity↔record mapping round-trips.** What was written comes back as the same entity (ids, payload fields, and — when the read path hydrates it — the vector). A returned scored pair asserts both the entity and that the score is a real `float`, not a placeholder.
18. **Assert the SDK-error → domain-exception translation end-to-end.** This is the load-bearing contract (the client-store analogue of the relational `context["constraint"]` assertion): point the repository at an unreachable/closed client, or trigger a store rejection, and assert the boundary raises the domain exception the adapter promises — `UpstreamError` for a network / store failure, `NotFoundError` for an absent record — never the raw SDK exception. These are the domain exceptions `hex-store-repository` translates into at its boundary (shown here as placeholders); assert whichever ones that adapter actually raises, not a frozen literal. Assert the `context` keys the adapter promises.
19. Follow `test-principles` for natural-key test values. Namespace isolation gives each test an empty store at start (same as the relational contract's rollback guarantee).
20. **Small test vectors.** Use a tiny dimension (e.g. 3) created on the per-test collection; the production embedding dimension is a settings concern, not the contract's.
21. **No web framework, no HTTP client, no DI container in this file either** (rule 11). Import the repository class, construct it with the real client and a settings object scoped to the per-test namespace, call methods, assert.
22. **No assertions on global store contents.** Assert only within this test's namespace — exactly the `s3_prefix` discipline, because cleanup is namespace-scoped, not transactional.

## Inlined typing / import rules

- `pytest`, `sqlalchemy.ext.asyncio`, stdlib `uuid`, `myapp.domain.*`, `myapp.infrastructure.postgres.repositories.*`. No `myapp.application.*`, no `myapp.restapi.*`.
- Full annotations on every test signature including `sf: async_sessionmaker[AsyncSession]`.
- Builder `_<aggregate>()` returns the entity type; overrides keyword-only.
- No `from __future__ import annotations`.

For a client-style store, the store's own SDK and `myapp.infrastructure.<store-kind>.*` — `store_sdk`
and `myapp.infrastructure.store.*` in the template above stand in for whatever the profile names —
replace the SQLAlchemy and Postgres imports; the `store` fixture is annotated with its
`tuple[<Client>, str]` shape, and a yielding fixture uses `AsyncIterator[T]` / `Iterator[T]`.

## Hard stops

- `tests/integration/conftest.py` missing or `sf` not provided → stop, use `hex-test-integration-setup`.
- Spec asks for `@pytest.mark.integration` or `@pytest.mark.asyncio` → stop, use `test-principles`.
- Spec asks the test to `dispose_engine` / start its own connection / instantiate `async_sessionmaker(bind=engine)` directly → stop, that bypasses rollback; use `sf`.
- Spec asks to assert on `len(items) == N + 1` or use `any(...)` defensively → stop, use `test-principles`.
- Spec asks to assert on `ConflictError` without checking `context["constraint"]` → stop, the constraint-name map is the load-bearing contract this test exists to pin.
- Spec adds raw INSERT for seed data on the table under test, **in a test of that repository** → stop, drive setup through `repo.create`; seeding behind the subject proves nothing about it.
- Spec includes FastAPI / `httpx` / DI container references → stop, use `hex-test-restapi-endpoint`.
- Spec asks to run Alembic from this test → stop, that's a migration regression test in a separate flat file.
- Spec uses `uuid4().hex[:8]` suffixes "to avoid duplicate-key flakes" → stop, use `test-principles`; rollback removes the need.
- Spec asks to use `sf` / transaction rollback for a client store → stop, there is no nested transaction; isolate by per-test namespace + teardown.
- Spec asks to mock the store SDK or assert against a fake → stop, use `hex-test-application-handler` at the handler-unit layer; this layer drives the real backend.
- Spec asserts on `ConflictError` + `context["constraint"]` → stop, that is the relational `IntegrityError` contract; a client store asserts the domain exceptions its adapter translates SDK errors into (`UpstreamError` / `NotFoundError`) instead.
- Spec asserts on store contents outside the test's own namespace → stop, assert only within the per-test collection/prefix.
