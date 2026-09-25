---
name: hex-project-setup
description: Use when laying a hexagonal project down once — the `pyproject.toml` dependency substrate by role, the ruff and mypy configuration, and the initial Alembic bootstrap the revision chain cannot start without. Never per feature — the per-change migration revision is `hex-persistence`, runtime DI bindings and settings classes are `hex-wiring`.
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
- Layer boundaries → `hex-architecture`; packaging mechanics → `python-packaging`.
- Module files, `__all__` and the re-export contract inside the package → `python-packaging`.
- The runtime DI bindings and the env-backed settings classes → `hex-wiring`; this skill stops at which libraries exist.
- Whether the project should be hexagonal or flat-layered at all → `architecture-choice`; settle that before laying this down.
- A multi-service uv workspace rather than a single package → `python-workspace`.

## A. Stack substrate (library ROLES, no versions)

`pyproject.toml` carries the core substrate plus whatever each entrypoint package and each
infrastructure adapter needs.

- **Core substrate** (always present, whatever the program is): the settings library, the
  dependency-injection library, and the structured logger. Every hexagonal program reads configuration,
  composes its adapters at one root, and logs — a worker, a batch job and a single-command CLI included.
- **Entrypoint substrate** (whatever the entrypoint packages the project actually has require, and
  nothing else): an HTTP entrypoint brings its web framework, that framework's server, and the
  validation library its wire schemas are written in; a queue or scheduled entrypoint brings its broker
  or scheduler client; a CLI entrypoint brings its argument parser, which may be the standard library
  and therefore nothing at all. A project with no HTTP entrypoint carries no web framework and no
  server — the same trigger rule as a feature extra, applied to the entrypoint layer.
- **Relational bootstrap** (only when a relational store backs a repository): the ORM/Core library with
  its async extra, the async driver, and the migration tool.
- **Feature-triggered extras** — a package required only because some endpoint or adapter uses a specific
  feature. Multipart form handling is the canonical example: a web framework typically imports its
  multipart library at app-construct time for any form route, and without it constructing the app raises
  — which lint, type-check and the unit tier do **not** catch. An app with no such endpoint must not
  carry it.
- **Dev** (always present): the test runner and its async plugin, the linter and the type checker.
  Triggered alongside them: the container library, once an integration tier drives a real backing
  service, and a transport test client for each entrypoint the suite drives over its own transport — an
  HTTP test client belongs to a project with HTTP routes to call.
- **Test-bootstrap extras** follow the same trigger rule as feature extras: a suite that mints
  asymmetric-signature tokens needs the crypto library that generates the keypair; a project verifying
  symmetric or opaque tokens generates no keypair and must **not** carry it. A dev dependency nothing
  imports is a stray package.
- **SDK packages are not listed as substrate** — each rides along with the adapter that needs it.

**No versions in the substrate.** This list carries names only. The lock file is the only home for a
concrete pin, so nothing rots. A pinned `>=` on a substrate library under eternal manual bump is the
disease this avoids. A floor at a known breaking boundary, below, is the one exception.

**Floors — the one exception, and it is the same for an SDK as for a substrate library.** An adapter's
SDK *may* carry a `>=` floor, but only when it marks a **known breaking-version boundary** — an API the code relies on landed or changed
there — with the floor sitting at that boundary, expressed as the major, and the reason in a comment. It
is a *contract* fact ("needs v2, where the API changed"), never a recency guess: do not write a version
you recall as "recent", because that recollection is frozen at a training cutoff, and a floor padded
above the real break is exactly that stale memory masquerading as a constraint. The shape of a good
floor: a library whose 2.0 changed a return type from `bytes` to `str` gets `>=2`; a library whose async
client merged in at 4.2, having been a separate package before, gets `>=4.2`; a library whose API has
been stable for years gets **no floor at all**. Symmetry lives in the *rule*, not in pinning every
library.

**A substrate library takes a floor on the same terms and no others** — only where code the project
carries relies on an API that landed at a known release. Under the bindings here that case is real
twice. The FastAPI one:
the app-invariant and auth-probe tests (`hex-test-app-invariants`, `hex-test-restapi-auth`) walk the
app's resolved operations through `fastapi.routing.iter_route_contexts`, which first ships in 0.137.2,
and from 0.137.0 an included router is a single `_IncludedRouter` entry in `app.routes`, so a walk over
`app.routes` alone no longer reaches the operations. Below 1.0 a release's minor is its breaking segment,
so the floor names the release that shipped the API rather than a major:

```toml
[project]
dependencies = [
    "fastapi>=0.137.2",  # iter_route_contexts, the resolved-route walk the app-invariant tests rely on
]

[dependency-groups]
dev = [
    "pytest-asyncio>=0.26",  # asyncio_default_test_loop_scope, the session loop the integration suite runs on
]
```

The dev one: the integration suite shares one event loop across the session (`hex-test-integration-setup`,
whose `CONFTEST.md` carries the `[tool.pytest.ini_options]` block that sets it), and
`asyncio_default_test_loop_scope`, the key that puts the tests on that loop, first ships in
`pytest-asyncio` 0.26.

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
  - **One kind of file is not a content module: a module outside the packaged tree whose import exists
    for a registration side effect.** It sits outside `src/`, ships in no wheel, and imports a package
    purely so that importing it registers something — so the unused-import suppression on that line is
    sanctioned and required there, and nowhere else. Delete it and the linter deletes the import, and
    whatever the import was registering silently stops being registered. The standing case is the
    migration tool's environment module importing the tables package (`migrations/env.py` under the
    binding in block C, which carries the `# noqa: F401`), where losing it makes autogeneration stop
    seeing the schema.
- **`line-length` is the project's own parameter. The rule is the decision, not the number.** Settle it
  when the project is laid down, **write it in the root `pyproject.toml` explicitly**, and never argue it
  again. A decision invisible in the config has not been made, and a later reader cannot tell a chosen 88
  from an inherited default. **This skill mandates no value**; it mandates that the value is written and
  that it stops being a per-file debate. Two documented options:
  - **88** — the linter's and formatter's default. Pick it and every tool and every shared config already
    agrees.
  - **120** — the value **this catalogue's own templates are written to**, and the argument for it is
    greenfield-specific. The signal that argues for a wider limit — signatures and single-line
    explanatory comments colliding with it — cannot be read on an empty tree, because there are no
    signatures and no comments yet; while the reformat cost that argues for staying at 88 is **zero**
    there, there being nothing to reformat. Against that zero stand the recurring cases where 88 makes
    the limit cut the content instead of wrapping it: single-line comments trimmed with a loss of
    meaning. On an established project the same argument runs the other way, because the cost is no
    longer zero.
  The cost of moving is real, which is why this is a **project-setup decision** and not a mid-change
  one: `line-length` drives the **formatter** as well as the line-length lint rule, so raising it
  reformats the tree. If an established project does move, the reformat travels as its own commit, so it
  cannot hide a behaviour change inside it.
- **The interpreter floor is settled here too, and by the same logic as the line length.** Three
  settings name one interpreter — `requires-python` in `[project]`, the linter's `target-version`, and
  the type checker's `python_version` — and all three name the **oldest** interpreter the project must
  run on. Write them at setup, in the root config, and keep them in step; a linter configured for a
  newer runtime than the deployment one accepts forms that fail there. `python-style` owns the floor —
  **3.13**, the house floor, which a project may raise and never lower — so the three read
  `requires-python = ">=3.13"`, `target-version = "py313"` and `python_version = "3.13"`.
- **Type checker config**: strict mode, an explicit `python_version`, and the validation library's plugin
  if it ships one. Under the pydantic-settings binding (`hex-wiring`) that is `plugins = ["pydantic.mypy"]`,
  and it is not optional: without it strict mode reports every no-argument settings construction in the
  composition root — `DbSettings()` — as a call missing its required fields. A third-party package that ships **no type stubs and no `py.typed` marker** gets one
  per-package override block with missing-imports ignored — list every such package the project carries,
  dev dependencies included when the suite imports them. This is the **only** sanctioned way to silence a
  missing-stub error; never an inline ignore comment on a content module.
- **Package bases for `tests`**: the suite has a `conftest.py` in several directories and no
  `__init__.py` above them, so the checker is told to derive a module's name from its path under the
  source roots (`explicit_package_bases`, with `src` and the tree root as `mypy_path`); without it,
  `mypy src tests` stops at the second `conftest.py` with a duplicate-module error.

### Template — `pyproject.toml` toolchain tables, ruff and mypy

```toml
[tool.ruff]
line-length = 120
target-version = "py313"

[tool.ruff.lint]
select = ["E", "F", "I", "B006", "B904"]

[tool.ruff.lint.per-file-ignores]
"__init__.py" = ["F403", "F405"]

[tool.mypy]
strict = true
python_version = "3.13"
plugins = ["pydantic.mypy"]
explicit_package_bases = true
mypy_path = ["src", "."]
```

