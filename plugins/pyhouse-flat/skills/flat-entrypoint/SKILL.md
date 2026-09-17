---
name: flat-entrypoint
description: Use when choosing how a flat-layered service is triggered and writing the process that triggers it — a plain loop, a cron entry or a timer, a continuous stream process, or durable execution — and deciding whether a workflow engine is earned at all; the loop is the default and the engine is earned by durability, cross-restart retries or long-running orchestration, never assumed. Owns the framework-free run function every trigger wraps, the process definition that builds its dependencies once and passes them down, and, once an engine is earned, the orchestration obligations that come with it — a continuation carrying every value the next run needs, progress reported through a guarded helper, and schedules held as code. Testing any of it is `flat-test-run-function`.
when_to_use: Also when asked for a polling loop, a `__main__` entrypoint, a nightly or periodic job, a queue or websocket consumer process, a durable workflow, a batch loop, a heartbeat, a schedule or a cron expression, an overlap or catch-up policy, or whether this service needs a workflow engine at all.
paths: ["**/entrypoints/**", "**/ingest/**", "**/jobs/**"]
---

# Flat-Layered Entrypoint — loop vs schedule vs stream vs durable

Covers the **process-definition** and **framework-wrapper** packages of one `flat-layered` service —
`entrypoints/` and `temporal/` in that skill's worked example, whatever this service calls its own. The
shapes differ only in *what triggers a run*; the run itself always calls the same run functions, so
switching later is a wrapper change, not a rewrite.

The invariant that makes that true: **the run function is a plain async function taking its
dependencies as arguments, living in a run-function package — upstream-pull or stored-data-pass,
`ingest/` and `jobs/` in the worked example — and importing no framework.** Everything in this skill is
a wrapper around one of those.

Every template below is one service, one distribution: `myapp` is this service's own package
(`flat-layered`), and nothing here needs a workspace or a sibling service.

## When to use vs. neighbours

- The architecture family is not settled yet — this may not be a flat-layered service at all →
  `architecture-choice` decides hexagonal versus flat first; everything here assumes flat.
- The service's own settings and logging modules, its client and payload packages — `settings.py`,
  `services/`, `schemas/` in the worked example → not this skill, use `flat-layered`.
- The tables, the write path and the storage class the run function calls → `flat-persistence`.
- Several services sharing one repository — the member split, the container profiles, the root task
  runner → `flat-monorepo`. A lone service needs none of it.
- The worked durable-execution code — the activity class, the orchestration module, the worker process,
  the batch loop, the guarded progress helper, the healthcheck workflow and the schedule definition →
  the sibling `DURABLE.md` in this skill's own directory. **Read it only once shape 2 is earned**; the
  obligations it binds are in `## Rules` below.
- The scheduling needs are met by a loop, a cron entry or a timer — the default → nothing in `DURABLE.md`
  applies; do not add orchestration modules "for later".
- The named exceptions a wrapper translates at the framework boundary → `exception-catalog` owns the
  catalogue and the error types; this skill owns only the translation at the wrapper.
- Testing any of it — the run function, the loop's containment, the wrapper, the orchestration above them
  → `flat-test-run-function`.

## Picking a shape

| The work is… | Shape | Lives in |
|---|---|---|
| Anything on a schedule, as the starting assumption — a poll, a periodic pass, a nightly job | **Self-scheduling loop, or an external scheduler running the process once** | a process module, `entrypoints/<name>_loop.py` in the worked example |
| Scheduled work that must *also* survive a restart mid-run, retry across process death, or orchestrate steps over hours or days | **Durable execution** — a workflow engine, worked in `DURABLE.md` with Temporal | a framework-wrapper package plus its worker process |
| A never-ending stream — a subprocess tailing an append-only upstream log, a queue consumer, a websocket feed | **Standalone stream process**, watched by an external liveness check | `entrypoints/<name>_stream.py` |

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

Shape 3 is the exception to the choice: a continuous stream is **not** scheduled work, and neither shape
applies to it. See below.

## The run function — shared by every shape (structlog)

`myapp/ingest/foo_ingest.py` — an upstream-pull run function: no framework import, every dependency a
parameter.

```python
import structlog

from myapp.schemas.foo import IngestResult
from myapp.services.foo_client import FooClient
from myapp.storage.foo_storage import FooStorage

logger = structlog.get_logger()


async def run_once(client: FooClient, storage: FooStorage) -> IngestResult:
    payloads = await client.fetch_batch()
    foos = [foo for foo in (to_foo(payload) for payload in payloads) if foo is not None]
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

It returns an **aggregate**, not the rows. That matters most under a workflow engine, where the return
value is serialized into durable history, but it is the right shape everywhere: the rows are in the
datastore, and the caller wants counts.

## Shape 1 — the self-scheduling loop, on asyncio (the default)

`myapp/entrypoints/foo_loop.py`:

```python
import asyncio
from collections.abc import Awaitable, Callable

