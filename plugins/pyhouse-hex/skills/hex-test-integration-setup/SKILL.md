---
name: hex-test-integration-setup
description: Use when laying or changing the `tests/integration/conftest.py` hierarchy one hexagonal package's suite rests on — session-scoped testcontainers, the Alembic run and the disposable-database guard, savepoint-rollback isolation through the `sf` session factory, and `real_app` on a dishka composition root whose infrastructure providers are overridden. Owns the Postgres container fixture; testing a repository against it is `hex-test-repository-contract`. Not a uv workspace's shared `myschema_testing` plugin module — that is `flat-test-integration-setup`.
paths: ["**/tests/**"]
---

# Hex Test — Integration Setup

Consult `test-principles` for the testing constitution. Where this skill contradicts `test-principles`, the constitution wins.

One-shot per project, and everything else in the integration suite depends on it. **This is the relational-store isolation strategy.**

## When to use vs. neighbours

- Laying either conftest for the first time, or changing a fixture in one → this skill.
- A repository contract test → `hex-test-repository-contract` (consumes `sf`).
- An API endpoint test → `hex-test-restapi-endpoint` (consumes `sf` and `real_app`).
- The cross-cutting OpenAPI / CORS / request-size invariants → `hex-test-discovery-invariants` (consumes `real_app` directly).
- A handler test that runs on in-memory fakes and needs no database at all → `hex-test-application-handler`; none of these fixtures apply to it.
- A capability adapter's own assertions — the respx gateway, the SDK-error translation, the pure-CPU case → `hex-test-capability-adapter`. The session-scoped container its backend needs is still declared here.
- The signing-key and token-minting fixtures, the authenticated client, and the `jwt_settings` override `real_app` grows in an auth app → `hex-test-restapi-auth`. Only for an app that declares auth; this skill is complete without it.
- The route-side auth dependencies themselves → `hex-restapi-auth`.
- Per-resource row factories (`make_foo`, `foo_id`, …) → not this skill; they live in `tests/integration/api/<resource>/conftest.py` next to the tests that use them.
- Which scope a fixture takes, which conftest level it belongs at, builders versus fixtures → `test-principles`, the constitution. This skill is the hexagonal artifact that implements it.
- The same fixtures for a uv workspace — one plugin module shared by many members instead of one package's conftest → `flat-test-integration-setup`, in the `pyhouse-flat` plugin.
- The composition root has no `session_factory` binding, or no way to pass extra providers into it → `hex-wiring` first; the substitution seam is `create_container`'s parameter, not something a test can bolt on.
- The grep that enforces "`sf` is the only sessionmaker under `tests/integration/`" → `test-architecture-rule`.

## Template(s) — pytest, testcontainers, dishka

### `tests/integration/conftest.py`

