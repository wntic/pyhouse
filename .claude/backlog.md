# Backlog — catalogue edits not yet made

Each entry is **Proposed** (awaiting the maintainer's decision) or **Agreed** (decided, not yet done).
Remove an entry in the change that does it; record the decision in `DECISIONS.md` as usual.

## Agreed

Item 55 predates the rest. 87 waits until there are defects found after a change landed to run it on.
Every other item has landed or was closed (D130–D178, D191, D192, D195).

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
rather than by file, would cut the cost of the largest diffs. To be measured with `/usage` on specs after
verify is gone, not by rerunning the calibration set; the fourteen that closed 104 took none (D195).

### 105. A live check that does not wait on the person piece by piece
Measured on the first twelve specs under delivery 0.4.1 (D195) in two adopted repositories: consent and credentials
for the live check caused most of the person's waits — on six specs; one spec spent three questions in a
row on a user's password and then an admin login, and skipped the check; one waited 56 minutes for
leave to start a cluster profile the repository uses only for this. The person's words: do it yourself
end to end, and where a hook stops you, hand me a script to run. `delivery-change-contract` rule 9
already leaves whose environment it is to the person, and `/implement` reads what the project says about
its environments, so part of the fix is the project naming its own. Proposed for the catalogue: the
implementer finds or creates throwaway credentials and environments itself; what it cannot reach comes to
the person once, as one script to run, never as a series of questions; consent for an environment others
use is asked once, before the build, not mid-run.

### 106. Adding a decision record or a guarding rule is not an edit to what is frozen
In the same twelve specs, four stopped to ask whether a new entry could go into the frozen decision
records, and one whether two new rules could go into the architecture test; the answer was yes every
time, and a spec that named the record in its scope asked nothing. Proposed for
`delivery-change-contract`: a new decision record and a new rule in a guarding check are free and read
by the review in the diff; changing, removing or loosening an existing one stays frozen. Whether a new
record contradicting an old one is "changing" it is the question to settle first.
