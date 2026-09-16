---
name: flat-test-integration-setup
description: Use when a uv workspace needs the shared integration fixtures every member loads — where shared fixtures live in a workspace — the pytest plugin module `packages/myschema/tests/myschema_testing.py`, registered once through `addopts = "-p myschema_testing"` rather than a conftest copied into each member, carrying the Postgres container with its database-name guard and Alembic run, the rollback-scoped `conn` and `truncate_all`. Testing a table, bulk helper or repository against that database is `flat-test-schema-package`; one package's `tests/integration/conftest.py` with a dishka `real_app` is `hex-test-integration-setup`.
paths: ["**/tests/**"]
---

# Flat-Layered Test — Integration Setup

Consult `test-principles` for the testing constitution. Where this skill contradicts `test-principles`, the constitution wins.

One-shot per workspace. Every member's `tests/integration/` depends on it. It is a **pytest plugin
module living with the tests of the package that owns the schema** —
`packages/myschema/tests/myschema_testing.py` — loaded by `addopts = "-p myschema_testing"` plus
`pythonpath = ["packages/myschema/tests"]`.

A plugin, not a conftest, because a plugin is registered **once per session**: every member shares one
container, where a conftest copied into each member's `tests/` starts one container per member. A root
`conftest.py` would share correctly but puts test infrastructure at the workspace root and reaches
members only from above.

Beside the tests, not inside `src/`: it is test-support code and has no business shipping in the wheel
or the runtime image. `pythonpath` is what makes it importable by name — it needs a distinctive one,
since the entry lands on `sys.path` for the whole session. That entry resolves against pytest's
**rootdir**, so a member that later grows its own `[tool.pytest.ini_options]` (moving rootdir) has to
repeat it.

**Nothing in it is autouse.** The plugin is loaded for every collection in the workspace, pure-unit runs
included, and an autouse fixture here would start a container for tests that asked for none. Ordering
comes from the dependency chain instead: `engine` requires `_migrated_db`, which requires `db_dsn`,
which carries the safety guard. The whole-schema TRUNCATE, `truncate_all`, is **defined
here but not autouse here**; each package whose code commits makes it autouse in its own integration
conftest, in one line.

**Two isolation mechanisms, not one.** A ports-and-adapters project gets away with a single
savepoint-rollback fixture because its DI container lets the test swap the session factory underneath
the code under test. A flat-layered service has no container: `EntitiesRepository.record_batch` calls
`self._engine.begin()` itself, opening its own connection, which a test's outer transaction can neither
see nor roll back. So:

- **`conn`** — a rollback-scoped connection, for anything that *accepts* a connection (`bulk_upsert`,
  `bulk_upsert_returning`, and every assertion query). Fast, nothing reaches disk.
- **`truncate_all`** — wipes every table after each test, for anything that *owns* its transactions
  (repository classes, run functions, Temporal activities). Defined in the plugin so its body exists
  once; made autouse per committing package.

Both are always present. Which one a given test relies on follows from what it calls, and the skill
owning that test says which.

## When to use vs. neighbours

- Laying or changing `myschema_testing.py`, or the root `[tool.pytest.ini_options]` block that loads it → this skill.
- A test of a table, bulk helper or repository class → `flat-test-schema-package` (consumes both `conn` and `truncate_all`).
- An `ingest/`/`jobs/` run function or a Temporal activity → `flat-test-run-function` (its package's
  conftest makes `truncate_all` autouse).
- A Temporal workflow → `flat-test-temporal-workflow`; it needs no database at all.
- A `services/*_client.py` test → `flat-test-service-client`; it needs no database and must not
  live under a member's `tests/integration/`.
- Per-producer row builders → not this skill; they are module-level `def`s in the test file using them.
- Where the workspace's members, packages and schema owner sit in the first place → `flat-monorepo`;
  this skill only adds the test-support module beside the schema package's tests.
- Which scope a fixture takes, which conftest level it belongs at, builders versus fixtures →
  `test-principles`, the constitution. This skill is the flat-family artifact that implements it, so
  "where do the shared fixtures live in this workspace" lands here.
- The project has a domain layer and a dishka composition root → `hex-test-integration-setup`, in the
  `pyhouse-hex` plugin; a
  savepoint session-factory fixture works there and does not work here, because a flat repository
  opens its own connection through `engine.begin()`.
