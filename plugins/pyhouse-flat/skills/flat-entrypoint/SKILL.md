---
name: flat-entrypoint
description: Use when choosing how a flat-layered service is triggered and writing the process that triggers it — one run per process started by a cron entry or a timer, a loop, a continuous stream or queue consumer, a thin HTTP wrapper, or durable execution — and deciding whether a workflow engine is earned at all; one run per process is the default, and an engine is earned only by durability across process death, retries that outlive the process, or orchestration long enough that the sequence itself must survive. Owns the framework-free run function every trigger wraps, the process definition that builds its dependencies once and passes them down, the retry declared where the work is invoked, the aggregate a run returns, the containment that keeps one failed run from killing a long-lived process, and the bounded redelivery and dead letter a contained unit goes to. It also carries the obligations an earned engine adds, inert under every other trigger. Testing any of it is `flat-test-run-function`.
when_to_use: Also when asked for a polling loop, a `__main__` entrypoint, a nightly or periodic job, a queue or websocket consumer process, a webhook, an internal CRUD or proxy endpoint on a service with no invariants, a durable workflow, a batch loop, a heartbeat, a schedule or a cron expression, an overlap or catch-up policy, or whether this service needs a workflow engine at all.
---

# Flat-Layered Entrypoint — loop vs schedule vs stream vs HTTP vs durable

Covers the **process-definition** and **framework-wrapper** roles of one `flat-layered` service, whatever
this service calls those packages. The shapes differ only in *what triggers a run*; the run itself always
calls the same run functions, so switching later is a wrapper change, not a rewrite.

The invariant that makes that true: **the run function is a plain async function taking its dependencies
as arguments, living in a module of its own, and importing no framework.** Everything in this skill is a
wrapper around one of those.

Every template below is one distribution: `myapp` is this service's own root package (`flat-layered`), and
nothing here assumes a sibling distribution or a repository above it.

## When to use vs. neighbours

- The architecture family is not settled yet — this may not be a flat-layered service at all →
  `architecture-choice` decides hexagonal versus flat first; everything here assumes flat.
- The service's own settings and logging modules, its client and payload packages → not this skill, use
  `flat-layered`, which owns the role kinds and the import contract between them.
- The tables, the write path and the repository class the run function calls → `flat-persistence`.
- Several distributions sharing one repository — the member split, the container profiles, the root task
  runner → `python-workspace`. One distribution on its own needs none of it.
- **Durable execution, once it is earned** → still this skill, in the `## Rules` subsection that applies
  once rule 1 has earned an engine. Nothing else in this file depends on it.
- The scheduling needs are met by a loop, a cron entry or a timer — the default → none of those
  obligations apply; do not add orchestration modules "for later".
- The named exceptions a wrapper translates → `exception-catalog`; the one place they are rendered is
  this skill's HTTP shape (`HTTP.md`).
- The service answers HTTP but has business invariants, or several entrypoints share its rules → not
  this family; `architecture-choice` decides, and the HTTP shell is `hex-restapi-app`, in the
  `pyhouse-hex` plugin.
- Testing any of it — the run function, the loop's containment, the wrapper, the orchestration above them
  → `flat-test-run-function`.

## The trigger process — four shapes

| The work is… | Shape | Lives in |
|---|---|---|
| Anything on a schedule, as the starting assumption — a poll, a periodic pass, a nightly job | **One run per process**, started by an external scheduler or repeated by a loop around it | the process definition |
| Scheduled work that must *also* survive a restart mid-run, retry across process death, or orchestrate steps over hours or days | **Durable execution** — a workflow engine | a framework-wrapper package plus its serving process |
| A never-ending stream — a log or change feed, a queue consumer, a websocket feed | **Standalone stream process**, watched by an external liveness check | a process definition of its own |
| A request someone else sends — a webhook, an internal CRUD or proxy endpoint, on a service with no invariants of its own | **HTTP trigger** — a thin web-framework wrapper | a framework-wrapper package plus its server process |

