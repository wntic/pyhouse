---
name: flat-test-integration-setup
description: Use when laying the shared fixtures a flat-layered service's integration tests rest on — the datastore container with its exact-name safety guard, the migration run, the session-scoped engine every fixture and test shares one event loop with, the rollback-scoped connection for code that accepts one, and the whole-schema wipe for code that opens its own transaction. Defaults to one service's own `tests/integration/conftest.py`; several members share a single instance of it as a plugin module registered once per session instead. Testing the storage package against that datastore is `flat-test-persistence`; a hexagonal package's conftest hierarchy with a dishka `real_app` is `hex-test-integration-setup`, in the `pyhouse-hex` plugin.
when_to_use: Also when asked where a flat service's test fixtures live, how integration tests get a real database, why a test suite must never truncate a developer's database, or why a session-scoped engine needs a session-scoped event loop.
paths: ["**/tests/**"]
---

# Flat-Layered Test — Integration Setup

Consult `test-principles` for the testing constitution. Where this skill contradicts `test-principles`, the constitution wins.

One-shot per service. Everything under that service's `tests/integration/` depends on it: the datastore
the suite runs against, the migration history replayed onto it, the engine every test shares, and the two
isolation fixtures. **The default home is the service's own `tests/integration/conftest.py`.** Where
several services share one repository and one datastore, the identical fixtures move into a pytest plugin
module registered once per session, so the members share one container instead of starting one each —
that is the second kind of the same artifact, not a different one.

**Two isolation fixtures, and which one a test uses follows from the declared transaction owner.** Every
callable in the storage package either *accepts* a live connection and never commits, or *opens and owns*
one for the whole of its work (`flat-persistence` rule 3). That declaration decides the fixture:

- **`conn`** — a rollback-scoped connection, for anything that *accepts* one: the bulk write helpers, and
  every assertion query. Fast, nothing reaches disk.
- **`truncate_all`** — wipes every table after each test, for anything that *opens and owns* its
  transaction: storage classes, run functions, and the wrappers above them. A test's outer transaction
  can neither see nor roll back a connection the code under test opened for itself.

Both are always present, and neither is a workaround. A hexagonal service whose adapter owns its
transaction needs the same wipe; a flat callable that accepts a connection is covered by the rollback.
The split is about ownership, not about which family the service is in.

## When to use vs. neighbours

- Laying or changing the fixtures themselves, or the pytest configuration block that loads them → this
  skill.
- A test of a table, a bulk helper or the storage class → `flat-test-persistence`, which consumes both
  `conn` and `truncate_all` and lays none of its own.
- A run function, a trigger wrapper or the orchestration above them → `flat-test-run-function`; its code
  owns its transactions, so it takes the wipe.
- A `services/*_client.py` test → `flat-test-service-client`; it needs no datastore and must not live
  under `tests/integration/`.
- Row builders → not this skill; they are module-level `def`s in the test file using them.
- What the storage package under test contains, and which callables own their transactions →
  `flat-persistence`.
- Where members, packages and the shared storage package sit when several services share one repository →
  `flat-monorepo`; this skill only adds the test-support module beside them.
- Which scope a fixture takes, which conftest level it belongs at, builders versus fixtures →
  `test-principles`, the constitution. This skill is the flat-family artifact that implements it.
- The project has a domain layer and a dishka composition root → `hex-test-integration-setup`, in the
  `pyhouse-hex` plugin.
- The family itself is unsettled → `architecture-choice`, before either setup skill.

## Template(s) — the shared fixtures (testcontainers, SQLAlchemy async, Alembic)

One artifact, two kinds. Write the first unless the repository holds several services sharing one
datastore.

### One service — `tests/integration/conftest.py`

