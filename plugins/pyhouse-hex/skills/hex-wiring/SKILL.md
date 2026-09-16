---
name: hex-wiring
description: Use when adding a binding in `containers.py` or an env-backed settings class — dishka `Provider` classes, binding `Scope`, the `create_container` composition root and its declaration order, and the `pydantic-settings` class with its env prefix, `.env` and `SecretStr`. The class being bound must already exist — `hex-application`, `hex-capability-adapter`; the project substrate and toolchain are `hex-project-setup`, not runtime wiring.
paths: ["**/domain/**", "**/application/**", "**/infrastructure/**", "**/restapi/**"]
---

# Hex — Wiring

Two halves of one job: getting values in from the environment, and handing objects to whoever needs
them. The two meet at one rule: a settings class is instantiated **only** by the composition root.

## When to use vs. neighbours

- Adding or extending env-backed configuration for an integration → the **Settings** half of this skill.
- Binding a new class in the composition root, or choosing its lifetime → the **dishka** half of this skill.
- The class being wired must already exist — a handler, repository, service, adapter → `hex-application`, `hex-persistence`, `hex-store-repository`, `hex-domain-service`, `hex-capability-adapter`.
- A frozen domain-shaped view of settings values the domain consults → the tunable variant in `hex-domain-model`; its provider reads the single field off a settings class and passes it.
- Attaching the composition root to the HTTP app and closing it at shutdown, which runs every declared teardown → `hex-restapi-app`.
- Resolving a bound object inside a route → `hex-restapi-endpoint`.
- The token-verifier port, its adapter and the route dependencies that consume the resolved caller → `hex-restapi-auth`.
- Substituting a binding for a test → `hex-test-integration-setup`.
- Which libraries the project carries, the ruff and mypy configuration, and the Alembic bootstrap → `hex-project-setup`; that is laid once, not per binding.
- What a settings class, its env prefix or a provider method is called → `naming`.
- Whether a class may be bound here at all, and which layer it belongs to → `hex-architecture`; it owns the layer contract this composition root sits outside of.
- The `IUnitOfWork` binding a multi-repository transaction needs, and the compensating-handler shape → `hex-patterns`.

## Settings

### Template — pydantic-settings, relational database

A **relational-engine** example. Its connection-pool fields (`port`, `pool_size`,
`max_overflow`, `pool_pre_ping`, `echo`) and the `dsn` are **relational-only** — they mean nothing for an
API key, a blob store, a vector store or an observability backend. Never copy them into a non-engine
settings class.

```python
from pydantic import SecretStr, computed_field
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["DbSettings"]

class DbSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MYAPP_DB_",
        env_file=".env",
        extra="ignore",
    )

    host: str
    port: int = 5432
    user: str
    password: SecretStr
    name: str

    pool_size: int = 10
    max_overflow: int = 5
    pool_pre_ping: bool = True
    echo: bool = False

    @computed_field
    @property
    def dsn(self) -> str:
        return (
            f"postgresql+asyncpg://{self.user}:{self.password.get_secret_value()}"
            f"@{self.host}:{self.port}/{self.name}"
        )
```

**The pool numbers above are this example's, and pool sizing is a deployment decision.** `pool_size=10`
and `max_overflow=5` are a plausible single-process web app; a worker running one long job wants far
fewer, and a fleet of processes has to multiply its pool by its replica count against the server's
connection ceiling. `port` defaults to the driver's own well-known port; `pool_pre_ping=True` and
`echo=False` are the two that are **not** taste — pre-ping costs one cheap round trip and buys immunity
to connections the server closed underneath the pool, and `echo=True` in production writes every
statement, parameters included, into the log. Set the sizes from the deployment; keep the last two.

### Template — pydantic-settings, generic integration (API key, blob store, vector store, observability)

Most integrations need a credential plus an endpoint or model name and maybe a knob or two — no pool, no
port, no DSN. This is the shape for everything that is not a relational engine:

```python
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["FooApiSettings"]

class FooApiSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MYAPP_FOO_",
        env_file=".env",
        extra="ignore",
    )

    api_key: SecretStr
    base_url: str = "https://api.foo.example"
    timeout_seconds: int = 30   # this example's number — see below
```

