---
name: python-style
description: Use when choosing a type annotation, deciding what shape a record takes as it crosses a boundary, deciding what to log, or asking whether a comment belongs here. Owns `X | None` over `Optional`, the ban on `from __future__ import annotations`, immutable collection types, the rule that a fixed-shape record is a declared type rather than a bare `dict` or tuple, which builtin represents an exact decimal quantity, an instant and an identifier, one structured `structlog` event per occurrence, and which layer logs an error. Whether a constrained scalar also earns a named type of its own belongs to the architecture family; the error classes themselves are `exception-catalog`.
---

# Python Style

Project-wide rules that are stricter than CPython's defaults and hold **whatever the architecture is** —
a hexagonal app, a flat-layered worker, or a standalone script. Three subjects: what the types look like,
who logs what, and where a comment is warranted.

Only one thing here varies by architecture, and it varies as a *consequence*, not as a separate rule:
an error is logged once, by the layer that can add context and will not re-raise it — and the families
differ in which layer that is. Everything else is unconditional.

## When to use vs. neighbours

- Writing or changing any annotation, or any log call → this skill.
- One class per module, `__all__`, the `__init__.py` re-export contract, import forms →
  `python-packaging`.
- Deriving a concrete class or module name → `naming`; deriving a concrete artifact *path* in a
  hexagonal project → `hex-conventions`, in the `pyhouse-hex` plugin.
- The exception classes themselves → `exception-catalog`.
- Where a module lives and what may import it → `hex-architecture` (in the `pyhouse-hex` plugin) or
  `flat-layered` (in `pyhouse-flat`), whichever style the project uses.
- The shape of a specific artifact → its own skill. This skill is consulted **alongside** them.

## Typing

### `X | None`, not `Optional[X]`

```python
# yes
name: str | None = None
def find(id: UUID) -> Foo | None: ...

# no
from typing import Optional
name: Optional[str] = None
```

PEP 604 union syntax is the default. `Union[A, B]` is equally banned — write `A | B`. This holds
everywhere, validation models included.

### Never `from __future__ import annotations`

Do not add this import to any module. Projects in this style rely on **runtime annotation
introspection** — the validation library, dependency-injection providers, dataclass `__post_init__`
checks, ORM/Core column inference. Stringified annotations break those tools silently, and the failure
shows up as a mis-parsed field rather than an error. Modern runtimes give PEP 604 syntax without it.

If a third-party tool tells you to add it, the fix is to change the annotation, not to silence the
runtime.

**A self-referential annotation is written as a string literal.** A class that annotates with its own
name — `def satisfies(self, required: "Foo") -> bool` inside `class Foo`, a factory classmethod annotated
`-> "Foo"`, a node whose field is `parent: "Foo | None"` — quotes that one annotation. The name is not
bound until the class statement finishes, so an unquoted reference raises `NameError` at
class-definition time, and the future import that would have deferred it is banned above. Quote only the
self-reference; every other annotation stays bare, so runtime introspection keeps working everywhere it
matters.

### The interpreter floor

**Every form in this skill needs Python 3.10, and nothing in this catalogue needs more.** PEP 604
unions, `X | None`, and the `collections.abc` generics that replace the `typing` aliases all land in
3.10; the ban on `from __future__ import annotations` above is affordable precisely because 3.10 gives
that syntax natively. So **3.10 is the catalogue's own floor** — the oldest interpreter its templates
are written to run on.

Two things are misremembered as raising it, and neither does:

- **A library raises the floor only when its own minimum is above 3.10.** Every binding this
  catalogue's templates use runs on 3.10, so adopting one raises nothing; check the minimum of any
  library added beyond them before assuming otherwise, and record the answer with the floor rather than
  re-deriving it.
- **A feature reaching the standard library on a later interpreter does not raise the floor either**,
  as long as the project takes it from a third-party package instead. Whether to take it at all is the
  decision of the skill that generates the value, not of this one — but it is taken **once, for the
  whole project**, never in half the code.

**A project's own floor is the project's to choose, and like the line length it is chosen once, at
setup, and written down.** Three settings name that one interpreter and must stay in step:
`requires-python` in the root `pyproject.toml`, the linter's `target-version`, and the type checker's
`python_version`. All three name the **oldest** interpreter the project must run on, never the newest
one on the developer's machine — a form the linter permits because `target-version` drifted upward is a
form that fails on the deployment runtime. A member of a workspace never restates them; the root
settles them and every member inherits.

