---
name: hex-test-domain
description: Use when testing a domain entity, value object, enum or domain service with stdlib, `pytest` and `myapp.domain` — no IO, no fixtures, no container, and an orchestrator service run on the in-memory fake of its port. Covers identity equality, one test per invariant and the pinned enum member set; a frozen value object with neither an invariant nor a canonicalization rule gets no test file at all. Not for writing the domain object itself — `hex-domain-model` or `hex-domain-service`.
---

# Hex Test — Domain

Consult `test-principles` for the testing constitution. Where this skill contradicts `test-principles`, the constitution wins.

The four kinds of test the domain layer takes: stdlib plus `pytest` plus `myapp.domain.*`, and for an
orchestrator service the hand-written fake of its port.

## When to use vs. neighbours

Inside this skill, by what is under test — the four templates under `## Template(s)`. Outside it:

- An application command or query handler → `hex-test-application-handler`.
- An in-memory fake under `tests/unit/fakes/` → `hex-test-application-handler`.
- A grep-firewall architectural rule → `test-architecture-rule`.
- The infrastructure adapter implementing a protocol a service depends on → `hex-test-repository-contract` (repository) or `hex-test-capability-adapter` (capability). A canonicalizer is tested here when it is pure domain logic with no library behind it; one that delegates to an external library sits behind a capability port, and its adapter is `hex-test-capability-adapter`'s.
- The handler that *uses* a service, end to end → `hex-test-restapi-endpoint`.
- The domain object itself rather than its test → `hex-domain-model` (entity, value object, enum) or `hex-domain-service`.
- Anything that needs a fixture, a container or a database — "add a testcontainer fixture for Postgres" included → `hex-test-integration-setup`; nothing in this skill takes a fixture.
- The no-mocks rule and the pure-unit speed target → `test-principles`.

## Template(s) — pytest, stdlib dataclass domain objects

Inside this skill, by what is under test:

- A `@dataclass` entity with UUID identity → **Entity**.
- A frozen value object **with** `__post_init__` invariants or a canonicalization rule → **Value object**.
  With neither, **write no file at all**: Python's data model already guarantees frozen-dataclass
  equality, and a test for it is maintenance with no defect-detection value.
- A `StrEnum` / `Enum` member set → **Enum**.
- A domain service with injected protocols, or the module-level function a pure transformation takes
  instead of a class (`hex-domain-service`) → **Domain service**.

File placement mirrors the source file (`test-principles`): the test for
`domain/<subdomain>/<module>.py` is `tests/unit/domain/<subdomain>/test_<module>.py`, whatever kind of
object the module holds — `foo.py` → `test_foo.py`, `foo_status.py` → `test_foo_status.py`,
`foo_uniqueness_service.py` → `test_foo_uniqueness_service.py`. The file name adds no suffix the
module name does not already carry.

The subjects below are `hex-domain-model`'s shapes filled in: `FooKey` is the normalized-plus-raw value
object with an invariant that `canonical` is non-empty, `Money` the standard value object over `amount`
(non-negative) and `currency` (three letters), `FooStatus` a `StrEnum` of `ALPHA` and `BETA`, and
`FooPriority` the rank-ordered `StrEnum` of `LOW`, `NORMAL` and `HIGH` with `satisfies`.

### Entity — standard

```python
import uuid

import pytest

from myapp.domain.exceptions import ValidationError
from myapp.domain.foos import Foo

def _make_foo(
    *, id: uuid.UUID | None = None, name: str = "Test", bar_id: uuid.UUID | None = None
) -> Foo:
    return Foo(id=id or uuid.uuid4(), name=name, bar_id=bar_id or uuid.uuid4())

def test_equality_by_id() -> None:
    shared_id = uuid.uuid4()
    a = _make_foo(id=shared_id, name="alpha")
    b = _make_foo(id=shared_id, name="beta")
    c = _make_foo(name="alpha")

    assert a == b
    assert a != c
    assert hash(a) == hash(b)
    assert hash(a) != hash(c)

def test_name_must_be_non_empty() -> None:
    with pytest.raises(ValidationError) as exc:
        _make_foo(name="")
    assert exc.value.context["field"] == "name"
```

