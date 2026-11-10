# Backlog — catalogue edits not yet made

Each entry is **Proposed** (awaiting the maintainer's decision) or **Agreed** (decided, not yet done).
Remove an entry in the change that does it; record the decision in `DECISIONS.md` as usual.

## Agreed

Item 55 predates the rest. 104 is the simplification of `pyhouse-delivery` agreed in D192; 98, 99 and
100 are done with it. 87 waits until there are defects found after a change landed to run it on. Every
other item has landed or was closed (D130–D178, D191, D192).

### 104. Simplify `pyhouse-delivery`
Agreed in D192, from what each step of `/pyhouse-delivery:implement` caught and cost over seventeen
runs in an adopted repository. The change is breaking for `pyhouse-delivery`, and touches
`/pyhouse-universal:change-review`.
- **No acceptance step and no criteria as commands.** A spec says in words what must be true once the
  change is done; tests are written from it, and its wording may be refined during the work, the edit
  visible in the diff. Its goal and scope are frozen: an agent stops and asks before changing what the
  change does or leaves alone. Done is the project's gate passing. `delivery-prover` goes.
- **The spec's form.** A feature keeps Goal, In/Out — which absorbs **Where the code goes** as one
  line — and Contracts, all three frozen; Behaviour and failures, free, the list the tests are written
  from; Source, Depends on, Settings and metrics where they apply. **Tests** and **Acceptance
  criteria** go; in their place an optional **How to see it working**, only where the change shows
  only in a running process — in words, no commands, not frozen, a hint for the implementer's live
  check. A fix keeps Symptom, Cause and Regression test and has no criteria.
- **What `/pyhouse-delivery:spec` checks before code** is the spec's claims about today's system, not
  commands: a fix's cause reproduced or read in the code, or why it cannot be; a feature's statements
  about existing code and data set against them. Reading only; anything that writes needs consent. A
  spec is ready once the person has accepted the draft and its claims are checked. `delivery-spec`
  rule 8 — a person's step as a command or script — stays, its consumer now the merge body; rules 6,
  7, 9, 10 and 11 go, and 12–13 are rewritten for the new readiness and the frozen sections.
- **The implementer checks its own work.** It runs the gate, and where the change is seen only in a
  running process, starts the fewest services that show it, exercises them through their public surface,
  reads their logs and stops them. No stand and no description of how to start one; an environment
  others use, shared services and secrets are not touched without the person's consent. Its report shows
  each command and its output, not a claim.
- **Tests before the code, by the implementer.** For a feature: names with no behaviour, the tests from
  the spec, each failing on an assertion or the not-implemented marker, committed as the tests' base,
  then the code. For a fix: the regression test seen failing on today's code, then the fix.
  `delivery-tester` and the skeleton step go. `--tests-at` stays, so an edit to a test after its base is
  judged by the review.
- **No declarations.** What remains of `delivery-change-contract` is the short frozen list — the checks
  that guard the repository, the decision records, what a test written before the code asserts, the
  spec's goal and scope — the diff of those paths checked before the review, and the review judging an
  edit to a test.
- **`/change-review` without verify.** One find run sets severity and marks what predates the change; a
  wrong finding is answered by the implementer's "wrong: <why>" or by the person. The outcome line loses
  "refuted".
- **A short hand-over.** The merge body says what changed and why, the decisions the spec did not make,
  the person's steps after landing as a script, the review's outcome line and only the findings not
  fixed. The reply adds the gate's command and result, the live check where one ran, and the open
  questions; nothing else.
- **One path.** A fix and a feature differ only in the implementer's first step, so there is no second,
  lighter lane.

Judged afterwards on the next three to five specs: the person's minutes, the share of the window
(`/usage`), and what the review finds. Thresholds, set before the first of them:
- more than two waits for the person on a spec — not counting "merge" or a question about a defect of
  the spec — or more than two full gate runs in one implementation: find the step that caused them;
- a test written to fit the code about to be written rather than the spec, on two specs of five — seen
  by the review through `--tests-at` or in the tests' base: a separate test writer returns;
- a wrong Important finding, answered "wrong" by the implementer or the person, on two specs of five:
  verify returns;
- a defect found after landing that the old acceptance on the stand would have caught: that case is
  examined on its own before anything returns.

### 98. The implementer runs the repository's guard tests on the tests it writes
In two of six runs the first full gate failed on the architecture test, which bans a multi-line
docstring — once on a fix's regression test, once on a feature's tests before the code — and each cost a
second full run. Before it commits tests, the implementer runs the checks the repository's
`CLAUDE.md` lists as guarding, beside its linters, on the files it wrote, and its report shows their
output; a test commit that fails them is sent back like a test that passes.

### 99. Folding fixups without moving the branch's base
`git -c sequence.editor=: rebase -i --autosquash main` (`.claude/commands/commit.md` step 5 and the
spellings in `git-branching`) also replays the branch onto wherever `main` stands now; in two runs the
fold, made after the gate and the review, brought in code neither had seen. Fold onto the point the
branch left from — `rebase -i --autosquash $(git merge-base main HEAD)` — and check that the tree is
unchanged by `git diff <before> <after>`; a non-empty diff means the branch moved and the gate runs
again. Bringing in the mainline stays the merge's job.

### 100. A person's step after the change lands is a script, and a shared run names what it recreates
Two fix specs carried their after-merge step — set a value in an environment file the agent may not
read, then restart the service — as prose, and the person asked for the script both times. The step goes
in the merge body as the script `delivery-spec` rule 8 already asks for. Running a restart, the agent
asked first, but the command also recreated two shared services, said only afterwards: a request to run
anything in an environment others use names everything the command recreates, read from its definition,
before asking.

### 87. A retrospective over released changes
`/retro`: the defects found after a change landed, which check each escaped, and the rule or test that
would close it — the loop D186 was the first output of. Deferred (D192) until such defects exist: in
the repository it would run on, most defects testing will find predate the pipeline, and half its
steps are gone.

### 55. Performance obligations, placed with their owners
No `performance` skill: a bag of tips would restate rules other skills own. Two groups, each with an
owner. Language-level, a universal skill on async code: no blocking I/O or CPU-bound work inside a
coroutine (today one `## Other bindings` bullet in `hex-capability-adapter`), concurrency always
bounded, a client or pool built once per process rather than per call. Data access, in `persistence`:
no query per item in a loop, filtering and paging in the store rather than in Python, only the columns
and rows used, and every filter of a hot query backed by an index. Only what is expensive to retrofit
and checkable in review belongs; a micro-optimisation without a measurement does not. The maintainer
collects concrete findings from the lead's reviews first, and each becomes a rule.

## Proposed

### 88. Bound what `/change-review` reads in full on a large diff
Calibrated at about 3% of a five-hour window per review, and nearly twice that on a diff of 179 files,
of which it read about seventy in full (D187). A ceiling on full reads, or reading by lens question
rather than by file, would cut the cost of the largest diffs. Measured on the specs that judge 104,
after verify is gone, not by rerunning the calibration set.
