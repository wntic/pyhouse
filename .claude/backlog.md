# Backlog — catalogue edits not yet made

Each entry is **Proposed** (awaiting the maintainer's decision) or **Agreed** (decided, not yet done).
Remove an entry in the change that does it; record the decision in `DECISIONS.md` as usual.

## Agreed

Item 55 predates the rest. 104 is the measurement of the simplified `pyhouse-delivery` (D192), its
thresholds set before the first spec. 87 waits until there are defects found after a change landed to
run it on. Every other item has landed or was closed (D130–D178, D191, D192).

### 104. Judge the simplified `pyhouse-delivery`
The simplification of D192 is judged on the next three to five specs implemented with it: the person's
minutes, the share of the window (`/usage`), and what the review finds. Thresholds, set before the
first of them:
- more than two waits for the person on a spec — not counting "merge" or a question about a defect of
  the spec — or more than two full gate runs in one implementation: find the step that caused them;
- a test written to fit the code about to be written rather than the spec, on two specs of five — seen
  by the review through `--tests-at` or in the tests' base: a separate test writer returns;
- a wrong Important finding, answered "wrong" by the implementer or the person, on two specs of five:
  verify returns;
- a defect found after landing that the old acceptance on the stand would have caught: that case is
  examined on its own before anything returns.

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
