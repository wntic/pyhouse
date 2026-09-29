# Skill conventions

Shared vocabulary, index and skill shapes for the catalogue. The authoritative format lives in
`meta-skill-author`.

## Index

The 48 skills currently in the catalogue, grouped by family. Each entry is the skill's `name` plus one
**disambiguating line** — the thing a reader scanning the list needs in order not to pick the skill
next to it. It is written to agree with that skill's own `description` and body, not copied from
either, so changing a skill's scope means changing its entry here and its row in `skills/README.md`
too. The counts in every heading are the number of directories on disk.

### Universal (14)

- `architecture-choice` — Settle the hex-vs-flat family once per service before either family skill; names the project shapes the catalogue does not cover instead of routing them.
- `naming` — Load first when porting or generating code, before inherited names become project vocabulary; a suffix naming a role the architecture defines (`Handler`, `Result`, `Payload`, `Service`) is not a vague noun, and the class owning a record's data access is a `Repository` with or without a port.
- `coupling` — Consult alongside either style anchor when the architecture choice depends on component volatility.
- `python-style` — Owns the 3.13 house floor, the declared-type-over-bare-`dict` rule with a `type` alias for a repeated complex type, and a closed set of constants as an `Enum`; what to log and who logs it is `python-logging`.
- `python-logging` — The logging allocation that keeps every re-raising scope silent, whatever the project's layering, one structured event per occurrence under a never-renamed name, and logging configured only at the entry point — never inside a distributed package; a program's result on stdout is not a log, and a program whose stdout is its result logs to stderr.
- `python-packaging` — Decides whether a module wants a class at all before capping it at one — a closed set of declarations may share a module by test, and a module a framework dictates follows the framework — and keeps collapsed imports within one re-export hop so runtime resolution and type checking agree.
- `python-settings` — One settings class per configured component, reading only its own non-strict namespace and built once at the program's composition root; no default on a required field, a secret or a tunable, and a published library reads no environment at all.
- `python-toolchain` — The configuration every distribution carries once, whatever its family — the src layout, a narrow lint selection with every size and complexity threshold written, strict type checking over `src` and `tests` alike, the sanctioned suppressions, one line length, the test runner's block, and a floor only at a named break; which libraries a service's roles bring stays with the family's setup skill.
- `python-workspace` — Establish workspace ownership before adding shared libraries or runnable members; it governs members only, never what is inside one, and a lone distribution needs none of it.
- `python-versioning` — Decide whether the version is a compatibility promise or only a label before bumping it; owns which change forces which segment, and what 0.y.z deliberately withholds.
- `persistence` — The store-generic data-access obligations whatever the family, and which of them lapse for a store without transactions, named constraints, a conditional write, a schema of its own, migrations or two versions running at once; it binds no library and writes no file, leaves the identity scheme to the family, and points at `exception-catalog` for the translation itself.
- `exception-catalog` — Reuse an existing catalog entry before adding a new failure type; a failure is re-raised or stopped, never swallowed, and best-effort compensation is the one case a re-raising scope stops a second failure; a failure after a committed write is stopped, never re-raised; transport rendering, and the status a transport maps a class to, stay at the boundary.
- `test-principles` — The testing constitution for any Python project, and it wins wherever an artifact-specific test skill contradicts it — where tests and fixtures sit and the closed autouse set, one substitution ladder, assert strength with literal expected values, HTTP interception asserted on the exercised route's own call record and pinning what the route does not match on, and a datastore contract that reads the store back and forces translated driver errors.
- `test-architecture-rule` — Enforces source-level structure; runtime route discovery belongs to the hex app-wide invariant tests.

### Meta (1)

- `meta-skill-author` — Consult this sibling's vocabulary and index before adding a skill so its scope fits the existing catalogue; a template is copied verbatim, shows a house pattern rather than a vendor's manual, and a skeleton carries only lines most services of its family have, a variant marked with its condition.

### Hex core (11)

