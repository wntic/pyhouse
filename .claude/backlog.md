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

### 37. `CONVENTIONS.md` promises a banned-name blocklist that does not exist
`meta-skill-author/CONVENTIONS.md` (~:218-220) says the repository's lint and review check carries a
literal blocklist of banned names; none exists in `.claude/`, `tools/` or `/commit`, and `git log -S`
finds only the commit that added the sentence. Either write the check (a script beside
`check_template_imports.py`) or drop the promise.

### 38. `python-settings` rule 9 does not say which client unwraps a secret
Rule 9 says a secret is unwrapped "where the client that sends it is constructed". Where a composition
root builds a transport client and injects it into an adapter (`hex-capability-adapter`), that reads as
the shared client, not the adapter's constructor, which `hex-capability-adapter` rule 7 now requires.

### 39. The commit-msg hook's own header gives the install recipe that silences other hooks
`plugins/pyhouse-git/git-hooks/commit-msg` (~:5-7) gives the shared-install recipe (`core.hooksPath`)
with no warning; `/install-commit-hook` step 1 now warns that it silences hooks a manager such as
pre-commit wrote into the clone. The header should agree.

### 40. `hex-application` cannot carry "clear this field" through a partial update
`hex-restapi-schema` and `hex-restapi-endpoint` now say a field a client may clear passes its presence
beside its value, but `UpdateFooCommand` (None = unchanged) and `hex-test-application-handler`'s update
test have no way to carry it. Decide the command's shape for a clearable field.

### 41. Smaller leftovers found by the reviews
- `flat-test-integration-setup`'s `truncate_all` wipes only the tables whose modules the session
  imported (`metadata.sorted_tables`).
- `hex-domain-service`'s template has `is_name_taken` beside `assert_name_available`, and only the
  second is tested.
- `Foo.note` rides through every hex template; it earns its place in the partial-update and round-trip
  tests, but no service in the test list needs it in production — decide whether the worked entity keeps
  a second field.
- Nothing obliges a test of what a read-only repository returns (the nightly job's).
- Review fix-ups land as separate "apply the review" commits, while the shipped `git-branching` rule 4
  says a fix to unlanded work is folded; this repository's practice and its own skill disagree.
- `hex-test-application-handler/FAKES.md`'s `_RaiseAfterUploadRepo` raises `RuntimeError`, while
  `test-principles` rung 4 says an injected failure raises the catalogue exception; the second
  compensation test tells the two failures apart by type, so the fix needs a small redesign.
- `hex-wiring` (~:63-65) restates the dependency-injection override trap `hex-test-integration-setup`
  owns.
- `mypy` over a workspace (`packages/ services/ tests/` with `explicit_package_bases`) sees two members'
  `tests.unit.fakes` as one module name; untested.
- `test-principles`' wiring-smoke row names only the hex binding; a flat service has no named smoke.
- `hex-test-application-handler`'s compensating checklist is worded for storage plus a database
  (`upload`, `blob`, `db`).
- `hex-test-integration-setup/CONFTEST.md`'s `api/conftest.py` and per-resource sections now only route
  away, for files the skill no longer writes.
- The absent-row tests for `update` and `delete` are required in prose (`hex-test-repository-contract`)
  but are not template lines, so the template alone passes a repository that drops its zero-rowcount
  branch.

## Agreed

Items 42–44 were decided on 2026-09-29, item 4 on 2026-09-28; every other item agreed on 2026-09-28 has
landed (D130–D137).

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

### 44. Fold review fixes into the commits they correct before a branch lands
Decided by the maintainer on 2026-09-29 (option b of the review's three). A fix to unlanded work is
committed with `git commit --fixup=<sha>` and folded non-interactively before the merge, as
`git-branching` rule 4 already says, so the history and the changelog `/release` builds carry no fix for
a defect no release ever had. Record it in `CLAUDE.md`'s *Branching*, in `.claude/commands/commit.md`
and in `/kickoff`'s *How work is done here*. The existing history is left as it is.

### 4. Re-run the short-prompt scenario on the current skills
Last, once everything above has landed. The maintainer runs the short `dns_scanner` prompt on GLM
against the pushed `main`, as before the generality rework; the output is then reviewed the same way
(layout, module size, which skills loaded, defects → rules).
