---
name: hex-architecture
description: Use when the family is already settled as hexagonal and the question is where a module belongs or whether an import may cross a boundary — the four layers, inward-only dependencies, ports, adapters, the composition root. Not whether hexagonal is the right family at all (`architecture-choice`), not where a boundary goes in the first place (`coupling`).
when_to_use: Which layer does this class go in; may infrastructure import application; a cycle between layers; where the DI container or composition root lives; moving code between layers.
paths: ["**/domain/**", "**/application/**", "**/infrastructure/**", "**/restapi/**"]
---

# Hexagonal Architecture — the layer contract

Which layer a thing belongs to, and what it is allowed to reach. This skill owns boundaries only: the
mechanics of packaging a module and spelling an import are `python-packaging`, and they are the same here
as in any other project. What goes *inside* a module belongs to whichever skill owns that artifact.

## When to use vs. neighbours

- Whether this style is the right one at all, or the service belongs in the flat-layered family →
  `architecture-choice`, which owns the hex-vs-flat decision in full and is universal, so it is
  available whichever family plugins are installed.
- The family is settled the other way — a worker, crawler, pipeline or integration service grouped by
  technical role, with no ports until a second real implementation → `flat-layered`, in the
  `pyhouse-flat` plugin. Nothing in this skill applies there.
- Where a boundary goes at all — split vs merge, whether an integration needs a contract, how much
  structure a component deserves → `coupling`, loaded alongside this skill; it owns the boundary
  reasoning, this skill owns the layer layout.
- Deciding where a module belongs, or whether an import may cross a boundary → this skill.
- Moving code between layers, or restructuring a layer package's public surface → this skill for where
  it lands; `python-packaging` for how the module and its re-exports are spelled.
- Editing the body of an existing module, once its layer is settled → that artifact's skill
  (`hex-domain-model`, `hex-domain-ports`, `hex-domain-service`, `hex-application`, `hex-persistence`,
  `hex-restapi-endpoint`, …). Each already assumes the boundaries this skill sets.
- One class per module, `__all__`, the `__init__.py` contract, relative vs absolute → `python-packaging`.
- Choosing an annotation form, a collection type, or where to log → `python-style`.
- The error catalog → `exception-catalog`.
- Deriving a concrete path or class name from an identifier → `hex-conventions`.
- Library substrate, toolchain config, the migration bootstrap → `hex-project-setup`.
- A table, a relational repository, a migration → `hex-persistence`.
- Compensation or a unit of work → `hex-patterns`.
- What the composition root actually binds — providers, lifetimes, settings, teardown, declaration
  order → `hex-wiring`. This skill owns only that the root exists — one module, `src/myapp/containers.py`
  — and that nothing else imports a concrete adapter.
- Turning the import rules below into an automated test → `test-architecture-rule`.

## Is this the right style at all?

This layout costs indirection, and it buys the ability to change a database, a queue or a framework
without touching business rules. That trade is only worth making when there are business rules to
protect; a service with none pays the whole price and gets nothing back, and `flat-layered`, in the
`pyhouse-flat` plugin, is the sibling style for exactly that case.

**The decision itself is `architecture-choice`'s** — the question that settles it, the confirming
evidence, what each family costs, and the cases this section does not cover: a service with rules
*and* heavy integration work, a flat service growing its first rule, a workspace whose members differ,
and the services that need neither family. Read it before writing anything if the trade above is not
already obvious for this service. What follows here assumes hexagonal has been chosen.

How much that protection is worth buying is a volatility question, and `coupling` owns the judgment:
the indirection pays off in proportion to how much the business will keep changing the protected
rules. Around a core subdomain — the part the business reshapes on purpose — ports and layers earn
their keep; around a stable supporting workflow the same structure is cost without a buyer, which is
the flat-layered case. "Not all of a large system will be well designed" is real permission, and
volatility is how you decide where it applies.

## The four layers

