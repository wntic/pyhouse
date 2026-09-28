# Decisions

Judgement calls made while reshaping this catalogue, each with its reasoning and how to reverse it.
Most were taken unattended, during work the maintainer had approved in outline but was not watching;
a few were taken after review and say so. They are recorded because the reasoning is the part that
does not survive in a diff, and because a decision nobody can find is one the next person re-litigates.

This file is not a changelog. It holds only choices that could defensibly have gone the other way.

## Settled before execution began

### D1 — Keep the `flat-*` prefix; do not rename the family
Plan 05 costed three options and recommended keeping it. `meta-skill-author:286` already carries a
written decision to the same effect ("`flat-layered` keeps its name — it is the style anchor"), so a
rename would overturn a recorded decision, and the maintainer never asked for one. A rename must ride
with Plan 04 or not happen, so deferring it costs nothing later beyond a second restructuring pass.
**Reverse by:** taking Plan 05 option (b), which is fully costed in that file (32 files, ~262 `flat-`
tokens, 10 directories, 4 manifests).

### D2 — Apply the corrected slash form rather than deferring it
Plan 01 listed "confirm `/pyhouse-universal:naming` against a live install" as an open decision. It is
confirmed: a session with plugins installed lists their skills namespaced (`anthropic-skills:docx`,
`microsoft-docs:microsoft-docs`) while non-plugin skills list bare. Matches the documented behaviour.
**Reverse by:** reverting that one edit in `plugins/pyhouse-universal/skills/README.md`.

### D3 — Leave the upstream licence question alone
`coupling` is a port of `vladikk/modularity` (CC BY-NC-SA 4.0, `Disallow-Training: yes`); pyhouse ships
MIT. This is a maintainer decision, not an engineering task, and it blocks no plan. No file touched.

### D4 — Work on a branch, not on `main`
`fix/catalogue-remediation`. The repo's default branch is `main` and the maintainer is asleep; a branch
keeps `main` untouched and fast-forwards cleanly.
**Reverse by:** `git checkout main && git merge --ff-only fix/catalogue-remediation`.

### D5 — Commit per plan, not per edit
One commit per plan, each with a message naming what changed and why. Keeps the history reviewable and
lets any single plan be reverted alone.

## Taken during execution

<!-- appended as they occur -->
### D6 — Fixed `test-principles`' flat example instead of deferring it
**Superseded by D105.** The flat AAA example this entry fixed left `test-principles` with the flat tree.
Plan 01's own verification flagged `EntitiesRepository`, `record_batch(foo_filtered_table, "foo", …)`
and `entity_kinds_table` in a **universal** skill — source-project vocabulary, banned outright by
CLAUDE.md. The plan's Finding 4 triage had grepped only `myschema|packages/|services/|workspace` and
missed it. Rewrote the example with placeholder vocabulary (`FooRepository`, `bars_table`), preserving
the AAA point it illustrates. Deferring it to Plan 04 would have left a banned name in the universal
plugin across several commits.

### D7 — Fixed one routing edge the plan's census missed
`python-style/SKILL.md:21-22` routes to `hex-conventions` without naming the plugin — exactly the class
Finding 3 fixes, absent from its table. Applied the same treatment.

### D8 — Did NOT propagate `mycommon` into the four abbreviated placeholder enumerations
Plan 01's ripple tail asked for it, but its own Scope section says `meta-skill-author/SKILL.md` is not
touched and `CONVENTIONS.md` gets "one placeholder row only". Those enumerations are abbreviated by
design and defer to the table: `meta-skill-author:251` says to "read that file for the full set rather
than guessing at it". The authoritative row exists at `CONVENTIONS.md:126`. Adding the name to five
more lists is churn for a placeholder used once.
**Reverse by:** adding `mycommon` at `skills/README.md:6`, `:202`, `meta-skill-author/SKILL.md:251`,
`:263`, `CONVENTIONS.md:152`.

### D9 — Corrected a semantic regression the plan introduced
Plan 01 edit 1.4 built `_SRC_OUTSIDE_SCHEMA` from whole member *roots*, so the two firewall examples
swept each member's `tests/` tree as well as its `src/`. An integration test that legitimately names a
table object would have turned the firewall red. Rebuilt the constants to sweep source trees only
(`_SRC_DIRS` globbing `{d}/*/src`, plus `_SCHEMA_SRC`), which preserves the rule and its intent.

### D10 — Relabelled a stale example
`test-architecture-rule`'s `print(` example was headed "Hex example:" after the scaffolds became
standalone / multi-member. It uses the standalone constants, so it is now "Standalone example:".

### D11 — Left a cosmetic phrasing variance between two routing lines
Plan 01 committed "`hex-architecture` (in `pyhouse-hex`)" where plan 02's text would have written
"(in the `pyhouse-hex` plugin)". Substance identical; churning an already-committed line to match a
plan's wording is not worth a commit.

### D12 — `stripe` kept in `naming`, bounded by a note in `CONVENTIONS.md`
`CONVENTIONS.md` whitelists six technology names and bans product names; `skills/README.md:212-213`
separately sanctions `stripe` for `naming`. Two hand-maintained docs disagreed. Took plan 02's
recommended option: one bounded paragraph in `CONVENTIONS.md` permitting a named vendor used purely as
a disambiguation example, with explicit limits (never a subject; no rule, section or template may
depend on it; never travels into a path, package, env prefix or shipped identifier). `naming` untouched.
**Reverse by:** replacing `stripe`'s five uses in `naming` with a whitelisted technology name.

### D13 — Deleted the `dishka` and `uuid7` floor bullets rather than restating them
The `uuid7` bullet said "This catalogue does not use it" while `flat-schema-package` mandates
`uuid6.uuid7()` for every primary key — a false claim cannot be restated library-free, so it went. The
`dishka` bullet was a duplicate pointing the wrong way: `hex-project-setup:126` already states the same
floor fact in the family skill where that binding lives. Both replaced by the plan's library-free
bullet pair. Kept the pair rather than collapsing to one sentence, because the second carries an
obligation the single sentence loses (the floor is chosen once for the whole project).

### D14 — `python-style` is now exactly 500 lines; not splitting it
`meta-skill-author` rule 3 treats ~500 lines as the signal to split into sibling topic files. The file
landed exactly on it. Splitting is a structural change nobody asked for and would churn a file three
plans have just edited. Left whole and flagged: **the next addition to `python-style` should split it.**

### D15 — Deferred a scope question about `-> dict:` in test builders
Two test-helper signatures in `flat-test-schema-package` (`:53`, `:204`) are arguably caught by the new
record rule. Whether the rule reaches test builders or only production boundaries is a real question;
handed to plan 04, which rewrites that file.

### D16 — Added the literature attributions the plan's edit text omitted
Plan 05's option (a) exists so a reader can map this catalogue onto the literature, but its literal
edit named only the terms. Added "after Simon Brown" and "what Fowler calls", since the terms without
their sources do not do the job the option was chosen for.

### D17 — Deferred the `flat-layered` literature sentence to plan 04
Option (a) calls for one sentence in `flat-layered` too. That file is rewritten by plan 04, so the
sentence goes in there rather than being written into text about to move.

### D18 — Storage settings: engine factory, not a settings class per storage package
Plan 04 suggested `flat-persistence`'s single-service form carry its own settings class with a
`MYAPP_` prefix. That contradicts `flat-layered` rules 7 and 8 — a package below the process
definition importing settings, and two classes sharing one prefix. The single-service form is an
engine factory taking the connection string, with the process definition passing it down; the
own-settings-class case moved to the shared-distribution bullet under `## Other bindings`.

### D19 — `FooStorage` writes across two statements
**Superseded by D107.** Plan 04's `FooStorage` was single-statement, but it has to carry the "a write spanning more than one
statement is one transaction" rule and be the subject of the atomicity test. A single statement has no
atomicity to pin. Gave `record_batch` an ordinary parent-and-children shape in one `engine.begin()`.
This is not the deleted registry: no cross-service identity, no junction, no view, no kinds.

### D20 — The record rule reaches test code, but not a table-generic column mapping
**The table-generic mapping exemption superseded by D113.** Handed to plan 04 as an open question. A mapping passed to a `Table`-parameterised bulk helper is
genuinely data — there is no fixed field set for a type to declare. So builders keep a mapping return
but are annotated `dict[str, object]`, never bare `dict`; a builder constructing the service's own type
returns that type. `python-style` untouched.

### D21 — Bumped all three plugins and the marketplace to 0.2.0
Two skills were deleted and two renamed. Shipping that under the version consumers already installed
would silently change what a plugin contains. Plan 04 recorded the bump as unanswered; taken.
**Reverse by:** setting the four `version` fields back to `0.1.0`.

### D22 — Updated CLAUDE.md's "instances to unwind" paragraph
It named the two durable-execution skills and `python-style` as outstanding. Both are now done, so the
instruction was stale and would have misdirected the next agent. Rewritten to record what unwinding
looked like and that the list is clear. Verified `python-style`'s remaining library names are all
legitimate: a structured logger under a stack-named binding heading, and a driver exception used as
the example in a rule that reads without it.

## After the maintainer's review of D18

### D23 — D18 reversed: settings belong to the component, not to the service
D18 kept "a lone service has exactly one settings class", justifying it partly on `flat-layered` rule 7.
That justification was wrong — rule 7 forbids a module *below* the process definition importing
settings, which a component-owned class exposed as a factory does not do. The real constraint was rule
8's own "a lone service has exactly one", a house-style choice, and the maintainer's is the opposite.
Rule 8 now reads: every component that has configuration declares its own settings class in a
`settings.py` beside it, under its own prefix. `flat-persistence` gained the storage half.

### D24 — Stated the nested-prefix trap rather than banning nesting
The rewritten rule said "prefixes are disjoint" while its own template shipped `MYAPP_` and
`MYAPP_STORAGE_`, which are not disjoint — under pydantic-settings a field `storage_dsn` on the outer
class and `dsn` on `StorageSettings` resolve to the same variable, which is exactly the failure the
rule exists to prevent. The nested form is conventional and worth keeping, so the rule now states the
invariant precisely (no variable may satisfy two components' fields) and names the trap: either keep
the stems disjoint, or treat each inner segment as reserved in the classes above it.

### D25 — `@lru_cache` removed from `get_engine` too, not just `get_settings`
Same structural argument — one caller by construction — plus a stronger one specific to engines:
memoising on the connection string pins a live pool for the process lifetime, outliving the shutdown
path and any test that wants to dispose of it.

### D26 — `core/` flattened; the framework-guard exemption now names a module
`core/` was a category word of the kind `naming` rejects. Settings, logging and the guarded helper move
to the service package root. `flat-layered` rule 9's exemption used to be located by package and now
names a module by path, so it stays enforceable; the skeleton shows `durable.py` so the exemption has a
concrete referent. The workspace form keeps a shared package — only the lone-service form flattened.

### D27 — Strengthened `coupling`'s attribution; did NOT add a CC licence notice
The maintainer asked what the upstream licence requires. Position taken: the skill is this catalogue's
own expression of Khononov's *model*, not an adaptation of his *text* — copyright reaches expression,
not systems or methods — so MIT stands and no BY-NC-SA notice was added. Adding one would assert the
adaptation the repo does not believe it made, and would drag NonCommercial into an MIT marketplace.
What was done instead: named the book as the canonical source alongside the blog, stated plainly that
the model is his and this is a restatement, pointed readers at the book for what is only gestured at
here, and reworded the one clause that paraphrased the source closely ("drifting toward a ball of mud").
Recommended to the maintainer, not done here: a one-paragraph courtesy email asking permission, since
that repo offers commercial licensing and the author can settle it definitively.

## Portability audit — phase 0

### D28 — Drop `paths` from the flat skills (taken, pending execution in phase 2)
`flat-layered` teaches that package names are the roles this service chose; `flat-entrypoint` fires on
`**/ingest/**` and `**/jobs/**`. A project that follows the rule never triggers the skills that teach
it. `description` matching still works, so the cost is a slower match, not a lost skill.
**Reverse by:** shipping a prescribed skeleton and deleting the role-naming rule instead — the other
coherent position, but it changes what the family is.

### D29 — Deleted the `foo_parser` and `mycommon` placeholders
`foo_parser` forced every example into a `services/` + `packages/` workspace, which is the shape the
audit found re-growing after each pass. Its job — naming a distribution's own package — is `myapp`'s.
`mycommon` existed only to house the framework guard that phase 0 removed. Renamed the 19 uses:
`myapp` in the three test skills, and in `flat-monorepo`'s two-member tree `myapp/` plus the file's own
angle-bracket form `<second-service>/`, since one placeholder cannot name two members.

### D30 — Added `myframework` as a bounded exception to "technology names stay concrete"
The framework-wrapper rule needs a worked example that names a framework. Naming a real one makes the
rule that framework's rather than the project's — which is precisely how the vendor got into the
universal plugin. A technology a rule is *about wrapping* takes a placeholder.

### D31 — Dropped the per-member framework-wrapper override
`_FRAMEWORK_WRAPPER_BY_MEMBER = {"foo_parser": "durable"}` was an uncapped per-member allow-list in a
file whose rule 6 caps allow-lists at three, and it was legible only to someone who knew the source
repository. Rule 9's obligation — read the role from what the project declared, never from a directory
name — is carried by one constant per declared name.

### D32 — Let the agent update CLAUDE.md's placeholder paragraph
Out of the four fixes' stated scope, but it restated the old definitions, and it is what an agent reads
first — leaving it would have re-grown the defect phase 0 exists to remove.

## Portability audit — phase 1

### D33 — Left `exception-catalog` rule 15 family-shaped
**Closed by D94.** It reconciles the two families' upstream-failure class names (`UpstreamError` vs
`UpstreamUnavailableError`). That is a cross-family naming decision, not something a Django, library or
CLI reader needs, and it was outside the four defects phase 1 targets. Flagged rather than fixed.

### D34 — Compressed `python-style`'s logging prose instead of splitting the file
Phase 1's rewrite would have pushed it past the ~500-line split signal. Splitting would have moved the
allocation rule out of the auto-loaded `SKILL.md` into a sibling nothing loads by default, which costs
more than the length does. It sits at exactly 500 again — **the next addition to this file must split
it**, and that is now true for the second time.

## Portability audit — phases 2 and 3

### D35 — Engine test material went to a second sibling file, not into the entrypoint one
**Superseded by D50.** Folding `flat-test-run-function`'s engine-only test rules into
`flat-entrypoint`'s engine sibling would have put that file near 590 lines, past the split signal, so
the plugin carried two engine sibling files, one per owning skill. Both files are gone; the obligations
they held sit in their owning skills' `## Rules`, and there is no engine file left to merge.

### D36 — `flat-monorepo` stays in the flat plugin for now
All nine of its rules survive a move to a universal `python-workspace`, and nothing in it is
flat-specific. Not moved, because it changes counts in nineteen places and three of its rules currently
lean on `flat-persistence` and `flat-test-integration-setup` for obligations a universal skill may name
only as examples. Stripped of its flat framing in place; the move is a clean follow-up.

### D37 — `flat-persistence` held at exactly 500 lines
Adding its relational precondition pushed it to 504. Bought the lines back from prose restating two of
its own rules rather than splitting — it is template-heavy and a sibling would need a "read this"
instruction the body does not want. **Third file now sitting on the split signal**, with `python-style`.

### D38 — Fixed the indexes myself after phase 2
Both hand-maintained indexes and the flat plugin manifest described the old shape. Phase 2 was
forbidden from touching `pyhouse-universal`, so it reported the four stale rows and I applied them.

## Portability audit — phase 4

### D39 — One placeholder ladder and one tenant claim, added to the vocabulary
The auth pair carried two source projects' role ladders (`MEMBER/AGENT/ADMIN`, `ADMIN/COLLABORATOR`)
and two tenant names (`workspace_id`, `organization_id`), each with a "one app's model" disclaimer —
the audit's proof case for hedging-instead-of-placeholdering. Both replaced by `Role.LOWER` <
`Role.HIGHER` and `tenant_id`, and both added to `CONVENTIONS.md` as real placeholder rows, which is
the sanctioned route. `hex-application` was swept to the same spelling; it had been left out of phase
4's scope and would otherwise have disagreed with the pair.

### D40 — Kept 13 scheme-independent rules in `hex-restapi-auth`, not nine
My brief said "nine portable rules" from the audit's prose; the audit's own enumeration (1–9, 11–14)
is thirteen. Kept thirteen. Three of them name "the verifier" and are vacuous under the gateway
binding, where no verifier exists — they fire correctly under every other binding, and duplicating them
into two places would cost more than the vacuity does.

### D41 — Did not move the assert-strength recipes out of `hex-test-application-handler`
Phase 4's verdict is that four of seven are layer-generic and belong to `test-principles`, which owns
assert strength — and that the section heading duplicates `test-principles`' own heading verbatim,
which is the silent "a rule lives in one skill" failure. Real, but it is a rule-ownership question
rather than a portability one, and it was outside the phase. Recorded for a follow-up.

### D42 — Removed the last reference to a deleted placeholder
`naming` still illustrated env prefixes with `FOO_PARSER_`, months after `foo_parser` left the
vocabulary. Restated in terms of a distribution, a shared library, and a component's own segment.

## Residual defects (after the stop-hook check)

