---
name: hex-conventions
description: Use when asking where does this file go or what is this class called — the registry deriving a path and class name from a bare identifier, plus the two store profiles with their connection factories and `<subdomain>:<Name>` cross-context resolution. Produces no file of its own. What a thing is *called* in general is `naming`; layer boundaries are `hex-architecture`.
paths: ["**/domain/**", "**/application/**", "**/infrastructure/**", "**/restapi/**"]
---

# Hexagonal Conventions — the derivation registry

This is the **derivation layer**: the rules that turn the bare identifiers a change introduces — an
entity name, a protocol name, a command base-name, a datastore kind — into concrete file paths, class
names and package placement. Other skills own what goes *inside* an artifact; this one owns the mapping
between a name and its place in the tree. It produces **no file of its own**.

All paths below are relative to the target package root `src/myapp/`. Worked names use a deliberately
neutral vocabulary — subdomains `foos` and `bars`, entities `Foo` and `Bar` — so nothing here reads as
belonging to one product. Technology tokens (`postgres`, `redis`, `s3`, `jwt`) stay concrete, because the
whole point of the infrastructure rule is that the folder is named after the real technology.

## When to use vs. neighbours

- Turning a bare identifier into a file path or class name → this skill.
- Deciding which repository form a datastore gets, or writing its connection factory → block B.
- Resolving a `<subdomain>:<Name>` reference, or deciding what is shared across contexts → block C.
- Layer boundaries, `__all__`, the re-export contract, import forms → `hex-architecture`.
- What goes *inside* the artifact whose name you just derived → the skill that owns it
  (`hex-persistence`, `exception-catalog`, `hex-patterns`). This skill is consulted **alongside**
  them, never instead of them — it produces no file of its own.
- Which libraries the project carries and how the toolchain is configured → `hex-project-setup`.
- Choosing what an identifier should be *called* once you know where it goes — the derivation procedure and the naming tests → `naming`. This skill maps a name to a place; `naming` picks the name.
- One class per module, `__all__`, and the `__init__.py` re-exports → `python-packaging`.
- The composition root and the settings classes a store profile's connection factory is wired from → `hex-wiring`.
- Whether the service should be hexagonal at all → `architecture-choice`.
- The command, query or handler that lives at the path you just derived → `hex-application`.

## A. Path & name derivation

**`snake_case`** — PascalCase → snake by inserting `_` before each interior capital, then lowercasing:
`IFooRepository` → `i_foo_repository`, `S3ObjectStorage` → `s3_object_storage`. Acronym runs are **not**
special-cased; revisit if an identifier ever needs `o_t_p` avoided.

**`pluralize`** (table names) — `y` after a consonant → `ies`; trailing `s`/`x`/`z`/`ch`/`sh` → `+es`;
else `+s`. So `Category` → `categories`, `Box` → `boxes`, `Foo` → `foos`. Table name =
`pluralize(snake(aggregate))`. Singular and plural table names are both long-standing house styles with
no winner; what matters here is that the name is **derived** rather than chosen, so the catalogue picks
one. A project that prefers singular changes this one derivation rule, not every table.

**Class names** carry only the identifier plus a derived suffix. Protocol identifiers already include
their `I`-prefix / `Repository` suffix.

Everything below is mechanical **given a good identifier**, and this skill cannot supply one: it turns
`Foo` into a path, it does not judge whether `Foo` was the right word. Choose the identifier by
`naming`'s rules first — a generic one (`Manager`, `Data`, `Worker`) propagates through
every derived path and class name here, multiplying one careless choice across the tree.

