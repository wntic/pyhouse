# House-style skills

42 project-neutral Python skills in seven families: Universal (9), Meta (1), Hex core (12),
Hex REST API (5), Hex tests (8), Flat core (3), and Flat tests (4).

Worked examples use `myapp`, `myschema`, `myrepo`, `foos`/`bars`, and `Foo`/`Bar`. The directory names
in the flat-layered example are roles you rename, not vocabulary you copy — see
**Adapting to a project**.
Technology names (`postgres`, `redis`, `jwt`, `s3`) stay concrete, because the
folder-per-technology rule is meaningless with the technology abstracted away.

Add the `pyhouse` marketplace and install the plugin you need; each one lives under `plugins/` in this
repository:

| Plugin | Directory | Skills |
|---|---|---|
| `pyhouse-universal` | `plugins/pyhouse-universal/` | the 9 universal + `meta-skill-author`, and the `/choose-architecture` command |
| `pyhouse-hex` | `plugins/pyhouse-hex/` | the 25 `hex-*` |
| `pyhouse-flat` | `plugins/pyhouse-flat/` | the 7 `flat-*` |

Installing `pyhouse-hex` or `pyhouse-flat` brings `pyhouse-universal` with it. To carry a family
everywhere without the marketplace, copy that plugin's `skills/` **and** `pyhouse-universal/skills/`
into a project's `.claude/skills/` or into `~/.claude/skills/`; copying carries the skills only, not
`/choose-architecture`. **This index ships inside `pyhouse-universal`, so every install has it** — and
it lists the whole catalogue, including the skills of a family plugin that is not installed.

## How the catalogue fits together

**The two architecture families are mutually exclusive.** A service is hexagonal (`hex-*`) or
flat-layered (`flat-*`); no service is both. **The universal skills bind either way** — they govern
names, Python forms, packaging, errors, boundaries and testing whichever family a project chose. The
architecture chooser, **`architecture-choice`**, picks between the two families for a greenfield
service — and says when neither of them applies — a project too small to need one, or a shape the
catalogue does not cover. It is itself universal, because it is what you consult before you know
which family you are in, and the `/choose-architecture` command walks it one question at a time.

**The catalogue ships as three plugins** on the Claude Code marketplace: `pyhouse-universal` (the
unprefixed skills, `meta-skill-author`, the chooser), `pyhouse-hex` and `pyhouse-flat`. Both family
plugins depend on `pyhouse-universal`, which Claude Code enables transitively, so installing one family
always brings the universal skills with it. `pyhouse-universal` is installable alone: a universal skill
may *name* a family skill as an example but never require one.

Frontmatter and description rules — including the real length limits — are owned by
`meta-skill-author`. There is **no total description budget** across the catalogue, and no per-skill
character cap: `description` has no documented maximum, `description` + `when_to_use` truncate at
**1,536 characters combined**, and length is spent where it buys disambiguation. Descriptions are
rewritten as complete sentences to fit, never truncated.

## Universal (9) — always in play

These skills bind in **every** project in this style, whichever architecture it uses. They are
unprefixed because they belong to neither architecture family. `architecture-choice` is the one read
once rather than throughout — before the family is known:

| Skill | Owns |
|---|---|
| `architecture-choice` | **Which family a service belongs to** — the question that decides it, the confirming evidence, what each choice costs, the projects too small for either family, and the shapes this catalogue does not cover |
| `naming` | **What anything is called** — the derivation procedure, the six tests, kind-by-kind rules (incl. protocol, error-class and repository-class forms), the vague-noun families, renaming |
| `coupling` | Where boundaries go and what may cross them — split vs merge, contract vs shared knowledge, the three coupling dimensions, the balance rule, design effort by volatility |
| `python-style` | Typing forms, `collections.abc`, the `from __future__` ban, declared record types over bare `dict`s, which builtin holds which kind of scalar, structured logging, comments |
| `python-packaging` | One class per module, `__all__`, the `__init__.py` re-export contract, import rules |
| `python-workspace` | The repository root when several distributions share one — the member split, in-repo dependency edges, tooling settled once, compose profiles and task-runner targets; about members, never about what is inside one |
| `exception-catalog` | The single error-catalog file and translation of library exceptions at the boundary |
| `test-principles` | The testing constitution for both styles — pyramid, fixture placement, substitution ladders, assertion strength, reliability |
| `test-architecture-rule` | Static structural invariants and the grep firewall, with standalone and multi-member path scaffolds |

Load them alongside the architecture skill. The architecture says *which package* a module belongs
in; the universal skills govern names, Python forms, packaging, errors, boundaries, and testing.
`test-principles` is the source of truth for every test family: where another test skill contradicts
it, that skill is wrong.

