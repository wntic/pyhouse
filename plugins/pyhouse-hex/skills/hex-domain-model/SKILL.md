---
name: hex-domain-model
description: Use when creating or changing a domain entity, value object, enum or filter record — stdlib dataclasses, `__post_init__` invariants, identity versus value equality, when a bare primitive carrying a constraint, a unit or a rule must become a value object instead, and the tunable variant of a value object for an env-sourced threshold (max rows, retention days), which is neither a service nor a settings class. A rule needing another aggregate's state is `hex-domain-service`; the wire model is `hex-restapi-schema`.
paths: ["**/domain/**"]
---

# Hex — Domain Model

The four data shapes of the domain layer. They share one substrate — stdlib only, no third-party
imports — and a change that adds a capability usually adds several of them together,
which is why they live in one place.

## When to use vs. neighbours

Inside this skill, pick by what the thing *is*:

- A thing with a UUID and a lifecycle → **Entity**.
- An immutable type defined by its content, or a primitive that carries a constraint, a unit or a rule → **Value object**.
- A closed set of named values → **Enum**.
- A read-side parameter bag passed to a repository `list`/`count` → **Filter record**.
- An env-tunable threshold the domain consumes (max rows, retention days, quotas) → the **tunable variant** of a value object, not a service and not a settings class.

Outside it:

- The interface a repository or a capability must satisfy → `hex-domain-ports`.
- A rule needing another aggregate's state, or a domain capability → `hex-domain-service`.
- The single error catalog → `exception-catalog`.
- A DTO crossing the application boundary → `hex-application`. A filter record may be reused there; the query DTO wraps it plus authorization context.
- The request or response model on the wire → `hex-restapi-schema`; a domain type is never serialized straight out.
- Persistence of any of these → `hex-persistence` (a relational store) or `hex-store-repository` (a client-style store).
- The settings class the tunable variant's values come from, and the provider that constructs it → `hex-wiring`.
- Testing an invariant, identity equality or the pinned enum member set → `hex-test-domain`.
- What the class and its module are called → `naming`; one class per module and the re-export → `python-packaging`.

One case is neither a shape here nor a neighbour's:

- A predicate over a field carried by **both** the entity and a read-model of the same aggregate → a module-level function in the aggregate's package, not the same method written twice, not a shared base class, and not a domain service; see Choosing a shape below.

## Template(s) — stdlib dataclasses and enums

### Entity

```python
from dataclasses import dataclass
from uuid import UUID

from ..exceptions import ValidationError

__all__ = ["Foo"]

@dataclass
class Foo:
    id: UUID
    name: str
    bar_id: UUID

    def __post_init__(self) -> None:
        if not self.name:
            raise ValidationError("name must be non-empty", {"field": "name"})

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Foo):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)
```

`Baz`, the third placeholder aggregate — held only by the key-value store example in
`hex-store-repository` — is the same form with its own fields, in `domain/bazs/baz.py`:

```python
from dataclasses import dataclass
from uuid import UUID

from ..exceptions import ValidationError

__all__ = ["Baz"]

@dataclass
class Baz:
    id: UUID
    name: str

    def __post_init__(self) -> None:
        if not self.name:
            raise ValidationError("name must be non-empty", {"field": "name"})

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Baz):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)
```

### Value object — standard case (value equality across all fields)

```python
from dataclasses import dataclass

from ..exceptions import ValidationError

__all__ = ["Foo"]

@dataclass(frozen=True)
class Foo:
    field_a: str
    field_b: int

    def __post_init__(self) -> None:
        if self.field_b < 0:
            raise ValidationError("field_b must be non-negative", {"field": "field_b"})
```

The `@dataclass(frozen=True)`-generated `__eq__` / `__hash__` compare all fields. Do not override them
in the standard case.

### Value object — escape hatch (normalized plus raw form)

When the value object stores both a raw input and a normalized form — an email with the user-typed
string and the canonical lowercased version — equality must compare by the **canonical** field only,
otherwise two semantically equal values compare unequal.

```python
from dataclasses import dataclass

__all__ = ["Foo"]

@dataclass(frozen=True)
class Foo:
    raw: str
    canonical: str

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Foo):
            return NotImplemented
        return self.canonical == other.canonical

    def __hash__(self) -> int:
        return hash(self.canonical)
```

### Value object — tunable variant (configuration the domain consumes)

