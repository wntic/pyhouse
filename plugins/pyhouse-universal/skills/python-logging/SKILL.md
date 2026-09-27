---
name: python-logging
description: Use when writing a log call, naming a log event, deciding which scope logs a failure and at what level, or configuring logging in an entry point or a distributed package. Owns one structured event per occurrence with a stable `<subject>_<past_tense_verb>` name and identifiers as fields, the rule that an error is logged once by the scope that stops it and never by a scope that re-raises, the warning a failed undo under compensation earns, logging configured once at the entry point and never inside a distributed package, what never reaches a log line, and a program's result on stdout as output rather than a log event. Annotation forms and comments are `python-style`; the error classes and their `context` are `exception-catalog`.
---

# Python Logging

A log line exists to be **queried** — filtered, grouped, counted, alerted on. Prose cannot be queried, so
every occurrence worth recording produces **exactly one structured event**: a name plus fields, never a
sentence with values spliced into it. These rules hold whatever the architecture is.

Only one thing here varies from project to project, and it varies as a *consequence*, not as a separate
rule: an error is logged once, by the scope that can add context and will not re-raise it — and where a
project's errors propagate to decides which scope that is. Everything else is unconditional.

## When to use vs. neighbours

- Writing or changing any log call, naming an event, configuring logging → this skill.
- Annotation forms, record types, comments → `python-style`.
- The exception classes, what goes into their `context`, translation with `from exc`, best-effort
  compensation itself → `exception-catalog`.
- Which layer of a hexagonal service may log at all → `hex-architecture`, in the `pyhouse-hex` plugin;
  in a flat service, where the guard that stops a run's failure sits → `flat-layered` and
  `flat-entrypoint`, in `pyhouse-flat`.
- Whether a test may assert on what was logged → `test-principles`.
- An event name as a frozen external contract among the others → `naming`.

## Template — structlog

```python
import structlog

log = structlog.get_logger()

# inline fields
log.info("foo_created", foo_id=str(foo.id), tag_count=len(foo.tags))

# bound context for a sequence of calls
log_ctx = log.bind(import_id=str(import_id))
log_ctx.info("import_started", row_count=len(rows))
log_ctx.info("import_completed", imported=imported, skipped=skipped)
```

## Other bindings

- **Stdlib `logging` plus a structured adapter** — the binding for a distributed package (rule 4),
  which calls `logging.getLogger(__name__)` and stops there, and an alternative for an application,
  whose entry point configures `logging` once with a JSON formatter, the event name as the record's
  message and the fields passed through `extra=` or a `LoggerAdapter` (or the whole module kept behind a
  thin structured wrapper). What changes: how the logger is obtained and configured, and how fields
  reach the record. What does not: one event per occurrence, the `<subject>_<past_tense_verb>` name and
  its never-rename contract, identifiers and counts as fields rather than interpolated text, the
  never-log-and-re-raise rule, and the allocation rule.
- **What that binding buys**, so it reads as a choice rather than a fallback: third-party libraries log
  through `logging`, so on this binding their records land in the same stream with no bridge to
  configure. What it costs is that nothing in the library enforces the field discipline — the
  obligations below have to be held by the author, where a keyword-field interface makes them the path
  of least resistance.

## The event

Four obligations, whichever library provides them:

- **One logger, obtained at module level.** Not per call, not per instance, and not a second logging
  mechanism running alongside the first — two mechanisms split one event stream in half and neither half
  is complete. `print()` is not one of them, outside a deliberate entrypoint debug path. **What a
  program writes to stdout as its result is not a log event** — a CLI's report, a table, the JSON a
  caller pipes onward is the product, and `print()` or `sys.stdout` is the right way to emit it; this
  rule is about diagnostics, which never share that stream.
- **One event per occurrence.** The same occurrence logged twice is two incidents on the dashboard.
- **The event name is a stable contract** — snake_case, `<subject>_<past_tense_verb>`.
- **Identifiers and counts ride as fields**, never interpolated into the message.

The event name is what a query matches on: `foo_created`, `bar_archived`, `foos_imported`,
`run_failed`. These are stable strings — **do not rename once shipped**, because dashboards and
alerts key on them. `naming` lists them among the frozen external contracts for that reason.

Identifiers and counts are fields: the primary id as `<subject>_id`, the actor as `caller_id` where one
exists, counts (`imported`, `skipped`, `errors`) for a bulk operation.

```python
# yes
log.info("foo_created", foo_id=str(foo.id))

# no — nothing in this line can be filtered by foo, grouped, or counted
log.info(f"created foo {foo.id}")
```

## Configuring the logger

**The logger is configured once, by the process's entry point, before its first event** — the sink, the
format, the level, and the routing that brings records from libraries into the same stream. Nothing
below the entry point configures logging, and a process whose entry point configures nothing emits
whatever defaults the library happens to have. **A distributed package configures nothing at all**: it
logs through the stdlib's `logging.getLogger(__name__)`, the one interface every importer already routes,
adds no handler and sets no level, and leaves every one of those choices to the application that imports
it.

## Who logs an error

**An error is logged once, by the scope that can add context and will not re-raise it.** That is the
whole rule, and it binds with no layers at all: a scope that re-raises stays silent — what it was about
to log rides in the exception instead, the fields in `context` and the cause through `from exc`
(`exception-catalog`) — and the scope that stops the exception is the only one that logs.