Three are core — `domain/`, `application/`, `infrastructure/`; the fourth is one or more entrypoint
packages (`restapi/`, `cli/`, `worker/`). The split exists so the business rules in `domain/` stay
independent of databases, HTTP frameworks and SDKs, and so the dependency graph stays acyclic.

```
                    ┌──────────────────┐
                    │  entrypoints     │   restapi/, cli/, worker/
                    │                  │   build containers.py, translate
                    │                  │   transport ↔ application
                    └────────┬─────────┘
                             │ may import all three core layers
                             ▼
        ┌────────────────────────────────────────┐
        │            application/                │   commands, queries,
        │   (orchestration, no business logic)   │   handlers (CQRS)
        └────────────┬───────────────────────────┘
                     │ imports domain only
                     ▼
        ┌────────────────────────────────────────┐
        │              domain/                   │   entities, VOs, enums,
        │   (pure logic, stdlib only)            │   protocols, exceptions,
        │                                        │   services
        └────────────▲───────────────────────────┘
                     │ implements protocols
                     │
        ┌────────────┴───────────────────────────┐
        │           infrastructure/              │   adapters, repositories,
        │   (third-party SDKs, IO)               │   tables, clients
        └────────────────────────────────────────┘
```

Dependency direction: **`application → domain ← infrastructure`**, and **entrypoints → all three**. No
other arrow is legal.

### What each layer may import

**`domain/`**

- Allowed: stdlib (`dataclasses`, `datetime`, `enum`, `uuid`, `typing`), other domain modules.
- Forbidden: everything else. No third-party libraries — no ORM, no settings library, no HTTP client, no
  cloud SDK, no web framework. No `application/`, no `infrastructure/`, no entrypoint imports.
- Defines: entities, value objects, enums, filter records, domain protocols (`I*` / `ICan*`), domain
  services, domain exceptions, type aliases.
- Zero IO. No file reads, no network, no database, no logging.

**`application/`**

- Allowed: stdlib, the logging library, domain modules. **The logging carve-out exists for one reason**:
  this is the layer that logs business successes (`python-style` allocates logging by layer), so it
  carries the logging facade and nothing else outward. A second third-party import is not covered by it.
- Forbidden: third-party libraries beyond logging. No `infrastructure/` imports, no entrypoint imports.
- Defines: commands, queries, handlers, result DTOs.
- Depends on infrastructure capabilities only through domain protocols, and receives concrete adapters
  by injection.

**`infrastructure/`**

- Allowed: stdlib, any third-party library, domain modules for protocol types and entities.
- Forbidden: `application/` imports, entrypoint imports.
- Defines: adapters implementing domain protocols — relational repositories, object storage, token
  verifiers, renderers.
- Translates between external representations (database rows, HTTP JSON, queue messages) and domain
  objects. Translation happens *inside* the adapter; a raw row or SDK object never leaks upward.

**Entrypoint packages** — **one package per entrypoint kind, named for the kind**, so that dropping or
adding a transport moves one directory. The catalogue spells the HTTP one `restapi/`; `api/`, `web/` and
`http/` are equally good words and nothing depends on which, but two transports sharing a package is a
defect. Siblings are `cli/` and `worker/`.

- Allowed: everything. An entrypoint builds the composition root, `src/myapp/containers.py`, at startup
  and closes it at shutdown; the root itself is that one module, not the entrypoint package.
- Defines: HTTP routes, CLI commands or queue consumers; request and response wire schemas; the central
  error handler; the dependency wiring.
- Wires `containers.py` at startup, resolves handlers, translates transport ↔ application DTOs.

### Top-level layout

```
src/myapp/
├── containers.py         # dependency wiring (the composition root)
├── domain/               # pure business model
├── application/          # CQRS orchestration
├── infrastructure/       # adapters
└── restapi/              # HTTP entrypoint
```

`domain/` and `application/` mirror the same subdomain partition — `domain/foos/`, `application/foos/`.
**`infrastructure/` groups by external tech, not by subdomain**: `infrastructure/postgres/`,
`infrastructure/redis/`, `infrastructure/s3/`, `infrastructure/jwt/` (the derivation is
`hex-conventions`). A new subdomain adds a folder under `domain/` and `application/`; a new external
technology adds one under `infrastructure/`.

