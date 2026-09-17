# Skill conventions

Shared vocabulary and index for the catalogue. The authoritative format lives in `meta-skill-author`.

## Index

The 42 skills currently in the catalogue, grouped by family. Each entry is the skill's `name` plus one
**disambiguating line** — the thing a reader scanning the list needs in order not to pick the skill
next to it. It is written to agree with that skill's own `description` and body, not copied from
either, so changing a skill's scope means changing its entry here and its row in `skills/README.md`
too. The counts in every heading are the number of directories on disk.

### Universal (9)

- `architecture-choice` — Settle the hex-vs-flat family once per service before either family skill; names the project shapes the catalogue does not cover instead of routing them.
- `naming` — Load first when porting or generating code, before inherited names become project vocabulary.
- `coupling` — Consult alongside either style anchor when the architecture choice depends on component volatility.
- `python-style` — Owns the declared-type-over-bare-`dict` rule and the logging allocation that keeps every re-raising scope silent, whatever the project's layering.
- `python-packaging` — Keeps collapsed imports within one re-export hop so runtime resolution and type checking agree.
- `python-workspace` — Establish workspace ownership before adding shared libraries or runnable members; it governs members only, never what is inside one, and a lone distribution needs none of it.
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
- `hex-domain-model` — Decides when a constrained primitive becomes a value object, on a stdlib-only substrate separate from transport models.
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

### Flat core (3)

- `flat-layered` — Four role kinds carry the rules; the worked example's directory names are one project's and are replaceable, and one distribution on its own is the default.
- `flat-persistence` — Confine a service's statements and connections to one package, with one declared transaction owner per callable and no driver error escaping untranslated; relational throughout.
- `flat-entrypoint` — Changing the trigger wraps the same dependency-injected run function without rewriting its work; a workflow engine is earned, never assumed.

### Flat tests (4)

- `flat-test-integration-setup` — Choose the isolation fixture from the callable's declared transaction owner: rollback where it accepts a connection, wipe where it opens one.
- `flat-test-persistence` — Pin the storage package's behavior against the real datastore — the generated constraint name, the update set from both sides, the translated exception.
- `flat-test-service-client` — HTTP transport substitution needs no client Protocol; vendor SDK clients require their own backend or supplied test double.
- `flat-test-run-function` — Test the body and the wrapper that invokes it; the orchestration level and its engine bindings are in the sibling file.

## Packaging — which plugin a skill ships in

The catalogue is distributed on the Claude Code marketplace as three plugins under the marketplace name
`pyhouse`. Every new skill belongs to exactly one of them.

| Plugin | Directory | Contains | Depends on |
|---|---|---|---|
| `pyhouse-universal` | `plugins/pyhouse-universal/` | the 9 unprefixed universal skills + `meta-skill-author`, the architecture chooser `architecture-choice` among them, with its `/choose-architecture` command | — |
| `pyhouse-hex` | `plugins/pyhouse-hex/` | every `hex-*` skill (25) | `pyhouse-universal` |
| `pyhouse-flat` | `plugins/pyhouse-flat/` | every `flat-*` skill (7) | `pyhouse-universal` |

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
| `myapp` | a distribution's **own root package** |
| `myschema` | a **shared library several distributions depend on** — imported by them, owned by none of them |
| `myframework` | a **third-party framework** a rule is about *wrapping*, where naming a real one would make the rule that framework's |
| `myrepo` | the repository root |
| `Role.LOWER` / `Role.HIGHER` | the **placeholder rank ladder** — two positional members, lower first; a project substitutes its own members and however many it has |
| `tenant_id` | the **placeholder tenant or scope identifier** an authenticated identity carries |

`myapp` and `myschema` are two names because they are two roles. One name for both is what broke the
flat family's worked examples: a reader cannot tell a distribution's own package from a library it
imports when both are called the same thing. **Neither name asserts a repository shape.** One
distribution and no `myschema` at all is the ordinary case; `myschema` appears only where an example
needs a library that more than one distribution imports, and it says nothing about what that library
holds — a database schema is one thing shared code can be, not the definition. Environment prefixes
follow the package: `MYAPP_` for a distribution's own settings, `MYSCHEMA_` for a shared library's.

Names derived from them:

- Module `foo.py`; subdomain packages `domain/foos/`, `application/foos/`
- Table `foos_table` in `infrastructure/postgres/tables/foos.py`
- Protocol `IFooRepository` in `i_foo_repository.py`; capability `ICan<Verb>` in `i_can_<verb>.py`
- Commands/queries `CreateFooCommand`, `ListFoosQuery`, `CreateFooHandler`, `ListFoosResult`
- REST `FooResponse`, `FooListResponse`, `FooCreateRequest`, `FooUpdateRequest`, router `restapi/routers/foos.py`
- A repository of several distributions groups them as it chose — `myrepo/<group>/myapp/` for one
  distribution, `myrepo/<group>/myschema/` for a library they share

## Banned vocabulary

Names carried over from a real system are banned outright, in templates, rules and prose alike:
**any real role, tenant, bucket, database, queue, service or product name**, in every spelling it
travels in — snake_case, kebab-case, and the SCREAMING env-var prefix derived from it. A skill that
teaches through one system's vocabulary is unreadable to everyone else on it.

Use the placeholder vocabulary above instead: `Foo`/`Bar` for aggregates, `myapp` for a service's own
package, `myschema` for a library several distributions share, `myrepo` for the repo root,
`myframework` where a rule is about wrapping a framework rather than about that framework. A real
name with no placeholder to map onto gets a row added to the
table above — never an exception here. The repo's own lint and review check carries the literal
blocklist of names already found and removed, so this file states the category and does not reprint
them.

Technology names stay concrete, because a rule about grouping infrastructure by technology is
meaningless with the technology abstracted away: `postgres`, `redis`, `s3`, `jwt`, `dishka`. A
technology the rule is *about wrapping* is the opposite case and takes `myframework`, because naming
one there makes the rule that framework's instead of the project's.

One bounded exception sits outside that list: a **named third-party vendor used purely as a
disambiguation example** — where the point of the example is that the reader recognises the name as
one of several interchangeable providers, so a placeholder would blunt it. It stays an example and
never becomes a subject: no rule, section or template may depend on that vendor, and the name may not
travel into a path, a package, an env-var prefix or a shipped identifier.

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
