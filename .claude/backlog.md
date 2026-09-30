# Backlog — catalogue edits not yet made

Each entry is **Proposed** (awaiting the maintainer's decision) or **Agreed** (decided, not yet done).
Remove an entry in the change that does it; record the decision in `DECISIONS.md` as usual.

## Proposed

### 50. A platform that supplies one connection URL
D148 gave both `PostgresSettings` templates one field per credential and a derived `dsn`, and removed
flat's single secret `dsn` field with its scheme-normalizing validator. A deployment whose platform
injects one database URL now has no line telling it how to read it, and an agent may split the URL by
hand in a consumer (`python-settings` rule 10). Proposed: one `## Other bindings` bullet in
`flat-persistence` and `hex-persistence` — the class holds that one secret-typed field in place of the
five, a validator normalizes its scheme to the driver's (`python-settings` rule 12), and `dsn` unwraps it.

## Agreed

Item 4 remains, agreed on 2026-09-28. Every other agreed item has landed (D130–D148).

### 4. Re-run the short-prompt scenario on the current skills
Last, once everything above has landed. The maintainer runs the short `dns_scanner` prompt on GLM
against the pushed `main`, as before the generality rework; the output is then reviewed the same way
(layout, module size, which skills loaded, defects → rules).
