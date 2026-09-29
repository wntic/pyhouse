# Backlog — catalogue edits not yet made

Each entry is **Proposed** (awaiting the maintainer's decision) or **Agreed** (decided, not yet done).
Remove an entry in the change that does it; record the decision in `DECISIONS.md` as usual.

## Proposed

### 47. Smaller leftovers found by round 2's reviews
- `hex-conventions` (~:77) cites `hex-restapi-app` rule 6 (a middleware is transport-level) for where
  the catch-all lives; the rule may not say that.
- `hex-wiring`'s "Declaration order" list is numbered 1–5 inside `## Rules`, beside the numbered rules
  1–7; a citation reader can confuse them.
- Nothing tests that an entrypoint runs the settings check (`hex-wiring` rule 2), and a long-lived
  client that validates in its constructor still fails on first use rather than at start.
- `resolve_settings` reads dishka's `Provider.factories` and `provides.type_hint`, which are not
  documented API (verified on 1.10.1 only).
- The outbox's retrying deliverer, which `hex-application` *After the store write* relies on, is
  described nowhere beyond a mention in `hex-persistence/UNIT_OF_WORK.md`.
- `myapp.postgres.create_engine` shares its name with SQLAlchemy's synchronous `create_engine`.
- `python-versioning`'s `version.py` example has no `__all__`.

## Agreed

Items 45 and 46 were decided on 2026-09-30, item 4 on 2026-09-28. Every other agreed item has
landed (D130–D144).

### 45. A settings module is named for its class, everywhere
Decided by the maintainer on 2026-09-30. `python-packaging`'s rule — a module holding one class is named
for it in snake_case — holds without a carve-out: `QuxSettings` lives in `qux_settings.py`,
`RedisSettings` in `redis_settings.py`, never in a bare `settings.py`. `flat-layered` rule 7,
`hex-conventions`' settings row and every template, tree line and import that spells `settings.py`
change to match.

### 46. Rename the abbreviations `naming` bans in the templates
Decided by the maintainer on 2026-09-30. `cmd`, `repo`, `sf`, `fid`, `creds`, `trans` and any other
invented abbreviation in a template or a rule's text is spelled out as `naming` requires (`command`,
`repository`, `session_factory`, …). `hex-restapi-auth`'s `get_current_user` stays: it is the
framework's documented idiom.

### 4. Re-run the short-prompt scenario on the current skills
Last, once everything above has landed. The maintainer runs the short `dns_scanner` prompt on GLM
against the pushed `main`, as before the generality rework; the output is then reviewed the same way
(layout, module size, which skills loaded, defects → rules).