**The default for scheduled work is one run per process.** A process that does one run and exits,
started by a cron entry or a timer, or a loop that repeats it, is the whole of most scheduling
requirements, and it costs one module and no infrastructure. Start there.

**A workflow engine is earned, not assumed.** Three things earn it, and nothing else does:

- **Durability across process death** — a run that is half-finished when the pod is evicted must resume,
  not restart. A loop cannot offer this; its state is in the process.
- **Cross-restart retries with a real backoff and a history** — an operator needs to see that attempt 3
  of 5 failed at 04:12 and why, after the process that made it is gone.
- **Long-running orchestration** — several steps, with waits, timers or human input between them,
  where the sequence itself is the thing that must survive.

If one of them is true, a loop reinvents the engine badly: a `_state` table, a retry counter, a lease,
an at-most-once guard, hand-rolled and untested. Shapes 3 and 4 are outside that choice: a continuous
stream and a request are **not** scheduled work.

## The run function — shared by every shape (structlog)

`src/myapp/foo_sync.py` — a run function that fetches from an upstream and records what it fetched: no
framework import, every dependency a parameter, the module named for its work (`flat-layered`).

```python
from datetime import UTC, datetime

import structlog

from myapp.foo_api import FooClient
from myapp.postgres import FooRepository
from myapp.schemas import Foo, FooPayload, FooReference, RunResult

__all__ = ["run_once", "to_foo"]

logger = structlog.get_logger()


def to_foo(payload: FooPayload, observed_at: datetime) -> Foo:
    return Foo(reference=FooReference(payload.ref), name=payload.name, observed_at=observed_at)


async def run_once(client: FooClient, repository: FooRepository) -> RunResult:
    payloads = await client.fetch_foos()
    observed_at = datetime.now(UTC)
    await repository.record_batch([to_foo(payload, observed_at) for payload in payloads])

    logger.info("foo_sync_completed", recorded=len(payloads))
    return RunResult(recorded=len(payloads))
```

`to_foo` is the mapping as one pure step, so a test covers it without a datastore; a filter the run
needs belongs in the same pure step. The body writes what one call returns; a source whose size the
service does not control is read and written in bounded batches instead (rule 10).

**The run function opens no transaction.** The repository class owns its own (`flat-persistence` rule
3); a run function that opens a connection has moved data access out of the one package allowed it.

It returns an **aggregate**, not the rows (rule 5): the rows are in the datastore, and a trigger that
serializes the return value into a durable history makes this load-bearing rather than merely tidy.

## Shape 1 — one run per process, on asyncio (the default)

`src/myapp/__main__.py` — the process definition of a service with one process:

```python
import asyncio

import httpx

from myapp.foo_api import FooApiSettings, FooClient
from myapp.foo_sync import run_once
from myapp.logging import configure_logging
from myapp.postgres import FooRepository, PostgresSettings, get_engine


async def _run() -> None:
    api = FooApiSettings()
    engine = get_engine(PostgresSettings().dsn.get_secret_value())
    try:
        async with httpx.AsyncClient(base_url=api.url, timeout=api.timeout_seconds) as http:
            await run_once(FooClient(http), FooRepository(engine))
    finally:
        await engine.dispose()


def main() -> None:
    configure_logging()
    asyncio.run(_run())


if __name__ == "__main__":
    main()
```

Each block here exists only for a role the service has: a service with no store builds no engine, one with
no upstream builds no transport.

**Logging is configured once, first** (`python-style` rule 17). **The run is not guarded:** a failure
propagates out of `main()` to a non-zero exit, which is how the scheduler that started the process
sees it. `python -m myapp` runs the one process; a service with several defines each as a module in
`entrypoints/` — the same module without its last two lines — declares one console script per module in
`[project.scripts]` (`python-toolchain`), and has no `__main__.py`.

