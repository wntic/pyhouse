# Backlog — catalogue edits not yet made

Each entry is **Proposed** (awaiting the maintainer's decision) or **Agreed** (decided, not yet done).
Remove an entry in the change that does it; record the decision in `DECISIONS.md` as usual.

## Proposed

Nothing open.

## Agreed

Item 46 was decided on 2026-09-30, item 4 on 2026-09-28. Every other agreed item has landed
(D130–D146).

### 46. Rename the abbreviations `naming` bans in the templates
Decided by the maintainer on 2026-09-30. `cmd`, `repo`, `sf`, `fid`, `creds`, `trans` and any other
invented abbreviation in a template or a rule's text is spelled out as `naming` requires (`command`,
`repository`, `session_factory`, …). `hex-restapi-auth`'s `get_current_user` stays: it is the
framework's documented idiom.

### 4. Re-run the short-prompt scenario on the current skills
Last, once everything above has landed. The maintainer runs the short `dns_scanner` prompt on GLM
against the pushed `main`, as before the generality rework; the output is then reviewed the same way
(layout, module size, which skills loaded, defects → rules).