`naming` is the one most worth loading before writing anything, and the one to load *first* when code
is being ported in from another project or generated wholesale. A name chosen by inertia — copied
from the source repo where its missing qualifiers were obvious (`CheckResult`), or one generic word
(`worker`, `manager`, `utils`) spread over several unrelated things — is the most expensive mistake in
this set, because nothing ever fails to make you fix it.

## Meta (1)

| Skill | Owns |
|---|---|
| `meta-skill-author` | Skill format, frontmatter and its real limits, the two-layer principle/binding anatomy, section order, naming scheme, rule ownership, packaging, and shared catalogue conventions |

## Pick a style first

| | `hex-*` (ports and adapters) | `flat-*` (package by tech) |
|---|---|---|
| **Use when** | Business invariants must survive a change of database, queue or framework; two or more entrypoints drive the same rules | The service orchestrates external systems: workers, crawlers, pipelines, ETL, glue |
| **Layers** | `domain/` → `application/` ← `infrastructure/`, entrypoints on top — canonical names | One package per technical role, named for the role; no fixed vocabulary |
| **Interfaces** | A `Protocol` port for every outward dependency | None until a second real implementation exists |
| **Wiring** | A container at the composition root | Direct construction in the entrypoint |
| **Persistence** | Repository adapters behind domain protocols | A shared schema package every service imports |

The table is the summary, not the decision. **`architecture-choice` owns the decision** — it is
universal, so it is present whichever family plugins are installed, and it covers the cases this table
cannot: a service with real rules *and* heavy integration work, a flat service growing its first rule,
a workspace whose members differ, the scripts and one-shot jobs that need neither family, and the
project shapes — framework-dictated trees, package-by-feature services, libraries, modular
monoliths — that this catalogue does not cover at all. Run `/choose-architecture` to walk it
interactively, or read the skill. When the choice turns on how much
the protected rules will keep changing, load `coupling` alongside it — it owns that judgment.

## Hex core (12)

| Skill | Owns |
|---|---|
| `hex-architecture` | Layer boundaries, dependency direction, the composition root, ports vs adapters |
| `hex-conventions` | Identifier → file path and class name; store profiles; multi-context resolution |
| `hex-project-setup` | Library substrate, toolchain configuration, the write-once migration bootstrap |
| `hex-patterns` | Compensating transactions, units of work and their nesting order, framework-free run functions |
| `hex-persistence` | The relational table, repository adapter, and paired migration revision |
| `hex-domain-model` | Entities, value objects — including when a constrained primitive becomes one — enums, filters, and tunable thresholds |
| `hex-domain-ports` | Aggregate repository and external-capability protocols |
| `hex-domain-service` | Stateless domain rules that use cross-aggregate state or capabilities |
| `hex-application` | CQRS commands, queries, handlers, and read-result forms |
| `hex-wiring` | Integration settings, DI providers, lifetimes, and container declaration order |
| `hex-capability-adapter` | Concrete capability implementations using SDKs, HTTP, or CPU work |
| `hex-store-repository` | Aggregate repositories for nonrelational stores and their record mappings |

Hex projects also use the universal skills unchanged. `hex-architecture` adds the re-export
rules the layer split imposes on top of `python-packaging`; `python-style` carries the per-layer
logging allocation (domain never logs, application logs successes only).

## Hex REST API (5)

| Skill | Owns |
|---|---|
| `hex-restapi-app` | FastAPI lifecycle, middleware, central error translation, and the shared error schemas |
| `hex-restapi-endpoint` | Resource routers, JSON operations, multipart uploads, streaming downloads, and handler resolution |
| `hex-restapi-schema` | Resource request/response models, partial updates, pagination, and schema exports |
| `hex-restapi-route-contracts` | The advertised error responses a route declares, and the middleware-code registry |
| `hex-restapi-auth` | Caller identity, the token-verifier port and adapter, route dependencies, the role gate, and the auth codes a route advertises |

**The first four are complete on their own.** `hex-restapi-auth` is optional: a service behind an
authenticating gateway, an mTLS-fronted API or a public one declares no auth and never loads it.

## Hex tests (8)

| Skill | Owns |
|---|---|
| `hex-test-integration-setup` | Session containers, rollback isolation, DI overrides, and the real-app fixture |
| `hex-test-domain` | Entity, value-object, enum, and domain-service unit tests |
| `hex-test-application-handler` | Handler unit tests, failure injection, and in-memory repository and capability fakes |
| `hex-test-repository-contract` | Real-backend repository contracts with relational rollback or client-store namespace isolation |
| `hex-test-capability-adapter` | Capability adapter tests with containers, HTTP transport substitution, or real CPU work |
| `hex-test-restapi-endpoint` | Real-app ASGI integration tests, response validation, and per-resource fixtures |
| `hex-test-discovery-invariants` | App-construction smoke tests and discovered OpenAPI, CORS, and request-size invariants |
| `hex-test-restapi-auth` | Token-minting fixtures, the authenticated client, the anonymous-caller probe, and role and tenancy assertions |