- `hex-architecture` — Once the family is hexagonal, decides which layer a module belongs in and which way an import may cross; whether hexagonal fits at all is `architecture-choice`'s.
- `hex-conventions` — Resolve artifact locations and context ownership before applying an artifact's file template; it names each store profile's connection factory, while the factory itself is written by the store's own skill.
- `hex-project-setup` — Run the bootstrap once — which libraries each role brings with the floors this family's templates rely on, and migrations with a baseline only over an existing schema; the toolchain itself is `python-toolchain`'s, later table changes the persistence skill's paired revision.
- `hex-persistence` — Binds `persistence`'s store-generic rules behind a port; choose the standalone or unit-of-work-managed form according to who owns the transaction; the relational store's settings class, its engine and session factories, and its container binding sit beside the adapter. A command writing two or more repositories atomically reads its unit-of-work file.
- `hex-domain-model` — Decides when a constrained primitive becomes a value object, on a stdlib-only substrate separate from transport models; a tunable threshold carries no default.
- `hex-domain-ports` — Defines the signatures that adapters satisfy without inheriting or importing the protocol; a capability is async unless it is pure CPU, and a reversible action declares its undo beside it.
- `hex-domain-service` — Place rules beside their primary aggregate; use an entity for rules enforceable from its own fields, and a module function for a transformation with nothing to inject.
- `hex-application` — Commands mutate and return an id, and a clearable field in one carries whether the caller gave it; queries read and return data through an execute-only handler surface; an external write undone when a later store write fails is its compensation body, and a side effect after the store write is stopped and logged or handed on — the sanctioned `try/except`s beside a failure-state transition.
- `hex-wiring` — Extend the existing composition root when a concrete dependency must become available to a handler; it builds and binds settings classes, all of them before the process serves or takes work, whose contents are `python-settings`'s.
- `hex-capability-adapter` — Implements an external action, templated once as an HTTP gateway with the SDK-client and pure-CPU forms in prose; aggregate persistence belongs to a repository skill.
- `hex-store-repository` — Use for client-style storage, bound to redis, other stores under Other bindings; it writes the store's connection factory and fixes the key prefix in code, while relational tables and Alembic revisions belong to the persistence skill.

### Hex REST API (4)

- `hex-restapi-app` — Establish the shared shell before adding resource routers; the shell it lays presumes no authentication and no declared middleware, CORS included; the status each error class answers with, and a status a middleware emits, are registered here.
- `hex-restapi-endpoint` — Maps transport inputs to application calls while keeping domain logic out of the route body, and keeps the errors the route advertises aligned with what it can actually produce; a route that carries a file moves the bytes and nothing else.
- `hex-restapi-schema` — Match the domain filter's chosen pagination shape and the command DTO's partial-update contract.
- `hex-restapi-auth` — Add only when a route needs its caller's identity; a service whose routes need none, behind a gateway or not, declares no auth and skips it. The caller is an opaque subject, and a rank exists only where a route gates on one.

### Hex tests (8)

- `hex-test-integration-setup` — Establish shared infrastructure fixtures before repository, adapter, or API integration tests, and map the whole hex suite tree, naming the skill that writes each file in it; the base ends framework-free at the `container` fixture, and `real_app` is the REST add-on.
- `hex-test-domain` — Choose the template for the domain shape, running a service on the in-memory fake of its port.
- `hex-test-application-handler` — Keeps in-memory collaborator behavior and failure injection beside the handler contracts they support, and owns every fake.
- `hex-test-repository-contract` — Exercise the same aggregate contract across adapters while selecting isolation for the actual store.
- `hex-test-capability-adapter` — Select the backend-specific flavor; the HTTP gateway is templated, and a pure-CPU implementation runs directly without a container.
- `hex-test-restapi-endpoint` — Reuse the shared integration setup and keep resource-specific fixture preparation in the sibling conftest.
- `hex-test-app-invariants` — Pins properties of the assembled app that adding or removing an endpoint must never oblige anyone to edit; the CORS and request-size checks exist only where the app configures them, and a service with no HTTP entrypoint keeps only the construct smoke.
- `hex-test-restapi-auth` — Layer the auth fixtures over the shared integration setup; produced only for an app whose entrypoint authenticates.

### Flat core (4)