### D43 — `paths` removed from all eight test skills
An identical `paths: ["**/tests/**"]` on eight siblings narrows nothing — it selects no skill over
another, and costs a project whose tests live elsewhere the skill entirely. Same reasoning already
applied to the flat family; I had failed to carry it across. Descriptions were checked to confirm each
still distinguishes itself without the glob; none needed tightening.

### D44 — `flat-monorepo` moved to `pyhouse-universal` as `python-workspace`
All nine rules survive unchanged against a hexagonal member; nothing in it was flat-specific. Counts:
universal 9→10, flat 8→7, total still 42. Three cross-references that *required* flat skills were
handled individually — two restated in place, one deleted outright because it was **dangling**: rule 6
cited `flat-test-integration-setup` for a pytest rootdir trap that skill never mentions, and whose own
template does the opposite. Third fabricated pointer found this session.

### D45 — Assert strength returned to its owner
`hex-test-application-handler` opened a section under `test-principles`' exact heading while the
ownership table names `test-principles` the owner. Five layer-generic recipes moved there, stated
artifact-neutrally; two that genuinely depend on this skill's fakes stayed under a non-colliding
heading.

### D46 — Three files split into sibling topic files
`flat-persistence` 500 → 179 + SETUP/TABLE/STORAGE; `python-style` 500 → 400 + LOGGING; 
`hex-test-integration-setup` 490 → 176 + CONFTEST. Each sibling opens by declaring which numbered
obligations it binds, and each is reached by an explicit "read this" instruction — only `SKILL.md`
auto-loads, so a sibling nothing points at is invisible.

### D47 — Fixed a hard stop that named the wrong owner from inside itself
`hex-test-application-handler` carried a stop citing that same file by name and describing "(this
skill)" as the owner of capability fakes, which it is not. Drafted for another skill and pasted in; it
read as authoritative in both places while being correct in neither.

## The two structural questions

### D48 — `hex-restapi-route-contracts` folded into `hex-restapi-endpoint` (maintainer approved)
It was a modifier on one keyword argument of a decorator the endpoint skill already writes, and
produced no file. Folded as obligations into `## Rules` plus a sibling `CONTRACTS.md` for the tables —
not inline, which would have been 640 lines. The fold also removed a hand-copied duplicate of its
error-code table in `hex-restapi-auth/ROUTES.md`; that file now points at the single table and states
only the codes auth adds. Two copies of one table is the same defect as the two role ladders.

### D49 — Declined the regroup; renamed instead
The audit called `hex-test-discovery-invariants` "four unrelated files in a bag". Reading it, the skill
states a real unifying property in its own opening: none of these tests needs editing when an endpoint
is added or removed. `meta-skill-author` rule 5 permits one skill covering several artifacts a single
change always adds at once, which these are. Splitting would have minted two or three near-empty
skills — the granularity defect the audit was complaining about, not a cure for it.
What was wrong was the name: only the OpenAPI walk discovers anything. Now `hex-test-app-invariants`,
which passes `naming`'s identity-over-mechanism test — discovery is how one of the five gets its
inputs, and would have to change if that walk were replaced; the property would not.

## Removing the vendor SDK

### D50 — The engine binding was deleted outright, not rewritten against another engine
The two engine sibling files were 648 lines, 22% of the flat plugin, and the larger was bigger than the
skill it bound. Everything in them below the obligations was one vendor's SDK spelled out — the API the
model already knows — standing where the rules only this catalogue can supply have to be. The
obligations and the engine-neutral hard stops moved up into `flat-entrypoint` and
`flat-test-run-function` as subsections of `## Rules` and `## Hard stops` that state their precondition
and point at `flat-entrypoint` rule 1 for the earning test; everything else went with the files. No
replacement binding was written for a second engine, because a template that exists to show the shape
of an obligation is the defect being removed, not the thing to re-supply. These skills are meant to
drive code review, where a rule that only fires on one stack is noise.
**Reverse by:** restoring the two files from the commit that removed them and cutting the two
subsections back out; nothing else referenced them by then.

### D51 — Durable obligation 7 kept its loop shape, stated as a consequence rather than a shape
**Obligation 7 merged into durable obligation 6 by D107.** The obligation said the batch loop is "an unbounded loop with an explicit counter, never a bounded loop
with a trailing `return`", which reads as one engine's control flow. The reason underneath it is not:
where a run takes a continuation it never reaches the statement after the loop, so a loop bounded by a
count has its termination condition nowhere and dead code where it belongs. That is true of every
continuation-based engine, so the obligation now states the reason and lets the shape follow, and the
matching hard stop was reworded the same way. The alternative considered was dropping the clause with
the rest of the spellings — rejected because the mistake it catches is the one a reader who has never
run a continuation actually makes.

### D52 — `flat-persistence` partitions by store property, not by store category
Its precondition split "relational and transactional" from "a document store, a key-value store or a
vendor-managed index", which left no slot for a SQL store that is not transactional — a columnar
analytical store has tables and statements but no multi-statement transactions, no named unique
constraints, no conflict clause, and no guarantee that a write is readable when it returns. The
`## Other bindings` escape hatch missed it too: it offered `MERGE` or lock-and-check to a backend
without a conflict clause, and such a store has neither.

The category split was also wrong in detail — rules 6, 9 and 15 sat in the "presupposes relational"
bucket and hold for any store at all.

The precondition is now four questions about the store's properties, each naming the rules that lapse
when the answer is no, with rule 10 called out as holding everywhere while inverting its reason: a bind
-parameter cap is a ceiling, a columnar store's small-write penalty is a floor, and the constant is
named once either way. Nine rules hold for any store, SQL or not.

**Why properties rather than a profile table:** `hex-store-repository` uses profiles because its
vendors differ in *client shape*, and one row captures that. Here the vendors differ in *guarantees*,
and a reader needs to know which guarantee is missing to know which rule lapses — a profile name would
hide exactly the fact the rules turn on.

## The review half

### D53 — The reviewer is a command over a subagent, and not a skill
The catalogue states the rules and nothing applied them to existing code. Three mechanisms were
available and the choice was argued from what each one does, not from taste.

A **subagent** holds the procedure. A review reads a diff, a tree and several `SKILL.md` bodies —
including ones loaded to settle scope and then discarded — and emits a handful of findings. In the
calling session that is thousands of lines spent on a paragraph, and the discarded rules stay resident
afterwards. Isolation is the argument, and it is about context rather than tidiness.

A **command** is the entry point, thin, modelled on `/choose-architecture`: it resolves the target and
renders what comes back, and holds no procedure of its own. Review has to be invoked deliberately
because its natural triggers — persistence, endpoint, repository — are the authoring skills' triggers,
so a description-matched reviewer would fire while someone was writing and compete for the same load.

**A skill was rejected.** It would have to either restate rules, which is the drift failure this
catalogue keeps finding, or carry procedure alone, which `CONVENTIONS.md` puts out of scope as
process-only. It would auto-fire during authoring. And it loads into the caller's context, which is the
cost the subagent exists to avoid. No skill was added, so the counts stay at 41 — universal 10, hex 24,
flat 7 — and neither index gained a row.

The ruleless property is kept by a mechanism rather than by discipline: a judgement the reviewer cannot
attribute to a numbered rule or a hard stop is reported as a **gap in the catalogue**, addressed to the
maintainer, never as a finding. The pressure to invent a rule has somewhere to go that is not the
review.

Three steps come straight from existing skills rather than from the reviewer. Scope is
`architecture-choice`'s, including its "neither" answer and the shapes it names as uncovered.
Applicability is `flat-persistence`'s pattern, D52's four store-property questions, generalised: read
the skill's own precondition, and hold the code only to the rules that survive it. The obligation/
spelling line is drawn by a section: the reviewer reads `## Hard stops`, `## Rules` and precondition
prose, and never `## Template(s)` — which makes D50's reason enforceable, since a rule that only fires
on one stack has no section left to be read out of.
**Reverse by:** deleting `plugins/pyhouse-universal/agents/` and `commands/code-review.md`, dropping
the `agents` key from that plugin's manifest, and reverting the paragraph in `CLAUDE.md`, the packaging
row and note in `CONVENTIONS.md`, the table row in `skills/README.md` and the section in `README.md`.

### D54 — `CLAUDE.md` described a `/commit` delegation that `.claude/commands/commit.md` never had
It said `/commit` "delegates the family detection to a `/style-review` command that is not in this
repo". No such call exists in that file, and family detection is meaningless here — this repository
holds no Python and no service. The two were also aimed at different subjects: `/commit` checks the
catalogue's own contract, while the review command checks a project that installs the catalogue. The
paragraph now says what each one's subject is and that they do not overlap. `/commit` was left alone;
wiring the new command into it would have pointed a Python reviewer at a tree of Markdown.

### D55 — Only `pyhouse-universal` was bumped, to 0.3.0
D21 bumped all three plugins together because all three changed. Here only one did. Bumping `hex` and
`flat` for an unchanged payload makes the version say something untrue, and nothing pins the dependency
by range. The marketplace's own metadata went to 0.3.0, since what it offers changed.

### D56 — What the reviewer cannot check, recorded rather than hidden
The limits below are properties of the catalogue or of review itself, not defects in the artifact.
They are where a human still has to look.

**Only six skills state a precondition the reviewer can answer.** `flat-persistence` (four store
properties), `flat-entrypoint` and `flat-test-run-function` (the earned engine), `hex-project-setup`
and `hex-test-integration-setup` (a relational store backing a repository), `hex-restapi-endpoint` (a
size-cap middleware). For the other thirty-five, applicability is inferred from the skill's
`description` and its `## When to use vs. neighbours` routing, which is weaker evidence, and that is
where a false positive will come from. Each skill that grows an explicit precondition makes the filter
sharper; none of them needs one written for the reviewer's sake alone.

**Intent-based rules are not decidable.** `test-architecture-rule` already names the class — "no `Any`
*unless* at a true external boundary" — and the limit is the same for a reader as for a grep. The
reviewer can see the shape and not the justification, so a rule of this class is checkable only where
the code makes its intent explicit.

**"The rule two callers now share" is the migration signal `architecture-choice` names, and it is not
visible in a diff.** Detecting it needs the second caller, which is usually outside the target. A flat
service growing its first domain rule will read as compliant.

**A rule stated once but obeyed in many places is reviewed only where the target touches it.** Nothing
here audits a whole tree for a rule the diff did not go near; a tree review is a different, larger job
the command asks before starting.

**Silence has two causes and the header distinguishes them only partly.** "No findings" means the
applied skills found nothing; it does not mean the remaining skills would have found nothing had they
been judged applicable. The `Applied:` line is what a reader checks when the silence looks too quiet.

**The reviewer cannot review the catalogue.** Its criteria come from the skills, so a wrong rule reads
as compliance and a missing rule reads as silence. Gaps reported to the maintainer are the only channel
by which either surfaces, and they depend on a reader noticing something the skills do not state.

### D57 — The command is `code-review`, namespaced, not `style-review` (maintainer's call)
It shipped first as `/style-review`, for two reasons that did not survive. The first was to fill a hole
`CLAUDE.md` named — which D54 then established had never existed. The second was a collision with
Claude Code's own `/code-review`, and a plugin command is namespaced: `pyhouse-universal:code-review`
cannot be confused with the built-in.

What decided it was that the short name misled a reader about scope in the direction that costs most.
"Style" reads as formatting and lint — which is precisely the half this reviewer *delegates*, to the
project's own checkers, on `test-architecture-rule`'s grounds. The half it keeps is structural: the
architecture family, layer boundaries and dependency direction, transaction ownership, boundary
translation, the error catalogue. Two of the forty skills it can apply are coding style in the narrow
sense. A name that advertises those two and hides the other thirty-eight stops the reader running it
before the commit that restructures a layer, which is the one commit it exists for.

The cost of `code-review` is the opposite over-promise — the name suggests bugs, races and
vulnerabilities, none of which it looks for. That is carried by the `description` on both the command
and the subagent rather than by the name, and by a `## What this is not` section in the command, so a
clean report is never read as "the code is correct".
**Reverse by:** renaming the command file and the six references listed under D53.

## Versioning

### D58 — `python-versioning` is a new universal skill, not an edit to `python-packaging`
An audit of all 57 files under `skills/` found four fragments touching versions, every one a *token*
rather than a rule: `__version__` named as the sole permitted occupant of an application root
(`python-packaging`, `hex-architecture`), two inert `version = "0.1.0"` lines in `python-workspace`
templates, and one `semver` mention about `plugin.json`. Bump semantics, tags, release notes,
single-sourcing and "what counts as a breaking change to a Python distribution" had **zero** coverage,
so `meta-skill-author`'s duplication stop does not fire and neither does its description-overlap stop.

