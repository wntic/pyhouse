# hex-test-integration-setup — the conftest hierarchy

Topic file of `hex-test-integration-setup`. The mechanism-free obligations are `test-principles`' suite
rules and the three under `### The obligations` in `SKILL.md`; what follows is the **pytest +
testcontainers + Alembic + SQLAlchemy savepoints + dishka** binding that satisfies them — the files
themselves first, then the three spellings this binding adds.

## `tests/integration/conftest.py`

```python
import os
import subprocess
import sys
from collections.abc import AsyncIterator, Callable, Iterator
from functools import partial

import pytest
from dishka import AsyncContainer, Provider, Scope, provide
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)

from myapp.infrastructure.postgres import PostgresSettings, create_engine


@pytest.fixture(scope="session")
def postgres_settings() -> Iterator[PostgresSettings]:
    from testcontainers.community.postgres import PostgresContainer

    # An exact, deliberately bumped tag (e.g. `17-alpine`) — never `:latest`.
    with PostgresContainer("postgres:<pinned-tag>") as postgres:
        # Only the fixture that created the database may declare it disposable.
        os.environ["MYAPP_TEST_DISPOSABLE_DB"] = "1"
        yield PostgresSettings(
            host=postgres.get_container_host_ip(),
            port=int(postgres.get_exposed_port(5432)),
            user=postgres.username,
            password=SecretStr(postgres.password),
            name=postgres.dbname,
        )


@pytest.fixture(scope="session", autouse=True)
def _guard_against_real_db(postgres_settings: PostgresSettings) -> None:
    """Refuse to run unless whatever provisioned the database declared it disposable."""
    if os.getenv("MYAPP_TEST_DISPOSABLE_DB") != "1":
        raise RuntimeError(
            f"Integration tests refuse to run against "
            f"{postgres_settings.host}:{postgres_settings.port}/{postgres_settings.name}: "
            "MYAPP_TEST_DISPOSABLE_DB is not set. Set it only where the database "
            "is created for the test run and destroyed with it."
        )


def _run_alembic(postgres_settings: PostgresSettings, *args: str) -> subprocess.CompletedProcess[str]:
    environment = {
        **os.environ,
        "MYAPP_POSTGRES_HOST": postgres_settings.host,
        "MYAPP_POSTGRES_PORT": str(postgres_settings.port),
        "MYAPP_POSTGRES_USER": postgres_settings.user,
        "MYAPP_POSTGRES_PASSWORD": postgres_settings.password.get_secret_value(),
        "MYAPP_POSTGRES_NAME": postgres_settings.name,
    }
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        capture_output=True,
        text=True,
        env=environment,
    )


@pytest.fixture(scope="session", autouse=True)
def _migrated_db(_guard_against_real_db: None, postgres_settings: PostgresSettings) -> PostgresSettings:
    result = _run_alembic(postgres_settings, "upgrade", "head")
    assert result.returncode == 0, result.stderr
    return postgres_settings


@pytest.fixture(scope="session")
def run_alembic(_migrated_db: PostgresSettings) -> Callable[..., subprocess.CompletedProcess[str]]:
    """The migration runner, for tests that move the schema themselves."""
    return partial(_run_alembic, _migrated_db)


@pytest.fixture(scope="session")
async def _engine(_migrated_db: PostgresSettings) -> AsyncIterator[AsyncEngine]:
    engine = create_engine(_migrated_db)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
async def _outer_connection(_engine: AsyncEngine) -> AsyncIterator[AsyncConnection]:
    """One connection and one transaction per test, rolled back at teardown."""
    async with _engine.connect() as connection:
        transaction = await connection.begin()
        try:
            yield connection
        finally:
            await transaction.rollback()


@pytest.fixture
def session_factory(_outer_connection: AsyncConnection) -> async_sessionmaker[AsyncSession]:
    """The one sanctioned session factory; every session joins the test's outer transaction."""
    return async_sessionmaker(
        bind=_outer_connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )


class TestInfrastructureProvider(Provider):
    """Per-test infrastructure bindings, passed last to the real composition root so they
    supersede the production ones before anything resolves."""

    scope = Scope.APP

    def __init__(
        self,
        postgres_settings: PostgresSettings,
        session_factory: async_sessionmaker[AsyncSession],
    ) -> None:
        super().__init__()
        self._postgres_settings = postgres_settings
        self._session_factory = session_factory

    @provide(override=True)
    def postgres_settings(self) -> PostgresSettings:
        return self._postgres_settings

    @provide(override=True)
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        return self._session_factory


@pytest.fixture
async def container(
    session_factory: async_sessionmaker[AsyncSession],
    postgres_settings: PostgresSettings,
) -> AsyncIterator[AsyncContainer]:
    """The real composition root with the per-test infrastructure bindings in place."""
    from myapp.containers import create_container

    container = create_container(
        TestInfrastructureProvider(postgres_settings=postgres_settings, session_factory=session_factory),
    )
    try:
        yield container
    finally:
        await container.close()
```