## Flat core (3)

| Skill | Owns |
|---|---|
| `flat-layered` | The four role kinds and the import contract between them, with the package layout as one worked example; component-owned settings and the one-implementation client |
| `flat-persistence` | One package owning a service's data access, relational: transaction ownership, driver-error translation, row mapping, chunked and conflict-resolved writes |
| `flat-entrypoint` | Trigger choice — loop, schedule, stream or durable execution — and the framework-free run function every trigger wraps; the obligations an engine adds are in its sibling binding |

## Flat tests (4)

| Skill | Owns |
|---|---|
| `flat-test-integration-setup` | The container, the safety guard, and the isolation fixture each declared transaction owner needs |
| `flat-test-persistence` | The storage package's contract against a real datastore |
| `flat-test-service-client` | One client class's test |
| `flat-test-run-function` | What a trigger runs — the body and the wrapper that invokes it; the orchestration level is in its sibling binding |

## Conventions across both sets

- Each skill ends in **Hard stops** — absolute conditions that mean "do not proceed as asked".
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
  is why `description` alone must identify a skill. Marketplace distribution via a GitHub repo and
  `plugin.json` carries them fine; publishing to claude.ai or the Skills API does not — that channel
  fails hard on any key outside `name`, `description`, `license`, `compatibility`, `metadata` and
  `allowed-tools`, so both fields are stripped on that path.

## Adapting to a project

Three kinds of name appear in these skills, with different rules for adapting each.

**Placeholders — always replace.** `myapp` (a distribution's own root package), `myschema` (a shared
library several distributions depend on), `myrepo` (the repository root), `myframework` (a framework a
rule is about wrapping), `foos`/`bars`, and `Foo`/`Bar`. These stand in for whatever the project
actually calls things, and the environment prefixes `MYAPP_` and `MYSCHEMA_` follow their packages.
None of them asserts a repository shape — one distribution and no `myschema` is the ordinary case.

**Structural names — replace when the role does not exist.** `ingest/`, `jobs/`,
`entrypoints/`, `services/` in the flat-layered set are *role names from a worked example*, not
a required vocabulary; `flat-layered` opens with the rule. Create the packages your service's roles
require, named for those roles, and no others. The canonical hexagonal names — `domain/`,
`application/`, `infrastructure/` — are the exception: those are the style's own terms and stay.

**Technology names — keep.** `postgres`, `redis`, `s3`, `jwt`. Abstracting these would
destroy the meaning of the rule that infrastructure is grouped by the real technology. The one
exception is a technology a rule is about *wrapping*, which takes `myframework` — naming a real one
there makes the rule that framework's instead of the project's.

The same three categories govern `naming`'s examples, which are deliberately drawn from no real
project: `Foo`/`Bar` and a generic upstream-availability check, with `redis`/`stripe`/`s3` kept
concrete. Like `coupling`, it assumes no layout and no architecture — only Python.

## Backlog

- **A hex entrypoint skill other than REST** (CLI, worker). `hex-patterns` carries the framework-free
  run function such an entrypoint calls, and `hex-restapi-app` is the only worked entrypoint; a CLI or
  queue-consumer skill would own the shell around that run function.
- **A read-model skill**, the first time a query handler genuinely needs a denormalized, join-flattened
  DTO rather than an aggregate read. The condition and the shape it should take are recorded in
  `meta-skill-author/CONVENTIONS.md`.
- **`flat-service-client` as its own skill** — *not currently needed*. `flat-layered` carries the
  external-system client template, its constructor-argument rule and its alternatives, and
  `flat-test-service-client` carries the test. Split it out only if the client family grows past one
  template.

Two entries that stood here are closed. `hex-persistence` is no longer oversized — it is 175 lines with
`TABLE.md`, `REPOSITORY.md` and `REVISION.md` beside it. Flat-side exception translation is genuinely
covered: `exception-catalog` carries a flat-layered catalog template, the translation section and the
mandatory-fallback rule, and `flat-layered` routes to it.

## Licence

MIT — see `LICENSE` at the repository root.

The templates in these skills are meant to be copied into your own project. Doing that requires no
attribution and puts no obligation on the code you write around them, in open-source or proprietary
work. The attribution clause covers redistributing the catalogue itself, not the code you write after
reading it.
