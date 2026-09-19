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
Plan 04's `FooStorage` was single-statement, but it has to carry the "a write spanning more than one
statement is one transaction" rule and be the subject of the atomicity test. A single statement has no
atomicity to pin. Gave `record_batch` an ordinary parent-and-children shape in one `engine.begin()`.
This is not the deleted registry: no cross-service identity, no junction, no view, no kinds.

### D20 — The record rule reaches test code, but not a table-generic column mapping
Handed to plan 04 as an open question. A mapping passed to a `Table`-parameterised bulk helper is
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
It reconciles the two families' upstream-failure class names (`UpstreamError` vs
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
The obligation said the batch loop is "an unbounded loop with an explicit counter, never a bounded loop
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
