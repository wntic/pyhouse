---
name: hex-wiring
description: Use when adding a binding in `containers.py` or an env-backed settings class — provider classes, binding lifetimes, the `create_container` composition root and its declaration order, and the settings class owning one integration's env namespace, its secret fields and its derived values. Bound here to dishka and pydantic-settings, with other DI and settings libraries mapped under `## Other bindings`. The class being bound must already exist — `hex-application`, `hex-capability-adapter`; the project substrate and toolchain are `hex-project-setup`, not runtime wiring.
paths: ["**/domain/**", "**/application/**", "**/infrastructure/**", "**/restapi/**"]
---

# Hex — Wiring

Two halves of one job: getting values in from the environment, and handing objects to whoever needs
them. The two meet at one rule: a settings class is instantiated **only** at a composition root
(settings rule 13).

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
from pydantic import SecretStr
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

    @property
    def dsn(self) -> str:
        return (
            f"postgresql+asyncpg://{self.user}:{self.password.get_secret_value()}"
            f"@{self.host}:{self.port}/{self.name}"
        )
```

**Pool sizing is a deployment decision.** `pool_size=10` and `max_overflow=5` suit a single-process
web app; a worker running one long job wants far
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
    timeout_seconds: int = 30
```

**A timeout is a per-integration decision.** It is set from the
integration's own observed latency plus headroom, and bounded above by what the caller can wait for — a
request-path adapter whose timeout exceeds the app's own request timeout can never fire usefully. What
the template does fix is that the timeout is a **settings field**, read once by the composition root and
injected — never a constant hardcoded inside the adapter. Whether it carries a default at all is rule 1
and rule 2's question: default it only if one value is safe for every deployment, and make it required
otherwise.

### Template — pydantic-settings, S3-compatible blob store

The settings class the S3 adapter (`hex-capability-adapter`) consumes, in `infrastructure/s3/settings.py`
(`hex-conventions` derives the path and the name). The endpoint is required, so the same class reaches
a hosted store and an S3-compatible one; the adapter reads `bucket` and `endpoint_url`, and the
composition root builds the SDK session from the two credential fields.

```python
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["S3Settings"]

class S3Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MYAPP_S3_",
        env_file=".env",
        extra="ignore",
    )

    endpoint_url: str
    access_key: str
    secret_key: SecretStr
    bucket: str
```

### Template — pydantic-settings, the other classes the adapter templates read

One class per consuming technology, each in that technology's `settings.py`, with the fields the
adapter or the composition root reads and nothing else. Each sets the settings-file key in its
`model_config` exactly as `DbSettings` does, beside the prefix shown.

```python
# src/myapp/infrastructure/idna/settings.py
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["IdnaSettings"]

class IdnaSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MYAPP_IDNA_", extra="ignore")

    allowed_schemes: frozenset[str]
```

```python
# src/myapp/infrastructure/bar/settings.py
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["BarGatewaySettings"]

class BarGatewaySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MYAPP_BAR_", extra="ignore")

    base_url: str
    api_key: SecretStr
    timeout_seconds: float
```

```python
# src/myapp/infrastructure/qdrant/settings.py
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["QdrantSettings"]

class QdrantSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MYAPP_QDRANT_", extra="ignore")

    url: str
    foos_collection: str
    api_key: SecretStr | None = None
```

```python
# src/myapp/infrastructure/redis/settings.py
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["RedisSettings"]

class RedisSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MYAPP_REDIS_", extra="ignore")

    url: SecretStr
    foos_key_prefix: str
```

```python
# src/myapp/infrastructure/export/settings.py
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["ExportSettings"]

class ExportSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MYAPP_EXPORT_", extra="ignore")

    max_rows: int
```

`IdnaSettings.allowed_schemes` is read from a JSON list (`MYAPP_IDNA_ALLOWED_SCHEMES='["http","https"]'`).
The Redis URL is a secret because it carries the password. The Qdrant key is the one optional secret: a
store that runs unauthenticated has none, and `None` there is a declared mode rather than a missing
credential (settings rule 6). `ExportSettings` has no adapter behind it — its one consumer is the factory
of `FooExportTunable` (`hex-domain-model`) — so its package is named for itself (`hex-conventions`).

### How this binding spells the settings obligations

