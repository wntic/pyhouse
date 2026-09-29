# Backlog — catalogue edits not yet made

Each entry is **Proposed** (awaiting the maintainer's decision) or **Agreed** (decided, not yet done).
Remove an entry in the change that does it; record the decision in `DECISIONS.md` as usual.

## Proposed

Nothing open.

## Agreed

Items 42 and 4 remain: 42 decided by the maintainer on 2026-09-29, 4 on 2026-09-28. Every other agreed
item has landed (D130–D143).

### 42. Rename the identifiers carried over from the reference application
Decided by the maintainer on 2026-09-29. The skills still spell names taken from the application they
were first written from — `foo_api` (27 occurrences), `observed_at` (22), `run_once` (12), `RunResult`
(12), `fetch_foos` (11), `FooPayload` (11), `FooReference` (10), `record_batch` (8) and others. `Foo`
is a placeholder; the suffixes, method and field names are the sample's. Sweep the catalogue for
identifiers that come from the reference rather than from `naming`'s derivation, and replace each with a
neutral name derived by `naming` (a method named for what it does, a field for what it means). The
flat upsert template's ordering guard (a marked `where=` line, D131 kept it prose) is revisited after
the rename, on the renamed column.

### 4. Re-run the short-prompt scenario on the current skills
Last, once everything above has landed. The maintainer runs the short `dns_scanner` prompt on GLM
against the pushed `main`, as before the generality rework; the output is then reviewed the same way
(layout, module size, which skills loaded, defects → rules).
