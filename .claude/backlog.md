# Backlog — catalogue edits not yet made

Each entry is **Proposed** (awaiting the maintainer's decision) or **Agreed** (decided, not yet done).
Remove an entry in the change that does it; record the decision in `DECISIONS.md` as usual.

## Agreed

Item 55 predates the rest; 86–87 are the remaining build steps of one agreed design, done in order,
one branch each. Every other item has landed or was closed (D130–D178). The first four steps of that
design landed as D186, D187, D188 and D190.

### 86. Running several changes at once
`/orchestrate` and `delivery-runner` — one runner per change in its own worktree, step agents under it
— plus `/adopt` and `/install-worktree-hook`, which links a repository's untracked environment files
into each new worktree.

### 87. A retrospective over released changes
`/retro`: the defects found after a change landed, which check each escaped, and the rule or test that
would close it — the loop D186 was the first output of.

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
rather than by file, would cut the cost of the largest diffs. Measured on the next real changes it
reviews, not by rerunning the calibration set.

### 89. One shared acceptance environment, taken in turn
Input to 86. In an adopted repository running about eight sessions at once, specs and implementations
each checked criteria on the one shared stand, and found it busy only by looking: one spec session
stopped because another implementation had rebuilt the stand from its own worktree, and each asked the
person whether the stand was free. Since D189 a spec runs its criteria on the stand too, so the stand is
contended at spec time as well as at acceptance. Proposal: the session that takes the environment
records it where the others look (a lock the project names, or a line in the run plan), and the others
wait for it instead of asking the person; `/orchestrate` hands the environment out in turn. Whether the
record belongs to `delivery-spec` rule 7, to `/pyhouse-delivery:implement` step 8 or to 86 alone is
decided with 86.

### 90. Fewer separate waits on the person in `/pyhouse-delivery:implement`
The first real run of the command (D190) stopped for the person at four separate moments: three tester
questions, consent for acceptance asked early, then whether the stand was free, asked twice — once
before the fix round and once after it. Each wait was right, but with several sessions running, the
person answered each one through another session, and answers took 30–55 minutes to come back.
Proposal: step 8 asks consent, the person's steps and whether the environment is free in one message,
once, right before the prover starts; the fix round does not ask again unless the environment changed.
Decide after the next two runs, not on one.
