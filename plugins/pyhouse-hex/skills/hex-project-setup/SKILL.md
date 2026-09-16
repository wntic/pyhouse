---
name: hex-project-setup
description: Use when laying a hexagonal project down once — the `pyproject.toml` dependency substrate by role, the ruff and mypy configuration, and the initial Alembic bootstrap the revision chain cannot start without. Never per feature — the per-change migration revision is `hex-persistence`, runtime DI bindings and settings classes are `hex-wiring`.
paths: ["**/pyproject.toml", "**/alembic.ini", "**/alembic/**", "**/migrations/**"]
---

# Hexagonal Project Setup — substrate, toolchain, migration bootstrap

Everything a project needs *once*, at the moment it is laid down or when a dependency is added. None of
it recurs per feature. The derivation rules that do recur are `hex-conventions`; the layer boundaries are
`hex-architecture`.

## When to use vs. neighbours

- Adding a dependency, or justifying a version floor → block A.
- Configuring the linter, the type checker, or the line length → block B.
- Laying migrations for the first time on a project that has none → block C.
- The *per-change* migration revision that pairs with a schema edit → `hex-persistence`, not here;
  this skill covers only the bootstrap that lets the chain start.
- Where a file goes and what it is called → `hex-conventions`.
- Layer boundaries and packaging → `hex-architecture`.
- Module files, `__all__` and the re-export contract inside the package → `python-packaging`.
- The runtime DI bindings and the env-backed settings classes → `hex-wiring`; this skill stops at which libraries exist.
- Whether the project should be hexagonal or flat-layered at all → `architecture-choice`; settle that before laying this down.
- A multi-service uv workspace rather than a single package → `flat-monorepo`, in the `pyhouse-flat`
  plugin.

## A. Stack substrate (library ROLES, no versions)

`pyproject.toml` carries the framework substrate plus whatever each infrastructure adapter needs.

- **Framework substrate** (always present in a layered web app): the web framework and its server, the
  validation library, the settings library, the dependency-injection library, and the structured logger.
- **Relational bootstrap** (only when a relational store backs a repository): the ORM/Core library with
  its async extra, the async driver, and the migration tool.
- **Feature-triggered extras** — a package required only because some endpoint or adapter uses a specific
  feature. Multipart form handling is the canonical example: a web framework typically imports its
  multipart library at app-construct time for any form route, and without it constructing the app raises
  — which lint, type-check and the unit tier do **not** catch. An app with no such endpoint must not
  carry it.
- **Dev** (always present): the test runner and its async plugin, the linter, the type checker, the
  container library for integration tests, and an HTTP test client.
- **Test-bootstrap extras** follow the same trigger rule as feature extras: a suite that mints
  asymmetric-signature tokens needs the crypto library that generates the keypair; a project verifying
  symmetric or opaque tokens generates no keypair and must **not** carry it. A dev dependency nothing
  imports is a stray package.
- **SDK packages are not listed as substrate** — each rides along with the adapter that needs it.

**No versions in the substrate.** This list carries names only. The lock file is the only home for a
concrete pin, so nothing rots. A pinned `>=` on a substrate library under eternal manual bump is the
disease this avoids.

**Floors on an SDK — the lone, disciplined exception.** An adapter's SDK *may* carry a `>=` floor, but
only when it marks a **known breaking-version boundary** — an API the code relies on landed or changed
there — with the floor sitting at that boundary, expressed as the major, and the reason in a comment. It
is a *contract* fact ("needs v2, where the API changed"), never a recency guess: do not write a version
you recall as "recent", because that recollection is frozen at a training cutoff, and a floor padded
above the real break is exactly that stale memory masquerading as a constraint. The shape of a good
floor: a library whose 2.0 changed a return type from `bytes` to `str` gets `>=2`; a library whose async
client merged in at 4.2, having been a separate package before, gets `>=4.2`; a library whose API has
been stable for years gets **no floor at all**. Symmetry lives in the *rule*, not in pinning every
library.