The builder spreads **only the entity's real declared fields** — `id` plus its domain fields — because a
domain test constructs the subject the way the domain layer declares it and knows nothing of what a
store adds around it. Two things it must therefore not carry: `created_at` / `updated_at`, which are not
entity fields at all (`hex-domain-model`, Entity rule 6 — the audit timestamps are a DB-managed table
convention), so `Foo(created_at=...)` fails; and any `import datetime` that exists only to feed them.
`datetime` enters the file **only** when the entity genuinely declares a datetime domain field.

### Entity — few fields, so no builder

```python
import uuid

import pytest

from myapp.domain.exceptions import ValidationError
from myapp.domain.foos import Foo

def test_equality_by_id() -> None:
    shared_id = uuid.uuid4()
    bar_id = uuid.uuid4()
    assert Foo(id=shared_id, name="a", bar_id=bar_id) == Foo(id=shared_id, name="b", bar_id=bar_id)

def test_name_must_be_non_empty() -> None:
    with pytest.raises(ValidationError) as exc:
        Foo(id=uuid.uuid4(), name="", bar_id=uuid.uuid4())
    assert exc.value.context["field"] == "name"
```

### Value object — canonical-form equality plus an invariant

```python
import pytest

from myapp.domain.exceptions import ValidationError
from myapp.domain.foos import FooKey

def test_canonical_equality() -> None:
    a = FooKey(raw="abc", canonical="ABC")
    b = FooKey(raw="ABC", canonical="ABC")

    assert a == b
    assert hash(a) == hash(b)

def test_rejects_empty() -> None:
    with pytest.raises(ValidationError) as exc:
        FooKey(raw="", canonical="")
    assert exc.value.context["field"] == "canonical"
```

### Value object — invariants only, no canonicalization

```python
import pytest

from myapp.domain.amounts import Money
from myapp.domain.exceptions import ValidationError

def test_amount_must_be_non_negative() -> None:
    with pytest.raises(ValidationError) as exc:
        Money(amount=-1, currency="USD")
    assert exc.value.context["field"] == "amount"

def test_currency_must_be_three_letters() -> None:
    with pytest.raises(ValidationError) as exc:
        Money(amount=1, currency="US")
    assert exc.value.context["field"] == "currency"
```

### Enum — values plus rejection

```python
import pytest

from myapp.domain.foos import FooStatus

def test_values() -> None:
    assert FooStatus.ALPHA == "ALPHA"
    assert FooStatus.BETA == "BETA"

    with pytest.raises(ValueError):
        FooStatus("GAMMA")
```

### Enum — with a pure-logic method

```python
import pytest

from myapp.domain.foos import FooPriority

def test_values() -> None:
    assert FooPriority.LOW == "LOW"
    assert FooPriority.NORMAL == "NORMAL"
    assert FooPriority.HIGH == "HIGH"

    with pytest.raises(ValueError):
        FooPriority("URGENT")

def test_satisfies() -> None:
    assert FooPriority.HIGH.satisfies(FooPriority.NORMAL) is True
    assert FooPriority.NORMAL.satisfies(FooPriority.NORMAL) is True
    assert FooPriority.LOW.satisfies(FooPriority.NORMAL) is False
    assert FooPriority.LOW.satisfies(FooPriority.LOW) is True
```

The rank ladder is this example enum's own. Test every member's value, the rejection of an unknown one,
and the method at, above and below the bar — `satisfies` is the rank-ordered `StrEnum` shape from
`hex-domain-model`, whatever the enum ranks.

### Domain service — orchestrator, on the fake of its port

