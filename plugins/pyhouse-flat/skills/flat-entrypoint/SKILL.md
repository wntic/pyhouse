---
name: flat-entrypoint
description: Use when choosing how a flat-layered service is triggered and writing the process that triggers it — a plain loop, a cron entry or a timer, a continuous stream process, a thin HTTP wrapper, or durable execution — and deciding whether a workflow engine is earned at all; the loop is the default, and an engine is earned only by durability across process death, retries that outlive the process, or orchestration long enough that the sequence itself must survive. Owns the framework-free run function every trigger wraps, the process definition that builds its dependencies once and passes them down, the retry declared where the work is invoked, the aggregate a run returns, and the containment that keeps one failed run from killing the process. It also carries the obligations that exist only once a durable-execution engine is in play, which are inert under every other trigger. Testing any of it is `flat-test-run-function`.
when_to_use: Also when asked for a polling loop, a `__main__` entrypoint, a nightly or periodic job, a queue or websocket consumer process, a webhook, an internal CRUD or proxy endpoint on a service with no invariants, a durable workflow, a batch loop, a heartbeat, a schedule or a cron expression, an overlap or catch-up policy, or whether this service needs a workflow engine at all.
---

# Flat-Layered Entrypoint — loop vs schedule vs stream vs HTTP vs durable

Covers the **process-definition** and **framework-wrapper** roles of one `flat-layered` service, whatever
this service calls those packages. The shapes differ only in *what triggers a run*; the run itself always
calls the same run functions, so switching later is a wrapper change, not a rewrite.

The invariant that makes that true: **the run function is a plain async function taking its dependencies
as arguments, living in a work-unit package, and importing no framework.** Everything in this skill is a
wrapper around one of those.

Every template below is one distribution: `myapp` is this service's own root package (`flat-layered`), and
nothing here assumes a sibling distribution or a repository above it.

## When to use vs. neighbours

- The architecture family is not settled yet — this may not be a flat-layered service at all →
  `architecture-choice` decides hexagonal versus flat first; everything here assumes flat.
- The service's own settings and logging modules, its client and payload packages → not this skill, use
  `flat-layered`, which owns the role kinds and the import contract between them.
- The tables, the write path and the storage class the run function calls → `flat-persistence`.
- Several distributions sharing one repository — the member split, the container profiles, the root task
  runner → `python-workspace`. One distribution on its own needs none of it.
- **Durable execution, once it is earned** — the obligations that exist only under a workflow engine →
  still this skill, under `## Rules`, in the subsection that applies once rule 1 has earned an engine.
  Nothing else in this file depends on them.
- The scheduling needs are met by a loop, a cron entry or a timer — the default → none of those
  obligations apply; do not add orchestration modules "for later".
- The named exceptions a wrapper translates at the framework boundary → `exception-catalog` owns the
  catalogue, how a library's exception is translated into it, and its status; the one rendering place is
  this skill's HTTP shape (`HTTP.md`). `flat-layered` rule 6 places the translation inside the client
  that called the library, and its `CATALOG.md` states the classes this family raises.
- The service answers HTTP but has business invariants, or several entrypoints share its rules → not
  this family; `architecture-choice` decides, and the HTTP shell is `hex-restapi-app`, in the
  `pyhouse-hex` plugin.
- Testing any of it — the run function, the loop's containment, the wrapper, the orchestration above them
  → `flat-test-run-function`.

## The trigger process — four shapes

| The work is… | Shape | Lives in |
|---|---|---|
| Anything on a schedule, as the starting assumption — a poll, a periodic pass, a nightly job | **Self-scheduling loop, or an external scheduler running the process once** | one module in the process-definition package |
| Scheduled work that must *also* survive a restart mid-run, retry across process death, or orchestrate steps over hours or days | **Durable execution** — a workflow engine | a framework-wrapper package plus its serving process |
| A never-ending stream — a log or change feed, a queue consumer, a websocket feed | **Standalone stream process**, watched by an external liveness check | one module in the process-definition package |
| A request someone else sends — a webhook, an internal CRUD or proxy endpoint, on a service with no invariants of its own | **HTTP trigger** — a thin web-framework wrapper | a framework-wrapper package plus its server process |

**The default for scheduled work is a plain loop, a cron entry or a timer.** A process that wakes up,
does one run, and sleeps is the whole of most scheduling requirements, and it costs one module and no
infrastructure. Start there.

**A workflow engine is earned, not assumed.** Three things earn it, and nothing else does:

- **Durability across process death** — a run that is half-finished when the pod is evicted must resume,
  not restart. A loop cannot offer this; its state is in the process.
- **Cross-restart retries with a real backoff and a history** — an operator needs to see that attempt 3
  of 5 failed at 04:12 and why, after the process that made it is gone.
- **Long-running orchestration** — several steps, with waits, timers or human input between them,
  where the sequence itself is the thing that must survive.

If none of those is true, the engine is the heaviest thing in the deployment and buys nothing. If one of
them is, a loop will be reinvented badly: a `_state` table, a retry counter, a lease, an at-most-once
guard, all of it hand-rolled and none of it tested.

Shapes 3 and 4 are outside that choice: a continuous stream and a request are **not** scheduled work,
and neither scheduling shape applies to them. See below.

## The run function — shared by every shape (structlog)

`src/myapp/ingest/foo_ingest.py` — an upstream-pull run function: no framework import, every dependency a
parameter. `ingest/` is this example's name for one work-unit package (`flat-layered`).

```python
from datetime import UTC, datetime

import structlog

from myapp.schemas import Foo, FooPayload, IngestResult
from myapp.services import FooClient
from myapp.storage import FooStorage

logger = structlog.get_logger()


def to_foo(payload: FooPayload, observed_at: datetime) -> Foo | None:
    """The filter and the mapping in one pure step: a payload with no reference is dropped."""
    if payload.ref is None:
        return None
    return Foo(id=None, reference=payload.ref, name=payload.name, observed_at=observed_at, labels=payload.labels)


async def run_once(client: FooClient, storage: FooStorage) -> IngestResult:
    payloads = await client.fetch_batch()
    observed_at = datetime.now(UTC)
    foos = [foo for foo in (to_foo(payload, observed_at) for payload in payloads) if foo is not None]
    await storage.record_batch(foos)

    logger.info("foo_ingest_completed", fetched=len(payloads), kept=len(foos))
    return IngestResult(fetched=len(payloads), kept=len(foos))
```

`run_once` takes the client and the storage class as **parameters**. A body that reaches for a
module-level engine or a settings singleton cannot be pointed at a test container, and a test of it
proves nothing.

**The run function opens no transaction.** The storage class is the declared owner of its own
(`flat-persistence` rule 3), so the body composes calls and counts what came back. A run function that
opens a connection has moved data access out of the one package that is allowed to hold it.

It returns an **aggregate**, not the rows: the rows are in the datastore, and the caller wants counts. A
trigger that serializes the return value into a durable history makes this load-bearing rather than
merely tidy.

## Shape 1 — the self-scheduling loop, on asyncio (the default)

`src/myapp/entrypoints/foo_loop.py`:

```python
import asyncio
from collections.abc import Awaitable, Callable

import structlog

from myapp.ingest.foo_ingest import run_once
from myapp.services import FooClient
from myapp.settings import get_settings
from myapp.storage import FooStorage, get_engine, get_storage_settings

logger = structlog.get_logger()

_POLL_INTERVAL_SECONDS = 30


async def guarded(run: Callable[[], Awaitable[object]]) -> bool:
    """One run with its failure contained; returns whether the run succeeded."""
    try:
        await run()
    except Exception:
        logger.exception("foo_ingest_run_failed")
        return False
    return True


async def main() -> None:
    settings = get_settings()
    storage = FooStorage(get_engine(get_storage_settings().dsn.get_secret_value()))
    client = FooClient(settings.foo_api_url, settings.foo_api_timeout_seconds)

    while True:
        await guarded(lambda: run_once(client, storage))
        await asyncio.sleep(_POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
```

`run_once` is imported from its own module: run functions routinely share that name, so a module whose
name collides stays out of its package's re-export and is reached by explicit import where it is
consumed (`python-packaging`). A run function with a name of its own is re-exported like any other.

**The process definition is the only place a settings factory is called.** It reads each configured
component's settings — the process's own and the storage package's — and hands concrete values down to
the client, the storage class and the run function. A component owning its settings class does not give
a module inside it licence to call that factory (`flat-layered` rules 7 and 8).

**Extract the `try/except` into `guarded`.** The loop's contract is "one failed run does not kill the
process", and that is the only part worth testing. A `try/except` written inline inside `while True`
can only be tested by driving the loop, which needs an artificial escape — and building the escape
changes the thing under test. `guarded` returns whether the run succeeded, so a test asserts the
containment on a value rather than on what was logged.

