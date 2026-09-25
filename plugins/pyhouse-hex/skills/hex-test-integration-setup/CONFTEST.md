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
import uuid
from collections.abc import AsyncIterator, Callable, Iterator
from functools import partial
from typing import TypedDict

import aioboto3
import pytest
from dishka import Provider, Scope, provide
from fastapi import FastAPI
from pydantic import SecretStr
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)

from myapp.infrastructure.postgres.engine import create_engine, dispose_engine
from myapp.infrastructure.postgres.settings import DbSettings
from myapp.infrastructure.s3 import S3Settings

class _PgConn(TypedDict):
    host: str
    port: int
    user: str
    password: str
    name: str

class _BlobStoreConn(TypedDict):
    endpoint_url: str
    access_key: str
    secret_key: str

# A dedicated opt-in variable, never an ambient one like `CI`: this suite wipes what it reaches.
_EXTERNAL_DB_FLAG = "MYAPP_TEST_USE_EXTERNAL_DB"
_EXTERNAL_STORAGE_FLAG = "MYAPP_TEST_USE_EXTERNAL_STORAGE"

@pytest.fixture(scope="session")
def postgres_container() -> Iterator[_PgConn]:
    if os.getenv(_EXTERNAL_DB_FLAG) == "1":
        yield {
            "host": os.environ["MYAPP_DB_HOST"],
            "port": int(os.environ.get("MYAPP_DB_PORT", "5432")),
            "user": os.environ["MYAPP_DB_USER"],
            "password": os.environ["MYAPP_DB_PASSWORD"],
            "name": os.environ["MYAPP_DB_NAME"],
        }
        return

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
def minio_container() -> Iterator[_BlobStoreConn]:
    if os.getenv(_EXTERNAL_STORAGE_FLAG) == "1":
        yield {
            "endpoint_url": os.environ["MYAPP_S3_ENDPOINT_URL"],
            "access_key": os.environ["MYAPP_S3_ACCESS_KEY"],
            "secret_key": os.environ["MYAPP_S3_SECRET_KEY"],
        }
        return

    from testcontainers.community.minio import MinioContainer

    # Same pin rule as the relational image (e.g. a dated `quay.io/minio/minio:RELEASE.…` tag).
    with MinioContainer("<blob-store-image>:<pinned-tag>") as minio:
        yield {
            "endpoint_url": f"http://{minio.get_container_host_ip()}:{minio.get_exposed_port(9000)}",
            "access_key": minio.access_key,
            "secret_key": minio.secret_key,
        }

@pytest.fixture(scope="session")
def db_settings(postgres_container: _PgConn) -> DbSettings:
    return DbSettings(
        host=postgres_container["host"],
        port=postgres_container["port"],
        user=postgres_container["user"],
        password=SecretStr(postgres_container["password"]),
        name=postgres_container["name"],
        # A session-long container never idles a pooled connection stale.
        pool_pre_ping=False,
    )

@pytest.fixture(scope="session")
def s3_session(minio_container: _BlobStoreConn) -> aioboto3.Session:
    return aioboto3.Session(
        aws_access_key_id=minio_container["access_key"],
        aws_secret_access_key=minio_container["secret_key"],
    )