```python
import os
import subprocess
import sys
from collections.abc import AsyncIterator, Iterator
from typing import TypedDict

import pytest
from dishka import Provider, Scope, provide
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import (
    AsyncConnection,
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
)

from myapp.infrastructure.postgres.engine import create_engine, dispose_engine
from myapp.infrastructure.postgres.settings import DbSettings
from myapp.infrastructure.s3.settings import StorageSettings

# ---------- container lifecycle (session-scoped) ----------

class PgConn(TypedDict):
    host: str
    port: int
    user: str
    password: str
    name: str

# Opt in to an already-provisioned throwaway database through a DEDICATED variable,
# never an ambient one: any shell or CI image that exports `CI` would otherwise divert
# the suite onto whatever is in the environment, and this suite is entitled to wipe it.
_EXTERNAL_DB_FLAG = "MYAPP_TEST_USE_EXTERNAL_DB"
_EXTERNAL_STORAGE_FLAG = "MYAPP_TEST_USE_EXTERNAL_STORAGE"

@pytest.fixture(scope="session")
def postgres_container() -> Iterator[PgConn]:
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

    # Pin the image tag — never float on `:latest` or a moving alias, which makes
    # the suite non-reproducible: the same commit meets a different server on a
    # rerun. Fill `<relational-image>:<pinned-tag>` from your own stack;
    # `postgres:17-alpine` is the worked example. The pin is bumped deliberately,
    # not frozen forever.
    with PostgresContainer("<relational-image>:<pinned-tag>") as pg:
        # This fixture created the container, so it knows the database is
        # disposable and is the one place entitled to set the guard's marker.
        # The external branch above is not: there, whatever provisions the
        # database sets it.
        os.environ["MYAPP_TEST_DISPOSABLE_DB"] = "1"
        yield {
            "host": pg.get_container_host_ip(),
            "port": int(pg.get_exposed_port(5432)),
            "user": pg.username,
            "password": pg.password,
            "name": pg.dbname,
        }

@pytest.fixture(scope="session")
def minio_container() -> Iterator[dict[str, str]]:
    if os.getenv(_EXTERNAL_STORAGE_FLAG) == "1":
        yield {
            "endpoint_url": os.environ["MYAPP_STORAGE_ENDPOINT_URL"],
            "access_key": os.environ["MYAPP_STORAGE_ACCESS_KEY"],
            "secret_key": os.environ["MYAPP_STORAGE_SECRET_KEY"],
        }
        return

    from testcontainers.community.minio import MinioContainer

    # Same pin rule as the relational image above, and the conventions' "no
    # floating versions" rule: an exact tag, never `:latest` and never a moving
    # alias. Fill `<blob-store-image>:<pinned-tag>` from your own stack; MinIO is
    # the worked example. The specific pin is a per-deployment choice, bumped
    # deliberately, not a frozen constant.
    with MinioContainer("<blob-store-image>:<pinned-tag>") as minio:
        yield {
            "endpoint_url": f"http://{minio.get_container_host_ip()}:{minio.get_exposed_port(9000)}",
            "access_key": minio.access_key,
            "secret_key": minio.secret_key,
        }

@pytest.fixture(scope="session")
def db_settings(postgres_container: PgConn) -> DbSettings:
    return DbSettings(
        host=postgres_container["host"],
        port=postgres_container["port"],
        user=postgres_container["user"],
        password=postgres_container["password"],
        name=postgres_container["name"],
        # The container is up for the whole session and the pool never idles long
        # enough to go stale, so the per-checkout liveness round-trip costs a query
        # per checkout and buys nothing. A suite pointed at a shared or remote
        # database wants it left on.
        pool_pre_ping=False,
    )

@pytest.fixture(scope="session")
def storage_settings(minio_container: dict[str, str]) -> StorageSettings:
    return StorageSettings(
        endpoint_url=minio_container["endpoint_url"],
        access_key=minio_container["access_key"],
        secret_key=minio_container["secret_key"],
        public_endpoint_url=None,
    )

# ---------- safety guard ----------

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

# ---------- migrations (once per session) ----------

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

# ---------- engine (session-scoped, one per session) ----------

@pytest.fixture(scope="session")
async def _engine(_migrated_db: DbSettings) -> AsyncIterator[AsyncEngine]:
    engine = create_engine(_migrated_db)
    try:
        yield engine
    finally:
        await dispose_engine(engine)

# ---------- the load-bearing pair: outer transaction + bound sessionmaker ----------

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

# ---------- test infrastructure bindings (for API tests) ----------

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
        storage_settings: StorageSettings,
        sf: async_sessionmaker[AsyncSession],
    ) -> None:
        super().__init__()
        self._db_settings = db_settings
        self._storage_settings = storage_settings
        self._sf = sf

    @provide(override=True)
    def db_settings(self) -> DbSettings:
        return self._db_settings

    # BLOB-ONLY: present only when the app has a blob store. Drop this factory, the
    # constructor field and the fixture parameter below on an app with no S3/MinIO
    # (see the storage-strip Hard stop).
    @provide(override=True)
    def storage_settings(self) -> StorageSettings:
        return self._storage_settings

    @provide(override=True)
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        return self._sf


@pytest.fixture
async def real_app(
    sf: async_sessionmaker[AsyncSession],
    db_settings: DbSettings,
    storage_settings: StorageSettings,
) -> AsyncIterator[FastAPI]:
    """FastAPI app on a composition root whose DB / storage / session-factory
    bindings are the per-test fixtures. Repositories it builds therefore
    participate in the same outer transaction the test fixtures use, and
    ROLLBACK at teardown drops everything they wrote — including rows the
    route under test committed via its handler.

    This fixture is usable only from tests under `tests/integration/api/`;
    tests in `tests/integration/postgres/` use `sf` directly and do not need
    `real_app`.
    """
    from myapp.containers import create_container
    from myapp.restapi.main import create_app

    container = create_container(
        TestInfraProvider(db_settings, storage_settings, sf),
    )
    app = create_app(container=container)
    try:
        yield app
    finally:
        await container.close()

# ---------- S3 prefix (per-test namespace, no transactions in S3) ----------

@pytest.fixture
def s3_prefix() -> str:
    """Each test owns a unique prefix under the shared bucket. Tests that
    upload blobs must put everything under this prefix; tests that assert
    on bucket contents must filter by it. There is no S3 ROLLBACK — the
    bucket is reset only at session end. Cross-test isolation is by
    namespace, not by cleanup."""
    import uuid
    return f"test-{uuid.uuid4().hex}/"

@pytest.fixture(scope="session", autouse=True)
async def _cleanup_bucket_at_session_end(storage_settings: StorageSettings) -> AsyncIterator[None]:
    yield
    # session-end best-effort cleanup; implementation depends on the s3 helper
```

