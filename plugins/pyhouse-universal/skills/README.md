# House-style skills

49 skills: 47 project-neutral Python skills in seven families — Universal (15), Meta (1), Hex core
(11), Hex REST API (4), Hex tests (8), Flat core (4), Flat tests (4) — and two language-independent
Git skills.

Worked examples use `myapp`, `myschema`, `myrepo`, `foos`/`bars`, and `Foo`/`Bar` (with `Baz` where an example needs a third aggregate, and `Qux` for an external system). The directory names
in the flat-layered example are roles you rename, not vocabulary you copy — see
**Adapting to a project**.
Technology names (`postgres`, `redis`, `jwt`, `s3`) stay concrete, because the
folder-per-technology rule is meaningless with the technology abstracted away.

Add the `pyhouse` marketplace and install the plugin you need; each one lives under `plugins/` in this
repository:

| Plugin | Directory | Skills |
|---|---|---|
| `pyhouse-universal` | `plugins/pyhouse-universal/` | the 15 universal + `meta-skill-author`, the `/choose-architecture`, `/pyhouse-universal:code-review` and `/pyhouse-universal:adopt` commands |
| `pyhouse-hex` | `plugins/pyhouse-hex/` | the 23 `hex-*` |
| `pyhouse-flat` | `plugins/pyhouse-flat/` | the 8 `flat-*` |
| `pyhouse-git` | `plugins/pyhouse-git/` | the 2 `git-*`, the `/commit`, `/release`, `/pyhouse-git:adopt` and `/install-commit-hook` commands |

Installing `pyhouse-hex` or `pyhouse-flat` brings `pyhouse-universal` with it. To carry a family
everywhere without the marketplace, copy that plugin's `skills/` **and** `pyhouse-universal/skills/`
into a project's `.claude/skills/` or into `~/.claude/skills/`; copying carries the skills only, not
`/choose-architecture`, `/pyhouse-universal:code-review`, `/pyhouse-universal:adopt` or the reviewer subagent. **This index ships inside `pyhouse-universal`, so every install has it** — and
it lists the whole catalogue, including the skills of a family plugin that is not installed.

## How the catalogue fits together

**The two architecture families are mutually exclusive.** A service is hexagonal (`hex-*`) or
flat-layered (`flat-*`); no service is both. **The universal skills bind either way** — they govern
names, Python forms, packaging, settings, the toolchain, errors, data access, boundaries and testing whichever family a project chose. The
architecture chooser, **`architecture-choice`**, picks between the two families for a greenfield
service — and says when neither of them applies — a project too small to need one, or a shape the
catalogue does not cover. It is itself universal, because it is what you consult before you know
which family you are in, and the `/choose-architecture` command walks it one question at a time.

**The catalogue ships as four plugins** on the Claude Code marketplace: `pyhouse-universal` (the
unprefixed skills, `meta-skill-author`, the chooser), `pyhouse-hex` and `pyhouse-flat` for Python
house style, and `pyhouse-git`, which ships beside them for repository workflow rather than Python house style; it depends on
nothing, nothing depends on it, and it holds in a repository of any language. Both family
plugins depend on `pyhouse-universal`, which Claude Code enables transitively, so installing one family
always brings the universal skills with it. `pyhouse-universal` is installable alone: a universal skill
may *name* a family skill as an example but never require one.

Frontmatter and description rules — including the real length limits — are owned by
`meta-skill-author`. There is **no total description budget** across the catalogue, and no per-skill
character cap: `description` has no documented maximum, `description` + `when_to_use` truncate at
**1,536 characters combined**, and length is spent where it buys disambiguation. Descriptions are
rewritten as complete sentences to fit, never truncated.

## Universal (15) — always in play

These skills bind in **every** project in this style, whichever architecture it uses. They are
unprefixed because they belong to neither architecture family. `architecture-choice` is the one read
once rather than throughout — before the family is known:

| Skill | Owns |
|---|---|
| `architecture-choice` | **Which family a service belongs to** — the question that decides it, the confirming evidence, what each choice costs, the projects too small for either family, and the shapes this catalogue does not cover |
| `naming` | **What anything is called** — the derivation procedure, the six tests, kind-by-kind rules (incl. protocol, error-class and repository-class forms — `Repository` whether or not a port stands in front), the vague-noun families and the role suffixes an architecture defines, renaming |
| `coupling` | Where boundaries go and what may cross them — split vs merge, contract vs shared knowledge, the three coupling dimensions, the balance rule, design effort by volatility |
| `python-style` | The 3.13 house floor, typing forms, `type` aliases, `collections.abc`, the `from __future__` ban, declared record types over bare `dict`s, which builtin holds which kind of scalar, closed constant sets as an `Enum`, comments |
| `python-logging` | One structured event per occurrence with a stable name and identifiers as fields, the levels, which scope logs an error and the warning a failed undo earns, logging configured once at the entry point and never by a distributed package, what never reaches a log line, a program's stdout result as output rather than a log, and a program whose stdout is its result logging to stderr |
| `python-packaging` | Whether a module wants a class at all, the one-class cap and the test for when a closed set of declarations shares a module, framework-dictated modules, `__all__`, the `__init__.py` re-export contract, import rules, a library's `py.typed` marker |
| `python-settings` | **Configuration read from the environment** — one settings class per configured component, its non-strict namespace, no default on a required field, a secret or a tunable, the secret type and where it is unwrapped, derived values, validation that only normalizes or rejects, construction at the composition root, and a published library that reads nothing |
| `python-toolchain` | **What every distribution configures once** — the src layout, the lint selection with written function-size and complexity thresholds, the sanctioned suppressions, strict type checking over `src` and `tests`, the line length, the test runner's configuration block, development dependencies by role, a version floor only at a named break, and every hand-written version read from its source, never recalled |
| `python-workspace` | The repository root when several distributions share one — the member split, in-repository dependency edges, tooling settled once, compose profiles and task-runner targets; about members, never about what is inside one |
| `python-container-image` | **The image a runnable program ships in** — a runtime stage carrying only the installed environment, exactly what the lock pins with the build failing on drift, one interpreter for build and runtime, a non-root user named by number, no secret in any layer, an allow-list build context, one image per runnable distribution and for every environment, unbuffered output, a server reachable from outside the container, and a stop signal the process acts on |
| `python-versioning` | **What the version promises and what changes it** — whether it is a compatibility claim or only a label, the single declaration, which change forces which segment, what `0.y.z` withholds, the tag and the note |
| `persistence` | **The store-generic data-access obligations**, whatever the family — which of them bind given the store's properties, one declared transaction owner and none across two stores, driver errors translated at the data-access edge by one shared translator, the field and the full constraint name in the context, one constraint-naming convention and one table-name rule, the pure row mapping, stored types, closed sets and indexes, no schema created at runtime, explicit conflicts, an older write never replacing a newer one, deduplication left to the store, a batched write one statement per chunk sized under the store's limit, paged reads over a total order, migrations that run once before the new code and reverse, and no logging |
| `exception-catalog` | The single error-catalog file, translation of library exceptions at the boundary, swallowing versus stopping a failure, best-effort compensation, and a failure after a committed write stopped rather than re-raised |
| `test-principles` | The testing constitution for any Python project — layer budgets, where tests and fixtures sit and the closed autouse set, fixture versus builder, the substitution ladder and no-mocks contract, assert strength and literal expected values, HTTP interception, the datastore contract, reliability |
| `test-architecture-rule` | Static structural invariants and the grep firewall, with standalone and multi-member path scaffolds |

Load them alongside the architecture skill. The architecture says *which package* a module belongs
in; the universal skills govern names, Python forms, packaging, settings, the toolchain, errors, data access, boundaries, and testing.
`test-principles` is the source of truth for every test family: where another test skill contradicts
it, that skill is wrong.

`naming` is the one most worth loading before writing anything, and the one to load *first* when code
is being ported in from another project or generated wholesale. A name chosen by inertia — copied
from the source repository where its missing qualifiers were obvious (`CheckResult`), or one generic word
(`worker`, `manager`, `utils`) spread over several unrelated things — is the most expensive mistake in
this set, because nothing ever fails to make you fix it.

## Meta (1)

| Skill | Owns |
|---|---|
| `meta-skill-author` | Skill format, frontmatter and its real limits, the two-layer principle/binding anatomy, templates copied verbatim — a house pattern rather than a vendor's manual, a skeleton carrying only lines most services have — section order, naming scheme, rule ownership, packaging, and shared catalogue conventions |

