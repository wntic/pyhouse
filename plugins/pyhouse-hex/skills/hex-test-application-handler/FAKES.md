# hex-test-application-handler — the fakes

Topic file of `hex-test-application-handler`. The obligations are `### Fakes` and
`### What a fake must not do` in `SKILL.md`; what follows is the hand-written in-memory binding that
satisfies them.

## CRUD repository fake

```python
from collections.abc import Sequence
from dataclasses import replace
from uuid import UUID

from myapp.domain.exceptions import FooConflictError, NotFoundError
from myapp.domain.foos import Foo, FooListFilter, FooSort

__all__ = ["FakeFooRepository"]


class FakeFooRepository:
    def __init__(self, items: list[Foo] | None = None) -> None:
        # Store DETACHED copies; never alias the caller's instances (Fakes rule 9).
        self._store: dict[UUID, Foo] = {f.id: replace(f) for f in (items or [])}
        self.updated: list[UUID] = []  # call record — ids passed to update(), in order

    async def list(self, *, filter: FooListFilter) -> Sequence[Foo]:
        # The real ORDER BY per sort key; insertion order stands in for creation order.
        matching = self._matching(filter)
        ordered: Sequence[Foo]
        if filter.sort is FooSort.NAME_ASC:
            ordered = sorted(matching, key=lambda f: f.name)
        elif filter.sort is FooSort.CREATED_AT_DESC:
            ordered = matching[::-1]
        else:
            ordered = matching
        return [replace(f) for f in ordered[filter.offset : filter.offset + filter.limit]]

    async def count(self, *, filter: FooListFilter) -> int:
        return len(self._matching(filter))

    def _matching(self, filter: FooListFilter) -> Sequence[Foo]:
        # One condition per scoping field the filter declares, as the real WHERE applies it.
        return [f for f in self._store.values() if not filter.bar_ids or f.bar_id in filter.bar_ids]

    async def get_by_id(self, id: UUID) -> Foo:
        if id not in self._store:
            raise NotFoundError("Foo not found", {"id": str(id)})
        return replace(self._store[id])  # a copy — a caller mutation must not leak into the store

    async def get_by_name(self, name: str) -> Foo | None:
        match = next((f for f in self._store.values() if f.name == name), None)
        return replace(match) if match is not None else None

    async def create(self, foo: Foo) -> None:
        if any(f.name == foo.name for f in self._store.values()):
            raise FooConflictError(
                "foo name already exists",
                {"field": "name", "constraint": "uq_foos_name"},
            )
        self._store[foo.id] = replace(foo)

    async def update(self, foo: Foo) -> None:
        if foo.id not in self._store:
            raise NotFoundError("Foo not found", {"id": str(foo.id)})
        if any(f.name == foo.name and f.id != foo.id for f in self._store.values()):
            raise FooConflictError(
                "foo name already exists",
                {"field": "name", "constraint": "uq_foos_name"},
            )
        self._store[foo.id] = replace(foo)
        self.updated.append(foo.id)  # so a "mutate-but-never-persist" handler is observably caught

    async def delete(self, id: UUID) -> None:
        if id not in self._store:
            raise NotFoundError("Foo not found", {"id": str(id)})
        del self._store[id]
```

## Aggregate with cascading sub-collection

For an aggregate that owns children — here `FooAttachment`, an entity (`id: UUID`, `foo_id: UUID`,
`mime: str`) in `domain/foos/` whose table cascades from `foos` (`hex-persistence`'s owned-children
table). The CRUD methods above stay; the cascade adds these:

```python
from dataclasses import replace
from uuid import UUID

from myapp.domain.exceptions import NotFoundError
from myapp.domain.foos import Foo, FooAttachment

__all__ = ["FakeFooRepository"]


class FakeFooRepository:
    def __init__(self, items: list[Foo] | None = None) -> None:
        self._store: dict[UUID, Foo] = {f.id: replace(f) for f in (items or [])}
        self._attachments: dict[UUID, FooAttachment] = {}

    async def add_attachment(self, foo_id: UUID, attachment: FooAttachment) -> None:
        if foo_id not in self._store:
            raise NotFoundError("Foo not found", {"id": str(foo_id)})
        self._attachments[attachment.id] = replace(attachment)

    async def delete(self, id: UUID) -> None:
        if id not in self._store:
            raise NotFoundError("Foo not found", {"id": str(id)})
        # Replay the schema's ON DELETE CASCADE
        cascaded = [a_id for a_id, a in self._attachments.items() if a.foo_id == id]
        for a_id in cascaded:
            del self._attachments[a_id]
        del self._store[id]
```

## Behavioral capability (`ICanDoX`) — single async method

```python
from collections.abc import Sequence

from myapp.domain.foos import FooExportRow

__all__ = ["FakeExportFoosXlsx"]


class FakeExportFoosXlsx:
    def __init__(self, payload: bytes = b"fake-xlsx") -> None:
        self._payload = payload
        self.exported: list[Sequence[FooExportRow]] = []

    async def export(self, rows: Sequence[FooExportRow]) -> bytes:
        self.exported.append(tuple(rows))
        return self._payload
```

Behavioral fakes expose a call-record list (`self.exported`) so handler tests can assert what was invoked. Prefer asserting on resulting domain state when possible; reach for call records only when call shape is the thing under test.

## Storage gateway with a call-record observation surface

A storage fake records what it was asked to do (uploads / deletes) so compensating-transaction tests can assert the undo ran — no failure-injection flags, just observable call records. Its `delete` is the port's plain reversing method and succeeds like the real one; a test that needs the undo itself to fail subclasses it (`_RaiseOnDeleteStorage` in the `compensating-tx` handler template in `SKILL.md`):

```python
__all__ = ["FakeFooStorage"]


class FakeFooStorage:
    def __init__(self) -> None:
        self.uploads: list[tuple[str, bytes]] = []
        self.deletes: list[str] = []

    async def upload(self, key: str, body: bytes) -> None:
        self.uploads.append((key, body))

    async def delete(self, key: str) -> None:
        self.deletes.append(key)
```

The `uploads` and `deletes` lists are the test-side observation surface. **No `fail_next_call=...` flags**: a test that needs the DB write *after* an upload to fail uses an inline `_RaiseAfterUploadRepo(FakeFooRepository)` at the test scope, and one that needs the undo to fail an inline storage subclass — never a flag on the fake.

## The fake's copy contract, pinned once

`tests/unit/test_fake_foo_repository.py` — one test per fake that keeps state, because Fakes rule 9 is
what lets every handler test pin persistence, and nothing else would notice the fake losing it:

```python
import uuid

from myapp.domain.foos import Foo
from tests.unit.fakes import FakeFooRepository


async def test_a_mutated_entity_does_not_reach_the_store() -> None:
    foo = Foo(id=uuid.uuid4(), name="alpha", bar_id=uuid.uuid4())
    repo = FakeFooRepository(items=[foo])

    foo.name = "seeded-then-mutated"
    loaded = await repo.get_by_id(foo.id)
    loaded.name = "read-then-mutated"

    assert (await repo.get_by_id(foo.id)).name == "alpha"
```