To apply it, trace the exception outward to the first scope that handles it rather than re-raising.
A project that funnels every failure into one handler makes that handler the scope; a process that
contains each run's failure and carries on makes its guard the scope; where the exception
leaves the codebase entirely — a distributed package handing it to its caller — no scope inside
qualifies and nothing inside logs. Each architecture family fixes where that scope is, in its own
architecture skill — e.g. `hex-architecture`, in the `pyhouse-hex` plugin, or `flat-layered`, in
`pyhouse-flat`.

A branch unreachable through the normal write path — a constraint standing as defence in depth behind a
rule that already refuses — is **not** excused from logging: if it fired, the rule was bypassed, and that
is the most interesting line in the log. It is logged by whoever stops it, under the same allocation as
any other failure.

Level guide, for the scope that does log: `warning` for an expected rule violation surfacing at a
boundary — uniqueness, a foreign key; `error` for an unexpected failure — a network timeout, a
third-party 5xx, malformed data.

## Never log and re-raise the same event

`log.x(...)` immediately followed by `raise` in the same scope is two entries for one event, and there is
**no sanctioned exception** — a failed undo stopped under compensation, below, logs a different event
from the one it re-raises. A scope that re-raises is not the scope that will explain the failure: the
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

## A failed undo under compensation

Best-effort compensation (`exception-catalog`) is the one place a scope that re-raises also stops a
failure, and so the one place a scope that re-raises logs. The two are different events, which is why it
does not break the rule above: the **undo's** failure stops in this scope and is logged here, once; the
**original** failure is re-raised unlogged and is logged by whoever stops it.

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

## What never reaches a log line

- A full request or response body → log identifiers and counts only; bodies may carry personal data.
- A password, bearer token, API key or connection string → log a length or a hash, never the value.
- A `UUID` object rather than `str(uuid_value)` → some sinks render it poorly.

The first two reach an exception's `context` as well, because the scope that logs renders `context`
verbatim into the log line. `exception-catalog` owns that statement of the rule.

## Rules

1. **One logger, obtained at module level, and one structured event per occurrence.** No `print()` for
   diagnostics outside a deliberate entrypoint debug path, and no second logging mechanism beside the
   configured one — two mechanisms split the event stream and neither half is complete. Output a program
   writes to stdout as its result is not a log event, and this rule does not reach it.
2. **Give every event a stable snake_case `<subject>_<past_tense_verb>` name, and carry its identifiers
   and counts as fields rather than interpolating them into the message.** A value inside a sentence
   cannot be filtered, grouped or counted, and a renamed event silently breaks every dashboard keyed on
   the old string.
3. **Configure the logger once, in the process's entry point, before its first event.** Nothing below
   the entry point configures logging, and that one configuration renders every event in one
   machine-readable format and routes the standard library's loggers (the server's, the drivers')
   through it.
4. **A distributed package logs through the stdlib `logging.getLogger(__name__)` and configures
   nothing** — no handler, no level, no format; the application importing it owns all three.
5. **Log an error once, in the scope that can add context and will not re-raise it** — traced outward
   from the raise to the first scope that handles the exception rather than re-raising it; a project
   that funnels failures into one handler makes that handler the scope. A scope that re-raises does
   not log; the detail it would have logged goes into the exception's `context`. The one failure a
   re-raising scope stops — an undo's, under `exception-catalog`'s best-effort compensation — ends
   there, so that scope logs it: one `warning` event naming the failed undo, before re-raising the
   original.
6. Check logged fields against **What never reaches a log line** before emitting them, and apply the
   same two bans to anything placed in an exception's `context`.

## Hard stops

- `log.x(...); raise` in the same scope → stop, that is two entries for one event; put the detail in the
  exception's `context` and let the layer that stops it log. A failed undo stopped and logged before the
  original is re-raised is two events, not this case.
- An undo's failure stopped under best-effort compensation with no log line, or logged at `error`, or
  logged by the undo itself → stop, the compensating scope logs one `warning` naming the failed undo; it
  is the only record that an effect was left behind.
- A log call emitting an interpolated sentence — no event name, no fields (`log.info(f"created foo
  {foo.id}")`) → stop, nothing in that line can be filtered, grouped or alerted on; emit an event name
  plus the identifiers as fields. This fires on every binding, the stdlib one included.
- `print()` used for diagnostics outside an entrypoint debug path behind a flag → stop, use the
  structured logger. A program's result written to stdout is not a diagnostic.
- Logging configured — a handler added, a level or format set — anywhere but the process's entry point,
  or inside a distributed package at all → stop, the entry point configures once and a package's
  importer owns every one of those choices.
- A second logging mechanism introduced beside the one already configured → stop, one logger everywhere;
  two split the event stream and neither half is complete.
- An event name that is not snake_case past tense (`FooCreated`, `create-foo`) → stop, rename it to
  `foo_created`. Once shipped, never rename — dashboards depend on the string.
- Logging a full body, a secret, or a bare `UUID` object → stop.
- A scope that re-raises the failure logs it as well → stop, it is not the scope that explains it; the
  detail goes into the translated exception's `context` and whoever stops the exception logs.