**The process definition builds every settings object and hands concrete values down** — it is
this family's composition root, so the rule is `python-settings` rule 13 and its flat spelling
`flat-layered` rule 7.

**The transport and the engine are built once and wrap the whole run.** One pooled `httpx.AsyncClient`
and one engine exist before the run starts and are closed when it ends, the engine disposed even when
the run leaves by an exception (`flat-layered` rule 14). A second process definition building the same
things takes them from one builder rather than a copy (rule 14).

### A process that outlives one run

A loop or a consumer wraps each run in one guard and, for a loop, sleeps between runs on an interval
read from the process's settings — a required field with no default (`python-settings` rule 5). The
fragment sits inside `_run`, after `settings = Settings()`, the process's `Settings` declaring
`poll_interval_seconds: float` with no default:

```python
while True:
    await guarded("foo_sync", lambda: run_once(client, repository))
    await asyncio.sleep(settings.poll_interval_seconds)
```

`src/myapp/containment.py` — the guard, defined **once** for every process definition that needs it:

```python
from collections.abc import Awaitable, Callable

import structlog

__all__ = ["guarded"]

logger = structlog.get_logger()


async def guarded(run_name: str, run: Callable[[], Awaitable[object]]) -> bool:
    try:
        await run()
    except Exception:
        logger.exception("run_failed", run=run_name)
        return False
    return True
```

**The `try/except` is extracted into `guarded`, written once** (rule 8). It returns whether the run
succeeded, so a test asserts the containment on a value rather than on what was logged, and the run's
name rides on the one event it logs. It is not the framework-guarded progress helper of durable
obligation 8, which run functions call.

## Shape 2 — durable execution, once it is earned

Reach here only once one of the three conditions above has earned it. The shape is **three modules**:
an orchestration module that invokes units of work and computes nothing, a wrapper class adapting the
run function into the engine's unit of work, and a process definition that builds the dependencies once
and serves the engine's work — the only modules importing the engine's SDK (`flat-layered` rule 9). The
run function does not move, and none of the rules below changes.

Under a managed cloud orchestrator the orchestration definition leaves the repository and the wrapper
becomes the handler; under an in-process durable-function engine the three roles collapse into a durable
function plus its host.

**An engine adds obligations of its own** — replay determinism, continuations, progress reporting,
schedules as code — in the `## Rules` subsection that applies only once rule 1 has earned an engine.

## Shape 3 — the continuous stream process

A never-ending stream stays a standalone process with its own entrypoint module, whatever else the
service runs. It needs not a trigger but a **liveness check**: something outside the process reads the
stream's last observation timestamp and alarms if it is too old — a container healthcheck, a liveness
probe, or a scraped freshness metric with an alert rule.

A service that runs a stream beside scheduled work therefore has two processes, each a module in
`entrypoints/` with a console script of its own (`flat-layered`); the stream is the one that holds state
of its own between observations (rule 12), and it wraps each unit in the guard like any process that
outlives one run.

Never park the stream in one long-lived unit of work or make each item a workflow (rule 7): a workflow
per item is overhead and history for nothing, and a long-lived unit fights the engine's replay model.

A consumer's broker is its trigger: the SDK that receives messages is imported only by the
framework-wrapper package, which parses the message, runs the run function under `guarded`, and
acknowledges on `True` or returns the message on `False` (rules 11, 15). A broker the service publishes
to is an external system with a package of its own (`flat-layered` rule 16).

## Shape 4 — an HTTP trigger, on FastAPI

A service with no invariants of its own that answers requests — an internal CRUD surface, a webhook
receiver, a proxy — takes the same run functions behind a web framework. The framework is one more
wrapper (rule 9): routes validate, call one run function and hold no logic; every failure leaves in one
shape from one place; and the app is built by a factory the process definition calls with the
dependencies it built.

**Read `HTTP.md`** in this skill's directory before writing the app factory, its error handling, the
route's run function or the server's process definition — it carries the FastAPI and uvicorn templates
for rule 9.