## Pick a style first

| | `hex-*` (ports and adapters) | `flat-*` (package by technology) |
|---|---|---|
| **Use when** | Business invariants must survive a change of database, queue or framework; two or more entrypoints drive the same rules | The service orchestrates external systems: workers, crawlers, pipelines, ETL, glue |
| **Layers** | `domain/` → `application/` ← `infrastructure/`, entrypoints on top — canonical names | One package per technical role, named for the role; no fixed vocabulary |
| **Interfaces** | A `Protocol` port for every outward dependency | None until a second real implementation exists |
| **Wiring** | A container at the composition root | Direct construction in the process definition |
| **Persistence** | Repository adapters behind domain protocols | One package per store owning the service's data access |

The table is the summary, not the decision. **`architecture-choice` owns the decision** — it is
universal, so it is present whichever family plugins are installed, and it covers the cases this table
cannot: a service with real rules *and* heavy integration work, a flat service growing its first rule,
a workspace whose members differ, the scripts and one-shot jobs that need neither family, and the
project shapes — framework-dictated trees, package-by-feature services, libraries, modular
monoliths — that this catalogue does not cover at all. Run `/choose-architecture` to walk it
interactively, or read the skill. When the choice turns on how much
the protected rules will keep changing, load `coupling` alongside it — it owns that judgment.

## Hex core (11)

| Skill | Owns |
|---|---|
| `hex-architecture` | Once the family is hexagonal — layer boundaries, dependency direction, the composition root, ports vs adapters |
| `hex-conventions` | Identifier → file path and class name; the two store profiles and their connection-factory names (the factories themselves sit with their store skills); multi-context resolution |
| `hex-project-setup` | Which libraries each role brings, with the floors this family's templates rely on, and the migration bootstrap — a baseline only over a schema that already exists; the toolchain is `python-toolchain`'s |
| `hex-persistence` | `persistence`'s store-generic rules bound behind a port — the relational table, repository adapter (standalone and unit-of-work-joining), and paired migration revision, and the store's settings class, engine and session factories, and container binding; the unit of work over two repositories and the handler form that opens it |
| `hex-domain-model` | Entities, value objects — including when a constrained primitive becomes one — enums, filter records with their sort enum, and tunable thresholds with no default |
| `hex-domain-ports` | Aggregate repository protocols, including one for a store that answers only some reads, and external-capability protocols — async by default, a reversible pair, sync for pure CPU |
| `hex-domain-service` | Stateless domain rules that need state one entity cannot see, with injected ports; a pure transformation stays a module function |
| `hex-application` | CQRS commands, queries, handlers, and read-result forms; a clearable field carried with its presence; the compensating handler body that undoes an external write, and a side effect after the store write that never fails a committed command |
| `hex-wiring` | DI providers, lifetimes, container declaration order, and where each settings class is built, bound and checked before the process serves or takes work |
| `hex-capability-adapter` | Concrete capability implementations — one template, an HTTP gateway with its settings and binding; the SDK-client and pure-CPU forms in prose |
| `hex-store-repository` | Aggregate repositories for nonrelational stores, their record mappings, settings and connection factory, with the key prefix a module constant; bound to redis, other stores under Other bindings |

Hex projects also use the universal skills unchanged. `hex-architecture` adds the re-export
rules the layer split imposes on top of `python-packaging`; `hex-architecture` allocates logging by layer
(domain never logs, application logs successes only) under `python-logging`'s log-once rule.

## Hex REST API (4)

| Skill | Owns |
|---|---|
| `hex-restapi-app` | FastAPI lifecycle, central error translation and the map from error class to HTTP status, the shared error schemas, and declared middleware — none presumed, CORS included — with the registration of a status a middleware emits |
| `hex-restapi-endpoint` | Resource routers, JSON operations with read-back, route ordering, the rules for a route that carries a file, handler resolution, and the error responses a route advertises |
| `hex-restapi-schema` | Resource request/response models, partial updates, pagination, and schema exports |
| `hex-restapi-auth` | Caller identity as the issuer's opaque subject, with a rank only where a route gates on one; the token-verifier port and adapter, route dependencies, and the auth codes a route advertises |

**The first three are complete on their own.** `hex-restapi-auth` is optional: a service whose routes
need no caller identity — a public one, or one behind a gateway that authenticates for it — declares no
auth and never loads it.

