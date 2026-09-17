---
name: hex-test-application-handler
description: Use when unit-testing a CQRS command or query handler against in-memory fakes, or when writing one of those fakes — this skill owns `tests/unit/fakes/`, so a request for a fake repository or a fake `ICan<Verb>` capability lands here rather than on either adapter-test skill. Also covers failure injection through an inline `_RaiseXxxRepo` subclass. Not the real adapter against a real backend (`hex-test-repository-contract`, `hex-test-capability-adapter`) nor the handler over HTTP (`hex-test-restapi-endpoint`).
---

# Hex Test — Application Handler (unit)

Consult `test-principles` for the testing constitution. Where this skill contradicts `test-principles`, the constitution wins.

Produces one unit-test file per handler module. Runs in milliseconds against in-memory fakes. Coverage targets the happy path plus every domain exception the handler propagates and — for compensating-transaction handlers — the post-failure undo.

## When to use vs. neighbours

- A new or modified handler under `application/<subdomain>/`, or a fake it needs under `tests/unit/fakes/` → this skill (write the fake first).
- A fake for a capability port (`ICan<Verb>`) as much as for a repository (`IFooRepository`) → this skill; it owns both, which is why a bare "write me a fake" lands here and not on an adapter-test skill.
- One-off failure injection for a single handler test → this skill — declare a `_RaiseXxxRepo(FakeFooRepository)` subclass at the handler test module scope instead of extending the fake.
- A test that drives the handler through the HTTP surface → `hex-test-restapi-endpoint` (integration, not unit); as an authenticated caller → `hex-test-restapi-auth`.
- A test for a domain entity, value object, enum or service → `hex-test-domain`.
- A real-backend test of the repository the fake stands in for → `hex-test-repository-contract`; of a capability adapter → `hex-test-capability-adapter`. The fake's exception contract is copied verbatim from whichever of those pins it.
- The real adapter itself → `hex-persistence` (relational), `hex-store-repository` (client store) or `hex-capability-adapter`.
- The domain protocol the fake matches → `hex-domain-ports`; the handler under test → `hex-application`.
- Any container, engine or session fixture — this layer has none and needs none → `hex-test-integration-setup`.
- The substitution ladder that permits a fake at all, and the no-mocks rule → `test-principles`.

## Template(s) — pytest, hand-written in-memory fakes

### Handler unit-test file location

```
tests/unit/application/
└── test_<verb>_<noun>_handler.py        # mirrors the handler module's filename
```

One file per handler. Compensating-tx assertions live in the file for the handler that performs the compensation, not in a separate file.

### `create` handler

```python
import uuid

import pytest

from myapp.application.foos import CreateFooCommand, CreateFooHandler
from myapp.domain.exceptions import ConflictError
from tests.unit.fakes.fake_foo_repository import FakeFooRepository

_CALLER = uuid.uuid4()

async def test_assigns_uuid_and_stores() -> None:
    repo = FakeFooRepository()
    handler = CreateFooHandler(repo=repo)

    foo_id = await handler.execute(CreateFooCommand(caller_id=_CALLER, name="alpha"))

    assert foo_id is not None
    stored = await repo.get_by_id(foo_id)
    assert stored.name == "alpha"
    assert stored.id == foo_id

async def test_duplicate_name_raises_conflict() -> None:
    repo = FakeFooRepository()
    handler = CreateFooHandler(repo=repo)
    await handler.execute(CreateFooCommand(caller_id=_CALLER, name="alpha"))

    with pytest.raises(ConflictError) as exc:
        await handler.execute(CreateFooCommand(caller_id=_CALLER, name="alpha"))

    assert exc.value.context["constraint"] == "uq_foos_name"

async def test_name_is_stripped_on_create() -> None:
    repo = FakeFooRepository()
    handler = CreateFooHandler(repo=repo)

    foo_id = await handler.execute(CreateFooCommand(caller_id=_CALLER, name="  alpha  "))

    stored = await repo.get_by_id(foo_id)
    assert stored.name == "alpha"
```