**Dev dependencies live under `[dependency-groups]` (PEP 735).** Write `[dependency-groups]` with
`dev = [...]`, which the package manager installs by default. Do not write a deprecated
tool-specific dev-dependency table.

### Adding a package and starting a project — uv

`uv add <lib>`, or `uv add --dev <lib>` for a dev dependency. Starting a project:
`uv init --package <name>` — the `--package` flag is what produces the `src/<name>/` layout with an
`__init__.py` and a build backend; plain `uv init` lays a flat single-module project that matches nothing
in this house style.

## B. Toolchain configuration — ruff and mypy

The commands that define "green" belong to the project. What lives here is the configuration those
commands read, because it is house style and has no other home.

- **Lint and type-check hold `src` and `tests` at parity** — so a defect never hides in whichever surface
  the other skips — **and lint reaches one directory further than the type checker**: the linter runs
  with no paths and so covers `migrations/` as well, while the type checker names `src tests` and stops
  at their edge. What keeps `tests` green is the rule that every fixture and helper is fully annotated: a
  fixture consuming the app types it, a yielding fixture annotates `-> AsyncIterator[T]`, a parametrize
  hook types its argument.
- **Lint rule selection**: the error and pyflakes families, import sorting, plus two individual bugbear
  rules — **not** the whole bugbear family; keep the select narrow.
  - The **raise-without-from** rule makes a bare `raise X` inside an `except` an error: chain the cause
    with `raise X(...) from exc`, or suppress it deliberately with `from None` (e.g. translating a lookup
    miss into an auth error without leaking the internal cause).
  - The **mutable-default-argument** rule flags `def f(x: list = [])`, a shared-state bug; use an
    immutable default or `None` and build inside.
  - Per-file, `__init__.py` ignores the two wildcard-import warnings, because the re-export contract in
    `python-packaging` requires wildcards. **This is the only sanctioned suppression on a content
    module** — never an inline ignore comment there.
  - **One file is not a content module: Alembic's `env.py`.** It sits outside `src/`, ships in no wheel,
    and imports the tables package purely for its registration side effect, so the `# noqa: F401` on
    that line is sanctioned and required — block C's template carries it. Delete it and the linter
    deletes the import, and migration autogeneration silently stops seeing the schema.
- **`line-length` is the project's own parameter. The rule is the decision, not the number.** Settle it
  when the project is laid down, **write it in the root `pyproject.toml` explicitly**, and never argue it
  again. A decision invisible in the config has not been made, and a later reader cannot tell a chosen 88
  from an inherited default. **This skill mandates no value**; it mandates that the value is written and
  that it stops being a per-file debate. Two documented options:
  - **88** — the linter's and formatter's default, and the most common value in the wider ecosystem. Pick
    it and every tool, every shared config and every contributor's muscle memory already agrees.
  - **120** — the value **this catalogue's own templates are written to**, and the argument for it is
    greenfield-specific. The signal that argues for a wider limit — signatures and single-line
    explanatory comments colliding with it — cannot be read on an empty tree, because there are no
    signatures and no comments yet; while the reformat cost that argues for staying at 88 is **zero**
    there, there being nothing to reformat. Against that zero stand the recurring cases where 88 makes
    the limit cut the content instead of wrapping it: single-line comments trimmed with a loss of
    meaning, and a port docstring's contract keys dropped. On an established project the same argument
    runs the other way, because the cost is no longer zero.
  The cost of moving is real and measurable, which is why this is a **project-setup decision** and not a
  mid-change one: `line-length` drives the **formatter** as well as the line-length lint rule, so raising
  it reformats the tree, and on a mid-sized project the move from 88 to 120 puts a substantial minority
  of files under reformat. If an established project does move, the reformat travels as its own commit,
  so it cannot hide a behaviour change inside it.
