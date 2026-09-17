---
name: flat-layered
description: Use when structuring a worker, crawler, pipeline, ETL job or integration service whose family is already settled as flat — one service on its own by default, and a workspace member under the same rules. Defines packages named for the technical roles the service actually has, the import contract between those roles, the settings class each configured component owns, the single-implementation client, and why no `Protocol` appears until a second real implementation does. A service's data access has its own package whose rules are `flat-persistence`; several services sharing one repository is `flat-monorepo`; an unsettled family is `architecture-choice`.
when_to_use: Also when asked for a worker's or a pipeline's package layout, where a client class or a settings class belongs, whether a dependency deserves an interface, or how to lay out a single-service repository with no workspace around it.
---

# Flat-Layered Architecture — package-by-tech, no ports

Covers project layout for services where the ports-and-adapters split (domain/application/
infrastructure/entrypoints, `Protocol` ports, DIP) would add indirection with nothing to protect. The
code groups by **technical role**, dependencies point wherever they need to, and an interface is
introduced only when a second real implementation is about to exist — not in anticipation of one.
This skill assumes the family is already chosen; `architecture-choice` chooses it.

**The subject is one service on its own** — its own repository, its own package, and its own datastore
where it has one. A service that shares a repository with siblings is the same service under the same
rules with a workspace root above it, and that root is a separate skill. Nothing below requires one.

The style has established names: what the literature calls **package by layer**, after Simon Brown, with
what Fowler calls **transaction scripts** above it. `architecture-choice` carries the same clause where
the family is chosen.

## When to use vs. neighbours

- The style is not settled yet — a greenfield service, or one that may have outgrown the family it was
  built in → `architecture-choice`, which owns the hex-vs-flat decision in full: the question that
  settles it, what each family costs, and the cases the bullets below do not cover. It is universal, so
  it is there whichever family plugins are installed.
- The service enforces business invariants that must survive a change of database, queue or framework
  → not this skill; use a hexagonal / ports-and-adapters layout instead — `hex-architecture`, in the
  `pyhouse-hex` plugin. Nothing in this skill applies there.
- More than one entrypoint drives the same domain logic (REST + gRPC + a queue consumer, all calling
  the same rules) → not this skill; that shared core is exactly what ports exist to protect.
- A dependency already has, or is about to get, a second real implementation (two providers, a fake for
  tests standing in for a real backend) → not this skill for that dependency; extract a narrow
  `Protocol` for it and keep the rest flat.
- A single script with no more than a couple of modules → still too heavy for this skill; just write
  the script (`architecture-choice` states what does apply to one).
- The question is not the layout but the boundary — split vs merge, contract vs shared knowledge,
  how much structure something deserves → `coupling` decides that; it loads alongside this skill,
  never instead of it.
- The service is mostly "call external system A, transform, call external system B/C, repeat" with one
  implementation per system and no rules worth isolating → this skill.
- Where this service's SQL, table definitions and write path live → `flat-persistence`, which owns the
  storage package this skill's skeleton creates a slot for. A service with no datastore skips it.
- This service is one of several sharing one repository → this skill still covers its own internal
  layout unchanged; the repository root, the member split and the tooling settled once are
  `flat-monorepo`. A lone service needs none of that.
- What triggers a run — a loop, a cron entry, a stream, or durable execution once it is earned →
  `flat-entrypoint`.

Four skills apply here exactly as they do anywhere else, and this skill does **not** restate them:

- One class per module, `__all__`, the `__init__.py` re-export contract, import forms →
  `python-packaging`.
- Annotation forms, collection types, the shape a record takes as it crosses a package boundary,
  logging, comments → `python-style`.
- The `exceptions/` catalog and translating SDK errors into it → `exception-catalog`.
- Where boundaries go at all — split vs merge, contract vs shared knowledge, how much structure a
  component deserves → `coupling`.

## Package names are roles, not vocabulary

The skeleton below is **one worked example**, not a required set of directory names. The rule is *group
by technical role, one role per package*; the names are whatever describes the roles this service
actually has. A service that fetches nothing has no `ingest/`. A service that runs no scheduled passes
has no `jobs/`. A service with no datastore of its own has no `storage/`. A crawler might have `fetch/` and `parse/`; a report pipeline `extract/` and `render/`.