This is the base: a relational store and nothing else, and no entrypoint framework — a queue-driven or
RPC service collects it as it stands and resolves its handlers from `container`. Each other store the
app carries adds its own fixtures to this file — each add-on's fixtures (the key-value store is the
worked one) — and a REST entrypoint adds `real_app`. Each store add-on, and in an app that declares
auth the verifier settings (`hex-test-restapi-auth`), adds one parameter, field and factory to
`TestInfrastructureProvider` and one parameter to `container`. With no relational store the base's Postgres
fixtures go, and `TestInfrastructureProvider` and `container` keep only the add-on parameters.

## Client-store fixtures — redis-py

An app with a client-style store (the key-value repository, `hex-store-repository`) adds this to
`tests/integration/conftest.py`: the container for the whole run, and a per-test client whose teardown
empties the container's database. The client sits here rather than beside the repository tests because
`container` binds it too.

```python
from collections.abc import AsyncIterator, Iterator

import pytest
from redis.asyncio import Redis


@pytest.fixture(scope="session")
def redis_url() -> Iterator[str]:
    from testcontainers.community.redis import RedisContainer

    # Same pin rule as the relational image (e.g. `7.4-alpine`) — never `:latest`.
    with RedisContainer("redis:<pinned-tag>") as redis:
        yield f"redis://{redis.get_container_host_ip()}:{redis.get_exposed_port(6379)}/0"


@pytest.fixture
async def redis_client(redis_url: str) -> AsyncIterator[Redis]:
    """A client on the suite's own container, emptied after each test."""
    client = Redis.from_url(redis_url)
    try:
        yield client
    finally:
        await client.flushdb()
        await client.aclose()
```

The flush is safe only because the container is the suite's own: it is disposable by construction, and
a run split across workers gives each worker its own session container. A store the suite did not start
is emptied only behind the same disposability marker; with no relational store, the guard moves to this
add-on. The same app's `container`
binds that client, so an entrypoint reaching `Baz` reads and writes the test's own store, never
whatever store the environment names: one fixture parameter passed on to `TestInfrastructureProvider`,
and there one constructor parameter, one field and one factory. The factory replaces the client binding
itself, so the production factory's close never runs and the fixture's does.

```python
    redis_client: Redis,  # in container's signature; TestInfrastructureProvider(..., redis_client=redis_client)
```

```python
        redis_client: Redis,            # in TestInfrastructureProvider.__init__
    ) -> None:
        ...
        self._redis_client = redis_client

    @provide(override=True)             # in TestInfrastructureProvider
    def redis_client(self) -> Redis:
        return self._redis_client
```

## REST entrypoint add-on — FastAPI

An app with a REST entrypoint (`hex-restapi-app`) adds `real_app` to `tests/integration/conftest.py`:
the app built on the per-test `container`, so a route under test reaches exactly the bindings the base
and each store add-on substituted. The container fixture already closes the graph; this one only builds
the app over it. Driven over an in-process transport, it never runs the lifespan, so the startup
settings check stays out of the suite; a test that must run it substitutes every settings class
`SettingsProvider` declares. A service with no HTTP entrypoint has neither this fixture nor the FastAPI
import.

```python
import pytest
from dishka import AsyncContainer
from fastapi import FastAPI


@pytest.fixture
def real_app(container: AsyncContainer) -> FastAPI:
    """FastAPI app on the per-test composition root. Rows the route under test
    commits through its handler roll back with the test's outer transaction."""
    from myapp.restapi.main import create_app

    return create_app(container=container)
```

## `pyproject.toml` and the root conftest

The runner's configuration belongs in the root `pyproject.toml` — `python-toolchain`'s
`[tool.pytest.ini_options]` block, whose session loop scopes the session-scoped engine above needs.

**A root `tests/conftest.py`, where a project has one, never imports the composition root or an entrypoint's app factory at module level, nor defines a fixture that builds either.** pytest applies the root conftest to the WHOLE suite, so a *module-level* `from myapp.restapi.main import create_app` there makes every `tests/unit/**` collection pay the entire infrastructure import chain and fail on any module it never touches. The composition-root and app-construction fixtures (`container`, and `real_app` where the app has a REST entrypoint) live in `tests/integration/conftest.py` and import `create_container` / `create_app` **inside the fixture body** (deferred, as the templates above do), so only the integration suite — which legitimately constructs the app — pays that import. Keep app construction out of any conftest a unit test inherits.

## How this binding spells them — SQLAlchemy savepoints, dishka

1. **`session_factory` binds the per-test outer connection with `join_transaction_mode="create_savepoint"`, and neither is negotiable.** Bound to the engine instead, it bypasses the rollback and every row a test commits survives into the next; without the savepoint mode, the handler's `session.commit()` either commits to disk (defeating rollback) or raises `InvalidRequestError`. With both, commit() releases a SAVEPOINT inside the outer transaction — exactly what the test needs. Rollback alone isolates; a truncate teardown beside it is the fallback for stores without nested transactions and only slows the suite.
2. **`expire_on_commit=False`** keeps loaded entities usable after a savepoint release. With `True`, every commit detaches attributes; tests asserting on returned entities then trigger lazy loads against a closed session.
3. **A substituting factory returns the plain fixture value.** `def session_factory(self) -> async_sessionmaker[AsyncSession]: return self._session_factory` — the fixture object is returned as-is, with no wrapper. Same for `postgres_settings`, and for each add-on's binding (`redis_client`). The return annotation is what binds it, so it must be the exact type the production factory binds.
