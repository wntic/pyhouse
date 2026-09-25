---
name: flat-test-integration-setup
description: Use when laying the shared fixtures a flat-layered service's integration tests rest on — the datastore container with its exact-name safety guard, the migration round trip, the session-scoped engine every fixture and test shares one event loop with, the rollback-scoped connection for code that accepts one, and the whole-schema wipe for code that opens its own transaction. Lives in the distribution's own `tests/integration/conftest.py`. Testing the storage package against that datastore is `flat-test-persistence`; a hexagonal package's conftest hierarchy with a dishka `real_app` is `hex-test-integration-setup`, in the `pyhouse-hex` plugin.
when_to_use: Also when asked where a flat service's test fixtures live, how integration tests get a real database, why a test suite must never truncate a developer's database, or why a session-scoped engine needs a session-scoped event loop.
---

# Flat-Layered Test — Integration Setup

Consult `test-principles` for the testing constitution. Where this skill contradicts `test-principles`, the constitution wins.

One-shot per distribution. Everything under its `tests/integration/` depends on this file: the datastore
the suite runs against, the migration history replayed onto it, the engine every test shares, and the two
isolation fixtures. **Its home is the distribution's own `tests/integration/conftest.py`.**

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
- An external-system client's own test → `flat-test-service-client`; it needs no datastore and must not
  live under `tests/integration/`.
- Row builders → not this skill; they are module-level `def`s in the test file using them.
- What the storage package under test contains, and which callables own their transactions →
  `flat-persistence`.
- Where members sit when several distributions share one repository, and the root configuration that
  registers a shared fixture module → `python-workspace`.
- Which scope a fixture takes, which conftest level it belongs at, builders versus fixtures →
  `test-principles`, the constitution. This skill is the flat-family artifact that implements it.
- The project has a domain layer and a dishka composition root → `hex-test-integration-setup`, in the
  `pyhouse-hex` plugin.
- The family itself is unsettled → `architecture-choice`, before either setup skill.

## Template — the shared fixtures (testcontainers, SQLAlchemy async, Alembic)

`tests/integration/conftest.py`:

```python
import os
import subprocess
import sys
from collections.abc import AsyncIterator, Iterator
from pathlib import Path

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

_EXTERNAL_FLAG = "MYAPP_TEST_USE_EXTERNAL"
_REQUIRED_EXTERNAL_VARS = ("MYAPP_STORAGE_DSN",)
_CONTAINER_IMAGE = "postgres:17-alpine"  # the major production runs, pinned
_ALLOWED_TEST_DATABASES = frozenset({"test"})
_DISTRIBUTION_ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture(scope="session")
def db_dsn() -> Iterator[str]:
    """A suite-owned container, or an external database only behind a dedicated opt-in flag."""
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

    from testcontainers.community.postgres import PostgresContainer

    with PostgresContainer(_CONTAINER_IMAGE, driver="asyncpg") as pg:
        yield pg.get_connection_url()


def _refuse_if_not_a_test_database(dsn: str) -> None:
    database_name = dsn.rsplit("/", 1)[-1].split("?")[0]
    if database_name not in _ALLOWED_TEST_DATABASES:
        raise RuntimeError(
            f"refusing to run integration tests against database {database_name!r} — "
            f"the external database must be one of {sorted(_ALLOWED_TEST_DATABASES)}"
        )


def _alembic(dsn: str, *args: str) -> None:
    result = subprocess.run(
        [sys.executable, "-m", "alembic", *args],
        capture_output=True,
        text=True,
        cwd=_DISTRIBUTION_ROOT,
        env={**os.environ, "MYAPP_STORAGE_DSN": dsn},
    )
    assert result.returncode == 0, result.stderr


@pytest.fixture(scope="session")
def _migrated_db(db_dsn: str) -> str:
    """Up, down to the base and up again, so every downgrade() runs once per session."""
    _alembic(db_dsn, "upgrade", "head")
    _alembic(db_dsn, "downgrade", "base")
    _alembic(db_dsn, "upgrade", "head")
    return db_dsn


@pytest.fixture(scope="session")
async def engine(_migrated_db: str) -> AsyncIterator[AsyncEngine]:
    engine = create_async_engine(_migrated_db, pool_pre_ping=False)
    try:
        yield engine
    finally:
        await engine.dispose()


@pytest.fixture
async def conn(engine: AsyncEngine) -> AsyncIterator[AsyncConnection]:
    """For anything that accepts a connection; rolled back at teardown."""
    async with engine.connect() as connection:
        trans = await connection.begin()
        try:
            yield connection
        finally:
            await trans.rollback()


@pytest.fixture(autouse=True)
async def truncate_all(engine: AsyncEngine) -> AsyncIterator[None]:
    """For code that opens and owns its own transaction; wipes every table afterwards."""
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
accepts are **declared by the project** in `_ALLOWED_TEST_DATABASES`; a project that calls its throwaway
database something else edits the constant rather than the comparison, which stays whole-name equality.

The image tag is a constant for the same reason: **the container runs the major version production
runs**, pinned to it, so the suite exercises the planner and DDL surface the migrations will meet. A
floating tag moves the schema under the suite between runs.

**The migration history runs up, down to the base, and up again, once per session.** That round trip is
what proves every revision's `downgrade()` reverses its `upgrade()` (`flat-persistence`), and the suite
then runs against the schema the history produces. The subprocess runs from the distribution root, where
`alembic.ini` sits, and hands the container's DSN to the migration environment under the variable that
environment reads — the data-access component's own, `MYAPP_STORAGE_DSN` (`flat-project-setup`).

`truncate_all` is autouse **here** because this conftest is scoped to one directory of integration tests,
all of which reach code that commits. Its teardown ordering is what keeps it safe: `TRUNCATE` takes an
`ACCESS EXCLUSIVE` lock, so it must run after `conn`'s transaction has been rolled back and its connection
returned to the pool. Because it is autouse, pytest sets it up before any fixture the test requests by
name and therefore finalizes it last. Request it by name alongside `conn` and that ordering is no longer
guaranteed, and the wipe can deadlock against the still-open transaction.

## Template — pytest configuration (pytest, pytest-asyncio)

In the distribution's own `pyproject.toml` — or, where several distributions share one repository, in
the root `pyproject.toml` that `python-workspace` lays, since pytest reads one configuration per run:

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "session"
asyncio_default_test_loop_scope = "session"
filterwarnings = ["error"]
```