## Other bindings

- **An external scheduler around the run-once process.** A cron entry, a systemd timer or a Kubernetes
  `CronJob` starts the process as written. Containment does not apply there: a failed run exits
  non-zero and the scheduler records it. The cadence becomes operable without a redeploy and the idle
  process goes, so prefer it to a loop wherever the platform runs a scheduler. A run killed halfway is
  still a run lost.
- **A durable-execution engine in place of either.** Restate and DBOS take the durable-function shape
  in-process; Step Functions and Azure Durable Functions are the managed equivalents; Airflow, Dagster
  and Prefect solve the batch-DAG half. The wrapper package and its process appear, every rule below
  holds unchanged, and the run function moves in none of them. What the engine *adds* is the durable
  obligations under `## Rules`, which hold in all of them.
- **Another web framework in place of FastAPI.** Starlette, Litestar, aiohttp or Flask: the app factory,
  the routes and the one error handler are spelled in that framework, and the process definition starts
  its server. The factory taking built dependencies, the routes that validate and call one run function,
  and the single rendering of catalogue errors are unchanged.

## Rules

1. **The trigger is chosen; a workflow engine is earned.** A loop, a cron entry or a timer is the
   default for scheduled work. Adopt a durable-execution engine only when a half-finished run must
   resume rather than restart, retries must outlive the process that made them, or a sequence runs
   long enough that the sequence itself has to survive. Absent one of those, the engine is the heaviest
   thing in the deployment and buys nothing.
2. **Every trigger wraps the same framework-free run function.** The loop body, the scheduled process
   and any framework wrapper all call one run function from its own module. The wrapper holds the
   trigger and no logic of its own; that is what keeps the shape choice reversible and keeps two
   triggers of the same work from drifting apart.
3. **A run function takes its dependencies as parameters** — the client, the repository class, whatever
   connection handle the data-access package's declared owner needs — and so does a wrapper that needs any:
   the process definition builds them once and hands them in. Never a module-level engine, never a
   settings singleton read from inside the body: a body that reaches for a global cannot be pointed at a
   test container, so a test of it proves nothing, and a wrapper that reaches for one puts the service's
   wiring back into global state, out of the process definition's reach and out of a test's.
4. **Retry and backoff are declared where the work is invoked, never hand-rolled inside it.** Under a
   loop that is the guard wrapping one run; under any trigger that offers a retry policy it is declared
   at the call site. A run function that sleeps and counts its own attempts has two retry policies and
   the outer one no longer bounds it.
5. **Return aggregates, not lists of items.** Run functions return frozen dataclasses of counters or
   timestamps, so what a trigger reports, logs or stores stays bounded; the items themselves live in the
   datastore. A read served over HTTP is the one exception by construction — it returns the single record
   it was asked for, never the items a run processed.
6. **The routing name a run is addressed to has exactly one source, and every participant reads it from
   that one place.** A queue URL, a topic, a subscription name or the name an engine routes work by is
   normally a per-deployment value and then belongs with the rest of the process's settings
   (`flat-layered` rule 8); where the platform makes the schedule itself code in the same repository, the
   name is a module constant both the schedule and the process serving it import, and a firewall rule
   pins that both read the one source. What is never
   acceptable is two sources — a schedule resolving the name from one environment and the process
   serving it from another — because the disagreement surfaces as work that silently goes nowhere, with
   nothing to catch it.
7. **A continuous stream is a process, not a scheduled run.** Give it its own entrypoint module and
   watch it from outside with a liveness check on the freshness of its last observation — for a queue,
   on the age of its oldest unconsumed message. Never model
   each incoming item as an orchestration, and never park the stream inside one long-lived unit of
   work — its retries restart a stream that was meant to resume.
