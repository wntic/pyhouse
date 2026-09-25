---
name: flat-layered
description: Use when structuring a worker, crawler, pipeline, ETL job or integration service whose family is already settled as flat — one distribution on its own by default, and one of several in a repository under the same rules. Defines the four role kinds a flat service divides into and the import contract between them, the packages named for the roles this service actually has, the settings class each configured component owns, the single-implementation client, and why no `Protocol` appears until a second real implementation does. A service's data access has its own package whose rules are `flat-persistence`; several distributions sharing one repository is `python-workspace`; an unsettled family is `architecture-choice`.
when_to_use: Also when asked for a worker's or a pipeline's package layout, where a client class or a settings class belongs, whether a dependency deserves an interface, or how to lay out a single-distribution repository with no workspace around it.
---

# Flat-Layered Architecture — package-by-tech, no ports

Covers project layout for services where the ports-and-adapters split (domain/application/
infrastructure/entrypoints, `Protocol` ports, DIP) would add indirection with nothing to protect. The
code groups by **technical role**, dependencies point wherever they need to, and an interface is
introduced only when a second real implementation is about to exist — not in anticipation of one.
This skill assumes the family is already chosen; `architecture-choice` chooses it.

**The worked example throughout is a service that fetches from an upstream and lands rows in a store**,
because it exercises every role at once. The roles are not that workload: a service that consumes a
queue and calls an API, one that renders reports, one that only transforms what it is handed, fills the
same four roles and leaves empty the ones it has no use for. A role with nothing in it is not a gap.

**The subject is one distribution on its own** — its own package and its own datastore where it has one.
A service that shares a repository with siblings is the same service under the same rules with a
workspace root above it, and that root is a separate skill. Nothing below requires one.

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
- A dependency already has, or is about to get, a second real production implementation (two providers
  the service switches between) → not this skill for that dependency; extract a narrow `Protocol` for
  it and keep the rest flat. A test double is not a second implementation (rule 13).
- A single script with no more than a couple of modules → still too heavy for this skill; just write
  the script (`architecture-choice` states what does apply to one).
- The question is not the layout but the boundary — split vs merge, contract vs shared knowledge,
  how much structure something deserves → `coupling` decides that; it loads alongside this skill,
  never instead of it.
- The service is mostly "call external system A, transform, call external system B/C, repeat" with one
  implementation per system and no rules worth isolating → this skill.
- Where this service's SQL, table definitions and write path live → `flat-persistence`, which owns the
  data-access role. A service with no datastore skips it.
- This service is one of several distributions sharing one repository → this skill still covers its own
  internal layout unchanged; the repository root, the member split and the tooling settled once are
  `python-workspace`. One distribution on its own needs none of that.
- What triggers a run — a loop, a cron entry, a stream, or durable execution once it is earned →
  `flat-entrypoint`, which owns the run function's own obligations.
- The `pyproject.toml`, the toolchain configuration and the migration environment, laid once when the
  service is created → `flat-project-setup`.

Four skills apply here exactly as they do anywhere else, and this skill does **not** restate them:

- One class per module, `__all__`, the `__init__.py` re-export contract, import forms →
  `python-packaging`.
- Annotation forms, collection types, the shape a record takes as it crosses a package boundary,
  logging, comments → `python-style`.
- The `exceptions.py` catalog and translating SDK errors into it → `exception-catalog`.
- Where boundaries go at all — split vs merge, contract vs shared knowledge, how much structure a
  component deserves → `coupling`.

## The four role kinds and the import contract

A flat service divides into four **role kinds**. The kinds are the architecture; the directory names are
this project's and appear nowhere in the rules. A service creates a package per role it actually has,
names it for that role, and declares which kind it is when it creates it.