Both loop-scope lines are load-bearing, not decoration. The `engine` fixture is session-scoped, so every
test and fixture must share **one** event loop. Under pytest-asyncio's default function loop scope, the
session engine's connections outlive the loop they were opened on, and the first test running a
statement that *errors* — a constraint violation through the storage class, the ordinary contract case —
crashes at teardown with `RuntimeError: Event loop is closed`, because the driver cannot cancel the
aborted command on a closed loop.

No placeholder connection string is set for collection: nothing in the service builds settings or an
engine at import (`flat-persistence` rule 14), so an unset variable fails only the code that reads it.

The container library is imported **inside** the fixture that needs it, not at module scope, so a
pure-unit collection pays nothing for it.

## Other bindings

- **One shared instance of these fixtures, where several distributions in one repository share a
  datastore.** The bodies move verbatim into a pytest plugin module beside the tests of the library that
  owns the schema, registered once per session from the repository root, so every member shares one
  container instead of starting one each (`python-workspace` carries the root configuration). Three things
  change and nothing else does: every environment name follows the owning library rather than a
  dependant, the migration subprocess runs from that library's directory, and **nothing in the module is
  autouse** — a plugin is loaded for every collection in the repository, so `truncate_all` keeps its body
  but loses `autouse=True` and each member whose code commits turns it on for its own tests in a
  one-line wrapper fixture.
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

1. **The migration runs from wherever the schema is defined** — this distribution when it owns its
   store, the owning library when several share one. One store, one history, replayed the same way the
   deploy command replays it, and taken down to the base and up again once per session so every
   `downgrade()` runs.
2. **The safety guard lives inside the fixture producing the connection details**, and guards on an
   exact database name drawn from a project-declared constant, never a port or substring heuristic.
3. **Using a datastore the suite did not start is opt-in and explicit.** Key it on a dedicated variable,
   never on ambient `CI`. Raise a named error listing every missing variable rather than letting a
   `KeyError` escape.
4. **The connection pool is session-scoped, the transaction function-scoped.** One datastore and one
   pool per run; one transaction per test. A function-scoped pool re-establishes itself every test and
   adds seconds to the run; a session-scoped connection serializes the suite onto one connection.
5. **Nothing under `tests/` builds its own pool or calls the production engine factory.** A second pool
   against the same datastore runs outside the session's loop and teardown and is never disposed. Tests
   take the shared fixture and pass it explicitly to whatever needs one.
6. **The whole-schema wipe has one body, and it runs after the test rather than before.** Cleaning up
   afterwards means a failing test leaves the datastore inspectable under a debugger, and the next test
   still starts empty. One body wherever it is defined — a second copy is two behaviours waiting to
   diverge.
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

## Hard stops

- The guard is being moved into its own fixture, or relaxed to a port or substring heuristic → stop,
  both are how a suite ends up truncating a developer's database.
- The external-database branch is being keyed on `CI` or any other ambient variable → stop, use a
  dedicated opt-in flag; ambient variables are exported by tools that know nothing about this suite.
- An autouse fixture is being added to a fixture module shared with other distributions → stop, it fires
  for every collection in the repository, pure-unit runs included; define it non-autouse there and wrap
  it as autouse where the tests actually commit.
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
- The distribution has no relational store at all → stop, none of this applies; there is no transaction to
  roll back and no schema to truncate.
- The migration fixture is trimmed to `upgrade head` alone → stop, the down-and-up round trip is the only
  thing that runs each `downgrade()` before a deploy needs it.