- `flat-layered` — Four role kinds carry the rules and each package, at the package root, is named for a role the service actually has — the skeleton holds only what most flat services have; a configured component is a package with its own settings class, built by the process definition, whose contents are `python-settings`'s, and a client holds one pooled transport; one distribution on its own is the default.
- `flat-persistence` — Confine each store's statements and connections to one package named for its technology, binding `persistence`'s store-generic rules with no port in front — batched writes chunked from the driver's cap, application-minted time-ordered keys, one migration directory per store — and a store another project owns gets no migrations.
- `flat-entrypoint` — Changing the trigger — one run per process by default, a loop, a stream, a thin HTTP wrapper or durable execution — calls the same dependency-injected function without rewriting its work; only a process that outlives one run contains a run's failure, a contained unit is redelivered to a limit and then dead-lettered, and a workflow engine is earned, never assumed.
- `flat-project-setup` — Lay a flat service down once — which libraries each role brings with the floors this family's templates rely on, and the migration bootstrap with no empty greenfield baseline; the toolchain itself is `python-toolchain`'s, per-change revisions `flat-persistence`'s.

### Flat tests (4)

- `flat-test-integration-setup` — The suite starts its own datastore container; choose the isolation fixture from the callable's declared transaction owner: rollback where it accepts a connection, wipe where it opens one.
- `flat-test-persistence` — Pin the data-access package's behavior against the real datastore — the generated constraint name, the update set from both sides, an ordering-stamp guard from both directions, the translated exception, a paged read's page edge — and atomicity only where one write spans statements.
- `flat-test-service-client` — HTTP transport substitution needs no client Protocol; vendor SDK clients require their own backend or supplied test double.
- `flat-test-run-function` — Test the body end to end, the containment only where a process outlives one run, and the wrapper that invokes it; the orchestration level above them only where a durable-execution engine was earned.

### Git (2)

- `git-commit-message` — The type records which release a change earns and is picked by what the change is, never its size; a commit that is not a release never touches the version.
- `git-branching` — One mainline, one merge method recorded per repository, short-lived one-change branches; a fix to unlanded work is folded, and history someone else built on is never rewritten.

## Packaging — which plugin a skill ships in

The catalogue is distributed on the Claude Code marketplace as four plugins under the marketplace name
`pyhouse`. Three of them hold Python house style, and every new Python skill belongs to exactly one of
those three. The fourth, `pyhouse-git`, ships beside them and holds the `git-*` skills — repository workflow rather than Python house style. It
depends on nothing and nothing in the catalogue depends on it, so a `git-*` skill may name a catalogue
skill only as an example and must read correctly in a repository with no Python in it.

| Plugin | Directory | Contains | Depends on |
|---|---|---|---|
| `pyhouse-universal` | `plugins/pyhouse-universal/` | the 14 unprefixed universal skills + `meta-skill-author`, the architecture chooser `architecture-choice` among them, with its `/choose-architecture` command, and the `/pyhouse-universal:code-review` command with the `pyhouse-reviewer` subagent behind it | — |
| `pyhouse-hex` | `plugins/pyhouse-hex/` | every `hex-*` skill (23) | `pyhouse-universal` |
| `pyhouse-flat` | `plugins/pyhouse-flat/` | every `flat-*` skill (8) | `pyhouse-universal` |
| `pyhouse-git` | `plugins/pyhouse-git/` | every `git-*` skill (2), `/commit`, `/release`, `/install-commit-hook`, the `commit-msg` hook | — |

**The two review artifacts state no rules.** `/pyhouse-universal:code-review` and the `pyhouse-reviewer` subagent behind it decide which skills apply to a target and apply them; every criterion they report is a numbered rule or a hard stop in the skill that owns it. A rule restated in either of them would be a second copy with no reader to catch it drifting, so a judgement neither can attribute to a skill is reported as a gap in the catalogue instead of as a finding.

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
`hex-restapi-*` and `hex-test-*`) → `pyhouse-hex`; `flat-*` (including `flat-test-*`) → `pyhouse-flat`;
`git-*` → `pyhouse-git`.
A skill that would need to sit in two plugins is two skills.

**The two family plugins may route to each other, and that reference is expected to dangle.** The
families are mutually exclusive, so "not this skill — you are in the other family" is a route a reader
follows exactly once, by installing the other plugin. Write those with the plugin named —
"`flat-layered`, in the `pyhouse-flat` plugin" — never as a bare pointer, so a reader who cannot
resolve the name learns why. A cross-family reference that carries a rule the referring skill needs is
a different thing and is a defect — restate the rule, or move it to a universal skill both families
reach, as the interpreter floor was moved to `python-style`.

## Skill shapes

The four shapes `meta-skill-author` names, what each emphasises, and the skills already in each. Pick
the shape with the table there.

### Producer — the default