A value object can serve as the domain-shaped view of an environment-tunable threshold (max upload
size, max export rows, retention days). The form is identical — frozen dataclass, primitive fields, no
methods. For the file and class names, see `naming`.

```python
from dataclasses import dataclass

__all__ = ["FooExportTunable"]

@dataclass(frozen=True)
class FooExportTunable:
    max_rows: int
    retention_days: int = 30
```

Distinguishing characteristics:

- Sourced from a settings class at the composition root — a provider of its own reads each field off
  the settings object and passes it: `FooExportTunable(max_rows=settings.max_rows)`. See `hex-wiring`.
- Injected into domain services and application handlers, never into entities. Entities do not read
  tunables; services do.
- Every value-object rule still applies: frozen, no methods, primitive or VO fields only. Which
  builtin each primitive field takes — an exact decimal quantity, an instant with an offset, an
  identifier — is `python-style`'s.

Use this variant only when the value carries no domain meaning beyond "this is a knob to turn". If it
participates in the ubiquitous language — a `FooTotal`, a `RetentionWindow` with behaviour — it is an
ordinary value object.

### Value object — the instances the port templates name

The port signatures in `hex-domain-ports` name four value objects. Each is the standard form above,
filled in, in the subdomain package whose port names it:

```python
# src/myapp/domain/bars/canonical_bar_url.py
from dataclasses import dataclass

__all__ = ["CanonicalBarUrl"]

@dataclass(frozen=True)
class CanonicalBarUrl:
    value: str
```

```python
# src/myapp/domain/bars/bar_token.py
from dataclasses import dataclass
from datetime import datetime

__all__ = ["BarToken"]

@dataclass(frozen=True)
class BarToken:
    value: str
    expires_at: datetime
```

```python
# src/myapp/domain/foos/foo_export_row.py
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

__all__ = ["FooExportRow"]

@dataclass(frozen=True)
class FooExportRow:
    id: UUID
    name: str
    created_at: datetime
```

```python
# src/myapp/domain/audit/audit_event.py
from dataclasses import dataclass
from uuid import UUID

__all__ = ["AuditEvent"]

@dataclass(frozen=True)
class AuditEvent:
    subject_id: UUID
    action: str
```

`FooExportRow` is a read-model rather than a value object — it carries `created_at`, which no entity
does (Entity rule 6) — and takes the same frozen form (`hex-application`, read models).

### Enum — `StrEnum` (the default, for string-valued sets)

```python
from enum import StrEnum

__all__ = ["Foo"]

class Foo(StrEnum):
    A = "A"
    B = "B"
    C = "C"
```

### Enum — `StrEnum` with a pure-logic method

Pure logic means it depends only on the enum's own values: no IO, no other aggregates. The common
shapes are ordering, ranking and membership tests.

```python
from enum import StrEnum

__all__ = ["Foo"]

_RANK: dict[str, int] = {"A": 1, "B": 2, "C": 3}

class Foo(StrEnum):
    A = "A"
    B = "B"
    C = "C"

    def satisfies(self, required: "Foo") -> bool:
        return _RANK[self.value] >= _RANK[required.value]
```

**The self-reference is quoted.** `required: "Foo"` inside `Foo`'s own body, because the name is not
bound until the class statement finishes and the catalogue bans `from __future__ import annotations`
(`python-style`). An unquoted `Foo` there raises `NameError` at class-definition time on the Python
versions this catalogue targets.

A module-level constant like `_RANK` is allowed only when it encodes a pure mapping the enum uses. See
`python-packaging` for its visibility and exports.

**`_RANK` is method-body logic, not part of the enum's declaration.** The template shows the *filled*
end state: `_RANK` exists only to serve `satisfies` and is written together with that method's body,
distilled from its rule ("rank order C >= B >= A"). The type's public shape is its members
plus the method signature; `_RANK` is implementation, the same way a repository's
`_map_integrity_error` or a module-level `logger` is.

### Enum — `Enum` (non-string values)

```python
from enum import Enum

__all__ = ["Foo"]

class Foo(Enum):
    A = 1
    B = 2
    C = 3
```

### Filter sort enum

`domain/foos/foo_sort.py`, beside the filter that imports it (`hex-conventions`). One member per ordering
the list read offers, each naming a column and a direction; the repository maps every member to its
ordered column (`hex-persistence`).

```python
from enum import StrEnum

__all__ = ["FooSort"]

class FooSort(StrEnum):
    CREATED_AT_DESC = "created_at_desc"
    CREATED_AT_ASC = "created_at_asc"
    NAME_ASC = "name_asc"
```