Where a template in this catalogue shows a concrete value it writes `>=3.12` and `py312`. That is one
project's choice shown whole, not a requirement: substitute the project's floor, at or above 3.10, in
all three places at once.

### Full coverage on every signature

Every function, method and `__init__` parameter is fully annotated, return type included. `-> None` is
required on a procedure. Lambdas inside business logic are forbidden — use a named function; a lambda in
`dataclasses.field(default_factory=...)` is fine because it carries no annotations.

This includes test code: a fixture annotates what it yields (`-> AsyncIterator[T]`), a builder annotates
its return, a parametrize hook types its argument. Type-checking `tests` at parity with `src` is only
possible because of this.

### `Any` only at raw external boundaries

`typing.Any` is permitted only where data has not yet been parsed:

- raw deserialized JSON before validation;
- a third-party SDK return type not yet narrowed.

Related convention: when collecting heterogeneous values, use `dict[str, object]`, not `dict[str, Any]`
— as in `context: dict[str, object]` on an exception — because `object` forces explicit narrowing at the
point of consumption.

Past the boundary — in business logic, a handler body, a run function — `Any` is forbidden. If a type is
hard to express, introduce a `TypeAlias` or a small dataclass.

### `TypeAlias` for repeated complex types

```python
from typing import TypeAlias

FooKey: TypeAlias = tuple[UUID, int]
```

Use one whenever the same composite — a `tuple[…, …]`, a `dict[str, frozenset[UUID]]`, a callable
signature — appears in more than one signature. Place it at the top of the module owning the concept,
after imports and before classes, and re-export it via `__all__` if it crosses module boundaries. For a
module-internal one-shot type, write the type out; a premature alias hides intent.

### Immutable collections on shared value types

A type that is frozen, hashed, compared, or passed across a boundary uses **immutable** collections, so
it cannot be mutated by a holder that was only meant to read it.

| Mutable | Immutable equivalent |
|---|---|
| `list[T]` | `tuple[T, ...]` when ordered, `Sequence[T]` for a read-only view |
| `set[T]` | `frozenset[T]` |
| `dict[K, V]` | `Mapping[K, V]` for a read-only view, a frozen dataclass for a fixed-shape record |

```python
@dataclass(frozen=True)
class Foo:
    id: UUID
    bar_ids: frozenset[UUID]
    items: tuple[Item, ...]
```

Conversion happens at the boundary: the caller converts — `bar_ids=frozenset(payload.bar_ids)`,
`items=tuple(item_inputs)`. A wire schema may hold `list[...]`, the validation library's natural shape;
the frozen type stores the frozen form.

Ordinary procedural code may use mutable collections **internally** — loop accumulators, row building —
but anything crossing into a frozen type is converted first.

*In a hexagonal project this binds the whole of `domain/`, without exception. In a flat-layered service
it binds the frozen result and payload dataclasses in `schemas/`, and nothing forces it on a local
accumulator.*

### A record that crosses a boundary is a declared type

A value that leaves the scope that built it — returned from a client, handed to a run function, passed
between packages, stored on another object — arrives somewhere that has to know its shape. A bare
`dict`, a bare tuple or a forwarded `**kwargs` does not carry that shape: the receiving side learns the
keys by reading the sender, the checker verifies nothing, and a renamed key fails at the line that
reads it rather than at the line that changed it.

**Anything with a fixed set of named fields is declared once, as a type, and passed as that type.**
The declaration is a frozen dataclass in the ordinary case — the form the table above already names for
a fixed-shape record — or the validation library's model where the same boundary is also where the data
is parsed.

| Being passed | Declare instead |
|---|---|
| a `dict` whose keys are known when the code is written | a frozen dataclass, or a validation model at a parse boundary |
| a tuple whose positions mean different things | a frozen dataclass; a `TypeAlias` only when it is genuinely n of one thing |
| `**kwargs` forwarded and unpacked further down | named parameters, or one parameter of a declared type |