### `update` handler — PATCH `None`-means-don't-touch (the most common bug catch)

```python
async def test_partial_update_leaves_unspecified_fields_untouched() -> None:
    repo = FakeFooRepository()
    create_handler = CreateFooHandler(repo=repo)
    update_handler = UpdateFooHandler(repo=repo)
    foo_id = await create_handler.execute(
        CreateFooCommand(caller_id=_CALLER, name="alpha", sort_order=5),
    )

    await update_handler.execute(
        UpdateFooCommand(caller_id=_CALLER, id=foo_id, name="beta", sort_order=None),
    )

    stored = await repo.get_by_id(foo_id)
    assert stored.name == "beta"
    assert stored.sort_order == 5  # None on the command means "don't touch"

async def test_update_unknown_id_raises_not_found() -> None:
    handler = UpdateFooHandler(repo=FakeFooRepository())

    with pytest.raises(NotFoundError):
        await handler.execute(
            UpdateFooCommand(caller_id=_CALLER, id=uuid.uuid4(), name="x"),
        )
```

### `delete` handler with one-off `InUseError`

```python
class _RaiseInUseFooRepo(FakeFooRepository):
    async def delete(self, id: uuid.UUID) -> None:
        raise InUseError(
            "foo is used by one or more bars",
            {"reference_type": "foo", "id": str(id)},
        )

async def test_delete_propagates_in_use_error() -> None:
    target_id = uuid.uuid4()
    handler = DeleteFooHandler(repo=_RaiseInUseFooRepo(items=[
        Foo(id=target_id, name="alpha"),
    ]))

    with pytest.raises(InUseError) as exc:
        await handler.execute(DeleteFooCommand(caller_id=_CALLER, id=target_id))

    assert exc.value.context["reference_type"] == "foo"
    assert exc.value.context["id"] == str(target_id)
```

### `list` query handler — sort + pagination

```python
async def test_sorted_by_sort_order_then_name() -> None:
    repo = FakeFooRepository(items=[
        Foo(id=uuid.uuid4(), name="b", sort_order=1),
        Foo(id=uuid.uuid4(), name="a", sort_order=1),
        Foo(id=uuid.uuid4(), name="c", sort_order=0),
    ])
    handler = ListFoosHandler(repo=repo)

    # Three rows seeded, page size 2 — the page must be smaller than the seeded
    # set or the test proves nothing about paging (Rule 4).
    result = await handler.execute(ListFoosQuery(filter=FooListFilter(limit=2)))

    assert [f.name for f in result.items] == ["c", "a"]
    assert result.total == 3
```

**Seed 3, page 2 — the page size is smaller than the seeded set on purpose.** At `limit=10` over
three rows the page holds every match, so the same asserts pass a handler that never applies the
bound and one that returns `len(items)` as `total`. 3 and 2 are the smallest pair that reds both.

### `compensating-tx` handler — upload, then DB fails, assert undo

```python
class _RaiseAfterUploadRepo(FakeFooRepository):
    async def create(self, foo: Foo) -> None:
        raise RuntimeError("simulated DB failure after blob upload")

async def test_db_failure_after_upload_deletes_blob() -> None:
    repo = _RaiseAfterUploadRepo()
    storage = FakeBlobStorage()
    handler = UpsertFooHandler(repo=repo, storage=storage)

    with pytest.raises(RuntimeError):
        await handler.execute(
            UpsertFooCommand(caller_id=_CALLER, data=b"payload", ...),
        )

    # Compensation contract: the blob written before the failed DB step
    # must have been deleted via the best-effort cleanup capability.
    assert len(storage.puts) == 1
    assert storage.deletes == [storage.puts[0][0]]  # exactly the uploaded key
```

The simulated exception type is incidental — `RuntimeError` here, or any uncaught exception. The contract is: **the put landed, then something failed, then the same key was deleted.** That's the compensation assertion.

## Fake repository and capability templates

