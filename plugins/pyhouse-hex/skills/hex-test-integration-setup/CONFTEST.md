# hex-test-integration-setup — the conftest hierarchy

Topic file of `hex-test-integration-setup`. The mechanism-free obligations are the ten numbered under
`### The obligations` in `SKILL.md`, plus the two under `### The authenticated client`; what follows is
the **pytest + testcontainers + Alembic + SQLAlchemy savepoints + dishka** binding that satisfies them —
the files themselves first, then how this binding spells each obligation.

## `tests/integration/conftest.py`

```python
import os
import subprocess
import sys
from collections.abc import AsyncIterator, Callable, Iterator
from functools import partial
from typing import TypedDict

import pytest
from dishka import AsyncContainer, Provider, Scope, provide
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)

from myapp.infrastructure.postgres import DbSettings, create_engine


class _PgConn(TypedDict):
    host: str
    port: int
    user: str
    password: str
    name: str


@pytest.fixture(scope="session")
def postgres_container() -> Iterator[_PgConn]:
    from testcontainers.community.postgres import PostgresContainer

    # An exact, deliberately bumped tag — never `:latest` (e.g. `postgres:17-alpine`).
    with PostgresContainer("<relational-image>:<pinned-tag>") as pg:
        # Only the fixture that created the database may declare it disposable.
        os.environ["MYAPP_TEST_DISPOSABLE_DB"] = "1"
        yield {
            "host": pg.get_container_host_ip(),
            "port": int(pg.get_exposed_port(5432)),
            "user": pg.username,
            "password": pg.password,
            "name": pg.dbname,
        }


@pytest.fixture(scope="session")
def db_settings(postgres_container: _PgConn) -> DbSettings:
    return DbSettings(
        host=postgres_container["host"],
        port=postgres_container["port"],
        user=postgres_container["user"],
        password=SecretStr(postgres_container["password"]),
        name=postgres_container["name"],
    )


@pytest.fixture(scope="session", autouse=True)
def _guard_against_real_db(db_settings: DbSettings) -> None:
    """The suite migrates and rewrites schema, so it refuses to run against any
    database not **explicitly** marked disposable. The marker is set by whatever
    brought that database up — the container fixture above, the CI job, a local
    compose file — and by nothing else. It is an opt-in, not a deduction:
    inferring disposability from the port number or a substring of the database
    name guesses, and the guess is wrong in exactly the case that matters — a
    real database on a non-default port, or a production one named `*_test`,
    passes it and loses its contents. A settings flag the test environment sets
    (`DbSettings.disposable`) works the same way; what matters is that something
    declared it."""
    if os.getenv("MYAPP_TEST_DISPOSABLE_DB") != "1":
        raise RuntimeError(
            f"Integration tests refuse to run against "
            f"{db_settings.host}:{db_settings.port}/{db_settings.name}: "
            "MYAPP_TEST_DISPOSABLE_DB is not set. Set it only where the database "
            "is created for the test run and destroyed with it."
        )


def _run_alembic(db_settings: DbSettings, *args: str) -> subprocess.CompletedProcess[str]:
    env = {
        **os.environ,
        "MYAPP_DB_HOST": db_settings.host,
        "MYAPP_DB_PORT": str(db_settings.port),
        "MYAPP_DB_USER": db_settings.user,
        "MYAPP_DB_PASSWORD": db_settings.password.get_secret_value(),
        "MYAPP_DB_NAME": db_settings.name,
    }
    return subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        capture_output=True,
        text=True,
        env=env,
    )


@pytest.fixture(scope="session", autouse=True)
def _migrated_db(_guard_against_real_db: None, db_settings: DbSettings) -> DbSettings:
    result = _run_alembic(db_settings, "upgrade", "head")
    assert result.returncode == 0, result.stderr
    return db_settings


@pytest.fixture(scope="session")
def run_alembic(_migrated_db: DbSettings) -> Callable[..., subprocess.CompletedProcess[str]]:
    """The migration runner, for the migration tests that move the schema
    themselves (`hex-test-repository-contract`)."""
    return partial(_run_alembic, _migrated_db)


@pytest.fixture(scope="session")
async def _engine(_migrated_db: DbSettings) -> AsyncIterator[AsyncEngine]:
    engine = create_engine(_migrated_db)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
async def _outer_connection(_engine: AsyncEngine) -> AsyncIterator[AsyncConnection]:
    """One connection per test. Open it, begin a transaction, hand it out,
    roll it back at teardown. The handler under test can `commit()` as many
    times as it wants — each commit lands as a SAVEPOINT release inside this
    outer transaction, and the final ROLLBACK undoes everything."""
    async with _engine.connect() as conn:
        trans = await conn.begin()
        try:
            yield conn
        finally:
            await trans.rollback()


@pytest.fixture
def sf(_outer_connection: AsyncConnection) -> async_sessionmaker[AsyncSession]:
    """Sessionmaker bound to the per-test outer connection. Every session
    opened through this factory joins the outer transaction; its commit()
    creates and releases a SAVEPOINT instead of committing to disk.

    This is the *only* sanctioned sessionmaker inside `tests/integration/`.
    Direct `async_sessionmaker(bind=engine, ...)` or `bind=_engine` bypasses
    rollback and leaks rows across tests — never do it."""
    return async_sessionmaker(
        bind=_outer_connection,
        expire_on_commit=False,
        join_transaction_mode="create_savepoint",
    )


class TestInfraProvider(Provider):
    """Replaces the infrastructure bindings of the real composition root with the
    per-test fixtures. `override=True` declares that each factory deliberately
    supersedes the production one for the same type; the graph is assembled once
    with this provider last, so nothing can have resolved a production value first.

    Every add-on binding the app carries adds one parameter, one field and one
    factory here, and `container` one fixture parameter it passes on by name: each
    store add-on (the key-value store below is the worked one) and, in an app
    that declares auth, the verifier settings (`hex-test-restapi-auth`, which owns
    them and the down-tree fixture resolution they rely on).
    """

    scope = Scope.APP

    def __init__(
        self,
        db_settings: DbSettings,
        sf: async_sessionmaker[AsyncSession],
    ) -> None:
        super().__init__()
        self._db_settings = db_settings
        self._sf = sf

    @provide(override=True)
    def db_settings(self) -> DbSettings:
        return self._db_settings

    @provide(override=True)
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        return self._sf


@pytest.fixture
async def container(
    sf: async_sessionmaker[AsyncSession],
    db_settings: DbSettings,
) -> AsyncIterator[AsyncContainer]:
    """The real composition root with the DB and session-factory bindings
    replaced by the per-test fixtures. Whatever an entrypoint resolves from it —
    a route, a consumer, an RPC servicer — writes inside the same outer
    transaction the test uses, so ROLLBACK at teardown drops it too."""
    from myapp.containers import create_container

    container = create_container(
        TestInfraProvider(db_settings=db_settings, sf=sf),
    )
    try:
        yield container
    finally:
        await container.close()
```

