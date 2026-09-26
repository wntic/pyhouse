---
name: flat-project-setup
description: Use when laying a flat-layered service down once — which runtime and development libraries each of its roles brings, with the version floors this family's templates rely on, and the relational migration bootstrap (`alembic.ini`, the environment under `migrations/postgres/` that reads the connection string at its own composition root, the revision template, and a baseline only over a schema that already exists). The src layout, ruff and mypy, the line length and the dependency-floor discipline every Python project shares are `python-toolchain`'s. Never per feature — each later schema revision is `flat-persistence`'s, and the package layout inside `src/` is `flat-layered`'s. A hexagonal project's setup is `hex-project-setup`, in the `pyhouse-hex` plugin.
when_to_use: Also when asked to start a new worker, pipeline or ETL service, which libraries it needs, to add a dependency or justify one of this family's version floors, or to add migrations to a flat service that has none.
---

# Flat Project Setup — dependencies by role, migration bootstrap

What a flat-layered service needs **once**, beyond the toolchain every Python project carries: the
libraries its roles bring, and the migration bootstrap the first revision cannot be written without.
None of it recurs per feature. The project file itself — src layout, ruff, mypy, dependency
declarations — is `python-toolchain`'s; what goes inside `src/myapp/` is `flat-layered`; what a schema
change looks like after the bootstrap is `flat-persistence`.

```
myapp/                    # the distribution's root — the repository root when it stands alone
├── pyproject.toml
├── alembic.ini           # only with a relational store whose schema this service owns
├── migrations/           # only then; one directory per store — `flat-persistence`
│   └── postgres/
│       ├── env.py
│       ├── script.py.mako
│       └── versions/     # empty until the first table's revision
├── src/
│   └── myapp/            # the package — `flat-layered`
└── tests/
    ├── unit/
    └── integration/
```

## When to use vs. neighbours

- Starting a flat service, adding a dependency, or justifying one of this family's floors → block A.
- Laying migrations on a service that has none → block B, once; this skill is one-shot, and
  `flat-persistence`'s revisions and `flat-test-integration-setup`'s migration fixture both depend on it
  having run.
- The `pyproject.toml` tables, the src layout, the linter and type checker, the sanctioned
  suppressions, the line length, and whether any dependency may carry a floor → `python-toolchain`.
- A second store's migration directory beside `migrations/postgres/`, and the tool that applies it →
  `flat-persistence`, which owns where every store's history lives.
- The per-change revision that pairs with a table edit, and what a deploy obliges of it →
  `flat-persistence`.
- The packages inside `src/myapp/`, the settings class each component owns, and the entry point →
  `flat-layered`.
- The pytest configuration block and the fixtures it loads → `flat-test-integration-setup`.
- Which version the distribution itself declares, and what changes it → `python-versioning`.
- The interpreter floor, annotation forms, and the comment rules migrations follow → `python-style`.
- `__init__.py` re-exports and import forms → `python-packaging`.
- Several distributions in one repository — the workspace root, settings shared at the root →
  `python-workspace`; each member's libraries are still chosen by this skill.
- The family is not settled → `architecture-choice`. A hexagonal project → `hex-project-setup`, in the
  `pyhouse-hex` plugin.

## A. Dependencies by role — uv

