# Backlog — catalogue edits not yet made

Each entry is **Proposed** (awaiting the maintainer's decision) or **Agreed** (decided, not yet done).
Remove an entry in the change that does it; record the decision in `DECISIONS.md` as usual.

## Proposed

None. Every item proposed up to 121 was decided on 2026-11-18 (D204): 116 closed, 120 folded into 117,
the rest agreed below.

## Agreed

Taken in this order: 112, 118. Waiting: 87 for defects found after a change landed; 110 and 114
for a run of `tools/measure_skill_loading.py --full` on the prompt each names; 121 for a rewrite of a
generated service through `/implement`. Every other item has landed or was closed (D130–D178, D191,
D192, D195–D198, D201–D210, D212).

### 87. A retrospective over released changes
**Waits** for defects found after a change landed.
`/retro`: the defects found after a change landed, which check each escaped, and the rule or test that
would close it — the loop D186 was the first output of. Deferred (D192) until such defects exist: in
the repository it would run on, most defects testing will find predate the pipeline, and half its
steps are gone.

110 comes from a read of ECC (github.com/affaan-m/ECC, commit `d2ef268`, 2026-11-06, version
2.2.3), a multi-language agent kit of 71 agents and 314 skills, compared with the catalogue on
2026-11-17. ECC paths below are at that commit. Most of ECC was not taken: about 35 of ~70 Python rules
the catalogue already states, ~8 are performance (D196), ~15 bind one stack; its two-reviewer and
generator/evaluator loops are what D185, D192 and D195 removed; and its Python material contradicts the
catalogue in many places — `Optional[X]`, an HTTP status on the exception class, log-and-re-raise,
`create_all` at startup, settings built at import, `@patch` and an in-memory sqlite in tests. This one
is what survived still open; 108 landed as D210, 109 as D206, and 111 as D202 and D203.

### 110. Which failures a retry repeats, and which calls it may repeat
**Waits for a run.** Tried on a short prompt first, with `tools/measure_skill_loading.py --full`: a
rule only if Opus, unprompted, retries a rejection or repeats a write that is not idempotent.
ECC states it in `skills/error-handling/SKILL.md:376` — "Retry logic only retries retriable errors (not
4xx client errors)" — with `retryIf` at `:343`, and breaks it itself in
`skills/backend-patterns/SKILL.md:318-340`, a retry around every error. The catalogue states only where a
retry lives: `flat-entrypoint` rule 4 (declared where the work is invoked), `hex-capability-adapter`
rule 10 (the client's own policy, never the adapter). Nothing says which failures are worth repeating —
a rejection repeats to the same answer and only delays the failure — or which calls may be repeated at
all: a write that is not idempotent, repeated after a timeout whose outcome is unknown, repeats its
effect. Only the outbox relay carries the same-key-per-attempt idea (`at-least-once-delivery` rule 6).
A search for "transient", "retriable" and "retryable" in `plugins/` finds nothing, and no decision
covers it. It passes lens 1: it holds for a retry library, an HTTP client's transport retries or a
broker client, in either family, and any test service that calls a third party has a retry. Proposal:
an obligation, without mechanism, in `at-least-once-delivery` — rule 6 widened from the relay to any
caller that retries — or one sentence beside each family's placement rule. Open: no generated service
has shown the defect yet, and a defect becomes a rule; whether the generality alone earns it.

### 112. A security review before a service is first exposed to the internet
**Agreed, first, as research:** the comparison and one trial run below, before anything is written
here. The likely outcome is a third-party skill installed beside the catalogue rather than one it ships.
The maintainer builds web applications and other services that will be reachable by anyone on the
internet, and a service an agent wrote in a short time is an easy target. Wanted: a check of the code
for security before its first deploy. The catalogue has nothing for this — `/pyhouse-universal:change-review`
reviews one change for what it breaks, not a whole codebase for what an attacker can reach, and the linter
selects only six of its security rules (D203). A candidate to start from is Cloudflare's
`security-audit-skill` (github.com/cloudflare/security-audit-skill, MIT, read 2026-11-17): six phases —
reconnaissance into an architecture note and a coverage ledger of trust boundaries and input surfaces,
hunting by isolated sub-agents assigned from the ledger, a fresh verifier trying to disprove each
candidate, findings written as confirmed / needs-validation / rejected against a JSON schema, an
independent re-check of each record's source claims, and a report — with attack-class guides (HTTP and
authentication, client-side code, supply chain and CI, cloud and deployment, serialization and queues,
resource exhaustion, data isolation, LLM-backed targets, and more) and Node validators for its outputs.
It is multi-agent by design. Claude Code's own `/security-review` exists and has not been compared. To
do: look for other credible security-review skills and checklists, compare them with Cloudflare's, and
try the best on one real service before its deploy. Open: whether the catalogue ships anything at all
or the maintainer installs a third-party skill beside it — the catalogue's rules state obligations, and
a security audit may be a tool rather than a rule set; if obligations come out of it (an untrusted input
validated at the boundary, secrets never in the repository), which existing skill owns each; and how
many agents a run costs against the two the delivery pipeline settled on.

