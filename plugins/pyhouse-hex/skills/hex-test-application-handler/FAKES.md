# hex-test-application-handler — the fakes

Topic file of `hex-test-application-handler`. The obligations are `### Fakes` and
`### What a fake must not do` in `SKILL.md`; what follows is the hand-written in-memory binding that
satisfies them.

## CRUD repository fake

```python
from collections.abc import Sequence  # only where the port lists
from dataclasses import replace
from uuid import UUID

from myapp.domain.exceptions import (
    FooConflictError,  # only where Foo has a natural key
    NotFoundError,
)
from myapp.domain.foos import (
    Foo,
    FooListFilter,  # only where the port lists
    FooSort,  # only where the port lists
)

__all__ = ["FakeFooRepository"]


class FakeFooRepository:
    def __init__(self, items: list[Foo] | None = None) -> None:
        # Store DETACHED copies; never alias the caller's instances.
        self._store: dict[UUID, Foo] = {foo.id: replace(foo) for foo in (items or [])}
        self.updated: list[UUID] = []  # call record — ids passed to update(), in order

    # only where the port lists
    async def list(self, *, filter: FooListFilter) -> Sequence[Foo]:
        # insertion order stands in for creation order
        matching = self._matching(filter)
        ordered: Sequence[Foo]
        if filter.sort is FooSort.NAME_ASC:
            ordered = sorted(matching, key=lambda foo: foo.name)
        elif filter.sort is FooSort.CREATED_AT_DESC:
            ordered = matching[::-1]
        else:
            ordered = matching
        return [replace(foo) for foo in ordered[filter.offset : filter.offset + filter.limit]]

    # only where the port lists
    async def count(self, *, filter: FooListFilter) -> int:
        return len(self._matching(filter))

    # only where the port lists
    def _matching(self, filter: FooListFilter) -> Sequence[Foo]:
        # One condition per scoping field the filter declares.
        return [foo for foo in self._store.values() if filter.name is None or foo.name == filter.name]

    async def get_by_id(self, id: UUID) -> Foo:
        if id not in self._store:
            raise NotFoundError("Foo not found", {"id": str(id)})
        return replace(self._store[id])  # a copy — a caller mutation must not leak into the store

    # only where Foo has a natural key
    async def get_by_name(self, name: str) -> Foo | None:
        match = next((foo for foo in self._store.values() if foo.name == name), None)
        return replace(match) if match is not None else None

    async def create(self, foo: Foo) -> None:
        # only where Foo has a natural key
        if any(stored.name == foo.name for stored in self._store.values()):
            raise FooConflictError(
                "foo name already exists",
                {"field": "name", "constraint": "uq_foos_name"},  # "constraint" only with a relational adapter
            )
        self._store[foo.id] = replace(foo)

    async def update(self, foo: Foo) -> None:
        if foo.id not in self._store:
            raise NotFoundError("Foo not found", {"id": str(foo.id)})
        # only where Foo has a natural key
        if any(stored.name == foo.name and stored.id != foo.id for stored in self._store.values()):
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

The `uploads` and `deletes` lists are the test-side observation surface. **No `fail_next_call=...` flags**: a test that needs the store write *after* an upload to fail uses an inline `_RaiseAfterUploadRepository(FakeFooRepository)` at module scope, and one that needs the undo to fail an inline storage subclass — never a flag on the fake.

### The compensating handler's tests — upload, then the write fails, assert the undo

The handler under test is `hex-application`'s compensating `CreateFooHandler` (`COMPENSATION.md`), whose command carries the
uploaded bytes. The file is that handler's own `tests/unit/application/test_create_foo_handler.py`.

```python
import pytest

from myapp.application.foos import CreateFooCommand, CreateFooHandler
from myapp.domain.exceptions import UpstreamError
from myapp.domain.foos import Foo
from tests.unit.fakes import FakeFooRepository, FakeFooStorage


class _RaiseAfterUploadRepository(FakeFooRepository):
    def __init__(self) -> None:
        super().__init__()
        self.raised: UpstreamError | None = None

    async def create(self, foo: Foo) -> None:
        self.raised = UpstreamError("the datastore could not complete the operation", {"id": str(foo.id)})
        raise self.raised


class _RaiseOnDeleteStorage(FakeFooStorage):
    async def delete(self, key: str) -> None:
        await super().delete(key)
        raise UpstreamError("foo storage could not complete the operation", {"key": key})


async def test_store_failure_undoes_the_upload() -> None:
    repository = _RaiseAfterUploadRepository()
    storage = FakeFooStorage()
    handler = CreateFooHandler(repository=repository, storage=storage)

    with pytest.raises(UpstreamError) as exc:
        await handler.execute(CreateFooCommand(name="alpha", data=b"payload"))

    assert exc.value is repository.raised
    assert len(storage.uploads) == 1
    assert storage.deletes == [storage.uploads[0][0]]


async def test_failed_undo_still_raises_the_original_failure() -> None:
    repository = _RaiseAfterUploadRepository()
    storage = _RaiseOnDeleteStorage()
    handler = CreateFooHandler(repository=repository, storage=storage)

    with pytest.raises(UpstreamError) as exc:
        await handler.execute(CreateFooCommand(name="alpha", data=b"payload"))

    assert exc.value is repository.raised
    assert storage.deletes == [storage.uploads[0][0]]
```

Each injected failure is the catalogue class and `context` its real adapter raises (Fakes rules 6 and
8, `test-principles` rung 4) — the repository's as `hex-persistence` translates a driver error, the
storage's as its own adapter does — so both are `UpstreamError`, and the class alone cannot tell them apart. Which call raised
does: the repository subclass keeps the exception it raised, and `exc.value is repository.raised` passes only
when the caller sees that very failure. The contract is: **the upload landed, then the store write failed,
then the same key was deleted, and the caller sees the failure that started it, unchanged.** The undo
raises like any other call (`hex-application`, Compensation); the second test pins that the handler
stops the *undo's* failure and re-raises the original — the storage's `UpstreamError` escaping instead,
or the original wrapped in another exception, fails the identity assertion. A handler catching only the
catalogue root passes both; Compensation rule 3 is checked by reading.

## The fake's copy contract, pinned once

`tests/unit/test_fake_foo_repository.py` — one test per fake that keeps state, because Fakes rule 9 is
what lets every handler test pin persistence, and nothing else would notice the fake losing it:

```python
import uuid

from myapp.domain.foos import Foo
from tests.unit.fakes import FakeFooRepository


async def test_a_mutated_entity_does_not_reach_the_store() -> None:
    foo = Foo(id=uuid.uuid4(), name="alpha")
    repository = FakeFooRepository(items=[foo])

    foo.name = "seeded-then-mutated"
    loaded = await repository.get_by_id(foo.id)
    loaded.name = "read-then-mutated"

    assert (await repository.get_by_id(foo.id)).name == "alpha"
```