Three `model_config` keys are mandatory **under pydantic-settings**, and each is one obligation from
`### Rules — settings`: `env_prefix` declares the class's env namespace; `env_file` points at the
project's dotenv file, so local development reads it while production injects real environment and the
file simply is not there; and `extra="ignore"` keeps the namespace non-strict, without which a
neighbouring variable in it crashes startup. `SecretStr` is this binding's non-printing secret type and
`.get_secret_value()` its unwrap; a plain `@property` is where a derived value is computed on
the object; `@field_validator` is where normalization and rejection are written.

### Explicit settings values for tests

Settings test construction → `test-principles`. The test infrastructure provider and its fixtures are
one of the three composition roots rule 13 names, so they construct settings with explicit values:

`DbSettings(host="localhost", user="t", password=SecretStr("t"), name="t")`.

## Template — dishka

`src/myapp/containers.py` is the only file this half touches. Bindings are grouped into provider classes
by layer and by subdomain; `create_container` assembles them. **Every dependency is resolved by type** —
no binding is reached by its attribute name, so renaming a class cannot silently break a call site. The
template binds every adapter the catalogue's templates define for one app; an app binds the ones it has.

```python
from collections.abc import AsyncIterator

import aioboto3
import httpx
from dishka import AnyOf, AsyncContainer, Provider, Scope, make_async_container, provide
from qdrant_client import AsyncQdrantClient
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from myapp.application.foos import (
    CreateFooHandler,
    DeleteFooHandler,
    GetFooHandler,
    ListFoosHandler,
    UpdateFooHandler,
)
from myapp.domain.bars import ICanCanonicalizeBarUrl, ICanFetchBarToken
from myapp.domain.foos import (
    FooExportTunable,
    FooUniquenessService,
    ICanFetchFoos,
    ICanStoreFoos,
    IFooRepository,
    IFooSearchIndex,
)
from myapp.infrastructure.bar import BarGatewaySettings, HttpBarGateway
from myapp.infrastructure.export import ExportSettings
from myapp.infrastructure.idna import IdnaBarUrlCanonicalizer, IdnaSettings
from myapp.infrastructure.postgres import DbSettings, create_engine, create_session_factory
from myapp.infrastructure.postgres.repositories import FooRepository
from myapp.infrastructure.qdrant import QdrantSettings, create_vectors_client
from myapp.infrastructure.qdrant.repositories import FooRepository as QdrantFooRepository
from myapp.infrastructure.s3 import S3FooStorage, S3Settings

__all__ = ["create_container"]


class SettingsProvider(Provider):
    """1. Settings — process lifetime; everything else may depend on them."""

    scope = Scope.APP

    @provide
    def db_settings(self) -> DbSettings:
        return DbSettings()

    @provide
    def s3_settings(self) -> S3Settings:
        return S3Settings()

    @provide
    def qdrant_settings(self) -> QdrantSettings:
        return QdrantSettings()

    @provide
    def bar_gateway_settings(self) -> BarGatewaySettings:
        return BarGatewaySettings()

    @provide
    def idna_settings(self) -> IdnaSettings:
        return IdnaSettings()

    @provide
    def export_settings(self) -> ExportSettings:
        return ExportSettings()


class InfrastructureProvider(Provider):
    """2. Long-lived handles, each released after its yield, and 3. cross-cutting adapters."""

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
    def s3_session(self, settings: S3Settings) -> aioboto3.Session:
        # A session holds credentials, not connections; the adapter opens a client per call.
        return aioboto3.Session(
            aws_access_key_id=settings.access_key,
            aws_secret_access_key=settings.secret_key.get_secret_value(),
        )

    @provide
    async def vectors_client(self, settings: QdrantSettings) -> AsyncIterator[AsyncQdrantClient]:
        client = create_vectors_client(settings)
        yield client
        await client.close()

    @provide
    async def http_client(self, settings: BarGatewaySettings) -> AsyncIterator[httpx.AsyncClient]:
        async with httpx.AsyncClient(timeout=settings.timeout_seconds) as client:
            yield client

    foo_storage = provide(S3FooStorage, provides=AnyOf[ICanStoreFoos, ICanFetchFoos])
    bar_gateway = provide(HttpBarGateway, provides=ICanFetchBarToken)
    bar_url_canonicalizer = provide(IdnaBarUrlCanonicalizer, provides=ICanCanonicalizeBarUrl)


class FoosProvider(Provider):
    """4. One provider class per subdomain: repository, then the services that use it,
    then the handlers that use them. `provides=` is what binds the adapter to the port;
    every constructor argument is resolved from its annotation, so nothing is passed here.
    """

    scope = Scope.REQUEST

    foo_repository = provide(FooRepository, provides=IFooRepository)
    foo_search_index = provide(QdrantFooRepository, provides=IFooSearchIndex)
    foo_uniqueness_service = provide(FooUniquenessService)

    create_foo_handler = provide(CreateFooHandler)
    get_foo_handler = provide(GetFooHandler)
    list_foos_handler = provide(ListFoosHandler)
    update_foo_handler = provide(UpdateFooHandler)
    delete_foo_handler = provide(DeleteFooHandler)

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

Two repositories back `Foo` from two stores, and both classes are `FooRepository` in their own packages
(`hex-conventions`), so the second is imported under an alias naming its store; the alias lives in this
file only. One adapter satisfying two ports is bound once, to both (`AnyOf`), so the two ports share the
one instance. A client-style store the templates do not bind here — the Redis archive
(`hex-store-repository`) — joins the same way: a settings factory, a client factory that closes the
client after its yield, and the repository bound to its port.

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

from myapp.domain.uow import IUnitOfWork
from myapp.infrastructure.postgres import SqlAlchemyUnitOfWork


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

### Settings

`### Rules — settings` is what a settings library has to satisfy, and none of those rules names one.
What changes between libraries is only where each obligation is written.