```python
import uuid

import pytest

from myapp.domain.exceptions import FooConflictError
from myapp.domain.foos import Foo, FooUniquenessService
from tests.unit.fakes import FakeFooRepository

def _service(existing_names: list[str] | None = None) -> FooUniquenessService:
    foos = [Foo(id=uuid.uuid4(), name=n, bar_id=uuid.uuid4()) for n in existing_names or []]
    return FooUniquenessService(repo=FakeFooRepository(items=foos))

async def test_assert_name_available_raises_when_taken() -> None:
    service = _service(["alpha"])
    with pytest.raises(FooConflictError) as exc:
        await service.assert_name_available("alpha")
    assert exc.value.context["field"] == "name"

async def test_assert_name_available_passes_when_free() -> None:
    service = _service([])
    await service.assert_name_available("alpha")  # does not raise
```

### Domain function — pure logic

`tests/unit/domain/foos/test_canonical_url.py`, for `hex-domain-service`'s `canonicalize_url`:

```python
import pytest

from myapp.domain.exceptions import ValidationError
from myapp.domain.foos import canonicalize_url

def test_strips_trailing_slash() -> None:
    assert canonicalize_url("https://example.com/path/") == "https://example.com/path"

def test_drops_default_port() -> None:
    assert canonicalize_url("https://example.com:443/path") == "https://example.com/path"

@pytest.mark.parametrize(
    "raw", ["https://example.com/", "https://example.com/path/?b=2&a=1"]
)
def test_idempotent(raw: str) -> None:
    once = canonicalize_url(raw)
    assert canonicalize_url(once) == once

def test_rejects_non_http() -> None:
    with pytest.raises(ValidationError) as exc:
        canonicalize_url("ftp://example.com")
    assert exc.value.context["field"] == "scheme"
```

The canonicalizer here is a domain function because it is pure logic over the standard library. One
that delegates to an external library (an IDNA or URL-parsing package) sits behind a capability port
instead, and its test is `hex-test-capability-adapter`'s pure-CPU flavour.

## Rules

### All four kinds

1. **A domain test is synchronous unless the thing under test is awaited.** Only a test of an async
   method is declared async; making the rest async buys nothing and hides which subjects do IO-shaped
   work. Async configuration and markers → `test-principles`.
