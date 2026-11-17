# Backlog — catalogue edits not yet made

Each entry is **Proposed** (awaiting the maintainer's decision) or **Agreed** (decided, not yet done).
Remove an entry in the change that does it; record the decision in `DECISIONS.md` as usual.

## Agreed

87 waits until there are defects found after a change landed to run it on. Every other item has
landed or was closed (D130–D178, D191, D192, D195–D198, D201).

### 87. A retrospective over released changes
`/retro`: the defects found after a change landed, which check each escaped, and the rule or test that
would close it — the loop D186 was the first output of. Deferred (D192) until such defects exist: in
the repository it would run on, most defects testing will find predate the pipeline, and half its
steps are gone.

## Proposed

108–111 come from a read of ECC (github.com/affaan-m/ECC, commit `d2ef268`, 2026-11-06, version
2.2.3), a multi-language agent kit of 71 agents and 314 skills, compared with the catalogue on
2026-11-17. ECC paths below are at that commit. Most of ECC was not taken: about 35 of ~70 Python rules
the catalogue already states, ~8 are performance (D196), ~15 bind one stack; its two-reviewer and
generator/evaluator loops are what D185, D192 and D195 removed; and its Python material contradicts the
catalogue in many places — `Optional[X]`, an HTTP status on the exception class, log-and-re-raise,
`create_all` at startup, settings built at import, `@patch` and an in-memory sqlite in tests. These four
are what survived.

### 108. A harness that measures whether an agent follows a skill under a naive prompt
ECC's `skills/skill-comply` (`SKILL.md`, `prompts/`, `scripts/runner.py`) generates, for one skill or
rule, the behaviour it expects as 3–7 ordered steps, then one task at three prompt strictness levels —
supportive ("use TDD to implement …"), neutral (the task only), and competing ("quickly implement …,
tests are optional") — runs each through `claude -p` with stream-json, and classifies the tool-call
trace against the steps, checking order deterministically (`prompts/scenario_generator.md`,
`prompts/spec_generator.md`). The catalogue judges by outcome and has measured it only by hand: D178
(39 headless Opus runs on which skill loads) and D182 (9 runs on the outbox), each scripted afresh. The
competing level is the prompt this catalogue exists for — two sentences, no layout, "just make it work".
Proposal: a maintainer tool under `tools/`, not shipped in a plugin, that runs a fixed prompt set with
the checkout's plugins loaded by `--plugin-dir` and user settings excluded, and reports per run which
skills loaded and whether each loaded before the first `Write`/`Edit` — the part a trace answers without
a model — leaving what the code looks like to be read, as D182 did. Not taken from ECC: its LLM
classifier of tool calls (the catalogue's question is the structure written, not the call sequence), its
auto-generated scenarios (a fixed set is what makes runs comparable across releases), and its "promote
to hook below 60% compliance" advice. Open: whether the prompt set lives in `tools/` or in `.sources`;
which model it runs on, given that Haiku is not evidence; and whether its first use is to re-run D178 now
that the catalogue has 53 skills.

### 109. An agent bypasses the commit-msg hook with `--no-verify`
ECC ships a PreToolUse hook, `scripts/hooks/block-no-verify.js:3-6`, that "blocks git hook-bypass flags
(--no-verify, -c core.hooksPath=) to protect pre-commit, commit-msg, and pre-push hooks from being
skipped by AI agents". The catalogue's own run shows the case: in the hand-over for spec 064 "the agent
committed it with `--no-verify`, so the commit hook has not checked it"
(`.sources/delivery/runs/timelines/064-067-impl-detail.txt:39`), the one case seen. Our hook teaches
it: on a rejection it prints `Bypass once with --no-verify.` (`plugins/pyhouse-git/git-hooks/commit-msg:66`),
and the agent reads that output. Nothing in `delivery-implementer`, `/implement` or
`/pyhouse-git:commit` forbids it, and `delivery-change-contract` rule 6's diff cannot see a bypass, since
no file changes. A malformed type that skipped the hook reaches `/release`, which trusts the types it
reads (D200). No harm yet: the 064 commit was a `fixup!`, which the hook skips anyway (D65), and the gate
re-ran the lint. D65 keeps the escape hatch documented on purpose — a hook that cannot be bypassed gets
deleted rather than fixed — so any remedy leaves the human's bypass open. Options, cheapest first:
(a) one line in `delivery-implementer`'s never-list and in `/pyhouse-git:commit` — a hook's refusal is
fixed or reported, never bypassed; (b) `/implement` re-runs the installed `commit-msg` over every
message on the branch before the review, catching rather than forbidding, as D190 prefers; (c) a
PreToolUse hook in `plugins/pyhouse-git/hooks/` (the directory D65 keeps free for one), which binds the
agent only and is still evaded by a script or `git commit-tree`. Open: whether the hook's rejection text
should stop advertising the bypass, given that D65 put it there for the person.

### 110. Which failures a retry repeats, and which calls it may repeat
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

### 111. Data migrations in `persistence`, and the security lint family
Two gaps found on the way, neither from a defect.

Data migrations: ECC's `skills/database-migrations/SKILL.md:24` — "Schema and data migrations are
separate — never mix DDL and DML in one migration" — and `:102-125`, a backfill in bounded batches
rather than one transaction over the table. The catalogue has the separation only in `hex-persistence`
(`SKILL.md:44`, a routing line; `:178`, a hard stop), with no reason given; `persistence` rules 19–20
and `flat-persistence` are silent, so a flat service never meets it. That half is placement (lens 2):
the obligation and its reason move to `persistence`, and `hex-persistence` points at it. The batching
half is performance and stays out under D196 unless a review finds it.

Security lint: ECC's `agents/python-reviewer.md:28-32` lists SQL or a shell command built from strings,
path traversal, `eval`, unsafe deserialization and YAML's unsafe load. The catalogue states none, and
`python-toolchain` rule 3 keeps the linter's selection narrow without the security family (ruff's `S`,
from bandit) and without a decision saying why. The model already knows these and a linter catches most,
so the proposal is not a rule but a decision either way: add `S` to the selection, or record why it is
left out.

### 112. A security review before a service is first exposed to the internet
The maintainer builds web applications and other services that will be reachable by anyone on the
internet, and a service an agent wrote in a short time is an easy target. Wanted: a check of the code
for security before its first deploy. The catalogue has nothing for this — `/pyhouse-universal:change-review`
reviews one change for what it breaks, not a whole codebase for what an attacker can reach, and 111 asks
only whether the linter's security family is selected. A candidate to start from is Cloudflare's
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

### 113. How much context the catalogue's listing takes now
The maintainer remembers that the descriptions passed the default listing budget (1% of the context
window, ~10k tokens) and that the budget was raised to 2% (~20k). Measured from the frontmatter on
2026-11-17: 53 skill descriptions are 41,362 characters (~10,300 tokens at four characters a token), 11
command descriptions 2,513, and 2 agent descriptions 1,474 — about 45,000 characters, ~11,300 tokens,
before names and the listing's own formatting. `meta-skill-author`'s "Length" section still says
~38,700, and D178 ~38,300; both are stale. D178 measured the default budget at 30,000 characters, so the
catalogue alone overruns it by half and the least-invoked skills are listed by name only; the
`README.md` tells a user to set `"skillListingBudgetFraction": 0.02` to list them all, and `/pyhouse:setup`
does not set it, since which skill loaded did not depend on it. The maintainer's
`~/.claude/settings.json` does not carry the setting; where it is set, if anywhere, is unchecked. Other
installed plugins share the same budget. To do: measure what a session actually spends — `/context` in a
project with the catalogue and the maintainer's usual plugins installed, at the default and at 0.02 —
and update the stale figures. Open: whether a 2% budget still holds the catalogue with other plugins
beside it; and whether the size matters beyond D178's finding that names carry the routing — the
listing is paid on every session, and D178 did not measure what the agent then wrote.

### 114. A read, a decision in code and a write back lose a concurrent update
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

### 115. Books as evidence for the catalogue, never shipped in it
The maintainer generated two skills from books with `book-to-skill` — `khononov-coupling` (Vlad
Khononov, *Balancing Coupling in Software Design*) and `kleppmann-ddia` (above) — and asked whether they
belong in the catalogue. Judged 2026-11-17: the summaries are accurate where they could be checked, but
they do not ship. They are reference, not obligations, and restate rules the catalogue already gives an
owner (`coupling` is Khononov's model restated with credit; DDIA overlaps `persistence` and
`at-least-once-delivery`), so a rule would have two owners. They fire on studying a book, not on writing
a service, so an agent's output does not change, and the model already knows DDIA well. They would add
~900 characters to an overrun listing (113). And `khononov-coupling` bundles 22 figures extracted from
the PDF beside detailed chapter summaries, which a public marketplace cannot redistribute. Proposal: a
book skill stays in the maintainer's user scope, or in `.sources` if it is to be versioned, and serves
as a lens — read beside the owning skill to ask which obligation the book states that the owner lacks,
with each finding going through `/review-skills` like any other and the book cited in the decision
record only, per CLAUDE.md's "Source material is evidence". 114 is its first output.

What is taken is a fragment, never the skill. A fragment reaches a skill only past five filters: (1) it
is an obligation on code, not knowledge — "LSM versus B-tree" or "percentiles, not averages" is
knowledge; (2) it passes lens 1 against the test services in `QUESTIONS.md` — a template line only where
most have it, otherwise one sentence of prose; (3) an owning skill exists and does not already state it,
checked by a search of `plugins/`; (4) it is restated in the catalogue's words without mechanism, the
book cited only in the decision record, which also keeps the book's text out; (5) an agent without the
rule gets it wrong — the model knows DDIA but does not apply it unprompted, and that gap is what a rule
is for, so a candidate is tried on a short prompt (for 114, a service with a PATCH endpoint: does the
agent read, decide and write back unguarded?) and a seen defect earns the rule, which 108's harness
would make routine. Systematic form: one agent per pair of book and owning skill, given `QUESTIONS.md`
and these filters; each finding verified against `DECISIONS.md` by an agent that did not write it;
survivors land here.

Candidates already seen in `kleppmann-ddia`, past filter 3 only (searched 2026-11-17): a lost update
(114); retrying only transient failures (110); a duration or timeout measured with a monotonic clock,
never the wall clock, which jumps — nothing in `plugins/` names a monotonic clock, and the owner would
be `python-style`; and a consumer of a message tolerating fields it does not know, since during a rolling
deploy old and new versions read each other's messages — `extra="ignore"` appears only on settings
classes, and the owner would be `coupling` or `at-least-once-delivery`. A client-chosen id with a unique
constraint for effectively-once looks covered by `at-least-once-delivery` rule 6. Fewer are expected
from `khononov-coupling`, since `coupling` is built on that book; its rebalancing and case-study chapters
(`ch11`, `ch13`) are where a gap would be. Open: whether the procedure is written down (in `.sources`, or
as a maintainer command), and which books come next.

### 116. A second `change-reviewer` in `/implement`'s review step
Asked by the maintainer (2026-11-16): whether the review step gains from two find runs, with a third
agent confirming or refuting their findings. The verifier half was tried and removed — it refuted none
of 13 calibration findings nor any in 17 `/implement` runs (D187, D192) — so the question is the second
finder. Measured 2026-11-16/17, 8 headless Opus runs of the v0.35.0 `/change-review` on three producer
diffs from the 2c calibration (`.sources/delivery/steps/2-review/calibration-2d.md`, raw outputs in
`raw/cal-out-2d/`). Repeats did not catch what calibration missed: D10 0 of 3, D12 0 of 3, so those
misses are the lens questions' limit, not a run's chance. The other findings did differ between runs:
on the 44-file diff three findings recurred in every run and one run added two more Important ones; on
the 232-file diff four distinct serious findings appeared, each run seeing one or two; on the clean
diff one run found an Important weakened test the other did not. Duplicates across runs are obvious, so
a judge would mostly merge. None of the extra findings is verified, and none is fixed at the producer's
current head. The runs cost $35.97, $4.50 each against $2.64 in 2c, about 40% of a five-hour window by
2c's ratio; two finders and a judge would make the step about $9–14 a feature. To do: the maintainer
checks the seven extra findings and the recurring core against the producer, then decides — mostly real
earns a second finder, at least on large diffs; mostly false keeps one (D192). Open: whether a second
finder is worth its cost when the review's known misses are ones a repeat does not reach.

### 117. The guard that keeps an agent out of secret files, shipped as a plugin hook
Asked by the maintainer (2026-11-17), after copying env files into worktrees by hand for every spec run
in parallel: agents were refused by a PreToolUse hook that lives outside the catalogue, in two copies
kept by hand (user settings and one repository's `.claude/`). It refuses any Bash command whose text
contains the dotenv token and any Read or Grep of such a path. The 359 refusals in the producer's
transcripts (2026-10-16 … 11-13, `.sources/delivery/runs/2026-11-17-env-hook.md`): 15 (4%) read values,
the hook's purpose, nearly all a non-secret URL, list or setting; the rest read nothing — the name in a
grep pattern, an exclusion, a document edit or a jsonpath (176), an existence or gitignore check (64), a
template other than exactly `.env.example` (36), loading into a process (29), a key edit or a copy (24).
After a refusal agents dropped the step silently (31) or hid the token (11); subagents never escalated
once. Worktrees were made without their env files and removed without comparing them. The hook misses
reads all the same — a heredoc with a redirect, `$(…)` inside a commit message — and every destruction
that does not name the file: `>` over an existing one, `git clean -x`, `git worktree remove --force`.

Decided with the maintainer, the rewrite refuses reading content and destroying a file, never naming
it. Allowed: a mention, an existence check, any `*.example`, appending, editing keys in place, loading
into a process unless the command prints values (`docker compose … config`, `… exec … env`), and a copy
or move whose target is dotenv-named, git-ignored (checked, not inferred from the name — a project's
ignore list rarely covers `.env.local` or `.env.bak`) and absent. Refused: reading content; `rm`; `>`,
`truncate`, `cp` or `mv` over an existing file; `git clean -x`/`-X`; `git worktree remove --force` and
`rm -r` on a directory that holds one. Acceptance: the recorded commands — every value read still
refused, the false positives gone.

Proposed: ship it as a plugin's `hooks/hooks.json`, versioned like any change here. A plugin's hooks
run once it is enabled, so `/pyhouse:setup` installs nothing for it, and the hand-kept copies are
deleted. Open: which plugin — not `pyhouse`, which holds no rule. A plugin of its own outside the skill
graph, like `pyhouse-git`, since dotenv files are not Python's, `pyhouse` depending on it; it can then
be disabled alone, and a plugin's hook cannot be switched off without its plugin. Or
`pyhouse-delivery`, whose rules the hook enforces — but those rules must change with it: `delivery-spec`
rule 7 sends "handling a secret" and any edit of a file of secrets to the person as a script, which an
agent that may copy and edit without reading no longer needs. Also open: whether "an agent never reads
a file of secrets" belongs in a universal skill (`python-settings` owns the secret) rather than only in
delivery's two rules.