```python
import os
import subprocess
import sys
from collections.abc import AsyncIterator, Iterator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

_EXTERNAL_FLAG = "MYAPP_TEST_USE_EXTERNAL"
_REQUIRED_EXTERNAL_VARS = ("MYAPP_STORAGE_DSN",)
# The image the suite starts: the major version this project runs in production, pinned.
# `17-alpine` is one project's answer — a project on another major writes its own.
_CONTAINER_IMAGE = "postgres:17-alpine"
# The database names this project declares throwaway. Matched whole, never as a substring.
_ALLOWED_TEST_DATABASES = frozenset({"test"})


# ---------- container / DSN (session-scoped, guarded) ----------


@pytest.fixture(scope="session")
def db_dsn() -> Iterator[str]:
    """The DSN every integration test runs against.

    Ephemeral container by default. Pointing the suite at an already-running database is
    opt-in through a dedicated variable, never an ambient one: any shell or CI image that
    exports `CI` would otherwise silently divert the suite onto whatever is in the
    environment — and this suite TRUNCATEs every table it can see.
    """
    if os.getenv(_EXTERNAL_FLAG) == "1":
        missing = [name for name in _REQUIRED_EXTERNAL_VARS if not os.getenv(name)]
        if missing:
            raise RuntimeError(
                f"{_EXTERNAL_FLAG}=1 but these are unset: {', '.join(missing)}"
            )
        dsn = os.environ["MYAPP_STORAGE_DSN"]
        _refuse_if_not_a_test_database(dsn)
        yield dsn
        return

    from testcontainers.postgres import PostgresContainer

    with PostgresContainer(_CONTAINER_IMAGE) as pg:
        yield (
            f"postgresql+asyncpg://{pg.username}:{pg.password}"
            f"@{pg.get_container_host_ip()}:{pg.get_exposed_port(5432)}/{pg.dbname}"
        )


def _refuse_if_not_a_test_database(dsn: str) -> None:
    """Integration tests DROP and TRUNCATE. Refuse any name not on the declared allowlist."""
    database_name = dsn.rsplit("/", 1)[-1].split("?")[0]
    if database_name not in _ALLOWED_TEST_DATABASES:
        raise RuntimeError(
            f"refusing to run integration tests against database {database_name!r} — "
            f"the external database must be one of {sorted(_ALLOWED_TEST_DATABASES)}"
        )


# ---------- migrations (once per session) ----------


@pytest.fixture(scope="session")
def _migrated_db(db_dsn: str) -> str:
    """Replay the migration history from where the schema is defined, as the deploy command does."""
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        capture_output=True,
        text=True,
        env={**os.environ, "MYAPP_STORAGE_DSN": db_dsn},
    )
    assert result.returncode == 0, result.stderr
    return db_dsn


# ---------- engine (session-scoped) ----------


@pytest.fixture(scope="session")
async def engine(_migrated_db: str) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(_migrated_db, pool_pre_ping=False)
    try:
        yield engine
    finally:
        await engine.dispose()


# ---------- isolation 1: rollback-scoped connection ----------


@pytest.fixture
async def conn(engine: AsyncEngine) -> AsyncIterator[AsyncConnection]:
    """One connection per test, inside a transaction rolled back at teardown.

    For anything that ACCEPTS a connection — the bulk write helpers, and every assertion
    query. Nothing written through it reaches disk, so tests using only this fixture are
    the fastest and cannot leak.
    """
    async with engine.connect() as connection:
        trans = await connection.begin()
        try:
            yield connection
        finally:
            await trans.rollback()


# ---------- isolation 2: whole-schema TRUNCATE (autouse here) ----------


@pytest.fixture(autouse=True)
async def truncate_all(engine: AsyncEngine) -> AsyncIterator[None]:
    """Wipe every table after each test, for code that opens and owns its own transaction."""
    from myapp.storage.metadata import metadata

    yield
    tables = ", ".join(f'"{t.name}"' for t in metadata.sorted_tables)
    if not tables:
        return
    async with engine.begin() as cleanup:
        await cleanup.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
```

**The guard lives inside the fixture that produces the connection details**, not in a fixture of its
own. A separate guard fixture is bypassed by any test that reaches for the DSN directly; a check inside
`db_dsn` cannot be. And it guards on an **exact database name**, never a port heuristic — a project whose
dev stack is remapped to non-default ports sails straight through "not the default port". The names it
accepts are **declared by the project** in `_ALLOWED_TEST_DATABASES`; `test` is one project's convention,
and a project that calls its throwaway database something else edits the constant rather than the
comparison, which stays whole-name equality.

The image tag is a constant for the same reason: **the container runs the major version production
runs**, pinned to it, so the suite exercises the planner and DDL surface the migrations will meet. A
floating tag moves the schema under the suite between runs.

