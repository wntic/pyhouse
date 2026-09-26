---
name: hex-restapi-schema
description: Use when a REST request or response body gains or changes a field — the pydantic models in `restapi/schemas/<resource>.py` (`FooResponse`, `FooListResponse`, `FooCreateRequest`, `FooUpdateRequest`), PATCH `T | None = None` semantics, pagination shape, schema exports. Not the domain entity they mirror (`hex-domain-model`) and not the route that maps them (`hex-restapi-endpoint`).
paths: ["**/restapi/**", "**/api/**"]
---

# Hex REST — API Schema

Produces one resource's schema module — the declared HTTP wire format for that resource, written here as pydantic models. The module is the boundary itself: domain entities never cross the wire, and schemas never cross into application or domain code.

## When to use vs. neighbours

- Per-resource Pydantic schemas (request/response), including a field added to or removed from a body → this skill.
- The route that consumes these schemas and maps them field by field → `hex-restapi-endpoint`.
- The entity, value object, enum or filter record these models mirror — never imported here beyond enums → `hex-domain-model`.
- Cross-cutting `ErrorResponse` / `error_responses()` in `restapi/schemas/errors.py` → `hex-restapi-app`; which of those codes a route advertises → `hex-restapi-endpoint`.
- An auth login schema (`restapi/schemas/auth.py`) or any other auth-shaped wire type → `hex-restapi-auth`; reuse it, don't re-declare it per resource.
- The handlers beneath this delivery layer, and the command DTO carrying the same partial-update contract → `hex-application`.
- The container beneath this delivery layer → `hex-wiring`.
- The five schema names and any field name → `naming`; `__all__` and the wildcard re-export into `schemas/__init__.py` → `python-packaging`.
- Validating a successful response against its schema in a test → `hex-test-restapi-endpoint`.

## Template — pydantic

### File location

```
src/myapp/restapi/schemas/foos.py        # the resource's schemas
src/myapp/restapi/schemas/__init__.py        # update to re-export
```

The module holds several classes on purpose: one resource's request and response models are a closed set of declarations that change together, the case `python-packaging` lets share a module named for the set. Sub-resource schemas live **in the same file as the parent** when they are only used through the parent router (e.g. `BarResponse` in `foos.py` if `bars` are nested under `/foos/{id}/bars`).

### Schema module

```python
from collections.abc import Sequence
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field

__all__ = [
    "FooCreateRequest",
    "FooListResponse",
    "FooResponse",
    "FooUpdateRequest",
]


class FooResponse(BaseModel):
    id: UUID
    name: str
    bar_id: UUID


# Offset paging; a filter that pages by cursor makes this `items`, `next_cursor`, `limit` (Rule 7).
class FooListResponse(BaseModel):
    items: Sequence[FooResponse]
    total: int
    limit: int
    offset: int


class FooCreateRequest(BaseModel):
    name: Annotated[str, Field(min_length=1)]  # mirrors Foo's non-empty-name invariant
    bar_id: UUID


class FooUpdateRequest(BaseModel):
    name: Annotated[str | None, Field(min_length=1)] = None
    bar_id: UUID | None = None
```

## Other bindings

- **msgspec `Struct`, or attrs with a conversion layer.** The declarations and the constraint spelling
  change — a `Meta` annotation or a validator argument instead of `Field`, an explicit decode step
  instead of model construction. Unchanged: the five names, the in-file order, the partial-update
  contract, the one-pagination-shape rule, and the ban on domain types crossing into the module.
- **A plain dataclass plus an explicit validation step.** Honest only with the validation step actually
  written: something must reject a wrong shape *before* the handler sees it and must feed the published
  API document. A bare dataclass does neither, so rule 3 has nothing to attach to and the boundary stops
  being a boundary.
- **Whatever the web framework parses bodies and generates its schema from.** If the framework
  understands one model library only, that library is the binding: swapping it means supplying the
  parse-and-document step yourself, not renaming a base class.

## Rules

### Naming (exhaustive — do not invent alternates)

See `naming` for the shared naming rules.

| Schema | Purpose |
|--------|---------|
| `FooResponse` | Single-entity GET / POST / PATCH response |
| `FooListResponse` | List GET response — `items` + the resource's pagination fields (offset: `total`/`limit`/`offset`; cursor: `next_cursor`/`limit`), matching `hex-domain-model` |
| `FooCreateRequest` | POST body |
| `FooUpdateRequest` | PATCH body — every field `T \| None = None` |
| `FooWithBarResponse` | Single-entity response that embeds a sub-resource collection |

Do **not** introduce alternates (`Dto`, `Schema`, `In`, `Out`). The five names above cover the wire surface.

### Class form