Four rules it would have restated are referenced instead, each opened and confirmed present first:
what the compatible surface *is* (`python-packaging`, "a distributable package's root *is* its public
API"), retiring a published identifier (`naming`'s frozen-contract list), `code` stability
(`exception-catalog` rule 3), and `__version__` in a root (`python-packaging` rule 6). What this skill
adds in each case is the same missing half — *which bump that forces*.

The catalogue already stated how to **read** someone else's version: `hex-project-setup` block A says a
dependency floor names a known breaking boundary, never a recency guess. It said nothing about
producing your own. That asymmetry is what the skill closes, and the consuming rule stays where it is —
a universal skill may cite a family skill only as an example, so the routing edge names the plugin.
**Reverse by:** deleting the skill directory and reverting one Index line, one README table row, one
ownership-table row and the six counts.

### D59 — Bound to canonical PEP 440, and the SemVer spellings deliberately left out
The obligations are SemVer's clauses 1 and 4–8, which are ecosystem-neutral. The *spellings* are not:
a hyphenated pre-release and a `+` build label are both invalid in a Python version field, and the
failure mode is the dangerous one. Verified by executing builds rather than from recollection —
`version = "1.0.0-alpha.1"` ships as `1.0.0a1` under both common backends with **zero** warnings, and
`1.0.0-1`, a legal SemVer pre-release ordered *below* `1.0.0`, normalises to `1.0.0.post1`, which orders
*above* it. The sort order inverts silently. Meanwhile `1.0.0-alpha.beta` and several of SemVer's own
spec examples fail the build outright. So the skill states canonical form as an obligation (rule 3)
rather than leaving it to the template, because a non-canonical string is either rewritten into
something else or rejected, and which one you get depends on the string.

**No sibling file was written for the PEP 440 tables**, though the research filled one. That is D50's
lesson applied before the fact: a spec the model already knows, spelled out at length, would stand
where the rules only this catalogue can supply have to be. Only the traps that change what a reader
*does* survive, as rules 3, 4, 5, 12 and four hard stops. The skill is 199 lines.

### D60 — The catalogue's four version fields are correct as they are
Applying the new skill to this repository: `pyhouse-universal` 0.4.0 against `pyhouse-hex` and
`pyhouse-flat` at 0.2.0 looks like drift and is not. Each plugin is installed independently, so rule 13
applies — members version independently, and lockstep is right only where one artifact ships them all.
D55 reached the same answer from the other direction, before the rule existed to name it.

Tags are the exception: one artifact does ship all three, so the tag names the marketplace version
rather than any plugin's. `## Releasing` in `CLAUDE.md` states this. **No tags were created** — the
repository has none, and cutting the first one retroactively picks which commit gets to be `v0.4.0`,
which is the maintainer's call and not reversible once pushed.

### D61 — Commits are Conventional Commits, because the type decides the release
The repo's own commit rules were a verb table and a length limit — good prose discipline that carried
no machine-readable claim about what a change *was*. `## Releasing` had just introduced three rows
(major on a skill removed or a rule reversed, minor on a skill added, patch on a correction that
changes no obligation) and nothing connected a commit to a row, so the next number was argued at
release time from memory of what had landed.

Conventional Commits closes that: `feat` is the minor row, `fix` is the patch row, and `BREAKING
CHANGE` is the major row, so the version is read off the commits since the last tag. The type is
therefore load-bearing, not decorative, and a mistyped commit proposes the wrong number.

Two choices the specification leaves open were made deliberately. **Descriptions are lowercase** —
the spec says casing is not case-sensitive except `BREAKING CHANGE` and advises only consistency, so
this is a house choice and is written as one. **A skill plus the index entries it forces takes the
skill's type**, `feat`, never `docs`; the atomic-commit rule already made them one commit, and
splitting the type would be the same defect in another spelling.

The verb table went. It existed to push `Update X` toward `Refactor X`, and the type now carries that
distinction in a position a tool can read. What survived is the requirement underneath it — a
description specific enough to understand without the diff.
**Reverse by:** restoring step 4 from the commit that replaced it and cutting the paragraph added to
`## Releasing`; nothing else reads the types yet.

### D62 — `/commit` ships in a new `pyhouse-git` plugin, not in `pyhouse-universal`
The repository already had a private `/commit` in `.claude/commands/`, whose step 2 checks the
catalogue's own contract and is meaningless anywhere else. What was wanted was a *shipped* command
anyone can install, which is a different artifact with a different subject.

It does not belong in `pyhouse-universal`. That plugin is Python house style, and a commit convention
is language-independent — it holds in a Go repository. More decisively, `pyhouse-universal` is a
dependency of both family plugins, so shipping the command there would mean installing `pyhouse-hex`
for Python skills and silently also changing how commit messages get written. `CONVENTIONS.md` already
pointed at the answer: process belongs under a separate prefix if it is reintroduced.

`pyhouse-git` therefore depends on nothing and is depended on by nothing, which is what lets it be
installed alone and lets the catalogue be installed without it. It ships **no skills**, so the
catalogue's counts and both indexes are untouched at 42.

**Why a command and not a skill.** A skill would auto-fire on description match, which is the right
mechanism for a rule an agent should follow unprompted — but this is a procedure with side effects on
the repository, and a procedure that runs because a description matched is a procedure nobody asked
for. The same reasoning that kept the code reviewer out of a skill in D53 applies here. A skill
carrying the convention without the staging procedure is a reasonable future addition, and is the
obvious candidate for "what else goes in this plugin".

**Starting at 0.1.0, deliberately.** By `python-versioning` rule 9 that withholds the compatibility
promise, which is honest for a plugin whose contents are expected to grow. It stops being honest once
something depends on it.

### D63 — The private command stopped restating the spec
With the shipped command carrying the Conventional Commits template, scope rule, breaking-change form
and description rules, the private one held a second copy — the exact drift failure this catalogue
keeps finding in its own skills. Its step 4 now points at `plugins/pyhouse-git/commands/commit.md`,
which is in this tree and so cannot dangle, and keeps only what is genuinely the repository's own: the
mapping of types onto catalogue artifacts, where `feat` means a skill rather than "a capability".
D61's table moved there rather than being deleted; the spec mechanics around it went.

### D64 — The shipped `/commit` is neutral on merge strategy but refuses to be neutral on choosing one
A commit written by the command survives to the mainline under a merge commit and is discarded under a
squash, where the request's title becomes the message instead. The command covered neither, so a team
that squashes would have got a conventional history up to the moment the first request title was
written by someone who thought the commits were what counted.

Neutrality is right on *which* strategy — merge policy belongs to the repository, and the command
ships to repositories it will never see. It is wrong on whether to pick one. Mixing does not break
version derivation, which was the worry worth checking: the strongest type in a range decides the bump
identically under both. What it breaks is the enforcement point, which sits on the request title under
one strategy and on each commit under the other, so a repository allowing both needs both checks and
usually has one. The section therefore states both, states that either is fine and both together is
not, and tells the reader to detect rather than assume.

This is `architecture-choice`'s posture applied to a different question — decline to prefer, refuse to
let the choice go unmade and unstated.

### D65 — The commit-msg hook is POSIX `sh`, and lives in `git-hooks/`, not `hooks/`
`hooks/` is Claude Code's own plugin convention and means its hook system — PreToolUse and the rest —
which is a different mechanism from a git hook entirely. A git hook placed there would be read by
neither, or by the wrong one. `git-hooks/` says which kind it is and collides with nothing.

POSIX `sh` rather than Python, because the plugin installs into repositories that are not Python
projects and a hook that needs an interpreter the repository does not have is a hook that gets
deleted. `grep -E` throughout for the same reason: basic `grep`'s alternation is a GNU extension that
BSD does not carry reliably, which `test-architecture-rule` had already established for this
catalogue.

**What it deliberately does not enforce.** No type allowlist by default — specification rule 14 says
types other than `feat` and `fix` may be used, so rejecting `perf` out of the box would reject a valid
commit. The allowlist is opt-in through `pyhouse.commit.types`. What is enforced by default is
structure, the blank line before a body, the uppercase `BREAKING CHANGE` token, and a 72-character
subject; only the last is a house choice rather than the specification, and it is configurable.

Merge, revert and `fixup!`/`squash!`/`amend!` subjects are skipped: git writes them itself or a later
rebase consumes them, and a hook that rejects `Merge branch 'develop'` is a hook that teaches people
`--no-verify`. The escape hatch is documented for the same reason — a hook that cannot be bypassed
gets deleted rather than fixed.

Verified against 27 cases before shipping, accept and reject, including the 72/73-character boundary.

### D66 — Installing shared is recommended, with the catch stated rather than buried
`.githooks/` plus `core.hooksPath` puts the hook under review and gives everyone the same one, which
is why it is the recommendation. But `core.hooksPath` is per-clone configuration: every contributor
runs one command, or the hook protects nobody. The command says that out loud and asks to be added to
whatever setup script the repository already has, because the failure mode here is silent and looks
exactly like success.

The command also refuses to report success on a copy — it runs the installed hook against a message
that must be rejected and one that must pass, and shows both. A hook installed without its executable
bit, or shadowed by an existing `core.hooksPath`, exits 0 on everything and reads as working.

**The gap it names rather than hides:** a local hook cannot see a squash merge, where the mainline
message is the request title. That check belongs in CI or the forge's settings, and the command says
so when it installs into a repository that squashes rather than leaving the impression the mainline is
guarded.

### D67 — Versions corrected to one bump per plugin per release, and `v0.5.0` cut
`## Releasing` says a plugin's next number is read off the commits since the last tag, and the
commits since `v0.4.0` had instead bumped versions as they landed, and inconsistently: one `feat`
moved the marketplace to 0.5.0 and created `pyhouse-git` at 0.1.0, a second `feat` bumped nothing,
and a third moved them to 0.6.0 and 0.2.0. The marketplace reached a number no release had earned, and
0.5.0 existed only in a manifest that no tag ever carried.

Applied as the rule states, per plugin, strongest change since `v0.4.0`:

- **marketplace 0.5.0** — it now offers a fourth plugin, which is a minor change to what it offers.
- **`pyhouse-universal` 0.4.1** — under-bumped, not over. It had four touching commits and was still
  at 0.4.0. All four are corrections that change no obligation — a manifest field the schema rejected,
  a list completed with `python-versioning`, two index lines — so the strongest is a patch.
- **`pyhouse-git` 0.1.0** — never released, so this is its first release, whatever its manifest said.
- **`pyhouse-hex`, `pyhouse-flat` 0.2.0** — nothing touched them.

The correction took `chore`, which triggers no bump of its own; a version fix that proposed a further
version would be the same defect again.

`## Releasing` also restated the current numbers, which is how it came to say the marketplace was at
0.4.0 while its manifest said 0.6.0, and to count four version fields when there were five. It no
longer restates them; it says to read the manifests, and it now states the one-bump-per-release rule
explicitly, since the rule was implicit enough to be missed three times in one range.
**Reverse by:** not possible for the tag — a pushed tag is immutable, and a correction is the next number.

### D68 — The convention moved out of `/commit` into a `git-commit-message` skill
D62 named it as the obvious next addition: a skill carrying the convention without the staging
procedure, because a skill is how an agent follows a rule unprompted and a command is how it runs a
procedure someone asked for. An agent writing a commit message by hand, or through any command but
`/commit`, had no convention in context at all.

The skill **takes** the convention rather than copying it. It lived in `/commit`'s step 4 and its
merging section, and leaving it there beside a new skill would have been two copies — the drift D63
fixed once already, one level up. So the rules moved and the command kept only procedure: stage, read
the diff, find out the repository's practice and merge strategy, compose by the skill, commit. It went
from 143 lines to 69. The merging section split along the same line — *that* the convention holds
wherever the surviving message is written is a rule and went to the skill; *how to find out* which
strategy a repository uses is procedure and stayed.

**The prefix is `git-*`**, mapping to `pyhouse-git`, and the name is `git-commit-message` rather than
`git-conventional-commits`: `naming`'s identity-over-mechanism test — the skill's subject is the
message, and Conventional Commits is its binding, with a changelog-fragment workflow named as another.

**One rule is deliberately stated twice.** That a commit which is not a release does not touch the
version is `git-commit-message` rule 2 and is also in `python-versioning`. Neither plugin can depend on
the other — `pyhouse-git` is installed in repositories with no Python in it — so neither can point at
the other as the owner. They are worded from different sides, the commit's and the number's, and
`CLAUDE.md` says in so many words that this is not a duplicate to delete.

**No version was bumped.** Adding a skill is a `feat`, so at the next release `pyhouse-git` goes
0.1.0 → 0.2.0 and the marketplace follows — in the release commit, once, per D67.

The skill's worked example was run through the `commit-msg` hook it describes before shipping, and
passes. A skill whose own example its own enforcement rejects would have been worse than none.

### D69 — The reviewer reads commit messages, and only for what can still change
A commit range carries messages as well as code, and `git-commit-message` makes each message's type the
record a release is computed from, so a mistyped message is a wrong version waiting to be cut. The
reviewer now checks messages against that skill, as a second axis independent of the architecture
family, and only where `pyhouse-git` is installed — a convention held from memory is no better than a
family held from memory.

**The hook checks shape; the reviewer checks meaning.** The `commit-msg` hook cannot see the diff, so it
can never say whether `feat` is true. The reviewer can, and that is all it adds: the type against the
diff, a version edit outside a release, an unmarked break, two changes in one commit, and a scope,
casing or trailer the practice does not use.

A trial run over `v0.4.0..v0.5.0` shaped three clauses the first draft lacked:

- **Practice is the one in force when the commit was written.** Conventional Commits was adopted
  *inside* that range, and "take the practice from before the range" flagged every commit after the
  adoption for following it. A commit that changes the convention and records it where contributors
  read now sets the practice for what follows, and a commit written before a convention is not held
  to it.
- **A published message is reported only for what a release will misread** — a wrong type, an unmarked
  break, a version edit nothing undid. A pushed message cannot be reworded, so a finding about its
  scope or casing is a finding nobody can act on.
- **A hard stop is its rule's trigger, not a stricter rule.** `git-commit-message`'s "the description
  needs 'and' → stop" would have flagged a hook shipped with its own installer, which rule 6's
  exception allows. This holds for every skill, so it went into step 3, not the commit section.

The trial also reported one gap, which is left open on purpose: nothing owns versioning an artifact
that is not a Python distribution. That is outside what this catalogue is for, and `git-commit-message`
rule 2 already stops the version edit in any language.
**Reverse by:** removing `## Commit messages` and the `Commits:` header line from the reviewer, and the
range clause from `/code-review`.

### D70 — `/release` computes the number and cuts nothing unasked
With every commit's type a record of the release it earns (D68), the next version is arithmetic on the
history, and arithmetic is what a command should do rather than a person at release time. `/release`
takes each commit since the last tag, classifies it by `git-commit-message`'s table, attributes it to
the members whose directories it touches, applies the strongest classification once per member, and
moves the aggregate after them. That is the whole of D67's correction done mechanically, so it cannot
be done per commit again.

**Whether to release is not in the history**, so the command proposes and stops. It cuts — one
`chore(release)` commit editing only the named version fields, and an annotated tag — only on an
explicit yes, and pushes only when asked in so many words. An agent may suggest a release and never
cut one: a pushed tag is irreversible, and "the task looks finished" is not a release decision.

Three defaults, each overridden by a rule the repository states for itself:

- **Below 1.0.0 a break bumps the minor, and 1.0.0 is never proposed.** `python-versioning` rule 9
  makes reaching 1.0.0 the act of making a promise, which no commit type can decide.
- **A commit it cannot classify is listed and asked about, never guessed.** An under-counted break
  ships as a compatible release, which is the one error the whole scheme exists to prevent.
- **It writes no release note.** `python-versioning` stops a note generated from the commit log; the
  tag annotation names the bumps and is not a note.

It lives in `pyhouse-git`, not `pyhouse-universal`, because nothing in it is Python — a manifest may be
`package.json` or `Cargo.toml` — and `pyhouse-git` depends on nothing.

`CLAUDE.md`'s marketplace rule said the aggregate moves "when a plugin's minor does", which left a
patch-only release with no number for its tag. It now moves by a patch then.
**Reverse by:** deleting `plugins/pyhouse-git/commands/release.md` and its mentions in the indexes,
the manifest, `git-commit-message`'s neighbours and `CLAUDE.md`.

### D71 — `git-branching` states what holds under every strategy, and binds the lightest
The git plugin covered what a commit says and how a release is cut, and nothing covered how a change
travels between them — yet an agent branches, rebases, force-pushes and deletes branches constantly,
and each of those is where work is lost. `/release` already stopped on "not on the branch releases are
cut from" with nothing to tell it which branch that was, and `git-commit-message` rule 9 said to pick a
merge method without saying how.

**No strategy is named as correct.** GitHub Flow, trunk-based development and GitFlow are all legitimate,
and a skill that picked one would fail the portability test and be a manual the model already knows.
The rules are what holds under all three — one releasable mainline, the method recorded once, the
short-lived branch, history made true before landing and never rewritten after it, deletion only of
what landed. The template binds the lightest, short-lived branches with every commit kept, and the
other two are `## Other bindings`. GitFlow's extra branches are rule 7's exception, earned by a release
that must stabilise while work continues or by an old line still maintained.

**Rule 5 is "history someone else may have built on", not "pushed history".** The stricter form forbids
cleaning your own request branch after pushing it for CI, which is the ordinary case; the lease is
what keeps the looser form safe.

**Rule 4 is the reason keep-every-commit works.** Under it every branch commit lands, so a `fix` to a
`feat` on the same branch would record a defect no release carried. Folding it with `--fixup` is the
curation a squash would do, done by whoever still knows what each commit was. The template spells the
fold `GIT_SEQUENCE_EDITOR=: git rebase -i --autosquash`: run against git 2.39.5, `--autosquash` without
`-i` exited successfully and left the `fixup!` commit in place — it takes effect without `-i` only from
git 2.44. The `commit-msg` hook was run against `fixup!`, `squash!` and `amend!` subjects and accepts all
three, so fixups remain usable wherever it is installed.

**Rule 8 carries a precondition, as `python-versioning` does.** A maintenance branch is earned only
where something runs a version other than the latest; for a service deployed from its newest tag
that never happens, and every fix ships as the next number.

`/release` now takes the mainline from the repository's record, and routes its release commit through a
request where the mainline takes changes no other way. `/commit` offers a branch before committing
onto such a mainline.
**Reverse by:** deleting `plugins/pyhouse-git/skills/git-branching/`, its index rows and counts, and the
pointers in `git-commit-message`, `/release` and `/commit`.

### D72 — A pre-release review, fixed in verified batches rather than by hand
Before the catalogue was used on real projects, eight read-only agents reviewed it: five against the
portability gate plugin by plugin, three for how the skills fit together (citations and ownership,
conflicting rules, an end-to-end walk of five project shapes). About a hundred findings came back. The
portability problem an earlier review had fought — one project's engine and names hard-wired into
rules — was essentially gone; what remained was **template code that did not run against the library it
binds**, skills contradicting one another where a template met a universal rule, and a few coverage
gaps. The import checker could not see the first kind: every import resolved, and the code still failed.

The fix ran as batches that owned disjoint files, each on its own branch, each checked by a second agent
that had not written it and rebuilt the templates into a real project — mypy strict, the test suites
against real Postgres, MinIO and Qdrant containers, migrations up and down, and mutations proving a test
goes red on the defect it claims to guard. A final verification assembled every template of each family
into one project. What that last step found is the lesson worth keeping: **templates reviewed one skill at
a time pass; templates copied together did not** — five settings classes named and never defined, a
repository that did not satisfy its own port, a response schema without the field every test asserted.
**Reverse by:** nothing to reverse; the decisions it produced are D73–D78.

### D73 — The house interpreter floor is 3.13, a choice rather than a consequence
`python-style` claimed 3.10 was the floor and that nothing in the catalogue needed more, while templates
used `StrEnum` and `datetime.UTC` (3.11). The floor is now 3.13 and stated as a house choice — one floor
means every template runs as pasted — with `type` aliases replacing `TypeAlias`. A project may raise it,
never lower it. The commits carry `!`: a project on 3.10–3.12 that complied no longer does. *(Narrowed by
D79: the floor applies to new projects, an existing one below it is not a violation, and the
templates type-check from 3.12 — "every template runs as pasted" overstated what 3.13 buys.)*
**Reverse by:** lowering the three settings in `python-style`, both setup skills and `python-workspace`,
and rewriting the 3.11+ forms in templates.

### D74 — One class per module is capped by a test, not a list of exceptions
Every new multi-class case had to argue its way onto a list. `python-packaging` now states a test:
several classes may share a module only when all are declarations (no state, not injected, no
lifecycle), they change as one closed set, and the module is named for the set. A class with behaviour
always has its own module. Two allowances remain: a private declaration that never leaves its module,
and a module whose name a framework dictates (Django's `models.py`), which is what makes the universal
skills read correctly on a framework tree. An application's root `__init__.py` now stays empty — a
module-level `__version__` read is building something at import — which supersedes the root-`__version__`
occupant D58 refers to. The flat catalog became the module `exceptions.py` for the same reason.
**Reverse by:** restoring the two-item list in `python-packaging` and the root-`__version__` carve-out.

### D75 — Swallowing is defined, and compensation is its one named exception
Three skills could not be satisfied at once: `hex-patterns` swallowed a failed undo with `pass`,
`exception-catalog` forbade swallowing, `LOGGING.md` let only the stopping scope log. `exception-catalog`
now defines swallowing — catching a failure and neither re-raising it nor logging it as the scope that
stops it — so a loop that logs a failed run and carries on is stopping, not swallowing. Best-effort
compensation is the one case where a scope that re-raises also stops a second failure: it logs one
warning for the failed undo and re-raises the original. A `*_best_effort` method that drops its own
failure is a hard stop. An upstream rejecting the service's own credential is an `UpstreamError`;
`UnauthorizedError` is for a credential the service's caller presented.
**Reverse by:** deleting rule 15 (was 16) and the subsection from `exception-catalog` and the matching section of
`LOGGING.md`.

### D76 — Names that denote a role are not vague nouns
`naming`'s vague-noun stop fired on `…Handler`, `…Result`, `…Payload` and "`Service` anywhere" — names the
families require. It now lists the role suffixes an architecture defines and allows them when the subject
is present and the class plays the role; a framework-defined word (`Manager` on a Django manager) is
allowed on the same terms.
**Reverse by:** removing the role-suffix section and its hard-stop carve-outs from `naming`.

### D77 — A service with no invariants that answers HTTP is flat, and flat can now be set up
`architecture-choice` sent a service with no invariants to flat and said a flat service "may expose a small
HTTP surface", yet flat had no HTTP entrypoint and hex refused the service — the most common internal
service had no home. `flat-entrypoint` gained an HTTP shape: a thin framework wrapper around the same run
functions, errors rendered once, templates in `HTTP.md`. `architecture-choice` now routes a service that
serves requests over data it stores without rules of its own there. The flat family also had no setup
skill, so `flat-project-setup` was added (pyproject, toolchain, dependency floors each justified by a real
break, the Alembic bootstrap); the catalogue is 45 skills.
**Reverse by:** deleting `flat-project-setup` and the HTTP shape, and the routing sentences in
`architecture-choice`; restore the counts.

### D78 — Templates name the vendor they bind, and one aggregate has one shape
The client-style store template used a `store_sdk` that was Qdrant with the name removed, down to its
port — unrunnable, and a vendor disguised as generic. It now binds `qdrant-client` under a heading that
says so *(superseded by D79: the vector-store binding is removed)*; key-value stores get their own narrower port (`IFooArchive`, now `IBazRepository` — D79) because they cannot answer the
aggregate port's queries. Across the hex family `Foo` is `Foo(id, name, bar_id)` in every template *(superseded by
D108: `Foo(id, name, note)`, with no reference to `Bar`)*, every
settings class a template constructs has a body and a provider, and settings are constructed at exactly
three composition roots (the container, the migration environment, the test infrastructure) *(D79 names
them by role instead, since a hex service need not have a migration environment)*.
**Reverse by:** not advisable — each of these was a template that did not run as copied.

### D79 — The vector store leaves, and optional adapters stop spreading through the base
D78 answered a disguised vector store by naming it. That fixed the disguise and kept the thing
disguised: a vector index is a workload most services never have, and naming it honestly made it
spread — a template, a port, settings, a container binding, session fixtures and contract tests across
the hex family. It was the durable-execution engine's mistake again, one level down. The reason it
survived two rounds of review is the lesson worth keeping: the reviewers flagged the disguise; the fix
plan decided to bind the vendor; every later verifier then checked the work **against the plan**, so
each round made the vendor more complete and none asked whether it belonged. **A plan's decisions
are held to the portability gate themselves, not only the text that carries them out** — a later
verification re-gated every decision and found two more to narrow.

- `hex-store-repository` keeps one non-relational binding: the Redis key-value form. A search index,
  vector or full-text, is a bullet under its `## Other bindings`.
- The key-value example holds a third placeholder aggregate, `Baz`, behind a narrower
  `IBazRepository` — `Foo` and `Bar` are relational in every other template, and one aggregate in two
  stores is what `hex-store-repository` rule 1 forbids. `Baz` is a new row in `CONVENTIONS.md`.
- The same spread came through the two files every hex project copies. `hex-wiring`'s container
  template bound every adapter the catalogue defines, and the root integration conftest wired a blob
  store into `real_app` *(D108: the base now ends at the per-test `container`, and `real_app` is itself the REST
  add-on)*. Both are now a relational **base**: each optional adapter carries its own
  container binding in the skill that owns the adapter, as JWT already did, and its test fixtures are
  an add-on section of the integration conftest that a project adds only when it has that store.
- Settings are constructed at composition roots named by role — the process's container, any tool that
  loads configuration outside it, test infrastructure — with the migration environment as the usual
  example, because a hex service need not have a relational store at all.
- The 3.13 floor is a house choice for new projects. The claim that templates stop being correct below
  it was false (they type-check and lint under 3.12), and an existing project below it is no longer a
  violation; a floor is raised deliberately, never lowered.

**Reverse by:** reinstating a vector binding would need a workload that most projects share, which is
the bar it failed; the base/add-on split reverses by folding each adapter skill's binding snippet back
into `CONTAINER.md` and the conftest's add-on sections back into its base.

## The flat family, after a service was generated from it

Several of this round's rules were written against defects in a service an agent generated from the
flat templates. Where the skills spoke, it followed them verbatim; where they were silent — what a
second store looks like, what a component with settings looks like, what a run may hold while it runs
— it improvised. This round closes those silences, renames what the catalogue had named against its
own rules, and records why. The entries describe each failure as the rule states it, not the service.

### D80 — The flat data-access class is `FooRepository`, not `FooStorage`
`naming` gives the class that owns a record's data access the suffix `Repository`; the flat family
called it `FooStorage`, and nothing recorded why — D19 used the name without deciding it. The only
difference from the hex case is that no port stands in front, and the suffix names the role, not the
port. `naming` now says so: `Repository` with or without a port, the `I` only on a port, and
`FooStorage`/`FooStore`/`FooDao` a second word for one concept. The module is `foo_repository.py`,
the topic file `REPOSITORY.md`, the test `test_foo_repository.py`. `StorageUnavailableError` and
`StorageWriteRejectedError` keep their names: they name a failure of the store, not the class. The ban
reaches only the class owning a record's data access: an adapter for one capability is named for what
the capability does, so hex's `S3FooStorage` behind `ICanStoreFoos` stays, and `naming` says so *(superseded
by D108: the S3 adapter template is gone, and `naming` states the exception with no vendor in it)*.
**Reverse by:** renaming the class, module, topic file and test back, and removing the flat sentence
and the widened table row from `naming`.