| Artifact | Given | Derived class name(s) | Derived file path(s) |
|---|---|---|---|
| domain enum | `FooKind` in subdomain `foos` | `FooKind` | `domain/foos/foo_kind.py` |
| domain value object | `FooCode` in `foos` | `FooCode` | `domain/foos/foo_code.py` |
| domain entity | `Foo` in `foos` | `Foo` | `domain/foos/foo.py` |
| domain service | `FooVerifier` in `foos` | `FooVerifier` | `domain/foos/foo_verifier.py` |
| domain filter | `FooListFilter` in `foos` | `FooListFilter` | `domain/foos/foo_list_filter.py` |
| filter sort enum | `FooSort` in `foos` | `FooSort` | `domain/foos/foo_sort.py` — its own module, not folded into the filter's (one class per module); the filter imports it |
| repository protocol | `IFooRepository` in `foos` | `IFooRepository` | `domain/foos/i_foo_repository.py` |
| capability protocol | `ICanSendNotification` in `foos` | `ICanSendNotification` | `domain/foos/i_can_send_notification.py` |
| domain exception | `NotFoundError` | `NotFoundError` | appended to `domain/exceptions.py` (single catalog) |
| application command | `CreateBar` (subdomain derived, see below) | `CreateBarCommand` + `CreateBarHandler` | `application/bars/create_bar_command.py` + `application/bars/create_bar_handler.py` |
| application query | `ListBars` | `ListBarsQuery` + `ListBarsHandler` + `ListBarsResult` | `application/bars/list_bars_query.py` + `_handler.py` + `_result.py` |
| datastore | named `<name>`, kind `<kind>` (e.g. `vectors` on a vector store) | — (a configured resource, no class) | `infrastructure/<kind>/connection.py`, holding `create_<name>_client` |
| settings | `S3Settings` | `S3Settings` | `infrastructure/s3/settings.py` — subpackage = the consuming tech; the module is always `settings.py`, one settings class per subpackage |
| repository adapter | implements `IFooRepository`, backs `Foo`, on store `main` | `FooRepository` | `infrastructure/<store-kind>/repositories/<repo-stem>.py` (+ a write-once `Table` at `infrastructure/<store-kind>/tables/foos.py` for a relational store) |
| capability adapter | implements `ICanManageTokens`, adapter `jwt`, role `TokenManager` | `JwtTokenManager` | `infrastructure/jwt/jwt_token_manager.py` |
| wire schema | `LoginRequest` for resource `foos` | `LoginRequest` | grouped into `restapi/schemas/foos.py` |
| endpoint | method + path, resource `foos` | endpoint function (name from method + path) | grouped into `restapi/routers/foos.py` |
| middleware | `RequestId` | `RequestIdMiddleware` | `restapi/middleware/request_id.py` |

**An application handler's subdomain is derived, not chosen.** It is the subdomain of the first
repository protocol the handler depends on (a repository protocol carries its own subdomain); with no
repository dependency, fall back to the subdomain of the first domain entity it touches. So `CreateBar`
depending on `IBarRepository` (subdomain `bars`) lands in `application/bars/`.

**A value object used as a dependency is a tunable VO, and its wiring follows.** A value object is
normally built inline at its use site. When it is instead *injected* into a handler or a domain service,
it is the **tunable variant** — the config-knob view of an environment threshold: wired as a singleton
constructed field-by-field from a settings class, not from an inline literal. The stem pairing
`<Stem>Tunable` ← `<Stem>Settings` is an **advisory default, not load-bearing** — the real binding is the
wiring, which sources the tunable from whichever settings fields match. A stem mismatch is fine:
`FooLimitTunable(max_attempts=foo_settings.provided.max_attempts, …)` from a single `FooSettings` is
correct. Name them to match when a dedicated settings class exists; reuse a broader one (and let the
stems differ) when the knobs naturally live there. The field-by-field construction
`<tunable>(field=<settings>.provided.field, …)` is the invariant. This is how an environment-tunable
domain threshold — rate limits, quotas, retention — reaches a domain service without the domain importing
a settings library.

**Infrastructure groups by external TECH, never by a domain subdomain and never under a catch-all
`db/`.** The tech token is:

- a repository's **store kind** — the kind of the datastore it sits on; with no datastore named, the
  project's single relational store under whatever kind it is named (block B: a project has at most one
  relational kind). Relational repositories, their write-once table, and the shared engine / session
  factory / shared-metadata bootstrap all sit under `infrastructure/<relational-kind>/`
  (`repositories/`, `tables/`).
