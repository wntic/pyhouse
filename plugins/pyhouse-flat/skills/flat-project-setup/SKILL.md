---
name: flat-project-setup
description: Use when laying a flat-layered service down once — the `pyproject.toml` with its src layout and dependency groups by role, the ruff and mypy configuration, the interpreter floor, version floors on the libraries it consumes, and the migration bootstrap (`alembic.ini`, the migration environment that reads the connection string at its own composition root, the revision template and the baseline revision). Never per feature — each later schema revision is `flat-persistence`'s, and the package layout inside `src/` is `flat-layered`'s. A hexagonal project's setup is `hex-project-setup`, in the `pyhouse-hex` plugin.
when_to_use: Also when asked to start a new worker, pipeline or ETL service, to add a dependency or justify a version floor, to configure the linter or type checker for one, or to add migrations to a flat service that has none.
---

# Flat Project Setup — pyproject, toolchain, dependency floors, migration bootstrap

Everything a flat-layered service needs **once**, when it is laid down or when a dependency is added —
the project file, the toolchain configuration, and the migration bootstrap the first revision cannot be
written without. None of it recurs per feature. What goes inside `src/myapp/` is `flat-layered`; what a
schema change looks like after the bootstrap is `flat-persistence`.

```
myapp/                    # the distribution's root — the repository root when it stands alone
├── pyproject.toml
├── alembic.ini           # only with a relational store
├── migrations/           # only with a relational store
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 0001_baseline.py
├── src/
│   └── myapp/            # the package — `flat-layered`
└── tests/
    ├── unit/
    └── integration/
```

## When to use vs. neighbours

- Starting a flat service, adding a dependency, or writing a version floor → this skill, block A.
- Configuring the linter, the type checker, the line length or the interpreter floor → block B.
- Laying migrations on a service that has none → block C, once; this skill is one-shot, and
  `flat-persistence`'s revisions and `flat-test-integration-setup`'s migration fixture both depend on it
  having run.
- The per-change revision that pairs with a table edit, and what a deploy obliges of it →
  `flat-persistence`.
- The packages inside `src/myapp/`, the settings class each component owns, and the entry point →
  `flat-layered`.
- The pytest configuration block and the fixtures it loads → `flat-test-integration-setup`.
- Which version the distribution itself declares, and what changes it → `python-versioning`.
- The interpreter floor as a rule, annotation forms, and the comment rules migrations follow →
  `python-style`.
- `__init__.py` re-exports and import forms → `python-packaging`.
- Several distributions in one repository — the workspace root, settings shared at the root →
  `python-workspace`; each member is still laid down by this skill, minus what the root settles.
- The family is not settled → `architecture-choice`. A hexagonal project → `hex-project-setup`, in the
  `pyhouse-hex` plugin.

## A. The project file — `pyproject.toml`, on uv and hatchling

`uv init --package --build-backend hatch myapp` lays the src layout; delete the `main` it writes into
`src/myapp/__init__.py` and the `[project.scripts]` entry that points at it — the package root stays
empty and the process starts from `__main__.py` (`flat-layered`). Then `uv add <lib>` for a dependency
and `uv add --dev <lib>` for a development one.

`pyproject.toml`, for the worked example in `flat-layered` — a client over HTTP, a relational store, a
loop:

```toml
[project]
name = "myapp"
version = "0.1.0"
requires-python = ">=3.13"
dependencies = [
    "alembic",
    "asyncpg",
    "httpx",
    "pydantic>=2",  # 2.0 is where model_validate_json and ConfigDict arrived
    "pydantic-settings",
    "sqlalchemy[asyncio]>=2",  # 2.0 is the first release with inline type annotations
    "structlog",
    "uuid6",
]

[dependency-groups]
dev = [
    "mypy",
    "pytest",
    "pytest-asyncio>=0.26",  # 0.26 is where asyncio_default_test_loop_scope arrived
    "respx",
    "ruff",
    "testcontainers[postgres]>=4.15",  # 4.15 is where testcontainers.community arrived
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
line-length = 120
target-version = "py313"

[tool.ruff.lint]
select = ["E", "F", "I", "B006", "B904"]

[tool.ruff.lint.per-file-ignores]
"__init__.py" = ["F403", "F405"]

[tool.mypy]
python_version = "3.13"
strict = true
plugins = ["pydantic.mypy"]
files = ["src", "tests"]
```