### D81 — The data-access package is named for its technology, one per store
`src/myapp/storage/` answered one store and left the second unanswered, and an unanswered question is
answered by improvisation (D88) — a second store's settings and connection added to the first's
package. The package is now named for the
store — `postgres/` — which makes the second one obvious (`clickhouse/` beside it, with its own
settings, connection factory and migration history), and `flat-layered` rule 4 and `flat-persistence`
rule 17 state it. The settings follow: `PostgresSettings`, `get_postgres_settings()`, `MYAPP_POSTGRES_`.
This supersedes the single-package reading of D18; the settings class inside the package that D18
moved out came back earlier and stays.
**Reverse by:** renaming `postgres/` back to a role name and deleting rule 17 and its hard stop; the
second-store question then has no answer again.

### D82 — A configured external system is a package holding its client and its settings
The process's `Settings` carried `foo_api_url` and `foo_api_timeout_seconds`, fields of a component
that is not the process — the thing `flat-layered` rule 8 forbids, in its own template. The client is
now `services/foo_api/` with `foo_client.py` and `settings.py` (`FooApiSettings`, `MYAPP_FOO_API_`),
and the process's own class holds only the process's fields, possibly none.
**Reverse by:** folding the two fields back into the process's `Settings`, which reinstates the
contradiction with rule 8.

### D83 — The client is handed one pooled transport, and a token is refreshed
The client built its own HTTP client inside each method: a new connection per call, no pool, and a
stub reachable only by patching the library. `FooClient` now takes an `httpx.AsyncClient`, which the
process definition builds once and closes when the process ends (`flat-layered` rule 14); a test
builds the same client against a stub base URL. A credential with an expiry is refreshed on the
transport, once, on expiry or rejection (rule 15): a login token cached for the process's life passes
every short test and fails the first run after it expires.
**Reverse by:** giving the client `base_url` and `timeout_seconds` again; the pool and the refresh
obligation go with it.

### D84 — Migrations are data at the distribution root, one directory per store
Revisions sat under `migrations/versions/`, a layout with no room for a second store's history, which
leaves the second history to land wherever the author guesses — inside the package under `src/`, run
by a hand-written loop, among them.
`alembic.ini` stays at the distribution root with `script_location = %(here)s/migrations/postgres`;
another store's history goes in `migrations/<store>/`, applied by a tool that speaks it, and a
hand-written runner is allowed only where no tool fits and must do what one would — record applied
versions, apply in order, stop at the first failure, never run twice at once (`flat-persistence`
rule 20). The first wording demanded a lock the store provides, which some stores lack; the exclusion
may equally come from the tool's own lock or from the deploy — one migration job per deploy, never
every replica at start-up. It also put the runner in the package and the files at the root, which a
built wheel does not ship together, so the history now ships with whatever deployable applies it and a
runner takes the directory as a parameter.
**Reverse by:** pointing `script_location` back at `migrations` and deleting rule 20; hex keeps its
own `migrations/versions/` either way, since a hex service's second store is a separate question.

### D85 — No empty baseline on a greenfield chain
Both setup skills wrote an empty `0001_baseline` so the chain had a root. Alembic needs no such root:
`upgrade head` and `downgrade base` succeed on an empty chain, and the first real revision gets no
parent. The empty revision was a no-op every database replays forever. A baseline now exists only over
a schema that already exists, holds that schema as frozen hand-written DDL, and is stamped on the
databases that have it. `flat-project-setup` and `hex-project-setup` state it in their own words.
**Reverse by:** restoring the empty template in both setup skills; nothing else depends on it.

### D86 — The linter bounds function size and complexity, with the thresholds written down
Nothing in either setup skill measured a function's size, so an oversized one passed every check. Both
setup skills now select C901 and PLR0911/0912/0913/0915/0917 with every number written: complexity 10
(McCabe's published ceiling), 12 branches, 6 returns and 50 statements (pylint's long-standing
defaults), and arguments capped twice — 5 positional, 7 in all — because a keyword-only argument names
itself at every call site; the flat bulk-write helper takes three positional and four keyword-only,
which is the shape the split permits. Numbers equal to the tool's default are written anyway, as the
line length is, so they do not move when the default does. A function over a bound is split, never
suppressed. Module length has no lint rule and stays a review matter.
**Reverse by:** dropping the codes and the two tables from both setup skills, with flat rule 11 and
hex rule 10.

### D87 — Revision files ignore the statement count, and nothing else
A revision's body is generated DDL — one statement per column and constraint — so a wide table trips
PLR0915 with no function to split. Both setup skills exempt that one code per file for revisions
(`migrations/**/versions/*.py` in flat's layout, `migrations/versions/*.py` in hex's). Complexity,
branches and arguments stay on: a revision with branching logic is still authored code.
**Reverse by:** deleting the per-file line and the sentence beside it in both skills.

### D88 — Templates are copied, so they show a house pattern and the common variants
**Rule 16 superseded by D95.** An agent copies a template verbatim — comments, constants and all — and improvises wherever a skeleton
is silent. `meta-skill-author` now states it three ways. Rule 4: a
template is copied, not read, so a comment in it must be true in the reader's file; the API a version
floor relies on qualifies, which is why `flat-project-setup` rule 3 keeps its reason beside the floor,
and only explanations of the template itself go to prose. Rule 15: a template shows the house pattern
around a minimal vendor call, never the vendor's manual. Rule 16: a skeleton shows the common variants
— a second store, a component with its own settings — one line each, because an unasked question gets
answered by improvisation.
**Reverse by:** deleting rules 15 and 16 and the comment clause of rule 4; the skeleton lines they
justified can stay.

### D89 — What a run holds while it runs is bounded, whatever triggers it
Four failure modes share one cause — the family said what a run is, never what it may hold while it
runs: a whole upstream source loaded into memory and deduplicated with an in-process set; a progress
marker written while the rows it confirms still sit in a buffer shared with another unit; a local
position file overwritten in place, its unreadable remains caught inside the loop's guard so the
process stays up doing nothing; and a fan-out whose first failure cancels every other unit.
`flat-entrypoint` rules 10 to 13 state the four obligations — bounded memory, marker after data, atomic local state read at startup, fan-out that awaits every unit and fails after.
The loop guard moved to its own module, `entrypoints/containment.py`, and names the run it contains.
`flat-persistence` states where its columnar write floor meets rule 11, since that floor is the pressure
that pooled units in one buffer: a buffer spans units only if each unit's marker follows its flush.
**Reverse by:** deleting rules 10 to 13 and their hard stops; the defects they name come back
unflagged.

### D90 — Deduplication belongs to the store, and a cursor carries a total order
**The collapse by the normalized key, and `list_after` as the worked case, superseded by D107.** Two more, both in data access: looking up which rows already exist before writing each chunk — a round
trip per chunk that still admits the duplicates two concurrent runs write — and paging a table by
timestamp alone, which silently skips every row sharing a timestamp at a page edge, and a batch shares
one. `flat-persistence` rule 18 leaves deduplication to
the store's write-time conflict clause or merge-time engine; rule 19 orders a resumed read by a total
order and carries all of it in the cursor. `FooRepository.list_after` is the worked case, and
`flat-test-persistence` pins it across a page edge inside one timestamp.
Rule 18 then gained two clauses (the `LEAST`/`GREATEST` spelling reduced to one sentence by D107). An earliest, latest or aggregated column (a first-seen time) is
resolved by the conflict clause's `LEAST`/`GREATEST` or a merge engine that aggregates — a generated
service had looked rows up before every insert only to keep a first-seen time. And inputs sharing a key
are collapsed by it before the statement: Postgres refuses to update one row twice in one statement
(SQLSTATE `21000`), and `record_batch` given `alpha` and ` ALPHA ` failed as `StorageUnavailableError`.
`record_batch` collapses by the normalized key, last one winning, and `flat-test-persistence` rule 13
pins it. The "no conflict clause" bullet no longer offers lock-and-check, a read-before-write rule 18
forbids; such a store carries rule 12 as a `MERGE` or leaves resolution to merge time.
**Reverse by:** deleting rules 18 and 19, `list_after` and its test.

## Generality pass — templates reduced to what most services have

### D91 — No family-wide exception catalogue; one generic template in `exception-catalog`
`flat-layered`'s `CATALOG.md` defined six classes with hard-coded `http_status` for a family where an
HTTP entrypoint is optional, and `exception-catalog` carried a flat template and a hexagonal one with
eight example classes — a universal skill holding family material. Exceptions are a language-level
concern: `exception-catalog` now shows one stdlib template (the root with `code` and `context`, two
bare subclasses) and `http_status` as an optional field added where the service has an HTTP
entrypoint. Every family template imports only the class it raises from the reader's own
`exceptions.py`; the one reader of `http_status` is the HTTP boundary. Every rule is kept; rule 6 now
speaks of any added field, and rule 13's worked example follows the new subclass.
**Reverse by:** restoring `CATALOG.md` and its pointers in `flat-layered`, `flat-entrypoint`,
`HTTP.md` and `REPOSITORY.md`, and the two templates in `exception-catalog`.

### D92 — The fan-out and shared-wiring templates are rules only
`FANOUT.md`, its test template in `flat-test-run-function` and `entrypoints/wiring.py` were each added
as a template for one defect a generated service showed; most flat services fan out over nothing and
run one process definition. `flat-entrypoint` rules 13 and 14 stay as written; `flat-test-run-function`
rule 7 is one sentence, and its fan-out hard stop is deleted. The loop and the HTTP process definition
build their client and engine directly and dispose the engine in a `finally`.
**Reverse by:** restoring `FANOUT.md`, the fan-out test template and hard stop, and the `wiring.py`
template with the loop and HTTP process definitions importing from it.

### D93 — The client template is one call, with no pagination loop
`FooClient` had a cursor-paging generator beside its single fetch — one upstream's shape. It is now one
method, `fetch_foos`, translating transport and parse failures at the boundary, and `run_once` writes
what that one call returns. Bounded memory stays `flat-entrypoint` rule 10, stated in one sentence
beside the run function; the template no longer accumulates, so it no longer needs to show how.
`flat-test-service-client` and `flat-test-run-function` test that one call and nothing more.
**Reverse by:** restoring `fetch_pages` and the per-page loop in `run_once`, with the paging tests.

### D94 — `exception-catalog` rule 15 deleted; the rules after it renumbered
It reconciled `UpstreamError` with a flat `UpstreamUnavailableError` that no skill defines since D91,
and its "no `http_status`" contradicted `flat-entrypoint`'s `HTTP.md`. Closes what D33 left open. Rule
16 (swallowing) is now rule 15, and the citations of it moved with it. Rules 13 and 14 lost their HTTP
walk-through and RFC-7235 detail to the HTTP owners; the family table became one sentence; the
compensation code block is `LOGGING.md`'s alone.
**Reverse by:** restoring the rule as 15 and renumbering swallowing back to 16.

### D95 — `meta-skill-author` rule 16 reversed: a skeleton carries only common lines
"Show the common variants — a second store, a component with its own settings" pulled every skeleton
toward the one sample those variants came from. A skeleton now carries only lines most services of its
family have; a variant is one line marked with the condition that earns it, or one sentence of prose.
Supersedes rule 16 as D88 stated it.
**Reverse by:** restoring the "common variants" wording in rule 16, its hard stop and both indexes.

### D96 — The review criteria live in `.claude/review/QUESTIONS.md`
Earlier reviews graded skills against `meta-skill-author`'s format and one sample application. The
criteria — generality first, deletion a finding — are one repository file that `/review-skills`, the
reviewer agent and `CLAUDE.md` point at; no shipped skill names it.
**Reverse by:** deleting the file and the pointers to it, and reviewing against `meta-skill-author`
alone.