**A timeout is a per-integration decision and `30` is only this example's.** It is set from the
integration's own observed latency plus headroom, and bounded above by what the caller can wait for — a
request-path adapter whose timeout exceeds the app's own request timeout can never fire usefully. What
the template does fix is that the timeout is a **settings field**, read once by the composition root and
injected — never a constant hardcoded inside the adapter. Whether it carries a default at all is rule 1
and rule 2's question: default it only if one value is safe for every deployment, and make it required
otherwise.

### Explicit settings values for tests

Settings test construction → `test-principles`.

`DbSettings(host="localhost", user="t", password=SecretStr("t"), name="t")`.

## Template — dishka

`src/myapp/containers.py` is the only file this half touches. Bindings are grouped into provider classes
by layer and by subdomain; `create_container` assembles them. **Every dependency is resolved by type** —
no binding is reached by its attribute name, so renaming a class cannot silently break a call site.

```python
from collections.abc import AsyncIterator

from dishka import AsyncContainer, Provider, Scope, make_async_container, provide
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

# ...imports for the classes being wired...

__all__ = ["create_container"]


class SettingsProvider(Provider):
    """1. Settings — process lifetime; everything else may depend on them."""

    scope = Scope.APP

    @provide
    def db_settings(self) -> DbSettings:
        return DbSettings()

    @provide
    def storage_settings(self) -> StorageSettings:
        return StorageSettings()


class InfrastructureProvider(Provider):
    """2. Long-lived handles, and 3. cross-cutting helpers.

    A factory that opens a resource is a generator: what is yielded is the dependency,
    what follows the yield is its release, run when the composition root is closed.
    The engine + session_factory pair exists ONLY when a relational store backs a
    repository. A client-style store (qdrant / redis / ...) has no engine — it yields
    the client its `create_<store>_client(settings)` factory builds and closes that
    instead. Bind the long-lived handles the app's datastores actually need, not a
    fixed relational pair.
    """

    scope = Scope.APP

    @provide
    async def engine(self, settings: DbSettings) -> AsyncIterator[AsyncEngine]:
        engine = create_engine(settings=settings)
        yield engine
        await engine.dispose()

    @provide
    def session_factory(self, engine: AsyncEngine) -> async_sessionmaker[AsyncSession]:
        return create_session_factory(engine=engine)

    @provide
    def url_canonicalizer(self) -> UrlCanonicalizer:
        return UrlCanonicalizer()


class FoosProvider(Provider):
    """4. One provider class per subdomain: repository, then the services that use it,
    then the handlers that use them. `provides=` is what binds the adapter to the port;
    every constructor argument is resolved from its annotation, so nothing is passed here.
    """

    scope = Scope.REQUEST

    foo_repository = provide(FooRepository, provides=IFooRepository)
    foo_uniqueness_service = provide(FooUniquenessService)

    create_foo_handler = provide(CreateFooHandler)
    list_foos_handler = provide(ListFoosHandler)

    # 5. A tunable value object is process-lifetime and takes single settings fields.
    @provide(scope=Scope.APP)
    def foo_export_tunable(self, settings: ExportSettings) -> FooExportTunable:
        return FooExportTunable(max_rows=settings.max_rows)


def create_container(*overrides: Provider) -> AsyncContainer:
    """The composition root. `overrides` is the test seam and nothing else appends to it
    (`hex-test-integration-setup`)."""
    return make_async_container(
        SettingsProvider(),
        InfrastructureProvider(),
        FoosProvider(),
        *overrides,
    )
```

Add `FastapiProvider()` to that list **only** when a factory takes `fastapi.Request` or
`fastapi.WebSocket` as a parameter; the default composition root above takes neither and stays free of
transport imports.

### The unit-of-work factory

A handler that uses a unit of work receives `Callable[[], IUnitOfWork]` and opens a fresh one per
`execute` (`hex-patterns`). **Bind the callable, not the unit of work.** Per-operation lifetime would
hand the handler one shared instance for the whole request, which is a different contract.