## Packaging and imports — not owned here

One class per module, `__all__` placement, the `__init__.py` wildcard re-export contract, relative vs
absolute imports, the collapsed same-package form and import ordering are **architecture-neutral** and
live in `python-packaging`. They apply here unchanged; this skill adds only what the layer split imposes
on top of them:

- **The distribution root's `__init__.py` stays empty** — `python-packaging`'s carve-out for an
  application's root, with a layered reason: aggregating the layer subpackages to the root would make
  `import <package>` transitively pull infrastructure and entrypoint third-party dependencies on every
  use, and would destroy the dependency-free `domain` / `application` import path.
- **A layer package re-exports its subdomain subpackages**, not only its direct modules:
  `from . import bars, foos` + the wildcards + `__all__ = bars.__all__ + foos.__all__`, so
  `from myapp.domain import Foo` resolves.
- **A subdomain package re-exports its whole public surface** — entities, value objects, enums and type
  aliases; every `i_*_repository.py` and `i_can_*.py` protocol; domain services; and in `application/`,
  every command, query, result and handler.
- **The entrypoint package is a side-effect carve-out.** `restapi/__init__.py` must not
  `from .main import *`, because importing `main.py` builds the application object; and the router
  package stays empty, because route modules each export a colliding `router`. A middleware package is
  **not** exempt — its class names are distinct, so it re-exports normally.
- **The declaration sets `python-packaging`'s one-class test lets share a module are, here, two, and
  they are not one rule.**
  The exception catalogue is a single file by principle — `exception-catalog` owns it, and it survives
  any framework. Grouping one resource group's wire schemas into a single module is a REST binding and
  belongs to `hex-restapi-schema`; a project with no HTTP surface has only the first.
- **Cross-layer imports are absolute**, always: `application/` reaching into `domain/`, `restapi/`
  reaching into `application/`. Relative imports stay within one layer. This is `python-packaging`'s
  across-a-package-boundary rule applied to the layer split, not a second rule.

## Rules

The checkable form. Each one is decidable by reading a single import, signature or file path; the
subsections beneath give the reasoning and the judgement calls.

1. **Check every import in `domain/` resolves to `domain/` or the standard library.** Nothing else — no
   third-party package, not even a logger, and no other layer.
2. **Check `application/` imports only `domain/`, stdlib and the logging library**, and **`infrastructure/` only `domain/`,
   stdlib and third-party libraries** — that last allowance is the layer's whole purpose, and the table
   above grants it. Neither imports the other, and neither imports an entrypoint. Only entrypoint
   packages may import all three.
3. **Check no import cycle exists** between modules, subpackages or layers.
4. **Check each new module against the placement table** — pure logic in `domain/`, a rule needing a port
   in `domain/` as a domain service, orchestration in `application/`, anything touching a datastore,
   filesystem, HTTP API or SDK in `infrastructure/`, anything that knows a transport in an entrypoint.
5. **Check every port is a `typing.Protocol` in `domain/<subdomain>/`**, one per module, named
   `I<Thing>Repository` or `ICan<Verb>`.
6. **Check every handler constructor annotates a protocol type, not a concrete class.** `repo:
   IFooRepository`, never `repo: FooRepository`.
7. **Check no adapter inherits from the protocol it satisfies.** Satisfaction is structural and is
   checked at the injection site.
8. **Check the composition root is the only module importing concrete adapters** from
   `infrastructure/` — one module, `src/myapp/containers.py` — and that it binds them at startup, not at
   import time.
9. **Check no module-level singleton holds a stateful resource** — a connection, an engine, a client.
   Inject it.
10. **Check every cross-layer import is absolute** and every within-layer import is relative.

### Direction

- `application/` may import from `domain/` only, beside stdlib and the logging library. Never
  `infrastructure/`, never an entrypoint.
