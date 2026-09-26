---
name: flat-project-setup
description: Use when laying a flat-layered service down once — the `pyproject.toml` with its src layout and dependency groups by role, the ruff configuration that bounds function size and complexity, the mypy configuration, the interpreter floor, version floors on the libraries it consumes, and the relational migration bootstrap (`alembic.ini`, the environment under `migrations/postgres/` that reads the connection string at its own composition root, the revision template, and a baseline only over a schema that already exists). Never per feature — each later schema revision is `flat-persistence`'s, and the package layout inside `src/` is `flat-layered`'s. A hexagonal project's setup is `hex-project-setup`, in the `pyhouse-hex` plugin.
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
├── migrations/           # one directory per store — `flat-persistence`
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

- Starting a flat service, adding a dependency, or writing a version floor → this skill, block A.
- Configuring the linter, the type checker, the line length or the interpreter floor → block B.
- Laying migrations on a service that has none → block C, once; this skill is one-shot, and
  `flat-persistence`'s revisions and `flat-test-integration-setup`'s migration fixture both depend on it
  having run.
- A second store's migration directory beside `migrations/postgres/`, and the tool that applies it →
  `flat-persistence`, which owns where every store's history lives.
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
    "pydantic>=2",  # 2.0: model_validate_json, ConfigDict
    "pydantic-settings",
    "sqlalchemy[asyncio]>=2",  # 2.0: inline type annotations under mypy --strict
    "structlog",
    "uuid6",
]

[dependency-groups]
dev = [
    "mypy",
    "pytest",
    "pytest-asyncio>=0.26",  # 0.26: asyncio_default_test_loop_scope
    "respx",
    "ruff",
    "testcontainers[postgres]>=4.15",  # 4.15: testcontainers.community
]

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[tool.ruff]
line-length = 120
target-version = "py313"

[tool.ruff.lint]
select = ["E", "F", "I", "B006", "B904", "C901", "PLR0911", "PLR0912", "PLR0913", "PLR0915", "PLR0917"]

[tool.ruff.lint.mccabe]
max-complexity = 10

[tool.ruff.lint.pylint]
max-args = 7
max-positional-args = 5
max-branches = 12
max-returns = 6
max-statements = 50

[tool.ruff.lint.per-file-ignores]
"__init__.py" = ["F403", "F405"]
"migrations/**/versions/*.py" = ["PLR0915"]

[tool.mypy]
python_version = "3.13"
strict = true
plugins = ["pydantic.mypy"]
files = ["src", "tests"]
explicit_package_bases = true
mypy_path = ["src", "."]
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

**Each floor's comment names the API the code relies on, and the floor lasts only as long as the code
calls it.** The four above are there because this family's templates call exactly those names — the
parse, the settings configuration, the strictly typed engine, the session-scoped test loop, the
container module. A service whose own code calls none of a floor's names drops the floor and its comment
together; one that relies on something newer raises the floor and names that instead.

## B. Toolchain configuration — ruff and mypy

The tables above are the whole of it; what they settle:

- **Lint and type-check hold `src` and `tests` at parity**, and lint reaches one directory further: ruff
  runs with no paths and so covers `migrations/`, while mypy names `src` and `tests` and stops there.
  Every fixture and helper under `tests/` is annotated, so the parity holds (`python-style`). `tests/`
  is not a package, so mypy is told the source roots (`explicit_package_bases`, with `src` and the tree
  root as `mypy_path`); without it, a `conftest.py` at two levels is two modules with one name.
- **The correctness selection is narrow**: the error and pyflakes families, import sorting, and two
  bugbear rules — a bare `raise` inside `except` without `from` (B904) and a mutable default argument
  (B006). `__init__.py` alone ignores the two wildcard-import warnings, because `python-packaging`'s
  re-export contract requires wildcards there.
- **Function size and complexity are bounded by the linter, with every threshold written down.**
  Cyclomatic complexity (C901) stops at 10, McCabe's own published ceiling; branches (PLR0912) at 12,
  return statements (PLR0911) at 6 and statements (PLR0915) at 50, pylint's long-standing defaults.
  Arguments are capped twice: positional ones (PLR0917) at 5, and all of them (PLR0913) at 7, because a
  keyword-only argument names itself at every call site — this family's bulk write helper takes three
  positional and four keyword-only. The numbers are written even where they equal the tool's default,
  for the reason the line length is: an unwritten threshold moves when the tool's default does. The
  linter has no module-length rule, so a module's size stays `flat-layered`'s one-responsibility rule,
  held in review.
- **Three suppressions are sanctioned, and no others.** The per-file wildcard ignore above; the per-file
  statement-count ignore on migration revisions, because a revision's body is generated DDL — one
  statement per column and constraint — not authored logic, and a wide table is not a function to split;
  and the `# noqa: F401` on the migration environment's table imports (block C), which exist only for
  their registration side effect — without it the linter deletes them and autogenerate stops seeing the
  schema. A function that trips a size or complexity bound is split, never suppressed. A package that
  ships no type information gets one `[[tool.mypy.overrides]]` block with `ignore_missing_imports =
  true`; none of the libraries above needs one.