```python
from collections.abc import Callable
from functools import partial


class FoosProvider(Provider):
    @provide(scope=Scope.APP)
    def uow_factory(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> Callable[[], IUnitOfWork]:
        return partial(SqlAlchemyUnitOfWork, session_factory=session_factory)
```

The closure is stateless, so it is process-lifetime. The unit of work it builds is owned by the
handler's `async with`, which commits or rolls it back — not by the composition root, which never sees
it. There is for the same reason **no per-request session binding**: a session's lifetime belongs either
to the repository call that opened it or to the unit of work, never to the composition root
(`hex-persistence`).

## Other bindings

Both libraries below are actively maintained; this is a fit decision, not a liveness one. The honest
counterweights to the primary binding: `dependency-injector` is far more widely known, and `dishka`
requires Python 3.10 or newer — which the union type syntax used throughout this catalogue already does.

- **`dependency-injector`.** The obligations are identical; what changes is the spelling and one extra
  rule. A `containers.DeclarativeContainer` subclass replaces the provider classes, `providers.*`
  replace the factories, and — the rule dishka does not need — **a binding is reached at the call site
  by its attribute name, which must be the snake_case form of the class** — the call site writes
  `<root>.<snake_case_attr>()`. That name-based contract is unenforced: rename the class and the call
  site breaks at runtime. Test substitution also differs: `.override(value)` / `.reset_override()`
  mutate a *built* container, so an already-resolved `Singleton` may have captured the pre-override
  value and needs a `.reset()` at teardown.

  | dishka | dependency-injector |
  |---|---|
  | `Provider` + `@provide` | `DeclarativeContainer` + `providers.*` |
  | `Scope.APP` | `providers.Singleton` |
  | `Scope.REQUEST` | `providers.Factory` |
  | `provides=IFooRepository` | `providers.Provider[IFooRepository]` annotation |
  | constructor arguments resolved by annotation | each argument passed explicitly |
  | generator factory + `container.close()` | `providers.Resource`, or teardown in the entrypoint |
  | `FromDishka[T]` at the call site | `container.<snake_case_attr>()` |
  | an extra provider with `override=True`, before the container is built | `.override()` / `.reset_override()` on a built container |

- **Manual composition — a plain factory module.** A service small enough not to want a framework
  writes `create_container()` as a function that constructs each object and returns a frozen dataclass
  of them. Every rule below still holds; declaration order becomes literal statement order, teardown
  becomes an `AsyncExitStack` the entrypoint closes, and per-operation lifetime becomes a stored factory
  callable rather than a stored instance.

## Rules

- A **settings class** is the only place this codebase reads environment variables. Adapters always
  receive a settings object; nothing calls `os.getenv`.
- **`containers.py` is the composition root.** Every concrete class is bound to the protocol it
  satisfies here and **only** here. Domain and application code never instantiates a concrete type.
- **Every binding declares a lifetime, and the choice is deliberate.** Nothing is bound without an
  answer to "how long does this live".
- **Anything holding a resource that must be released declares its teardown in the same place as its
  construction**, so construction and release cannot drift apart. The entrypoint closes the composition
  root exactly once, which runs every declared teardown (`hex-restapi-app`).
- **Bindings are reached by type, not by name.** A call site names the type it needs; the composition
  root decides what satisfies it. Nothing outside this file may depend on how a binding is spelled.

### File location and naming

- Path: `src/myapp/infrastructure/<subpackage>/settings.py`. File and class naming → `naming`; location mapping → `hex-conventions`.
- Env prefix naming → `naming`. Never reuse a prefix across two classes.

**A prefix is one stem naming the deployable, plus the integration it configures — `<APP>_<INTEGRATION>_`.**
The stem is whatever the project calls the process it deploys; `MYAPP_` is this catalogue's placeholder
for it, and a real project substitutes its own. What is not negotiable is what the stem may **not** be: a
bounded-context name. Env vars are a deployment concern and a deployable serves every context in it, so a
context-named prefix becomes incoherent the moment a second context shares the datastore — shared settings
collapse to one object (`hex-conventions` block C), and operators would be setting a variable named for
one context to configure a database both use. Working inside a single context, that context is the
salient name; resist it and stem on the deployable.

