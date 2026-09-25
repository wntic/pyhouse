---
name: python-workspace
description: Use when several Python distributions live in one repository — creating the workspace root, or admitting a member to it. Covers the root project as a container with no runtime code of its own, the shared-library versus runnable-member split, the two-sentence admission test a new member passes, in-repo dependency edges the packaging tool resolves rather than path hacks, tooling values settled once at the root, one container profile per runnable member, and the task-runner targets that sync every member, apply migrations where members share a store, and launch each member from its own directory. Everything here is about members, never about what is inside one, so a member of any internal layout needs the same root. One distribution on its own needs none of it; a member's own layout and data access belong to that member's architecture skills, and whether a proposed member is a boundary at all is `coupling`.
when_to_use: Also when asked for a monorepo, a uv workspace, a `packages/` and `services/` layout, a root `Makefile` target, or a `docker compose` profile per runnable member.
---

# Workspace — the root for several distributions in one repository

One-shot bootstrap for a repository holding several distributions: the runnable ones plus the library
packages they depend on. Run once per repository; adding the Nth member afterward is just a new member
directory, not a re-run of this skeleton.

**The rules below are about members, not about what is inside one.** A member's own internal layout is
its architecture's business — `hex-architecture`, in the `pyhouse-hex` plugin, for a hexagonal member;
`flat-layered`, in the `pyhouse-flat` plugin, for a flat one — and this root is the same either way.

## When to use vs. neighbours

- The architecture family of the members going into the workspace is not settled →
  `architecture-choice` decides hexagonal versus flat per distribution; nothing here depends on the
  answer.
- Adding the shared `Table` definitions, engine, and bulk-write helpers → not this skill; what a
  storage package holds is the member family's own persistence skill. This skill only creates the empty
  `packages/myschema/` shell.
- Adding one member's internal layout — its layer or role packages, its clients, its work units → not
  this skill, use that member's architecture skill.
- Choosing a member's trigger — a loop, a cron entry or a timer by default, durable execution only once
  it is earned → the member family's entrypoint skill (`flat-entrypoint`, in the `pyhouse-flat`
  plugin, is one).
- Bootstrapping one member's dependency substrate and tool configuration → the member family's setup
  skill (`hex-project-setup`, in the `pyhouse-hex` plugin, is one). Nothing below needs it: the tooling
  values this root settles are stated here, and the interpreter floor behind them is `python-style`'s.
- The pytest plugin module the root `addopts` loads, and the fixtures inside it → the member family's
  integration-setup skill (`flat-test-integration-setup`, in the `pyhouse-flat` plugin, or
  `hex-test-integration-setup`, in `pyhouse-hex`).
- Building a single standalone distribution with no siblings and no shared store → not this skill; it
  needs no workspace root at all. Its own architecture skill lays its package skeleton, including the
  data-access role — neither assumes anything above the distribution.
- Whether a proposed member is a boundary at all — its encapsulated knowledge and change vectors →
  `coupling`.
- The repository-wide grep firewall in `tests/test_architecture.py` → `test-architecture-rule`.

## Template — uv workspace, Docker Compose and Make

```
myrepo/
├── pyproject.toml            # workspace container + shared tooling config; NO runtime code
├── Makefile
├── docker/
│   ├── local.compose.yaml    # development — what every make target drives
│   └── compose.yaml          # deployment template — registry images, resource limits
├── tests/
│   └── test_architecture.py  # repository-wide grep firewall
├── packages/
│   └── myschema/             # a library the runnable members depend on
└── services/
    ├── myapp/                # one runnable distribution per directory
    └── <second-service>/
```

**A library that drags a heavy dependency in is not the same member as one that does not.** A library
owning the schema pulls in the database driver and the migration tool; a member that only wants the
logging setup should not inherit those. When the second cross-cutting helper appears, that is the signal
for a second `packages/` member, not a bigger first one — and a repository with nothing cross-cutting yet
has only the one.

**Where members share a datastore, its fixtures are not at the root.** They live in a pytest plugin
module beside the owning library's own tests, `packages/myschema/tests/myschema_testing.py`, loaded
repository-wide from the root `pyproject.toml` with `-p myschema_testing` in `addopts` and
`pythonpath = ["packages/myschema/tests"]`. A plugin is registered once per session, so every member
shares one container. What goes inside that module is the member family's integration-setup skill's;
what this root owns is the two settings that load it.

The templates below show the workspace whose members share a store, because it is the one with the
most to write down. **A workspace whose members share no store drops every line that serves it** — the
`-p` option and `pythonpath` in the test configuration, the datastore service in the compose file, and
the `migrate` target — and everything else stands unchanged.

Root `pyproject.toml`:

```toml
[project]
name = "myrepo"
version = "0.1.0"
requires-python = ">=3.13"

[tool.uv.workspace]
members = ["packages/*", "services/*"]

[tool.ruff]
line-length = 120
target-version = "py313"

[tool.mypy]
python_version = "3.13"
strict = true

[tool.pytest.ini_options]
addopts = "--import-mode=importlib -p myschema_testing"
pythonpath = ["packages/myschema/tests"]
testpaths = ["packages", "services", "tests"]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "session"
asyncio_default_test_loop_scope = "session"
filterwarnings = ["error"]

[dependency-groups]
dev = ["ruff", "mypy", "pytest", "pytest-asyncio", "testcontainers"]
```

The test configuration is whole here and nowhere else (rule 6). `--import-mode=importlib` is what lets
two members each keep a `test_exceptions.py` without a collision; the two session loop scopes let every
test share the session-scoped engine the shared plugin opens; `filterwarnings = ["error"]` is
`test-principles`' rule that a warning fails the run. Each of those is owned where it is explained —
this root only has to carry all of them at once.

The root project is a **workspace container plus shared tooling config, with no runtime code of its
own**. Nothing importable lives at the root; every line of shipped code sits inside a member.

**The tooling values above are the project's to choose; what the workspace fixes is that they are chosen
once, at the root, and inherited.** A member never restates them — a second `line-length` in a member's
`pyproject.toml` is how two halves of one workspace start disagreeing about what a diff should look like.
`line-length = 120` is the value this catalogue's templates are written to; **88** is the linter's and
the wider ecosystem's default, and the argument between them turns on whether there is an existing
tree to reformat. Pick either, write it at the root, and stop arguing. The interpreter floor is
settled at the root the same way, and `python-style` owns it: the house floor is 3.13, a workspace may
raise it and never lower it, and the three settings that name it — `requires-python`, the linter's
`target-version` and the type checker's `python_version` — stay in step here and nowhere else.

Each member's `pyproject.toml` declares its workspace dependencies explicitly:

```toml
# services/myapp/pyproject.toml
[project]
name = "myapp"
version = "0.1.0"
dependencies = ["myschema"]

[tool.uv.sources]
myschema = { workspace = true }

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

The member carries no `requires-python` and no tool configuration of its own: the root settles both,
and a member that restates the floor is the first half of a workspace that disagrees with itself
(rule 6).

`docker/local.compose.yaml`, with the datastore the members share:

```yaml
name: myrepo

services:
  postgres:
    image: postgres:17-alpine
    profiles: ["postgres", "myapp", "second-service"]
    environment:
      POSTGRES_USER: myrepo
      POSTGRES_PASSWORD: myrepo
      POSTGRES_DB: myrepo
    ports: ["127.0.0.1:5432:5432"]
    volumes: ["pgdata:/var/lib/postgresql/data"]

volumes:
  pgdata:
```

**Pin `name:` explicitly.** Without it compose names the project after the directory holding the
file — `docker/` — and every volume is recreated under a new prefix the first time someone runs it
from a different path.

**One compose profile per runnable member**, named after the member, and each such profile also pulls in
the datastores it depends on. That is what makes `--profile myapp` bring up exactly what one member needs
and nothing else.

`Makefile`:

```makefile
.PHONY: help install lint fmt typecheck test verify migrate run-myapp

help:  ## list targets
	@grep -E '^[a-z-]+:.*?## ' $(MAKEFILE_LIST) | sed 's/:.*## /\t/'

install:  ## sync the whole workspace (bare `uv sync` only syncs the root project)
	uv sync --all-packages

lint:
	uv run ruff check packages/ services/ tests/

fmt:
	uv run ruff check --fix packages/ services/ tests/
	uv run ruff format packages/ services/ tests/

typecheck:
	uv run mypy packages/ services/ tests/

test:
	uv run pytest

verify: lint typecheck test  ## run before pushing

migrate:  ## the ONLY sanctioned way schema changes reach a database
	cd packages/myschema && uv run alembic upgrade head

run-myapp:
	cd services/myapp && uv run python -m myapp