`truncate_all` is autouse **here** because this conftest is scoped to one directory of integration tests,
all of which reach code that commits. Its teardown ordering is what keeps it safe: `TRUNCATE` takes an
`ACCESS EXCLUSIVE` lock, so it must run after `conn`'s transaction has been rolled back and its connection
returned to the pool. Because it is autouse, pytest sets it up before any fixture the test requests by
name and therefore finalizes it last. Request it by name alongside `conn` and that ordering is no longer
guaranteed, and the wipe can deadlock against the still-open transaction.

### Several members — one registered plugin module

Where several services share one repository and one datastore, the fixture bodies above move verbatim
into a plugin module beside the owning package's tests —
`packages/myschema/tests/myschema_testing.py` — and three things change:

- **Every environment name follows the owning package**, not a service: `MYSCHEMA_DSN`, and the migration
  subprocess runs with `cwd="packages/myschema"`, because that is where the schema is defined.
- **Nothing in the module is autouse.** A plugin is loaded for *every* collection in the repository,
  pure-unit runs included, and an autouse fixture there would start a container for tests that asked for
  none. `truncate_all` keeps its body but loses `autouse=True`; each member whose code commits turns it
  on for its own tests, in one line:

```python
# services/foo_parser/tests/integration/conftest.py
import pytest


@pytest.fixture(autouse=True)
async def _truncate_all(truncate_all: None) -> None:
    """Everything under this directory commits; wipe the schema after each test."""
```

- **The module is registered once per session**, from the root configuration below. No import is needed:
  a plugin's fixtures are visible by name everywhere in the session, and the wrapper body is empty
  because the work is the dependency.

A plugin rather than a conftest because a plugin is registered **once per session**: every member shares
one container, where a conftest copied into each member's `tests/` starts one container per member. A
root `conftest.py` would share correctly but puts test infrastructure at the repository root and reaches
members only from above.

Beside the tests, not inside `src/`: it is test-support code and has no business shipping in the wheel or
the runtime image. `pythonpath` is what makes it importable by name — it needs a distinctive one, since
the entry lands on `sys.path` for the whole session. That entry resolves against pytest's **rootdir**, so
a member that later grows its own `[tool.pytest.ini_options]` (moving rootdir) has to repeat it.

## Template — pytest configuration (pytest, pytest-asyncio, pytest-env)

