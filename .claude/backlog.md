# Backlog — catalogue edits not yet made

Each entry is **Proposed** (awaiting the maintainer's decision) or **Agreed** (decided, not yet done).
Remove an entry in the change that does it; record the decision in `DECISIONS.md` as usual.

## Proposed

### 35. A side effect after the store write has no rule
Found by item 19's review (lens 3). `hex-application` Compensation rule 1 puts a notification after
`repo.create` with nothing after it, and command handler rule 5 forbids a `try/except`, so a partner
timeout answers 502 for a stored foo (the client's retry then conflicts), a queue redelivery conflicts
forever, or an agent spawns an unobserved task. Proposed rule, mechanism left open: a side effect after
the store write never reports a committed command as failed and is never dropped unrecorded — the
handler stops its failure and logs it once, after the success event, or hands it to something that
retries it.

## Agreed

Decided by the maintainer on 2026-09-28, every open item at once. Order of work: 34, 19, 11 and 31
first, in parallel, since they touch disjoint files; then 14 (after 11 and 31, which touch
`flat-persistence`) and 24 (after 34, which touches `hex-restapi-app`); then 26; 4 last. Review
findings are applied where a test service backs them; a contested one — lenses disagreeing, a whole
file or skill deleted, a rule reversed — goes to the maintainer.

### 24. Audit the four `hex-restapi-*` skills and their tests
Run `/review-skills` on `hex-restapi-app`, `hex-restapi-auth`, `hex-restapi-endpoint`,
`hex-restapi-schema`, `hex-test-restapi-auth` and `hex-test-restapi-endpoint`, generality first, and
apply the findings. `TRANSFER.md` is code taken from one application — an import/export CSV pair, a
10 MiB ceiling, a mixed multipart + JSON route; lens 1 decides whether it is reduced to rules or
deleted. Absorbs item 5: `TRANSFER.md`'s `ImportFoosHandler`/`ExportFoosHandler` go with it.

### 26. Audit the test skills the same way
After 14, 19 and 24 have landed, run `/review-skills` over every `hex-test-*` and `flat-test-*` skill,
in two batches, and apply the findings. Known echoes: the unit-of-work and session fakes (14), the
repository-contract and persistence tests against the new universal owner (14), the restapi tests (24),
the template comments (D123, D128). `hex-test-restapi-auth` and `hex-test-application-handler/FAKES.md`
are the densest in domain nouns.

### 4. Re-run the short-prompt scenario on the current skills
Last, once everything above has landed. The maintainer runs the short `dns_scanner` prompt on GLM
against the pushed `main`, as before the generality rework; the output is then reviewed the same way
(layout, module size, which skills loaded, defects → rules).
