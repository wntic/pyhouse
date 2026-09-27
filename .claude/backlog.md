# Backlog — catalogue edits not yet made

Each entry is **Proposed** (awaiting the maintainer's decision) or **Agreed** (decided, not yet done).
Remove an entry in the change that does it; record the decision in `DECISIONS.md` as usual.

## Proposed

Nothing proposed.

## Agreed

### 1. Logging becomes its own universal skill
`python-style` holds three subjects — typing, logging, comments — and its `description` is ~900
characters because of it, the "two skills wearing one name" pitfall `meta-skill-author` names. Logging
is the largest and most self-contained: the event shape, levels, who logs an error, configuring once at
the entry point, a library that configures nothing, what never reaches a log line, stdout that is a
program's product rather than a log. Move the `## Logging` section and `LOGGING.md` into a new
`python-logging`; `python-style` keeps a one-line pointer. Touches: `python-style`, the ownership table
in `meta-skill-author`, every pointer to `python-style` for logging (grep "python-style" near
"log"), both indexes, counts (universal 12 → 13 + meta), `architecture-choice`'s list of universal
skills, `DECISIONS.md`. A minor for `pyhouse-universal`.

### 4. Re-run the short-prompt scenario on the current skills
The maintainer's GLM run with a short `dns_scanner` prompt was made on the skills before the generality
rework. Run it again on current `main` and review the output the same way (layout, module size, which
skills loaded, defects → rules).

### 5. Small leftovers from the generality rework
- `hex-restapi-endpoint/TRANSFER.md` names `ImportFoosHandler`/`ExportFoosHandler`, which no
  `hex-application` template shows — acceptable as "written like any other handler", revisit if a
  review flags it.