## Hex tests (8)

| Skill | Owns |
|---|---|
| `hex-test-integration-setup` | The map of the whole hex suite tree; a framework-free base of session containers, rollback isolation and the per-test `container` with overridden providers; the key-value store as the worked store add-on; `real_app` as the REST add-on |
| `hex-test-domain` | Entity, value-object, enum, and domain-service unit tests — no file for a value object with no invariant |
| `hex-test-application-handler` | Handler unit tests for create, PATCH, delete, list and compensation, failure injection, and in-memory repository and capability fakes |
| `hex-test-repository-contract` | Real-backend repository contracts with relational rollback or client-store namespace isolation |
| `hex-test-capability-adapter` | Capability adapter tests — a `respx` template for the HTTP gateway; the containerized and pure-CPU flavours in prose, pointing at their worked instances |
| `hex-test-restapi-endpoint` | Real-app ASGI integration tests, success-body and error-code assertions, and per-resource fixtures |
| `hex-test-app-invariants` | Properties of the assembled HTTP app that no endpoint change touches — the app-construction smoke and the catalogue's error shape on every advertised code, plus CORS and request-size checks only where the app configures them; a service with no HTTP entrypoint keeps only the smoke |
| `hex-test-restapi-auth` | Token-minting fixtures, the authenticated client, the probe every operation not declared public must pass, and role and tenancy assertions |

## Flat core (4)

| Skill | Owns |
|---|---|
| `flat-layered` | The four role kinds and the import contract between them, with a skeleton of only what most flat services have — packages at the package root, each named for a role the service has; a package and settings class per configured component, a directory written for another reader included, built by the process definition, and the one-implementation client over one pooled transport with a refreshable credential |
| `flat-persistence` | One package per store, named for its technology, owning a service's data access and binding `persistence`'s store-generic rules to SQLAlchemy Core — a single-row upsert, time-ordered keys, the component's settings class and engine factory, one migration directory per store, and none for a store another project owns |
| `flat-entrypoint` | Trigger choice — one run per process by default, a loop, a stream or queue consumer, a thin HTTP wrapper receiving a body, or durable execution — and the framework-free function every trigger calls: bounded memory, progress markers after their data, atomic writes of files another reader collects, containment only in a process that outlives one run, bounded redelivery with a dead letter, fan-out failure containment, and the obligations an engine adds once one is earned |
| `flat-project-setup` | The one-time project setup — which libraries each role brings, with the floors this family's templates rely on, and the migration bootstrap under `migrations/postgres/` with a baseline only over an existing schema; the toolchain is `python-toolchain`'s, per-change revisions `flat-persistence`'s |

## Flat tests (4)

| Skill | Owns |
|---|---|
| `flat-test-integration-setup` | The suite-owned container, the safety guard any database the suite did not start must pass, and the isolation fixture each declared transaction owner needs |
| `flat-test-persistence` | The data-access package's contract against a real datastore — constraint name, update set, an ordering-stamp guard from both directions, translated exception, what each read returns, a cursor page edge where a run pages, and atomicity only where a write spans statements |
| `flat-test-service-client` | One client class's test |
| `flat-test-run-function` | What a trigger runs — the body end to end with an idempotence test wherever a run can repeat, the containment test only where a process outlives one run, the wrapper that invokes it, and the orchestration level above them where an engine was earned |

## Git (2)

In `pyhouse-git`, which depends on nothing and holds in a repository of any language.

| Skill | Owns |
|---|---|
| `git-commit-message` | The commit message and a request's title and description — their shape, the type as the record of which release a change earns, the break marker, nothing about the tool that wrote it, references only to what outlives the work — never a working document — and where the convention has to hold under a squash or a merge |
| `git-branching` | How a change reaches the mainline — the one mainline releases are cut from, the merge method and branch-name pattern recorded once, the short-lived one-change branch, history made true before it lands and never rewritten after, and when a released version earns a maintenance branch |

## Conventions across both sets

- Each skill ends in **Hard stops** — the wrong turns taken before any rule applies, which mean "do
  not proceed as asked": the wrong skill, with a redirect, or nothing to write. The obligations
  themselves are the numbered rules.
- Each opens with **When to use vs. neighbours**, so the wrong skill routes to the right one.
- Rules that are non-obvious carry their *reason*, and a few carry an explicit **withdrawal condition**
  — the observation that would retire the rule. Those are deliberate; do not strip them.