### 114. A read, a decision in code and a write back lose a concurrent update
**Waits for a run.** D207's filter 5 decides it: whether Opus guards a PATCH endpoint's read-modify-write
unprompted, tried with `tools/measure_skill_loading.py --full`.
Found by reading `kleppmann-ddia` — a skill the maintainer generated on 2026-11-15 with
`book-to-skill` (github.com/virgiliojr94/book-to-skill) from Martin Kleppmann's *Designing
Data-Intensive Applications* (O'Reilly, 2017), kept outside the catalogue — against `persistence`. Its
`chapters/ch07-transactions.md` (lines 17, 31, 37, 41) restates the book: a read-modify-write in
application code with no lock, no compare-and-set and no atomic update loses one of two concurrent
updates, and the database's default isolation level (often read committed) does not stop it; a read of
a premise, a decision in code and a write that changes the premise (write skew) needs serializable
isolation or an explicit lock. `persistence` rule 16 covers a different case — an older write arriving
after a newer one for the same key, guarded by an ordering stamp — and nothing in `plugins/` names a
lost update, write skew or an isolation level (searched 2026-11-17). Candidate obligation, without
mechanism: where a write depends on a value the same callable read, the write is made conditional on
that value still holding — an atomic update in the store, a version or compare-and-set guard, or a lock
taken by the read — never read, decided and written back unguarded. Lens 1: a CRUD service with
concurrent updates to one aggregate has it; a feed poller writing what it finds, an LLM worker storing
one result per record and a proxy that stores nothing do not, so it is a rule where the service has
concurrent writers of one record, not a template line. Open: whether it is architecture or the logic
edge case the catalogue leaves alone; whether rule 16 widens to hold it or it is a rule of its own; and
that no generated service has shown the defect yet. The same chapter (line 32) also separates retries of
transient and permanent errors, which supports 110.

### 118. A project's own review checks, each triggered by the diff and read from the base
**Agreed, second:** the experiment in the producer below first; code in the catalogue only if it shows a
gain.

118 and 121 — and 120, which landed with 117 as D208, and 119, closed as D212 — come from "How the Claude Code team
thinks about verification" (Addy Osmani, claude.dev, 2026-11-16; a copy and the comparison with the catalogue are in
`.sources/articles/` and `.sources/research/2026-11-17-verification-article.md`). Much of the article is
already here: three runs then a person (D194), a flaky failure never retried or skipped
(`delivery-implementer`), no sleeping in a test (`test-principles` reliability rule 3), cheap checks
before the review, a review tied to commits, Important / Nit / Pre-existing. It is one team's practice on
a different setup — a hosted reviewer, CI, hundreds of agents — with one number behind it, so **each item
below is decided only after it is tried on ours**: the producer and the second project, Opus, and the
calibration in `.sources/delivery/steps/2-review/`.

The article's team keeps a reliability checklist of 39 items, "each with a trigger that can be read from
a diff, a check, and the incidents or PRs behind it"; the reviewer reads the diff and runs only the items
whose trigger matches, usually 3 to 10. The rules that gate a change are read "from the base or default
branch, never from the pull request's changes". A missed bug becomes such an item when it is detectable:
three finders are replayed on the incident's change, and a bug at least two find that the reviewer missed
on a small diff earns a rule. `change-reviewer` has nowhere to put what a project learned: its lenses are
fixed, and it reads no project file. The catalogue's skills do not fill that gap, since a project's past
outage — a field older records lack, a consumer outside the repository — is not an obligation of any
family. The 2d calibration's misses (D10, D12) are the case: repeated runs did not reach them (D204),
and a check written for them might. 87 (`/retro`) would be the producer of such items.

Proposal: `change-reviewer` reads a project's file of checks — trigger, check, the incident behind it —
taken from the change's base commit, never from the change, and in find mode answers only the checks
whose trigger the diff matches, each finding still standing on its scenario (D187). Not a rule set of the
catalogue's: the file is the project's, written by its owner. To test before deciding: write checks for
D10 and D12 in the producer, rerun `/change-review` on the three 2d diffs with and without the file, and
count what is found, what is newly over-flagged on the clean diff, and the cost; then try it on one diff
that played no part in writing the checks. Open: where the file lives and what it is called; whether it
contradicts "a review artifact states none of its own" (CLAUDE.md) — it states the project's, not the
catalogue's; and whether `/implement` passes the base or the reviewer finds it.

### 121. A change that promises unchanged behaviour is checked against the code it replaces
**Waits** for a rewrite of a generated service through `/implement`; until one is done, how often a
rewrite goes that way is unknown.
The article's third test type is differential: "run both the old system and the new system with the same
inputs and see if you get different results", the inputs generated or sampled from production, irrelevant
differences such as whitespace normalised, and intended differences kept as a list. The catalogue's first
use is the maintainer rewriting a service an agent wrote — one or two modules of a thousand lines — into
a family's layout, a change whose promise is that nothing a caller sees changes. Nothing in
`pyhouse-delivery` or `test-principles` speaks of such a change: a search of `plugins/` for "refactor",
"restructure" and "unchanged" finds no rule (2026-11-17). The tests the rewrite writes come from the new
code's shape, and the old code usually has none, so a behaviour lost in the move passes them. Candidate
obligation, without mechanism: where a change's goal is unchanged behaviour, its check runs the old and
the new code on the same inputs and compares what each leaves behind, with every intended difference
named in the spec. To test before deciding: restructure one real generated service with `/implement`
twice, with and without that check, and count the behaviour differences each run leaves that its tests
do not catch. Open: whether it is `delivery-spec`'s (a spec form whose goal is "unchanged") or
`test-principles`'s; and how often a rewrite really goes through `/implement` rather than by hand.