### Filter record

```python
from dataclasses import dataclass, field
from datetime import date
from uuid import UUID

from .foo_sort import FooSort

__all__ = ["FooListFilter"]

@dataclass(frozen=True)
class FooListFilter:
    bar_ids: frozenset[UUID] = field(default_factory=frozenset)
    created_from: date | None = None
    created_to: date | None = None
    sort: FooSort = FooSort.CREATED_AT_DESC
    limit: int = 50
    offset: int = 0
```

## Rules

### Choosing a shape

Inside this skill, pick by what the thing *is*:

- A thing with a UUID and a lifecycle → **Entity**.
- An immutable type defined by its content, or a primitive that carries a constraint, a unit or a rule → **Value object**.
- A closed set of named values → **Enum**.
- A read-side parameter bag passed to a repository `list`/`count` → **Filter record**.
- An env-tunable threshold the domain consumes (max rows, retention days, quotas) → the **tunable
  variant** of a value object, not a service and not a settings class.

A DTO crossing the application boundary → `hex-application`. A filter record may be reused there; the
query DTO wraps it plus authorization context.

One case is neither a shape here nor a neighbour's:

- A predicate over a field carried by **both** the entity and a read-model of the same aggregate →
  a **module-level function in the aggregate's package**, taking the field values as parameters and
  called by whoever holds either type. Not the same method written twice, once per type: two copies of
  one rule drift, and only the rewritten path's criterion notices. Not a shared base class — the rules
  below forbid inheritance on both the entity and the value object, and the read-model is a frozen
  dataclass of its own, so there is no base to hang it on (`hex-application` carries the read/write split).
  Not a domain service either: the entity rules hand a service the rules an entity *cannot* see, and
  this one reads one field of one aggregate.

  The shape recurs by convention rather than by accident — audit timestamps are never entity fields, so
  a read that needs them comes back as a read-model, and the field then sits on two types.

### Entity

1. **An entity is mutable and stays mutable** — a plain `@dataclass`, never frozen. An entity has a
   lifecycle; freezing it forces every state change through a copy, and the copy is a different object to
   everything holding the old one.
2. **Identity equality is mandatory.** Two entities are equal when their `id` is equal and for no other
   reason, and the hash agrees. Field-wise equality makes a loaded row and the same row after an edit two
   different foos, so a set or a dict keyed by entity silently grows duplicates.
3. **Invariants are checked at construction, in one place** — `__post_init__` under the dataclass
   substrate — one raise per rule, using `exception-catalog` for the error class. A rule enforced at the
   call site instead is a rule the next call site forgets; omit the hook entirely when there are no
   invariants.
4. **Cross-aggregate rules do not go here.** Uniqueness, authorization, "does referenced X exist" → a
   domain service (`hex-domain-service`). Tunable thresholds → the tunable variant above. An entity only
   checks invariants it can see from its own fields.
5. **No inheritance.** No base classes, no `ABC`. Compose by holding other domain objects.
6. **Audit timestamps are never entity fields.** `created_at` / `updated_at` are a DB-managed table
   convention. A read that needs them returns a read-model DTO projected from the row.

### Value object

1. **A primitive carrying a constraint, a unit or a rule is a value object, not a bare field.** The
   test is whether the value can be wrong on its own terms: a string that must match a form, a number
   that must stay in a range or is denominated in something, a pair of values only meaningful together.
   Left bare, the check lives at whichever call site remembered it, and the next one does not — which
   is the same failure the entity's `__post_init__` rule exists to prevent, one level down. Give it a
   type and check it once, at construction.
   A primitive with nothing but its builtin type behind it stays a primitive: an opaque identifier, a
   free-text note, a count that is simply a count. Wrapping those buys a name and pays for it in
   conversions at every boundary. Which builtin a scalar takes in the first place — an exact decimal
   quantity, an instant with an offset — is `python-style`'s.
2. **A value object is immutable** — a frozen dataclass. An invariant checked at construction stops
   holding the moment a field can be reassigned, and a mutable value cannot safely be shared or used as a
   key.
3. **No identity field.** No `id: UUID`. If one is called for, this is an entity.
4. **Value equality.** Use the dataclass-generated equality. Override `__eq__` / `__hash__` only for the
   normalized-form escape hatch.
5. **Invariants in `__post_init__`.** Use `exception-catalog` for the error shape. Omit the method
   when there are none.
