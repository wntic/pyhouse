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

### 36. Settings a component needs fail before the app reports ready
Found by item 24's verification (lens 3). Under dishka's lazily built composition root, `JwtSettings()`
is first built on the first authenticated request: with the verifier's environment missing, a public
health route answers 200 while every protected route answers 500, so a readiness check passes on a
broken service (`python-settings` rule 4 asks for settings built "at startup, before any work"). The
obligation would be `hex-wiring`'s, and it collides with `hex-restapi-app` rules 4 (lifespan does
teardown only) and 5 (`main.py` resolves nothing), which the fix has to reconcile.

## Agreed

Decided by the maintainer on 2026-09-28, every open item at once. Order of work: 34, 19, 11 and 31
first, in parallel, since they touch disjoint files; then 14 (after 11 and 31, which touch
`flat-persistence`) and 24 (after 34, which touches `hex-restapi-app`); then 26; 4 last. Review
findings are applied where a test service backs them; a contested one — lenses disagreeing, a whole
file or skill deleted, a rule reversed — goes to the maintainer.

### 26. Audit the test skills the same way — batch 2 remains
Batch 1 (the four `flat-test-*` skills) is done (D136); `hex-test-restapi-auth` and
`hex-test-restapi-endpoint` were audited with item 24 (D135). Remaining: `hex-test-app-invariants`,
`hex-test-application-handler` (with `FAKES.md`), `hex-test-capability-adapter`, `hex-test-domain`,
`hex-test-integration-setup` (whose obligations 2–5 read as universal) and
`hex-test-repository-contract`, reviewed with `/review-skills` and the findings applied. Known echoes:
`hex-test-repository-contract` rule 18 no longer names the classes it promises; `hex-test-application-
handler` rule 6's `FooConflictError` example assumes a natural key; the `note` field carried through
`Foo` across hex; `flat-test-integration-setup` rule 9 still restates `test-principles` reliability rule
2 beside its savepoint clause; the credential-refresh obligation sits in `flat-test-service-client`'s
prose, not its rules; nothing obliges a test of what a read-only repository returns.

### 4. Re-run the short-prompt scenario on the current skills
Last, once everything above has landed. The maintainer runs the short `dns_scanner` prompt on GLM
against the pushed `main`, as before the generality rework; the output is then reviewed the same way
(layout, module size, which skills loaded, defects → rules).