@pytest.fixture
async def s3_settings(
    minio_container: _BlobStoreConn, s3_session: aioboto3.Session
) -> AsyncIterator[S3Settings]:
    """A fresh bucket per test — the blob store's namespace isolation, since it
    has nothing to roll back. Created before the test, emptied and dropped
    after it, so no test can see or depend on another's objects."""
    settings = S3Settings(
        endpoint_url=minio_container["endpoint_url"],
        access_key=minio_container["access_key"],
        secret_key=SecretStr(minio_container["secret_key"]),
        bucket=f"test-{uuid.uuid4().hex}",
    )
    endpoint_url = str(settings.endpoint_url)
    async with s3_session.client("s3", endpoint_url=endpoint_url) as s3:
        await s3.create_bucket(Bucket=settings.bucket)
    try:
        yield settings
    finally:
        async with s3_session.client("s3", endpoint_url=endpoint_url) as s3:
            paginator = s3.get_paginator("list_objects_v2")
            async for page in paginator.paginate(Bucket=settings.bucket):
                keys = [{"Key": obj["Key"]} for obj in page.get("Contents", [])]
                if keys:
                    await s3.delete_objects(Bucket=settings.bucket, Delete={"Objects": keys})
            await s3.delete_bucket(Bucket=settings.bucket)

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
        await dispose_engine(engine)

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

    An app that declares auth adds one field and one factory here, so that minted
    tokens verify against the running app — see `hex-test-restapi-auth`, which owns
    them and the down-tree fixture resolution they rely on.
    """

    scope = Scope.APP

    def __init__(
        self,
        db_settings: DbSettings,
        s3_settings: S3Settings,
        sf: async_sessionmaker[AsyncSession],
    ) -> None:
        super().__init__()
        self._db_settings = db_settings
        self._s3_settings = s3_settings
        self._sf = sf

    @provide(override=True)
    def db_settings(self) -> DbSettings:
        return self._db_settings

    # Blob-store apps only — see the storage-strip binding trap.
    @provide(override=True)
    def s3_settings(self) -> S3Settings:
        return self._s3_settings

    @provide(override=True)
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        return self._sf


@pytest.fixture
async def real_app(
    sf: async_sessionmaker[AsyncSession],
    db_settings: DbSettings,
    s3_settings: S3Settings,
) -> AsyncIterator[FastAPI]:
    """FastAPI app on a composition root whose DB / storage / session-factory
    bindings are the per-test fixtures. Repositories it builds therefore
    participate in the same outer transaction the test fixtures use, and
    ROLLBACK at teardown drops everything they wrote — including rows the
    route under test committed via its handler. Blobs the route writes land in
    the test's own bucket, which `s3_settings` drops at teardown.

    This fixture is usable only from tests under `tests/integration/api/`;
    tests in `tests/integration/postgres/` use `sf` directly and do not need
    `real_app`.
    """
    from myapp.containers import create_container
    from myapp.restapi.main import create_app

    container = create_container(
        TestInfraProvider(db_settings, s3_settings, sf),
    )
    app = create_app(container=container)
    try:
        yield app
    finally:
        await container.close()
```

The two connection records are private `TypedDict`s: they never leave this module, so they carry no
module of their own (`python-packaging`'s private-type allowance), and each is a declared shape rather
than a bare `dict` (`python-style`).

## Client-store session fixtures — Qdrant via `qdrant-client`

An app with a client-style store adds its session half to `tests/integration/conftest.py`: the
container and one client for the whole run. The per-test collection and its teardown sit beside the
repository tests in `tests/integration/qdrant/conftest.py` (`hex-test-repository-contract`).

```python
import os
from collections.abc import AsyncIterator, Iterator

import pytest
from qdrant_client import AsyncQdrantClient

@pytest.fixture(scope="session")
def qdrant_url() -> Iterator[str]:
    provided = os.getenv("MYAPP_TEST_QDRANT_URL")  # a dedicated opt-in variable, never ambient `CI`
    if provided:
        yield provided
        return
    from testcontainers.community.qdrant import QdrantContainer

    # An exact tag within one minor of the installed qdrant-client (it warns otherwise), never `:latest`.
    with QdrantContainer("<vector-store-image>:<pinned-tag>") as qdrant:
        yield f"http://{qdrant.rest_host_address}"

@pytest.fixture(scope="session")
async def qdrant_client(qdrant_url: str) -> AsyncIterator[AsyncQdrantClient]:
    client = AsyncQdrantClient(url=qdrant_url)
    try:
        yield client
    finally:
        await client.close()
```

## `tests/conftest.py` (top-level, optional sub-template)

Leave empty:

```python
```

`pytest-asyncio` mode and plugin declarations belong in `pyproject.toml` under `[tool.pytest.ini_options]`, not here. That block **must** carry `asyncio_mode = "auto"` **and** a **session** loop scope — `asyncio_default_fixture_loop_scope = "session"` + `asyncio_default_test_loop_scope = "session"`. The engine fixture above is session-scoped, so every test and fixture must share ONE event loop: under the default function loop scope the session engine's `asyncpg` connections outlive the loop they were opened on, and any integration test that runs a real statement which errors (a constraint violation through a repository, the canonical repo-contract case) crashes at teardown with `RuntimeError: Event loop is closed` (asyncpg cannot cancel the aborted command on a closed loop). The cheap api-discovery tests hide this — their routes (CORS / OpenAPI / an unauthenticated probe) short-circuit before touching Postgres, so no real command runs — which is why it only surfaces once a repository contract test exercises the DB.

**The root `tests/conftest.py` must NOT import `create_app` / `myapp.restapi.main` (nor define a `real_app` / `client` fixture).** pytest applies the root conftest to the WHOLE suite, so a *module-level* `from myapp.restapi.main import create_app` there makes every `tests/unit/**` collection pay the entire infrastructure import chain — and a domain-VO red→green is then blocked by an unfilled sibling (e.g. a column-less table) the unit test never touches. The app-construction fixture (`real_app`) lives in `tests/integration/conftest.py` and imports `create_app` **inside the fixture body** (deferred, as the template above does), so only the integration suite — which legitimately constructs the app — pays that import. Keep app construction out of any conftest a unit test inherits.

## `tests/integration/api/conftest.py`

Empty unless the app declares auth. When it does, this file carries the signing-key, verifier-settings
and authenticated-client fixtures, and `real_app` above grows the `jwt_settings` parameter while
`TestInfraProvider` grows the factory that makes minted tokens verify — all of it →
`hex-test-restapi-auth`.

## Per-resource `conftest.py` is **not** owned here

Per-resource fixtures (`make_foo`, `foo_id`, `bar_id`, …) live in `tests/integration/api/<resource>/conftest.py` next to the endpoint tests that use them. This skill does not write them; `hex-test-restapi-endpoint` references them but expects the consuming spec to declare what it needs.

## How this binding spells them — testcontainers, Alembic, SQLAlchemy savepoints

1. **`sf` is the only sanctioned sessionmaker.** Every integration test, fixture, and replaced infrastructure binding goes through `sf` (function-scoped, joins the outer transaction). Direct `async_sessionmaker(bind=engine, ...)` inside `tests/integration/` bypasses rollback and leaks rows. Nothing checks this automatically; a project that wants it machine-checked writes the grep firewall itself, following `test-architecture-rule`.
2. **`join_transaction_mode="create_savepoint"` is non-negotiable.** Without it, the handler's `session.commit()` either commits to disk (defeating rollback) or raises `InvalidRequestError`. With it, commit() releases a SAVEPOINT inside the outer transaction — exactly what the test needs.
3. **`expire_on_commit=False`** keeps loaded entities usable after a savepoint release. With `True`, every commit detaches attributes; tests asserting on returned entities then trigger lazy loads against a closed session.
4. **The outer connection is function-scoped, engine is session-scoped.** One Postgres container + one engine for the whole run; one connection (and one transaction) per test. Reversing this — session-scoped connection — serializes the whole suite and defeats `pytest-xdist`. Reversing the engine — function-scoped — re-establishes the pool every test and adds seconds.
5. Test-suite separation and collection by path → `test-principles`; enforcement → `test-architecture-rule`.
6. **Obligation 10, spelled out** — rollback leaves the DB empty at test start, so `name="alpha"` needs no `uuid4().hex[:8]` suffix and `assert len(items) == N` is correct. Builders may still use unique suffixes for readability; it is no longer load-bearing.
7. **Obligation 6, spelled out** — `TestInfraProvider` is passed to `create_container` and the graph is assembled once, with the test factories last, so there is no reset, no teardown ordering to get right, and no need to audit what `containers.py` snapshots. Substituting a binding on an already-built composition root is not possible; a test that needs a different binding builds a different composition root.
8. **A substituting factory returns the plain fixture value.** `def session_factory(self) -> async_sessionmaker[AsyncSession]: return self._sf` — the fixture object is returned as-is, with no wrapper. Same for `db_settings` and `s3_settings`. The return annotation is what binds it, so it must be the exact type the production factory binds.
9. **Obligation 8 is one `await container.close()`** in the `real_app` fixture's `finally`; it is function-scoped, so each test gets a clean graph.
10. **S3 has no transactions.** A bucket per test is obligation 9's spelling here: `s3_settings` creates a uniquely named bucket before the test and empties and drops it after, and `real_app` binds that same `S3Settings`, so a route under test writes into the test's own bucket with no test-only parameter on the route. The container and the `aioboto3.Session` are session-scoped; only the bucket is per test. A test asserts on its own bucket and nothing else.
11. **Container fixtures are session-scoped; the guard and the migration run are the autouse pair.** The relational and blob-store containers start once per session, on first request — the autouse guard pulls in the relational one — and the container branch is the one place entitled to set the marker obligation 4 requires — an env marker or a settings flag, **never a deduction from the port number or the database name**, because a real database on an unusual port passes that deduction and is then migrated over.
