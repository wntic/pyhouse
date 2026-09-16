---
name: flat-monorepo
description: Use when several flat-layered services live in one repository — creating the workspace root, or admitting a member to it. Covers the root project as a container with no runtime code of its own, the shared-library versus runnable-service member split, the two-sentence admission test a new member passes, in-repo dependency edges the packaging tool resolves rather than path hacks, tooling values settled once at the root, one container profile per service, and the task-runner targets that sync every member, apply migrations and launch each service from its own directory. One service on its own needs none of this and stays on `flat-layered`; what the package owning a shared store contains is `flat-persistence`.
when_to_use: Also when asked for a monorepo, a uv workspace, a `packages/` and `services/` layout, a root `Makefile` target, or a `docker compose` profile per service.
paths: ["**/packages/**", "**/services/**"]
---

# Flat-Layered Monorepo — uv workspace root

One-shot bootstrap for a repository holding several `flat-layered` services plus the shared library
packages they all depend on. Run once per repository; adding the Nth service afterward is just a new
`services/<name>/` package, not a re-run of this skeleton.

## When to use vs. neighbours

- The architecture family of the services going into the workspace is not settled →
  `architecture-choice` decides hexagonal versus flat per service; this skill assumes flat-layered
  members.
- Adding the shared `Table` definitions, engine, and bulk-write helpers → not this skill, use
  `flat-persistence` — this skill only creates the empty `packages/myschema/` shell.
- Adding one service's internal role-package layout — cross-cutting setup, clients, run functions;
  `core/`, `services/`, `ingest/`, `jobs/` in `flat-layered`'s worked example → not this skill, use
  `flat-layered`.
- Choosing a service's trigger — a loop, a cron entry or a timer by default, durable execution only
  once it is earned → `flat-entrypoint`.
- Building a single standalone service with no sibling services and no shared store → not this skill;
  a plain `flat-layered` project needs no workspace root at all. `flat-layered` lays its package
  skeleton, including the storage role, and `flat-persistence` states what that package holds — neither
  assumes anything above the service.
- Bootstrapping one hexagonal project's dependency substrate and tool configuration → the other
  family's `hex-project-setup`, in the `pyhouse-hex` plugin. Nothing below needs it: the tooling
  values this root settles are stated here, and the interpreter floor behind them is
  `python-style`'s.
- The `myschema_testing` pytest plugin module the root `addopts` loads, and the fixtures inside it →
  `flat-test-integration-setup`.
- Whether a proposed member is a boundary at all — its encapsulated knowledge and change vectors →
  `coupling`.
- The workspace-wide grep firewall in `tests/test_architecture.py` → `test-architecture-rule`.

## Template — uv workspace, Docker Compose and Make

```
myrepo/
├── pyproject.toml            # workspace container + shared tooling config; NO runtime code
├── Makefile
├── docker/
│   ├── local.compose.yaml    # development — what every make target drives
│   └── compose.yaml          # deployment template — registry images, resource limits
├── tests/
│   └── test_architecture.py  # workspace-wide grep firewall
├── packages/
│   ├── myschema/             # the shared storage package — see flat-persistence
│   └── shared/               # cross-cutting helpers with no schema of their own
└── services/
    ├── foo_parser/
    └── bar_parser/
```

**Two shared packages, with a sharp line between them.** `myschema` owns the schema: tables,
migrations, repositories, the engine. `shared` owns everything cross-cutting that is *not* schema —
logging setup, framework-guarded helpers, common settings base classes. The split matters because
`myschema` pulls in the database driver and the migration tool, and a service that only wants the
logging setup should not inherit those. A repository with nothing cross-cutting yet has no `shared`
package; add it when the second service copies the same helper.

**The datastore fixtures every member shares are not at the root.** They live in a pytest plugin module
beside the schema package's own tests, `packages/myschema/tests/myschema_testing.py`, loaded workspace-wide
from the root `pyproject.toml` with `addopts = "-p myschema_testing"` and
`pythonpath = ["packages/myschema/tests"]`. A plugin is registered once per session, so every member
shares one container. `flat-test-integration-setup` owns the module and the settings that load it.