- `infrastructure/` may import from `domain/` only. Never `application/`, never an entrypoint.
- `domain/` may not import anything outside `domain/` and stdlib.
- Entrypoints may import all three core layers.
- **No circular imports.** Ever — between modules, between subpackages, between layers.

### Where new code goes

- Pure logic depending only on data → `domain/`.
- A rule needing a repository or a capability → `domain/`, as a domain service.
- Orchestration of domain plus protocols, id generation, logging business events → `application/`.
- Anything talking to a database, file system, HTTP API or SDK → `infrastructure/`.
- Anything that knows about HTTP, CLI or queues → an entrypoint package.

If you are tempted to import `infrastructure` from `application`, you are wiring a concrete adapter where
a protocol belongs — define the protocol in `domain/` instead. If you are tempted to import `application`
from `infrastructure`, you have an adapter that knows a use case — move the orchestration up to a handler.

### Composition root

- Wiring lives in `src/myapp/containers.py`, a module of the distribution's root package. It is the only place that imports concrete
  adapters from `infrastructure/` and binds them to the domain protocol types `application/` handlers
  consume.
- Wire dependencies at startup, not at import time. Never a module-level singleton for a stateful object
  — a database connection, an HTTP client. Inject them.
- Entrypoints resolve handlers from the container at request time; they do not construct adapters.

### Protocols vs concrete

- A port is a `typing.Protocol` in `domain/<subdomain>/`, named `I<Thing>Repository` for persistence or
  `ICan<Verb>` for a capability, one per module.
- Application handlers depend on **domain protocol types** in their constructor signatures
  (`repo: IFooRepository`), never on concrete classes (`repo: FooRepository`).
- Infrastructure adapters **do not explicitly inherit** from protocols — satisfaction is structural, and
  checked at the injection site. An adapter that imports the protocol it satisfies leaves an unused
  import and gains nothing.

## How to apply

1. Decide the entry path: an HTTP route → `restapi/…`, a scheduled job → `worker/…`.
2. Sketch the use case as a CQRS handler in `application/<subdomain>/`.
3. List what the handler needs from the outside world. Each is a protocol in `domain/<subdomain>/`.
4. Implement each protocol as an adapter under `infrastructure/<tech>/`, grouped by the external
   technology and never by subdomain (`hex-conventions`). Adapters import domain types, translate raw
   payloads, and raise domain exceptions (`exception-catalog`).
5. Wire the adapters in `containers.py` and resolve the handler in the entrypoint.
6. Verify the direction by scanning the new files' imports: `domain/` imports only stdlib and domain;
   `application/` does not import `infrastructure/`; `infrastructure/` does not import `application/`.

### When moving code between layers

- `domain/` → `application/` usually means the rule needed a protocol. Extract the protocol first, then
  move the orchestrator.
- `application/` → `domain/` is rare, and correct only when the logic was pure all along: no IO, no
  protocol calls.
- `infrastructure/` → `application/` almost never happens. If you feel the urge, you probably want to
  move the orchestration up and leave the adapter behind.
- An entrypoint → `application/` is correct when a second entrypoint needs the same logic. Pull it into a
  handler; the entrypoint becomes a thin translator.

## Hard stops

- `infrastructure/` imports `application/` → stop, wrong direction; move the orchestration up to a
  handler.
- `application/` imports `infrastructure/` → stop, that wires a concrete adapter where a protocol
  belongs; define the protocol in `domain/` and inject the adapter.
- `domain/` imports anything outside `domain/` and stdlib → stop, the domain layer is data plus
  invariants only.
- A circular import between modules, subpackages or layers → stop, it always signals a layering
  violation. Fix the structure; do not paper over it with `TYPE_CHECKING` or an in-function import.
- An entrypoint module instantiates a concrete adapter directly → stop, `containers.py` is the only place
  that binds concrete classes.
- An adapter explicitly inherits the protocol it satisfies → stop, satisfaction is structural; remove the
  import.
- A packaging or import rule is being decided here → stop, `python-packaging` owns those; this skill
  adds only the layer-specific re-export rules above.
