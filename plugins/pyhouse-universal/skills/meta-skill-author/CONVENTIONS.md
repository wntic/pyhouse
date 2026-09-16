# Skill conventions

Shared vocabulary and index for the catalogue. The authoritative format lives in `meta-skill-author`.

## Index

The 44 skills currently in the catalogue, grouped by family. Each entry is the skill's `name` plus one
**disambiguating line** — the thing a reader scanning the list needs in order not to pick the skill
next to it. It is written to agree with that skill's own `description` and body, not copied from
either, so changing a skill's scope means changing its entry here and its row in `skills/README.md`
too. The counts in every heading are the number of directories on disk.

### Universal (8)

- `architecture-choice` — Settle the hex-vs-flat family once per service before either family skill; says when neither applies.
- `naming` — Load first when porting or generating code, before inherited names become project vocabulary.
- `coupling` — Consult alongside either style anchor when the architecture choice depends on component volatility.
- `python-style` — Keeps domain code silent and assigns successful business-event logging to the application layer.
- `python-packaging` — Keeps collapsed imports within one re-export hop so runtime resolution and type checking agree.
- `exception-catalog` — Reuse an existing catalog entry before adding a new failure type; transport rendering stays at the boundary.
- `test-principles` — Takes precedence whenever an artifact-specific test skill contradicts the shared constitution.
- `test-architecture-rule` — Enforces source-level structure; runtime route discovery belongs to the hex discovery tests.

### Meta (1)

- `meta-skill-author` — Consult this sibling's vocabulary and index before adding a skill so its scope fits the existing catalogue.

### Hex core (12)

- `hex-architecture` — Choose this style when business invariants must outlive infrastructure or serve multiple entrypoints.
- `hex-conventions` — Resolve artifact locations and context ownership before applying an artifact's file template.
- `hex-project-setup` — Run the migration bootstrap once; later table changes use the persistence skill's paired revision.
- `hex-patterns` — Extend a handler when an external effect needs undo or several repositories must commit together.
- `hex-persistence` — Choose the standalone or unit-of-work-managed form according to who owns the transaction.
- `hex-domain-model` — Keeps the domain's data shapes on a stdlib-only substrate, separate from transport models.
- `hex-domain-ports` — Defines the signatures that adapters satisfy without inheriting or importing the protocol.
- `hex-domain-service` — Place rules beside their primary aggregate; use an entity for rules enforceable from its own fields.
- `hex-application` — Commands mutate and return an id; queries read and return data through an execute-only handler surface.
- `hex-wiring` — Extend the existing composition root when a concrete dependency must become available to a handler.
- `hex-capability-adapter` — Implements an external action; aggregate persistence belongs to a repository skill.
- `hex-store-repository` — Use for client-style storage; relational tables and Alembic revisions belong to the persistence skill.

### Hex REST API (5)

- `hex-restapi-app` — Establish the shared shell before adding resource routers; the shell it lays presumes no authentication.
- `hex-restapi-endpoint` — Maps transport inputs to application calls while keeping domain logic out of the route body.
- `hex-restapi-schema` — Match the domain filter's chosen pagination shape and the command DTO's partial-update contract.
- `hex-restapi-route-contracts` — Keep the errors a route advertises aligned with what its handler and middleware can actually produce.
- `hex-restapi-auth` — Add only when the entrypoint itself authenticates; a gateway- or mTLS-fronted service declares no auth and skips it.

### Hex tests (8)

- `hex-test-integration-setup` — Establish shared infrastructure fixtures before repository, adapter, or API integration tests.
- `hex-test-domain` — Choose the template for the domain shape, using a minimal inline stub when a service needs a collaborator.
- `hex-test-application-handler` — Keeps in-memory collaborator behavior and failure injection beside the handler contracts they support.
- `hex-test-repository-contract` — Exercise the same aggregate contract across adapters while selecting isolation for the actual store.
- `hex-test-capability-adapter` — Select the backend-specific flavor; a pure-CPU implementation runs directly without a container.
- `hex-test-restapi-endpoint` — Reuse the shared integration setup and keep resource-specific fixture preparation in the sibling conftest.
- `hex-test-discovery-invariants` — Discovers applicable routes so new endpoints enter the checks without a hand-maintained route list.
- `hex-test-restapi-auth` — Layer the auth fixtures over the shared integration setup; produced only for an app whose entrypoint authenticates.

### Flat core (5)

- `flat-layered` — Create packages only for roles the service actually has; the worked example's directory names are replaceable.
- `flat-monorepo` — Establish workspace ownership before adding shared packages or runnable service members.
- `flat-schema-package` — Gives every service one shared source of table definitions instead of service-local copies.
- `flat-entrypoint` — Changing the trigger wraps the same dependency-injected run function without rewriting its work.
- `flat-temporal-workflow` — Extend the entrypoint skill's plain activity trio only when a run needs more than one activity.

### Flat tests (5)

- `flat-test-integration-setup` — Choose rollback for connection-bound code and truncation when the code owns its transactions.
- `flat-test-schema-package` — Pin the shared database behavior once so each service need not repeat the schema contract.
- `flat-test-service-client` — HTTP transport substitution needs no client Protocol; vendor SDK clients require their own backend or supplied test double.
- `flat-test-run-function` — Cover activity effects here so workflow tests can stay focused on orchestration.
- `flat-test-temporal-workflow` — Register stub activities under the production activity names so string-based workflow dispatch reaches them.

## Packaging — which plugin a skill ships in

The catalogue is distributed on the Claude Code marketplace as three plugins under the marketplace name
`pyhouse`. Every new skill belongs to exactly one of them.