Root `pyproject.toml`:

```toml
[project]
name = "myrepo"
version = "0.1.0"
requires-python = ">=3.12"

[tool.uv.workspace]
members = ["packages/*", "services/*"]

[tool.ruff]
line-length = 120
target-version = "py312"

[tool.pytest.ini_options]
asyncio_mode = "auto"
testpaths = ["packages", "services", "tests"]

[dependency-groups]
dev = ["ruff", "mypy", "pytest", "pytest-asyncio", "testcontainers"]
```

The root project is a **workspace container plus shared tooling config, with no runtime code of its
own**. Nothing importable lives at the root; every line of shipped code sits inside a member.

**The tooling values above are the project's to choose; what the workspace fixes is that they are chosen
once, at the root, and inherited.** A member never restates them — a second `line-length` in a member's
`pyproject.toml` is how two halves of one workspace start disagreeing about what a diff should look like.
`line-length = 120` is the value this catalogue's templates are written to; **88** is the linter's and
the wider ecosystem's default, and the argument between them turns on whether there is an existing
tree to reformat. Pick either, write it at the root, and stop arguing. The interpreter floor is the
same kind of decision, and `python-style` owns it: **3.10** is what this catalogue's own Python forms
require, and a workspace may sit higher. Whatever it picks, three settings name that one oldest
supported interpreter and stay in step — `requires-python` here, `target-version` under the linter, and
`python_version` under the type checker. The `>=3.12` and `py312` in the templates above are one
workspace's choice shown whole, not a requirement.

Each member's `pyproject.toml` declares its workspace dependencies explicitly:

```toml
# services/foo_parser/pyproject.toml
[project]
name = "foo-parser"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["myschema", "shared"]

[tool.uv.sources]
myschema = { workspace = true }
shared = { workspace = true }

[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"
```

`docker/local.compose.yaml`:

```yaml
name: myrepo

services:
  postgres:
    image: postgres:17-alpine
    profiles: ["postgres", "foo-parser", "bar-parser"]
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

**One compose profile per service**, named after the service, and each service profile also pulls in
the datastores it depends on. That is what makes `--profile foo-parser` bring up exactly what one
service needs and nothing else.

`Makefile`:

```makefile
.PHONY: help install lint fmt typecheck test verify migrate run-foo run-bar

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

run-foo:
	cd services/foo_parser && uv run python -m foo_parser