### D97 — `python-workspace` rule 9 folded into one sentence
"Infrastructure with its own schema owner gets its own datastore" was a rule most workspaces never
reach. It is now one sentence in the paragraph on members sharing a store, which keeps the
`compose down -v` hard stop backed; the rule and its compose walk-through are gone, and rule 8 applies
only where a member resolves settings files against the working directory.
**Reverse by:** restoring rule 9 and pointing "rules 1–8" back at 1–9.

### D98 — The framework firewall is `flat-layered` rule 9's, in standard form, with no template
`test-architecture-rule` rule 9 lost its framework-wrapper walk-through and its multi-member framework
constants, and a copy of that template briefly sat under `flat-entrypoint` shape 2. Both are gone. Rule 9
of `flat-layered` holds for any framework, HTTP included, and is enforced by a standard-form firewall
that forbids the framework's import outside the declared wrapper package; only an earned engine adds its
one allow-list entry, the guarded helper of durable obligation 8. `test-architecture-rule` rule 9 keeps
the general obligation — a role's name read from a declared constant, one constant per name.
**Reverse by:** restoring the framework constants and test to `test-architecture-rule` and pointing
`flat-layered` and `flat-entrypoint` back at it.

### D99 — Each family lists what is worth a firewall in its own architecture skill
The two "What is worth a firewall" lists in `test-architecture-rule` were family material in a
universal skill. The hex list is under `hex-architecture` rules, the flat list beside `flat-layered`'s
import contract; `test-architecture-rule` says in one sentence where each family keeps it. `print(`
left both lists — it is the linter's (ruff `T201`), and the skill's own hard stop forbids restating the
linter — and the allow-list example became `sys.exit(` outside the entry point.
**Reverse by:** moving both lists back under `test-architecture-rule` `## Rules`.

### D100 — `CONVENTIONS.md` "Read models" removed
It was guidance for a skill that does not exist, and `hex-application` already owns the read-model
versus write-model rule. The README backlog entry for a read-model skill went with it.
**Reverse by:** restoring the section and the backlog entry.

### D101 — `coupling`'s worked example is a library's public surface
The shared-schema monorepo example taught one repository shape as the case the rule is easiest to see
in. A library's public surface against its internals is a case every reader has, needs no workspace and
no store, and leaves the monorepo as one of the cases the same counterbalance decides.
**Reverse by:** restoring the shared-schema monorepo example.

### D102 — The hex logging table lives in `hex-architecture`
Which layer logs is a fact about the hexagonal layers, so the table moved from `python-style` to
`hex-architecture` (*Who logs, by layer*), with a checkable rule and a hard stop. `python-style` keeps
the universal log-once rule and the level guide in `LOGGING.md`; `hex-restapi-app`, `hex-test-domain`
and the catalogue README point at the table's new home.
**Reverse by:** moving the table, its rule and its hard stop back to `python-style`.

## Universal owners — settings, the toolchain and the test constitution

### D103 — `python-settings` owns settings from the environment
Settings rules sat twice, in `hex-wiring` (with `SETTINGS.md`) and in `flat-layered`, worded
differently and each applicable to every Python program. They are one universal skill now;
`hex-wiring/SETTINGS.md` is deleted, `hex-wiring` keeps where a settings class is built and bound, and
`flat-layered` keeps that a configured component is a package with its own class, built by the process
definition. Where the two disagreed, flat's rule won: **a tunable with no single right value carries no
default** (rule 5), hex's defaulted pool sizes having been one deployment's tuning frozen into a
template. So the relational store's pool sizes are required, and pre-ping is not a setting at all — the
engine factory passes it literally. `DbSettings`, the engine and the relational repository
binding moved to `hex-persistence/REPOSITORY.md`, beside the adapter that reads them, so the base
container binds no store — every store's binding now lives with its adapter, as the add-ons' already
did. Rule 15 (a value chosen per invocation is an argument, not a setting) is new: a CLI tool is in
scope, and there the confusion is the common one.
**Reverse by:** restoring `hex-wiring/SETTINGS.md` and the settings halves of `hex-wiring` and
`flat-layered`, defaulting the hex tunables again, moving `DbSettings` and the relational binding back
into `hex-wiring/CONTAINER.md`, and deleting `python-settings` with its index lines and ownership row.

### D104 — `python-toolchain` owns the configuration every distribution carries once
The src layout, the ruff selection and its written thresholds, the sanctioned suppressions, strict
mypy, the line length, development dependency groups and the dependency-floor discipline were stated
in both `hex-project-setup` and `flat-project-setup`, and a library or CLI tool with no family had no
home for them at all. They are one universal skill now. The family setup skills keep only what differs
by family — which libraries each role brings with the floors their own templates rely on, and the
migration bootstrap. The inline type-ignore policy is `python-style`'s (**Type suppressions**:
fix first, an ignore is the last resort and names its code and reason); `python-toolchain` owns only
the per-package missing-stub override. With that, flat's blanket ban on any inline `# type: ignore` or
`# noqa` under `src/` is gone: lint suppressions are the closed list `python-toolchain` rule 5
sanctions (D106), and type suppressions follow `python-style`.
**Reverse by:** restoring the toolchain blocks to both `*-project-setup` skills, restoring flat's
inline-suppression hard stop, moving the type-ignore policy back beside it, and deleting
`python-toolchain` with its index lines and ownership row.

### D105 — `test-principles` is family-neutral
The constitution carried two family trees and two substitution ladders, so a library, a CLI tool, or a
project with one family plugin installed read half a skill about something it did not have. The hex
tree moved to `hex-test-integration-setup`, which now maps the whole hex suite and names the skill that
writes each file. The flat tree was deleted rather than moved: `test-principles` states where tests and fixtures sit,
and each flat test skill names the file it writes. The two ladders merged into one five-rung ladder whose
port-fake rung is conditional — taken where the architecture defines a port, skipped where it does
not, never a reason to create one. The autouse set is closed at three: the safety guard, the schema
setup and the isolation reset. HTTP interception was reconciled: every happy-path test asserts the
route it exercised was hit, on that route's own call record, never by requiring every stubbed route to
be called — `flat-test-service-client`'s first happy-path test now does exactly that. General rules on
assert strength and literal expected values moved in from the family test skills.
**Reverse by:** restoring both trees and both ladders to `test-principles`, removing the tree map from
`hex-test-integration-setup`, and restoring the all-routes-called form of the interception rule.

### D106 — The base container binds no feature; setup triggers key on owning the schema
A review of D103–D105 found template lines most services would not have. The hex base container now
binds no store and no feature: `ExportSettings`, its package and the tunable's provider are gone from
`hex-wiring/CONTAINER.md`, and the tunable's binding is an add-on beside the tunable value object in
`hex-domain-model`; the unit-of-work factory binding moved to `hex-patterns` under its implementation,
with one rule left in `hex-wiring` — a unit of work is bound as its factory callable. The base's
handler provider says where `IFooRepository`'s binding comes from, and the numbered docstrings that
copied the skill's ordering into a reader's code are gone. `python-settings` rule 5 gained a CLI
exception — a program its users run may ship a documented tunable default — and its hard stop narrowed
to deployables; the dotenv read became conditional, since a CLI tool run from arbitrary directories
reads none. The migration tool and bootstrap in both setup skills are triggered by owning the schema of
a relational store, not by having one, so a service that only reads a table carries no migration tool.
`python-toolchain` rule 5 sanctions one suppression everywhere and lets the family setup skill that
lays a migration bootstrap sanction the two migration ones, whose rationales now live there.
`flat-layered`'s settings template is gone in favour of `python-settings`', named in one sentence.
**Reverse by:** restoring `ExportSettings`, the tunable provider and the unit-of-work section to
`hex-wiring/CONTAINER.md` and removing their add-ons from `hex-domain-model` and `hex-patterns`;
dropping the CLI exception from `python-settings` rule 5; keying the migration tool back on having a
relational store; moving the migration suppressions back into `python-toolchain` rule 5 as a list of
three; and restoring the settings template to `flat-layered`.

## The flat family, reduced to what most flat services have

### D107 — The flat skeleton, entrypoint, persistence and tests cut to the common case
A generality review walked the flat family through its test services — a queue consumer that stores
nothing, a nightly report job, a webhook receiver, a CLI-triggered export, a crawler with two stores —
and found one sample application's shape throughout. The skeleton in `flat-layered` now holds only what
most flat services have, with packages at the package root: no `services/`, `ingest/` or `jobs/`, the
external system's package named for it (`foo_api/`), the run function a module named for its work
(`foo_sync.py`), `containment.py` only where a process outlives one run, and `entrypoints/` only where
there is more than one process. The service's own record has a non-nullable key and no labels; a
directory written for another reader is an external system with its own package. In
`flat-entrypoint` one run per process, started by an external scheduler, is the default; a loop is the
same run repeated, and only a process that outlives one run is guarded, sleeping on an interval read
from settings. A contained unit returns for redelivery up to a declared limit and then goes to a dead
letter, its effect idempotent (rule 15); a file another reader collects is written atomically (rule 12).
Durable obligations 6 to 8 — the continuation's carried values, the empty-batch end and the public
batch ceiling — are merged into 6, which keeps the first two and drops the ceiling a test had to read;
the old 9 to 13 are 7 to 11. The HTTP shape is
one route receiving a body and handing it to one run function, with no upstream client in the HTTP
process, and the framework's validation failure rendered as the catalogue's `InvalidPayloadError` —
first named `InvalidRequestError`, renamed because it collided with SQLAlchemy's exception of that name.
`flat-persistence` is one table and a repository with `record_batch` alone: `list_after` went, rule 19
staying as a rule and its test becoming conditional on a run that pages, because most flat services
never walk their own table; the record's `reference` is a `FooReference`, a distinct type over `str`
wrapped at each mapping point, because `python-style` makes an identifier issued elsewhere one;
`normalize_reference` is gone because it silently merged keys the source tells apart by case, the key
now stored as it arrives, and the read-back helper and the atomicity test are stated as conditional on a
write that spans statements (D19's parent-and-children write is gone). The integration conftest lost
its external-database mode, now one `## Other bindings` bullet carrying its own guard, and a store
another project owns gets no migrations — the suite creates its schema from metadata. The test skills
follow: no filter test, the aggregate asserted as `RunResult`, the containment test only where a
process outlives a run, the HTTP test driving one body-receiving route, and the batch-loop tests
matched to durable obligation 6, with the public-loop-constant rule gone. A later pass in the same
review left the redelivery limit and dead letter to the broker's own configuration, scoped to units a
broker delivered; had no transaction span two stores; dropped the client's failure-injection subclass
for a transport failure; and replaced the startup-state recovery message with one sentence.
**Reverse by:** restoring the flat skill files, their indexes and the `python-toolchain`,
`flat-project-setup` and `naming` sentences from the commit before this one, renumbering the durable
obligations back to 13, and removing the superseded markers on D19, D51 and D90.

## The hex family, reduced to what most hex services have

### D108 — The sample application leaves the hex family
**The blob-store add-on superseded by D109.**
The generality review that cut the flat family (D107) walked the hex family through its test services —
a CRUD REST service with one aggregate, a queue-driven service, a gRPC service with two aggregates and
no auth, a service with no relational store — and found one sample application under the placeholders.
It is gone: the `Foo`→`Bar` foreign key and its `bar_id`/`bar_ids` fields and filter, the audit trail
(`IAuditRepository`, `AuditEvent`, `domain/audit/`), the xlsx export and its settings and tunable, the URL
canonicalizer with its value object, the S3 and idna adapters, the framework-free run function in
`hex-patterns`, the date-range filter, `caller_id` on every command, CORS in the app shell, a `413`
advertised by default, the `/bulk` route and attachments. `Foo` is `Foo(id, name, note)` — `note` so a
PATCH test has an untouched field to check — and `Bar` is a second aggregate of the same form, named and
never templated. Where the caller is authenticated, the entrypoint sets a `caller_id` from whatever
authenticated it, stated in one sentence where commands are defined. The caller identity is the
issuer's opaque subject, a `str`, and a rank exists only where a route gates on one; JWKS is an
`## Other bindings` bullet. The unit-of-work example writes one `Foo` and one `Bar` over `foos` and
`bars`. A tunable value object carries no default (`python-settings` rule 5). The Redis key prefix is
a module constant in the adapter. The engine, session and connection factories moved out of
`hex-conventions` to sit beside their store skills — `hex-persistence`'s `REPOSITORY.md` and
`hex-store-repository` — leaving `hex-conventions` the factory names. The capability adapter has one
template, the HTTP gateway; the SDK-client and pure-CPU forms are prose. The base integration conftest is
framework-free and ends at the per-test `container`; `real_app` is the REST add-on, and the blob-store
add-on names its settings class by role. Registering a status a middleware emits moved to
`hex-restapi-app`, which owns the middleware.
**Reverse by:** restoring the hex skill files, their indexes, the `naming`, `python-style` and
`flat-test-integration-setup` examples from the commit before this one, and removing the superseded
markers on D78, D79 and D80.

### D109 — The hex family uses the universal catalogue and states what a transport-free service needs
A second pass over the hex family (D108) moved its remaining sample shapes to the universal owners and
reduced them to obligations. The exception root is the project's own `MyappError` from
`exception-catalog`, never a family-wide `DomainError`; in a hexagonal service the one catalogue lives in
`domain/exceptions.py`, and `hex-restapi-app` names the classes the shell and the routes add, each with
its optional `http_status` and each only where something raises it. The auth templates are rank-less by
default — `CurrentUser(id)`, a verifier requiring `sub` alone, `get_current_user` alone — and `Role`,
its claim arm, `ForbiddenError` and `require_role` sit in one *Rank apps only* block, where `Role` is
also the catalogue's one worked enum with a method (the duplicate templates in `hex-domain-model` and
`hex-test-domain` are a sentence each). The relational delete has no in-use branch; the FK translation
is a rule that applies where another table references this one. `hex-architecture` states the
non-HTTP entrypoint obligations as rules: a per-operation scope, one catching scope rendering off the
exception's attributes, acknowledgement after the handler returns, and a create safe to repeat under
at-least-once delivery. A port declares only what some handler calls; a PATCH field the client may
clear distinguishes absent from null; `caller_id` is persisted only where the aggregate records an
owner or actor. The base composition root carries one handler line. The blob-store test add-on and the
`/info` invariant test are gone: the key-value add-on is the worked store add-on, and a health or info
endpoint is tested like any endpoint. The page-size default is the filter's alone.
**Reverse by:** restoring the hex skill files and the `README.md` index line from the commit before
this one.

### D110 — Logging is its own universal skill, `python-logging`
`python-style` held three subjects — typing, logging, comments — and its `description` ran to about 900
characters listing all three, the "two skills wearing one name" pitfall `meta-skill-author` names. Its
`## Logging` section, the logging rules and hard stops, and the sibling `LOGGING.md` moved into one new
universal skill, `python-logging`, as a single `SKILL.md` (about 210 lines, so no sibling): the event
shape, levels, who logs an error, the failed undo under compensation, configuring once at the entry
point, a distributed package that configures nothing, what never reaches a log line, and a program's
stdout result as output rather than a log. Its trigger names the code that reports, not the word
"log" — a `print` for progress, an `except` that records a failure, setup in a CLI or a library. The
rules were renumbered 1–6 (`python-style` 10, 11, 17, 18, 12, 13 in that order), moved verbatim but
for rule 6, which now leaves the `context` ban to `exception-catalog`, its owner;
`python-style`'s remaining rules 14–16 became 10–12, and its `description` now covers typing and
comments only. The move was also a review: the template shrank to the one event line, marked as the
application binding; the bulk-import `bind` block, the failed-undo code block and a repeated passage
went; and the hard stop that duplicated the log-and-re-raise one went, as did the two
`exception-catalog` hard stops restating it. The ownership table in `meta-skill-author` gives logging
its own row; every pointer to `python-style` about an event's shape, and the two citations of its old
rule 17, now name `python-logging` (rule 3), while a pointer asking *which layer* logs names
`hex-architecture`, which owns that table. Universal goes from 12 to 13 skills, the catalogue from 47
to 48.
**Reverse by:** moving the body of `python-logging` back under `python-style`'s `## Logging` (the
binding, examples and level guide into a sibling `LOGGING.md`), restoring its rules 10–13, 17 and 18,
its logging hard stops and its three-subject `description`, deleting the `python-logging` directory,
repointing the references, the ownership row, both indexes and the counts, and restoring the deleted
template lines, code blocks and hard stops from the commit before this one.

