# Backlog — catalogue edits not yet made

Each entry is **Proposed** (awaiting the maintainer's decision) or **Agreed** (decided, not yet done).
Remove an entry in the change that does it; record the decision in `DECISIONS.md` as usual.

## Proposed

Nothing proposed.

## Agreed


### 4. Re-run the short-prompt scenario on the current skills
The maintainer's GLM run with a short `dns_scanner` prompt was made on the skills before the generality
rework. Run it again on current `main` and review the output the same way (layout, module size, which
skills loaded, defects → rules).

### 5. Small leftovers from the generality rework
- `hex-restapi-endpoint/TRANSFER.md` names `ImportFoosHandler`/`ExportFoosHandler`, which no
  `hex-application` template shows — acceptable as "written like any other handler", revisit if a
  review flags it.