Copying a package name because it appears here, when the service has no such role, is the failure mode
this warning exists to prevent — it produces an empty `jobs/` package and a reviewer who assumes work
lives there. What *is* fixed is the shape of the decision:

- cross-cutting setup — logging, and the process's own settings — sits in modules at the package root,
  never in a package named after the category; and a component with configuration of its own keeps its
  settings module beside it;
- each external system gets one module holding one class;
- run functions are grouped by kind and sit **below** the process that runs them;
- a framework wrapper is isolated in its own package so the work it wraps stays framework-free;
- process definitions sit in one package that everything else can be imported *by*, and that nothing
  imports.

Two or three roles is a normal size. Splitting into seven packages because the example shows seven is as
wrong as putting everything in one.

Naming each one is `naming`'s job, and its rules bind here: a package is named for the
responsibility it holds, never for a generic category word carried over from an example. `worker` is the
word this style attracts and the one to be most suspicious of — it fits a polling loop, a queue-serving
process, an activity class and a run function equally badly.

## Template — package skeleton (worked example)

```
myapp/
├── __init__.py
├── __main__.py                  # the declared entry point — `python -m myapp` selects and runs one
├── settings.py                  # the process's own pydantic-settings class, env-prefixed
├── logging.py                   # structlog/stdlib logging setup, called once at startup
├── durable.py                   # the one framework-guarded helper module (rule 9), where one is needed
├── enums/
│   └── __init__.py               # ONLY vocabulary genuinely used across packages — see rule 11
├── exceptions/
│   └── __init__.py               # one catalog of this service's exception classes
├── schemas/
│   ├── __init__.py
│   └── foo.py                    # Pydantic models / frozen dataclasses — payloads and results
├── services/
│   ├── __init__.py
│   └── foo_client.py             # one concrete class per external system, SDK exceptions caught here
├── storage/
│   ├── __init__.py
│   ├── settings.py               # this component's own class and prefix — `flat-persistence`
│   ├── foo_table.py              # this service's own table definitions
│   └── foo_storage.py            # the ONLY place a statement is built or a connection opened
├── ingest/
│   ├── __init__.py
│   └── foo_ingest.py             # run functions that PULL from upstream and land raw rows
├── jobs/
│   ├── __init__.py
│   └── foo_recheck.py            # run functions over ALREADY-STORED data
├── temporal/
│   ├── __init__.py
│   ├── activities.py             # the only package that imports temporalio
│   └── workflows.py
└── entrypoints/
    ├── __init__.py
    ├── temporal_worker.py        # process: serves the task queue
    └── foo_stream.py             # process: a long-lived continuous stream
```

### What each package is for

The four execution packages are the part people get wrong, so they are defined by **what may import
what**, not by vibes:

| Role | Holds | May import | Imported by |
|---|---|---|---|
| data access (`storage/`) | table definitions, the write path, and the mapping from stored rows back to this service's own types | schema packages, and the settings values handed to it | the run-function packages, the framework wrapper, entrypoints |
| upstream pull (`ingest/`) | one function per pull: fetch → normalize → write rows | client, schema and storage packages | the framework wrapper, entrypoints |
| stored-data pass (`jobs/`) | one function per pass over already-stored data: recheck, classify, expire | client, schema and storage packages | the framework wrapper, entrypoints |
| framework wrapper (`temporal/`) | `@workflow.defn` / `@activity.defn` wrappers, nothing else | the two above, plus schemas | entrypoints |
| process definitions (`entrypoints/`) | build dependencies, run one process | everything | nothing |

The parenthesised names are what this example calls them; the **columns** are the contract.

**"Run function"** is the term used throughout this family for the unit those two packages hold: a plain
async function that performs one complete run, takes every dependency as a parameter, imports no
framework, and returns an aggregate rather than rows. `run_once` in the templates is a *name for one
particular run function*, whose work genuinely is one pass, and not a convention to copy onto the next
one: what a function is called is `naming`'s decision and it names the work done. The *kind* is
deliberately *not* called a "unit of work" — that name belongs to the
transactional pattern of that name in the other family (`hex-patterns`, in `pyhouse-hex`), and one word
for two unrelated things is how names stop
identifying anything.