2. The no-mocks contract → `test-principles`. The domain has no IO to stub, and where
   a stand-in is needed (a service's injected protocol) it is hand-written — the port's fake, or a
   class for a narrow protocol (rule 17).
3. Fixture-versus-builder rules → `test-principles`.
4. **Assert against literal expected values.** Never re-implement the rule under test to compute the
   expected value — that hides the defect where both sides make the same mistake.
5. **Test what the author wrote, never what the data model already guarantees.** Field-by-field
   equality, hashability and immutability come free with a frozen `@dataclass`; asserting them is
   maintenance with no defect-detection value, because no plausibly-wrong change to the domain could
   red them. What is not free is the constructor's invariants, the computed properties and the methods —
   those are the whole coverage target.
6. **One test per invariant, and a rejection test asserts the failure's machine-readable field key,
   never its message.** Capture the raised catalogue exception (`pytest.raises(ValidationError) as exc`)
   and assert the `context` entry naming the offending field: the message is prose and drifts, the key is
   what the entrypoint reads. Several failure modes of the *same* invariant group under one test named
   after that invariant; two different invariants never share a test.

### Entity

7. **The four-line identity-equality block is the contract**: equality by id only, and `hash` agreeing
   with `eq`. Do not paraphrase it.
8. **`_make_<entity>(*, <field>: <type> = <valid default>, …)` is a module-level `def`** with one
   keyword-only, annotated parameter per declared field and valid defaults, so construction with no
   arguments succeeds. **No logic in it beyond a fresh id** — it is a dumb spreader, and computation
   belongs in the tests.
9. **A computed property or method gets its own `test_*`** named after the rule — but only when the entity
   actually declares one. Do not add a lifecycle or archive test to an entity that has no such property;
   that is a per-aggregate feature, not a default.

### Value object

10. **Write no file for a value object that declares no invariant of its own and no custom equality.**
    There is nothing the author wrote left to pin (rule 5).
11. **A canonical-form equality test pins the rule, not Python's `==`**: two instances with the same
    `canonical` must be equal even when their `raw` fields differ, and `hash` must agree.
12. **No builder.** Value objects are small — pass the fields directly.

### Enum

13. **Pin every member with an explicit assertion**, one line each. The database and the wire format
    depend on these strings, so a silent rename must break the test.
14. **Never loop over members.** `for m in FooStatus: assert m.value == m.name` masks the very bug it
    looks like it catches — a renamed value still passes.
15. **Always include the unknown-value rejection**:
    `with pytest.raises(ValueError): FooStatus("<unknown>")` proves the enum is closed.
16. **One `test_*` per pure-logic method**, named after the method, asserting every relevant
    input/output pair with `is True` / `is False` for booleans — `==` may accidentally compare `int(1)` to
    `True`.

### Domain service

17. **An orchestrator runs on the fake of the port it takes.** A service that takes the whole
    repository port (`IFooRepository`) is built on `FakeFooRepository` from `tests.unit.fakes`
    (`hex-test-application-handler`): under a strict type checker a stand-in must satisfy the whole
    protocol, and that fake already does, with the real adapter's exception contract. A minimal inline
    class is allowed only when the service's parameter is a protocol declaring exactly the methods it
    calls — it then implements that protocol and nothing more, which keeps the narrow dependency
    surface visible.
18. **The `_service(...)` factory returns the constructed service**, hiding the collaborator plumbing
    from each test body.
19. **One `test_*` per behaviour of each method**, named so the test name *is* the behaviour's one-line statement —
    `test_assert_name_available_raises_when_taken`, `test_assert_name_available_passes_when_free`.
20. **A domain function is called directly.** It has no instance to construct, share or fake.
21. **A canonicalizer always has `test_idempotent`** — parametrized over a few representative inputs,
    one reported case each, asserting `f(f(x)) == f(x)`. Idempotence is part of the canonicalization
    contract; a loop inside one test stops at the first failing input and hides the rest.
22. **Pair every happy path with a rejection test.** Single-direction tests are incomplete.

## Inlined typing / import rules

Identical for all four kinds:

- Stdlib (`uuid`, and `datetime` only when genuinely needed) plus `pytest` plus `myapp.domain.*`, and
  `tests.unit.fakes` for an orchestrator's collaborators. No infrastructure, no application, no restapi,
  no Pydantic, no SQLAlchemy.
- Full annotations on a builder or factory and on an inline stub class. Tests are
  `def test_*() -> None` or `async def test_*() -> None`.
- No `from __future__ import annotations`.

## Hard stops

- A test here needs a database, an HTTP endpoint or blob storage → stop, use
  `hex-test-repository-contract` or `hex-test-restapi-endpoint`.
- Asked for `MagicMock` / `AsyncMock` / `monkeypatch` → stop, use `test-principles`.
- Asked for a builder or factory as a `@pytest.fixture` → stop, use `test-principles`.
- Asked to test dataclass-given equality, hash or immutability → stop, omit the test; Python guarantees it.
- A test re-implements the rule to compute the expected value → stop, assert literal values.
- A test asserts on log output or captured logs → stop, the domain layer logs nothing at all
  (`python-style` allocates logging by layer); assert the return value or the raised exception.
- Asked to build an entity from anything the entity does not declare → stop, the builder spreads the
  entity's own fields and nothing else. `created_at` / `updated_at` are the usual case: the store
  maintains them, so they are not entity fields (`hex-domain-model`, Entity rule 6).
- The value object declares no invariant of its own and no custom equality → stop, produce no file.
- A test loops over enum members → stop, write explicit asserts.
- A test uses `==` instead of `is` for a boolean enum-method return → stop, use `is True` / `is False` to prevent
  truthy-but-not-`True` bugs.
- An enum's members are not known → stop, list them explicitly.
- An inline stub stands in for a full port, or implements methods beyond the narrow protocol the
  service's parameter declares → stop, use the port's fake from `tests.unit.fakes`, or the narrow
  protocol exactly.
- A test adds `@pytest.mark.asyncio` → stop, use `test-principles`.
- A pure-logic canonicalizer's test omits `test_idempotent` → stop, add `test_idempotent`; idempotence is part of the contract.