```

Two details in there are load-bearing. `uv sync --all-packages` is needed because a bare `uv sync`
syncs only the root project and leaves every member's dependencies uninstalled. And `run-*` targets
`cd` into the service directory first: a service's settings and the schema package's settings both
resolve their dotenv files relative to the process working directory, so a service launched from the
repo root reads none of them.

## Other bindings

- **Another workspace tool in place of uv.** Poetry path dependencies, PDM local sources, Pants and
  Bazel all express the same two things: the member list declared once at the root, and each member
  pinning its in-repo dependencies through an edge the tool itself resolves. The member-glob syntax,
  the lock file and the sync command change; rules 1–9 do not. Rule 5 is the one to carry over
  literally — whatever the tool, the edge is *declared*, never faked with a path insert.
- **Another task runner in place of Make, another container runtime in place of Compose.** `just`,
  `invoke` and `nox` give the same one-discoverable-command-set-at-the-root property; a dev Kubernetes
  cluster or Tilt gives the same per-service profile. What must survive either swap: one command syncs
  *every* member and not only the root, one command applies migrations, each service still starts from
  its own directory, and a cleanup command names what it destroys instead of sweeping the project.

## Rules

1. **One workspace, two member groups.** `packages/*` holds shared libraries with no entrypoint of
   their own; `services/*` holds runnable services, one directory per worker. Never put runnable code
   in `packages/` or shared library code in `services/`.
2. **A new member is admitted with two sentences, not just a directory.** Before creating
   `services/<name>/` (or a new `packages/` member), the change that adds it names the member's
   **encapsulated knowledge** — the tables it owns, the upstream it speaks, the vocabulary it
   defines, none of which another member may assume — and two or three **change vectors**: plausible
   changes that would touch *only* this member. A member whose knowledge cannot be named is a
   category word, not a boundary; one whose every change vector drags a sibling along is drawn in
   the wrong place. The reasoning is `coupling`'s; the check costs two sentences and is the cheapest
   boundary test available.
3. **The package owning a shared store is a `packages/*` member, and no `services/*` member defines a
   table.** That one package owns the schema and the migration history for the store its services share —
   the obligation itself is `flat-persistence`'s, and this rule is its workspace half: the owner sits in
   `packages/`, every service declares an edge to it, and a grep firewall enforces that no service
   constructs a statement of its own (`test-architecture-rule`).
4. **The one migration command runs from where the schema is defined** — `make migrate` here, which
   `cd`s into the owning package. That there is one history per store, applied by one command, is
   `flat-persistence`'s obligation; what this rule adds is workspace-specific and is a property of
   members, not of storage: a migration run from inside a *service* resolves its connection settings from
   that service's environment and working directory, so two services can apply one migration history to
   two different databases and neither of them notices.
5. **A member declares its in-repo dependencies as edges the packaging tool resolves** —
   `[tool.uv.sources]` under uv — never a path hack, a `sys.path` append, or a copy-pasted module. A
   dependency the packaging tool cannot see is one the installer, the type checker and CI each resolve
   differently, and the disagreement surfaces as an import error on somebody else's machine.
6. **Tooling values are settled once at the root and inherited, never re-argued in a member.** Line
   length, the interpreter floor, the lint target, the test-runner configuration: the *values* are the
   project's to choose, and what the workspace fixes is that they live in one file. A member overrides
   one only for a genuine per-package exception, and never the test-runner's own configuration block —
   declaring it in a member moves the runner's rootdir and silently invalidates every root-relative
   path in the test setup (`flat-test-integration-setup`).
7. **Services never import each other.** Two services needing the same code means that code belongs in
   `packages/shared` (or `packages/myschema` if it touches the schema). A service-to-service import is
   what turns a workspace of independent deployables into one program.
8. **Each service is launched from its own directory** — `cd services/<svc> && uv run python -m <svc>`,
   which is what `make run-<svc>` does. Both a service's settings and the shared schema package's
   resolve their env files against the process working directory, so a service started from the repo
   root silently reads none of them. Migrations and syncs have no such restriction.
9. **Infrastructure with its own schema owner gets its own datastore.** A workflow engine, a metrics
   store or a queue that ships its own migration tool does not share the application's database: the
   two have opposite workload profiles and different backup value, and the split means no maintenance
   command aimed at one can reach the other's data. Give it a separate compose service and a
   separately named volume, and never clean up with `compose down -v`, which drops every volume in the
   project.

## Hard stops

- Only one service will ever exist, or services do not share a datastore → stop, this is a single
  `flat-layered` project and it needs no workspace root; `flat-layered` lays its packages and
  `flat-persistence` its storage package.
- A new member is being created and its encapsulated knowledge cannot be named in one sentence →
  stop; write the two sentences first (`coupling`) — the boundary, not the directory, is what needs
  to exist.
- A service needs its own private tables no other service touches → still put the `Table` in the one
  owning package; a second schema owner over one store means two migration histories and the second to
  run decides what the first one's tables look like (`flat-persistence`).
- A service imports a sibling service → stop, promote the shared code into `packages/`.
- Runtime code is being added to the root `pyproject.toml`'s project → stop, the root is a container;
  create a member for it.
- A cleanup target runs `docker compose down -v` → stop, name the one volume to remove; `-v` drops
  every volume in the project, application data included.