import structlog

from myapp.ingest.foo_ingest import run_once
from myapp.services.foo_client import FooClient
from myapp.settings import get_settings
from myapp.storage.engine import get_engine
from myapp.storage.foo_storage import FooStorage
from myapp.storage.settings import get_storage_settings

logger = structlog.get_logger()

_POLL_INTERVAL_SECONDS = 30


async def guarded(run: Callable[[], Awaitable[object]]) -> None:
    """One run, with failure contained. Extracted so it can be tested without the loop."""
    try:
        await run()
    except Exception:
        logger.exception("foo_ingest_run_failed")


async def main() -> None:
    settings = get_settings()
    storage = FooStorage(get_engine(get_storage_settings().dsn))
    client = FooClient(settings.foo_api_url, settings.foo_api_timeout_seconds)

    while True:
        await guarded(lambda: run_once(client, storage))
        await asyncio.sleep(_POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
```

**The process definition is the only place a settings factory is called.** It reads each configured
component's settings — the process's own and the storage package's — and hands concrete values down to
the client, the storage class and the run function. A component owning its settings class does not give
a module inside it licence to call that factory (`flat-layered` rules 7 and 8).

**Extract the `try/except` into `guarded`.** The loop's contract is "one failed run does not kill the
process", and that is the only part worth testing. A `try/except` written inline inside `while True`
can only be tested by driving the loop, which needs an artificial escape — and building the escape
changes the thing under test.

**The interval is one named constant, declared beside the loop that sleeps on it.** `30` is this
example's cadence and means nothing outside it — a project sets the number from how fast upstream
changes and what the upstream will tolerate. What the rule fixes is the *shape*: a bare
`asyncio.sleep(30)` buried in the loop body hides the service's cadence from anyone reading the module,
and a cadence read from the environment can drift out of step with the rate limit it was chosen against.
If the cadence genuinely has to change per deployment, it becomes a settings field and the entrypoint
passes it in — the same rule as every other tunable in `flat-layered`.

**The same loop body runs under an external scheduler.** Drop the `while True` and the sleep, run
`main()` once, and the process is a cron entry, a systemd timer or a Kubernetes `CronJob` — a scheduler
outside the process decides the cadence, and the module is otherwise unchanged. Prefer this wherever the
platform already runs one: it makes the cadence operable without a redeploy and removes the idle
process. It does **not** add durability; a run killed halfway is still a run lost.

## Shape 2 — durable execution, once it is earned

Reach here only once durability, cross-restart retries or long-running orchestration has earned it, by
the three conditions above. The shape is **three modules**: an orchestration module that invokes units of
work and computes nothing, a wrapper class that adapts the run function into the engine's unit of work
and translates the service's exceptions, and a worker process that builds the dependencies once and
serves the engine's queue. They are the only modules in the service that import the engine's SDK
(`flat-layered` rule 9). The run function does not move.

Under a managed cloud orchestrator the orchestration definition leaves the repository and the wrapper
becomes the handler; under an in-process durable-function engine the three roles collapse into a durable
function plus its host. The obligations in `## Rules` hold in all of them.

**Read the sibling `DURABLE.md` in this skill's directory for the worked code** — the wrapper class, the
orchestration module, the worker process, the batch loop with its continuation, the addable aggregate,
the guarded progress helper, the healthcheck workflow and the schedule definition, all bound to Temporal
and each under a heading naming it.

## Shape 3 — a continuous stream is not a workflow

A never-ending stream stays a standalone process with its own entrypoint module, under either of the
shapes above. What it needs is not a trigger but a **liveness check**: something outside the process
reads the stream's last observation timestamp and alarms if it is too old. A container healthcheck, a
liveness probe, or a scraped freshness metric with an alert rule all do this, and a service with no
workflow engine should use one of them. Where the engine is already present for other work, a short
**healthcheck workflow** on a schedule is the same check with the same retry and visibility machinery as
everything else (`DURABLE.md`).

So a service can end up with two entrypoint modules:

```text
entrypoints/
├── temporal_worker.py      # registers the orchestration and its units of work, serves the queue
└── foo_stream.py           # the continuous stream itself, stateful, long-lived
```

Do **not** wrap the stream in a "long-lived activity with heartbeat", and do not model each incoming
item as a workflow. A workflow per item burns the engine's action budget and adds no value; a long-lived
activity fights the replay model every durable-execution engine is built on, and its retries restart a
stream that was meant to resume.

## Other bindings

- **Another durable-execution engine in place of Temporal.** Restate and DBOS take the same durable-
  function shape in-process; Step Functions and Azure Durable Functions are the managed equivalents;
  Airflow, Dagster and Prefect solve the batch-DAG half. The wrapper package and the worker process
  change — under a managed orchestrator the orchestration definition leaves the repository and the
  wrapper becomes the handler; a batch-DAG scheduler replaces the continuation with a task that re-queues
  itself. Every rule below holds unchanged, and the run function moves in none of them.
- **An external scheduler in place of the self-scheduling loop.** Drop the `while True` and the sleep,
  run `main()` once, and the module is a cron entry, a systemd timer or a Kubernetes `CronJob` (shape 1
  above). Wiring and failure containment are unchanged; the cadence becomes operable without a
  redeploy, and durability is still not bought.
- **The plain loop is not one binding among several — it is the default the engine must be earned
  against.** Nothing above licenses shape 2 without durability, cross-restart retries or long-running
  orchestration to point at.

## Rules

1. **The trigger is chosen; a workflow engine is earned.** A loop, a cron entry or a timer is the
   default for scheduled work. Adopt a durable-execution engine only when a half-finished run must
   resume rather than restart, retries must outlive the process that made them, or a sequence runs
   long enough that the sequence itself has to survive. Absent one of those, the engine is the heaviest
   thing in the deployment and buys nothing.
2. **Every trigger wraps the same run function.** The loop body, the scheduled process and the
   durable-execution wrapper all call one run function from the upstream-pull or stored-data-pass
   package — `ingest/` and `jobs/` in the worked example. The wrapper holds the trigger, the retry and
   the backoff and no logic of its own; that is what keeps the shape choice reversible and keeps two
   triggers of the same work from drifting apart.
3. **A run function takes its dependencies as parameters** — the client, the storage class, whatever
   connection handle the storage package's declared owner needs. Never a module-level engine, never a
   settings singleton read from inside the body: a body that reaches for a global cannot be pointed at a
   test container, so a test of it proves nothing.
4. **Orchestration orchestrates; it does not compute.** Under a durable-execution engine the
   orchestration body is replayed from history, so any parsing, filtering, I/O or datastore access in it
   produces a different answer on replay and corrupts the run. It invokes units of work and does
   nothing else.
5. **Retry and backoff are declared where the unit of work is invoked, never hand-rolled inside it.**
   Under an engine that is a retry policy on the call; under the plain loop it is the guard wrapping one
   run. A unit of work that sleeps and counts its own attempts has two retry policies and the outer one
   no longer bounds it.
6. **The routing name a worker serves is one module constant per service.** Never shared with a sibling
   service, and never read from the environment: a schedule and a worker that resolve it from separate
   environments can disagree at runtime with nothing to catch them.
7. **A wrapper that needs dependencies takes them through its constructor**; a bare function is only
   for a wrapper with none. The process definition builds them once and hands them in — a wrapper that
   reaches for a module-level engine puts the service's wiring back into global state, out of the
   process definition's reach and out of a test's.
8. **The wire name of a unit of work is declared explicitly, separately from the symbol implementing
   it.** Schedules, execution history and test stubs all bind to the wire name, so renaming the method
   must not be able to break a running schedule.
9. **The service's exceptions are translated at the framework boundary**, carrying the message, the
   identifying context and the original type across it. An untranslated exception reaches the history as
   an opaque framework failure with the context stripped, and the operator reading that history is the
   person who needed it.
10. **Return aggregates, not lists of items.** Run functions return frozen dataclasses of counters or
    timestamps, so payload and history size stay bounded; the items themselves live in the datastore.
11. **An orchestration module keeps its non-engine imports out of the engine's sandbox.** An engine
    that re-imports modules per run is slow on anything heavy and fails outright on anything with
    import-time state.
12. **A continuous stream is a process, not a scheduled run.** Give it its own entrypoint module and
    watch it from outside with a liveness check on the freshness of its last observation. Never model
    each incoming item as an orchestration, and never park the stream inside one long-lived unit of
    work — its retries restart a stream that was meant to resume.
13. **The loop's failure containment is extracted into a named function.** "One failed run does not
    kill the process" is the loop's only testable contract, and a `try/except` written inline inside
    `while True` can only be reached by driving the loop — which needs an artificial escape that
    changes the thing under test.
14. **Inside replayed code the engine's clock is the only clock.** Reading the wall clock, drawing
    randomness, or minting a random identifier makes replay diverge from the recorded history. Take the
    value from the engine, or pass it in as an argument.
15. **A continuation carries every value the next run needs** — the cutoff *and* the running total. A
    continuation starts a fresh run with fresh defaults, so a cutoff left behind means the next run
    recomputes it and reprocesses part of the same window, and a total left behind means the final
    result under-reports the logical run. Two or more values go through the engine's argument-list form,
    because the single-positional form fails *inside* the run, which retries the failure forever instead
    of surfacing it.
16. **The batch loop ends on an empty batch and returns the summed aggregate**, and it is written as an
    unbounded loop with an explicit counter, never a bounded loop with a trailing `return`. A
    continuation never returns, so that trailing statement is dead code standing where the real control
    flow should be.
17. **The batch ceiling is a named, public module constant** — no leading underscore — so the test that
    asserts the continuation fires reads the same number the loop does instead of hardcoding it a second
    time. An underscore-prefixed name says "do not read this" to the one reader that has to.
18. **A unit of work that runs for minutes reports progress, and the gap the engine will tolerate is
    declared at the call site.** Without progress reports a dead worker goes unnoticed until the whole
    close timeout elapses, and the unit can never be cancelled — so cancelling the run and shutting a
    worker down gracefully both have to cut it off mid-flight. The tolerated gap must exceed the longest
    realistic interval between reports, the first one included.
19. **Progress reporting goes through a guarded helper, never the framework call directly.** The same
    body is called from a plain loop and from its own test, where the raw call raises because there is
    no framework context — the guard is what lets the body keep one shape under every trigger. **The
    helper is one named module at the root of the service's own package** — `durable.py` in the worked
    example — and it is the one module outside the framework-wrapper package allowed to import the
    framework, which is why the architecture firewall's allow-list names it (`flat-layered` rule 9,
    `test-architecture-rule`). Where several services share one repository it is promoted to a shared
    package instead, and the exemption is the same one.