- **The interpreter floor is settled here too, and by the same logic as the line length.** Three
  settings name one interpreter — `requires-python` in `[project]`, the linter's `target-version`, and
  the type checker's `python_version` — and all three name the **oldest** interpreter the project must
  run on. Write them at setup, in the root config, and keep them in step; a linter configured for a
  newer runtime than the deployment one accepts forms that fail there. `python-style` owns the floor
  this catalogue's own forms require (3.10) and what does and does not raise it — including that
  `dishka`, this family's DI binding, needs exactly 3.10 and no more.
- **Type checker config**: strict mode, an explicit `python_version`, and the validation library's plugin
  if it ships one. A third-party package that ships **no type stubs and no `py.typed` marker** gets one
  per-package override block with missing-imports ignored — list every such package the project carries,
  dev dependencies included when the suite imports them. This is the **only** sanctioned way to silence a
  missing-stub error; never an inline ignore comment on a content module.

## C. Relational migration bootstrap (write-once) — Alembic over SQLAlchemy and Postgres

Laid **only when a relational store backs a repository**, the same trigger as the relational substrate
and the first table. The migration tool owns the revision chain, but the chain cannot start — and
`alembic upgrade head` cannot run — without two things: the **config** (pure glue, rewritten freely) and
an **initial baseline revision** (write-once). Without them the integration suite dies at setup with
`No 'script_location' key found`. Nothing in lint, type-check or the unit tier catches that; only a real
run against a database does.

The three config files are complete glue at the tree root and `migrations/`:

```ini
# alembic.ini  (tree root)
[alembic]
script_location = migrations
prepend_sys_path = src
```

```python
# migrations/env.py  — async, wired to the project's shared MetaData, online mode only:
# the app is always migrated against a live connection, and autogenerate also runs online.
import asyncio

from alembic import context

import myapp.infrastructure.postgres.tables  # noqa: F401  — registers every Table on the shared metadata
from myapp.infrastructure.postgres.engine import create_engine
from myapp.infrastructure.postgres.metadata import metadata
from myapp.infrastructure.postgres.settings import DbSettings

target_metadata = metadata


def _run(connection) -> None:  # the migration context drives this inside run_sync
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def _run_online() -> None:
    engine = create_engine(DbSettings())  # DSN from the environment the caller sets
    async with engine.connect() as connection:
        await connection.run_sync(_run)
    await engine.dispose()


asyncio.run(_run_online())
```

`migrations/script.py.mako` is the tool's standard revision template (`${message}` / `${up_revision}` /
`${down_revision}` / `upgrade()` / `downgrade()`); write it verbatim so `alembic revision` can author
later deltas.

The **baseline revision** is **write-once** — create `migrations/versions/0001_initial.py` only when
`migrations/versions/` carries no `*.py` yet. Never clobber a chain that already has deltas:

```python
# migrations/versions/0001_initial.py
"""initial — the foos table

Every column, type and constraint is written out here rather than derived from the shared metadata:
`metadata.create_all` reads the metadata as it stands when the revision RUNS, so replaying this
revision later would build whatever the table has become rather than what it was when this was
written. Schema evolution is versioned from this change onward, which means history stays replayable.
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "foos",
        sa.Column("id", UUID(as_uuid=True), nullable=False),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        # A check constraint's `name` is the SUFFIX: the metadata convention prepends `ck_foos_`; a full name doubles.
        sa.CheckConstraint("char_length(name) > 0", name="name_non_empty"),
    )


def downgrade() -> None:
    op.drop_table("foos")
```

The baseline **freezes** the tables as they stood the day it was written — every column, type and
constraint spelled out by hand, nothing read from the live metadata at run time. It carries no logic
delta; it exists so the chain can start, and being frozen is what keeps the chain replayable from zero.
The revision does not import the project's metadata or its table registrar at all: it needs neither, and
either import would be a false trail back to the derived form.