| Plugin | Directory | Contains | Depends on |
|---|---|---|---|
| `pyhouse-universal` | `plugins/pyhouse-universal/` | the 8 unprefixed universal skills + `meta-skill-author` + the architecture chooser `architecture-choice`, with its `/choose-architecture` command | — |
| `pyhouse-hex` | `plugins/pyhouse-hex/` | every `hex-*` skill (25) | `pyhouse-universal` |
| `pyhouse-flat` | `plugins/pyhouse-flat/` | every `flat-*` skill (10) | `pyhouse-universal` |

A new skill's directory goes under that plugin's `skills/`, beside its siblings. The plugin's own
manifest is the single file `.claude-plugin/plugin.json`; nothing else belongs in that directory, and
`skills/`, `commands/` and any other component directory sit at the plugin root.

`plugin.json` carries `dependencies` with semver, and Claude Code enables them transitively at the same
scope, so a family plugin always arrives with `pyhouse-universal` and a reference from `hex-*` or
`flat-*` into a universal skill never dangles.

**The dependency direction is one-way.** A `hex-*` or `flat-*` skill may reference a universal skill
freely. **A universal skill may not reference a family skill as a requirement** — only as an example,
and it must read sensibly with that example's plugin absent, because `pyhouse-universal` must be
installable alone. A universal skill that tells the reader "see `hex-persistence` for the rules" is a
broken install waiting to happen; one that says "the hexagonal family applies this under
`hex-persistence`, in the `pyhouse-hex` plugin" is not.

The prefix decides the plugin: unprefixed and `meta-*` → `pyhouse-universal`; `hex-*` (including
`hex-restapi-*` and `hex-test-*`) → `pyhouse-hex`; `flat-*` (including `flat-test-*`) → `pyhouse-flat`.
A skill that would need to sit in two plugins is two skills.

**The two family plugins may route to each other, and that reference is expected to dangle.** The
families are mutually exclusive, so "not this skill — you are in the other family" is a route a reader
follows exactly once, by installing the other plugin. Write those with the plugin named —
"`flat-layered`, in the `pyhouse-flat` plugin" — never as a bare pointer, so a reader who cannot
resolve the name learns why. A cross-family reference that carries a rule the referring skill needs is
a different thing and is a defect — restate the rule, or move it to a universal skill both families
reach, as the interpreter floor was moved to `python-style`.

## Placeholder vocabulary

One vocabulary for the whole catalogue.

| Placeholder | Stands for |
|---|---|
| `Foo` | the primary aggregate |
| `Bar` | the secondary aggregate |
| `myapp` | a service's **own root package** |
| `myschema` | the **shared schema library** a workspace's services depend on |
| `myrepo` | the repository root |
| `foo_parser` | a *specific* service, where a monorepo example must name one |

`myapp` and `myschema` are two names because they are two roles. One name for both is what broke the
flat family's worked examples: a reader cannot tell the service's own package from the library it
imports when both are called the same thing. Environment prefixes follow the package: `MYAPP_` for a
service's own settings, `MYSCHEMA_` for the shared schema library's.

Names derived from them:

- Module `foo.py`; subdomain packages `domain/foos/`, `application/foos/`
- Table `foos_table` in `infrastructure/postgres/tables/foos.py`
- Protocol `IFooRepository` in `i_foo_repository.py`; capability `ICan<Verb>` in `i_can_<verb>.py`
- Commands/queries `CreateFooCommand`, `ListFoosQuery`, `CreateFooHandler`, `ListFoosResult`
- REST `FooResponse`, `FooListResponse`, `FooCreateRequest`, `FooUpdateRequest`, router `restapi/routers/foos.py`
- Monorepo members `myrepo/services/foo_parser/`, `myrepo/packages/myschema/`

## Banned vocabulary

Names carried over from a real system are banned outright, in templates, rules and prose alike:
**any real role, tenant, bucket, database, queue, service or product name**, in every spelling it
travels in — snake_case, kebab-case, and the SCREAMING env-var prefix derived from it. A skill that
teaches through one system's vocabulary is unreadable to everyone else on it.

Use the placeholder vocabulary above instead: `Foo`/`Bar` for aggregates, `myapp` for a service's own
package, `myschema` for the shared schema library, `myrepo` for the repo root, `foo_parser` where an
example must name one service. A real name with no placeholder to map onto gets a row added to the
table above — never an exception here. The repo's own lint and review check carries the literal
blocklist of names already found and removed, so this file states the category and does not reprint
them.

Technology names stay concrete, because a rule about grouping infrastructure by technology is
meaningless with the technology abstracted away: `postgres`, `redis`, `s3`, `jwt`, `temporalio`,
`dishka`.

## Out of scope (intentionally not in this catalog)

- Process-only skills (brainstorming, retrospective notes). If reintroduced they belong under a separate
  prefix, e.g. `process-brainstorm`.
- Use-case authoring belongs to the spec-driven workflow plugin, not to this catalogue.

## Read models — guidance for a future skill

The catalog deliberately does **not** split repositories into write-side and read-side protocols. The
CQRS guarantee that matters — commands mutate, queries read — is carried by the handler split
(a command mutates, a query reads); partitioning every `IFooRepository` into read and write
halves would double the protocol, DI and test surface across all aggregates for a benefit that only
materializes with event sourcing, async projections, or a separate read store, none of which apply here
today.

Add a read-model skill the first time a query handler genuinely needs a denormalized, join-flattened DTO
that is not "an aggregate read" — for example foos with author name, tag count and last-modified-by name
joining three tables. Model it as an additive component with its own protocol, adapter and flat DTO, not
as a partition of the existing repository. Until that case appears, the unified `IFooRepository` with
both reads and writes is the canonical shape.