### D111 — Settings are built by calling the class; no factory function that only returns it
`get_foo_settings()`, `get_postgres_settings()`, `get_foo_api_settings()` and `get_settings()` each
returned their class's no-argument construction and added nothing. The obligation behind them is
`python-packaging` rule 8 — nothing is built at import time — and calling the class inside the function
that composes the process meets it. The settings templates in `python-settings` and `flat-persistence`'s
`SETUP.md` declare the class alone; the process definitions in `flat-entrypoint` and its `HTTP.md`, and
the migration environment in `flat-project-setup`, call `FooApiSettings()`, `PostgresSettings()` and
`Settings()` where they build the rest. `python-settings` rule 13 says the root constructs each class
once and that a factory function is written only when it adds something — a cache, assembly from
several sources — with a hard stop for an uncached one outside the composition root; a container's
provider method is the composition root and stays. When to cache a factory is `python-packaging` rule 8
alone, and its "yes" example is the class called inside `main()`. `flat-layered` rules 7 and 8,
`flat-persistence` rule 14 and the hard stops that named a factory say "build" or "construct", and the
`flat-layered` sentences restating rule 7 or `python-packaging` rule 8 are gone. A module-level instance
stays forbidden. The hex family was already this shape — its provider methods call the class — and its
prose now says "settings provider" rather than "settings factory".
**Reverse by:** restoring the factory functions, their `__all__` entries and the call sites, and the
wording of the rules, hard stops and hex prose above, from before the change that added this
entry.

### D112 — The test engine drops its pool-liveness opt-out, and `/commit` points at the placeholder table
`flat-test-integration-setup` rule 9 told the suite to turn off the pool's per-checkout liveness check
against its own container (`pool_pre_ping=False` in the conftest template); `hex-test-integration-setup`
had already lost the same opt-out. It is a small per-checkout saving with no correctness stake, which
is not worth a rule, so it is gone from flat too: rule 9 and the argument are removed, and both families
build the test engine without a test-only pool setting. It was the last rule, so nothing was renumbered,
and no skill cited it. The production `pool_pre_ping=True` in `hex-persistence` and `flat-persistence`
is unchanged. Separately, step 2 of `.claude/commands/commit.md` still listed `foo_parser` among the
placeholders a diff is checked against, after D29 deleted it, and lacked `Baz` and `myframework`. A copy
of the table goes stale with every row added to it, so the step now points at the `CONVENTIONS.md`
placeholder table instead of listing it. Dropping rule 9 is typed `fix`: it withdraws an obligation no
conforming project breaks on, so nothing a reader carries needs to change.
**Reverse by:** restoring rule 9 and `pool_pre_ping=False` in `flat-test-integration-setup` from the
parent of the commit that removed them; the `/commit` pointer is not reversed on its own.

### D113 — The repository builds its own chunked upsert; the table-generic `bulk_upsert` is gone
`flat-persistence` shipped `bulk_upsert(conn, table, rows, conflict_columns, update_columns)` in
`engine.py`, a table-agnostic helper carried over from the application the first skills were written
from. The obligations it bound are the house pattern — one multi-row statement per chunk (rule 9), a
chunk size held as a named constant below the driver's bind-parameter cap (rule 10), an explicit
conflict resolution with a declared update set that never holds the key (rule 12) — and the generic
helper was not: its mapping-typed rows needed an exemption from `python-style`'s declared-record rule
(D20), and six of the persistence tests exercised the helper rather than the class a caller uses.
`FooRepository.record_batch` now builds its own `insert … on conflict do update` per chunk from the
collapsed `Foo`s, the column mapping built inline so no function returns a record-shaped dict; the
update set is spelled from the statement's `excluded` row. `_CHUNK_SIZE` is computed in the repository
module from the cap and `len(foo_table.columns)`, and the constructor takes a keyword-only `chunk_size`
defaulting to it. The batch is optional: a method taking one `Foo` runs one statement with no cap, chunk
constant, collapse or loop, and rules 9 and 10 bind only where a method takes a batch. With a second
repository class the cap moves to `engine.py` as a public `BIND_PARAMETER_CAP`; otherwise `engine.py`
holds the engine factory alone, and a hard stop forbids re-extracting a table-generic write helper. The
unused `_to_foo` left the template and is named in prose for a class that reads. `flat-test-persistence`
has one template, the repository's: the update set from both sides in one test (the name changed, the
minted id kept), the chunk boundary and the in-batch duplicate marked as batch-only, and the
translation. The plain-insert constraint test is gone; test rules 2 and 3 apply where the translator
branches on a constraint's name, rules 5, 6 and 13 are conditional on their case, rule 8 points at
`test-principles` reliability rule 5, and a third restatement of "expect the catalogue exception" is removed. Rules 9
and 11 no longer name a helper, rule 10 computes from the written table's width rather than the widest
table's, and rule 12 says the write rather than the caller names the columns. No persistence obligation
changed; the mapping-builder exemption D20 granted is withdrawn, which is breaking for a project that
carried the helper.
**Reverse by:** restoring `bulk_upsert` and its `__all__` entry in `SETUP.md`, the `record_batch`
call to it, `_to_row` and `_to_foo` in `REPOSITORY.md`, the table-contract template and the row-builder
paragraph in `flat-test-persistence`, and the helper wording in `flat-persistence` rules 9–12, its tree,
its description, its hard stops and the neighbour lines in `flat-test-integration-setup` and
`flat-test-run-function`, from the parent of the commits that added this entry, with D20's
superseded marker removed.

### D114 — `python-logging` sends a CLI's diagnostics to stderr, renders per sink, and is Reference-shaped
A CLI tool is one of the universal test services, and `python-logging` told it that its stdout result is
not a log event without saying where the log events go — so nothing stopped a logger writing to stdout
from interleaving diagnostics with the data a caller pipes onward. Rule 1 now adds that a program
whose stdout is its product writes every log event to stderr, stated beside the stdout sentence in
`## The event` and backed by a hard stop; the description and both index lines state it as conditional
on such a program. Rule 3 no longer renders every event in one machine-readable format: the one
configuration picks the rendering for the sink — machine-readable wherever a collector reads it; on an
interactive terminal it may be human-readable — and routes a framework's and a driver's loggers
through it, with a new hard stop, addressed to an application's entry point, for a library's records
that bypass it. Rule 1 and its `print()` hard
stop now name one condition, "an entry-point debug path behind a flag", where rule 1 had said
"deliberate". Separately, the skill produces no file, so it is Reference-shaped: the `## Template —
structlog` heading is gone and its snippet, distributed-package comment included, is the example in
`## The event`, beside the interpolated-sentence counter-example; its lead-in names the library and
says that, unconfigured, it renders for a terminal on stdout, so the entry point sets both. A Reference
skill omits `## Other bindings` (`meta-skill-author`, *Skill shapes*), so its two stdlib bullets are
folded into one paragraph of `## Configuring the logger` that keeps who the binding is for (a
distributed package, and an application that chooses it), how fields reach the record, what it buys and
what it costs. With no template heading left to name a stack, the translate-and-stay-silent example's
lead-in names SQLAlchemy as one example, and `## Never log and re-raise the same event` is renamed
`## Logging a re-raised error` to name its subject; nothing cited the old heading. No rule was
renumbered, so the citations of rules 1 and 3 elsewhere stand.
**Reverse by:** restoring the `## Template — structlog (an application; …)` and `## Other bindings`
sections ahead of `## The event`, the `# yes` line in its example and its plain lead-in, the
`## Never log and re-raise the same event` heading without the SQLAlchemy lead-in, the "deliberate
entrypoint debug path" wording and the one-format clause of rule 3, and deleting the stderr sentences,
the rendering paragraph, the stdlib paragraph and the two new hard stops in `python-logging`; with its
description, both index lines and the `python-style` paragraph of `CLAUDE.md` restored to their
wording before this entry.

### D115 — `flat-test-integration-setup` points at `test-principles` instead of restating it
The skill restated what its own rules and `test-principles` already carry. Rule 4's pool and transaction
scopes are now the *Fixture scope rules* subsection's, cited, with only the one-connection consequence
kept. The `filterwarnings` hard stop points at reliability rule 9, which states the narrow `"ignore:…"`
entry and its reason. The prose after the pytest configuration shrinks to a pointer at rule 8, which
already explains the closed-loop crash, and the `truncate_all` paragraph keeps only the autouse
finalization order that rule 7 relies on without explaining. Rule 2 opens with its condition — where the
suite can reach a database it did not start — as rule 3 already did, since the template's `db_dsn`
yields only the suite's own container and has nothing to guard. The hard stop against relaxing the
guard for a local database duplicated the first guard stop, whose reason now ends that stop.
`## Other bindings` gains one sentence for a second, non-relational store: its own session-scoped
container and client, isolated by a per-test namespace deleted at teardown. No obligation changed.
**Reverse by:** restoring rule 2's unconditional opening, rule 4's two-sentence scope argument, the
local-database hard stop, the `filterwarnings` stop's `"ignore:..."` wording, the loop-scope paragraph
and the full `truncate_all` paragraph in `flat-test-integration-setup`, and removing its second-store
bullet under `## Other bindings`.

### D116 — A raise path expects the narrowest class and the field that distinguishes it
`test-principles`' *Assert strength* had five recipes and no word on the raise path, so the rule that a
test never expects a bare `Exception` lived only as family restatements: a hard stop in
`flat-test-persistence` and a clause in `hex-test-capability-adapter` rule 7. Recipe 6 now owns it for
any project: expect the narrowest class the contract raises, never `Exception` or any ancestor of that
class shared with unrelated failures — so a library whose contract raises `ValueError` still expects
`ValueError` — and assert the one attribute that distinguishes the failure from others of its
class — an error code, a context key, the offending input — or, where the class carries none, the part
of its message that does, so a library or CLI tool with no error catalogue still applies it. The
`flat-test-persistence` hard stop keeps only its family half (the driver's own class → expect the
translated catalogue class, rule 7); `hex-test-capability-adapter` rule 7 keeps the probe's SDK class
as the legitimate exception and cites recipe 6 for it; `hex-test-application-handler`'s list of the
universal recipes names the sixth. Three `pytest.raises(NotFoundError)` blocks in
`hex-test-repository-contract` asserted the class alone and now assert `context["id"]`, which the
repository templates already set. `hex-test-application-handler` rule 7 keeps only its fake-specific
half and points at recipe 6 for the rest; `hex-test-domain`'s unknown-enum-value test and rule 15, and
the first undo test in `hex-test-application-handler/FAKES.md`, expect their class with a `match=` on
the message, since for those classes the message is the only distinguishing part.
**Reverse by:** deleting recipe 6 and restoring "Five recipes" in `test-principles`, restoring
"expects a bare `Exception`, or the driver's own exception class → stop; name the catalogue exception
the translator produces, or the test pins nothing the package promises." in `flat-test-persistence`,
"never a bare `Exception`" in `hex-test-capability-adapter` rule 7, the five-item list in
`hex-test-application-handler` and the full text of its rule 7 ("pins the exception's machine-readable
context, not just its class. Capture the raised catalogue exception … and assert the `context` entries
that are the contract."), the class-only `NotFoundError` asserts in `hex-test-repository-contract`,
and the `match=`-free `pytest.raises(ValueError)` in `hex-test-domain` (template and rule 15) and
`pytest.raises(RuntimeError)` in the first undo test of `hex-test-application-handler/FAKES.md`.

### D117 — The flat entrypoint templates mark their optional blocks; a delivered record is timed by its sender
Shape 1's process definition in `flat-entrypoint` and the uvicorn process definition in its `HTTP.md`
built an engine and, in Shape 1, an HTTP client, followed by a sentence saying each block exists only
for a role the service has. An agent copies the template and not the sentence after it, so a queue
consumer that stores nothing got an engine. Shape 1 now marks every line that exists only with a
store or an upstream, imports included, so honouring the markers leaves valid code: `httpx` and the
`foo_api` import `# only with an upstream`, the `postgres` import `# only with a store`, the engine line
`# only with a store (so are try/finally, repository)`, the `api` line saying the run moves out of the
client block without one, and that block's line `# only with an upstream` — the way the family's trees
mark theirs. The sentence is gone. The uvicorn template carries no marker: its route and run function
exist only with a store, so the engine there is not optional. The longer comment wordings the review
proposed did not fit the catalogue's 120-column line length (`python-toolchain`).
Rule 9 said a redelivered request already recorded is answered as a success, which a route satisfies
while rewriting the row with a new timestamp; it now also changes nothing, agreeing with rule 15's
idempotency under redelivery, and the hard stop names both failures. The `HTTP.md` run function took
`observed_at` from the wall clock, so every redelivery rewrote the row. The stamp belongs to what a
sender delivers, not to the shared wire record a fetched upstream also returns — putting it on
`FooPayload` would have failed every poll's validation — so `HTTP.md` declares
`FooDelivery(FooPayload)` with `sent_at: AwareDatetime` in `schemas/`, the route validates it and
`record_foo` writes its `sent_at`, and a sentence states the split: a delivered record is timed by its
sender, a fetched one by the run. The prose after `record_foo` claims only that an exact redelivery
writes what the row holds, and leaves keeping the newer of two out-of-order deliveries to the conflict
clause (`flat-persistence`); Shape 3's consumer paragraph gains the same clock clause. In
`flat-test-run-function` the HTTP wrapper test posts `sent_at`, and the poll idempotence paragraph says
the second run "adds no row" rather than "changes nothing", since the run's own clock rewrites
`observed_at`; its rule 3 asks the second run to have added no row and changed nothing its input
determines, rather than an unchanged observable state. `FooDelivery` imports `FooPayload` from its
sibling module by one dot (`python-packaging`). `record_batch([foo])` stays; no single-row method was
added.
**Reverse by:** in `flat-entrypoint/SKILL.md`, removing the `# only with …` comments from Shape 1's
imports and body, restoring the paragraph "Each block here exists only for a role the service has: a
service with no store builds no engine, one with no upstream builds no transport." after it, dropping
"and changes nothing" from rule 9, restoring its hard stop to "…answered as a failure → stop (rule 9).",
and dropping ", the run writing values taken from the message, never the clock" from Shape 3; in
`HTTP.md`, restoring `FooPayload` in `web/app.py`'s `myapp.schemas` import and the route's parameter to
`payload: FooPayload` passed on as `payload`, "validates the body with the payload model", removing the
delivered-record paragraph, the `FooDelivery` template and the paragraph after `record_foo`, and
restoring `record_foo(repository, payload: FooPayload)` with `observed_at=datetime.now(UTC)` and its
`datetime` import; in `flat-test-run-function`, removing `sent_at` from the HTTP test's body, restoring
"changes nothing" in the idempotence paragraph and "run twice, assert the observable state is
unchanged" in rule 3.

### D118 — Smaller leftovers: a `context` key names the input, and the checker's dead placeholders go
`exception-catalog` states that a `context` key names the input, not the failure, and then showed
`{"field": "name", "constraint": "uq_foos_name"}` as its example — a key that names the constraint that
failed. The example is now `{"foo_name": foo.name}`, the spelling `python-logging` raises with. The
constraint name stays where it is a contract rather than an example: the relational adapter in
`hex-persistence` sets it and `hex-test-repository-contract` and `hex-test-application-handler` assert
on it. `tools/check_template_imports.py` listed `mycommon`, `store_sdk` and `shared` as placeholder
modules; no fenced `python` block imports any of them, and none is in the `CONVENTIONS.md` placeholder
table, so all three are dropped. The checker reports the same 231 resolved, 0 missing, 0 unchecked
before and after. The flat/hex difference in the test engine's pool pre-ping is closed with no change:
neither family states a rule about it, so there is nothing to align.
**Reverse by:** restoring the `{"field": "name", "constraint": "uq_foos_name"}` example in
`exception-catalog`'s `What context carries` and the three names in the checker's `PLACEHOLDERS`.

### D119 — In a module holding a class, its private helpers come after it
The maintainer's read-through found both orders in the templates, once in the same module
(`hex-persistence`'s repository put `_map_integrity_error` above the class and `_apply_filter` below it).
The maintainer chose *after*: a module reads from its interface down to its details — constants, then
the class, then the helpers it calls. `python-packaging` states it beside the rule that lets a module
hold one class and several private functions, and in its rule 3; the two repository templates move
their helpers below the class. The rule is scoped to a module holding a class, which is the question
asked: modules made only of functions — test modules, `__main__`, an app factory — keep their helpers
where they are, and 17 of them put helpers first; widening the rule to them is a separate decision.
**Reverse by:** deleting the sentence and the clause of rule 3 in `python-packaging`, and moving
`_translate` and `_map_integrity_error` back above their classes.

### D120 — `when_to_use` is optional, and neither its presence nor its absence is a defect
18 skills carry `when_to_use` and 30 do not, nearly all of `pyhouse-hex` among the latter. The
maintainer chose to legalize that state as it is rather than even it out: the field is Claude Code
only, every other client matches on `description` alone, so it is written where there are trigger
phrasings worth adding beyond what `description` already carries, and `description` must stand alone
either way. `meta-skill-author` now says so beside the field. No skill changes, and no sweep follows.
**Reverse by:** deleting that sentence, and then either adding the field to the 30 or removing it
from the 18.

### D121 — A template earns its place by being copied
The maintainer's read-through found `## Template(s)` filled where nothing is copied: `git-branching`
carried a fourteen-line script — switch, fixup, autosquash, force-with-lease push, open and merge the
request — that no repository takes as written, that rule 4 does not need, and that named its branch
`feat/…` where this repository's own flow says `feature/…`. `meta-skill-author` now says a template is a
file or block of text most projects would take as written, and anything else is prose beside the rule
or nothing. `git-branching` keeps the branching section a repository records and the forge settings
that enforce it, and the script becomes one sentence carrying the only fact it had that an agent may
not know (the git 2.44 `--autosquash` behaviour), keeping `GIT_SEQUENCE_EDITOR=:` in the fold command,
without which a non-interactive agent's `rebase -i` opens an editor and hangs. A skill left with
nothing to copy omits `## Template(s)`, as a reference or process skill does, and the required-sections
sentence points at that exception. `git-commit-message` keeps its format block: every
commit message is written from it. No other skill was swept against the new line; that is lens-1 work
for `/review-skills` as each skill comes up.
**Reverse by:** deleting the bullet in `meta-skill-author`'s universal rules and restoring the script
in `git-branching`.

### D122 — `flat-project-setup` lays the migration bootstrap with the tool's init and states what to change
Block B carried a full `env.py`, a full `script.py.mako` and a `0001_baseline.py`, and the body opened
with a directory tree. The tree restated `python-toolchain`'s src layout; where migrations go is rule 1's,
now worded to carry the location the tree showed. The two generated files are what `alembic init -t
async migrations/postgres`, run from the distribution root, already writes; what this family adds is
only the handful of changes, so block B now gives the command and the obligations on its output: nothing
in `alembic.ini` names a database, the environment builds its engine from the data-access component's
settings and disposes it however the run ends, `target_metadata` is the package's one metadata, every
table module is imported, and offline mode is refused. Checked against Alembic 1.20's async template:
its `env.py` builds the engine from the ini section, sets `target_metadata = None` (autogenerate then
refuses to run), disposes only after a clean run and carries an offline branch; its `script.py.mako`
annotates with `typing.Union`/`typing.Sequence` and orders `from alembic import op` before
`import sqlalchemy as sa`, which breaks `python-style` and the `I` selection — so the template's edits
are stated as a rule rather than the house forms being assumed. The baseline's obligations were already
rule 7 (now 8) and the hard stops; its code block is reduced to a sentence. Rules 5 and 6 absorb what the
templates carried (disposal, the metadata target), a new rule 7 states that the generated bootstrap is
changed before the first revision, and a hard stop names the unchanged-output failure; rule 7 and that
hard stop restate what the deleted templates enforced by being the file itself. One thing is not a
restatement: the generated `env.py` calls `fileConfig` on `alembic.ini`, whose logging sections — `[loggers]`,
`[handlers]`, `[formatters]` and the `[logger_*]`, `[handler_*]`, `[formatter_*]` sections they list — give Alembic's records their own handler and format beside the service's
structured stream — `python-logging` rule 3 and its hard stop on a library's records bypassing the
configured logger. The deleted `env.py` configured no logging at all, so the skill said nothing either
way; block B now has the environment configure logging as the service's other process definitions do,
deletes the ini's logging sections with it, and names `fileConfig` in the hard stop. The same pass
states that `init`'s `README` is deleted, that the tool's explanatory comments go (`python-style`,
Comments), and spells the import-order edit as `import sqlalchemy as sa` ahead of `from alembic import
op`; `flat-layered`'s pointer for the tree beside `src/` moves from this skill to `python-toolchain`
rule 1.
**Reverse by:** restoring the directory tree after the opening paragraph, the `alembic.ini`, `env.py`,
`script.py.mako` and `0001_baseline.py` blocks in block B with the prose between them, rules 1, 5 and 6
to their earlier wording, dropping rule 7 and renumbering 8 back to 7, dropping the unchanged-output hard
stop, the logging bullet and the logging clause of the `alembic.ini` paragraph, and restoring the
description's parenthesis "(`alembic.ini`, the environment under `migrations/postgres/` that reads the
connection string at its own composition root, the revision template, and a baseline only over a schema
that already exists)".

### D123 — Fifteen skills' production templates drop the comments `python-style` does not sanction
An agent copies a template verbatim, so every comment and docstring in one lands in every project, and
`python-style` allows a comment only as a single short line of non-obvious *why*. The production
templates carried more. `hex-wiring`'s `CONTAINER.md` had a docstring on each provider class and on
`create_container`, a two-line note on where the repository binding is merged from and a per-line
`# one line per handler`; all are gone and their content is a paragraph before the block. In
`hex-restapi-app`, `main.py`'s middleware placeholder comment and its commented-out router include
are gone — the notes under the block say where a middleware and a router are added — and so is the
comment above `MIDDLEWARE_ERRORS`, which the prose after the block already states. In
`hex-restapi-auth`, the field comment on `CurrentUser.id` (restated by the prose below it), the
"protocol is NOT imported" import comment (now named in the paragraph that points at
`hex-capability-adapter`) and `_RoleDependency`'s docstring (now the sentence introducing the gate)
are gone. `hex-application`'s `# <file>.py` headers in its two-file query blocks became a line of
prose naming the files, as its other two-file sections already do without them. `python-logging`'s
note that a distributed package uses the stdlib logger moved into the sentence before its example.
`hex-capability-adapter`'s "protocol is NOT imported" import comment is gone; its rule 2 and its import
rules already state it. The file-path header comment opening a block became a line of prose naming the
file before it in `hex-patterns` (both unit-of-work blocks), `hex-persistence`'s `TABLE.md` (two) and
`REVISION.md`, `hex-project-setup` (`alembic.ini` and `env.py`, whose "async, online mode only" reason
moved into that line), `exception-catalog`, `python-versioning` and `python-workspace`.
`python-packaging`'s `# imports` elision marker, a structural label `python-style` bans by name, became
a real import the block uses (`from dataclasses import dataclass` on the class), so the order imports →
`__all__` → definitions reads the same. In `hex-restapi-endpoint`'s `TRANSFER.md` the "beside
`router = APIRouter(...)`" comment moved into the prose before the upload block and the `media_type`
annotation is gone; `hex-restapi-schema`'s paging comment on `FooListResponse` is gone, rule 7 stating
it; `hex-persistence`'s `REPOSITORY.md` comment on `_SORT_COLUMNS` moved into the prose before its
block. With `main.py` no longer carrying a router include, `hex-restapi-endpoint` states where the
include goes — between `register_error_handlers(app)` and `setup_dishka(...)`.
Kept, and why: the two one-line *why* comments in `hex-restapi-app`'s `schemas/errors.py` (the bare
number for an unknown status; the annotation that strict mypy needs at the decorator), which are true
in the reader's file; every optional-line marker (`# only with …`, `# only where …`), including
`flat-entrypoint`'s extended ones, because D117 put that instruction in the template precisely because
an agent does not copy the sentence after it, and because `python-style`'s `## Comments` now says such a
marker is addressed to whoever copies the template and never lands in the project's file; the
`env.py` unused-import suppression and its reason, which `hex-project-setup` sanctions; and the
`# yes` / `# no` contrast labels and per-line annotations in `python-packaging` and `python-logging`,
which are illustrations of a rule rather than files a project copies. Test skills are not covered by
this change, and production templates outside the fifteen skills named here were not swept.
**Reverse by:** restoring the docstrings on `SettingsProvider`, `InfrastructureProvider`,
`FoosProvider` and `create_container`, the repository-binding comment and the per-handler comment in
`CONTAINER.md`, and dropping the paragraph before its block; restoring the middleware comment and the
commented-out router include in `hex-restapi-app`'s `main.py`, its "router-include block is a
placeholder" note, the shorter "No other middleware is presumed" note and "`main.py` leaves a
placeholder where they are wired in", and the comment above `MIDDLEWARE_ERRORS`; restoring the
`CurrentUser.id` field comment, the import comment and the `_RoleDependency` docstring in
`hex-restapi-auth` and dropping the prose that replaced them; restoring the `# <file>.py` headers in
`hex-application`; moving the distributed-package note in `python-logging` back into its example;
restoring the import comment in `hex-capability-adapter`, the file-path header comments (and
`hex-project-setup`'s reason on `env.py`'s) in place of the prose lines naming those files, the
`# imports` marker in `python-packaging`, the `TRANSFER.md`, `hex-restapi-schema` and `REPOSITORY.md`
comments, and `hex-restapi-endpoint`'s shorter router-registration sentence; and dropping the
optional-marker paragraph from `python-style`'s `## Comments`.