- The family itself is unsettled → `architecture-choice`, before either setup skill.

## Template — pytest plugin module (testcontainers, SQLAlchemy async, Alembic)

`packages/myschema/tests/myschema_testing.py`:

```python
import os
import subprocess
import sys
from collections.abc import AsyncIterator, Iterator

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine, create_async_engine

_EXTERNAL_FLAG = "MYSCHEMA_TEST_USE_EXTERNAL"
_REQUIRED_EXTERNAL_VARS = ("MYSCHEMA_DSN",)
# The image the suite starts: the major version this project runs in production, pinned.
# `17-alpine` is one workspace's answer — a project on another major writes its own.
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
        dsn = os.environ["MYSCHEMA_DSN"]
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
    """Run the one shared migration history from the schema package, as `make migrate` does."""
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd="packages/myschema",
        capture_output=True,
        text=True,
        env={**os.environ, "MYSCHEMA_DSN": db_dsn},
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

    Use it for anything that ACCEPTS a connection — `bulk_upsert`, `bulk_upsert_returning`,
    and every assertion query. Nothing written through it reaches disk, so tests using only
    this fixture are the fastest and cannot leak.
    """
    async with engine.connect() as connection:
        trans = await connection.begin()
        try:
            yield connection
        finally:
            await trans.rollback()


# ---------- isolation 2: whole-schema TRUNCATE (defined here, autouse per package) ----------


@pytest.fixture
async def truncate_all(engine: AsyncEngine) -> AsyncIterator[None]:
    """Wipe every table after each test, for code that commits past the outer rollback.

    Not autouse here: the plugin is loaded for every collection in the workspace. A package
    whose code commits makes it autouse in its own integration conftest.
    """
    from myschema.metadata import metadata

    yield
    tables = ", ".join(f'"{t.name}"' for t in metadata.sorted_tables)
    if not tables:
        return
    async with engine.begin() as cleanup:
        await cleanup.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
```

**The guard lives inside the fixture that produces the connection details**, not in a fixture of its
own. A separate guard fixture is bypassed by any test that reaches for the DSN directly; a check inside
`db_dsn` cannot be. And it guards on an **exact database name**, never a port heuristic — a workspace
whose dev stack is remapped to non-default ports sails straight through "not the default port". The
names it accepts are **declared by the project** in `_ALLOWED_TEST_DATABASES`; `test` is one workspace's
convention, and a workspace that calls its throwaway database something else edits the constant rather
than the comparison, which stays whole-name equality.

The image tag is a constant for the same reason: **the container runs the major version production
runs**, pinned to it, so the suite exercises the planner and DDL surface the migrations will meet. A
floating tag moves the schema under the suite between runs.

## Template — root `pyproject.toml`, pytest + pytest-asyncio + pytest-env

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "session"
asyncio_default_test_loop_scope = "session"
addopts = "-p myschema_testing --import-mode=importlib"
pythonpath = ["packages/myschema/tests"]
testpaths = ["packages", "services", "tests"]  # every member root, plus workspace-level tests
filterwarnings = ["error"]
env = ["D:MYSCHEMA_DSN=postgresql+asyncpg://test:test@localhost:1/placeholder"]
```

Both loop-scope lines are load-bearing, not decoration. The `engine` fixture is session-scoped, so every
test and fixture must share **one** event loop. Under pytest-asyncio's default function loop scope, the
session engine's connections outlive the loop they were opened on, and the first test running a
statement that *errors* — a constraint violation through a repository, the ordinary schema-contract case
— crashes at teardown with `RuntimeError: Event loop is closed`, because the driver cannot cancel the
aborted command on a closed loop.

`testpaths` names **every member root the workspace actually has, plus the workspace-level `tests/`** —
the three above are one workspace's roots, not a required shape; a workspace with one member root lists
one. Leaving a root out means its integration tests never run under a bare `pytest`.

The `D:` prefix on the placeholder makes it a **default** rather than an override, so the opt-in
external path still sees a real exported DSN.

Keep the plugin to fixtures alone — pytest imports it for the whole suite, so anything at module scope
there is paid for by every unit collection too. The container library is imported *inside* the fixture
that needs it for exactly this reason.

## Template — pytest conftest, a package's `tests/integration/`

Only what that package adds. Every package **whose code commits** — the schema package, and every
service with run-function or activity tests — adds the same single line, turning the plugin's
`truncate_all` into an autouse fixture for that package's tests and nothing else:

```python
import pytest


