# hex-test-application-handler — the fakes

Topic file of `hex-test-application-handler`. The obligations are `### Fakes` and
`### What a fake must not do` in `SKILL.md`; what follows is the hand-written in-memory binding that
satisfies them.

## CRUD repository fake

```python
from collections.abc import Sequence
from dataclasses import replace
from uuid import UUID

from myapp.domain.exceptions import (
    FooConflictError,  # only where Foo has a natural key
    NotFoundError,
)
from myapp.domain.foos import Foo, FooListFilter, FooSort

__all__ = ["FakeFooRepository"]


class FakeFooRepository:
    def __init__(self, items: list[Foo] | None = None) -> None:
        # Store DETACHED copies; never alias the caller's instances.
        self._store: dict[UUID, Foo] = {f.id: replace(f) for f in (items or [])}
        self.updated: list[UUID] = []  # call record — ids passed to update(), in order

    async def list(self, *, filter: FooListFilter) -> Sequence[Foo]:
        # insertion order stands in for creation order
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
        # One condition per scoping field the filter declares.
        return [f for f in self._store.values() if filter.name is None or f.name == filter.name]

    async def get_by_id(self, id: UUID) -> Foo:
        if id not in self._store:
            raise NotFoundError("Foo not found", {"id": str(id)})
        return replace(self._store[id])  # a copy — a caller mutation must not leak into the store

    # only where Foo has a natural key
    async def get_by_name(self, name: str) -> Foo | None:
        match = next((f for f in self._store.values() if f.name == name), None)
        return replace(match) if match is not None else None

    async def create(self, foo: Foo) -> None:
        # only where Foo has a natural key
        if any(f.name == foo.name for f in self._store.values()):
            raise FooConflictError(
                "foo name already exists",
                {"field": "name", "constraint": "uq_foos_name"},  # "constraint" only with a relational adapter
            )
        self._store[foo.id] = replace(foo)

    async def update(self, foo: Foo) -> None:
        if foo.id not in self._store:
            raise NotFoundError("Foo not found", {"id": str(foo.id)})
        # only where Foo has a natural key
        if any(f.name == foo.name and f.id != foo.id for f in self._store.values()):
            raise FooConflictError(
                "foo name already exists",
                {"field": "name", "constraint": "uq_foos_name"},  # "constraint" only with a relational adapter
            )
        self._store[foo.id] = replace(foo)
        self.updated.append(foo.id)  # so a "mutate-but-never-persist" handler is observably caught

    async def delete(self, id: UUID) -> None:
        if id not in self._store:
            raise NotFoundError("Foo not found", {"id": str(id)})
        del self._store[id]
```

## Capability that returns a value

A capability whose one method returns something (`ICanClassifyFoos`, say) is faked by a class that
returns a constructor-supplied value and appends each call's arguments to a public list. Prefer asserting
the resulting domain state; reach for the call record only when the call's shape is the thing under test.

## Storage gateway with a call-record observation surface

A storage fake records what it was asked to do (uploads / deletes) so compensating-transaction tests can assert the undo ran — no failure-injection flags, just observable call records. Its `delete` is the port's plain reversing method and succeeds like the real one; a test that needs the undo itself to fail subclasses it (`_RaiseOnDeleteStorage` in the compensating-handler tests below):

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

### The compensating handler's tests — upload, then the write fails, assert the undo

The handler under test is `hex-application`'s compensating `CreateFooHandler` (`COMPENSATION.md`), whose command carries the
uploaded bytes. The file is that handler's own `tests/unit/application/test_create_foo_handler.py`.

```python
import pytest

from myapp.application.foos import CreateFooCommand, CreateFooHandler
from myapp.domain.exceptions import UpstreamError
from myapp.domain.foos import Foo
from tests.unit.fakes import FakeFooRepository, FakeFooStorage


class _RaiseAfterUploadRepo(FakeFooRepository):
    async def create(self, foo: Foo) -> None:
        raise RuntimeError("simulated DB failure after blob upload")


class _RaiseOnDeleteStorage(FakeFooStorage):
    async def delete(self, key: str) -> None:
        await super().delete(key)
        raise UpstreamError("simulated undo failure", {"key": key})


async def test_db_failure_after_upload_deletes_blob() -> None:
    storage = FakeFooStorage()
    handler = CreateFooHandler(repo=_RaiseAfterUploadRepo(), storage=storage)

    with pytest.raises(RuntimeError, match="simulated DB failure"):
        await handler.execute(CreateFooCommand(name="alpha", data=b"payload"))

    assert len(storage.uploads) == 1
    assert storage.deletes == [storage.uploads[0][0]]


async def test_failed_undo_still_raises_the_original_failure() -> None:
    storage = _RaiseOnDeleteStorage()
    handler = CreateFooHandler(repo=_RaiseAfterUploadRepo(), storage=storage)

    with pytest.raises(RuntimeError, match="simulated DB failure"):
        await handler.execute(CreateFooCommand(name="alpha", data=b"payload"))

    assert storage.deletes == [storage.uploads[0][0]]
```

The simulated exception type is incidental — `RuntimeError` here, or any uncaught exception. The
contract is: **the upload landed, then something failed, then the same key was deleted, and the caller
sees the failure that started it.** The undo raises like any other call (`hex-application`, Compensation); the second
test pins that the handler swallows the *undo's* failure and re-raises the original — an
`UpstreamError` escaping instead fails `pytest.raises(RuntimeError)`.

## The fake's copy contract, pinned once

`tests/unit/test_fake_foo_repository.py` — one test per fake that keeps state, because Fakes rule 9 is
what lets every handler test pin persistence, and nothing else would notice the fake losing it:

```python
import uuid

from myapp.domain.foos import Foo
from tests.unit.fakes import FakeFooRepository


async def test_a_mutated_entity_does_not_reach_the_store() -> None:
    foo = Foo(id=uuid.uuid4(), name="alpha")
    repo = FakeFooRepository(items=[foo])

    foo.name = "seeded-then-mutated"
    loaded = await repo.get_by_id(foo.id)
    loaded.name = "read-then-mutated"

    assert (await repo.get_by_id(foo.id)).name == "alpha"
```