`B006` is the mutable-default-argument rule and `B904` the raise-without-from rule; `F403` and `F405` are
the two wildcard-import warnings. A package the project carries that ships no stubs adds one block,
`[[tool.mypy.overrides]]` with `module = ["<package>", "<package>.*"]` and
`ignore_missing_imports = true`.

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
# migrations/env.py  — async, online mode only: the app is always migrated against a live connection.
import asyncio

from alembic import context
from sqlalchemy import Connection

import myapp.infrastructure.postgres.tables  # noqa: F401  — registers every Table on the shared metadata
from myapp.infrastructure.postgres import DbSettings, create_engine
from myapp.infrastructure.postgres.metadata import metadata

target_metadata = metadata


def _run(connection: Connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def _run_online() -> None:
    engine = create_engine(DbSettings())  # env.py is a composition root (hex-wiring settings rule 13)
    async with engine.connect() as connection:
        await connection.run_sync(_run)
    await engine.dispose()


asyncio.run(_run_online())
```

`migrations/script.py.mako` is the tool's standard revision template (`${message}` / `${up_revision}` /
`${down_revision}` / `upgrade()` / `downgrade()`); write it verbatim so `alembic revision` can author
later deltas.

The **baseline revision** is **write-once** — create `migrations/versions/0001_baseline.py` only when
`migrations/versions/` carries no `*.py` yet. Never clobber a chain that already has deltas:

```python
# migrations/versions/0001_baseline.py
"""baseline — the root of the revision chain"""

from collections.abc import Sequence

revision: str = "0001"
down_revision: str | None = None
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
```

**On a greenfield project the baseline is empty.** It exists so the chain has a root, and it holds no
table: the first table the project adds is its own revision, autogenerated and then reviewed like every
later one (`hex-persistence` rule 12), so there is exactly one way a table enters the schema. **On a
database that already holds objects**, the baseline holds only those pre-existing objects, and it
**freezes** them as they stood the day it was written — every column, type and constraint spelled out by
hand, nothing read from the live metadata at run time, because `metadata.create_all` would build whatever
the tables have become by the time the revision runs, and the chain would stop being replayable from
zero. Either way the baseline imports neither the project's metadata nor its table registrar.

**Every subsequent migration is a real revision** (`uv run alembic revision --autogenerate -m "<change>"`)
— see `hex-persistence` for the per-change form.

`migrations/` lives at the tree root, outside `src/` and `tests/`, which puts it inside one of the two
toolchain surfaces and outside the other: the linter runs with no paths and covers it, the type checker
names `src tests` and does not.

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
  change; the write-once baseline — empty on a greenfield project, hand-frozen DDL over a database that
  already holds objects — and the mandatory reverse operation do not.

## Rules

1. Select dependencies by block A's core substrate plus its entrypoint, store and feature triggers;
   include an SDK only with its adapter.
2. Keep substrate declarations unversioned; justify any floor — an SDK's, or a substrate library's under
   block A's same terms — with the documented breaking boundary.
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
   above `python-style`'s 3.13), the applicable validation plugin and per-package
   missing-stub overrides as specified in block B.
8. Add the complete migration configuration only for a relational store; create the initial baseline
   only while the revision directory is empty.
9. Keep the baseline empty on a greenfield project and frozen hand-written DDL of pre-existing objects
   otherwise (block C); every table the project adds is its own revision under `hex-persistence`.

## Hard stops

- A substrate library is being pinned with a version → stop, names only; the lock file owns pins, and a
  floor is written only at a known breaking boundary (block A).
- A floor is being written from a recollection of what version is "recent" → stop, a floor states a
  known breaking boundary or it does not exist.
- A feature-triggered package is being added to an app that has no such feature → stop, a dependency
  nothing imports is a stray package.
- An inline lint-ignore or type-ignore comment is being added to a content module → stop, the only
  sanctioned suppressions are the `__init__.py` wildcard per-file ignore and a per-package missing-stub
  override. A registration-side-effect import on a non-content module outside the packaged tree is the
  one exception — the migration tool's environment module is that case (`migrations/env.py` under
  Alembic), where removing the suppression breaks migration autogeneration.
- `line-length` is being left unwritten → stop, write the number; an unwritten decision has not been
  made.
- `line-length` is being changed mid-feature on an established project → stop, it reformats the tree;
  make it its own commit.
- A baseline revision is being written into a `versions/` directory that already holds revisions → stop,
  the chain has already started; author a new revision instead.
- The baseline revision imports the project's metadata or calls `create_all` → stop, it must be frozen
  DDL written by hand, or the chain stops being replayable.
- A table the project is adding is being written into the baseline → stop, the baseline holds only what
  already existed; the new table is its own autogenerated, reviewed revision (`hex-persistence`).