### D124 — A hard stop is a test, not a limit
`meta-skill-author` bounded the body at ~500 lines and nothing else, and hard stops had grown into a
second copy of the rules: a skill's `## Hard stops` restated its `## Rules` with "→ stop" appended, so
one obligation was written twice and paid for twice on every load. A count was weighed and rejected —
it would be met by merging unrelated rules or dropping real ones, the same defect a bullet cap on
`## When to use vs. neighbours` was. The skill now states a test instead. Rule 7 says a hard stop
exists only for a wrong turn no rule in this skill governs — an action taken before any rule
applies: the request itself, the choice of skill, whether to write at all — stated as that action,
and every plausible wrong-skill case is one, with a redirect. The remedy decides which a stop is,
not its phrasing: one whose remedy is another skill, or writing nothing, stays, and one whose remedy
writes something in this skill differently goes however it is worded — declining and writing it
otherwise here counts as the latter — its better wording moving into the rule first. A stop can
always be reworded as an action, so the phrasing alone decides nothing. An intermediate reading
kept a content stop wherever it named a concrete action an agent is about to take; the maintainer
chose the narrower criterion over it, because such a stop still guards what a rule already governs and
is paid for twice. The portability gate's intro gains the remedy one deleted stop carried: whatever a
question flags is replaced with a placeholder or deleted before the skill ships. The canonical template's `## Rules`
placeholder says a rule states one obligation once, that there is no numeric limit, and that past ~20
entries review checks for two concerns to split or move to a sibling file; its `## Hard stops`
placeholder points at rule 7. `QUESTIONS.md` gains lens 4 question 7. It sits in lens 4, not lens 3,
because it is answered by reading the skill against `meta-skill-author`, with no test service and no
generation: a stop that restates a rule changes nothing an agent builds, so lens 3 would not see it;
what it costs is context, which is a contract matter. `meta-skill-author` applied the test to itself:
of its 17 hard stops, the 14 that restated one of its own sections or rules (the `description` and
`when_to_use` ones, the length limits, a library-free rule, a second template, the neighbour count,
publishing with Claude Code-only keys, application names, template comments, the vendor manual,
unchecked imports, evidence language, the portability gate and unmarked skeleton lines) are gone, and
the two that name an action taken before any rule applies stay — asked for a skill an existing one
covers, and writing one from material nothing survives. The last was reworded as the action. A third,
asked for a skill built on another frontmatter field, had a remedy that writes it differently here,
so it moved into `## Frontmatter` as "No other field; information that would need one goes in the
body." The four shapes' descriptions and examples moved to `## Skill shapes` in the sibling
`CONVENTIONS.md`, the picking table staying with a pointer, which with the stops brings `SKILL.md`
from 510 lines to 457. The sweep of every other skill against the
test is a separate change, backlog item 16.
**Reverse by:** restoring rule 7 as "**Hard stops are explicit.** Every plausible wrong-skill case
becomes a hard stop with a redirect. This is how a reader recovers from misclassification without
overreaching." followed by its unchanged last sentence; dropping the added sentences from the
`## Rules` and `## Hard stops` placeholders and from the portability gate's intro; restoring the 14
deleted hard stops and the frontmatter-field stop, dropping its sentence from `## Frontmatter`, and restoring the earlier wording of the question-5 stop; moving the four `###` shape sections back from `CONVENTIONS.md` into
`## Skill shapes` before `### Picking a shape`, with "(rule 1)" and "this skill" in place of their
qualified forms, and dropping the pointer and the "four skill shapes" mentions in both files' openings;
and dropping lens 4 question 7 from `QUESTIONS.md`, with question 2 again asking that "each plausible
wrong turn has a hard stop".

### D125 — Placeholders stay `Foo`/`Bar`; no template syntax
Jinja-style placeholders (`{{ aggregate }}` rather than `FooRepository`) were proposed and are
rejected. A template must stay valid Python: `tools/check_template_imports.py` parses every fenced
`python` block, and braces would make every block a syntax error, which that script skips silently —
it returns no imports for a block that does not parse — so no template's imports would be verified
again. An agent copies a template verbatim and
could leave the braces in the reader's file. And a slot still needs its names derived —
`{{ Aggregate }}Repository`, the plural, the snake case — which is `naming`'s job and what `Foo`,
`foos` and `IFooRepository` already show worked through. What the proposal rightly noticed is that some
templates read as an invented domain (`BarGateway`, `BarToken`); that is one template carrying one
application's shape, a lens-1 defect fixed in that template (backlog item 19), not a matter of syntax.
**Reverse by:** choosing a slot syntax that still parses as Python, rewriting every template and the
`CONVENTIONS.md` placeholder table to it, teaching `tools/check_template_imports.py` to read it, and
stating in `naming` how each derived name is spelled from a slot.

### D126 — `hex-patterns` is dissolved: the unit of work joins `hex-persistence`, compensation `hex-application`
Taken by the maintainer (backlog item 23). The skill held two patterns that share nothing but spanning
layers, and neither is a catalogue of patterns; each now sits beside the artifact it depends on.
The unit of work went to `hex-persistence` as a sibling topic file, `UNIT_OF_WORK.md`, next to
`REPOSITORY.md`'s unit-of-work-managed form it constructs: the domain protocol, the SQLAlchemy
implementation with its three load-bearing details, its dishka binding, and the handler form that
opens it. The handler form stayed with the protocol rather than going to `hex-application` because a
unit of work is never written without its protocol and implementation, so an agent writing a handler
that writes two repositories has to open that file anyway; `hex-application` fires on the handler and
routes there in its Command or query bullet, command handler rule 7, `When to use` and a hard stop, and
splitting the handler off would have made two reads and put the handler-side rules (commit last,
nothing caught inside, no retry) away from the exit-rolls-back behaviour they rely on. Its eight rules
became `hex-persistence` rules 15–17 (one per scope and never per aggregate, with the naming section
reduced to a sentence; one per `execute` from a factory, the binding rule pointing at `hex-wiring`,
which already owned it; commit last, no catch, no retry) and a sentence added to rule 7 (a joining
repository is handed the open handle, never a factory). Compensation went to `hex-application`: its
seven rules became a `Compensation` subsection of Rules (rule 1, the only sanctioned `try/except`, was
already command handler rule 5(a) and merged there; the when-to-use bullets, the several-side-effects
and success-path-cleanup paragraphs became rules 1, 6 and 8), and its template — `hex-application`'s
own `CreateFooHandler` with the undo — went to a sibling `COMPENSATION.md`, because in the body it would
have taken `SKILL.md` past ~500 lines for a form most hex services do not have. Dropped: the "both
patterns together" template (a sentence in each file says compensation's `try` wraps the `async with`),
the separate `CreateFooCommand` block (a sentence says the one command gains `data: bytes`), the
structured-logger bullet under Other bindings (`hex-application` already has one), the neighbour line
on CLIs and workers, and the hard stops a rule already catches — one repository only, per-aggregate
naming, a settable protocol member, a mismatched `__aexit__`, an unguarded undo, and an undo's failure
stopped anywhere but the handler's guard (its remedy is how to write the undo, now the end of
Compensation rule 4). Kept as hard stops, because a rule does not route them: no reversing method on
the port, a saga, and a unit of work spanning two backends. `paths` gained
`**/domain/uow/**` on `hex-persistence`; `hex-application`'s stays `**/application/**`.
**Reverse by:** recreating `plugins/pyhouse-hex/skills/hex-patterns/SKILL.md` from the commit before
this one, deleting `hex-persistence/UNIT_OF_WORK.md`, `hex-application/COMPENSATION.md`,
`hex-persistence` rules 15–17, the rule-7 sentence and its two-backends hard stop, `hex-application`'s
Compensation subsection and its two compensation hard stops, restoring both descriptions and the
`hex-persistence` `paths`, repointing every reference named in this commit back to `hex-patterns`, and
restoring the counts (48 skills, 24 hex, Hex core 12).