8. **A process that outlives one run contains each run's failure in a named function, defined once.**
   "One failed run does not kill the process" is such a process's only testable contract, and a
   `try/except` written inline inside `while True` can only be reached by driving the loop — which needs
   an artificial escape that changes the thing under test. It lives in one module beside the process
   definitions and every one that needs it imports it; a copy per entrypoint is one contract per copy,
   and a test pins only one of them. A process that does one run and exits is not guarded: its failure
   is its exit status.
9. **An HTTP route validates its input, calls one run function, and holds no logic.** The app is built
   by a factory from dependencies the process definition hands it, and every failure — a catalogue
   error, the framework's validation failure, an unexpected exception — is rendered in one shape, in
   one place, never per route, and logged once there. A route that branches on the data, reaches the
   repository class, or catches a catalogue error itself has become a second place the work lives. A
   request from a third party is verified against the raw body it signed before the body is parsed, and
   a redelivery of one already recorded is answered as a success.
10. **An input whose size the service does not control is processed in bounded memory.** An upstream
    file, an export or a feed is streamed — read, transformed and written in bounded batches — and
    nothing in the process accumulates a whole source: no list of every record, no in-process set of
    every key seen. Deduplicating an unbounded input is the store's job, by its key and its conflict
    clause (`flat-persistence`), not a set's. The size that fits today is the size that exhausts the
    process the day upstream grows.
11. **A progress marker is written only after the data it confirms is durably written.** A cursor, a
    watermark or a checkpoint for a unit of work is written after that unit's own writes have returned,
    never while any of its rows sits in a buffer; and a buffer is never shared across units whose
    markers are written independently, because one unit's marker then confirms rows another unit's
    failure loses. A message acknowledgement is a progress marker too — sent only after the unit's
    effect is durable. A marker ahead of its data is data lost with a record saying it was kept.
12. **A file the process writes for another reader is written atomically.** A report, an export, or a
    position kept for the next start is written under a temporary name and moved over the final one in
    one atomic step (`os.replace` in the standard library), never written in place — a crash mid-write
    otherwise leaves a file its reader cannot parse, or reads half of. Where a process keeps local state
    between starts, it reads it at startup and an unreadable value stops the process, never a guarded
    run.
13. **A run that fans out over independent units contains each unit's failure and fails as a whole
    afterwards.** With bounded parallelism, one unit's failure neither cancels nor orphans the others:
    every unit is awaited to completion, each failure is recorded with the unit it belongs to, and a
    non-empty list of failed units at the end fails the run, so the guard or the trigger sees it. A
    concurrency primitive that propagates the first failure — a bare `asyncio.gather`, or a task group
    whose units raise — leaves the rest unawaited or cancelled, and the run reports one failure of many.
14. **Construction that several process definitions share is written once, in the process-definition
    package, and closes what it built.** Reading a component's settings and building its client, pool or
    engine lives in one builder there that every process definition imports, never copied into each; a
    copy per process is one wiring per copy, and they drift. The builder owns the thing's end as well as
    its start — the pool closed, the engine disposed — when the process leaves it, by any exit
    (`flat-layered` rule 14).
15. **A unit a broker delivered and the guard contained is neither acknowledged as done nor retried
    without bound.** It returns for redelivery up to a declared limit, then goes to a dead-letter
    destination the operator can read. The limit and the dead-letter destination are the broker's own
    configuration (a redrive policy, a delivery limit), declared with the deployment, never a counter in
    the process. Because delivery is then at least once, the unit's effect is idempotent under
    redelivery — a second delivery of a unit already applied changes nothing. A contained failure that
    acknowledges the unit loses it silently; one that retries forever blocks everything behind it. A
    polling run needs neither: its next tick is the retry.

### Once a durable-execution engine is earned

Rule 1 decides whether an engine is earned at all, and nothing below licenses one. These obligations
exist **only once an engine is in play** — a service on a loop, a cron entry or a timer can neither
satisfy nor violate them, and every rule above holds unchanged under an engine. They are numbered
separately from the rules and cited elsewhere as *durable obligation N*.

