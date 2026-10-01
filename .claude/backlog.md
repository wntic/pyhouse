# Backlog — catalogue edits not yet made

Each entry is **Proposed** (awaiting the maintainer's decision) or **Agreed** (decided, not yet done).
Remove an entry in the change that does it; record the decision in `DECISIONS.md` as usual.

## Proposed

### 51. Flat tests may not call the engine factory; hex tests do
`flat-test-integration-setup` rule 5 says nothing under `tests/` calls the production engine factory, so
its session `engine` fixture builds its own with `create_async_engine` — without the factory's
`pool_pre_ping`, so the suite tests a different engine from production's, and with a second place the
connection string is unwrapped. `hex-test-integration-setup`'s `_engine` fixture calls `create_engine`.
Three reviewers of D150 proposed the flat fixture call the factory; that reverses flat rule 5, so it was
left. Decide which one both families follow, and what `test-principles`' reliability rule and its
exception actually permit.

## Agreed

Item 4 remains, agreed on 2026-09-28. Every other agreed item has landed (D130–D150).

### 4. Re-run the short-prompt scenario on the current skills
Last, once everything above has landed. The maintainer runs the short `dns_scanner` prompt on GLM
against the pushed `main`, as before the generality rework; the output is then reviewed the same way
(layout, module size, which skills loaded, defects → rules).
