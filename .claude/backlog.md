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

### 6. `python-logging` — where a CLI's diagnostics go, and one rendering per sink
Branch `feature/logging-cli`, together with the headings bullet of item 10. A minor for
`pyhouse-universal`.
- Rule 3 → "…and that one configuration picks the rendering for the sink — machine-readable wherever a
  collector reads it, human-readable only on an interactive terminal — and routes the standard
  library's loggers (a framework's, a driver's) through it."
- Rule 1 gains: "A program whose stdout is its product writes every log event to stderr."
- Rule 1 and its `print()` hard stop name one condition: "an entry-point debug path behind a flag".
- New hard stop: "A library's or framework's records bypass the configured logger — their own handler,
  their own format → stop, route them through the one configuration (rule 3)."

### 7. `flat-test-integration-setup` — point instead of restating
Branch `fix/flat-test-setup-pointers`. A patch for `pyhouse-flat`; about −14 lines, +3.
- Rule 2 opens "**Where the suite can reach a database it did not start**, the safety guard lives
  inside…", as rule 3 is already conditional.
- Delete the hard stop "the guard is being relaxed because someone wants to run against a local
  database"; the first guard stop ends "…a developer's database; the suite TRUNCATEs every table it can
  see."
- Rule 4 → "One pool per run, one transaction per test — the scopes `test-principles` *Fixture scope
  rules* set. A session-scoped connection would serialize the suite onto one connection."
- The `filterwarnings` hard stop → "…→ stop, add the exception as `test-principles` reliability rule 9
  states it."
- The prose after the pytest configuration becomes "Both loop-scope lines are load-bearing (rule 8)."; the
  `truncate_all` paragraph keeps only the lock explanation rule 7 lacks.
- `## Other bindings` gains: "**A second, non-relational store** gets its own session-scoped container
  and client beside these, and isolates by a per-test namespace deleted at teardown — there is no
  transaction to roll back."

### 8. `test-principles` — expect the narrowest class on a raise path
Branch `feature/raise-assert`. A minor for `pyhouse-universal`.
- *Assert strength* gains recipe 6: "**On a raise path, expect the narrowest class the contract raises**,
  never `Exception` or a base shared with unrelated failures, and assert the one field that
  distinguishes it (`code`, a key in `context`). A bare `Exception` passes a body that fails for any
  reason at all."
- `flat-test-persistence`'s hard stop keeps only its family half ("…or the driver's own exception class
  → stop, expect the translated catalogue class").
- `hex-test-capability-adapter` rule 7 stays — the probe's SDK class is the legitimate exception — and
  cites recipe 6.

### 9. `flat-entrypoint` — mark the optional lines; a webhook redelivery changes nothing
Branch `fix/flat-entrypoint-optional`. A minor for `pyhouse-flat` (rule 9 gains an obligation).
- Shape 1 and the `HTTP.md` process template mark `# only with a store` on the settings / engine /
  dispose lines and `# only with an upstream` on the HTTP-client block; the prose sentence saying so
  goes.
- Rule 9's clause → "…a redelivery of one already recorded is answered as a success **and changes
  nothing**", agreeing with the queue trigger's idempotency rule.
- The `HTTP.md` run function takes the time from the event (`observed_at=payload.sent_at`, with the
  field on `FooPayload`), not `datetime.now(UTC)`, so a redelivery rewrites identical values.
  `record_batch([foo])` stays; no single-row method is added to the template.

### 10. Smaller leftovers
Branch `fix/leftovers`, except the headings bullet, which goes with item 6. Patches.
- `exception-catalog`'s `context` example drops `"constraint": "uq_foos_name"` for a key that names
  the input (`{"foo_name": …}`), as `python-logging` now shows.
- `python-logging` becomes Reference-shaped: its structlog snippet moves into `## The event` as that
  section's example, the `## Template` heading goes, and its topical `##` headings then fall under
  `meta-skill-author` rule 1's Reference allowance. The snippet and its distributed-package comment stay
  where an agent copies them.
- `tools/check_template_imports.py` drops `mycommon` and `store_sdk` from `PLACEHOLDERS` after a grep
  confirms no template imports either; rerun the checker.
- The flat/hex test-engine pre-ping difference is closed with no change: neither family states a rule
  about it.