**Every subsequent migration is a real revision** (`uv run alembic revision --autogenerate -m "<change>"`),
authored when entity fields and table columns drift apart — see `hex-persistence` for the per-change
form.

`migrations/` lives at the tree root, outside `src/` and `tests/`, which puts it inside one of the two
toolchain surfaces and outside the other: the linter runs with no paths and covers it, the type checker
names `src tests` and does not. The two surfaces differ by exactly that one directory — which is why a
formatter count taken over `src tests` alone is not the count the full check produces.

## Other bindings

- **Another package manager.** poetry, pdm or hatch replace the commands and the lock file's format;
  unchanged are the names-only substrate, the SDK-floor discipline and the packaged `src/` layout. One
  thing does move: `[dependency-groups]` is the standard table, and a tool that does not read it keeps
  its own — the obligation is that dev dependencies are declared somewhere the tool installs by default,
  not in a deprecated table nothing reads.
- **Another linter or type checker.** flake8 with its plugin set, or pyright in strict mode: the rule
  codes and the config keys change; the `src`-and-`tests`-at-parity rule, the narrow selection, the
  explicit line length and the two sanctioned suppressions do not. Confirm the replacement still refuses
  a bare `raise` inside `except` and a mutable default argument — those two are why the selection is not
  simply the error family.
- **Another migration tool.** The config file, the revision template and the autogenerate command all
  change; the write-once baseline, the hand-frozen DDL and the mandatory reverse operation do not.

## Rules

1. Select dependencies by block A's substrate and feature triggers; include an SDK only with its adapter.
2. Keep substrate declarations unversioned; justify any SDK floor with the documented breaking boundary.
3. Declare development dependencies in the group table the package manager installs by default, never a
   deprecated tool-specific one, and lay the project down in the packaged `src/` layout from the first
   commit — a flat single-module tree matches nothing else in this style. Under the binding above that
   is `[dependency-groups]` and `uv init --package`.
4. Check the lint and type-check surfaces against block B, including lint's additional migration coverage;
   annotation requirements come from `python-style`.
5. Keep lint selection to the families and two bugbear rules specified in block B; configure the wildcard
   exception per file for the re-export contract in `python-packaging`.
6. Write the line length explicitly in the root config and settle it at setup. **This skill mandates no
   value** — block B documents 88 and 120 with the argument for each, and either is compliant once it is
   written down. On an established tree the change reformats the tree, so it travels as its own commit,
   never inside a feature change.
7. Configure strict type checking, the interpreter floor in all three places block B names (at or
   above `python-style`'s 3.10), the applicable validation plugin and per-package
   missing-stub overrides as specified in block B.
8. Add the complete migration configuration only for a relational store; create the initial baseline
   only while the revision directory is empty.
9. Check baseline DDL against the frozen schema form in block C; use `hex-persistence` for later revisions.

## Hard stops

- A substrate library is being pinned with a version → stop, names only; the lock file owns pins.
- An SDK floor is being written from a recollection of what version is "recent" → stop, a floor states a
  known breaking boundary or it does not exist.
- A feature-triggered package is being added to an app that has no such feature → stop, a dependency
  nothing imports is a stray package.
- An inline lint-ignore or type-ignore comment is being added to a content module → stop, the only
  sanctioned suppressions are the `__init__.py` wildcard per-file ignore and a per-package missing-stub
  override. Alembic's `env.py` is not a content module: its `# noqa: F401` on the tables import is
  sanctioned, and removing it breaks migration autogeneration.
- `line-length` is being left unwritten → stop, write the number; an unwritten decision has not been
  made.
- `line-length` is being changed mid-feature on an established project → stop, it reformats the tree;
  make it its own commit.
- A baseline revision is being written into a `versions/` directory that already holds revisions → stop,
  the chain has already started; author a new revision instead.
- The baseline revision imports the project's metadata or calls `create_all` → stop, it must be frozen
  DDL written by hand, or the chain stops being replayable.