### `tests/conftest.py` (top-level, optional sub-template)

Leave empty:

```python
```

`pytest-asyncio` mode and plugin declarations belong in `pyproject.toml` under `[tool.pytest.ini_options]`, not here. That block **must** carry `asyncio_mode = "auto"` **and** a **session** loop scope — `asyncio_default_fixture_loop_scope = "session"` + `asyncio_default_test_loop_scope = "session"`. The engine fixture above is session-scoped, so every test and fixture must share ONE event loop: under the default function loop scope the session engine's `asyncpg` connections outlive the loop they were opened on, and any integration test that runs a real statement which errors (a constraint violation through a repository, the canonical repo-contract case) crashes at teardown with `RuntimeError: Event loop is closed` (asyncpg cannot cancel the aborted command on a closed loop). The cheap api-discovery tests hide this — their routes (CORS / OpenAPI / an unauthenticated probe) short-circuit before touching Postgres, so no real command runs — which is why it only surfaces once a repository contract test exercises the DB.

**The root `tests/conftest.py` must NOT import `create_app` / `myapp.restapi.main` (nor define a `real_app` / `client` fixture).** pytest applies the root conftest to the WHOLE suite, so a *module-level* `from myapp.restapi.main import create_app` there makes every `tests/unit/**` collection pay the entire infrastructure import chain — and a domain-VO red→green is then blocked by an unfilled sibling (e.g. a column-less table) the unit test never touches (F-013). The app-construction fixture (`real_app`) lives in `tests/integration/conftest.py` and imports `create_app` **inside the fixture body** (deferred, as the template above does), so only the integration suite — which legitimately constructs the app — pays that import. Keep app construction out of any conftest a unit test inherits.

### `tests/integration/api/conftest.py`

Empty unless the app declares auth. When it does, this file carries the signing-key, verifier-settings
and authenticated-client fixtures, and `real_app` above grows the `jwt_settings` parameter while
`TestInfraProvider` grows the factory that makes minted tokens verify — all of it →
`hex-test-restapi-auth`.

### Per-resource `conftest.py` is **not** owned here

Per-resource fixtures (`make_foo`, `foo_id`, `bar_id`, …) live in `tests/integration/api/<resource>/conftest.py` next to the endpoint tests that use them. This skill does not write them; `hex-test-restapi-endpoint` references them but expects the consuming spec to declare what it needs.

## Other bindings

- **`dependency-injector`.** The container fixtures, the migration run, the guard and the savepoint-rollback `sf` are unchanged; only `real_app` differs, and it differs in kind rather than in spelling. There is no `TestInfraProvider`: the fixture builds the real container, calls `.override(value)` on each provider **after** construction, and must `.reset_override()` each one in the `finally` block. Because the substitution lands on a live container, an already-resolved singleton may have captured the pre-override value — the classic case is a singleton whose `__init__` snapshots a settings field — so the fixture set grows an autouse teardown that calls `.reset()` on every such capturing singleton, and `containers.py` has to be audited once to find them. That failure mode does not exist under the primary binding, where the graph is assembled with the test factories already in it.
- **Manual composition.** The composition root is a factory function, so the fixture calls it with the test objects as arguments. No provider classes, no override marking, and teardown is whatever `AsyncExitStack` the factory returned.

## Rules

Consult `test-principles` for the testing constitution.

### Scope

- **`tests/integration/conftest.py`** — the containers, the engine, and the transaction-rollback `sf`.
  The contract: every integration test starts with an empty database, and rows the test (and its handler)
  commit are rolled back at teardown.