- **`environ-config`, `dynaconf`, or attrs plus `os.environ`.** The env namespace becomes that library's
  own prefix argument, a secret field becomes its secret wrapper — or a `str` behind a `__repr__` that
  refuses to print it — a derived value becomes an ordinary read-only property on the settings class, and
  a validator becomes that library's converter or validator hook. Unchanged: one class per integration,
  one prefix per class, a required field with no default, no default on a secret, construction only at
  a composition root, and no environment read anywhere else.
- **A hand-rolled settings module.** A frozen dataclass with a `from_env()` classmethod that reads each
  variable, raises on a missing required one, wraps each secret, and exposes derived values as
  properties. The obligations are identical; what the library was doing for free — the missing-value
  error, the type coercion, the non-strict namespace — becomes a few lines written once. A secret still
  gets a wrapper type rather than a bare `str`, because "keeps itself out of reprs and logs" is the
  obligation, not the library's class.

### Dependency injection

Both libraries below are actively maintained; this is a fit decision, not a liveness one. The honest
counterweight to the primary binding is that `dependency-injector` is far more widely known; `dishka`'s
own interpreter requirement sits below the house floor `python-style` sets, so it never raises it.

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

**A settings class owns one env namespace, and that namespace is non-strict.** Every field it reads is
prefixed with the deployable's stem plus this integration's name — `MYAPP_DB_` in the template above —
and a variable inside the namespace that the class does not declare must **not** fail startup: the
process environment is shared with the deployment's own variables and with every other settings class,
so strictness there turns an unrelated variable into an outage. Where the project also keeps a local
dotenv file for development, the class reads it when it is present and the real environment when it is
not, so one class serves both without a branch.

1. **A required field has no default.** A missing value fails loudly the first time the composition root
   builds the settings object, before any request is served.
2. **An optional field has an inline default**, and the default must be safe for a production-like setup.
3. Field typing → `python-style`.
4. **Engine-pool fields are relational-only, and their sizes are the deployment's.** `port`,
   `pool_size`, `max_overflow`, `pool_pre_ping`, `echo` and a computed connection string belong to the
   relational template, with the numbers set from the deployment rather than copied. A non-engine
   integration omits them entirely; carrying them is dead config copied from a database class.
5. **A value that must not appear in a log, a repr or a traceback carries a type that keeps it out of
   them** — passwords, API keys, signing secrets, JWT keys. A bare `str` is printed by every default
   repr in the program, so the type is what makes disclosure impossible rather than merely discouraged.
6. **Never default a secret the integration requires.** A missing secret env var must crash the process
   at startup. A credential that is genuinely optional — a store that may run unauthenticated — is
   `None` when absent, never a placeholder value.
