# Backlog — catalogue edits not yet made

Each entry is **Proposed** (awaiting the maintainer's decision) or **Agreed** (decided, not yet done).
Remove an entry in the change that does it; record the decision in `DECISIONS.md` as usual.

## Agreed

Item 55 predates the rest; 87 is the remaining build step of one agreed design. Every other item has
landed or was closed (D130–D178). The steps of that design landed as D186, D187, D188, D190 and D191;
running several changes at once was dropped (D191).

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
In an adopted repository running about eight sessions at once, specs and implementations each checked
criteria on the one shared stand, and found it busy only by looking: one spec session stopped because
another implementation had rebuilt the stand from its own worktree, and each asked the person whether
the stand was free. Since D191 one implementation runs at a time while the next change's spec is
written beside it, and the stand is asked for once, before acceptance — but a spec's checks still run
on it at the same time. Proposal: while an implementation holds the stand, a spec's checks only read
it; a check that writes waits for a line the project names as the stand's lock, which the session
holding it writes and clears. Whether the lock belongs to `delivery-spec` rule 11 or to
`/pyhouse-delivery:implement` step 8 is decided with the wording.

### 91. Less of the person's time per change — possible, not yet wanted
The maintainer's verdict after the first days of real use: the checks are worth it, but answering
eight sessions through a ninth costs more of the person's time than any agent spends. Watched first,
decided later; three candidates:
- **Two lanes by risk.** A fix, or a local feature with no contracts and no shared environment, goes
  through the implementation, the gate and `/pyhouse-universal:change-review` alone; the full
  `/pyhouse-delivery:implement` is kept for a change to contracts, shared configuration or an
  environment others use.
- **A standing agreement for an environment the person owns.** `delivery-spec` rule 11 asks before
  every run that writes. Where the project's instructions record that an environment is the person's
  and what an agent may do in it, that record could stand for the agreement, with the bans it lists
  still holding.
- **The agent decides what is not frozen.** A name, a small fork the spec leaves open: decided, recorded
  and listed in the handover, never asked; a stop only for a frozen artifact or money.

### 92. A fix's code is all "declared"
A fix takes the short form, which has no **Where the code goes**, so `delivery-change-contract` reads
every code edit of a fix as outside the named packages: in the first fix run all three code edits were
declared, and the declarations repeated the diff. Proposal: for a fix, the code its **Cause** names is
the change's own and free. Decide on one or two more fix runs.
A feature shows the same: in a run of 129 files, about thirty declarations, nearly all a filled gap
or an existing test changed in form, listed the diff back to the person; none was undeclared. Whether
a filled gap inside the packages **Where the code goes** names needs a declaration at all is decided
with the fix case.

### 93. A logs criterion for a component that calls an external system
In the second fix run, the standing logs criterion (`delivery-spec` rule 9) asked for no error line in
ten minutes from a collector that calls a third-party site. The site returned an empty body once; the
code handled it as designed and resumed on the next cycle; the criterion failed, and the person had to
accept it as written. The check before code could not see this: on today's code the criterion already
failed on the defect's own errors, which hid the site's. Proposal: rule 9's exception for a provoked
failure also covers an error an external system causes and the code handles as designed — the criterion
names it, so acceptance does not depend on someone else's site. Since D191 a fix takes no logs
criterion; the proposal stands for a feature's.

### 94. What goes into a fix's regression commit
In the same run, the regression commit held the tests and a refactor of two entry points into public
builders, the seam the tests needed. `/pyhouse-delivery:implement` regression mode says the test is
committed alone; the seam was declared as a filled gap, but the tests' base now carries production
code, and the diff from it no longer shows that code. Proposal: a seam a regression test needs is its
own commit before the test, or the rule says a seam may go with the test and is declared. Decide on
more fix runs.

### 95. A test that passes before the code because the skeleton laid its contract
`/pyhouse-delivery:implement` step 4 sends every new test that passes before the code back to its
writer once. In a feature run the skeleton wrote the migration and tables in full, because the
project's metadata-match test needs both together, and 71 of the 231 new tests passed on it — tests of
the schema, which a skeleton of a stored contract really does satisfy. The session left them in place
with the tester's reasons, against the step. Proposal: a test passing on a contract the skeleton
laid in full — a schema, a migration — is kept and listed, not sent back; the step still sends back
one passing on behaviour.


### 96. A fix that is a feature, caught before it is ready
`delivery-spec` rule 2 already says a change that adds behaviour, a surface or a schema is a feature,
however small. In an adopted repository a spec checked ready in the fix form still named a metric, a
log event and a field carried across runs under **Contracts**, plus ten test criteria, of which its
**Regression test** named one. `/pyhouse-delivery:implement` routes a fix through the regression step
with no tester, so the other nine tests would be written with the code, after the tests' base, and the
prover's rule — a test not in the base was not written before the code — fails all nine on the form of
the spec alone. Three of them pass on today's code by nature (a timeout that still spends an attempt, a
record without the new field still decoded, a replay of today's history), so listing them all as the
regression test would not work either. Proposal: rule 12's readiness check refuses a fix that has
**Contracts**, or more criteria than its regression test answers, and sends it back as a feature; and
`/pyhouse-delivery:implement` step 1 stops on the same sign rather than starting the regression step.