One service, in its own `pyproject.toml`:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "session"
asyncio_default_test_loop_scope = "session"
filterwarnings = ["error"]
env = ["D:MYAPP_STORAGE_DSN=postgresql+asyncpg://test:test@localhost:1/placeholder"]
```

Several members add three lines at the **root** `pyproject.toml`, which registers the plugin module and
names every member root the runner must collect:

```toml
addopts = "-p myschema_testing --import-mode=importlib"
pythonpath = ["packages/myschema/tests"]
testpaths = ["packages", "services", "tests"]  # every member root, plus repository-level tests
```

Both loop-scope lines are load-bearing, not decoration. The `engine` fixture is session-scoped, so every
test and fixture must share **one** event loop. Under pytest-asyncio's default function loop scope, the
session engine's connections outlive the loop they were opened on, and the first test running a
statement that *errors* — a constraint violation through the storage class, the ordinary contract case —
crashes at teardown with `RuntimeError: Event loop is closed`, because the driver cannot cancel the
aborted command on a closed loop.

The `D:` prefix on the placeholder makes it a **default** rather than an override, so the opt-in external
path still sees a real exported DSN.

`testpaths` names the member roots the repository actually has; the three above are one repository's, not
a required shape. Leaving a root out means its integration tests never run under a bare `pytest`.

Keep the plugin module to fixtures alone — pytest imports it for the whole suite, so anything at module
scope there is paid for by every unit collection too. The container library is imported *inside* the
fixture that needs it for exactly this reason.

## Other bindings

- **A pre-provisioned throwaway database** — a compose service, a CI service container, one issued per
  branch. The container fixture disappears and `db_dsn` takes the external branch it already carries;
  the migration run, the engine scope and both isolation fixtures are unchanged. **The name guard must
  not disappear with the container**: it stops being a second line of defence and becomes the only one,
  since the suite still TRUNCATEs every table it can see.
- **An in-process or file-backed engine** (SQLite through an async driver). Cheapest to start, and it
  costs what this level buys: upsert semantics, generated constraint names and transaction behaviour are
  no longer production's, so `flat-test-persistence`'s constraint-name and conflict-path assertions stop
  meaning anything. Never for the storage package's own suite.
- **Creating the schema from the metadata instead of replaying the migration history.** Faster, and it
  stops testing that the migrations produce the schema the code expects — which is the drift the history
  exists to prevent. Keep the history wherever the migrations are themselves an artifact the project
  ships.

## Rules

1. **The migration runs from wherever the schema is defined** — the service itself when it owns its
   store, the owning package when several services share one. One store, one history, replayed the same
   way the deploy command replays it.
2. **The safety guard lives inside the fixture producing the connection details**, and guards on an
   exact database name drawn from a project-declared constant, never a port or substring heuristic.
3. **Using a datastore the suite did not start is opt-in and explicit.** Key it on a dedicated variable,
   never on ambient `CI`. Raise a named error listing every missing variable rather than letting a
   `KeyError` escape.
4. **The connection pool is session-scoped, the transaction function-scoped.** One datastore and one
   pool per run; one transaction per test. A function-scoped pool re-establishes itself every test and
   adds seconds to the run; a session-scoped connection serializes the suite onto one connection.
5. **Nothing under `tests/` builds its own pool or calls the production engine factory.** That factory
   reads the placeholder connection string, and a second pool against the same datastore is never
   disposed. Tests take the shared fixture and pass it explicitly to whatever needs one.
6. **The whole-schema wipe has one body, and it runs after the test rather than before.** Cleaning up
   afterwards means a failing test leaves the datastore inspectable under a debugger, and the next test
   still starts empty. Shared across members it is defined once, non-autouse, and switched on per member.
7. **Do not request the wipe by name in a test that only uses the rollback connection.** The rollback
   already covers it, and a by-name request loses the autouse ordering that keeps the wipe's exclusive
   table lock from meeting the connection's still-open transaction.
8. **Every fixture and test in a run that shares a session-scoped pool runs on one event loop.** A
   session-scoped pool whose connections outlive the loop they were opened on crashes at teardown the
   first time a statement *errors* — the driver cannot cancel an aborted command on a closed loop — so
   the failure surfaces as an unrelated "event loop is closed" on an ordinary constraint-violation test.
9. **Turn off the pool's per-checkout liveness check where the datastore cannot vanish mid-run.** A
   suite-owned container is up for the whole session, so the check is a round trip per checkout buying
   nothing (`pool_pre_ping=False` here). Leave it on against a remote or shared datastore.
10. **A placeholder value the test configuration sets must default, never override**, so the opt-in
    external path still sees a real exported value. Under pytest-env that is the `D:` prefix.

## Hard stops

- The guard is being moved into its own fixture, or relaxed to a port or substring heuristic → stop,
  both are how a suite ends up truncating a developer's database.
- The external-database branch is being keyed on `CI` or any other ambient variable → stop, use a
  dedicated opt-in flag; ambient variables are exported by tools that know nothing about this suite.
- An autouse fixture is being added to a plugin module shared across members → stop, it fires for every
  unit test in the repository; define it non-autouse there and wrap it as autouse per member.
- The body of `truncate_all` is being copied into a second conftest → stop, depend on the shared fixture
  and add `autouse=True` in the wrapper; one body, one place.
- A savepoint-rollback fixture is being added so the storage class's tests can avoid the wipe → stop, that
  class is the declared owner of its transaction and opens its own connection (`flat-persistence`
  rule 3); the savepoint would isolate a connection nothing under test uses, and the test would pass
  while asserting nothing.
- A test calls `create_async_engine` itself instead of taking the `engine` fixture → stop, that is a
  second pool against the same container and it will not be disposed.
- The guard is being relaxed because someone wants to run against a local database → stop, the suite
  TRUNCATEs every table in the schema; that is exactly the accident the guard prevents.
- `filterwarnings = ["error"]` is being dropped because a dependency is noisy → stop, write one narrow
  `"ignore:..."` entry after `"error"` with its reason in a comment.
- The service has no relational store at all → stop, none of this applies; there is no transaction to
  roll back and no schema to truncate.