A `dict` is still the right type where the **keys are data**: a lookup keyed by id, a count per
category, a payload whose keys are not known until runtime. The rule is about a *record* — a fixed set
of named fields — not about every mapping. `dict[str, object]` for heterogeneous values, above, is that
case and is unaffected.

`TypedDict` declares the keys but leaves the object a `dict`: nothing is checked at construction, and
there is no type to hang an invariant or a method on. Use it only where a mapping's shape must be
described without changing the object — a third-party call that requires a literal `dict` — never as
the default record form. `NamedTuple` has no use here at all; a frozen dataclass gives the same
immutability without the positional half nobody wanted.

Conversion happens at the boundary, the same way the collection conversions above do: the raw form is
parsed or constructed into the declared type at the edge, and the declared type is what travels inward.

### Which builtin represents which kind of value

A scalar whose kind constrains its representation takes the type that carries the constraint, not the
one that is shortest to write:

- **An exact decimal quantity is `decimal.Decimal`** — money, a rate, anything summed, compared for
  equality, or shown to someone who will check the arithmetic. A binary float cannot represent most
  decimal fractions exactly, so the same total added in a different order is a different number and an
  equality check on it is a coin toss. A genuine measurement, carrying no exactness claim, stays a
  `float`.
- **An instant is a timezone-aware `datetime`.** A naive one carries no offset, so two of them cannot
  be compared or subtracted correctly once anything runs in a second zone, and every store it passes
  through is free to reinterpret it. A calendar day with no instant in it stays a `date`.
- **An identifier is `uuid.UUID`, not `str`.** The string form belongs at the edges — a log field, a
  path parameter, a wire model — and the conversion happens there. Inside, a swapped identifier is then
  a type error rather than a lookup that quietly returns nothing.

These are representation rules: they say which builtin holds the value. **Whether a constrained scalar
also earns a named type of its own** — an amount that must be non-negative, a code that must match a
pattern — is an architecture question this skill does not answer. The hexagonal family answers it with
a value object whose invariant is checked at construction (`hex-domain-model`, in the `pyhouse-hex`
plugin); a service with no domain layer checks it where the value enters and keeps the scalar.

### Protocols

- `typing.Protocol` for an interface, where the architecture calls for one at all. (A flat-layered
  service introduces one only when a second real implementation exists; the hexagonal family defines
  ports by default. Each family's own rule is in `flat-layered`, in the `pyhouse-flat` plugin, and
  `hex-domain-ports`, in `pyhouse-hex`.)
- `@runtime_checkable` **only** when `isinstance(x, IProtocol)` is genuinely needed, and never in a hot
  path: it walks the protocol's attributes on every call.
- A protocol's method signatures carry full annotations like any other function. The `...` is the
  **method body**, never a parameter default.

### Validation models

- Model field types use the same `X | None` and PEP 585 generic forms — `list[int]`, `dict[str, str]`,
  not `List[int]` / `Dict[str, str]`. The forms above hold here with no exemption.
- **A constraint is declared on the field it bounds, in the annotation**, so the accepted shape reads
  top to bottom in one pass and a generated schema can be derived from it. Not an imperative validator
  method, and not a default-carrying assignment standing in for a constraint on a field that has no
  default — a field is optional because it has a default, never because declaring the bound was
  awkward. Under the validation library this catalogue's templates bind, that is
  `Annotated[int, Field(ge=1)]` rather than `field: int = Field(default=…)`; under another, it is
  whatever that library declares beside the field.

### Collections from `collections.abc`

| Use | Not |
|---|---|
| `collections.abc.Sequence` | `typing.Sequence` |
| `collections.abc.Mapping` | `typing.Mapping` |
| `collections.abc.Iterable` | `typing.Iterable` |
| `collections.abc.AsyncIterator` | `typing.AsyncIterator` |
| `collections.abc.Callable` | `typing.Callable` |

The `typing.*` aliases have long been deprecated; `collections.abc` keeps imports consistent and avoids a
needless `typing` import.

## Logging

A log line exists to be **queried** — filtered, grouped, counted, alerted on. Prose cannot be queried, so
every occurrence worth recording produces **exactly one structured event**: a name plus fields, never a
sentence with values spliced into it. Four obligations, whichever library provides them:

- **One logger, obtained at module level.** Not per call, not per instance, and not a second logging
  mechanism running alongside the first — two mechanisms split one event stream in half and neither half
  is complete. `print()` is not one of them, outside a deliberate entrypoint debug path.
- **One event per occurrence.** The same occurrence logged twice is two incidents on the dashboard.
- **The event name is a stable contract** — snake_case, `<subject>_<past_tense_verb>`.
- **Identifiers and counts ride as fields**, never interpolated into the message.

Plus one allocation rule — *which* layer logs an error — stated at the end of this section.

### Binding — `structlog`

```python
import structlog

log = structlog.get_logger()

# inline fields
log.info("foo_created", foo_id=str(foo.id), caller_id=str(cmd.caller_id))

# bound context for a sequence of calls
log_ctx = log.bind(import_id=str(import_id))
log_ctx.info("import_started", row_count=len(rows))
log_ctx.info("import_completed", imported=imported, skipped=skipped)
```

### Event names and fields are a contract

The event name is what a query matches on: `foo_created`, `bar_archived`, `foos_imported`,
`ingest_run_failed`. These are stable strings — **do not rename once shipped**, because dashboards and
alerts key on them. `naming` lists them among the frozen external contracts for that reason.

Identifiers and counts are fields: the primary id as `<subject>_id`, the actor as `caller_id` where one
exists, counts (`imported`, `skipped`, `errors`) for a bulk operation.

```python
# yes
log.info("foo_created", foo_id=str(foo.id))

# no — nothing in this line can be filtered by foo, grouped, or counted
log.info(f"created foo {foo.id}")
```

### Never log and re-raise the same event

`log.x(...)` immediately followed by `raise` in the same scope is two entries for one event, and there is
**no sanctioned exception**. A scope that re-raises is not the scope that will explain the failure: the
detail it was about to log belongs in the exception it raises — the structured fields in `context`, the
original error in `__cause__` through `from exc` (`exception-catalog`). The layer that stops the
exception has both, and it is the layer that logs.

```python
# yes — translate, carry the detail forward, stay silent
try:
    await self._session.execute(stmt)
except IntegrityError as exc:
    raise ConflictError(
        "foo name already exists",
        {"field": "name", "constraint": "uq_foos_name"},
    ) from exc

# no — the layer that stops this will log it again, off the translated exception
except IntegrityError as exc:
    log.warning("foo_name_conflict", foo_name=foo.name)
    raise ConflictError("foo name already exists", {"field": "name"}) from exc
```

Level guide, for the layer that does log: `warning` for an expected rule violation surfacing at a
boundary — uniqueness, a foreign key; `error` for an unexpected failure — a network timeout, a
third-party 5xx, malformed data.

A branch unreachable through the normal write path — a constraint standing as defence in depth behind a
rule that already refuses — is **not** excused from logging: if it fired, the rule was bypassed, and that
is the most interesting line in the log. It is logged by whoever stops it, under the same allocation as
any other failure.

### What never reaches a log line

- A full request or response body → log identifiers and counts only; bodies may carry personal data.
- A password, bearer token, API key or connection string → log a length or a hash, never the value.
- A `UUID` object rather than `str(uuid_value)` → some sinks render it poorly.

The first two reach an exception's `context` as well, because the layer that logs renders `context`
verbatim into the log line. `exception-catalog` owns that statement of the rule.

### Who logs what — one principle, two allocations

**An error is logged once, by the layer that can add context and will not re-raise it.** That is the
whole rule. The two families differ only in *which* layer that is, because they differ in which layer is
contractually obliged to re-raise.

**Hexagonal projects** propagate every error to a single central handler, so the layer that does not
re-raise is the entrypoint:

| Layer | May log |
|---|---|
| `domain/` | **Nothing.** Zero IO includes the log socket; raise an exception carrying `context` instead. |
| `infrastructure/` | **Nothing.** An adapter translates and re-raises, so it is never the layer that stops; the low-level detail goes into the translated exception's `context`, where the layer that does log will find it. |
| `application/` | **Successes only**, at `info`, after the operation completes. Never errors — they propagate. |
| entrypoints | Errors, once, at the central handler, with request context attached. |

**The level the central handler uses**, since this table claims the entrypoint row:

- **4xx class** — the caller's request was wrong (validation, conflict, not-found, unauthorized,
  forbidden) → `warning`. Nothing is broken; do not page on it.
- **5xx class** — a `DomainError` whose status is 5xx, including an upstream failure → `error`.
- **Anything that is not a `DomainError`** → `error`, logged at the handler *before* the framework
  converts it to a 500. That is the only place it will ever be seen.

This skill owns the level rule; the **call** that implements it belongs to the entrypoint template that
has a central handler — `error_handler.py` in `hex-restapi-app`, in the `pyhouse-hex` plugin. The split
is deliberate: the rule is a logging-level rule and outlives any one framework, the call is
framework-shaped.

**Flat-layered services** have no such contract — nothing above a failure is obliged to re-raise into one
handler — so the layer that will not re-raise is usually the point of failure itself: **log the failure
there, with its context**. Where a scope does re-raise (a client translating an SDK error for its
caller), the principle points the same way: that scope stays silent and whoever stops the exception logs
it. The universal obligations above hold unchanged.

## Comments

Default to **no comments**. Where one is warranted it is a single short line of non-obvious *why* —
never *what*, never a multi-line block. The scope of that rule is not uniform across the tree:

- **In source**: the rule as stated, unconditionally.
- **In migrations**: the same form — a revision is code, not evidence. The *why* worth writing is why
  this DDL is spelled out by hand rather than read from live metadata; a block retelling what
  `create_table` does is exactly what the rule is written against. **A revision module's docstring is not
  a comment, and this rule does not reach it** — a docstring carrying ten lines of *why* is legal there
  and is not to be cut down.
- **In tests**: the same holds inside a test body. Additionally legal is a **multi-line section banner**
  above a group of tests, when it says *what* the group pins and *why* it is pinned that way — which
  behaviour the group stands as evidence for, that the clock is the real one and not a substituted
  double, that both routes have to be exercised. A banner that retells what the tests below it do →
  stop; that is the code said twice, and it is the form that goes stale. *This allowance rests on banners
  having held so far, not on a test of failure, so it carries its withdrawal condition: if a banner is
  ever found lying or silently out of date, the allowance goes and tests fall under the source form.*

Structural labels are not comments worth writing: no `# Arrange` / `# Act` / `# Assert`, no `# imports`,
no `# helpers`.

## Other bindings

The structured logger is the one library this skill binds; typing and comments bind none.

- **Stdlib `logging` plus a structured adapter** — `logging` configured once with a JSON formatter, the
  event name as the record's message and the fields passed through `extra=` or a `LoggerAdapter` (or the
  whole module kept behind a thin structured wrapper). What changes: how the logger is obtained and
  configured, and how fields reach the record. What does not: one event per occurrence, the
  `<subject>_<past_tense_verb>` name and its never-rename contract, identifiers and counts as fields
  rather than interpolated text, the never-log-and-re-raise rule, and the allocation table.
- **What that binding buys**, so it reads as a choice rather than a fallback: third-party libraries log
  through `logging`, so on this binding their records land in the same stream with no bridge to
  configure. What it costs is that nothing in the library enforces the field discipline — the obligations
  above have to be held by the author, where a keyword-field interface makes them the path of least
  resistance.

## Rules

1. Apply the union, generic and runtime-annotation forms in **Typing**, including validation models.
2. Check complete signature coverage in source and tests; use named functions for business logic.
3. **Settle the interpreter floor once, at setup, at or above the catalogue's 3.10**, and keep
   `requires-python`, the linter's `target-version` and the type checker's `python_version` naming
   that same oldest supported interpreter.
4. Restrict `Any` to the two raw-boundary cases; use the documented heterogeneous-value and repeated-type
   forms after parsing.
5. Check shared value types against the immutable-collection table and convert at their boundary.
6. **A record crossing a boundary is a declared type, not a bare `dict`, tuple or forwarded
   `**kwargs`.** A fixed set of named fields is declared once and passed as that type; a mapping whose
   keys are data stays a mapping. `TypedDict` describes a shape without creating a type and is for the
   case that must stay a `dict`; `NamedTuple` is not used.