**Only a package whose declared role is *framework wrapper* may import the framework** — in these
templates, `temporal/` importing `temporalio`. That single rule is what keeps `ingest/` and `jobs/`
runnable from a plain loop, a test, or a one-off script, and it is what makes switching a service
between continuous and scheduled a wrapper change rather than a rewrite. A workspace-wide grep enforces
it (`test-architecture-rule`).

**One other module holds that role: the framework-guarded helper.** A progress-reporting wrapper that
does nothing outside the framework's own context is the worked case (`flat-entrypoint`, and the
durable-execution templates its body sends you to). It exists precisely so a run function stays
framework-free, which is the rule's purpose, and the grep's allow-list names it. **For a lone service it
is one named module at the root of the service's own package** — `durable.py` in the example above; in a
workspace it is promoted to a shared package instead, and it is the same one exemption. Nothing else is
exempt: a role is declared when the package is created, not assumed from a directory name (in a
workspace, when the member is admitted — `flat-monorepo` rule 2).

A service that never uses Temporal simply has no `temporal/` package; its `entrypoints/` call
`ingest/` and `jobs/` directly. A very small service may collapse `ingest/` and `jobs/` into one
`jobs/` package — but never collapse either into `entrypoints/`, which is what makes the work
untestable without starting a process.

### Template — settings, on pydantic-settings

`myapp/settings.py` — the process's own configuration, beside the modules that hold the rest of the
cross-cutting setup:

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MYAPP_")

    foo_api_url: str
    foo_api_timeout_seconds: float


def get_settings() -> Settings:
    return Settings()
```

**A settings class belongs to the component whose configuration it holds, and lives in a `settings.py`
beside it.** The process's own fields sit here; the storage component declares its connection settings
in its own `settings.py` under its own prefix (`flat-persistence`), and so does any other component with
configuration of its own. `MYAPP_` above is the placeholder for this service's stem, and a component's
prefix extends it with that component's own segment — `MYAPP_STORAGE_` for the storage package. Two
components must never be able to claim one variable. Extending a stem this way keeps them apart only
while the outer class declares no field beginning with the inner segment: `storage_dsn` here would read
`MYAPP_STORAGE_DSN`, the same variable the storage class already claims. Treat each component's segment
as reserved in the classes above it, or give the components stems that do not nest at all.

**The timeout has no default.** A timeout is set from the upstream's observed latency and from what the
caller can wait for, and no single number is right for every deployment — a default here is one
service's tuning frozen into the template, and it hides a missing variable instead of failing on it.
Required fields fail at the first `get_settings()` call, before any work starts.

**Build settings behind a factory, never as a bare module-level instance.** A module-level
`settings = Settings()` runs at import time, so merely importing the package — from a test, from a
type checker, from a sibling module that needs one constant — fails in any environment that has not
set every required variable. The factory pushes that failure to the first real call. The storage package
builds its own settings and its engine behind the same shape (`flat-persistence`).

**`@lru_cache` on a settings factory is conditional, not automatic.** Under rule 7 the process
definition calls the factory once and hands concrete values down, so in a correctly structured service
there is no second call for the decorator to collapse. Add it only where a second caller genuinely
exists — a web framework resolving the factory per request is the case it comes from. Needing one
otherwise is usually the signal that something below the process definition is reading configuration
instead of being handed values, which rule 7 forbids.

### Template — an external-system client, on httpx

`services/foo_client.py` — one concrete class, no Protocol:

```python
import httpx

from myapp.exceptions import FooClientError
from myapp.schemas.foo import FooPayload


class FooClient:
    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        self._base_url = base_url
        self._timeout_seconds = timeout_seconds

    async def fetch(self, foo_id: str) -> FooPayload:
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as http:
                response = await http.get(f"{self._base_url}/foos/{foo_id}")
                response.raise_for_status()
        except httpx.HTTPError as exc:
            raise FooClientError(f"failed to fetch foo {foo_id}") from exc
        return FooPayload.model_validate(response.json())