This is the base: a relational store and nothing else, and no entrypoint framework — a queue-driven or
RPC service collects it as it stands and resolves its handlers from `container`. Each other store the
app carries adds its own fixtures to this file — each add-on's fixtures (the key-value store is the
worked one) — and a REST entrypoint adds `real_app`. With no relational store the base's Postgres
fixtures go, and `TestInfraProvider` and `container` keep only the add-on parameters.

The connection record is a private `TypedDict`: it never leaves this module, so it carries no module of
its own (`python-packaging`'s private-type allowance), and it is a declared shape rather than a bare
`dict` (`python-style`).

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

    # Same pin rule as the relational image (e.g. `redis:7.4-alpine`), never `:latest`.
    with RedisContainer("<key-value-image>:<pinned-tag>") as redis:
        yield f"redis://{redis.get_container_host_ip()}:{redis.get_exposed_port(6379)}/0"


@pytest.fixture
async def redis_client(redis_url: str) -> AsyncIterator[Redis]:
    """A client on the suite's own container, whose database is emptied after
    the test — a key-value store has no transaction to roll back, and the
    adapter's key prefix is fixed in code, so the namespace a test owns is the
    database of a container this fixture chain started and nothing else uses."""
    client = Redis.from_url(redis_url)
    try:
        yield client
    finally:
        await client.flushdb()
        await client.aclose()
```

The flush is safe only because the container is the suite's own: it is disposable by construction, and
a run split across workers gives each worker its own session container. The same app's `container`
binds that client, so an entrypoint reaching `Baz` reads and writes the test's own store, never
whatever store the environment names: one fixture parameter passed on to `TestInfraProvider`, and there
one constructor parameter, one field and one factory. The factory replaces the client binding itself, so
the production factory's close never runs and the fixture's does.

```python
    redis_client: Redis,                # in container's signature; TestInfraProvider(..., redis_client=redis_client)
```

```python
        redis_client: Redis,            # in TestInfraProvider.__init__
    ) -> None:
        ...
        self._redis_client = redis_client

    @provide(override=True)             # in TestInfraProvider
    def redis_client(self) -> Redis:
        return self._redis_client
```

## REST entrypoint add-on — FastAPI

An app with a REST entrypoint (`hex-restapi-app`) adds `real_app` to `tests/integration/conftest.py`:
the app built on the per-test `container`, so a route under test reaches exactly the bindings the base
and each store add-on substituted. The container fixture already closes the graph; this one only builds
the app over it. A service with no HTTP entrypoint has neither this fixture nor the FastAPI import.

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

## `tests/conftest.py` (top-level, optional sub-template)

Leave empty:

```python
```

The runner's configuration belongs in the root `pyproject.toml`, not here — the whole block:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "session"
asyncio_default_test_loop_scope = "session"
addopts = "--import-mode=importlib"
pythonpath = ["."]
filterwarnings = ["error"]
```