Creates one or more new files. Emphasis: `Template(s)` carries full literal file content with
placeholders, under a heading naming its stack; `Package wiring` appears when a new module needs
registering in an `__init__.py`.

Examples: `hex-domain-model`, `hex-application`, `hex-persistence`, `hex-restapi-endpoint`,
`hex-test-domain`.

### Modifier

Extends an existing file rather than creating one. Emphasis: `Template(s)` shows what gets inserted — a
class body, a function, a decorator argument — not a whole file; `Package wiring` is usually absent
because the file already lives in a package.

Examples: `hex-wiring` (modifies the composition root), `test-architecture-rule` (appends a test
function).

### Bootstrap

Produces a fixed set of files, once per project. Emphasis: `Template(s)` carries several full file
templates under `###` subheadings, one per file; `When to use vs. neighbours` says plainly that it is
one-shot and names what other skills depend on it having run.

Examples: `hex-restapi-app`, `hex-test-integration-setup`, `hex-test-app-invariants`.

### Reference

Produces no file — documents conventions other skills consult. Keeps `When to use vs. neighbours`,
`Rules` and `Hard stops`; omits `Template(s)`, `Other bindings` and `Package wiring`; may organise its
body under topical `##` headings that name the subject matter (`meta-skill-author` rule 1).

Examples: `hex-conventions`, `hex-architecture`, `python-style`, `test-principles`, `meta-skill-author`.

## Placeholder vocabulary

One vocabulary for the whole catalogue.

| Placeholder | Stands for |
|---|---|
| `Foo` | the primary aggregate |
| `Bar` | the secondary aggregate |
| `Baz` | a third aggregate, used where an example needs one held by a different kind of store than `Foo` and `Bar` — module `baz.py`, package `domain/bazs/`, port `IBazRepository` |
| `myapp` | a distribution's **own root package** |
| `myschema` | a **shared library several distributions depend on** — imported by them, owned by none of them |
| `myframework` | a **third-party framework** a rule is about *wrapping*, where naming a real one would make the rule that framework's |
| `myrepo` | the repository root |

`myapp` and `myschema` are two names because they are two roles. One name for both is what broke the
flat family's worked examples: a reader cannot tell a distribution's own package from a library it
imports when both are called the same thing. **Neither name asserts a repository shape.** One
distribution and no `myschema` at all is the ordinary case; `myschema` appears only where an example
needs a library that more than one distribution imports, and it says nothing about what that library
holds — a database schema is one thing shared code can be, not the definition. Environment prefixes
follow the package: `MYAPP_` for a distribution's own settings, `MYSCHEMA_` for a shared library's.

Names derived from them: module `foo.py`, table `foos`; a repository of several distributions groups
them as it chose — `myrepo/<group>/myapp/` for one distribution, `myrepo/<group>/myschema/` for a
library they share.

### Hex family

Vocabulary only the `hex-*` skills use:

- Subdomain packages `domain/foos/`, `application/foos/`; table `foos_table` in
  `infrastructure/postgres/tables/foos.py`
- Protocol `IFooRepository` in `i_foo_repository.py`; capability `ICan<Verb>` in `i_can_<verb>.py`
- Commands/queries `CreateFooCommand`, `ListFoosQuery`, `CreateFooHandler`, `ListFoosResult`
- REST `FooResponse`, `FooListResponse`, `FooCreateRequest`, `FooUpdateRequest`, router `restapi/routers/foos.py`
- Auth `Role.LOWER` / `Role.HIGHER` — the placeholder rank ladder, two positional members, lower first,
  which a project replaces with its own

## Banned vocabulary

Names carried over from a real system are banned outright, in templates, rules and prose alike:
**any real role, tenant, bucket, database, queue, service or product name**, in every spelling it
travels in — snake_case, kebab-case, and the SCREAMING env-var prefix derived from it. A skill that
teaches through one system's vocabulary is unreadable to everyone else on it.

Use the placeholder vocabulary above instead: `Foo`/`Bar` for aggregates (`Baz` where a third is needed), `myapp` for a service's own
package, `myschema` for a library several distributions share, `myrepo` for the repo root,
`myframework` where a rule is about wrapping a framework rather than about that framework. A real
name with no placeholder to map onto gets a row added to the
table above — never an exception here. No tool catches a real name; it is caught by reading the
diff before a commit, so this file states the category and does not list the names already found and
removed.

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