7. **A secret is unwrapped only at the point of use** — inside the derived value that assembles a
   connection string, when constructing an SDK client, or in the constructor of the adapter that sends
   it, which holds it privately for its lifetime (`hex-capability-adapter`). Never into a log field, an
   exception's context, or an intermediate string built for anything else. Follow `python-style` for
   logging and output.
8. **A value assembled from other fields is computed on the settings object, never reassembled by its
    consumers** — connection strings, composite URLs, normalized strings. Every consumer reads the
    computed value, so one place decides how the parts go together and a change to that recipe is one
    edit rather than a search.
9. **Two integrations do not share fields by importing one settings class from another.** Each is
    self-contained; copy the field if both genuinely need it.
10. **Field validation exists for two purposes only:** normalization, accepting an env-friendly form and
    storing the canonical one (unescaping `\\n` in a multi-line key); and rejection, refusing a value
    that would cause silent misbehaviour (an allowlist of JWT algorithms). Validation messages should be
    clear — they surface at startup, where stack traces get read.
11. **One settings class per infrastructure subpackage.** Bundling unrelated config under one prefix is
    forbidden.
12. **Settings live next to the adapter they configure.** There is no top-level central settings module.
13. **Settings are constructed only at a composition root, and there are exactly three:** the DI
    container module (`containers.py`), the migration environment (`migrations/env.py`), and the test
    infrastructure provider and its fixtures. Nowhere else — never `DbSettings()` in a handler, an
    adapter, an entrypoint module or another settings class.
14. **Adapters depend on the settings type**, never on `os.environ` or `os.getenv`. No `os.getenv`
    anywhere outside a settings class.
15. Settings test construction → `test-principles`.

### Lifetimes

| Lifetime | Use for | Examples |
|---|---|---|
| **Process** | Stateless or expensive-to-construct objects whose lifetime spans the process. | Settings (`*Settings`), the engine, the session factory, a token verifier, a library-backed canonicalizer adapter, **tunable value objects**, a stateless factory callable. |
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

- Each `*Settings` is process-lifetime, built by a factory that constructs it with no arguments — the
  environment is read during construction, so the factory passes nothing and a missing required variable
  fails there.
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

- **Under the pydantic-settings binding:** `from pydantic import SecretStr`, adding
  `field_validator` to that line **only when the class defines one** (settings rule 10) — an unused
  import is an F401 — plus `from pydantic_settings import BaseSettings, SettingsConfigDict`. Another
  settings library imports its own names; what carries over is that each is imported only where used.
- Full annotations on every field and validator (`python-style`). **Booleans are Python types**, not
  strings — a settings library coerces `"true"`, `"1"`, `"yes"` for you. **Numerics are real types**:
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

`containers.py` needs no package wiring at all: it is `src/myapp/containers.py`, a module of the
distribution's root package, and the root `__init__.py` does not re-export it — that file stays empty
(`python-packaging`'s carve-out for an application's root). For the classes it imports, follow
`python-packaging`.

## Hard stops

- Asked for an env read outside a settings class → stop, route it through a settings field.
- Two unrelated integrations share one prefix → stop, split into two classes.
- An adapter is asked to take individual fields instead of the settings object → stop, pass the
  whole object. A single field is extracted only by the factory of a tunable value object.
- Asked to add a binding whose dependency is not yet declared → stop, that dependency's own skill
  runs first.
- Asked to bind a repository at process lifetime → stop, repositories are per-operation.
- Asked for conditional wiring per environment → stop, that is a settings-value problem, not a wiring
  problem.
- Asked to import a `restapi/` symbol into `containers.py` → stop, wrong dependency direction.
- The composition root is asked to hand out a unit of work → stop, it hands out the factory callable;
  the unit of work's lifetime is the handler's `async with` (`hex-patterns`).
- The composition root is asked to bind a store connection or transaction handle per operation, so a
  repository can be injected with one outside a unit of work → stop, nothing would then own the commit;
  use the standalone repository form, which opens and owns its own (`hex-persistence` for a relational
  store, `hex-store-repository` for a client-style one), or a unit of work (`hex-patterns`). A store
  whose client is the connection and has nothing to commit is bound at process lifetime, not per
  operation.