6. **No inheritance.** Compose, do not inherit.
7. **No cross-aggregate logic.** Anything needing another aggregate's state is a domain service.

### Enum

1. **A member's value is the value that leaves the process.** A string-valued set uses `StrEnum` so the
   member compares and serializes as that string without a conversion step at every boundary; a set whose
   values are genuinely numeric uses a plain `Enum`. Never an integer enum for codes that are really
   strings — the mismatch surfaces in the database and on the wire, not here.
2. **Member names follow `naming`.** For a `StrEnum` the value is usually identical to the
   name; do not invent lowercased values unless the wire format requires them.
3. **Module boundaries follow `python-packaging`; module names follow `naming`.**
4. **Methods only when pure.** Anything touching another aggregate, IO or external state is not an enum
   method. Methods receive `self` and other enum values only.
5. **No custom base class.** Inherit from `StrEnum` or `Enum` directly; no "abstract enum" hierarchies.
6. **No constants pretending to be enums.** `class Status: ACTIVE = "active"` is banned everywhere, not
   just in the domain.

### Filter record

1. **Frozen dataclass, value equality.** Generated `__eq__` / `__hash__` — never override.
2. **A collection-valued filter field defaults to a fresh empty immutable collection**, built per
   instance (`field(default_factory=frozenset)`), never to a shared mutable default — see `python-style`
   for the collection types. One shared default is one object every filter in the process mutates.
3. **Absence of a constraint is expressed as `None`**, never a sentinel value such as `""` or `-1`,
   which the adapter cannot distinguish from a caller who meant it. Annotation forms follow
   `python-style`.
4. **Sort is an enum reference**, never a bare string. See `python-packaging` for its module.
5. **One pagination shape, explicitly.** Either `limit: int` + `offset: int`, both defaulted, or
   `cursor: str | None`. Never both. If it is not stated which, ask. **The default page size is the
   project's decision, not the catalogue's** — pick one bound, state it once, and keep every filter in
   the service on it.
6. **No methods.** A filter record is a passive data bag. Anything computed — translating a sort key to
   a SQL column, say — belongs in the repository adapter.
7. **No business invariants.** A repository receives whatever the caller passed; range and authorization
   checks live in the query handler. Default to no `__post_init__` at all.

## Inlined typing / import rules

These hold for all four shapes; the full rules are `python-style` and `python-packaging`.

- **Stdlib only**, plus relative domain imports. No third-party libraries — no Pydantic, no SQLAlchemy.
  The usable set is `dataclasses`, `datetime`, `decimal`, `enum`, `uuid`, `collections.abc`, `typing`;
  an enum module normally needs only `enum`.
- **No `from __future__ import annotations`**, anywhere in the project.
- `X | None`, never `Optional[X]`. Collection fields are `frozenset[T]` / `tuple[T, ...]`, never `set` /
  `list`.
- **Full annotations** on every field and every method signature, including `-> None` on
  `__post_init__`.
- Default to no comments. Add one only when the *why* is non-obvious, one short line — never a
  multi-paragraph docstring.

## Package wiring

Follow `hex-architecture` for file placement and `python-packaging` for module exports, package re-exports,
and imports, including the module-level predicate function above.

## Hard stops

- Asked for a frozen object defined by its content, with no identity → stop, model it as a value object; `id: UUID` plus mutation over time → stop, model it as an entity.
- A constraint, a unit or a format rule sits on a bare `str`, `int` or `Decimal` field and is checked at the call site → stop, model the value as a value object and check the invariant in its `__post_init__`.
- Asked for behaviour that needs another aggregate's state → stop, use `hex-domain-service`.
- Asked for repository methods or persistence on any of these → stop, use `hex-domain-ports` for the interface and `hex-persistence` for the adapter.
- Asked for runtime-extensible "enum" values loaded from config or a database → stop, model it as a value object plus a lookup repository.
- Asked for a filter-record method that translates the filter to SQL → stop, use `hex-persistence`.
- A filter record is asked to validate cross-aggregate state, or to range-check its own fields → stop, use `hex-application`.
- One filter needs both `limit`/`offset` and `cursor` → stop, pick one with the user.
- `created_at` / `updated_at` are put on an entity → stop, project the DB-managed audit timestamps into a read-model DTO instead.
- Asked for enum values persisted to a SQL column → stop, use `hex-persistence` for the column type and its mapping; the enum still belongs here.