### Rules — settings

**All three `model_config` keys are mandatory:** `env_prefix` set to the deployable's stem plus this
integration's name, `MYAPP_DB_` in the template above; `env_file=".env"`, so
local dev reads the file while production injects real environment and the file simply is not there; and
`extra="ignore"`, without which a stray env var in the namespace crashes startup.

1. **A required field has no default.** A missing value fails loudly the first time the composition root
   builds the settings object, before any request is served.
2. **An optional field has an inline default**, and the default must be safe for a production-like setup.
3. Field typing → `python-style`.
4. **Engine-pool fields are relational-only, and their sizes are the deployment's.** `port`,
   `pool_size`, `max_overflow`, `pool_pre_ping`, `echo` and a `dsn` computed field belong to the
   relational template, with the numbers set from the deployment rather than copied. A non-engine
   integration omits them entirely; carrying them is dead config copied from a database class.
5. **`SecretStr` for any value that must not appear in a log, a repr or a traceback** — passwords, API
   keys, signing secrets, JWT keys.
6. **Never default a secret.** A missing secret env var must crash the process at startup.
7. **`.get_secret_value()` is called only at the point of use** — inside a `@computed_field` like `dsn`,
   or when constructing an SDK client. Follow `python-style` for logging and output.
8. **Derived values live in `@computed_field @property`** — DSNs, composite URLs, normalized strings.
    Adapters consume the computed value, not the parts.
9. **Two integrations do not share fields by importing one settings class from another.** Each is
    self-contained; copy the field if both genuinely need it.
10. **`@field_validator` for two purposes only:** normalization, accepting an env-friendly form and
    storing the canonical one (unescaping `\\n` in a multi-line key); and rejection, refusing a value
    that would cause silent misbehaviour (an allowlist of JWT algorithms). Validation messages should be
    clear — they surface at startup, where stack traces get read.
11. **One settings class per infrastructure subpackage.** Bundling unrelated config under one prefix is
    forbidden.
12. **Settings live next to the adapter they configure.** There is no top-level central settings module.
13. **Settings are instantiated only in `containers.py`.** Never call `DbSettings()` from a handler, an
    entrypoint, a test fixture or another settings class.
14. **Adapters depend on the settings type**, never on `os.environ` or `os.getenv`. No `os.getenv`
    anywhere outside a settings class.
15. Settings test construction → `test-principles`.

### Lifetimes

| Lifetime | Use for | Examples |
|---|---|---|
| **Process** | Stateless or expensive-to-construct objects whose lifetime spans the process. | Settings (`*Settings`), the engine, the session factory, a token verifier, a URL canonicalizer, **tunable value objects**, a stateless factory callable. |
| **Per operation** | Instances meant to be fresh for each request or each job, cheap to construct. | Every `*Handler`, every `*Repository`, **domain services** that compose them, a stateful adapter bound to per-request state. |

**Default to per-operation for application and domain artifacts. Reserve process lifetime for objects
that own a connection pool, parse env once, or are pure-data configuration.**

The pitfall: giving a repository process lifetime looks fine because it is stateless, but it freezes the
session factory it was built with for the life of the process, which defeats substituting one for a test
and forecloses any future per-request session. **Repositories are per-operation.**

### Declaration order

Group bindings in dependency order and keep them in that order:

1. **Settings first** — everything else may depend on them.
2. **Long-lived infrastructure** — engine, session factory, verifiers.
3. **Cross-cutting helpers** — canonicalizers, storage adapters needed by several subdomains.
4. **Per-subdomain block:** repository → services that use it → handlers that use them.
5. **Cross-subdomain dependencies come first.** If subdomain A's repository is consumed by subdomain B's
   handlers, declare it before B's block.

Where the mechanism evaluates the composition root top to bottom, this ordering is **load-bearing** — a
binding may only reference an earlier one. Where the mechanism resolves by type it is the reading order
instead, and a binding that would have to forward-reference is the signal that it is grouped wrong. When
adding a binding, find the right section and insert it after the latest declaration it depends on.

