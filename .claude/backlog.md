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

#### 19. `hex-capability-adapter`'s template is one application's token client
`HttpBarGateway.fetch_token(subject)` and `BarToken` are a specific upstream's shape. A generic adapter
shows one capability call with the house pattern (injected client, status mapped to the catalogue at
the boundary) and nothing a particular vendor supplies. Lens 1, question 2.

#### 21. A conventions skill for the flat family
`hex-conventions` holds path and name derivation, store profiles and multi-context apps. Check what of
that `flat-layered` already covers before adding anything; a new skill is proposed only if the
derivation rules have no owner in the flat family today.

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

#### 26. Audit the test skills the same way
Test skills follow their production skills, so every item above has a test-side echo: the unit-of-work
and session fakes (item 14), the token adapter's test in `hex-test-capability-adapter` (item 19), the
restapi tests (item 24), the template comments (D123, item 30). `hex-test-restapi-auth` and
`hex-test-application-handler/FAKES.md` are the densest in domain nouns. Run `/review-skills` over the
test skills after the production skill each one follows has settled.

#### 28. A single-use helper is a private method in `hex-persistence`, a module function in `python-packaging`
`hex-persistence` rule 11 and its `REPOSITORY.md` rule 23 say a helper used by exactly one method is a
private method, which contradicts `python-packaging`'s "a helper that does not need `self` is a module
function, not a private method". Decide which holds and align the other. The standalone template's
`_row_to_entity(self, …)` never reads `self`, so as copied it already trips `python-packaging`'s hard stop.

#### 29. `hex-project-setup`'s migration bootstrap trails what `flat-project-setup` now states
Block B takes `script.py.mako` as `alembic init` writes it, which renders `typing.Union` forms and an
import order the linter rejects, contradicting `python-style` and `hex-persistence/REVISION.md`. Its
`env.py` disposes the engine only on a clean run, does not refuse offline mode and configures no logging, so
the tool's records reach no configured handler (`python-logging` rule 3). Align it with what `flat-project-setup` now states.

#### 30. Comments left in production templates after D123
Most likely to break `python-style`: `hex-persistence/REVISION.md` (the check-constraint suffix note) and
`hex-restapi-auth/ROUTES.md` (`# read — …`, `# mutation — …`). Also review `hex-persistence/REPOSITORY.md`
(the `cast` reason), `hex-restapi-endpoint/SKILL.md` (the `409 only because …` notes),
`hex-restapi-schema/SKILL.md` (`# mirrors …`) and `flat-persistence/REPOSITORY.md` (the SQLSTATE note).
Test skills were not swept.

#### 31. Command sequences the "a template earns its place by being copied" bullet flags
`flat-persistence/SETUP.md` (the alembic commands) and `python-versioning/SKILL.md` (tag and push) are
sequences a project runs, not files it copies. Also `meta-skill-author` says the skill shapes "add and
remove nothing" (~line 368) while a reference skill omits `Template(s)`; reword it.
`git-branching`'s one-time `gh api` block is a command too; D121 kept it deliberately — decide with the
rest.

## Agreed

### 4. Re-run the short-prompt scenario on the current skills
The maintainer's GLM run with a short `dns_scanner` prompt was made on the skills before the generality
rework. Run it again on current `main` and review the output the same way (layout, module size, which
skills loaded, defects → rules).

### 5. Small leftovers from the generality rework
- `hex-restapi-endpoint/TRANSFER.md` names `ImportFoosHandler`/`ExportFoosHandler`, which no
  `hex-application` template shows — acceptable as "written like any other handler", revisit if a
  review flags it.

### 16. Sweep every skill against the hard-stop test
Sweep every skill's `## Rules` and `## Hard stops` against the new test in `meta-skill-author`.