| Role kind | Holds | May import | Imported by |
|---|---|---|---|
| **data access** | table definitions, the write path, and the mapping from stored rows back to this service's own types. **The only role that constructs a statement or opens a connection.** | payload packages, and the settings values handed to it | work units, the framework wrapper, process definitions |
| **work unit** | one plain function per complete run — whatever one invocation of the trigger is for. Takes every dependency as a parameter, imports no framework, returns an aggregate rather than its individual results. | client, payload and data-access packages | the framework wrapper, process definitions |
| **framework wrapper** | the framework's own decorators, classes or handlers adapting a work unit to a trigger. **The only role that imports the framework, and it holds no logic of its own.** | work units, plus payload packages | process definitions |
| **process definition** | calls every settings factory once, builds the dependencies, wires them, runs one process. | everything | nothing |

The **columns are the contract**; a service that can fill this table for its own packages has applied
this skill. Everything else in a flat service is a supporting package the four reach for — payload models
and results, one class per external system, the exception catalog, the cross-cutting setup modules at the
package root — and none of them imports any of the four.

**"Run function"** is the term used throughout this family for a work unit. The kind is deliberately
*not* called a "unit of work" — that name belongs to the transactional pattern of that name in the other
family (`hex-patterns`, in `pyhouse-hex`), and one word for two unrelated things is how names stop
identifying anything. What one is called is `naming`'s decision and it names the work done; `run_once` in
the templates names *one* run function whose work genuinely is one pass, not a convention to copy.

**Only a package whose declared role is *framework wrapper* may import the framework.** That single rule
is what keeps the work units runnable from a plain loop, a test, or a one-off script, and it is what
makes switching a service's trigger a wrapper change rather than a rewrite. A repository-wide grep
enforces it (`test-architecture-rule`).

**One other module holds that role, and only once a durable-execution engine is earned: the
framework-guarded helper.** A helper that wraps a framework call so the body keeps one shape whether or
not the framework's context is present is the worked case (`flat-entrypoint`, durable obligation 10).
It exists precisely so a work unit stays framework-free,
which is the rule's purpose, and the grep's allow-list names it by path. **For one distribution it is one
named module at the root of that distribution's own package**; where several share a repository it is
promoted to a library they both depend on, and it is the same one exemption. Nothing else is exempt: a
role is declared when the package is created, never assumed from a directory name.

### The package names

The skeleton below is **one worked example**, not a required set of directory names. The rule is *one
package per role kind the service has*; the names are whatever describes those roles here. A service that
fetches nothing has no upstream-pull package. A service with no datastore of its own has no data-access
package. A service that fetches and parses might call its work units `fetch/` and `parse/`; a report
pipeline `extract/` and `render/`.

Copying a package name because it appears here, when the service has no such role, is the failure mode
this warning exists to prevent — it produces an empty package and a reviewer who assumes work lives
there. What *is* fixed is the shape of the decision:

- cross-cutting setup — logging, and the process's own settings — sits in modules at the package root,
  never in a package named after the category; and a component with configuration of its own keeps its
  settings module beside it;
- each external system gets one module holding one class;
- work units are grouped by kind and sit **below** the process that runs them;
- a framework wrapper is isolated in its own package so the work it wraps stays framework-free;
- process definitions sit in one package that everything else can be imported *by*, and that nothing
  imports.

Two or three packages is a normal size. Splitting into seven because the example shows seven is as wrong
as putting everything in one.

Naming each one is `naming`'s job, and its rules bind here: a package is named for the responsibility it
holds, never for a generic category word carried over from an example. `worker` is the word this style
attracts and the one to be most suspicious of — it fits a polling loop, a queue-serving process, a
wrapper class and a run function equally badly.

## Template — package skeleton (one worked example)

**Every directory name below is this example's choice, filling the role named in the comment.** A
different service fills the same roles under its own names, and creates only the ones it has.