- a non-relational datastore's **kind** — `infrastructure/<kind>/`, one directory per kind the project
  actually uses, holding `connection.py` (the `create_<name>_client` factory) and its settings. The kind
  is the vendor's own token, kept concrete: a cache, a vector store and a search index each get their
  own directory under their own name.
- a capability adapter's **adapter** token — `infrastructure/jwt/`, `infrastructure/s3/`.
- a settings class's **consuming tech** — the adapter of the capability that uses it, or the kind of the
  datastore that uses it; a settings class with no consumer falls back to its own snake name.

**Capability adapter class** = `<AdapterPascal><Suffix>`, where `Suffix` is the capability's agent-noun
role when there is one (adapter `jwt`, role `TokenManager` → `JwtTokenManager`) and otherwise the
protocol name minus its `ICan` prefix (adapter `jwt`, implements `ICanManageTokens`, no role →
`JwtManageTokens`). The role is named explicitly precisely because the agent-noun is not mechanically
derivable from the verb.

**Repository file stem — aggregate-derived for a relational store, protocol-derived for a client store.**
The class is always `<Aggregate>Repository` (backs `Foo` → `FooRepository`), but its **file stem** depends
on the store profile (block B), because polyglot persistence lets two repositories back ONE aggregate:

- a **relational store** repo → `<snake(aggregate)>_repository.py` (`Foo` on `main` →
  `foo_repository.py`).
- a **client-style store** repo → the **protocol-derived** stem: the implemented protocol name minus its
  leading `I`, snaked (`IFooSearchIndex` on `vectors` → `foo_search_index.py`).

So a `Foo` backed by both a relational `IFooRepository` and a search-store `IFooSearchIndex` lands two
distinct files — `<relational-kind>/repositories/foo_repository.py` and
`<store-kind>/repositories/foo_search_index.py`. An aggregate-only stem would collide.

**Which repository form applies is decided by the store profile, not the vendor.** A relational store →
the SQLAlchemy Core form in `hex-persistence`. **Any** client-style store → a vendor-agnostic
client-repository form covering every vector / cache / document backend. A new client-style backend is a
**profile row in block B plus its package**, never a new form.

**Imports and package mechanics are not restated here.** A referenced type resolves to its owning module:
same-subdomain domain types use a relative `.module` import, cross-subdomain a relative `..subdomain`,
cross-layer an absolute `myapp.domain.<subdomain>` import, stdlib its canonical import, builtins none.
`hex-architecture` owns the rules, `__all__`, and the `from .module import *` re-export contract the
collapsed import form depends on.

## B. Store profiles

A datastore's kind is a free token, not a closed enum — a fixed list is the same disease as a fixed type
map. The profile maps a kind to the few things needed to wire a repository **without** knowing the
backend's SQL/SDK internals:

There are only **two** profiles, and the table has only two rows. Everything else is a vendor filling
one of them in:

| profile | resource param / attr | resource type | resource import | relational |
|---|---|---|---|---|
| **relational** — reached through the shared engine bootstrap | `session_factory` / `sf` | `async_sessionmaker[AsyncSession]` | the engine library's session types | **yes** |
| **client-style** — reached through an injected SDK client | `client` / `client` | the SDK's own async client class | that SDK's client import | no |
| *(kind not yet profiled)* | `client` / `client` | `object` | — | no |

A concrete kind is one row of an **appendix the project fills in**, not a row of the table above. Three
worked out, as the shape to copy:

| kind | profile | resource type | resource import |
|---|---|---|---|
| `postgres` | relational | `async_sessionmaker[AsyncSession]` | `from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker` |
| `<vector-store>` | client-style | the SDK's async client | that SDK's client import |
| `<cache>` | client-style | the SDK's async client | that SDK's client import |

- **Relational** also selects the repository form (block A): yes → `hex-persistence`; no → the
  client-repository form. Adding a client-style backend is one row here.