Produces one in-memory stand-in class for a domain protocol. Handler unit tests under `tests/unit/application/` use this fake instead of the real `infrastructure/` adapter. The fake satisfies the protocol **structurally** — no `(IFooRepository)` inheritance, no `@runtime_checkable` registration.

### File location and naming

```
tests/unit/fakes/
└── fake_<aggregate_snake>_repository.py        # class FakeFooRepository
```

For capabilities: `fake_<capability_snake>.py` → `Fake<Capability>` (e.g. `fake_blob_storage.py` → `FakeBlobStorage`).

Follow `python-packaging` and the fake-specific inlined import rules below. Handler tests import directly:

```python
from tests.unit.fakes.fake_foo_repository import FakeFooRepository
```

This is deliberate: keeps fakes out of production import graphs.

### CRUD repository fake

```python
from collections.abc import Sequence
from dataclasses import replace
from uuid import UUID

from myapp.domain.exceptions import ConflictError, NotFoundError
from myapp.domain.foos import Foo, FooListFilter

class FakeFooRepository:
    def __init__(self, items: list[Foo] | None = None) -> None:
        # Store DETACHED copies; never alias the caller's instances (see Rule 9).
        self._store: dict[UUID, Foo] = {f.id: replace(f) for f in (items or [])}
        self.updated: list[UUID] = []  # call record — ids passed to update(), in order

    async def list(self, *, filter: FooListFilter) -> Sequence[Foo]:
        ordered = sorted(
            self._store.values(),
            key=lambda f: (f.sort_order, f.name),
        )
        return [replace(f) for f in ordered[filter.offset : filter.offset + filter.limit]]

    async def count(self, *, filter: FooListFilter) -> int:
        return len(self._store)

    async def get_by_id(self, id: UUID) -> Foo:
        if id not in self._store:
            raise NotFoundError("Foo not found", {"id": str(id)})
        return replace(self._store[id])  # a copy — a caller mutation must not leak into the store

    async def get_by_name(self, name: str) -> Foo | None:
        match = next((f for f in self._store.values() if f.name == name), None)
        return replace(match) if match is not None else None

    async def create(self, foo: Foo) -> None:
        if any(f.name == foo.name for f in self._store.values()):
            raise ConflictError(
                "foo name already exists",
                {"constraint": "uq_foos_name"},
            )
        self._store[foo.id] = replace(foo)

    async def update(self, foo: Foo) -> None:
        if foo.id not in self._store:
            raise NotFoundError("Foo not found", {"id": str(foo.id)})
        if any(f.name == foo.name and f.id != foo.id for f in self._store.values()):
            raise ConflictError(
                "foo name already exists",
                {"constraint": "uq_foos_name"},
            )
        self._store[foo.id] = replace(foo)
        self.updated.append(foo.id)  # so a "mutate-but-never-persist" handler is observably caught

    async def delete(self, id: UUID) -> None:
        if id not in self._store:
            raise NotFoundError("Foo not found", {"id": str(id)})
        del self._store[id]
```

### Aggregate with cascading sub-collection

```python
class FakeFooRepository:
    def __init__(self, foos: list[Foo] | None = None) -> None:
        self._store: dict[UUID, Foo] = {f.id: f for f in (foos or [])}
        self._attachments: dict[UUID, FooAttachment] = {}

    async def add_attachment(self, foo_id: UUID, attachment: FooAttachment) -> None:
        if foo_id not in self._store:
            raise NotFoundError("Foo not found", {"id": str(foo_id)})
        self._attachments[attachment.id] = attachment

    async def delete(self, id: UUID) -> None:
        if id not in self._store:
            raise NotFoundError("Foo not found", {"id": str(id)})
        # Replay the schema's ON DELETE CASCADE
        cascaded = [a_id for a_id, a in self._attachments.items() if a.foo_id == id]
        for a_id in cascaded:
            del self._attachments[a_id]
        del self._store[id]
```

### Behavioral capability (`ICanDoX`) — single async method

