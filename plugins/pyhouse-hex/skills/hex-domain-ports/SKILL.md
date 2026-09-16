---
name: hex-domain-ports
description: Use when defining a `typing.Protocol` port in the domain — the `I`-prefixed interface adapters satisfy structurally, `IFooRepository` for one aggregate root's data access or `ICan<Verb>` for a single external action. The interface, not its implementation — that is `hex-persistence`, `hex-store-repository` or `hex-capability-adapter`.
paths: ["**/domain/**"]
---

# Hex — Domain Ports

The domain's outbound interfaces. Both are `typing.Protocol` modules holding method signatures and
nothing else; infrastructure satisfies them **structurally**, without importing them to inherit.

## When to use vs. neighbours

- Aggregate-root data access — CRUD plus aggregate-specific reads → **repository protocol** (`IFooRepository`), in this skill.
- A single action that does IO or talks to an external system — file rendering, token verification, blob storage, a third-party gateway call → **capability protocol** (`ICan<Verb>`), in this skill.
- A pure-CPU operation such as JWT signature verification or URL canonicalization → **capability protocol**, with a sync method instead of async.
- The entity, value object, enum or filter record the signatures mention → `hex-domain-model`.
- A rule needing cross-aggregate state, which *consumes* these protocols → `hex-domain-service`.
- A concrete repository implementation → `hex-persistence` (a relational store) or `hex-store-repository` (a client-style store). The protocol itself is store-agnostic; the choice is made by store profile (`hex-conventions` block B).
- A concrete capability implementation → `hex-capability-adapter`.
- An in-memory fake satisfying one of these protocols in a unit test → `hex-test-application-handler`.
- Binding a concrete implementation to the protocol by type → `hex-wiring`.
- The token-verifier port, its adapter and the route dependency that resolves it → `hex-restapi-auth`; it is the sync shape below, bound to auth, and exists only in an app whose entrypoint authenticates.
- The `i_` and `i_can_` filename prefixes and the rest of the identifier derivation → `naming`.
- The command or query handler that consumes one of these protocols → `hex-application`.
- The `*_best_effort` cleanup method a compensating handler calls on one of these ports → declared here, used by `hex-patterns`.

## Template(s) — stdlib `typing.Protocol`

### Repository protocol

```python
from collections.abc import Sequence
from typing import Protocol
from uuid import UUID

from .foo import Foo
from .foo_list_filter import FooListFilter

__all__ = ["IFooRepository"]

class IFooRepository(Protocol):
    async def list(self, *, filter: FooListFilter) -> Sequence[Foo]: ...
    async def count(self, *, filter: FooListFilter) -> int: ...
    async def get_by_id(self, id: UUID) -> Foo: ...
    async def get_by_name(self, name: str) -> Foo | None: ...
    async def create(self, foo: Foo) -> None: ...
    async def update(self, foo: Foo) -> None: ...
    async def delete(self, id: UUID) -> None: ...
```

### Capability protocol — async (the default)

```python
from collections.abc import Sequence
from typing import Protocol

from .foo_export_row import FooExportRow

__all__ = ["ICanExportFoosXlsx"]

class ICanExportFoosXlsx(Protocol):
    async def export(self, rows: Sequence[FooExportRow]) -> bytes: ...
```

### Capability protocol — sync (pure CPU only)

```python
from typing import Protocol

from .canonical_bar_url import CanonicalBarUrl

__all__ = ["ICanCanonicalizeBarUrl"]

class ICanCanonicalizeBarUrl(Protocol):
    def canonicalize(self, raw: str) -> CanonicalBarUrl: ...
```

## Rules

Two shapes, and the split is about mental model rather than size: a **repository** is the collection of
one aggregate root, a **capability** is a single action the domain needs but cannot perform itself.

- Aggregate-root data access — CRUD plus aggregate-specific reads → **repository protocol**.
- A single action that does IO or talks to an external system — file rendering, blob storage, a
  third-party gateway call → **capability protocol**.
- A pure-CPU operation such as canonicalizing a string or rendering in-memory bytes → **capability
  protocol**, with a sync method instead of async.

The protocol itself is store-agnostic; the choice is made by store profile (`hex-conventions` block B).

### File location and naming