`--import-mode=importlib` lets two test modules with the same basename live in different directories
(a `test_foo.py` under both `tests/unit/` and `tests/integration/`, say) without an `__init__.py` in
every test directory; because that mode puts nothing on `sys.path`,
`pythonpath = ["."]` is what lets a test import `tests.unit.fakes` or `tests.helpers.jwt`.
`filterwarnings = ["error"]` makes every warning a failure, so a deprecation or an unclosed resource reds
the run instead of scrolling past (`test-principles`). The loop scopes are **session**, and both keys
are required. The engine fixture above is session-scoped, and everything that uses it shares its one event loop (`test-principles`, *Fixture scope rules*).

**The root `tests/conftest.py` must NOT import `create_app` / `myapp.restapi.main` (nor define a `real_app` / `client` fixture).** pytest applies the root conftest to the WHOLE suite, so a *module-level* `from myapp.restapi.main import create_app` there makes every `tests/unit/**` collection pay the entire infrastructure import chain and fail on any module it never touches. The composition-root and app-construction fixtures (`container`, and `real_app` where the app has a REST entrypoint) live in `tests/integration/conftest.py` and import `create_container` / `create_app` **inside the fixture body** (deferred, as the templates above do), so only the integration suite — which legitimately constructs the app — pays that import. Keep app construction out of any conftest a unit test inherits.

## `tests/integration/api/conftest.py`

Empty unless the app declares auth. When it does, this file carries the signing-key, verifier-settings
and authenticated-client fixtures, and `container` above grows the `jwt_settings` parameter while
`TestInfraProvider` grows the factory that makes minted tokens verify — all of it →
`hex-test-restapi-auth`.

## Per-resource `conftest.py` is **not** owned here

Per-resource fixtures (`make_foo`, …) live in `tests/integration/api/<resource>/conftest.py` next to the endpoint tests that use them. This skill does not write them; `hex-test-restapi-endpoint` references them, and each resource's tests declare the ones they need.

## How this binding spells them — testcontainers, Alembic, SQLAlchemy savepoints

1. **`sf` is the only sanctioned sessionmaker.** Every integration test, fixture, and replaced infrastructure binding goes through `sf` (function-scoped, joins the outer transaction). Direct `async_sessionmaker(bind=engine, ...)` inside `tests/integration/` bypasses rollback and leaks rows. Nothing checks this automatically; a project that wants it machine-checked writes the grep firewall itself, following `test-architecture-rule`.
2. **`join_transaction_mode="create_savepoint"` is non-negotiable.** Without it, the handler's `session.commit()` either commits to disk (defeating rollback) or raises `InvalidRequestError`. With it, commit() releases a SAVEPOINT inside the outer transaction — exactly what the test needs.
3. **`expire_on_commit=False`** keeps loaded entities usable after a savepoint release. With `True`, every commit detaches attributes; tests asserting on returned entities then trigger lazy loads against a closed session.
4. **The outer connection is function-scoped, engine is session-scoped.** One Postgres container + one engine for the whole run; one connection (and one transaction) per test. Reversing this — session-scoped connection — serializes the whole suite and defeats `pytest-xdist`. Reversing the engine — function-scoped — re-establishes the pool every test and adds seconds.
5. Test-suite separation and collection by path → `test-principles`; enforcement → `test-architecture-rule`.
6. **Obligation 10, spelled out** — rollback leaves the DB empty at test start, so `name="alpha"` needs no `uuid4().hex[:8]` suffix and `assert len(items) == N` is correct. Builders may still use unique suffixes for readability; it is no longer load-bearing.
7. **Obligation 6, spelled out** — `TestInfraProvider` is passed to `create_container` and the graph is assembled once, with the test factories last, so there is no reset, no teardown ordering to get right, and no need to audit what `containers.py` snapshots. Substituting a binding on an already-built composition root is not possible; a test that needs a different binding builds a different composition root.
8. **A substituting factory returns the plain fixture value.** `def session_factory(self) -> async_sessionmaker[AsyncSession]: return self._sf` — the fixture object is returned as-is, with no wrapper. Same for `db_settings`, and for each add-on's binding (`redis_client`). The return annotation is what binds it, so it must be the exact type the production factory binds.
9. **Obligation 8 is one `await container.close()`** in the `container` fixture's `finally`; it is function-scoped, so each test gets a clean graph.
10. **Container fixtures are session-scoped; the guard and the migration run are the autouse pair.** Every container — the relational one and each add-on's — starts once per session, on first request — the autouse guard pulls in the relational one — and the container branch is the one place entitled to set the marker obligation 4 requires — an env marker or a settings flag, **never a deduction from the port number or the database name**, because a real database on an unusual port passes that deduction and is then migrated over.
