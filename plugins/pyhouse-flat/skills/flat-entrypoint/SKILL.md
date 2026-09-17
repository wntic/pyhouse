---
name: flat-entrypoint
description: Use when choosing how a flat-layered service is triggered and writing the process that triggers it — a plain loop, a cron entry or a timer, a continuous stream process, or durable execution — and deciding whether a workflow engine is earned at all; the loop is the default, and an engine is earned only by durability across process death, retries that outlive the process, or orchestration long enough that the sequence itself must survive. Owns the framework-free run function every trigger wraps, the process definition that builds its dependencies once and passes them down, the retry declared where the work is invoked, the aggregate a run returns, and the containment that keeps one failed run from killing the process. The obligations that exist only once a durable-execution engine is in play live in the sibling `DURABLE.md`. Testing any of it is `flat-test-run-function`.
when_to_use: Also when asked for a polling loop, a `__main__` entrypoint, a nightly or periodic job, a queue or websocket consumer process, a durable workflow, a batch loop, a heartbeat, a schedule or a cron expression, an overlap or catch-up policy, or whether this service needs a workflow engine at all.
---

# Flat-Layered Entrypoint — loop vs schedule vs stream vs durable

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
  runner → `flat-monorepo`. One distribution on its own needs none of it.
- **Durable execution, once it is earned** — the obligations that exist only under a workflow engine, and
  the worked code binding them → the sibling `DURABLE.md` in this skill's own directory. Read it only
  once shape 2 below is earned; nothing in this file depends on it.
- The scheduling needs are met by a loop, a cron entry or a timer — the default → nothing in `DURABLE.md`
  applies; do not add orchestration modules "for later".
- The named exceptions a wrapper translates at the framework boundary → `exception-catalog` owns the
  catalogue and the error types; `flat-layered` rule 6 owns translating a library's exceptions into it.
- Testing any of it — the run function, the loop's containment, the wrapper, the orchestration above them
  → `flat-test-run-function`.

## Picking a shape

| The work is… | Shape | Lives in |
|---|---|---|
| Anything on a schedule, as the starting assumption — a poll, a periodic pass, a nightly job | **Self-scheduling loop, or an external scheduler running the process once** | one module in the process-definition package |
| Scheduled work that must *also* survive a restart mid-run, retry across process death, or orchestrate steps over hours or days | **Durable execution** — a workflow engine, worked in `DURABLE.md` | a framework-wrapper package plus its worker process |
| A never-ending stream — a subprocess tailing an append-only upstream log, a queue consumer, a websocket feed | **Standalone stream process**, watched by an external liveness check | one module in the process-definition package |

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
parameter. `ingest/` is this example's name for one work-unit package (`flat-layered`).

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

It returns an **aggregate**, not the rows: the rows are in the datastore, and the caller wants counts. A
trigger that serializes the return value into a durable history makes this load-bearing rather than
merely tidy.

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
work and computes nothing, a wrapper class that adapts the run function into the engine's unit of work,
and a worker process that builds the dependencies once and serves the engine's queue. They are the only
modules in the service that import the engine's SDK (`flat-layered` rule 9). The run function does not
move, and none of the rules below changes.

Under a managed cloud orchestrator the orchestration definition leaves the repository and the wrapper
becomes the handler; under an in-process durable-function engine the three roles collapse into a durable
function plus its host.

**An engine adds obligations of its own** — replay determinism, continuations, progress reporting,
schedules as code — and those are not in this file, because a service on a loop can neither satisfy nor
violate them. **Read the sibling `DURABLE.md` in this skill's directory once the engine is earned**: it
states them and binds each to one worked engine under headings naming it.

## Shape 3 — a continuous stream is not a workflow

A never-ending stream stays a standalone process with its own entrypoint module, under either of the
shapes above. What it needs is not a trigger but a **liveness check**: something outside the process
reads the stream's last observation timestamp and alarms if it is too old. A container healthcheck, a
liveness probe, or a scraped freshness metric with an alert rule all do this, and a service with no
workflow engine should use one of them.

So a service can end up with two entrypoint modules:

```text
entrypoints/
├── myframework_worker.py   # process: serves the engine's queue, where one is earned
└── foo_stream.py           # process: a long-lived continuous stream, stateful
```

Do **not** park the stream inside one long-lived unit of work, and do not model each incoming item as a
workflow. A workflow per item burns the engine's action budget and adds no value; a long-lived unit of
work fights the replay model every durable-execution engine is built on, and its retries restart a
stream that was meant to resume.

## Other bindings

- **An external scheduler in place of the self-scheduling loop.** Drop the `while True` and the sleep,
  run `main()` once, and the module is a cron entry, a systemd timer or a Kubernetes `CronJob` (shape 1
  above). Wiring and failure containment are unchanged; the cadence becomes operable without a
  redeploy, and durability is still not bought.
- **A durable-execution engine in place of either.** Restate and DBOS take the durable-function shape
  in-process; Step Functions and Azure Durable Functions are the managed equivalents; Airflow, Dagster
  and Prefect solve the batch-DAG half. The wrapper package and the worker process appear, every rule
  below holds unchanged, and the run function moves in none of them. What the engine *adds* is in
  `DURABLE.md`.
- **The plain loop is not one binding among several — it is the default the engine must be earned
  against.** Nothing above licenses shape 2 without durability, cross-restart retries or long-running
  orchestration to point at.

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
   datastore.
6. **The routing name a run is addressed to has exactly one source, and every participant reads it from
   that one place.** A queue URL, a topic, a subscription name or an engine's task queue is normally a
   per-deployment value and then belongs with the rest of the process's settings (`flat-layered` rule 8);
   where the platform makes the schedule itself code in the same repository, the name is a module
   constant both the schedule and the process serving it import. What is never acceptable is two
   sources — a schedule resolving the name from one environment and the process serving it from
   another — because the disagreement surfaces as work that silently goes nowhere, with nothing to
   catch it.
7. **A continuous stream is a process, not a scheduled run.** Give it its own entrypoint module and
   watch it from outside with a liveness check on the freshness of its last observation. Never model
   each incoming item as an orchestration, and never park the stream inside one long-lived unit of
   work — its retries restart a stream that was meant to resume.
8. **The loop's failure containment is extracted into a named function.** "One failed run does not
   kill the process" is the loop's only testable contract, and a `try/except` written inline inside
   `while True` can only be reached by driving the loop — which needs an artificial escape that
   changes the thing under test.

## Hard stops

- A workflow engine is being added for work that is merely *scheduled* — no run has to survive a
  restart, no retry has to outlive the process, no sequence runs for hours → stop, use shape 1; a loop,
  a cron entry or a timer is the default and the engine is not yet earned.
- Durability, cross-restart retries or multi-step orchestration is being hand-rolled inside a loop — a
  state table, a lease, an attempt counter, an at-most-once guard → stop, that is a workflow engine
  being reimplemented; adopt one, and read `DURABLE.md` for what it then obliges.
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