| | Path | Class |
|---|---|---|
| Repository | `src/myapp/domain/foos/i_foo_repository.py` | `IFooRepository` |
| Capability | `src/myapp/domain/foos/i_can_<verb>.py` | `ICan<Verb>` |

Follow `naming` for protocol names and prefixes, and `python-packaging` for module boundaries.

Place a capability where its primary input lives. Cross-cutting ones — auth, observability — go in their
own subdomain package (`domain/auth/`, `domain/observability/`).

### Both shapes

1. **A port is a structural interface with no behaviour** — method signatures and nothing else. Declare
   it with `typing.Protocol` (`python-style` owns the declaration form and runtime checking), never an
   abstract base class: a base class makes satisfaction a matter of inheritance, and the point of a port
   is that an adapter the domain has never heard of satisfies it.
2. **No default implementations and no docstring standing in for one.** A body the adapter inherits is
   behaviour that escaped the layer that owns it. Comments and docstrings follow `python-style`.
3. **Parameters and return types are domain types or primitives.** Never a database row, an SDK object
   or a validation model: a port typed in an adapter's vocabulary drags that library into every caller,
   and the domain then cannot be imported without it.
4. **Infrastructure satisfies the port without importing it.** The adapter neither inherits nor imports
   the protocol; satisfaction is checked where the adapter is injected, so an import here would be a dead
   one.
5. **No class-level state and no helper methods.** Both belong to the adapter — a helper on the port is a
   decision the domain has taken on the adapter's behalf, and every adapter then inherits it.

### Repository protocol

1. **Every method is `async`.** A repository method reaches a store once implemented, without exception;
   a sync signature forces every future adapter to either block the event loop or break the contract.
2. **Keyword-only arguments for `list`, `count` and any multi-parameter method**; positional only on a
   single-parameter lookup such as `get_by_id(id)`. Two positional parameters of the same type are
   silently swappable at the call site and no checker catches it — a one-parameter lookup cannot be.
3. **The return shape states what "missing" means, and the adapter has no say in it:**
   - `get_by_id` fails when missing — never `Foo | None`; the error class is `exception-catalog`'s.
   - `get_by_<other>` may return `Foo | None`, and does so exactly when "not found" is a normal outcome.
   - `list` returns a read-only view (`Sequence[Foo]`) — see `python-style` for why a read-only return
     type is not the same as a `list`.
   - `create` / `update` / `delete` return `None`. A write that returns data is a query in disguise.

### Capability protocol

1. **One method is the default; two is the maximum**, and only when the pair is one reversible action —
   `upload` plus `delete` on the same key. Three or more means the port has stopped being one action:
   split it, or model it as a repository.
2. **Async unless the operation is pure CPU.** Anything that may do IO is `async`; sync is reserved for
   work that provably cannot block — cryptographic, parsing and encoding helpers. Getting this wrong is
   only discovered under load, because the sync port cannot be widened without changing every caller.

## Inlined typing / import rules

Follow `python-style` and `python-packaging`; the load-bearing slice is:

- **`class IName(Protocol)` from `typing`.** Never `abc.ABC`, never a concrete base class.
- **No `@runtime_checkable`** unless the codebase genuinely does `isinstance(x, IFoo)`. Default off.
- Stdlib only — `typing`, `collections.abc`, `uuid`, `datetime` — plus relative domain imports. No
  third-party. No `from __future__ import annotations`.
- `X | None`. `Sequence[T]` from `collections.abc` for read-only views.
- Full annotations on every parameter and every return type.
- No comments unless a non-obvious *why*; one short line at most.

## Package wiring

Follow `python-packaging` for package exports and `hex-architecture` for layer placement.

## Hard stops

- Spec lists more than about three single-action methods that share no collection mental model → stop, that is one or more capability protocols, not a repository.
- A capability's method count would grow past two → stop, split the protocol or model it as a repository.
- Spec asks for SQL, SDK or framework types on a signature → stop, those are infrastructure concerns.
- Spec asks the protocol to inherit from an `ABC` or a concrete base → stop, it is a `Protocol` — see this skill's own typing slice above.
- Spec asks for a default implementation on the protocol → stop, that is behaviour leaking into a domain interface; it belongs in the adapter.