### D127 — Every skill swept against the hard-stop test: a stop survives only where its remedy writes nothing here
Taken by the maintainer (backlog item 16). `meta-skill-author` rule 7 decides a hard stop by its
remedy: one that sends the work to another skill, or writes nothing, stays; one whose remedy writes
something in this skill differently is a rule, and its better wording moves into that rule before the
stop is deleted. Every skill in all four plugins was swept against it. Bullets under `## Hard stops`
went from 182 to 54 in `pyhouse-universal`, 18 to 6 in `pyhouse-git`, 213 to 82 in `pyhouse-hex` and
117 to 20 in `pyhouse-flat` — 530 to 162. Nothing a deleted stop said was dropped unless a rule already
said it; the rest was folded into the rule it restated, and a stop whose obligation no rule stated
became one (`flat-layered` rule 15, `flat-entrypoint` rule 16). The review of the sweep narrowed both
to the stop they replaced — business logic, not wiring, logging or the loop around a run; a process
that waits, not a consumer that never does — restored the `hex-test-domain` stop that writes no file
for a value object with no invariant and no custom equality, and kept three `python-versioning` limits
unconditional (no bump for elapsed time or effort, no break shipped as a smaller segment, no fix as a
post-release, with rule 15's release note) rather than lifted with rules 6 and 8 by the precondition
table. `pyhouse-reviewer` Step 3 now judges a stop by the same test, keeping that a rule's exception
holds wherever the rule is applied, and `CLAUDE.md`'s sentence on the engine rules no longer promises
a matching subsection of `## Hard stops`.
Rules merged or emptied by the sweep renumbered their neighbours: `flat-layered` (3 and 5 merged, 13
removed: 6–12 → 5–11, 14–16 → 12–14, 15 new), `test-principles` reliability rules 4–9 → 3–8,
`architecture-choice` 9 → 8, `hex-test-repository-contract` 20 → 19 and 22 → 20, `hex-test-restapi-auth`
18–24 → 17–23; every live citation was updated to the new numbers. Citations in earlier entries of this
file keep the old numbers on purpose: each records the skill as it stood when that decision was taken.
**Reverse by:** restoring each skill's `## Hard stops` from the commit before the sweep's first commit,
reversing the renumberings above and every citation updated for them, removing `flat-layered` rule 15
and `flat-entrypoint` rule 16, restoring `pyhouse-reviewer` Step 3's "a hard stop is its rule's trigger"
paragraph and the `CLAUDE.md` sentence — and, unless rule 7 is reversed with it, the next review will
find every restored stop a restated rule.

### D128 — Five read-through items closed: the row mapper, hex's migration bootstrap, template comments, a fake unit of work, `domain/uow/`
Taken by the maintainer (backlog items 28–30, 32 and 33). **28:** `python-packaging` owns helper
placement and wins — a helper that reads no `self` is a private module function after the class.
`hex-persistence` rule 11 and `REPOSITORY.md` rule 23 no longer make a single-use helper a private
method, and `_row_to_entity` is a module function after `FooRepository`, shared with the session form.
**29:** `hex-project-setup` block B now states what `flat-project-setup` does: `script.py.mako` takes
the house annotation forms, `import sqlalchemy as sa` ahead of `from alembic import op`, and loses the
tool's comments; `env.py` disposes the engine in a `finally`, refuses offline mode and configures
logging through `myapp.logging.configure_logging`, the service's one logging setup, written once where
the service has none and called by every entrypoint (`python-logging` rule 3); rule 6 states the three.
**30:** the template comments `python-style` does not sanction are gone — the check-constraint suffix
note in `hex-persistence/REVISION.md`, the read/mutation labels in `hex-restapi-auth/ROUTES.md`, the
`409` notes in `hex-restapi-endpoint`, the SQLSTATE gloss in `flat-persistence/REPOSITORY.md` and the
explanation after `hex-project-setup`'s `noqa` (no suppression requires a reason) — each instruction
moved into prose; the `cast` reason in `hex-persistence/REPOSITORY.md` and the invariant note in
`hex-restapi-schema` are a single short *why* each and stay. **32:** `hex-test-application-handler`
Fakes rule 10 obliges a fake unit of work that hands out the fake repositories, records its commit and
exposes writes outside it only on commit, while reads inside it see its own writes, with the test pinning that and that an exception commits nothing — a
rule, not a template, since most handlers take no unit of work. **33:** `hex-conventions`' derivation
table gains the unit-of-work protocol's row, `domain/uow/i_unit_of_work.py`, as `UNIT_OF_WORK.md`
places it.
**Reverse by:** restoring the private-method wording in `hex-persistence` rule 11 and `REPOSITORY.md`
rule 23 with `_row_to_entity(self, …)` inside the class (and then reconciling `python-packaging`,
which would lose); restoring block B's generated-as-is revision template, the unguarded dispose and the
env.py with no offline check or logging call, and deleting `hex-project-setup` rule 6; putting the
removed comments back in the templates; deleting Fakes rule 10; deleting the `hex-conventions` row.

### D129 — No "run function", no `guarded`, and a minimal HTTP trigger
Taken by the maintainer (backlog items 12 and 13). **12:** "run function" was the body of a durable
engine's unit of work, kept after the engine left (D50), and is no industry term; no skill names it as a
concept any more. The obligation stays in `flat-entrypoint` rules 2 and 3 without the term — the work a
trigger performs is a plain framework-free function in a module named for its work, taking every
dependency as a parameter and named by `naming` for what it does, and every trigger calls it. The skill
`flat-test-run-function` keeps its name for now. `guarded` shared the root: the `containment.py`
template, the loop's `guarded(...)` call and the requirement that containment be one named function,
defined once and returning a value a test asserts on, are gone. Rule 8 keeps the behaviour — a process
that outlives one run keeps running when one fails, the failure logged once; a process that does one
run and exits contains nothing; a broker-delivered unit whose run failed is returned (rule 15) — and
the reason stays with it: the catch wraps one run in a function of the process definition that takes
what it needs as parameters (`sync_foos` in the template, named by `naming`, in no shared module and
returning nothing), so a test reaches one run without driving the loop. `flat-test-run-function` rule 8
calls that function with the transport failing, then again, and asserts the second run's effect —
never the log line, never an escape built into the loop. Durable obligation 8's helper is "the progress
helper", so one word no longer names two things. `flat-entrypoint`'s own templates no longer import a
logging library; `HTTP.md`'s app module, which must run as copied, binds its logger in the one form
`python-logging`'s example shows, and its heading names that library. **13:** `HTTP.md` keeps only rule 9's wrapper — the factory, one rendering place,
one route, the server's process definition; the delivery record is a sentence, and `hex-restapi-app`
is named only as an example of a fuller shell.
**Reverse by:** restoring `containment.py`, the `guarded` loop fragment and the named-function wording
of `flat-entrypoint` rule 8, the containment template and the old rule 8 of `flat-test-run-function`,
and the "run function" definition in `flat-layered`, from the parent of the commits that added this
entry; restoring `HTTP.md` and the structlog lines from the same parent.

### D130 — A command block run once stays; a routine is a sentence; `git-branching` binds no forge
Taken by the maintainer (backlog item 31), with a later decision on `git-branching`. `meta-skill-author`'s
"earns its place by being copied" bullet now states the criterion D121 left implicit: a command block is
a template only when a project runs it once, as written — a bootstrap such as `flat-project-setup`'s
`alembic init`; commands repeated per change or per release become a sentence beside the rule, given
inline and whole, with any flag that keeps them from prompting. By it, `flat-persistence/SETUP.md`'s
`alembic revision --autogenerate` / `alembic upgrade head` block and `python-versioning`'s tag block
became sentences — the tag keeps its `-m`, since `git tag -a` without one opens an editor — and the
pre-release ladder went inline. The shapes paragraph no longer says shapes "add and remove nothing": a
shape adds no canonical section, and `CONVENTIONS.md` points at the table instead of restating it.
**D121's keep of the `gh api` block is reversed.** The team works on GitLab as well as GitHub, most
members have no `gh` CLI, and the skill says it assumes no forge. The block is gone, the heading drops
"on GitHub", the recorded block says "request" and the lead-in tells the repository to write its own
default branch and its forge's word for it, and one sentence names the three settings the forge enforces
once (rule 2): merge commits only, the branch deleted when it lands (rule 6), and `main` protected — no
push straight to it and no request merged until its checks pass, which on GitLab is a separate setting.
The fold command became `git -c sequence.editor=:`, which runs in any shell, and the recorded merge line
says each commit is cleaned up before it lands. The review also changed: `install-commit-hook` warns
that the shared install silences hooks a manager such as pre-commit wrote into the clone;
`python-versioning`'s template shows `0.1.0` with no `requires-python` (the floor is `python-style`'s),
its `version.py` exists only where a program reports its version, and rule 5 keeps an existing tag
series' spelling; `SETUP.md` drops what `flat-project-setup` and its own rules 16 and 20 already state,
says a revision is reviewed against rule 16 and drafted against a database only its author uses; and
`flat-project-setup` no longer pins `--rev-id 0001`.
**Reverse by:** from the parent of the commits that added this entry, restoring the `alembic revision` /
`alembic upgrade` block in `SETUP.md`, the tag block, ladder, `requires-python` and `1.4.0` in
`python-versioning`, the "sequence of commands" bullet and the shapes sentence in `meta-skill-author` and
`CONVENTIONS.md`, and `git-branching`'s `gh api` block, "on GitHub" heading and "pull request" wording.

### D131 — An older write never overwrites a newer one; a redelivery is rule 3's case; a delivery is one row
Taken by the maintainer (backlog item 11, and a review finding that reverses D117's last sentence). No
new test: `flat-test-run-function` rule 3 already pins the second run of any run that can repeat. It now
names a delivery the sender may repeat — a webhook redelivery, an at-least-once broker delivery — says
the work's own test file pins it, never the wrapper's (rule 5), and that with no store the second run
sent what the first sent (rule 4); its idempotence template compares the values the input determines
rather than a count. `flat-persistence` rule 12 gains one conditional sentence: where an older write can
arrive after a newer one for the same key, the update is guarded by the row's ordering stamp — a version
or an instant fixed when the change was made or observed, the same on every delivery of it, never the
time of a delivery attempt or of the write — so an input stamped older never replaces a newer one, in the
row or in a batch collapsed by key. The stamp is defined by being fixed with the change, not by who
assigns it: a sender that restamps each attempt defeats a guard on its stamp, and a crawler whose runs
overlap has only the instant it fetched. An equal stamp may replace, so the copied update-set test still
passes. Rule 18 keeps the newest by that stamp in the in-batch collapse wherever the stamp guards the
write, and in a merge-time engine chosen once in the schema, so the guard does not lapse with rule 12 on
a store that deduplicates at merge time. `HTTP.md`'s delivery field is `changed_at` (was `sent_at`), its
pointer says keeping the newer is the data-access package's job (rules 12 and 18), and **the work calls
`repository.record(foo)`, the single-row form `REPOSITORY.md` describes — reversing D117's
"`record_batch([foo])` stays"**, so a webhook receiver no longer copies the batch machinery.
`flat-entrypoint` rule 10 and Shape 3 point at the same rules instead of naming a store mechanism. No
template gains a line for the guard; a test pinning it is left to item 26.
**Reverse by:** from the parent of the commits that added this entry, restoring `flat-persistence` rules
12 and 18, its precondition row and other-engine bullet; `flat-test-run-function` rule 3, its idempotence
template and paragraph and its wrapper test body; `flat-entrypoint` rule 10 and Shape 3; and `HTTP.md`'s
work paragraph, template (`sent_at`, `record_batch([foo])`) and pointer.

### D132 — The capability adapter templates one neutral call, with one client per integration
Taken by the maintainer (backlog item 19). `hex-capability-adapter`'s HTTP gateway was one application's
token client — `HttpBarGateway.fetch_token(subject) -> BarToken` behind `ICanFetchBarToken` — so every
service that copied it carried a subject, an expiry and a token type it did not have. The template is now
`HttpFooClassifier.classify(foo) -> FooKind` behind `ICanClassifyFoos`: an injected client and settings,
a request built from `Foo`, the body mapped into the existing `FooKind` inside its own translated scope,
and the status mapped as `exception-catalog`'s fallback example does. What only some services have is
shown as marked lines rather than removed — the credential (the secret field, its one unwrap in the
constructor, the header, the test's assertion of it) and the `400` row that becomes `ValidationError` —
each marker on its own line above a block, so honouring every marker leaves code that parses, type-checks
and passes the house lint. The review added obligations: each integration's factory builds its own
client, so a second upstream never inherits the first one's timeout (rule 5, `hex-wiring`'s
`CONTAINER.md`); settings sit one class per configured component, owned by `hex-conventions` block A; a
secret never rides in a URL the client library logs (rule 7); the upstream's labels are mapped onto the
domain's values, and whatever the conversion raises is the upstream's fault (rules 8–9). It reduced
others: rule 8 and most of rule 10 restated `exception-catalog` and are a pointer (rules renumbered
9–14 → 8–13); the error arms no longer put the exception's class name in `context` (`exception-catalog`
rule 11); the undo rule narrowed to a capability whose write a handler compensates. The test skill tests
the same arms plus the fallback row, with settings as a module constant and file names mirroring the
adapter's module. `hex-conventions` no longer uses a token manager as its adapter example.
**Reverse by:** restoring `hex-capability-adapter`, `hex-test-capability-adapter`, `hex-domain-ports`,
`hex-wiring` (`SKILL.md`, `CONTAINER.md`), `hex-conventions` and `hex-test-application-handler/FAKES.md`
from the parent of the first commit that added this entry; the shared-client binding then returns with
its single-timeout defect.

### D133 — Every hex template that logs does so once, configured, with its binding named
Taken by the maintainer (backlog item 34), widened by its review. The hex templates keep the structured
logger: unlike `flat-entrypoint` before D129, each hex log line carries an obligation — `hex-application`
Command handler rule 6, the warning a failed undo earns under compensation, and the central error
handler logging a failure once. What changed is that each line now logs once, under one configuration,
with its binding named. **Named:** `hex-restapi-app`'s template heading adds structlog;
`hex-persistence/UNIT_OF_WORK.md`'s handler heading names it and its lead sends another facade to
`hex-application`'s `## Other bindings`; its implementation heading names dishka. `hex-restapi-app` gets
no logging bullet of its own — `python-logging`'s *Configuring the logger* already covers the
alternative (lens 2 over lenses 3 and 4). **Once:** the shell's handler for bare `Exception` ran in
Starlette's outermost layer, which re-raises to the server, so one crash logged twice under uvicorn. It
is replaced by `UnexpectedErrorMiddleware`, a raw-ASGI class in `error_handler.py`, added first so every
declared middleware wraps it (the 500 keeps CORS headers and the event keeps a request id bound outside
it); after the response has started it re-raises unlogged, leaving the server one traceback. Every
`ErrorResponse` renders with `model_dump(mode="json")` — a UUID in a catalogue error's context had turned
an advertised 404 into a 500 logged twice — and the domain handler logs the rendered body's `context`,
so the log field is the string the body carries. **Configured:** `create_app` calls
`configure_logging()` first; the note names `uvicorn --factory` (never a module-level `app`), so the
setup runs after the server configured its loggers and takes them over. `python-logging` rule 3 now
requires the setup to be safe to run again — one handler of its own, none it did not install removed —
because each test builds the app again. `hex-project-setup` states the setup and that every entrypoint
calls it in block A and rule 1, not only in the migration block. `hex-architecture` says the
entrypoint's catch-all logs a non-catalogue failure without handing it back to the framework.
**Reverse by:** restoring `_handle_unexpected` as an `@app.exception_handler(Exception)`, dropping
`UnexpectedErrorMiddleware` and its `main.py` line, note and rule 6 clause; removing `configure_logging()`
from `create_app` and rule 3's added sentence, and moving the setup sentence back into
`hex-project-setup` block B and rule 6; reverting `model_dump(mode="json")` and the logged `context`; and
restoring the headings, the `UNIT_OF_WORK.md` lead, the replaced paragraphs and the indexes' "no
middleware", from the parent of the commits that added this entry.

### D134 — A universal `persistence` skill owns every store-generic data-access obligation
Taken by the maintainer on 2026-09-28 (backlog items 14 and 21, "all store-generic"), revised by a
four-lens review and a re-verification. One universal reference skill, `persistence`, holds what every
program with a store obeys whatever its family: one transaction owner per callable and none across two
stores; driver errors translated at the data-access edge on every public method, by one translator
shared from the second class onwards, with the field and the full constraint name in the context;
constraint names from one convention, matched whole; a pure row mapping; instants stored unambiguously;
the stored shape decided by meaning, a closed set or a length limit being the program's rule and not a
stored type; indexes on what is filtered, joined and sorted; a table name derived by one rule; no schema
created as a side effect of reading or writing; explicit conflict resolution where a write resolves one;
an older write never replacing a newer one (a conditional write, else a single writer per key);
deduplication by the store; a total order on every paged read; migrations run once, before the new code
touches the store, with expand-then-contract only where two releases run at once; reversible revisions;
no logging. A precondition table says which rules lapse for a store without transactions, named
constraints a driver reports, a conditional write, a schema of its own, migrations, or two releases at
once. Both families had stated parts of this apart and were drifting — flat and hex set the shared
translator at the second and third class, and hex's "defaulted database-side" timestamps contradicted the
ordering stamp. Each family now keeps only its shape and binding and tells the agent to load
`persistence` before writing a file: flat keeps one package per store, the chunked multi-row write,
read-back, time-ordered keys, the settings and engine factory, retry as its cross-store choice and
migration placement; hex keeps the structural adapter and its two forms, the port's read contract, the
paired revision and the unit of work. The id policy stays in the families. The rule that `context` never
carries a library's class name holds for any translation, so it went to `exception-catalog` rule 11. The
review also made the hex templates translate every driver error on every public method, the pool's own
timeout and the unit of work's commit included (a refusal at commit is a conflict, not unavailability),
gave offset pages an id tiebreaker, and spelled flat's ordering guard in prose beside the upsert. Item 21
closes here: the flat family needs no conventions skill, and the one derivation it lacked, the table
name, is `persistence` rule 13. Declined: moving batched writes to `persistence` (the decision keeps them
in flat) and a template line for the ordering guard (item 11's decision, D131).
**Reverse by:** from the parent of the commits that added this entry, deleting
`plugins/pyhouse-universal/skills/persistence/`; restoring `flat-persistence` rules 1–21 and its
precondition table, `hex-persistence` rules 1–18, its Evolution section and topic files,
`exception-catalog` rule 11 and its two routes, `hex-store-repository` rules 7, 13–15, and the citations
in `flat-entrypoint`, `HTTP.md`, `flat-layered`, `flat-test-integration-setup`, `flat-test-persistence`,
`hex-project-setup` and `hex-conventions`; and restoring the index entries, counts, ownership row,
`plugin.json` description and `pyhouse-reviewer` pointer.
