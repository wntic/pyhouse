# Backlog — catalogue edits not yet made

Each entry is **Proposed** (awaiting the maintainer's decision) or **Agreed** (decided, not yet done).
Remove an entry in the change that does it; record the decision in `DECISIONS.md` as usual.

## Proposed

Found by the reviews of items 6–10, outside what those items changed.

### 11. The webhook's redelivery obligation has no test, and ordering has no word
- `flat-entrypoint` rule 9 now says a redelivery "changes nothing", but no test template pins it for
  the HTTP run function; `flat-test-run-function` rule 3 covers it only in general. At most one test in
  the HTTP wrapper tests, if the reviewers of that skill agree most webhook services need it.
- `HTTP.md` says keeping the newer row under out-of-order delivery is the conflict clause's job, and
  `flat-persistence` shows no such clause. Decide whether that is one sentence in `REPOSITORY.md`
  (an update guarded by the stamp) or stays out as optional.

## Agreed

### 4. Re-run the short-prompt scenario on the current skills
The maintainer's GLM run with a short `dns_scanner` prompt was made on the skills before the generality
rework. Run it again on current `main` and review the output the same way (layout, module size, which
skills loaded, defects → rules).

### 5. Small leftovers from the generality rework
- `hex-restapi-endpoint/TRANSFER.md` names `ImportFoosHandler`/`ExportFoosHandler`, which no
  `hex-application` template shows — acceptable as "written like any other handler", revisit if a
  review flags it.
