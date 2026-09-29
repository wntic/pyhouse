# Backlog — catalogue edits not yet made

Each entry is **Proposed** (awaiting the maintainer's decision) or **Agreed** (decided, not yet done).
Remove an entry in the change that does it; record the decision in `DECISIONS.md` as usual.

## Proposed

### 45. `python-packaging`'s module-per-class rule and the families' `settings.py`
`python-packaging` (~:52-53) says a module holding one class is named for it in snake_case, while
`flat-layered` rule 7 puts `QuxSettings` in `qux/settings.py` and `hex-conventions` uses `settings.py`
the same way. A reviewer applying the universal rule flags both families' layouts. Either the rule
carves out a settings module inside a component package, or the families change.

### 46. Abbreviations `naming` bans survive in the hex templates
`cmd` and `repo` are written into `hex-application`'s handler-signature rule, and `sf`, `fid`, `creds`
and `trans` appear in hex templates; `hex-restapi-auth`'s `get_current_user` is an unqualified `get_`
(`naming` rule 5), though it is FastAPI's documented idiom. Renaming touches hex rule text, so it was
left out of item 42. Decide which to rename and whether a framework idiom earns an exception.

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

Item 4 remains, agreed on 2026-09-28. Every other agreed item has landed (D130–D144).

### 4. Re-run the short-prompt scenario on the current skills
Last, once everything above has landed. The maintainer runs the short `dns_scanner` prompt on GLM
against the pushed `main`, as before the generality rework; the output is then reviewed the same way
(layout, module size, which skills loaded, defects → rules).