- **`tests/integration/api/conftest.py`** — created here, empty by default. Its only current occupant is
  the auth fixture set, which is `hex-test-restapi-auth`'s and exists only for an app that declares auth.

**This is the relational-store isolation strategy.** The engine, the Alembic migration run, and the savepoint-rollback `sf` all assume a relational store — the per-test transaction that ROLLBACKs is a SQL-database mechanism. An app whose only datastore is client-style (qdrant / redis / …) has no engine, no migration chain, and cannot use savepoint rollback; it isolates by **per-test namespace + best-effort cleanup** instead (the `s3_prefix` block above is exactly that pattern). Lay the Postgres machinery only when the app has a relational store.

**What this skill owns, exactly: every session-scoped fixture, for every store kind.** Containers,
engines, migration runs and long-lived clients belong here because one container per session is the
guarantee the whole setup rests on, and a fixture duplicated into a store-kind conftest breaks it. The
**per-test** half — a fresh collection, key-prefix, database or bucket path, and its teardown — belongs
in the sibling `tests/integration/<store-kind>/conftest.py`, next to the tests that consume it
(`hex-test-repository-contract`). `s3_prefix` above is the per-test half shown here only because blob
storage has no store-kind conftest of its own in this template.

- Per-resource row factories (`make_foo`, `make_bar`, …) → not this skill; declare them in `tests/integration/api/<resource>/conftest.py` next to the tests that use them.
- Cross-cutting "OpenAPI codes match `error_responses(...)`" / CORS / request-size invariants → `hex-test-discovery-invariants`; the every-protected-route-rejects-an-anonymous-caller probe → `hex-test-restapi-auth`.

### `real_app` is usable only from `tests/integration/api/`

In an app that declares auth, `real_app` consumes a settings fixture defined **down-tree**, in
`tests/integration/api/conftest.py`. Pytest resolves fixture names by walking the conftest hierarchy from
the running test outward, so that only works for tests under `tests/integration/api/`. That is fine —
repository contract tests use `sf` directly and never construct the FastAPI app. The mechanism, and the
override that depends on it, are `hex-test-restapi-auth`'s.

### Isolation

1. **`sf` is the only sanctioned sessionmaker.** Every integration test, fixture, and replaced infrastructure binding goes through `sf` (function-scoped, joins the outer transaction). Direct `async_sessionmaker(bind=engine, ...)` inside `tests/integration/` bypasses rollback and leaks rows. The `test-architecture-rule` skill enforces this with a grep.
2. **`join_transaction_mode="create_savepoint"` is non-negotiable.** Without it, the handler's `session.commit()` either commits to disk (defeating rollback) or raises `InvalidRequestError`. With it, commit() releases a SAVEPOINT inside the outer transaction — exactly what the test needs.
3. **`expire_on_commit=False`** keeps loaded entities usable after a savepoint release. With `True`, every commit detaches attributes; tests asserting on returned entities then trigger lazy loads against a closed session.
4. **The outer connection is function-scoped, engine is session-scoped.** One Postgres container + one engine for the whole run; one connection (and one transaction) per test. Reversing this — session-scoped connection — serializes the whole suite and defeats `pytest-xdist`. Reversing the engine — function-scoped — re-establishes the pool every test and adds seconds.
5. Test-suite separation and collection by path → `test-principles`; enforcement → `test-architecture-rule`.
6. **Fixed natural keys are now allowed.** Without rollback, every UNIQUE column needed a `uuid4().hex[:8]` suffix to avoid collisions across tests. With rollback, the DB is empty at test start — `name="alpha"` is fine. Builders may still use unique suffixes for readability, but it's no longer load-bearing.
7. **`assert len(items) == N` is now correct.** Tests may assert exact counts; no defensive `any(...)` filters; no `+1` for the test's own row in a shared list. The fixture model gives the test sole ownership of the DB during its run.
8. **Substitution happens before the composition root is built, never after.** `TestInfraProvider` is passed to `create_container` and the graph is assembled once, with the test factories last. Nothing production-side can have resolved and captured a pre-substitution value, because nothing has resolved at all yet — so there is no reset, no teardown ordering to get right, and no need to audit what `containers.py` snapshots. Substituting a binding on an already-built composition root is not possible; if a test needs a different binding, it builds a different composition root.
9. **A substituting factory returns the plain fixture value.** `def session_factory(self) -> async_sessionmaker[AsyncSession]: return self._sf` — the fixture object is returned as-is, with no wrapper. Same for `db_settings` and `storage_settings`. The return annotation is what binds it, so it must be the exact type the production factory binds.
10. **Close the composition root in the fixture's `finally`.** One `await container.close()` releases every resource the test's bindings opened, in reverse order. It is function-scoped, so each test gets a clean graph.
11. **S3 has no transactions.** Per-test `s3_prefix` is the substitute: each test writes under its own prefix; the bucket is cleaned at session end (best effort). Tests must not assert on global bucket contents — only on contents under their `s3_prefix`.
12. **Container fixtures are session-scoped autouse for migration + guard.** The relational and blob-store containers start once per session. **The guard refuses to run unless the test environment explicitly marked the database disposable** — an env marker or a settings flag set by whatever provisioned it, never a deduction from the port number or the database name, because a real database on an unusual port passes that deduction and is then migrated over.

