# Backlog — catalogue edits not yet made

Each entry is **Proposed** (awaiting the maintainer's decision) or **Agreed** (decided, not yet done).
Remove an entry in the change that does it; record the decision in `DECISIONS.md` as usual.

## Proposed

Found by the reviews of items 6–10, outside what those items changed.

### 11. The webhook's redelivery obligation has no test, and ordering has no word
- `flat-entrypoint` rule 9 now says a redelivery "changes nothing", but no test template pins it for
  the HTTP run function; `flat-test-run-function` rule 3 covers it only in general. At most one test in
  the HTTP wrapper tests, if the reviewers of that skill agree most webhook services need it.
- `HTTP.md` says keeping the newer row under out-of-order delivery is the conflict clause's job, and
  `flat-persistence` shows no such clause. Decide whether that is one sentence in `REPOSITORY.md`
  (an update guarded by the stamp) or stays out as optional.

### Maintainer's read-through of 2026-09-27

Raised by the maintainer reading the skills; evidence gathered, nothing changed yet. Each is a
candidate for `/review-skills`, not a decision.

#### 12. `flat-entrypoint` still speaks the vocabulary of the durable engine it was unwound from
- "Run function" is no industry term. It is the body of the engine's unit of work (an activity) from
  the original `flat-temporal-workflow` era (`ffc8559`), kept when the engine left. The obligation
  (a framework-free, dependency-injected function every trigger wraps) is sound; decide whether to keep
  the name, and if so define it once in `flat-layered`, where the roles are named.
- `guarded` has the same root: it was the loop's `try/except`, and "guarded helper" is still used for
  the unrelated progress-report helper of durable obligation 8 (`SKILL.md:194`, `DECISIONS.md:169`).
  Rule 8 (containment in one named function) stands; the two meanings sharing one word do not.
- The heading `## The run function — shared by every shape (structlog)` and the `structlog` imports in
  the run function and `containment.py` bind the logger in a skill that owns triggers. `python-logging`
  owns the logger; the templates could log through it without naming the library, or not log at all
  (the guard is the only line that must). Same question in `hex-application` (7 mentions),
  `hex-patterns` (4), `hex-restapi-app` (2), `flat-entrypoint/HTTP.md` (2).
- 29 hard stops and 26 rules (15 + 11 durable): the largest skill in the flat family (see item 16).

#### 13. `flat-entrypoint/HTTP.md` is one module of FastAPI doing four jobs
`build_app` holds the error rendering, the unexpected-failure middleware, the validation handler and
the route in one 70-line function. The hex family already splits these (`hex-restapi-app`,
`hex-restapi-endpoint`, `hex-restapi-schema`). Decide whether a flat HTTP trigger points at a shared
split, or reduces to rule 9 plus the smallest wrapper. Either way the file is a lens-1 and lens-3 case.

#### 14. The persistence rules are written twice
`flat-persistence` and `hex-persistence` both state one transaction owner per callable, translating the
driver error at the package edge, the offending field plus the full constraint name in the context, and
constraint names as one contract from one convention. Those obligations hold in any Python project with
a store. Proposal: move them to a universal persistence skill; each family keeps only its shape (flat:
Core writes in bounded batches, no protocol; hex: port-satisfying adapters, entity mapping, revision,
unit of work). This is why hex reads "richer": it adds aggregates, ports and a second transaction
owner, not a different way to store data.
- On `AsyncSession` vs `async_sessionmaker[AsyncSession]` in hex: that is correct and deliberate.
  `FooRepository` takes the factory because it owns its transaction; `FooSessionRepository` takes a
  session because the unit of work owns it (`hex-persistence/REPOSITORY.md:68,152`). The skill should
  say so in one sentence at the constructor, since a reader asked.

#### 15. `flat-project-setup` writes files Alembic generates
`alembic init -t async migrations/postgres` lays `env.py`, `script.py.mako` and `alembic.ini`, and
current Alembic's template already carries the annotated `revision: str` forms. What the skill really
owns is the diff: the connection string read through the component's settings, one import per table
module, `target_metadata`, offline mode refused. Proposal: the init command plus those obligations as
rules, and the `env.py` and `script.py.mako` templates deleted or cut to the lines that differ.
- The directory tree at the top (`SKILL.md:15`) is not in `hex-project-setup`. It restates
  `python-toolchain`'s src layout plus `migrations/postgres/`, which rule 1 states in prose. Make the
  two setup skills agree: most likely delete it.

#### 16. No bound on the size of `## Rules` and `## Hard stops`
`meta-skill-author` bounds the body (~500 lines, then sibling files) and nothing else. Current extremes:
`hex-application` 27 rules, `test-principles` 27 rules and 18 stops, `flat-entrypoint` 26 and 29,
`flat-persistence` 20 and 24. Many hard stops restate a rule with "→ stop". Decide on a bound or a test
(a hard stop only for a wrong turn a rule alone does not catch), and apply it.

#### 17. The mandatory `## Template(s)` produces templates where none is needed
`meta-skill-author:29` already lets a process skill omit it, yet `git-branching` and
`git-commit-message` carry one. `git-branching`'s is a fixup/autosquash/force-push script that the
rules do not require and that differs from this repository's own flow (`feat/` vs `feature/`).
Proposal: a skill has a template only where most projects would copy a file from it. Otherwise the
section is absent, and the reviewer's lens 1 asks whether a template earned its place at all.

#### 18. `when_to_use` is present in 19 skills and absent in 29
Absent across nearly all of `pyhouse-hex`, and in `exception-catalog`, `python-logging`, `python-style`,
`python-versioning`, `test-architecture-rule`, `test-principles`, `flat-test-persistence` and
`flat-test-service-client`. `meta-skill-author` makes it optional and Claude Code only. Decide one way:
either it is dropped everywhere (the `description` must already stand alone), or every skill whose
triggers the `description` cannot hold carries one. The present split is accidental.

#### 19. `hex-capability-adapter`'s template is one application's token client
`HttpBarGateway.fetch_token(subject)` and `BarToken` are a specific upstream's shape. A generic adapter
shows one capability call with the house pattern (injected client, status mapped to the catalogue at
the boundary) and nothing a particular vendor supplies. Lens 1, question 2.

#### 21. A conventions skill for the flat family
`hex-conventions` holds path and name derivation, store profiles and multi-context apps. Check what of
that `flat-layered` already covers before adding anything; a new skill is proposed only if the
derivation rules have no owner in the flat family today.

#### 22. Code blocks nested in list items carry the list's indent
`hex-domain-model/SKILL.md:116` (two spaces) and `hex-test-application-handler/SKILL.md:268` (three)
render correctly but, read raw or copied, give the class body six or seven spaces. No top-level block
has a misaligned indent. Move the blocks out of the lists.

#### 23. `hex-patterns` is two patterns that happen to span layers
It holds compensation and the unit of work, and its template spends the most lines on the unit of
work's SQLAlchemy implementation. Neither is a catalogue of patterns. Decide whether it stays as the home
for cross-layer patterns (then say which belong), or the unit of work moves beside
`hex-persistence`'s session repository and compensation beside `hex-application`.

#### 24. Audit the four `hex-restapi-*` skills and their tests
The maintainer suspects much is buried there. Run `/review-skills` on `hex-restapi-app`,
`hex-restapi-auth`, `hex-restapi-endpoint`, `hex-restapi-schema`, `hex-test-restapi-auth` and
`hex-test-restapi-endpoint`, generality first.
- `TRANSFER.md` (item 5's leftover) is code taken from one application: an import/export CSV pair, a
  10 MiB ceiling, a mixed multipart + JSON route. Most REST services have no file transfer; lens 1
  decides whether it is reduced to rules or deleted.

#### 25. Comments and docstrings inside templates
`hex-wiring/CONTAINER.md` puts a docstring on every provider class and comments on the bindings,
against `python-style`'s default of no comments. Every template the agent copies carries them into the
project. Other heavy files: `hex-test-integration-setup/CONFTEST.md` (22 lines), `hex-test-app-invariants`
(20), `hex-test-restapi-auth/INTEGRATION.md` (19), `python-packaging` (10), `hex-restapi-app` (7). Keep
only a non-obvious *why*; move instructions to the reader into prose.

#### 26. Audit the test skills the same way
Test skills follow their production skills, so every item above has a test-side echo: the unit-of-work
and session fakes (item 14), the token adapter's test in `hex-test-capability-adapter` (item 19), the
restapi tests (item 24), the comments in item 25. `hex-test-restapi-auth` and
`hex-test-application-handler/FAKES.md` are the densest in domain nouns. Run `/review-skills` over the
test skills after the production skill each one follows has settled.

#### 27. Jinja-style placeholders in place of `Foo`/`Bar`
Proposed by the maintainer: `{{ aggregate }}` rather than `FooRepository`. Weighed against it: templates
stop being valid Python, so `tools/check_template_imports.py` and any syntax check stop working; an
agent copying verbatim can leave the braces in; and names still have to be derived (`{{ Aggregate }}Repository`,
the plural, the snake case), which is what `naming` states today. What the proposal gets right is that
some placeholders read as invented concepts (`BarGateway`, `BarToken`). That is a lens-1 defect
(item 19), not the placeholder syntax. Recommendation: keep `Foo`/`Bar`, and cut the templates that make
them read as a fictional domain.

#### 28. A single-use helper is a private method in `hex-persistence`, a module function in `python-packaging`
`hex-persistence` rule 11 and its `REPOSITORY.md` rule 23 say a helper used by exactly one method is a
private method, which contradicts `python-packaging`'s "a helper that does not need `self` is a module
function, not a private method". Decide which holds and align the other.

## Agreed

### 4. Re-run the short-prompt scenario on the current skills
The maintainer's GLM run with a short `dns_scanner` prompt was made on the skills before the generality
rework. Run it again on current `main` and review the output the same way (layout, module size, which
skills loaded, defects → rules).

### 5. Small leftovers from the generality rework
- `hex-restapi-endpoint/TRANSFER.md` names `ImportFoosHandler`/`ExportFoosHandler`, which no
  `hex-application` template shows — acceptable as "written like any other handler", revisit if a
  review flags it.