7. **A scalar takes the builtin that carries its kind** — an exact decimal quantity, an instant with an
   offset, an identifier as an identifier — and converts to a string form only at the edge that needs
   one. Whether it also earns a named type of its own is the architecture family's question, not this
   skill's.
8. Apply **Protocols** only where the architecture calls for an interface; reserve runtime checking for
   the documented need.
9. Check validation constraints and abstract collection imports against their dedicated typing sections.
10. **One logger, obtained at module level, and one structured event per occurrence.** No `print()`
    outside a deliberate entrypoint debug path, and no second logging mechanism beside the configured one
    — two mechanisms split the event stream and neither half is complete.
11. **Give every event a stable snake_case `<subject>_<past_tense_verb>` name, and carry its identifiers
    and counts as fields rather than interpolating them into the message.** A value inside a sentence
    cannot be filtered, grouped or counted, and a renamed event silently breaks every dashboard keyed on
    the old string.
12. **Log an error once, in the layer that can add context and will not re-raise it** — the entrypoint's
    central handler in a hexagonal project, the scope that stops the failure in a flat one. A scope that
    re-raises does not log; the detail it would have logged goes into the exception's `context`.
13. Check logged fields against **What never reaches a log line** before emitting them, and apply the
    same two bans to anything placed in an exception's `context`.
14. Apply **Comments** by location, preserving its revision-docstring and test-banner allowances and
    their stated limits.
15. Check casts, untyped variadic arguments and type suppressions against the typing hard stops below.

## Hard stops

Typing:

- `from __future__ import annotations` anywhere → stop, runtime annotation introspection breaks silently
  with stringified annotations.
- A class annotating with its own bare name inside its own body → stop, quote that one annotation
  (`required: "Foo"`); unquoted it is a `NameError` at class-definition time, and the future import that
  would defer it is banned.
- `Optional[X]` or `Union[A, B]` → stop, use `X | None` / `A | B`.
- Bare `Any` outside the documented external-boundary cases → stop, introduce a `TypeAlias` or a small
  dataclass; do not let `Any` spread.
- Untyped `**kwargs` / `*args` in business logic → stop, a dataclass is missing.
- A `dict` or tuple with a fixed set of known fields crossing a boundary — returned from a client,
  passed between packages, handed to a function that unpacks it → stop, declare the record as a type.
  A mapping whose keys are data is not this case.
- `float` for money or any other exact decimal quantity, or a naive `datetime` for an instant → stop,
  `Decimal` and an aware `datetime`; the first disagrees with itself under reordering, the second under
  a second timezone.
- An unannotated fixture, builder or test helper → stop, the test surface is type-checked at parity with
  source.
- `cast(...)` to silence a type error → stop, fix the type. `cast` is acceptable only to narrow after a
  runtime guard the checker cannot follow, which is rare.
- A type-ignore comment with no reason → stop, name the specific rule and give a brief explanation.
- A mutable collection on a frozen dataclass field → stop, use the immutable equivalent.

Logging:

- `log.x(...); raise` in the same scope → stop, that is two entries for one event; put the detail in the
  exception's `context` and let the layer that stops it log.
- A log call emitting an interpolated sentence — no event name, no fields (`log.info(f"created foo
  {foo.id}")`) → stop, nothing in that line can be filtered, grouped or alerted on; emit an event name
  plus the identifiers as fields. This fires on every binding, the stdlib one included.
- `print()` outside an entrypoint debug path behind a flag → stop, use the structured logger.
- A second logging mechanism introduced beside the one already configured → stop, one logger everywhere;
  two split the event stream and neither half is complete.
- An event name that is not snake_case past tense (`FooCreated`, `create-foo`) → stop, rename it to
  `foo_created`. Once shipped, never rename — dashboards depend on the string.
- Logging a full body, a secret, or a bare `UUID` object → stop.
- In a hexagonal project: any log call in `domain/` or `infrastructure/`, or an error logged in
  `application/` → stop, see the allocation table. An adapter translates and re-raises, so it never logs
  — the detail goes into the translated exception's `context`.

Comments:

- A comment that is not a non-obvious *why*, or one running past a single short line → stop.
- A structural label (`# Arrange`, `# helpers`) → stop, delete it.
- A test banner that retells what the tests do rather than what they pin → stop.
