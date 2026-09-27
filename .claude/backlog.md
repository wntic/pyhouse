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

### 2. No settings factory functions in the templates
`get_foo_settings()` only returns `FooSettings()`; it adds nothing. The obligation behind it is
`python-packaging` rule 8 — nothing is built at import time — and that is met by calling the class in
the composition root. Proposal: templates call the class where the process is composed
(`settings = FooSettings()` inside `main()` / the provider method); a module-level instance stays
forbidden; a factory function is written only when it adds something (a cache, assembly from several
sources). Touches: `python-settings` (template, rule 13, hard stops), `flat-layered` (rule 7 wording,
`FooApiSettings`), `flat-persistence` (`get_postgres_settings`, rule 14, `SETUP.md`), `flat-entrypoint`
and `HTTP.md` process templates, `flat-project-setup` migration env, `hex-wiring` (already says a
container's provider replaces the factory), test templates that call the factories.

### 3. Replace the generic `bulk_upsert` helper with the repository's own statement
`bulk_upsert(conn, table, rows: Iterable[Mapping[str, Any]], conflict_columns, update_columns)` is a
table-agnostic helper carried over from the application the first skills were written from. The
obligations it binds — chunk below the driver's bind-parameter cap with a named constant (rule 10),
resolve a conflict explicitly with a declared update set (rule 12) — are the house pattern; the
generic, mapping-typed helper is not: it needs its own excuse for breaking `python-style`'s
declared-record rule ("the row builder returns a mapping, deliberately"), and six of the
persistence tests exercise the helper rather than the repository. Proposal: `FooRepository.record_batch`
builds its own chunked `insert … on conflict` statement; the chunk constant stays; the helper, its
`engine.py` export and the helper tests go; the table tests target the repository. Rules 10 and 12
unchanged. Touches: `flat-persistence` (`SETUP.md`, `REPOSITORY.md`), `flat-test-persistence`.

### 4. Re-run the short-prompt scenario on the current skills
The maintainer's GLM run with a short `dns_scanner` prompt was made on the skills before the generality
rework. Run it again on current `main` and review the output the same way (layout, module size, which
skills loaded, defects → rules).

### 5. Small leftovers from the generality rework
- `hex-restapi-endpoint/TRANSFER.md` names `ImportFoosHandler`/`ExportFoosHandler`, which no
  `hex-application` template shows — acceptable as "written like any other handler", revisit if a
  review flags it.