```
src/myapp/
├── __init__.py
├── __main__.py                  # the declared entry point — `python -m myapp` selects and runs one
├── settings.py                  # the process's own pydantic-settings class, env-prefixed
├── logging.py                   # structlog/stdlib logging setup, called once at startup
├── enums.py                     # ONLY vocabulary genuinely used across packages — see rule 11
├── exceptions.py                # one catalog of this service's exception classes
├── schemas/
│   ├── __init__.py
│   └── foo.py                    # Pydantic models / frozen dataclasses — payloads and results
├── services/
│   ├── __init__.py
│   └── foo_client.py             # one concrete class per external system, SDK exceptions caught here
├── storage/                      # ROLE: data access
│   ├── __init__.py
│   ├── settings.py               # this component's own class and prefix — `flat-persistence`
│   ├── foo_table.py              # this service's own table definitions
│   └── foo_storage.py            # the ONLY place a statement is built or a connection opened
├── ingest/                       # ROLE: work units that PULL from upstream and land raw rows
│   ├── __init__.py
│   └── foo_ingest.py
├── jobs/                         # ROLE: work units over ALREADY-STORED data
│   ├── __init__.py
│   └── foo_recheck.py
└── entrypoints/                  # ROLE: process definitions
    ├── __init__.py
    ├── foo_loop.py               # process: the self-scheduling loop
    └── foo_stream.py             # process: a long-lived continuous stream
```

The tree sits under `src/`, beside the distribution's `pyproject.toml`, `tests/` and `migrations/`
(`flat-project-setup`). A service with no framework to wrap has no wrapper package; its process
definitions call the work units directly. One that has a framework adds one wrapper package — a
durable-execution engine's, together with the one guarded helper module, once the engine is earned
(`flat-entrypoint`). A very small service may collapse its two work-unit packages into one — but never
collapse either into the process-definition package, which is what makes the work untestable without
starting a process.

### Template — settings, on pydantic-settings

`src/myapp/settings.py` — the process's own configuration, beside the modules that hold the rest of the
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
beside it.** The process's own fields sit here; the data-access component declares its connection
settings in its own `settings.py` under its own prefix (`flat-persistence`), and so does any other
component with configuration of its own. `MYAPP_` above is the placeholder for this distribution's stem,
and a component's prefix extends it with that component's own segment — `MYAPP_STORAGE_` for the storage
package. Two components must never be able to claim one variable. Extending a stem this way keeps them
apart only while the outer class declares no field beginning with the inner segment: `storage_dsn` here
would read `MYAPP_STORAGE_DSN`, the same variable the storage class already claims. Treat each
component's segment as reserved in the classes above it, or give the components stems that do not nest at
all.

**The timeout has no default.** A timeout is set from the upstream's observed latency and from what the
caller can wait for, and no single number is right for every deployment — a default here is one
service's tuning frozen into the template, and it hides a missing variable instead of failing on it.
Required fields fail at the first `get_settings()` call, before any work starts.

**Build settings behind a factory, never as a bare module-level instance.** A module-level
`settings = Settings()` runs at import time, so merely importing the package — from a test, from a
type checker, from a sibling module that needs one constant — fails in any environment that has not
set every required variable. The factory pushes that failure to the first real call. The data-access
package builds its own settings and its engine behind the same shape (`flat-persistence`).

**`@lru_cache` on a settings factory is conditional, not automatic.** Under rule 7 the process
definition calls the factory once and hands concrete values down, so in a correctly structured service
there is no second call for the decorator to collapse. Add it only where a second caller genuinely
exists — a web framework resolving the factory per request is the case it comes from. Needing one
otherwise is usually the signal that something below the process definition is reading configuration
instead of being handed values, which rule 7 forbids.

### Template — an external-system client, on httpx

`src/myapp/services/foo_client.py` — one concrete class, no Protocol:

```python
import httpx
from pydantic import BaseModel, ValidationError

from myapp.exceptions import FooClientError
from myapp.schemas import FooPayload

__all__ = ["FooClient"]


class _FooPage(BaseModel):
    items: tuple[FooPayload, ...]
    next: str | None = None


class FooClient:
    def __init__(self, base_url: str, timeout_seconds: float) -> None:
        self._base_url = base_url
        self._timeout_seconds = timeout_seconds

    async def fetch(self, foo_id: str) -> FooPayload:
        try:
            async with httpx.AsyncClient(timeout=self._timeout_seconds) as http:
                response = await http.get(f"{self._base_url}/foos/{foo_id}")
                response.raise_for_status()
            return FooPayload.model_validate_json(response.content)
        except (httpx.HTTPError, ValidationError) as exc:
            raise FooClientError("failed to fetch a foo", {"foo_id": foo_id}) from exc

    async def fetch_batch(self) -> list[FooPayload]:
        payloads: list[FooPayload] = []
        cursor: str | None = None
        async with httpx.AsyncClient(timeout=self._timeout_seconds) as http:
            while True:
                params = {"cursor": cursor} if cursor is not None else {}
                try:
                    response = await http.get(f"{self._base_url}/foos", params=params)
                    response.raise_for_status()
                    page = _FooPage.model_validate_json(response.content)
                except (httpx.HTTPError, ValidationError) as exc:
                    raise FooClientError("failed to fetch a page of foos", {"cursor": cursor}) from exc
                payloads.extend(page.items)
                if page.next is None:
                    return payloads
                cursor = page.next
```

**Parsing sits inside the translated scope.** A 200 whose body is not JSON, or is JSON of the wrong
shape, is as much an upstream failure as a 503, so the decode and the validation run inside the same
`try` as the request and leave the client as the catalogue's error, with the identifying input in
`context` and the original chained (`exception-catalog`). A parse written after the `try` lets a
malformed 200 escape as the validation library's own exception. The page model is private to the module:
it describes the upstream's envelope and never leaves this file (`python-packaging`).

**The client returns a declared type, never the parsed `dict`.** The payload leaves the scope that
built it and arrives in a work unit that has to know its fields; a bare mapping makes the receiving
side learn them by reading the sender, and a renamed key then fails where it is read rather than where
it changed. `python-style` owns that rule and its hard stop, and the parse happens here because this is
the edge where the raw form arrives.

The client takes its configuration as **constructor arguments**, not by reaching for a settings
singleton. The process definition reads settings once and passes the values down; that is what lets a
test construct the client against a stub base URL without touching the environment.

## Other bindings

- **A console-script entry point in place of `__main__.py`.** Declaring `[project.scripts]` in the
  distribution's packaging metadata gives the same property the template is chosen for — one declared
  place a process starts from — and swaps `python -m myapp` for a named command. What must not change is
  the count: one declared entry point per runnable process, so a reader can find where the process begins
  without grepping for `asyncio.run`.
- **Another settings library in place of pydantic-settings.** `environ-config`, `dynaconf` or a
  hand-parsed `os.environ` all satisfy rules 7, 8 and 10 — what survives the swap is that a component's
  fields are declared and validated in one class of its own, that required fields have no defaults, and
  that the object is built behind a factory rather than at import time.
- **Another HTTP or SDK client in place of `httpx`.** `aiohttp`, `niquests`, a vendor SDK: the client
  class keeps its shape — configuration through the constructor, the library's own exceptions caught
  and translated inside it, no `Protocol` above it. Only the call and the exception type change.

## Rules

1. **Group by technical role, not by pretend layer** — one package per role kind the service actually
   has, named for the role it holds. No `domain/`/`application/` split: there is no domain layer to
   protect.
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
   `flat-persistence`. Where several distributions share one store, that one package is shared between
   them and `flat-persistence` states what changes.
5. **Introduce a port only when a second real production implementation is about to be written** — a
   second provider the service switches between. A fake for tests never counts: test doubles come from
   the real backend, a stubbed transport or a subclass (rule 13). Judge "about to be written" from the domain,
   not from caution (`coupling`): the credible case is a commodity dependency with a nameable
   alternative the business could plausibly adopt; a sticky one — the main datastore, the identity
   provider — never qualifies, however generic it looks, and stays concrete with test doubles made
   by subclassing (`test-principles`). At that point extract a narrow `Protocol` for
   *that one dependency*; do not retrofit the rest of the service.