1. **Each schema is a flat, self-contained declaration of one wire shape.** No shared base carrying "common fields" across resources — repetition is intentional. The file must read top to bottom as the JSON a client will see, with no field inherited from out of frame.
2. **Order in the file:** `Response`, `ListResponse`, `CreateRequest`, `UpdateRequest`, then sub-resource variants. Reads above writes; single above list.

### Validation

3. **Only request schemas constrain their input, and the constraint is declared on the field.** Declarative, beside the field it bounds — not an imperative validation method — so the whole accepted shape is readable in one pass and the published document can be generated from it. Under the binding above that is `Annotated[T, Field(min_length=..., max_length=..., ge=..., le=..., pattern=...)]`. A response carries no constraint: its data already passed the domain's invariants.
   **Every bound restates a limit the domain already has** — an entity invariant, a value object's range, the width a field is persisted at. Restating it is intentional (schemas are wire contracts, and rejecting at the edge beats a 500 later); *inventing* it is not. A number with no domain behind it is a guess that will disagree with the domain the first time either moves.
4. **A field constraint enforces input *shape* — length, range, pattern — never a business rule.** The test: a constraint that has to read another field, another aggregate, or the clock is a business rule, and it belongs on an entity or a policy. Only what can be checked from the one value in front of you belongs here.

### PATCH semantics

5. **Every field on `*UpdateRequest` is `T | None = None`.** The handler interprets `None` as "leave unchanged"; an explicit value as "set to this". Non-negotiable — the command DTO encodes the same partial-update contract.
6. **`*CreateRequest` lists required fields without `None`**, and gives a default only to an input that is genuinely optional.

### `*ListResponse`

7. **`*ListResponse` carries the resource's pagination shape — whichever one its filter record uses** (`hex-domain-model`'s one-pagination-shape rule for filter records picks exactly one), never a third:
   - **offset paging** → `items: Sequence[FooResponse]`, `total: int`, `limit: int`, `offset: int`.
   - **cursor paging** → `items: Sequence[FooResponse]`, `next_cursor: str | None`, `limit: int`.
   The route `hex-restapi-endpoint` builds constructs whichever shape the filter uses, so the schema must match it (see `hex-restapi-endpoint`'s cursor-list note). Don't mix the two.

### `__all__`

8. See `python-packaging` for `__all__` placement, ordering, and exports; the template above carries the schema symbols.

### What never goes in a schema file

- **No domain types beyond enums.** `FooResponse` does not import the `Foo` entity, and a value object crosses as its primitive fields, mapped in the route.
- **No business logic, computed properties, or `@validator`s that encode rules.** Use Pydantic's built-in `Field` constraints for shape; domain rules go elsewhere.
- **No persistence concerns.** Nothing that builds a schema straight from a stored row or mapped object — no ORM mode, no from-row constructor, no storage library's column types. A schema that can construct itself from the database has tied the wire format to the table, and the two then have to move together.
- **No shared base class beyond the model library's own** (rule 1).
- **No bare `dict` or `list` field standing in for a nested object.** A nested body is its own model in this file, declared and ordered like any other; a `dict` field publishes a hole in the wire contract that no generated document can describe. `python-style` owns the declared-record rule.

### Existing cross-cutting request schemas

A cross-cutting request schema that **already exists** elsewhere (e.g. an auth login schema in `restapi/schemas/auth.py` when the app has auth, or a shared body for a collection-level action several resources expose) → reuse it, don't re-declare it per resource. These are **feature-conditional**, not always present: an app with no auth has no `auth.py`, and an app whose resources have no such action has no shared body — don't assume either exists.

## Inlined typing / import rules

See `python-style` and `python-packaging` for the shared typing and import rules.

- **Allowed:** `pydantic`, stdlib (`uuid`, `collections.abc`, `datetime`, `decimal`, `typing`), and **domain enums only** (`FooCategory`, `Role`).
- **Forbidden:** domain entities, value objects and other dataclasses, repositories, application handlers, infrastructure types. Routers map field-by-field; the schema must not know about `Foo` the entity.
- **No `from __future__ import annotations`** (`python-style` — the model library reads annotations at runtime).
- **No `Optional[...]`** — `T | None` (`python-style`).

## Package wiring

After writing the module, update `restapi/schemas/__init__.py`:

```python
from . import errors, foos
from .errors import *
from .foos import *

__all__ = errors.__all__ + foos.__all__
```

`errors` is `hex-restapi-app`'s and stays; each resource module joins it in alphabetical order.

See `python-packaging` for package re-exports and `__all__` composition.

## Hard stops

- `*Response` is asked to validate input → stop, responses don't validate. The data already passed domain invariants.
- `*CreateRequest` is asked to allow all fields as `None` → stop, that's a `*UpdateRequest`.
- Asked for a shared base class to deduplicate fields across resources → stop, schemas are wire contracts; repetition is intentional.
- Asked to import a domain entity into the schema file → stop, mapping happens in the route.