### The authenticated client

13. **An authenticated client is not this skill's.** The single sanctioned authenticated client, the
    signing keypair, the token-minting helper and their rules → `hex-test-restapi-auth`. A raw
    `AsyncClient` over `real_app` is sanctioned here only for an app with no auth, and for the
    unauthenticated probes in `hex-test-discovery-invariants` / `hex-test-restapi-auth`.
14. **No `localhost` / `127.0.0.1` base URL.** `http://testserver` is the convention; the ASGI transport
    short-circuits the network anyway, but `testserver` makes route logs distinguishable from real
    traffic in CI logs.

## Inlined typing / import rules

- `pytest`, `dishka`, `sqlalchemy.ext.asyncio`, `subprocess`, `os`, `sys`, stdlib `collections.abc` — and the project's `infrastructure.postgres.*` + `infrastructure.s3.*`.
- `create_container` and `create_app` are imported **inside** the `real_app` fixture body, never at module level (see the root-conftest note above).
- Full annotations on every fixture signature. `AsyncIterator[T]` for yielding fixtures with cleanup.
- No `from __future__ import annotations`.

## Hard stops

- The composition root has no `session_factory` binding, or no way to pass extra providers into it → stop, use `hex-wiring` first; the substitution seam is `create_container`'s parameter, not something a test can bolt on.
- Spec asks to substitute a binding on a composition root that is already built — an `.override()`-style call inside a test → stop, build a second composition root with a substituting provider instead.
- Spec asks to keep `function`-scoped engine (one engine per test) → stop, that's the old slow model; engine is session-scoped, only the connection is function-scoped.
- Spec asks to drop `join_transaction_mode="create_savepoint"` → stop, that flag is the whole point — without it the handler's commits either escape or fail.
- Spec asks for session-scoped row fixtures (`make_foo` returning the same id across tests) → stop, rows are per-test; factories return fresh rows per call.
- Spec asks the `sf` fixture to bind to the engine directly (skipping the outer connection) → stop, that bypasses rollback and reintroduces every old failure mode.
- Spec infers "this must be a test database" from the port number, a `test` substring in the database name, or any other property of the DSN → stop, the guard takes an explicit marker set by whatever provisioned the database; a deduction passes for a real database that happens to match and the suite then migrates over it.
- Spec asks to add a `truncate_all_tables` teardown alongside rollback → stop, rollback alone is sufficient; truncate is the fallback for DBs without nested transactions and is strictly slower.
- Project does not use S3 / MinIO but spec includes the bucket fixtures → stop, strip the storage block; no need to start MinIO every session.
- The app has no relational store — a qdrant/redis-only app, say → stop, omit the Postgres engine / Alembic / savepoint-`sf` machinery; there is no SQL transaction to roll back. Isolate the client stores by per-test namespace + session-end cleanup (the `s3_prefix` pattern), not by this fixture.
- The app has no auth (every endpoint anonymous) but `real_app` carries a verifier-settings substitution → stop, strip the fixture parameter and the factory in `TestInfraProvider`. An auth-less app binds no verifier settings, so a factory claiming to override one fails when the graph is assembled; whether an app has auth follows from its routes (`hex-restapi-auth`), it is not a universal.
- Spec puts a token-minting fixture, a signing keypair or an authenticated client in either conftest this skill owns → stop, use `hex-test-restapi-auth`; they belong to the auth-only fixture set.
- Spec adds a per-resource row factory inside this conftest → stop, those live in `tests/integration/api/<resource>/conftest.py`.