### Naming and access

- Factory and attribute naming → `naming`. These names are internal to the composition root: nothing
  outside it may reach a binding by name.

### Settings lifecycle in the composition root

- Each `*Settings` is process-lifetime, built by a factory that constructs it with no arguments;
  Pydantic reads env in `__init__`.
- A consumer that needs the whole settings object declares it as a constructor parameter and receives it
  by type.
- A **tunable value object** that needs a single field gets a factory of its own, which reads the field
  off the settings object and passes it. Never pass raw settings fields around otherwise.

### What never goes in the composition root

- **No business logic.** It only wires.
- **No conditionals on env.** Different environments produce different settings *values*; the wiring
  stays the same. Hide a feature flag behind a settings field inside the implementation, never behind a
  branch in the wiring.
- **No imports from `restapi/` or another entrypoint.** The composition root sits below the entrypoint
  layer.
- **No mutable module-level state.** `create_container` returns a new composition root per call; a
  module-level singleton makes the test seam unreachable.
- **No instantiation of concrete domain types** — entities, value objects. It builds services, not data.

## Inlined typing / import rules

- `from pydantic import SecretStr, computed_field` — add `field_validator` to that line **only when the
  class defines one** (settings rule 10); an unused import is an F401.
- `from pydantic_settings import BaseSettings, SettingsConfigDict`.
- Full annotations on every field and validator (`python-style`). **Booleans are Python types**, not
  strings — Pydantic parses `"true"`, `"1"`, `"yes"` correctly. **Numerics are real types**:
  `port: int`, never `str`. **Optional is `T | None = None`**, never `T = ""`.

- **A factory's return annotation is the binding's type**, and it is the whole contract: `-> DbSettings`
  binds `DbSettings`, `-> AsyncIterator[AsyncEngine]` binds `AsyncEngine` with a teardown. Use
  `provides=<Protocol>` when the class-attribute form binds an adapter to its port. An unannotated or
  loosely annotated factory binds the wrong type or fails at container construction, not at the call
  site.

- **Import each class from the package that DIRECTLY re-exports it — one `from .module import *` hop —
  never a grandparent** (`python-packaging`). This bites the nested infra layout: a repository class lives in
  `infrastructure/<store>/repositories/<x>.py`, so import it from the **`repositories` subpackage** —
  `from myapp.infrastructure.postgres.repositories import FooRepository` — **not** from the `<store>`
  tech package. The tech-package form resolves at runtime but mypy reports `[attr-defined]`, because the
  intermediate `repositories/__init__.py` has a computed `__all__` mypy cannot evaluate across the
  `from .repositories import *` hop. A class sitting directly under the tech package — the `engine` or
  `settings` module, a capability adapter — is one hop away, so importing it from the tech package is
  correct.

- Both: no `from __future__ import annotations` (`python-style`).

## Package wiring

Settings re-exports → `python-packaging`; composition-root location → `hex-architecture`.

`containers.py` needs no package wiring at all: it is a top-level module at the project root, not a
package member. For the classes it imports, follow `python-packaging`.

## Hard stops

- Spec asks for an env read outside a settings class → stop, route it through a settings field.
- Spec wants two unrelated integrations under one prefix → stop, split into two classes.
- Spec asks an adapter to take individual fields instead of the settings object → stop, pass the
  whole object. A single field is extracted only by the factory of a tunable value object.
- Spec asks to add a binding whose dependency is not yet declared → stop, that dependency's own skill
  runs first.
- Spec asks to bind a repository at process lifetime → stop, repositories are per-operation.
- Spec asks for conditional wiring per environment → stop, that is a settings-value problem, not a wiring
  problem.
- Spec asks to import a `restapi/` symbol into `containers.py` → stop, wrong dependency direction.
- Spec asks the composition root to hand out a unit of work → stop, it hands out the factory callable;
  the unit of work's lifetime is the handler's `async with` (`hex-patterns`).
- Spec asks for a per-request session binding so a repository can be session-injected outside a unit of
  work → stop, nothing would own the commit; use the standalone repository form (`hex-persistence`) or a
  unit of work (`hex-patterns`).
