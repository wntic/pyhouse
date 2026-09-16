---
name: hex-domain-service
description: Use when a domain rule needs state one entity cannot see — a cross-aggregate check, a uniqueness check, does the referenced Bar exist — producing one stateless domain service (`FooUniquenessService`) with injected protocols and `assert_*`, `is_*` or verb methods. Not an entity invariant and not a tunable threshold, both `hex-domain-model`; orchestrating a use case is `hex-application`.
paths: ["**/domain/**"]
---

# Hex — Domain Service

Produces one domain service: a stateless class that orchestrates a domain rule using injected protocols. Domain services live next to the aggregate they primarily concern. See `naming` for identifiers.

## When to use vs. neighbours

- Rule enforceable from one entity's own fields → not a service; use `__post_init__` on the entity (see `hex-domain-model`).
- Rule needs to query other aggregates or a domain capability → this skill.
- Rule is a numeric or boolean threshold (max rows, retention days, quotas) → not a service; model it as the tunable value object in `hex-domain-model`.
- Orchestrating a use case across multiple aggregates → that is a command or query handler, not a service (see `hex-application`).
- The `IFooRepository` or `ICan<Verb>` protocols this service takes in its constructor → `hex-domain-ports`.
- The exception an `assert_*` method raises → `exception-catalog`.
- Binding the service (per-operation) so handlers receive it → `hex-wiring`.
- Testing it with stdlib, `pytest` and the domain package alone → `hex-test-domain`.
- What the service, its methods and its module are called → `naming`.

## Template — stdlib only, collaborators injected as domain ports

```python
from ..exceptions import FooConflictError
from .i_can_canonicalize_key import ICanCanonicalizeKey
from .i_foo_repository import IFooRepository

__all__ = ["FooUniquenessService"]

class FooUniquenessService:
    def __init__(
        self,
        repo: IFooRepository,
        canonicalizer: ICanCanonicalizeKey,
    ) -> None:
        self._repo = repo
        self._canonicalizer = canonicalizer

    def canonicalize(self, raw_key: str) -> str:
        return self._canonicalizer.canonicalize(raw_key)

    async def assert_available(self, canonical_key: str) -> None:
        if await self._repo.exists_by_canonical_key(canonical_key):
            raise FooConflictError("key already exists")

    async def is_taken(self, canonical_key: str) -> bool:
        return await self._repo.exists_by_canonical_key(canonical_key)
```

**Two forms.** An *orchestrator* service has collaborators: injected protocols on `__init__`, async
methods that touch them (the form above). A *pure* service has none: no `__init__` parameters, only
sync transformation methods (`canonicalize`, `derive_*`). The form follows directly from whether the
service has collaborators to inject.

## Rules

Path: `src/myapp/domain/foos/<class_snake>.py`. Follow `naming` for file and class names.

1. **A domain service is behaviour, not a record.** It holds collaborators, not fields, so it carries no
   data-class decorator and no generated equality or ordering — two services built from the same
   collaborators are not interchangeable values, and comparing them is meaningless.
2. **The constructor takes only domain protocols, other domain services, or value objects.** Never a
   concrete adapter, and never a settings object: a configured number reaches the domain wrapped in a
   tunable value object, so the domain never learns where configuration came from.
3. **Collaborators are private and set once.** Each is stored on a private attribute in the constructor;
   no public attribute, no assignment outside it. A service a caller can re-point is a service whose
   behaviour cannot be read off its construction site. Names follow `naming`.
4. **A method name states what happens on failure** — `assert_*` raises, `is_*`/`has_*`/`can_*` returns
   a boolean, a bare verb computes. The three are not interchangeable and `naming` owns the rule and its
   reason; it applies here because a policy's whole public surface is these methods.
5. **Async if and only if the method reaches IO through an injected protocol.** A pure transformation
   stays sync, so a sync signature is a standing claim that the call performs no IO.
6. **Failures raise a catalogue exception** — `exception-catalog`.
7. **No state beyond the constructor collaborators.** No cache, no counter, no mutable attribute: one
   instance serves every call made through it, so anything it remembers leaks from one call into the
   next.
8. **No transport, persistence or framework code.** The only IO is through the injected protocols, which
   is what lets the service run against hand-written stubs with no infrastructure present.
9. **A uniqueness rule this service asserts is not a guarantee.** A check that reads and then writes
   admits the second concurrent writer — nothing between the read and the write stops it. So the
   `assert_*` method goes in paired with a constraint in the store, which is what actually holds the
   rule (`hex-persistence`); follow `exception-catalog` for the store's rejection mapping to the same
   domain exception this service raises, so the caller sees one error whichever side refused. What the
   service contributes is the earlier refusal with a legible message, not the guarantee.

### What a domain service is not

- Not an application handler — services don't know commands, queries, or transactions.
- Not a single-entity validator — that's `__post_init__`.
- Not an infrastructure adapter — depends on protocols, not on concrete clients.
- Not a dumping ground for unrelated helpers.

## Inlined typing / import rules

See `python-style` and `python-packaging`.

- Stdlib only plus relative domain imports. No third-party. No `from __future__ import annotations`.
- `X | None`. Full annotations on `__init__`, every method, and every parameter.
- No comments unless a non-obvious *why*; one short line max.

## Package wiring

Follow `python-packaging` for module registration and `hex-architecture` for placement. The DI provider that constructs this service is the responsibility of `hex-wiring`, not this skill.

## Hard stops

- The service accumulates methods for rules that do not share a subject — past about four or five, in practice → stop, use `coupling`; one service holds one cohesive rule set, and the count is the symptom, not the rule.
- The class needs to reach a database session, driver or vendor client directly — a SQLAlchemy session, say → stop, add the access as a method on the existing domain protocol and depend on the protocol.
- The class needs to read settings → stop, wrap the relevant settings in a tunable value object (see `hex-domain-model`) and inject that.
