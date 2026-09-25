---
name: python-style
description: Use when choosing a type annotation, deciding what shape a record takes as it crosses a boundary, deciding what to log, or asking whether a comment belongs here. Owns the 3.13 interpreter floor, `X | None` over `Optional`, the ban on `from __future__ import annotations`, immutable collection types, the rule that a fixed-shape record is a declared type rather than a bare `dict` or tuple, which builtin represents an exact decimal quantity, an instant and an identifier, one structured event per occurrence, and which scope logs an error. Whether a constrained scalar also earns a named type of its own belongs to the architecture family; the error classes themselves are `exception-catalog`.
---

# Python Style

Project-wide rules that are stricter than CPython's defaults and hold **whatever the architecture is** —
a hexagonal app, a flat-layered worker, or a standalone script. Three subjects: what the types look like,
who logs what, and where a comment is warranted.

Only one thing here varies from project to project, and it varies as a *consequence*, not as a separate
rule: an error is logged once, by the scope that can add context and will not re-raise it — and where a
project's errors propagate to decides which scope that is. Everything else is unconditional.

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

**The house floor is Python 3.13.** It is a choice this style makes, not a limit some template
happened to hit: one floor across every project means every template runs as pasted and every reader
meets one set of forms. The catalogue's templates are written against it and use what 3.11–3.13 added
freely — `enum.StrEnum`, `datetime.UTC`, PEP 695 `type` aliases and generic syntax, `AsyncGenerator[None]`
with its defaulted send type.

**A project may raise the floor; it never lowers it.** Raising it is a decision — a library whose own
minimum sits higher, or a form the project wants from a newer interpreter — taken once, for the whole
project, never in half the code. Below 3.13 the templates stop being correct as written, and a project
that back-ports them one form at a time has two dialects in one tree.

**The floor is chosen once, at setup, and written down in three settings that must stay in step:**
`requires-python` in the root `pyproject.toml` (`>=3.13`), the linter's `target-version` (`py313`), and
the type checker's `python_version` (`3.13`). All three name the **oldest** interpreter the project must
run on, never the newest one on the developer's machine — a form the linter permits because
`target-version` drifted upward is a form that fails on the deployment runtime. A member of a workspace
never restates them; the root settles them and every member inherits.

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
hard to express, introduce a `type` alias or a small dataclass.

### A `type` alias for repeated complex types

```python
from uuid import UUID

type FooKey = tuple[UUID, int]
```

The PEP 695 `type` statement, not `typing.TypeAlias` — the statement is the form the 3.13 floor gives,
and it is evaluated lazily, so an alias may name a class defined further down. Use one whenever the same composite — a `tuple[…, …]`, a `dict[str, frozenset[UUID]]`, a callable
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
it binds the frozen result and payload records that pass between its packages, wherever the service
keeps them, and nothing forces it on a local accumulator.*

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
| a tuple whose positions mean different things | a frozen dataclass; a `type` alias only when it is genuinely n of one thing |
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

Plus one allocation rule — **an error is logged once, by the scope that can add context and will not
re-raise it**, traced outward from the raise to the first scope that handles the exception rather than
re-raising it. A scope that re-raises stays silent: the detail it would have logged rides in the
exception instead — the fields in `context`, the original error in `__cause__` through `from exc`
(`exception-catalog`) — where the scope that stops it will find both.

A branch unreachable through the normal write path — a constraint standing as defence in depth behind a
rule that already refuses — is **not** excused from logging: if it fired, the rule was bypassed, and that
is the most interesting line in the log. It is logged by whoever stops it, under the same allocation as
any other failure.

**Read the sibling `LOGGING.md` before writing a log call, naming an event, or deciding which scope logs
a failure.** Only this file is loaded automatically, so open it rather than working from the obligations
above: it carries the `structlog` binding, the event-name and field contract with its worked examples,
the never-log-and-re-raise case and its level guide, where a failed undo under compensation is logged, how the
allocation rule resolves in a hexagonal and in a flat-layered project, and the stdlib `logging`
alternative that satisfies the same obligations.

### What never reaches a log line

- A full request or response body → log identifiers and counts only; bodies may carry personal data.
- A password, bearer token, API key or connection string → log a length or a hash, never the value.
- A `UUID` object rather than `str(uuid_value)` → some sinks render it poorly.

The first two reach an exception's `context` as well, because the scope that logs renders `context`
verbatim into the log line. `exception-catalog` owns that statement of the rule.

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

## Rules

1. Apply the union, generic and runtime-annotation forms in **Typing**, including validation models.
2. Check complete signature coverage in source and tests; use named functions for business logic.
3. **Settle the interpreter floor once, at setup, at the house floor of 3.13 or above**, and keep
   `requires-python`, the linter's `target-version` and the type checker's `python_version` naming
   that same oldest supported interpreter. A project may raise the floor, never lower it.
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
12. **Log an error once, in the scope that can add context and will not re-raise it** — traced outward
    from the raise to the first scope that handles the exception rather than re-raising it; a project
    that funnels failures into one handler makes that handler the scope. A scope that re-raises does
    not log; the detail it would have logged goes into the exception's `context`. The one failure a
    re-raising scope stops — an undo's, under `exception-catalog`'s best-effort compensation — ends
    there, so that scope logs it: one `warning` event naming the failed undo, before re-raising the original.
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
- A `requires-python`, `target-version` or `python_version` below 3.13, or the three naming different
  interpreters → stop, set all three to the house floor or one above it; below it the templates are not
  correct as written, and three disagreeing settings let a form pass the linter that fails at runtime.
- Bare `Any` outside the documented external-boundary cases → stop, introduce a `type` alias or a small
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
  exception's `context` and let the layer that stops it log. A failed undo stopped and logged before the
  original is re-raised is two events, not this case.
- An undo's failure stopped under best-effort compensation with no log line, or logged at `error`, or
  logged by the undo itself → stop, the compensating scope logs one `warning` naming the failed undo; it
  is the only record that an effect was left behind.
- A log call emitting an interpolated sentence — no event name, no fields (`log.info(f"created foo
  {foo.id}")`) → stop, nothing in that line can be filtered, grouped or alerted on; emit an event name
  plus the identifiers as fields. This fires on every binding, the stdlib one included.
- `print()` outside an entrypoint debug path behind a flag → stop, use the structured logger.
- A second logging mechanism introduced beside the one already configured → stop, one logger everywhere;
  two split the event stream and neither half is complete.
- An event name that is not snake_case past tense (`FooCreated`, `create-foo`) → stop, rename it to
  `foo_created`. Once shipped, never rename — dashboards depend on the string.
- Logging a full body, a secret, or a bare `UUID` object → stop.
- A scope that re-raises the failure logs it as well → stop, it is not the scope that explains it; the
  detail goes into the translated exception's `context` and whoever stops the exception logs. In a
  hexagonal project that fires on any log call in `domain/` or `infrastructure/`, and on an error logged
  in `application/` other than a failed undo stopped under compensation.

Comments:

- A comment that is not a non-obvious *why*, or one running past a single short line → stop.
- A structural label (`# Arrange`, `# helpers`) → stop, delete it.
- A test banner that retells what the tests do rather than what they pin → stop.