The `[tool.pytest.ini_options]` block follows these tables in the same file; its contents are
`flat-test-integration-setup`'s.

**Dependencies are chosen by the roles the service actually has.** The settings library and the
structured logger are always present — every process reads configuration and logs. The rest arrive with
the role that needs them and not before:

| Role present | Runtime dependencies it brings | Development dependencies it brings |
|---|---|---|
| any | the settings library, the structured logger | the test runner and its async plugin, the linter, the type checker |
| a client over HTTP | the HTTP client | the transport stub |
| data access on a relational store | the Core library with its async extra, the async driver, the migration tool, the time-ordered id package | the container library |
| an HTTP trigger | the web framework and its server | — |
| a durable-execution engine, once earned | the engine's SDK | the engine's test harness |
| a vendor SDK client | that SDK, with the client that wraps it | whatever double the SDK ships |

A service with no datastore carries no Core library, no driver and no migration tool; one with no HTTP
trigger carries no web framework. A dependency nothing imports is a stray package.

## B. Toolchain configuration — ruff and mypy

The tables above are the whole of it; what they settle:

- **Lint and type-check hold `src` and `tests` at parity**, and lint reaches one directory further: ruff
  runs with no paths and so covers `migrations/`, while mypy names `src` and `tests` and stops there.
  Every fixture and helper under `tests/` is annotated, so the parity holds (`python-style`).
- **The lint selection is narrow**: the error and pyflakes families, import sorting, and two bugbear
  rules — a bare `raise` inside `except` without `from` (B904) and a mutable default argument (B006).
  `__init__.py` alone ignores the two wildcard-import warnings, because `python-packaging`'s re-export
  contract requires wildcards there.
- **Two suppressions are sanctioned, and no others.** The per-file wildcard ignore above, and the
  `# noqa: F401` on the migration environment's table imports (block C), which exist only for their
  registration side effect — without it the linter deletes them and autogenerate stops seeing the
  schema. A package that ships no type information gets one `[[tool.mypy.overrides]]` block with
  `ignore_missing_imports = true`; none of the libraries above needs one.
- **The line length is written down once, and the number is the project's.** `120` is the width this
  catalogue's templates are written to; `88` is the formatter's default. Either is compliant once it is
  written; a change on an established tree reformats it and travels as its own commit.
- **The interpreter floor is named three times — `requires-python`, ruff's `target-version`, mypy's
  `python_version` — and all three name the same oldest interpreter.** The house floor and what may
  raise it are `python-style`'s; a linter targeting a newer interpreter than the deployment runs accepts
  forms that fail there.

## C. The migration bootstrap — Alembic over SQLAlchemy async

Laid only when the service has a relational store, and once. `alembic upgrade head` — and the
integration suite that replays it — cannot run without the config, the environment and a first revision
to anchor the chain.

### `alembic.ini`

```ini
[alembic]
script_location = %(here)s/migrations
```

### `migrations/env.py`

```python
import asyncio

from alembic import context
from sqlalchemy.engine import Connection

import myapp.storage.foo_table  # noqa: F401 — registers its tables on the metadata
from myapp.storage import get_engine, get_storage_settings
from myapp.storage.metadata import metadata


def _run_migrations(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=metadata)
    with context.begin_transaction():
        context.run_migrations()


async def _run_online() -> None:
    engine = get_engine(get_storage_settings().dsn.get_secret_value())
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
connection string from the variable that component owns (`MYAPP_STORAGE_DSN`), unwraps it where the
engine is built, and disposes of the engine when the run ends (`flat-layered` rules 7 and 8). Nothing in
`alembic.ini` names a database. **Every table module is imported here, one line each**, because a table
module's names are bare objects the storage package does not re-export (`python-packaging`); a new table
module adds its line in the same change that adds the module. Offline SQL generation is refused rather
than half-supported: every migration runs against a live connection.

### `migrations/script.py.mako`

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

### `migrations/versions/0001_baseline.py`

```python
"""baseline

The root of the revision chain. Empty for a schema that starts here; for a schema that
already exists, it holds those objects as hand-written DDL, and each existing database is
stamped with it instead of upgraded through it.

Revision ID: 0001
Revises:
"""

from collections.abc import Sequence