```python
from myapp.domain.foos import FooExportRow

class FakeExportFoosXlsx:
    def __init__(self, payload: bytes = b"fake-xlsx") -> None:
        self._payload = payload
        self.exported: list[Sequence[FooExportRow]] = []

    async def export(self, rows: Sequence[FooExportRow]) -> bytes:
        self.exported.append(tuple(rows))
        return self._payload
```

Behavioral fakes expose a call-record list (`self.exported`) so handler tests can assert what was invoked. Prefer asserting on resulting domain state when possible; reach for call records only when call shape is the thing under test.

### Storage gateway with a call-record observation surface

A storage fake records what it was asked to do (puts / deletes) so compensating-transaction tests can assert the `*_best_effort` cleanup ran — no failure-injection flags, just observable call records:

```python
class FakeBlobStorage:
    def __init__(self) -> None:
        self.puts: list[tuple[str, bytes]] = []
        self.deletes: list[str] = []

    async def put(self, key: str, data: bytes) -> None:
        self.puts.append((key, data))

    async def delete_many_best_effort(self, keys: list[str]) -> None:
        # Swallows internal errors; mirrors the real best-effort contract.
        self.deletes.extend(keys)
```

The `puts` and `deletes` lists are the test-side observation surface. **No `fail_next_call=...` flags**: a test that needs the DB write *after* an upload to fail uses an inline `_RaisingFooRepo(FakeFooRepository)` at the test scope, not a flag on the storage fake.

## Rules

Consult `test-principles` for the testing constitution, `naming` for names, `python-style` for typing, logging and comments, `python-packaging` for packaging and imports, and `exception-catalog` for the error catalogue and boundary translation.

### Handler tests