1. **Orchestration orchestrates; it does not compute.** The orchestration body is replayed from
   history, so any parsing, filtering, I/O or datastore access in it produces a different answer on
   replay and corrupts the run. It invokes units of work and does nothing else.
2. **Inside replayed code the engine's clock is the only clock.** Reading the wall clock, drawing
   randomness, or minting a random identifier makes replay diverge from the recorded history. Take the
   value from the engine, or pass it in as an argument.
3. **Orchestration code imports nothing with import-time state or side effects.** An engine may load
   or re-load the orchestration module in an isolated environment of its own, so an import that builds
   an object, opens a connection or reads configuration either fails there or runs again on every load.
   The orchestration module imports the engine and the declarations of the units it invokes, and nothing
   else.
4. **The wire name of a unit of work is declared explicitly, separately from the symbol implementing
   it.** Schedules, execution history and test stubs all bind to the wire name, so renaming the method
   must not be able to break a running schedule.
5. **The service's exceptions are translated at the framework boundary**, carrying the message, the
   identifying context and the original type across it. An untranslated exception reaches the history as
   an opaque framework failure with the context stripped, and the operator reading that history is the
   person who needed it.
6. **Where a run continues as a fresh one, the continuation carries every value the next needs, and the
   loop ends on an empty batch.** A continuation starts with fresh defaults, so a value left behind is
   recomputed or lost — a window reprocessed, a total under-reported; and a run that continues never
   reaches the statement after its loop, so a loop bounded by a count has its real termination nowhere.
7. **A unit of work that runs for minutes reports progress, and the gap the engine will tolerate is
   declared at the call site.** Without progress reports a dead serving process goes unnoticed until
   the whole close timeout elapses, and the unit can never be cancelled — so cancelling the run and
   shutting the serving process down gracefully both have to cut it off mid-flight. The tolerated gap
   must exceed the longest realistic interval between reports, the first one included.
8. **Progress reporting goes through a guarded helper, never the framework call directly.** The same
   body is called from a plain loop and from its own test, where the raw call raises because there is
   no framework context — the guard is what lets the body keep one shape under every trigger. **The
   helper is one named module at the root of the distribution's own package**, and it is the one module
   outside the framework-wrapper package allowed to import the framework, which is why the architecture
   firewall's allow-list names it (the firewall is `flat-layered` rule 9's). Where several
   distributions share one repository it is promoted to a library they both depend on, and the
   exemption is the same one.
9. **A healthcheck declares no retries.** Its whole job is to turn red the moment the thing it watches
   is stale; a retry hides exactly the failure it exists to surface. Where the engine is already present
   for other work, a short healthcheck run on a schedule is how a continuous stream's liveness check
   (rule 7 above) gets the engine's visibility machinery.
10. **Schedules are code, held in one versioned, re-runnable definition** — never created by hand in a
    console and never from inside the process serving the work. Each one states its catch-up window, its
    overlap policy and its time zone explicitly, never inheriting the engine's: whatever an engine
    defaults to decides how many missed runs replay after an outage, whether an overrunning run stacks
    under the next, and whether the cadence moves with daylight saving — three operational decisions no
    one made.
11. **The engine's connection settings are required, with no default.** Its address, and whatever
    namespace or tenant it routes by, come from the process's settings like any other tunable
    (`flat-layered` rule 10); a default lets a deployment that forgot one start and reach the wrong
    engine instead of failing at startup.

## Hard stops

- A workflow engine is being added for work that is merely *scheduled* — no run has to survive a
  restart, no retry has to outlive the process, no sequence runs for hours → stop, use shape 1; one run
  per process, scheduled or looped, is the default and the engine is not yet earned.
- Durability, cross-restart retries or multi-step orchestration is being hand-rolled inside a loop — a
  state table, a lease, an attempt counter, an at-most-once guard → stop, that is a workflow engine
  being reimplemented; adopt one, and read the durable obligations for what it then obliges.
