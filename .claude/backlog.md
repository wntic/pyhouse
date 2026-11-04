# Backlog — catalogue edits not yet made

Each entry is **Proposed** (awaiting the maintainer's decision) or **Agreed** (decided, not yet done).
Remove an entry in the change that does it; record the decision in `DECISIONS.md` as usual.

## Agreed

Item 55 predates the rest; 83–87 are the build steps of one agreed design, done in order, one branch
each. Every other item has landed or was closed (D130–D178). The first step of that design landed as
D186.

### 83. A full review in `/code-review`, calibrated before it is built
`/pyhouse-universal:code-review` becomes the review a change goes through before it lands: lenses, one
verifier that tries to refute each finding, severity by the failure scenario, one recheck on the fix
diff, the outcome kept. A `change-reviewer` agent carries the verify mode and a test-strength lens
against `test-principles`. Built only after calibration: the defects an adopted repository shipped,
with clean branches as negatives, run through both the built-in `/code-review` and this one. If the
built-in finds the bugs, the catalogue's review states no rules of its own (D53 holds); if not, D53 is
revisited by its own entry, with CLAUDE.md and the command's "hunts no bugs".

### 84. A `pyhouse-delivery` plugin, and how a spec is written
A sixth plugin depending on `pyhouse-universal` only: `delivery-spec` and `/spec` — acceptance
criteria a check can decide, written with the person, and what an artifact's mode (free, declared,
frozen) lets an implementer change. `CONVENTIONS.md`'s line excluding use-case authoring changes here.

### 85. `/implement` and its step agents
`delivery-change-contract`, `/implement`, and `delivery-tester`, `delivery-implementer` and
`delivery-prover`: tests first, implementation against them, proof against the criteria, a bounded
number of fix rounds, and the review from 83 before the change is offered to land.

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