**The interval is one named constant, declared beside the loop that sleeps on it.** `30` is this
example's cadence and means nothing outside it — a project sets the number from how fast upstream
changes and what the upstream will tolerate. What the rule fixes is the *shape*: a bare
`asyncio.sleep(30)` buried in the loop body hides the service's cadence from anyone reading the module,
and a cadence read from the environment can drift out of step with the rate limit it was chosen against.
If the cadence genuinely has to change per deployment, it becomes a settings field and the entrypoint
passes it in — the same rule as every other tunable in `flat-layered`.

## Shape 2 — durable execution, once it is earned

Reach here only once durability, cross-restart retries or long-running orchestration has earned it, by
the three conditions above. The shape is **three modules**: an orchestration module that invokes units of
work and computes nothing, a wrapper class that adapts the run function into the engine's unit of work,
and a process definition that builds the dependencies once and serves the engine's work. They are the only
modules in the service that import the engine's SDK (`flat-layered` rule 9). The run function does not
move, and none of the rules below changes.

Under a managed cloud orchestrator the orchestration definition leaves the repository and the wrapper
becomes the handler; under an in-process durable-function engine the three roles collapse into a durable
function plus its host.

**An engine adds obligations of its own** — replay determinism, continuations, progress reporting,
schedules as code. They are stated under `## Rules` below, in the subsection that applies only once rule
1 has earned an engine; a service on a loop can neither satisfy nor violate them.

## Shape 3 — the continuous stream process

A never-ending stream stays a standalone process with its own entrypoint module, whatever else the
service runs. What it needs is not a trigger but a **liveness check**: something outside the process
reads the stream's last observation timestamp and alarms if it is too old. A container healthcheck, a
liveness probe, or a scraped freshness metric with an alert rule all do this, and a service with no
workflow engine should use one of them.

So a service can end up with two entrypoint modules:

```text
entrypoints/
├── foo_ingest_durable.py   # process: serves the engine's foo-ingest work, where an engine is earned
└── foo_stream.py           # process: a long-lived continuous stream, stateful
```

Do **not** park the stream inside one long-lived unit of work, and do not model each incoming item as a
workflow. A workflow per item turns every item into orchestration overhead and history the engine must
keep, and adds no value; a long-lived unit of work fights the replay model every durable-execution
engine is built on, and its retries restart a stream that was meant to resume.

## Shape 4 — an HTTP trigger, on FastAPI

A service with no invariants of its own that answers requests — an internal CRUD surface, a webhook
receiver, a proxy — takes the same run functions behind a web framework. The framework is one more
wrapper: **routes validate their input, call one run function, and hold no logic of their own**, and
every failure, catalogue or not, leaves in one shape from one place. A route never reaches the storage
class or the client except to hand them to a run function, and a read is a run function too, however
thin. The app is built by a factory the process definition calls with the dependencies it built.

**Read `HTTP.md`** in this skill's directory before writing the app factory, its error handling, the
read's run function or the server's process definition — it carries the FastAPI and uvicorn templates
for rule 9.

## Other bindings

- **An external scheduler in place of the self-scheduling loop.** Drop the `while True` and the sleep,
  run `main()` once, and the module is a cron entry, a systemd timer or a Kubernetes `CronJob`. Wiring
  and failure containment are unchanged; the cadence becomes operable without a redeploy and the idle
  process goes, so prefer it wherever the platform already runs a scheduler. Durability is still not
  bought — a run killed halfway is still a run lost.
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
   and any framework wrapper all call one run function from a work-unit package. The wrapper holds the
   trigger and no logic of its own; that is what keeps the shape choice reversible and keeps two
   triggers of the same work from drifting apart.
3. **A run function takes its dependencies as parameters** — the client, the storage class, whatever
   connection handle the storage package's declared owner needs — and so does a wrapper that needs any:
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
   name is a module constant both the schedule and the process serving it import. What is never
   acceptable is two sources — a schedule resolving the name from one environment and the process
   serving it from another — because the disagreement surfaces as work that silently goes nowhere, with
   nothing to catch it.
7. **A continuous stream is a process, not a scheduled run.** Give it its own entrypoint module and
   watch it from outside with a liveness check on the freshness of its last observation. Never model
   each incoming item as an orchestration, and never park the stream inside one long-lived unit of
   work — its retries restart a stream that was meant to resume.
8. **The loop's failure containment is extracted into a named function.** "One failed run does not
   kill the process" is the loop's only testable contract, and a `try/except` written inline inside
   `while True` can only be reached by driving the loop — which needs an artificial escape that
   changes the thing under test.