`pyproject.toml` is `python-toolchain`'s template, taken as written; `uv init --package --build-backend
hatch myapp` lays it. Then delete the `main` it writes into `src/myapp/__init__.py` and the
`[project.scripts]` entry that points at it. A service that runs a single process starts it from
`__main__.py`; a service with several processes, or a CLI tool, declares one console script per process
or command in their place (`flat-layered`). What this family adds is which libraries arrive, each with
`uv add` or `uv add --dev`, and the floors its own templates rely on.

**Dependencies are chosen by the roles the service actually has.** The settings library and the
structured logger are always present — every process reads configuration and logs. The rest arrive with
the role that needs them and not before:

| Role present | Runtime dependencies it brings | Development dependencies it brings |
|---|---|---|
| any | `pydantic`, `pydantic-settings`, `structlog` | `pytest`, `ruff`, `mypy` |
| a suite with async tests | — | `pytest-asyncio>=0.26` (0.26: `asyncio_default_test_loop_scope`) |
| a client over HTTP | `httpx` | `respx` |
| data access on a relational store | `sqlalchemy[asyncio]>=2` (2.0: inline type annotations under mypy `--strict`), `asyncpg` | `testcontainers[postgres]>=4.15` (4.15: `testcontainers.community`) |
| a relational store whose schema this service owns | `alembic` | — |
| a service that mints row ids | `uuid6` | — |
| an HTTP trigger | `fastapi`, `uvicorn` | — |
| a durable-execution engine, once earned | the engine's SDK | the engine's test harness |
| a vendor SDK client | that SDK, with the client that wraps it | whatever double the SDK ships |

A service with no datastore carries no Core library, no driver and no migration tool; one that only
reads a table another service owns carries the Core library and the driver and no migration tool; one
with no HTTP trigger carries no web framework. A dependency nothing imports is a stray package.

**Each floor is written with the API beside it, as a comment on its line** —
`"sqlalchemy[asyncio]>=2",  # 2.0: inline type annotations under mypy --strict`. The three above are
there because this family's templates call exactly those names — the strictly typed engine, the
session-scoped test loop, the container module. A service whose own code
calls none of a floor's names drops the floor and its comment together; one that relies on something
newer raises the floor and names that instead (`python-toolchain` rule 9).

## B. The migration bootstrap — Alembic over SQLAlchemy async

Laid only when the service owns the schema of a relational store, and once. `alembic upgrade head` —
and the integration suite that replays it — cannot run without the config and the environment. The
history lives in `migrations/postgres/`, the directory named for the store it versions, because a second
store's history would sit beside it (`flat-persistence`); `alembic.ini` stays at the distribution root,
beside `pyproject.toml`, where every `alembic` command and the integration suite run from.

### `alembic.ini`

```ini
[alembic]
script_location = %(here)s/migrations/postgres
```

### `migrations/postgres/env.py`

```python
import asyncio

from alembic import context
from sqlalchemy.engine import Connection

import myapp.postgres.foo_table  # noqa: F401 — registers its tables on the metadata
from myapp.postgres import get_engine, get_postgres_settings
from myapp.postgres.metadata import metadata


def _run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=metadata)
    with context.begin_transaction():
        context.run_migrations()


async def _run_online() -> None:
    engine = get_engine(get_postgres_settings().dsn.get_secret_value())
    try:
        async with engine.connect() as connection:
            await connection.run_sync(_run_migrations)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    raise RuntimeError("offline mode is not supported; migrate a live database")
asyncio.run(_run_online())
```

**The migration environment is the migration run's process definition**, so it is the one place outside
the service's own entrypoints that calls the data-access component's settings factory: it reads the
connection string from the variable that component owns (`MYAPP_POSTGRES_DSN`), unwraps it where the
engine is built, and disposes of the engine when the run ends (`flat-layered` rules 7 and 8). Nothing in
`alembic.ini` names a database. **Every table module is imported here, one line each**, because a table
module's names are bare objects the data-access package does not re-export (`python-packaging`); a new
table module adds its line in the same change that adds the module. Offline SQL generation is refused
rather than half-supported: every migration runs against a live connection.

**This block sanctions two lint suppressions, the ones `python-toolchain` rule 5 leaves to it.** The
inline unused-import suppression on the environment's registration imports: they exist only for their
side effect, and without it the linter deletes them and autogenerate stops seeing the schema. And the
per-file statement-count ignore on `migrations/**/versions/*.py`, the line `python-toolchain`'s template
marks: a revision's body is generated DDL, one statement per column and constraint, not authored logic,
and a wide table is not a function to split; every other bound stays on for revisions.

### `migrations/postgres/script.py.mako`

The revision template every `alembic revision` renders, in the house's own annotation forms:

```mako
"""${message}

Revision ID: ${up_revision}
Revises: ${down_revision | comma,n}
Create Date: ${create_date}

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
${imports if imports else ""}
revision: str = ${repr(up_revision)}
down_revision: str | Sequence[str] | None = ${repr(down_revision)}
branch_labels: str | Sequence[str] | None = ${repr(branch_labels)}
depends_on: str | Sequence[str] | None = ${repr(depends_on)}


def upgrade() -> None:
    ${upgrades if upgrades else "pass"}


def downgrade() -> None:
    ${downgrades if downgrades else "pass"}
```

### The root of the chain