revision: str = "0001"
down_revision: str | Sequence[str] | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
```

**The baseline is written once, into an empty `versions/`, and is frozen.** On a greenfield schema it is
empty and the first table is its own revision, autogenerated from the metadata and reviewed
(`alembic revision --autogenerate -m "create foos" --rev-id 0002`, per `flat-persistence`). On a service
adopting migrations over a schema that already exists, the baseline holds those objects as hand-written
DDL — never `metadata.create_all`, which reads the metadata as it stands when the revision runs rather
than as it stood when the revision was written — and each existing database is marked with
`alembic stamp 0001` instead of being upgraded through it.

## Other bindings

- **Another package manager or build backend.** poetry, pdm or hatch replace the commands and the lock
  file; `uv_build` or setuptools replace hatchling. The src layout, the development group installed by
  default (PEP 735 `[dependency-groups]`, or the tool's own table where it reads no other), names-only
  dependencies with floors only at a known break, and the three places the interpreter floor is named
  are unchanged.
- **Another linter or type checker.** flake8 with its plugins, or pyright in strict mode: the rule codes
  and keys change; the parity of `src` and `tests`, the narrow selection that still refuses an unchained
  `raise` in `except` and a mutable default, the written line length and the two sanctioned
  suppressions do not.
- **Another migration tool.** The config file, the revision template and the autogenerate command
  change; the environment reading the connection string at its own composition root, the frozen
  baseline in an empty chain, and a reverse operation in every revision do not.

## Rules

1. **Laid once, in the src layout, from the first commit.** The package lives under `src/myapp/`, tests
   under `tests/`, migrations beside them; a single-module or flat tree matches nothing else in the
   family and has to be moved before the second module.
2. **Dependencies follow the roles the service has.** The settings library and the structured logger
   always; everything else arrives with the role that imports it, and a package nothing imports is
   removed.
3. **Dependencies are declared by name; a version floor marks a known break and says which.** The lock
   file is the only home for a pin. A floor sits at the release where an API the code relies on arrived
   or changed, with that reason beside it — never at a version remembered as recent, which is a guess
   dressed as a constraint.
4. **Development dependencies go in the group the package manager installs by default**, never a
   deprecated tool-specific table.
5. **The linter and the type checker read one configuration, held in `pyproject.toml`, with `src` and
   `tests` at parity**, the lint selection narrow, and strict type checking with the validation
   library's plugin.
6. **Two suppressions are sanctioned: the wildcard ignore on `__init__.py`, and the registration-import
   `noqa` in the migration environment.** A missing-stub override is per package in the config, never an
   inline ignore on a content module.
7. **The line length and the interpreter floor are written explicitly and settled here.** The floor is
   named identically in all three places — for a new service at or above `python-style`'s house floor;
   an existing service below it keeps its own and raises it deliberately, never lowers it.
8. **The migration environment reads the connection string through the data-access component's own
   settings factory, and only there among migration files.** It is the migration run's process
   definition; `alembic.ini` names no database, and the variable the environment reads is the one the
   integration suite sets for it.
9. **Every table module is imported by the migration environment**, so autogenerate compares the whole
   schema, and a new table module adds its import in the same change.
10. **The baseline revision is written once, into an empty chain, and never regenerated.** Greenfield,
    it is empty and the first table is its own reviewed revision; over an existing schema it holds that
    schema as hand-written DDL, and existing databases are stamped with it.

## Hard stops

- The project is being laid down as a flat module tree with no `src/` → stop, use the src layout; every
  other skill in the family assumes it.
- A dependency is pinned in `pyproject.toml`, or given a floor with no stated break → stop, names only;
  the lock file pins, and a floor names the release it depends on.
- A dependency is being added for a role the service does not have → stop, it arrives with the role.
- An inline `# type: ignore` or `# noqa` is being added to a module under `src/` → stop, fix it, or
  use a per-package override for missing stubs.
- `line-length`, `target-version` or `python_version` is left unwritten, or the three floor settings
  disagree → stop, write them once, naming one interpreter.
- `alembic.ini` carries a connection string, or the migration environment builds one from anything but
  the data-access component's settings → stop, read it at the environment's composition root.
- A baseline revision is being written into a `versions/` that already holds revisions → stop, the chain
  has started; write a revision (`flat-persistence`).
- The baseline calls `metadata.create_all` or imports the tables → stop, it is frozen DDL or it is empty.
- A table is being added in the baseline of a greenfield schema → stop, it is the first autogenerated
  revision (`flat-persistence`).
- The service is hexagonal → stop, use `hex-project-setup`, in the `pyhouse-hex` plugin.