- **The line length is written down once, and the number is the project's.** `120` is the width this
  catalogue's templates are written to; `88` is the formatter's default. Either is compliant once it is
  written; a change on an established tree reformats it and travels as its own commit.
- **The interpreter floor is named three times — `requires-python`, ruff's `target-version`, mypy's
  `python_version` — and all three name the same oldest interpreter.** The house floor and what may
  raise it are `python-style`'s; a linter targeting a newer interpreter than the deployment runs accepts
  forms that fail there.

## C. The migration bootstrap — Alembic over SQLAlchemy async

Laid only when the service has a relational store, and once. `alembic upgrade head` — and the
integration suite that replays it — cannot run without the config and the environment. The history
lives in `migrations/postgres/`, the directory named for the store it versions, because a second store's
history would sit beside it (`flat-persistence`); `alembic.ini` stays at the distribution root, beside
`pyproject.toml`, where every `alembic` command and the integration suite run from.

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
        sa.Column("reference", sa.String(), nullable=False),
        sa.Column("name", sa.String(), nullable=False),
        sa.Column("observed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_foos"),
        sa.UniqueConstraint("reference", name="uq_foos_reference"),
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

- **Another package manager or build backend.** poetry, pdm or hatch replace the commands and the lock
  file; `uv_build` or setuptools replace hatchling. The src layout, the development group installed by
  default (PEP 735 `[dependency-groups]`, or the tool's own table where it reads no other), names-only
  dependencies with floors only at a known break, and the three places the interpreter floor is named
  are unchanged.
- **Another linter or type checker.** flake8 with its plugins, or pyright in strict mode: the rule codes
  and keys change; the parity of `src` and `tests`, the narrow selection that still refuses an unchained
  `raise` in `except` and a mutable default, written bounds on function complexity, branches, returns,
  statements and arguments, the written line length and the three sanctioned suppressions do not.
- **Another migration tool.** The config file, the revision template and the autogenerate command
  change; the history in `migrations/postgres/` at the distribution root, the environment reading the
  connection string at its own composition root, a greenfield chain rooted at its first real revision,
  a frozen baseline only over an existing schema, and a reverse operation in every revision do not.

## Rules

1. **Laid once, in the src layout, from the first commit.** The package lives under `src/myapp/`, tests
   under `tests/`, migrations beside them in one directory per store; a single-module or flat tree matches nothing else in the
   family and has to be moved before the second module.
2. **Dependencies follow the roles the service has.** The settings library and the structured logger
   always; everything else arrives with the role that imports it, and a package nothing imports is
   removed.
3. **Dependencies are declared by name; a version floor marks a known break and says which.** The lock
   file is the only home for a pin. A floor sits at the release where an API the code relies on arrived
   or changed, with that API named beside it — never at a version remembered as recent, which is a
   guess dressed as a constraint — and a floor whose API the code no longer calls is removed with it.
4. **Development dependencies go in the group the package manager installs by default**, never a
   deprecated tool-specific table.
5. **The linter and the type checker read one configuration, held in `pyproject.toml`, with `src` and
   `tests` at parity**, the correctness selection narrow, and strict type checking with the validation
   library's plugin.
6. **Three suppressions are sanctioned: the wildcard ignore on `__init__.py`, the statement-count ignore
   on migration revisions, and the registration-import `noqa` in the migration environment.** A missing-stub override is per package in the config, never an
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
10. **A greenfield chain is rooted at its first real revision; a baseline exists only over a schema that
    already exists.** Greenfield, `versions/` starts empty and the first table's reviewed, autogenerated
    revision is the root. Over an existing schema the baseline holds that schema as hand-written DDL, is
    written once into an empty chain, is never regenerated, and existing databases are stamped with it.
11. **The linter bounds function size and complexity, with each threshold written in the config, so
    neither is left to review.** A function that trips a bound is split, never suppressed.

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
- The baseline calls `metadata.create_all` or imports the tables → stop, it is frozen DDL of what already
  existed.
- A baseline, empty or not, is being written for a greenfield schema → stop, the first table's
  autogenerated revision is the root (`flat-persistence`).
- The migration environment or its revisions are being placed under `src/`, or directly in `migrations/`
  with no directory named for the store → stop, they go in `migrations/postgres/` at the distribution
  root.
- A size or complexity rule is being dropped from the selection, its threshold raised, or a function
  exempted with `noqa` to get a large function through → stop, split the function; the bound is the
  point.
- The service is hexagonal → stop, use `hex-project-setup`, in the `pyhouse-hex` plugin.