**Greenfield, `versions/` starts empty and the first real revision is the root.** The first table is
autogenerated from the metadata and reviewed like every later change
(`alembic revision --autogenerate -m "create foos" --rev-id 0001`, per `flat-persistence`), and Alembic
gives it no parent. An empty `upgrade head` and `downgrade base` succeed before it exists, so nothing
needs a placeholder revision ahead of it — one would be a no-op every database replays forever.

**Over a schema that already exists, the root is a baseline holding that schema as it stood**, written
once into an empty `versions/` and frozen:

`migrations/postgres/versions/0001_baseline.py`:

```python
"""baseline

Revision ID: 0001
Revises:
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "foos",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_foos"),
    )


def downgrade() -> None:
    op.drop_table("foos")
```

Every object is spelled out by hand as it stood the day the baseline was written — never
`metadata.create_all`, which reads the metadata as it stands when the revision runs rather than as it
stood when the revision was written, so the chain would stop being replayable. Each existing database is
marked with `alembic stamp 0001` instead of being upgraded through it; a fresh one — the integration
suite's — runs it like any revision.

## Other bindings

- **Another package manager.** poetry or pdm replace `uv add`; the roles and what each brings, and the
  floors with their APIs, are unchanged. The rest is `python-toolchain`'s.
- **Another migration tool.** The config file, the revision template and the autogenerate command
  change; the history in `migrations/postgres/` at the distribution root, the environment reading the
  connection string at its own composition root, a greenfield chain rooted at its first real revision,
  a frozen baseline only over an existing schema, and a reverse operation in every revision do not.

## Rules

1. **Laid once, in `python-toolchain`'s src layout, from the first commit**, with migrations — where the
   service owns the schema of a relational store — beside `src/` and `tests/` in one directory per store.
2. **Dependencies follow the roles the service has.** The settings library and the structured logger
   always; everything else arrives with the role that imports it, and a package nothing imports is
   removed.
3. **A floor is written only where this family's code relies on the API it names**, with that API
   beside it; the table in block A is the family's whole set, and each goes with the code that calls it.
   The floor discipline itself is `python-toolchain` rule 9.
4. **Everything else in the project file is `python-toolchain`'s** — the development group, the linter
   and type-checker configuration with its written bounds and the suppression it sanctions everywhere,
   the line length — and the interpreter floor is `python-style`'s. Block B's two suppressions are
   sanctioned here, and only where block B is laid.
5. **The migration environment reads the connection string through the data-access component's own
   settings factory, and only there among migration files.** It is the migration run's process
   definition; `alembic.ini` names no database, and the variable the environment reads is the one the
   integration suite sets for it.
6. **Every table module is imported by the migration environment**, so autogenerate compares the whole
   schema, and a new table module adds its import in the same change.
7. **A greenfield chain is rooted at its first real revision; a baseline exists only over a schema that
   already exists.** Greenfield, `versions/` starts empty and the first table's reviewed, autogenerated
   revision is the root. Over an existing schema the baseline holds that schema as hand-written DDL, is
   written once into an empty chain, is never regenerated, and existing databases are stamped with it.

## Hard stops

- A dependency is being added for a role the service does not have → stop, it arrives with the role.
- A floor from block A kept on a service whose code calls none of its API, or a new floor with no API
  named → stop, `python-toolchain` rule 9.
- The project file's lint, type-check or layout settings are being chosen here → stop, use
  `python-toolchain`.
- `alembic.ini` carries a connection string, or the migration environment builds one from anything but
  the data-access component's settings → stop, read it at the environment's composition root.
- A baseline revision is being written into a `versions/` that already holds revisions → stop, the chain
  has started; write a revision (`flat-persistence`).
- The baseline calls `metadata.create_all` or imports the tables → stop, it is frozen DDL of what already
  existed.
- A baseline, empty or not, is being written for a greenfield schema → stop, the first table's
  autogenerated revision is the root (`flat-persistence`).
- The migration environment or its revisions are being placed under `src/`, or directly in `migrations/`
  with no directory named for the store → stop, they go in `migrations/postgres/` at the distribution
  root.
- Migrations are being laid on a service that owns no relational schema — none at all, or one it only
  reads → stop, there is nothing for it to version; the schema's owner versions it.
- The service is hexagonal → stop, use `hex-project-setup`, in the `pyhouse-hex` plugin.