9. **An HTTP route validates its input, calls one run function, and holds no logic.** The app is built
   by a factory from dependencies the process definition hands it, and every failure — a catalogue
   error, the framework's validation failure, an unexpected exception — is rendered in one shape, in
   one place, never per route, and logged once there. A route that branches on the data, reaches the
   storage class, or catches a catalogue error itself has become a second place the work lives.

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
6. **A continuation carries every value the next run needs** — the cutoff *and* the running total. A
   continuation starts a fresh run with fresh defaults, so a cutoff left behind means the next run
   recomputes it and reprocesses part of the same window, and a total left behind means the final
   result under-reports the logical run.
7. **The batch loop ends on an empty batch and returns the summed aggregate.** The empty batch is its
   termination condition, never a bound on the number of iterations: a run that takes a continuation
   never reaches the statement after the loop, so a loop bounded by a count has its real termination
   condition nowhere and dead code where it should be. The ceiling in obligation 8 decides when to
   continue, not when to stop.
8. **The batch ceiling is a named, public module constant** — no leading underscore — so the test that
   asserts the continuation fires reads the same number the loop does instead of hardcoding it a second
   time. An underscore-prefixed name says "do not read this" to the one reader that has to.
9. **A unit of work that runs for minutes reports progress, and the gap the engine will tolerate is
   declared at the call site.** Without progress reports a dead serving process goes unnoticed until
   the whole close timeout elapses, and the unit can never be cancelled — so cancelling the run and
   shutting the serving process down gracefully both have to cut it off mid-flight. The tolerated gap must exceed the longest
   realistic interval between reports, the first one included.
10. **Progress reporting goes through a guarded helper, never the framework call directly.** The same
    body is called from a plain loop and from its own test, where the raw call raises because there is
    no framework context — the guard is what lets the body keep one shape under every trigger. **The
    helper is one named module at the root of the distribution's own package**, and it is the one module
    outside the framework-wrapper package allowed to import the framework, which is why the architecture
    firewall's allow-list names it (`flat-layered` rule 9, `test-architecture-rule`). Where several
    distributions share one repository it is promoted to a library they both depend on, and the
    exemption is the same one.
11. **A healthcheck declares no retries.** Its whole job is to turn red the moment the thing it watches
    is stale; a retry hides exactly the failure it exists to surface. Where the engine is already present
    for other work, a short healthcheck run on a schedule is how a continuous stream's liveness check
    (`## Rules` rule 7, not durable obligation 7) gets the engine's visibility machinery.
12. **Schedules are code, held in one versioned, re-runnable definition** — never created by hand in a
    console and never from inside the process serving the work. Each one states its catch-up window, its
    overlap policy and its time zone explicitly, never inheriting the engine's: whatever an engine
    defaults to decides how many missed runs replay after an outage, whether an overrunning run stacks
    under the next, and whether the cadence moves with daylight saving — three operational decisions no
    one made.
13. **The engine's connection settings are required, with no default.** Its address, and whatever
    namespace or tenant it routes by, come from the process's settings like any other tunable
    (`flat-layered` rule 10); a default lets a deployment that forgot one start and reach the wrong
    engine instead of failing at startup.

## Hard stops

- A workflow engine is being added for work that is merely *scheduled* — no run has to survive a
  restart, no retry has to outlive the process, no sequence runs for hours → stop, use shape 1; a loop,
  a cron entry or a timer is the default and the engine is not yet earned.
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
- An HTTP route reaches the storage class or the client itself, or maps a catalogue error to a status of
  its own → stop, route through a run function and let the one handler render it.
- The web app is built at module scope → stop, build it in a factory the process definition calls with
  the dependencies it built.

### Under a durable-execution engine

These fire only once rule 1 has earned an engine; under every other trigger there is nothing to break.

- An orchestration body is about to call an HTTP client, a write helper, or any I/O directly → stop,
  move that call into a unit of work and invoke it from the orchestration.
- The wall clock, randomness or a random identifier is read inside replayed code → stop, take the value
  from the engine's clock or pass it in; replay diverges from history and corrupts the run.
- A continuation is taken without a value the next run needs — the cutoff, the running total → stop, the
  next run recomputes the window or under-reports the logical run, and no other test notices.
- The batch loop terminates on an iteration bound instead of on an empty batch → stop; a run that takes
  a continuation never reaches the statement after the loop, so the real termination condition is
  missing and what stands in its place is dead.
- A unit of work that runs for minutes declares a close timeout and no progress reporting → stop, add
  both; otherwise a dead serving process goes unnoticed for the whole timeout and the unit can never be cancelled.
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