- **Frontmatter follows `meta-skill-author`.** `name` and `description` are required; `when_to_use`
  and `paths` are valid, documented Claude Code fields and optional on any skill. Descriptions open
  with **"Use when…"**, putting the trigger first and the content summary second, and each one must
  stand alone — clients other than Claude Code read `description` and nothing else.
- **Never write a bare `: ` inside an unquoted description.** A colon-plus-space breaks the YAML
  parse and can leave the skill with empty metadata and no description to match. Use an em dash.
- `name` is set on every skill and kept equal to its directory, so the listing and invocation agree.
- **Names carry their style.** Unprefixed skills are universal; `meta-*` covers skill authoring;
  `hex-*` and `flat-*` identify the architecture. `hex-restapi-*` covers HTTP artifacts, while
  `hex-test-*` and `flat-test-*` cover their respective tests. `flat-layered` is the flat style anchor.
- A rule has one owner. Consult `meta-skill-author` for the ownership table; other skills reference
  the owner rather than restating its rule.
- **Skills are invoked by name, not by a function call.** In Claude Code, a matching description
  loads a skill automatically. Typed by hand, the form depends on how the skill was installed: a
  skill delivered by a plugin is namespaced by its plugin — `/pyhouse-universal:naming`,
  `/pyhouse-hex:hex-persistence` — while one copied into `.claude/skills/` or `~/.claude/skills/`
  is typed bare, `/naming`. Inside a skill body, name the skill and never its slash form; it is
  the name that is stable across both install paths.
- **Portability.** `paths` and `when_to_use` are Claude Code fields; other clients ignore them, which
  is why `description` alone must identify a skill. Marketplace distribution via a GitHub repository and
  `plugin.json` carries them fine; publishing to claude.ai or the Skills API does not — that channel
  fails hard on any key outside `name`, `description`, `license`, `compatibility`, `metadata` and
  `allowed-tools`, so both fields are stripped on that path.

## Adapting to a project

Three kinds of name appear in these skills, with different rules for adapting each.

**Placeholders — always replace.** `myapp` (a distribution's own root package), `myschema` (a shared
library several distributions depend on), `myrepo` (the repository root), `myframework` (a framework a
rule is about wrapping), `foos`/`bars`, `Foo`/`Bar`/`Baz` (aggregates) and `Qux` (an external system the
service calls). These stand in for whatever the project actually calls things, and the environment
prefixes `MYAPP_`, `MYSCHEMA_` and `MYAPP_QUX_` follow the package or system they name.
None of them asserts a repository shape — one distribution and no `myschema` is the ordinary case.

**Structural names — keep the style's own.** The hexagonal layer names — `domain/`, `application/`,
`infrastructure/` — are the style's terms and stay; a flat service names its packages for the roles it
has (`flat-layered`).

**Technology names — keep.** `postgres`, `redis`, `s3`, `jwt` — a flat service's data-access package
included, named `postgres/` for its store. Abstracting these would
destroy the meaning of the rule that infrastructure is grouped by the real technology. The one
exception is a technology a rule is about *wrapping*, which takes `myframework` — naming a real one
there makes the rule that framework's instead of the project's.

The same three categories govern `naming`'s examples, which are deliberately drawn from no real
project: `Foo`/`Bar` and a generic upstream-availability check, with `redis`/`stripe`/`s3` kept
concrete. Like `coupling`, it assumes no layout and no architecture — only Python.

## Backlog

- **A hex entrypoint skill other than REST** (CLI, worker). Any entrypoint calls the same application
  handlers (`hex-application`), and `hex-restapi-app` is the only worked shell; a CLI or queue-consumer
  skill would own the shell around those handlers.
- **`flat-service-client` as its own skill** — *not currently needed*. `flat-layered` carries the
  external-system client template, its constructor-argument rule and its alternatives, and
  `flat-test-service-client` carries the test. Split it out only if the client family grows past one
  template.

## Licence

MIT — see `LICENSE` at the repository root.

The templates in these skills are meant to be copied into your own project. Doing that requires no
attribution and puts no obligation on the code you write around them, in open-source or proprietary
work. The attribution clause covers redistributing the catalogue itself, not the code you write after
reading it.
