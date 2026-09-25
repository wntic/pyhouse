# python-style — logging

Topic file of `python-style`. The mechanism-free obligations are rules 10, 11, 12 and 13 in `SKILL.md`,
together with the four bullets and the allocation rule under its `## Logging` heading; what follows is
the **structlog** binding that satisfies them, and the alternative that satisfies them differently.

## Binding — `structlog`

```python
import structlog

log = structlog.get_logger()

# inline fields
log.info("foo_created", foo_id=str(foo.id), caller_id=str(cmd.caller_id))

# bound context for a sequence of calls
log_ctx = log.bind(import_id=str(import_id))
log_ctx.info("import_started", row_count=len(rows))
log_ctx.info("import_completed", imported=imported, skipped=skipped)
```

## Event names and fields are a contract

The event name is what a query matches on: `foo_created`, `bar_archived`, `foos_imported`,
`ingest_run_failed`. These are stable strings — **do not rename once shipped**, because dashboards and
alerts key on them. `naming` lists them among the frozen external contracts for that reason.

Identifiers and counts are fields: the primary id as `<subject>_id`, the actor as `caller_id` where one
exists, counts (`imported`, `skipped`, `errors`) for a bulk operation.

```python
# yes
log.info("foo_created", foo_id=str(foo.id))

# no — nothing in this line can be filtered by foo, grouped, or counted
log.info(f"created foo {foo.id}")
```

## Never log and re-raise the same event

`log.x(...)` immediately followed by `raise` in the same scope is two entries for one event, and there is
**no sanctioned exception** — a failed undo stopped under compensation, below, logs a different event from the one it
re-raises. A scope that re-raises is not the scope that will explain the failure: the
detail belongs in the exception it raises — the fields in `context`, the original error in `__cause__`
through `from exc` (`exception-catalog`) — where the scope that stops it will find both.

```python
# yes — translate, carry the detail forward, stay silent
try:
    await self._session.execute(stmt)
except IntegrityError as exc:
    raise ConflictError(
        "foo name already exists",
        {"field": "name", "constraint": "uq_foos_name"},
    ) from exc

# no — the layer that stops this will log it again, off the translated exception
except IntegrityError as exc:
    log.warning("foo_name_conflict", foo_name=foo.name)
    raise ConflictError("foo name already exists", {"field": "name"}) from exc
```

Level guide, for the scope that does log: `warning` for an expected rule violation surfacing at a
boundary — uniqueness, a foreign key; `error` for an unexpected failure — a network timeout, a
third-party 5xx, malformed data.

## A failed undo under compensation

Best-effort compensation (`exception-catalog`) is the one place a scope that re-raises also stops a
failure, and so the one place a scope that re-raises logs. The two are different events, which is why it does not break
the rule above: the **undo's** failure stops in this scope and is logged here, once; the **original**
failure is re-raised unlogged and is logged by whoever stops it.

- **The scope that runs the compensation logs it** — the one that caught the original failure and
  will re-raise it — in the `except` around the undo call, and nowhere else. The undo it called stays
  silent, like any scope that raises.
- **At `warning`, exactly one event**, named for the undo that failed (`foo_blob_undo_failed`), with the
  undo's identifying inputs as fields and the undo's error attached (`exc_info=` under `structlog`).
  Not `error`: the operation's failure is the error, and it is logged where it stops.
- It carries what a person needs to clean up by hand — the key, the id, the reservation — because the
  event is the only record that an effect outlived the operation that made it.

```python
except Exception:
    try:
        await self._blobs.delete(blob_key)
    except Exception as undo_exc:
        log.warning("foo_blob_undo_failed", blob_key=blob_key, exc_info=undo_exc)
    raise
```

## Who logs an error

**An error is logged once, by the scope that can add context and will not re-raise it.** That is the
whole rule, and it binds with no layers at all: a scope that re-raises stays silent — what it was about
to log rides in the exception instead, the fields in `context` and the cause through `from exc` — and
the scope that stops the exception is the only one that logs.

To apply it, trace the exception outward to the first scope that handles it rather than re-raising.
A project that funnels every failure into one handler makes that handler the scope; where nothing above
a failure is obliged to re-raise, the scope is usually the point of failure itself; where the exception
leaves the codebase entirely — a distributed package handing it to its caller — no scope inside
qualifies and nothing inside logs. Each family fixes that answer once; the two this catalogue covers:

**Hexagonal projects** propagate every error to a single central handler, so the scope that does not
re-raise is the entrypoint:

| Layer | May log |
|---|---|
| `domain/` | **Nothing.** Zero IO includes the log socket; raise an exception carrying `context` instead. |
| `infrastructure/` | **Nothing.** An adapter translates and re-raises, so it is never the layer that stops; the low-level detail goes into the translated exception's `context`, where the layer that does log will find it. |
| `application/` | **Successes only**, at `info`, after the operation completes. Never errors — they propagate. The one exception is a failed undo stopped under best-effort compensation, which the handler running the compensation logs at `warning` (above). |
| entrypoints | Errors, once, at the central handler, with request context attached. |

**A central handler takes the same guide**, plus one case only it sees: an exception that is not a
catalogue class → `error`, logged *before* the framework turns it into a 500, or it is never seen.

This skill owns the level rule; the **call** that implements it belongs to the entrypoint template with
a central handler — `error_handler.py` in `hex-restapi-app`, in the `pyhouse-hex` plugin. The rule
outlives any one framework; the call is framework-shaped.

**Flat-layered services** funnel nothing — nothing above a failure is obliged to re-raise — so the scope
is usually the point of failure itself: **log the failure there, with its context**. A scope that does
re-raise (a client translating an SDK error) stays silent; whoever stops the exception logs.

## Other bindings

The structured logger is the one library this skill binds; typing and comments bind none.

- **Stdlib `logging` plus a structured adapter** — `logging` configured once with a JSON formatter, the
  event name as the record's message and the fields passed through `extra=` or a `LoggerAdapter` (or the
  whole module kept behind a thin structured wrapper). What changes: how the logger is obtained and
  configured, and how fields reach the record. What does not: one event per occurrence, the
  `<subject>_<past_tense_verb>` name and its never-rename contract, identifiers and counts as fields
  rather than interpolated text, the never-log-and-re-raise rule, and the allocation table.
- **What that binding buys**, so it reads as a choice rather than a fallback: third-party libraries log
  through `logging`, so on this binding their records land in the same stream with no bridge to
  configure. What it costs is that nothing in the library enforces the field discipline — the obligations
  above have to be held by the author, where a keyword-field interface makes them the path of least
  resistance.