- **Relational yes** → the repository reuses the shared engine + `session_factory` bootstrap under
  `infrastructure/<relational-kind>/` (a project has at most one relational kind, whatever it is named),
  and gets a write-once `Table` under `infrastructure/<relational-kind>/tables/`. **No** → lay a `create_<store>_client(settings)`
  factory in `infrastructure/<kind>/connection.py` that the composition root binds at process lifetime and
  injects into every repository on that store, and there is **no** table — the store persists through its own client.
- **Say in prose what a repository method promises on this store**, in the one comment the adapter
  carries: on a relational store the method issues a statement and the caller's unit of work decides when
  it commits; on a client store the call *is* the write and there is nothing to commit; on an unprofiled
  store the client is untyped and the method's guarantees are whatever the vendor documents. Write that
  sentence — there is no token to pick.
- An **unknown** kind degrades to a generic untyped `object` client plus a loud contract comment — fail
  loud, do not crash. Adding a backend is **one row here**, never a change to any tool.

**The connection factory is complete glue, not a stub.** For a known profile kind the connection / engine
factory carries zero judgment — it is a fixed function of the settings shape — so write it in **full**,
never as `raise NotImplementedError`. A stub here type-checks and lints clean, then crashes the container
at app construct. The canonical complete forms, the relational one written against SQLAlchemy's asyncio
engine with an asyncpg DSN — the catalogue's binding (`hex-persistence`). Another engine or driver
changes the DSN string and the factory's return type; the shape, the name and the completeness rule are
unchanged:

```python
# infrastructure/postgres/engine.py  (the relational engine + session factory — complete)
def create_engine(settings: DbSettings) -> AsyncEngine:
    dsn = (
        f"postgresql+asyncpg://{settings.user}:{settings.password.get_secret_value()}"
        f"@{settings.host}:{settings.port}/{settings.name}"
    )
    return create_async_engine(dsn)


def create_session_factory(engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(engine, expire_on_commit=False)
```

```python
# infrastructure/<kind>/connection.py  (a client-store connection factory — complete)
# <kind> is the vendor token, AsyncStoreClient the SDK's own async client class.
# Every client-style store has this shape; only the constructor kwargs differ.
def create_vectors_client(settings: StoreSettings) -> AsyncStoreClient:
    return AsyncStoreClient(
        url=settings.url,
        api_key=settings.api_key.get_secret_value() if settings.api_key else None,
    )
```

The factory name is `create_<datastore-name>_client` — the datastore's *name*, not its kind, so
`create_vectors_client` for a datastore named `vectors`. The resource type and import come from the
profile table. Only a genuinely unknown kind (the degraded `object` row) cannot be written complete;
there alone leave a `NotImplementedError` plus a loud comment.

## C. Multi-context apps

A deployable app may hold more than one bounded context in ONE package — contexts as sibling subpackages
keyed by subdomain (`domain/foos/` + `domain/bars/`, `application/foos/` + `application/bars/`, …). A
single-context app is the degenerate case. Two rules govern the rest:

**A cross-context reference is a cross-subdomain reference.** Where a name is written
`<subdomain>:<Name>` — a `bars` service depending on `foos:IFooRepository`, its body referencing
`foos:FooKind` — this is **not special**. Strip the `<subdomain>:` prefix and resolve `<Name>` in the
`<subdomain>` subpackage of the appropriate layer, by the ordinary import rules. So `foos:IFooRepository`
injected into a `bars` service → `from myapp.domain.foos import IFooRepository`. The prefix **is** the
subpackage, and the provider that injects it is wired in the one shared `containers.py`.

**The shared substrate exists once, as the union of the contexts.** Per-context artifacts — everything
under `domain/<subdomain>/` and `application/<subdomain>/`, a context's repositories and adapters under
their tech subpackage, its entrypoint modules and per-resource schemas — are per context. These are
**one each for the whole app**, and writing them per context would clobber the other context's
contributions. **Each entry below exists only where the app has the thing it names** — the rule is the
union, not the list, so an app with no relational store carries no relational bootstrap row and a
worker- or CLI-only app carries no HTTP ones; whatever the app does have, it has once:

- `domain/exceptions.py` — the single catalog is the union of every context's exceptions, deduped by
  name; two contexts both declaring `ValidationError` collapse to one.
- the relational bootstrap under `infrastructure/<relational-kind>/` (engine, session factory, shared
  metadata) and the single relational settings class — one relational substrate; that settings class, or
  a datastore named in several contexts, collapses to one, deduped by name and environment prefix. Only
  where a relational store backs a repository at all.
- **the shell of each entrypoint package the app has** — one per entrypoint kind, registering **every**
  context's contribution to it: `restapi/main.py` includes every context's router, and a worker's or a
  CLI's shell registers every context's consumers or commands the same way.
- **each entrypoint package's cross-cutting modules** — failure rendering, shared dependencies, shared
  error schemas — one each per entrypoint package, never one per context, and used by every context that
  needs them rather than only the one that introduced them. Under the HTTP binding that is
  `restapi/error_handler.py`, `restapi/schemas/errors.py` and `restapi/dependencies.py`.
- `containers.py` — ONE composition root, binding every context's classes.
- `pyproject.toml` — the substrate plus the union of every context's packages (`hex-project-setup`).

Dedup is by identifier: the same name and shape across contexts → one artifact. A genuine **conflict** —
same name, different shape — is never silently merged. Stop and surface it.

## Rules

1. Choose identifiers with `naming`, then check every derived artifact against block A's table.
2. Locate an application handler by its first repository's subdomain; use its first domain entity
   when it has no repository dependency.
3. Check injected tunables against the field-by-field settings construction in block A; matching stems
   are advisory.
4. Select each infrastructure directory by the consuming technology, using block A's tech-token cases.
5. Derive a repository's file stem from the aggregate for relational stores and the protocol for client
   stores; select its implementation form through block B's profile.
6. Extend datastore support through the profile table; retain the documented fallback for unknown kinds.
7. Check known-profile connection factories against the complete glue forms in block B, including the
   datastore-name-derived factory name.
8. Resolve context-qualified references through the named subdomain, using `python-packaging` for
   imports and `hex-architecture` for layer boundaries.
9. Build the shared substrate from block C's union of contexts; deduplicate identical declarations and
   surface incompatible shapes.
10. **Entity ids are `uuid.uuid4()`, generated in the application layer** — one scheme across every
    template, production and test alike. Stdlib only, on the interpreter floor `python-style` sets;
    `uuid.uuid7()` is standard library only from **Python 3.14**. Time-ordered v7 ids index better when
    rows created together are read together, and a project that wants them takes a third-party
    generator and applies it everywhere at once — never in half the templates. (The flat family does
    exactly that for primary keys, for a reason `flat-persistence` states in the `pyhouse-flat`
    plugin; the rule here does not depend on reading it.)

## Hard stops

- A path or class name is being invented that the table in block A does not derive → stop, either the
  artifact matches a row and follows it, or the row is missing and gets added here first.
- `infrastructure/` is being grouped by subdomain, or under a catch-all `db/` → stop, it groups by the
  external technology.
- A handler's subdomain is being chosen rather than derived → stop, it follows the first repository
  protocol it depends on.
- A composite aggregate is getting one repository file stem on two different stores → stop, a
  client-style store's repository takes the protocol-derived stem, or the two files collide.
- A connection or engine factory is being left as `NotImplementedError` for a known profile kind →
  stop, it is complete glue; a stub type-checks and lints clean, then crashes at app construct.
- A store kind is being added by changing a tool or a type map → stop, it is one row in block B.
- Two contexts declare the same name with different shapes → stop, do not silently merge; surface the
  conflict.

## See also

- `hex-architecture` — layer boundaries, relative vs absolute reach, the same-package collapse, one class
  per module, `__all__` placement, and the `from .module import *` re-export contract.
- `hex-project-setup` — which libraries the project carries, the toolchain configuration, and the
  migration bootstrap.
- `hex-persistence` — what goes inside a relational table, repository and revision.
