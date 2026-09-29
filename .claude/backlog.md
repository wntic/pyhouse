# Backlog — catalogue edits not yet made

Each entry is **Proposed** (awaiting the maintainer's decision) or **Agreed** (decided, not yet done).
Remove an entry in the change that does it; record the decision in `DECISIONS.md` as usual.

## Proposed

Nothing open.

## Agreed

Items 35–44 were decided on 2026-09-29 (35–41 as the orchestrator recommended: 35 a rule for a side
effect after the store write; 36 settings checked before the app reports ready; 37 drop the promised
blocklist; 38 name the component that unwraps a secret; 39 align the hook header; 40 a clearable field
carries its presence; 41 all leftovers but the commit-folding one, which 44 settles, keeping `Foo.note`
as the partial update's second field and saying why), item 4 on 2026-09-28; every other item agreed on 2026-09-28 has
landed (D130–D137).

### 35. A side effect after the store write has no rule
Found by item 19's review (lens 3). `hex-application` Compensation rule 1 puts a notification after
`repo.create` with nothing after it, and command handler rule 5 forbids a `try/except`, so a partner
timeout answers 502 for a stored foo (the client's retry then conflicts), a queue redelivery conflicts
forever, or an agent spawns an unobserved task. Proposed rule, mechanism left open: a side effect after
the store write never reports a committed command as failed and is never dropped unrecorded — the
handler stops its failure and logs it once, after the success event, or hands it to something that
retries it.

### 40. `hex-application` cannot carry "clear this field" through a partial update
`hex-restapi-schema` and `hex-restapi-endpoint` now say a field a client may clear passes its presence
beside its value, but `UpdateFooCommand` (None = unchanged) and `hex-test-application-handler`'s update
test have no way to carry it. Decide the command's shape for a clearable field.

### 41. Smaller leftovers found by the reviews
- `flat-test-integration-setup`'s `truncate_all` wipes only the tables whose modules the session
  imported (`metadata.sorted_tables`).
- `Foo.note` rides through every hex template; it earns its place in the partial-update and round-trip
  tests, but no service in the test list needs it in production — decide whether the worked entity keeps
  a second field.
- Nothing obliges a test of what a read-only repository returns (the nightly job's).
- Review fix-ups land as separate "apply the review" commits, while the shipped `git-branching` rule 4
  says a fix to unlanded work is folded; this repository's practice and its own skill disagree.
- `hex-test-application-handler/FAKES.md`'s `_RaiseAfterUploadRepo` raises `RuntimeError`, while
  `test-principles` rung 4 says an injected failure raises the catalogue exception; the second
  compensation test tells the two failures apart by type, so the fix needs a small redesign.
- `hex-test-application-handler`'s compensating checklist is worded for storage plus a database
  (`upload`, `blob`, `db`).

### 42. Rename the identifiers carried over from the reference application
Decided by the maintainer on 2026-09-29. The skills still spell names taken from the application they
were first written from — `foo_api` (27 occurrences), `observed_at` (22), `run_once` (12), `RunResult`
(12), `fetch_foos` (11), `FooPayload` (11), `FooReference` (10), `record_batch` (8) and others. `Foo`
is a placeholder; the suffixes, method and field names are the sample's. Sweep the catalogue for
identifiers that come from the reference rather than from `naming`'s derivation, and replace each with a
neutral name derived by `naming` (a method named for what it does, a field for what it means). The
flat upsert template's ordering guard (a marked `where=` line, D131 kept it prose) is revisited after
the rename, on the renamed column.

### 43. Batch writes leave the templates
Decided by the maintainer on 2026-09-29. Writing in chunks came from the reference service, which
loaded large volumes; most services write a row at a time, and batching is derived from a service's own
needs. The flat repository template shows a single-row write; the chunking machinery (the bind-parameter
cap, the chunk constant, the in-batch collapse, the per-chunk loop) and the batch-only tests leave the
templates. What survives is one conditional obligation in `persistence` — where a write takes a batch,
it is one statement per chunk sized under the driver's limit, never a per-row loop — because the
parameter cap failing a batch on size alone is the one part an agent would not derive.

### 4. Re-run the short-prompt scenario on the current skills
Last, once everything above has landed. The maintainer runs the short `dns_scanner` prompt on GLM
against the pushed `main`, as before the generality rework; the output is then reviewed the same way
(layout, module size, which skills loaded, defects → rules).