20. **A healthcheck declares no retries.** Its whole job is to turn red the moment the thing it watches
    is stale; a retry hides exactly the failure it exists to surface.
21. **Schedules are code, held in one versioned, re-runnable definition** — never created by hand in a
    console and never from inside the worker process. Each one states its catch-up window, its overlap
    policy and its time zone explicitly: the engine's defaults will replay a year of missed runs after
    an outage, stack overrunning runs, and shift the cadence twice a year with no code change.

## Hard stops

- An orchestration body is about to call an HTTP client, a write helper, or any I/O directly → stop,
  move that call into a unit of work and invoke it from the orchestration.
- A run function imports the workflow engine's SDK → stop, the framework belongs in the
  framework-wrapper package (`temporal/` in the worked example); the body must stay callable from a loop
  and a test.
- A workflow engine is being added for work that is merely *scheduled* — no run has to survive a
  restart, no retry has to outlive the process, no sequence runs for hours → stop, use shape 1; a loop,
  a cron entry or a timer is the default and the engine is not yet earned.
- Durability, cross-restart retries or multi-step orchestration is being hand-rolled inside a loop — a
  state table, a lease, an attempt counter, an at-most-once guard → stop, that is a workflow engine
  being reimplemented; adopt one.
- Retry logic is being hand-written inside a unit of work with sleeps and counters → stop, declare the
  retry policy at the call site.