1. Test function and marker conventions follow `test-principles`.
2. **`_CALLER = uuid.uuid4()` at module scope** so command construction stays terse. The templates show the **authenticated** form: `caller_id=_CALLER` is passed because the command carries `caller_id`. For a command in an app that declares no auth (or dispatched only by anonymous routes), the command has no `caller_id` field — drop the `caller_id=_CALLER` argument and the `_CALLER` constant (mirrors `hex-application`'s auth-derived-fields rule: a command reached only by anonymous routes omits `caller_id` entirely). `_CALLER` is the authenticated-form convention, not a blanket one.
3. **AAA structure follows `test-principles`.** Arrange — construct fake(s) and handler. Act — call `handler.execute(...)`. Assert — read state back through the fake or assert raised exception.
4. **The handler is constructed inside each test, not in a fixture.** Handlers are cheap to build; per-test instantiation keeps each test self-contained.
5. **Read state back via fake's domain methods** (`await repo.get_by_id(...)`), not via attribute peeking on `repo._store`.
6. **Drive setup through the handler path that production uses** when possible. An update-handler test calls `CreateFooHandler` first to set up an "existing" foo, rather than `repo.create(...)`. This keeps tests robust to repository-contract changes.
7. **A failure case pins the exception's machine-readable context, not just its class.** Capture the raised catalogue exception (`pytest.raises(<DomainExceptionType>) as exc`) and assert the `context` entries that are the contract — above all the constraint name on a conflict, which is what proves the adapter's integrity-error map is wired even though the test runs against a fake, because the fake's exception is copied from the real adapter's. Asserting the class alone passes against a fake that raises the right type with the wrong payload.
8. **Compensation tests assert call-record state**, not implementation details. For a storage capability, `storage.puts` and `storage.deletes` are the observation surface. Assert the right key was undone, in the right order, for the right reason — but never assert that a specific Python call site invoked them.
9. **One-off failure injection uses an inline `_RaiseXxxRepo(FakeFooRepository)` subclass at module scope.** Subclass naming follows `naming`. Override exactly the method under test — never re-stub the whole protocol.
10. **A handler dependency typed as a CONCRETE domain service (not a Protocol) cannot be faked structurally — subclass it.** Repositories/capabilities are injected as `Protocol`s, so a structural fake satisfies them. A domain *service* is often injected as its concrete class (`def __init__(self, limit_policy: FooLimitPolicy)`), and mypy rejects a structural `FakeFooLimitPolicy` there — a stand-in must be a true subtype. Two sanctioned shapes: (a) **subclass the service** — `class _StubFooLimitPolicy(FooLimitPolicy)` overriding the method under test and bypassing the real `__init__` (`def __init__(self) -> None: pass`, since the test doesn't need its injected deps); or (b) **inject via a Protocol** — give the service a `hex-domain-ports`-style interface and type the handler ctor to it, so a structural fake works like any other. Prefer (b) when the service is itself injected widely; (a) is the lighter test-only path. Do NOT reach for `# type: ignore` on the ctor or a mock — silencing the type checker hides that the handler's dependency surface is the thing that needs fixing.

### Assert strength on a handler over fakes

The recipes that hold for any test — assert a survivor rather than an empty result, seed a second row where one cannot prove scoping, pick a non-constant input for an echoed field, assert no side effect on a reject path, and exercise a non-boundary case as well as the boundary — are `test-principles`'. Two are specific to a handler driven through in-memory fakes:

1. **Pin PERSISTED state, not the in-memory entity.** Assert the write happened via the fake's `updated` call-record (`assert repo.updated == [id]`) AND read the value back (`(await repo.get_by_id(id)).status == DONE`). The fake returns a COPY and records updates (the `Fakes` rules below), so a body that mutates the entity but never calls `update()` **reds**. Asserting on the entity object the handler mutated in place pins nothing (it observes the in-memory mutation, not the persist).
2. **Distinguish `total` from `len(items)` with page size < match count.** A paged-list test where the page holds every match passes a body that returns `len(items)` as the total. Seed more rows than the page size so a `total = len(page)` bug reds.

### Coverage checklist (one `test_*` per case — `test-principles` owns when not to parametrize)

#### `create` handler

- `test_assigns_uuid_and_stores` — handler returns a `UUID`; `get_by_id` returns the entity with expected fields and that same id.
- `test_duplicate_<unique_field>_raises_conflict` — for every uniqueness constraint enforced by the repo, assert `ConflictError` on the second attempt with `exc.value.context["constraint"] == "<full_constraint_name>"`.
- Field normalization (when applicable): assert the stored entity has the normalized form (`strip`, `upper`, canonicalized URL), not the raw input.

#### `update` handler

- `test_partial_update_leaves_unspecified_fields_untouched` — set one field with a real value and another with `None`; assert the `None` field is **unchanged** and the real field is updated. This is the PATCH contract and the single most common bug-catching test.
- `test_update_unknown_id_raises_not_found`.
- `test_update_duplicate_<unique_field>_raises_conflict` — renaming row B to row A's name raises `ConflictError`.

#### `delete` handler

- `test_delete_removes` — happy path; `get_by_id` after delete raises `NotFoundError`.
- `test_delete_unknown_id_raises_not_found`.
- `test_delete_<resource>_in_use_propagates` — for referenceable resources, use the inline `_RaiseInUseFooRepo` subclass; assert `InUseError` propagates with the correct `context["reference_type"]`.

#### `get` / single-read query handler

- `test_returns_entity_when_present` — load the fake with one entity; the handler returns it intact.
- `test_returns_none_or_raises_when_absent` — match the handler's contract (`Entity | None` returns `None`; `Entity` returns raises `NotFoundError`).

#### `list` query handler

- `test_sorted_by_<order_key>` — load the fake with deliberately unsorted entities (vary both primary and secondary sort keys); assert the order of `result.items` is exactly the expected sequence.
- `test_pagination_offset_limit` — load N > limit entities; call with `limit=L, offset=O`; assert `len(result.items) == L` and `result.total == N`.

#### `compensating-tx` handler

- `test_db_failure_after_upload_deletes_blob` — fake repo's mutation step raises; assert `storage.deletes` contains the keys `storage.puts` recorded immediately before the failure.
- `test_db_failure_after_multi_step_upload_deletes_all_uploaded_so_far` — when the upload step accumulates multiple keys before the DB write, simulate failure mid-loop or after the loop; assert every key that was uploaded got passed to `delete_many_best_effort`.
- `test_successful_upsert_cleans_up_previous_blob` — for upsert handlers that return a `previous_key`, the success-path cleanup deletes the *old* key (not the new one); use the regular happy-path setup and assert `storage.deletes` contains the previous key after the second call.

### Hard prohibitions (across all handler-unit tests)

- **No mocks for protocol substitution** — apply `test-principles`. Use a fake from `tests/unit/fakes/`, or extend it via an inline `_RaiseXxxRepo` subclass.
- Test markers follow `test-principles`.
- **No fixtures from `tests/integration/`.** No database, no real app, no auth fixtures, no blob store.
- **No assertions on what the handler logged** — `test-principles` owns the rule; here it bites because a handler that logs the right success event and never calls `update()` would otherwise pass. Assert the returned value and the persisted state. Which layer may log at all → `python-style`.
- Timing and unit-test isolation follow `test-principles`. The whole file should run in well under a second.
- **No business-logic re-implementation in the test.** Don't compute the expected slug, normalize the name, or sort items the way the domain entity does — let the handler produce the output and assert against it.

### Fakes

1. **No inheritance from the protocol.** Structural matching is verified by the type checker.
2. **One state field per collection** — `self._store: dict[UUID, <Entity>]` keyed by id. No secondary indexes, no shadow caches. Queries scan the dict — the data set is tiny.
3. **Constructor takes `items: list[<Entity>] | None = None`** with `or []` fallback so the empty-fake call site is terse: `FakeFooRepository()`.
4. **Every method is `async def`**, even when there's nothing to await — the protocol says async; the fake matches.
5. **`list(*, filter: <FilterRecord>)` is keyword-only** and applies a deterministic sort matching the real repository's `ORDER BY`. Handler tests assert exact order — sort, don't return insertion order.
   - **A fake method MUST honour every filtering / scoping parameter it declares — never ignore one.** If the method takes a `since` / `tenant_id` / status-set / parent-id, the fake actually filters its `_store` by it (`v for v in self._store.values() if v.created_at >= since and v.tenant_id == tenant_id`). A fake that accepts `count_created_since(since)` but returns the all-time count makes the "monthly vs all-time" contract **uncatchable** — the assert for it can never be strong (this has been hit in practice). The fake's filtering need not be efficient, just correct: a wrong body that ignores the same parameter must produce a different result against the fake.
6. **The exception contract is copied verbatim from the real adapter.** Same class, same message, same `context` keys — exactly what `_map_integrity_error` populates and no more. The relational adapter raises `ConflictError("foo name already exists", {"constraint": "uq_foos_name"})` — context carries **only** `constraint`, so the fake matches it exactly. Adding a key the real adapter never sets (e.g. `"name"`) is the silent drift this rule exists to prevent: a handler test asserting that key passes against the fake and fails against the real adapter.
7. **Cascades match the schema.** When the real schema has `ON DELETE CASCADE`, the fake removes the dependent rows. Skipping the cascade in the fake produces a green unit test that a failing integration test then catches — defeats the point.
8. **Default-happy-path only.** No `fail_next_create=True` flags or `_should_raise` knobs. Tests needing one-off failures declare a private subclass at the **handler test module scope**, which is this skill's pattern:

   ```python
   class _RaiseInUseFooRepo(FakeFooRepository):
       async def delete(self, id: UUID) -> None:
           raise InUseError("foo is used", {"reference_type": "foo", "id": str(id)})
   ```

   The storage-gateway `puts` / `deletes` call records are the only sanctioned per-call observation surface — and they observe, they do not inject failure. A test that needs an injected failure uses the inline-subclass pattern above, not a flag or a hook on the fake.

9. **Never hand back the object the caller passed in — copy on write and on read, and record every `update()`.** The real repository round-trips through the database: a mutation is persisted **only** by an explicit `update()`, and a later read returns the persisted row, not the caller's object. A fake that stores and returns the same instance aliases it, so a handler that mutates the entity **in place and never calls `update()`** still sees its change on the next read — the mutate-but-never-persist bug passes green and no persistence assertion can pin it. So copy on write (`self._store[id] = replace(foo)`) and on read (`return replace(self._store[id])`) — a shallow copy via `dataclasses.replace`, deep only when a field is itself mutable and the test mutates through it — and keep an `updated: list[UUID]` call record. Handler tests then pin persistence twice, that `update` was called and that the new state reads back, and a body that forgets it reds both.

### What a fake must not do

- **No mocks** — apply `test-principles`. A fake is a hand-written class.
- **No production imports beyond `myapp.domain`.** Fakes import domain entities, value objects, enums, and exceptions. Never `myapp.infrastructure`, `myapp.application`, `myapp.restapi`.
- **No IO** — apply `test-principles` for isolation and determinism.
- **No third-party imports** other than what stdlib + `myapp.domain` + `pytest` require.
- **No state retained across instances.** No class variables, no module-level caches. Each `FakeFooRepository()` constructs a fresh `_store`.
- Packaging follows `python-packaging` and the fake-specific inlined import rules below.

## Inlined typing / import rules

### Handler tests

- Stdlib (`uuid`, `datetime`), `pytest`, `myapp.application.*`, `myapp.domain.exceptions`, `myapp.domain.<subdomain>`, `tests.unit.fakes.*` only.
- `X | None`, full annotations on every fixture, builder, and inline subclass `__init__`.
- No `from __future__ import annotations`.

### Fakes

- Stdlib (`collections.abc`, `uuid`), `myapp.domain.*` only. **No `__all__`, no `__init__.py` re-export.** Direct import only.
- `X | None`, full annotations on `__init__` and every method.
- No `from __future__ import annotations`.

## Hard stops

- Spec asks for `MagicMock` to stub the repo or storage → stop, use a fake or an inline `_RaiseXxxRepo` subclass.
- Spec needs the test to hit a real database or HTTP endpoint → stop, use `hex-test-repository-contract` or `hex-test-restapi-endpoint`.
- Spec asks for log assertions on the handler's success event → stop, those are side effects; tests assert on returned state.
- Required fake does not exist in `tests/unit/fakes/` → stop, produce it first using the fake templates in this skill.
- Spec asks to add `fail_next_create=True`-style flags to the fake → stop, use the inline subclass at the test module scope instead.
- Spec asks the test to construct the FastAPI app or import `myapp.restapi.*` → stop, use `hex-test-restapi-endpoint` for the HTTP surface.
- Spec asks to fake a handler's **concrete domain-service** dependency (e.g. `FooLimitPolicy`, injected as the class, not a Protocol) → stop, a structural fake won't type-check there; **subclass the service** (override the method under test, bypass `__init__`) or have the handler **inject via a Protocol**. Repository and capability fakes are structural because their dependencies are `Protocol`s; a concrete service is not, which is rule 10 above.
- Spec asks to register the fake with `@runtime_checkable` / `isinstance` → stop, type checking is enough.
- Spec asks to add failure-injection flags to a repository fake → stop, use the inline-subclass pattern at the handler test module scope instead.
- Spec asks to model `InUseError` in the default repository fake → stop, that's an inline subclass case at the test site (cross-aggregate references aren't modeled in-memory).
- Real adapter's exception contract cannot be located → stop, the fake's contract is copied, not invented.
- A handler test needs a fake that does not exist under `tests/unit/fakes/` → stop, write it with
  this skill. Do not improvise a stand-in at the test site, do not reach for a mock, and do not
  weaken the assertion to avoid needing it. A missing fake is a stop, not an invitation to improvise —
  the whole point of the fake is that its exception contract matches the real adapter's, and an
  improvised stub silently does not.
- Spec uses `MagicMock` / `AsyncMock` to "implement" the fake → stop, hand-write the class.
- Spec adds `__all__` or an `__init__.py` re-export → stop, use `python-packaging` and the fake-specific inlined import rules above.