- A run function imports a framework → stop, the framework belongs in the framework-wrapper package
  (`flat-layered` rule 9); the body must stay callable from a loop and a test.
- Retry logic is being hand-written inside a run function with sleeps and counters → stop, declare the
  retry where the work is invoked.
- A run function returns a list of ids or records → stop, return an aggregate dataclass; a trigger's
  report is not a data bus.
- A continuous stream is being modelled as a long-running unit of work, or one trigger per item → stop,
  keep the stream as a separate process and watch it with a liveness check.
- A schedule and the process serving it resolve the routing name from two different places → stop, give
  it one source both of them read.
- Business logic is being written into the wrapper instead of the run function → stop, the wrapper holds
  the trigger; the work stays where a test can call it directly.
- An HTTP route reaches the repository class or the client itself, or maps a catalogue error to a status of
  its own → stop, route through a run function and let the one handler render it.
- A third party's request body is parsed before its signature is verified against the raw bytes, or a
  redelivery of a request already recorded is answered as a failure → stop (rule 9).
- The web app is built at module scope → stop, build it in a factory the process definition calls with
  the dependencies it built.
- A run reads a whole unbounded source into memory, or deduplicates one with an in-process set → stop,
  stream it in bounded batches and let the store's key and conflict clause deduplicate.
- A cursor, watermark or checkpoint is written while the rows it confirms are still buffered, or one
  buffer is shared by units whose markers are written separately → stop, write each unit's rows, then
  its marker.
- A file written for another reader is written in place, or unreadable local state is caught inside a
  guard → stop, write under a temporary name and replace atomically, and stop at startup (rule 12).
- A contained failure acknowledges a unit a broker delivered, or returns it for redelivery with no
  broker-declared limit and no dead-letter destination, or the unit's effect is not idempotent under
  redelivery → stop (rule 15).
- A fan-out over independent units lets the first failure cancel or orphan the rest, or swallows the
  failures → stop, await every unit, collect the failures, and fail the run on a non-empty list.
- `guarded` is copied into a second process definition → stop, import the one module every process
  definition shares. A run-once process wraps its run in it → stop, the failure is its exit status.
- A process sleeps on a hard-coded interval → stop, the interval is a required settings field.
- A process definition copies construction another process definition also performs, or builds a
  client, a pool or an engine it never closes → stop, write the construction once in the
  process-definition package, closing what it built, and import it (rule 14).

### Under a durable-execution engine

These fire only once rule 1 has earned an engine; under every other trigger there is nothing to break.

- An orchestration body is about to call an HTTP client, a write helper, or any I/O directly → stop,
  move that call into a unit of work and invoke it from the orchestration.
- The wall clock, randomness or a random identifier is read inside replayed code → stop, take the value
  from the engine's clock or pass it in; replay diverges from history and corrupts the run.
- A continuation is taken without a value the next run needs, or a continuing batch loop ends on an
  iteration bound rather than an empty batch → stop, carry every value and end on the empty batch
  (durable obligation 6).
- A unit of work that runs for minutes declares a close timeout and no progress reporting → stop, add
  both; otherwise a dead serving process goes unnoticed for the whole timeout and the unit can never be
  cancelled.
- A run-function body calls the framework's progress function directly → stop, use the guarded helper;
  the unguarded call raises the moment the body runs from a loop or a test.
- A schedule is created by hand in a console, from inside the process serving the work, or without an
  explicit catch-up window, overlap policy and time zone → stop; it belongs in the versioned definition,
  and an inherited default is a decision nobody made.
- An orchestration module imports something with import-time state or side effects → stop, import only
  the engine and the unit declarations it invokes.
- A healthcheck run declares retries → stop, the retry hides the staleness it exists to report.
- A service exception escapes the framework boundary untranslated → stop, wrap it so the context and the
  error type survive.
- An engine connection setting is being given a default → stop, it is required; a deployment that
  forgets one must fail at startup rather than reach the wrong engine.