- The wall clock, randomness or a random identifier is read inside replayed code → stop, take the value
  from the engine's clock or pass it in; replay diverges from history and corrupts the run.
- A continuation is taken without a value the next run needs — the cutoff, the running total → stop, the
  next run recomputes the window or under-reports the logical run, and no other test notices.
- The batch loop is a bounded loop with a trailing `return` → stop, use an unbounded loop with a
  counter; the continuation never returns and the trailing statement is dead code.
- A unit of work that runs for minutes declares a close timeout and no progress reporting → stop, add
  both; otherwise a dead worker goes unnoticed for the whole timeout and the unit can never be cancelled.
- A run-function body calls the framework's progress function directly → stop, use the guarded helper;
  the unguarded call raises the moment the body runs from a loop or a test.
- A schedule is created by hand in a console, from inside the worker process, or without an explicit
  catch-up window → stop; it belongs in the versioned definition, and the default catch-up window replays
  a year of missed runs after an outage.
- A unit of work returns a list of ids or records → stop, return an aggregate dataclass; history is not a
  data bus.
- A continuous stream is being modelled as a long-running unit of work, or one workflow per item → stop,
  keep the stream as a separate process and watch it with a liveness check.
- A service exception escapes the framework boundary untranslated → stop, wrap it so the context and the
  error type survive.
- The engine's address, namespace or queue name is being given a default → stop; the first two are
  required settings, and the third is a code constant.
