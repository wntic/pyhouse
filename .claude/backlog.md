# Backlog — catalogue edits not yet made

Each entry is **Proposed** (awaiting the maintainer's decision) or **Agreed** (decided, not yet done).
Remove an entry in the change that does it; record the decision in `DECISIONS.md` as usual.

## Proposed

### 48. The flat store's settings class and the hex one are two words for one concept
The flat family calls its store's settings class `PostgresSettings` (`postgres/postgres_settings.py`),
the hex family `DbSettings` (`infrastructure/postgres/db_settings.py`). `naming` asks for one concept,
one word; since item 45 put each in a module named for it, the difference is visible in every tree.
Decide which name both families use.

### 49. The flat loop's prose names a settings object its template never builds
`flat-entrypoint` (~:179) says the loop starts "after `settings = MyappSettings()`", but the `_run`
template neither builds that object nor imports the class; only the HTTP template shows the import. An
agent copying the loop either invents the construction or drops the settings.

## Agreed

Item 4 remains, agreed on 2026-09-28. Every other agreed item has landed (D130–D147).

### 4. Re-run the short-prompt scenario on the current skills
Last, once everything above has landed. The maintainer runs the short `dns_scanner` prompt on GLM
against the pushed `main`, as before the generality rework; the output is then reviewed the same way
(layout, module size, which skills loaded, defects → rules).