```

Two details in there are load-bearing. `uv sync --all-packages` is needed because a bare `uv sync`
syncs only the root project and leaves every member's dependencies uninstalled. And `run-*` targets
`cd` into the member directory first: a member's settings and the shared library's settings both
resolve their dotenv files relative to the process working directory, so a member launched from the
repo root reads none of them.

## Other bindings

- **Another workspace tool in place of uv.** Poetry path dependencies, PDM local sources, Pants and
  Bazel all express the same two things: the member list declared once at the root, and each member
  pinning its in-repo dependencies through an edge the tool itself resolves. The member-glob syntax,
  the lock file and the sync command change; rules 1–9 do not. Rule 5 is the one to carry over
  literally — whatever the tool, the edge is *declared*, never faked with a path insert.
- **Another task runner in place of Make, another container runtime in place of Compose.** `just`,
  `invoke` and `nox` give the same one-discoverable-command-set-at-the-root property; a dev Kubernetes
  cluster or Tilt gives the same per-member profile. What must survive either swap: one command syncs
  *every* member and not only the root, each runnable member still starts from its own directory, one
  command applies migrations wherever members share a store, and a cleanup command names what it
  destroys instead of sweeping the project.

## Rules

1. **One workspace, two member groups.** One group holds libraries with no entrypoint of their own;
   the other holds runnable distributions, one directory per deployable. `packages/*` and `services/*`
   are this example's names for them. Never put runnable code in the library group or shared library
   code in the runnable one.
2. **A new member is admitted with two sentences, not just a directory.** Before creating the
   directory, the change that adds it names the member's **encapsulated knowledge** — the tables it
   owns, the upstream it speaks, the vocabulary it defines, none of which another member may assume —
   and two or three **change vectors**: plausible changes that would touch *only* this member. A member
   whose knowledge cannot be named is a category word, not a boundary; one whose every change vector
   drags a sibling along is drawn in the wrong place. The reasoning is `coupling`'s; the check costs two
   sentences and is the cheapest boundary test available.
3. **Exactly one member owns a shared store's schema and its migration history, and it is a library
   member.** Two members defining tables over one store means two migration histories over one schema,
   and the second one to run decides what the first one's tables look like. So the owner sits in the
   library group, every dependant declares an edge to it, and a grep firewall enforces that no runnable
   member constructs a statement of its own (`test-architecture-rule`). The flat family states the
   same ownership obligation from a member's side, under `flat-persistence`, in the `pyhouse-flat`
   plugin.
4. **One migration history per store is applied by one command, and that command runs from the member
   that defines the schema** — `make migrate` here, which `cd`s into the owning member. What makes the
   working directory load-bearing is a property of members, not of storage: a migration run from inside
   a *dependant* resolves its connection settings from that member's environment and working directory,
   so two members can apply one migration history to two different databases and neither of them
   notices.
5. **A member declares its in-repo dependencies as edges the packaging tool resolves** —
   `[tool.uv.sources]` under uv — never a path hack, a `sys.path` append, or a copy-pasted module. A
   dependency the packaging tool cannot see is one the installer, the type checker and CI each resolve
   differently, and the disagreement surfaces as an import error on somebody else's machine.
6. **Tooling values are settled once at the root and inherited, never re-argued in a member.** Line
   length, the interpreter floor, the lint target, the test-runner configuration: the *values* are the
   project's to choose, and what the workspace fixes is that they live in one file. A member overrides
   one only for a genuine per-package exception, and never the test-runner's own configuration block —
   declaring it in a member moves the runner's rootdir down to that member, and every root-relative
   path the test configuration carries then resolves against a directory nobody wrote it for.
7. **Runnable members never import each other.** Two of them needing the same code means that code
   belongs in a library member. A deployable-to-deployable import is what turns a workspace of
   independent deployables into one program.
8. **Each runnable member is launched from its own directory** — `cd services/<member> && uv run python
   -m <member>`, which is what `make run-<member>` does. Both a member's settings and a shared library's
   resolve their env files against the process working directory, so a member started from the repo
   root silently reads none of them. Migrations and syncs have no such restriction.
9. **Infrastructure with its own schema owner gets its own datastore.** A workflow engine, a metrics
   store or a queue that ships its own migration tool does not share the application's database: the
   two have opposite workload profiles and different backup value, and the split means no maintenance
   command aimed at one can reach the other's data. Give it a separate compose service and a
   separately named volume, and never clean up with `compose down -v`, which drops every volume in the
   project.

## Hard stops

- Only one distribution will ever exist → stop, this is a single-distribution project and it needs no
  workspace root; its own architecture skills lay its packages and its data access. Sharing a datastore
  is one reason members end up in one repository, not the test of whether they belong there — a
  repository of libraries and CLIs that share no store needs every rule here except the ones about a
  schema owner.
- A new member is being created and its encapsulated knowledge cannot be named in one sentence →
  stop; write the two sentences first (`coupling`) — the boundary, not the directory, is what needs
  to exist.
- A runnable member needs its own private tables in the store the members share → stop, put the
  `Table` in the one owning library; a second schema owner over one store means two migration
  histories, and the second to run decides what the first one's tables look like.
- A runnable member imports a sibling runnable member → stop, promote the shared code into a library
  member.
- Runtime code is being added to the root `pyproject.toml`'s project → stop, the root is a container;
  create a member for it.
- A cleanup target runs `docker compose down -v` → stop, name the one volume to remove; `-v` drops
  every volume in the project, application data included.