6. **One exception catalog**, and SDK/library exceptions are translated into it at the boundary — inside
   the client class that called the SDK. Shape and translation rules: `exception-catalog`.
7. **Settings are built by a factory and passed down as values.** A settings module — `src/myapp/settings.py`
   in the example above — exposes `get_settings()`; the process definition calls it once and hands
   concrete arguments to the clients and work units it constructs. The migration environment is the
   process definition of a migration run and calls the data-access component's factory the same way
   (`flat-project-setup`). Nothing below the process-definition
   role imports settings, and no module below it calls a settings factory, its own component's included.
   A settings object built at import time makes the package unimportable — by a test, by a type checker,
   by a sibling module wanting one constant — anywhere the environment is incomplete.
8. **Every component that has configuration declares its own settings class, in a `settings.py` beside
   it, under its own environment prefix.** The process's configuration and a data-access package's
   connection settings are two components' configuration and two classes, not one class with both sets
   of fields. Each class exposes a factory and stops there — declaring one is not licence to call it
   below the process definition, which rule 7 forbids. **No variable may ever satisfy two components'
   fields.** Sharing a prefix outright is the obvious way to break that; a *nested* prefix is the quiet
   one. `MYAPP_` for the process and `MYAPP_STORAGE_` for its storage package hold only while no field
   on the outer class begins with the inner segment — `storage_dsn` under `MYAPP_` and `dsn` under
   `MYAPP_STORAGE_` are the same variable. Either keep the stems disjoint, or treat each inner segment
   as reserved in the outer class and never declare a field there that begins with it. The failure is
   the same whether the second component is a package inside this distribution or a library shared with
   siblings (`flat-persistence` states that package's half).
9. **Only a package whose declared role is framework wrapper may import the framework** — plus, once a
   durable-execution engine is earned, the one framework-guarded helper module the firewall's allow-list
   names explicitly. For one distribution that is a single named module at the root of its own package,
   and where several share a repository it is promoted to a library they both depend on. The allow-list names
   that module by path, so the exemption stays one entry a reviewer can read. That one rule is what keeps
   the work units callable from a loop, a test or a one-off script, and it is what makes switching a
   service's trigger a wrapper change rather than a rewrite. The role is declared when the package is
   created, never inferred from a directory name.
10. **A tunable with no single right value carries no default.** A timeout is set from the upstream's
    observed latency and from what the caller can wait for; a default is one deployment's tuning frozen
    into a template, and it converts a missing variable into a silent wrong answer instead of a startup
    failure.
11. **An enum lives beside the module that owns it.** A shared vocabulary module holds only what is
    genuinely used across packages, and admission to it runs `coupling`'s test — a blanket category
    package pulls single-owner types away from their owner and stops naming anything.
12. **Which scope logs a failure is `python-style`'s rule, and it applies here unchanged.** In a flat
    service the scope that stops a failure is usually the loop's guard or the framework wrapper's error
    handler; a client translating an SDK error re-raises and so stays silent, with the detail riding in
    the translated exception's `context` (`exception-catalog`).
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
  the one framework-guarded helper module → stop, the work unit has just been welded to the framework;
  move the wrapper into the framework-wrapper package and leave the body where it was.
- A package cannot be placed in one row of the import-contract table → stop, it holds two roles or none;
  split it or delete it before writing code into it.
- A module builds its settings instance at import time → stop, expose `get_settings()` instead; the
  bare instance makes the package unimportable wherever the environment is incomplete.
- A module below the process definition calls a settings factory, its own component's included → stop,
  the process definition calls it and passes the values down; owning a settings class is not permission
  to read it from inside the component.
- Business logic appears inside a process definition → stop, a process definition wires and runs; the
  work belongs in a work-unit package where a test can call it directly.
- A package is being created because the example above shows it, with nothing to put in it → stop, the
  names are roles; a service only has the packages its roles require.