```

**The client returns a declared type, never the parsed `dict`.** The payload leaves the scope that
built it and arrives in a run function that has to know its fields; a bare mapping makes the receiving
side learn them by reading the sender, and a renamed key then fails where it is read rather than where
it changed. `python-style` owns that rule and its hard stop, and the parse happens here because this is
the edge where the raw form arrives.

The client takes its configuration as **constructor arguments**, not by reaching for a settings
singleton. The entrypoint reads settings once and passes the values down; that is what lets a test
construct the client against a stub base URL without touching the environment.

## Other bindings

- **A console-script entry point in place of `__main__.py`.** Declaring `[project.scripts]` in the
  member's packaging metadata gives the same property the template is chosen for — one declared place
  a process starts from — and swaps `python -m myapp` for a named command. What must not change is the
  count: one declared entry point per runnable process, so a reader can find where the process begins
  without grepping for `asyncio.run`.
- **Another settings library in place of pydantic-settings.** `environ-config`, `dynaconf` or a
  hand-parsed `os.environ` all satisfy rules 7, 8 and 10 — what survives the swap is that a component's
  fields are declared and validated in one class of its own, that required fields have no defaults, and
  that the object is built behind a factory rather than at import time.
- **Another HTTP or SDK client in place of `httpx`.** `aiohttp`, `niquests`, a vendor SDK: the client
  class keeps its shape — configuration through the constructor, the library's own exceptions caught
  and translated inside it, no `Protocol` above it. Only the call and the exception type change.

## Rules

1. **Group by technical role, not by pretend layer** — and give each package the name of the role it
   actually holds, creating only the roles this service has. No `domain/`/`application/` split: there is
   no domain layer to protect.
2. **One responsibility per module even without the layer split.** A module holding several unrelated
   classes, or a function grab-bag with no shared concern, is the failure mode this skill still forbids.
   Split when a module mixes unrelated concerns or grows past a couple hundred lines.
3. **No `Protocol` interface for a dependency with exactly one implementation.** Construct concrete
   classes directly, or via a plain factory function if the object graph is non-trivial. A dependency-
   injection container is unwarranted machinery here: with one implementation per dependency there is
   nothing for it to choose between.
4. **A service's data access lives in one package of its own, and no other package constructs a
   statement or opens a connection.** The table definitions, the write path and the mapping from stored
   rows back to this service's own types sit together, and every other package asks that one package for
   data — the same "no ad-hoc duplication of a single shared thing" reasoning as rule 3, applied to
   storage. A service's SQL is findable in one place or it is everywhere. What that package contains is
   `flat-persistence`. Where several services share one store, that one package is shared between them
   and `flat-persistence` states what changes.
5. **Introduce a port only when a second real implementation is about to be written** — a second
   provider, a fake standing in for integration tests. Judge "about to be written" from the domain,
   not from caution (`coupling`): the credible case is a commodity dependency with a nameable
   alternative the business could plausibly adopt; a sticky one — the main datastore, the identity
   provider — never qualifies, however generic it looks, and stays concrete with test doubles made
   by subclassing (`test-principles`). At that point extract a narrow `Protocol` for
   *that one dependency*; do not retrofit the rest of the service.
6. **One exception catalog**, and SDK/library exceptions are translated into it at the boundary — inside
   the client class that called the SDK. Shape and translation rules: `exception-catalog`.
7. **Settings are built by a factory and passed down as values.** A settings module — `myapp/settings.py`
   in the example above — exposes `get_settings()`; the process definition calls it once and hands
   concrete arguments to the clients and run functions it constructs. Nothing below the
   process-definition package imports settings, and no module below it calls a settings factory, its own
   component's included. A settings object built at import time makes the
   package unimportable — by a test, by a type checker, by a sibling module wanting one constant —
   anywhere the environment is incomplete.
8. **Every component that has configuration declares its own settings class, in a `settings.py` beside
   it, under its own environment prefix.** The process's configuration and a storage package's
   connection settings are two components' configuration and two classes, not one class with both sets
   of fields. Each class exposes a factory and stops there — declaring one is not licence to call it
   below the process definition, which rule 7 forbids. **No variable may ever satisfy two components'
   fields.** Sharing a prefix outright is the obvious way to break that; a *nested* prefix is the quiet
   one. `MYAPP_` for the process and `MYAPP_STORAGE_` for its storage package hold only while no field
   on the outer class begins with the inner segment — `storage_dsn` under `MYAPP_` and `dsn` under
   `MYAPP_STORAGE_` are the same variable. Either keep the stems disjoint, or treat each inner segment
   as reserved in the outer class and never declare a field there that begins with it. The failure is
   the same whether the second component is a package inside this service or a storage distribution
   shared with siblings (`flat-persistence` states that package's half).
9. **Only a package whose declared role is framework wrapper may import the framework** — `temporal/`
   for `temporalio` in this example — plus the one framework-guarded helper module the firewall's
   allow-list names explicitly. For a lone service that is a single named module at the root of the
   service's own package — `durable.py` in the example above — and in a workspace it is promoted to a
   shared package instead. The allow-list names that module by path, so the exemption stays one entry a
   reviewer can read. That one rule is what keeps the run functions callable from
   a loop, a test or a one-off script, and it is what makes switching a service's trigger a wrapper
   change rather than a rewrite. The role is declared when the package is created — in a workspace, when
   the member is admitted (`flat-monorepo` rule 2) — never inferred from a directory name.
10. **A tunable with no single right value carries no default.** A timeout is set from the upstream's
    observed latency and from what the caller can wait for; a default is one deployment's tuning frozen
    into a template, and it converts a missing variable into a silent wrong answer instead of a startup
    failure.
11. **An enum lives beside the module that owns it.** A shared vocabulary package holds only what is
    genuinely used across packages, and admission to it runs `coupling`'s test — a blanket category
    package pulls single-owner types away from their owner and stops naming anything.
12. **A failure is logged once, by the scope that will not re-raise it.** Nothing above a failure here
    is contractually obliged to re-raise into a single handler, so that scope is usually the point of
    failure itself — log it there, with its context. A scope that *does* re-raise (a client translating
    an SDK error for its caller) stays silent and lets whoever stops the exception log it; the detail
    rides in the translated exception's `context` (`exception-catalog`). The allocation rule and the
    event-name contract are `python-style`'s.
13. **Test at the boundary, not through fakes of internal abstractions.** Prefer a real integration test
    — a containerized dependency, a stubbed HTTP transport — over mocking a class that has no
    interface. When isolation is needed, subclass the concrete client for one-off failure injection; do
    not introduce a `Protocol` purely to make something mockable. The full ladder is `test-principles`.

## Hard stops

- The service has business invariants that must outlive a change of infrastructure → stop, use a
  ports-and-adapters layout instead (`hex-architecture`, in the `pyhouse-hex` plugin).
- Two or more entrypoints need to share the same business rules → stop, that shared core is what ports
  protect; do not force it flat.
- A dependency is gaining a second real implementation → stop for that one dependency, extract a
  `Protocol`; the rest of the service can stay flat.
- Reaching for a DI container or a Protocol "in case we need to swap it later" with no concrete second
  implementation in sight → stop, that is the anticipatory abstraction this skill exists to avoid.
- A framework import appears outside the package whose declared role is *framework wrapper*, or outside
  the one framework-guarded helper module — `import temporalio` outside `temporal/` in the example
  above → stop, the run function has just been welded to the framework; move the wrapper into the
  framework-wrapper package and leave the body where it was.
- A module builds its settings instance at import time → stop, expose `get_settings()` instead; the
  bare instance makes the package unimportable wherever the environment is incomplete.
- A module below the process definition calls a settings factory, its own component's included → stop,
  the process definition calls it and passes the values down; owning a settings class is not permission
  to read it from inside the component.
- Business logic appears inside a process definition → stop, a process definition wires and runs; the
  work belongs in a run-function package where a test can call it directly.
- A package is being created because the example above shows it, with nothing to put in it → stop, the
  names are roles; a service only has the packages its roles require.
