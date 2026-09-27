# Backlog — catalogue edits not yet made

Each entry is **Proposed** (awaiting the maintainer's decision) or **Agreed** (decided, not yet done).
Remove an entry in the change that does it; record the decision in `DECISIONS.md` as usual.

## Proposed

Found by the four-lens reviews of items 1, 2, 3 and 5, outside what those items changed.

### 6. `python-logging` rule 3 gives a CLI tool JSON on its terminal
"Renders every event in one machine-readable format" holds for a service a collector reads, not for a
CLI tool run by a person, and "(the server's, the drivers')" assumes a server. Proposal: "…in one
format, machine-readable wherever a collector reads it, and routes the standard library's loggers (a
framework's, a driver's) through it." Also: rule 1 says "a deliberate entrypoint debug path" where its
hard stop says "behind a flag" — make them one condition; no hard stop covers stdlib loggers left
unrouted.

### 7. `flat-test-integration-setup` restates and over-states
- Rule 2 (the safety guard) is unconditional, but the guard exists only for a database the suite did
  not start; say so, as rule 3 already does.
- The hard stop near the end repeating "guard relaxed → stop" is a duplicate; fold it into the first.
- Rule 4 restates `test-principles` *Fixture scope rules*; the `filterwarnings` hard stop restates
  `test-principles` reliability rule 9; the prose after the pytest config restates rule 8, and the
  `truncate_all` prose restates rule 7. Point instead.
- The crawler writing to two stores gets no word on fixtures for its second, non-relational store —
  at most one sentence.

### 8. `pytest.raises` names the narrowest class — a universal rule stated in family skills
"Never a bare `Exception`" is stated in `flat-test-persistence` and `hex-test-capability-adapter` and
holds in any Python test; `test-principles` does not state it. Add one line to its assert-strength
rules and point the family skills at it.

### 9. Flat entrypoint templates carry a store the service may not have
- `flat-entrypoint` Shape 1 imports and builds a Postgres engine; a queue consumer that stores nothing
  copies it and relies on prose to remove it.
- `flat-entrypoint/HTTP.md` calls `record_batch([foo])` with the default `DO UPDATE`, so every
  redelivered webhook rewrites `observed_at`; a webhook's natural write is one row, often
  `DO NOTHING`. Now that `flat-persistence` says the batch is optional, the webhook template can
  show the single-row write.

### 10. Smaller leftovers from this round
- `exception-catalog`'s good `context` example still carries `"constraint": "uq_foos_name"`, the
  invented relational key removed from `python-logging`.
- `python-logging` carries a template and still puts six topical `##` sections between
  `## Other bindings` and `## Rules`, which `meta-skill-author` rule 1 allows only in Reference bodies.
- `tools/check_template_imports.py` still lists `mycommon`, deleted by D29, in `PLACEHOLDERS`.
- Flat's test engine takes the driver default (no pre-ping); hex's reuses the production builder
  (pre-ping on). No test-only setting remains, but the two are not built the same way.

## Agreed

### 4. Re-run the short-prompt scenario on the current skills
The maintainer's GLM run with a short `dns_scanner` prompt was made on the skills before the generality
rework. Run it again on current `main` and review the output the same way (layout, module size, which
skills loaded, defects → rules).

### 5. Small leftovers from the generality rework
- `hex-restapi-endpoint/TRANSFER.md` names `ImportFoosHandler`/`ExportFoosHandler`, which no
  `hex-application` template shows — acceptable as "written like any other handler", revisit if a
  review flags it.