@pytest.fixture(autouse=True)
async def _truncate_all(truncate_all: None) -> None:
    """Everything under this directory commits; wipe the schema after each test."""
```

No import of the plugin is needed: a pytest plugin's fixtures are visible by name everywhere in the
session. The body is empty because the work is the dependency.

**Teardown ordering is what makes this safe, and it is not incidental.** `truncate_all` and `conn` are
both function-scoped and both depend on `engine`, and `TRUNCATE` takes an `ACCESS EXCLUSIVE` lock — it
blocks until every other transaction on those tables has ended. Because the wrapper is **autouse**,
pytest sets it up before any fixture the test requests by name, and therefore finalizes it **last**:
`conn`'s transaction is already rolled back and its connection returned to the pool when the TRUNCATE
runs. Make it autouse and it is harmless; request it by name alongside `conn` and the ordering is no
longer guaranteed, and the TRUNCATE can deadlock against the connection still holding the table.

## Other bindings

- **A pre-provisioned throwaway database** — a compose service, a CI service container, one issued per
  branch. The container fixture disappears and `db_dsn` takes the external branch it already carries;
  the migration run, the engine scope and both isolation fixtures are unchanged. **The name guard must
  not disappear with the container**: it stops being a second line of defence and becomes the only one,
  since the suite still TRUNCATEs every table it can see.
- **An in-process or file-backed engine** (SQLite through an async driver). Cheapest to start, and it
  costs what this level buys: upsert semantics, generated constraint names and transaction behaviour are
  no longer production's, so `flat-test-schema-package`'s constraint-name and conflict-path assertions
  stop meaning anything. Never for the schema package's own suite.
- **Creating the schema from the metadata instead of replaying the migration history.** Faster, and it
  stops testing that the migrations produce the schema the code expects — which is the drift the schema
  package exists to prevent. Keep the history where the migrations are themselves an artifact this
  workspace ships.

## Rules

1. **The migration runs from the schema package, never from a service.** One shared schema, one
   history — the same rule the production migration command enforces.
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
6. **The whole-schema wipe is defined once in the shared plugin, made autouse only in the packages whose
   code commits, and runs after the test rather than before.** One body, no copies. Cleaning up
   afterwards means a failing test leaves the datastore inspectable under a debugger, and the next test
   still starts empty.
7. **Do not request the wipe by name in a test that only uses the rollback connection.** The rollback
   already covers it, and a by-name request loses the autouse ordering that keeps the wipe's exclusive
   table lock from meeting the connection's still-open transaction. Inside a package where the wrapper
   is autouse it is harmless and costs one statement — the price of one uniform rule instead of two
   opt-in ones.
8. **Every fixture and test in a run that shares a session-scoped pool runs on one event loop.** A
   session-scoped pool whose connections outlive the loop they were opened on crashes at teardown the
   first time a statement *errors* — the driver cannot cancel an aborted command on a closed loop — so
   the failure surfaces as an unrelated "event loop is closed" on an ordinary constraint-violation test.
   Under pytest-asyncio that is the two session default loop-scope settings above.
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
- An autouse fixture is being added to the shared plugin → stop, it fires for every unit test in the
  workspace; define it non-autouse there and wrap it as autouse in a member's integration conftest.
- The body of `truncate_all` is being copied into a service's conftest → stop, depend on the plugin's
  fixture and add `autouse=True` in the wrapper; one body, one place.
- A savepoint-rollback session-factory fixture is being added so repository tests can avoid the TRUNCATE
  → stop, the repository opens its own connection through `engine.begin()`; the savepoint would isolate
  a connection nothing under test uses, and the test would pass while asserting nothing.
- A test calls `create_async_engine` itself instead of taking the `engine` fixture → stop, that is a
  second pool against the same container and it will not be disposed.
- The guard is being relaxed because someone wants to run against a local database → stop, the suite
  TRUNCATEs every table in the schema; that is exactly the accident the guard prevents.
- `filterwarnings = ["error"]` is being dropped because a dependency is noisy → stop, write one narrow
  `"ignore:..."` entry after `"error"` with its reason in a comment.
- The workspace has no relational store at all → stop, none of this applies; there is no transaction to
  roll back and no schema to truncate.
