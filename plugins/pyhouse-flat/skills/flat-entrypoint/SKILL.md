---
name: flat-entrypoint
description: Use when choosing how a flat-layered service is triggered — a plain loop, a cron entry or timer, a stream process, or durable execution — and whether a workflow engine is earned at all; the loop is the default. Owns the framework-free `run_once` and its entrypoint wrappers. Temporal batch loops, heartbeats and schedules are `flat-temporal-workflow`.
when_to_use: Also when asked for a polling loop, a `__main__` entrypoint, a nightly or periodic job, a queue or websocket consumer process, a Temporal worker, or whether this service needs a workflow engine at all.
paths: ["**/services/**", "**/ingest/**", "**/jobs/**"]
---

# Flat-Layered Entrypoint — loop vs schedule vs stream

Covers the **process-definition** and **framework-wrapper** packages of one `flat-layered` service —
`entrypoints/` and `temporal/` in that skill's worked example, whatever this service calls its own. The
shapes differ only in *what triggers a run*; the run itself always calls the same run functions, so
switching later is a wrapper change, not a rewrite.

The invariant that makes that true: **the run function is a plain async function taking its
dependencies as arguments, living in a run-function package — upstream-pull or stored-data-pass,
`ingest/` and `jobs/` in the worked example — and importing no framework.** Everything in this skill is
a wrapper around one of those.

## When to use vs. neighbours

- The architecture family is not settled yet — this may not be a flat-layered service at all →
  `architecture-choice` decides hexagonal versus flat first; everything here assumes flat.
- The service's own cross-cutting-setup, client and payload modules — `core/`, `services/`, `schemas/`
  in the worked example → not this skill, use `flat-layered`.
- The shared tables and bulk-write helpers the run function calls → `flat-schema-package`.
- The workspace this service is a member of — the `packages/*` versus `services/*` split, the Compose
  profiles, the root `Makefile` → `flat-monorepo`.
- Batch loops, `continue_as_new`, heartbeats, schedule specs, healthcheck workflows →
  `flat-temporal-workflow`. This skill stops at one activity behind one workflow.
- The scheduling needs are met by a loop, a cron entry or a timer — the default → nothing in
  `flat-temporal-workflow` applies; do not add workflow and activity modules "for later".
- The named exceptions an activity translates at the framework boundary → `exception-catalog` owns the
  catalog and the error types; this skill owns only the translation at the wrapper.
- Testing the run function, the activity body or the loop's containment → `flat-test-run-function`;
  testing a workflow's orchestration → `flat-test-temporal-workflow`.

## Picking a shape

| The work is… | Shape | Lives in |
|---|---|---|
| Anything on a schedule, as the starting assumption — a poll, a periodic pass, a nightly job | **Self-scheduling loop, or an external scheduler running the process once** | a process module, `entrypoints/<name>_loop.py` in the worked example |
| Scheduled work that must *also* survive a restart mid-run, retry across process death, or orchestrate steps over hours or days | **Durable execution** — a workflow engine, worked here with Temporal | a framework-wrapper package plus its worker process |
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

**Temporal is the binding worked end to end below; it is not the only one.** See `## Other bindings`.

Shape 3 is the exception to the choice: a continuous stream is **not** scheduled work, and neither shape
applies to it. See below.

## The run function — shared by every shape (SQLAlchemy async, structlog)

`myapp/ingest/foo_ingest.py` — an upstream-pull run function: no framework import, every dependency a
parameter. Two package roots
appear in these templates and they are different distributions: **`myapp`** is this service's own
package (`flat-layered`), **`myschema`** is the workspace's shared schema package — engine, tables,
repositories (`flat-schema-package`). A standalone service with no workspace has only `myapp`.

```python
import structlog
from sqlalchemy.ext.asyncio import AsyncEngine

from myapp.schemas import IngestResult
from myapp.services.foo_client import FooClient
from myschema.engine import bulk_upsert
from myschema.repositories.entities import EntitiesRepository
from myschema.tables.foo import foo_filtered_table, foo_raw_table

logger = structlog.get_logger()

_KIND = "foo"


async def run_once(
    client: FooClient, entities: EntitiesRepository, engine: AsyncEngine
) -> IngestResult:
    raw_rows = await client.fetch_batch()
    async with engine.begin() as conn:
        await bulk_upsert(
            conn, foo_raw_table, raw_rows,
            conflict_columns=["external_id"], update_columns=["raw"],
        )

    filtered_rows = [row for row in (filter_one(r) for r in raw_rows) if row is not None]
    await entities.record_batch(foo_filtered_table, _KIND, filtered_rows)

    logger.info("foo_ingest_completed", fetched=len(raw_rows), kept=len(filtered_rows))
    return IngestResult(fetched=len(raw_rows), kept=len(filtered_rows))
```

`run_once` takes the client, the repository and the engine as **parameters**. A body that reaches for a
module-level engine or a settings singleton cannot be pointed at a test container, and a test of it
proves nothing.

It returns an **aggregate**, not the rows. That matters most under a workflow engine, where the return
value is serialized into durable history, but it is the right shape everywhere: the rows are in the database,
and the caller wants counts.

## Shape 1 — the self-scheduling loop, on asyncio (the default)

`myapp/entrypoints/foo_loop.py`:

```python
import asyncio
from collections.abc import Awaitable, Callable

import structlog

from myapp.core.settings import get_settings
from myapp.ingest.foo_ingest import run_once
from myapp.services.foo_client import FooClient
from myschema.engine import get_engine
from myschema.repositories.entities import EntitiesRepository

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
    engine = get_engine()
    client = FooClient(settings.foo_api_url, settings.foo_api_timeout_seconds)
    entities = EntitiesRepository(engine)

    while True:
        await guarded(lambda: run_once(client, entities, engine))
        await asyncio.sleep(_POLL_INTERVAL_SECONDS)


if __name__ == "__main__":
    asyncio.run(main())
```

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

## Shape 2 — durable execution, bound to Temporal

Reach here only once durability, cross-restart retries or long-running orchestration has earned it. The
binding worked below is Temporal; the shape is three modules — a workflow, an activity that wraps the
run function, and a worker process — and they are the only ones in the service that import the engine's
SDK. Under Restate or DBOS the same three roles collapse into a durable function plus its host; under a
managed cloud orchestrator the workflow moves out of the repository and the activity becomes the
handler. The run function does not move in any of them.

`myapp/temporal/activities.py` — one class holding the service's activities, dependencies injected:

```python
from sqlalchemy.ext.asyncio import AsyncEngine
from temporalio import activity
from temporalio.exceptions import ApplicationError

from myapp.exceptions import MyappError
from myapp.ingest.foo_ingest import run_once
from myapp.schemas import IngestResult
from myapp.services.foo_client import FooClient
from myschema.repositories.entities import EntitiesRepository


class FooActivities:
    def __init__(
        self, client: FooClient, entities: EntitiesRepository, engine: AsyncEngine
    ) -> None:
        self._client = client
        self._entities = entities
        self._engine = engine

    @activity.defn(name="run_foo_ingest")
    async def run_foo_ingest(self) -> IngestResult:
        try:
            return await run_once(self._client, self._entities, self._engine)
        except MyappError as exc:
            raise ApplicationError(
                str(exc), exc.context, type=type(exc).__name__
            ) from exc
```

The activity is a **wrapper**: it calls `run_once` and translates the service's exceptions. It holds no
logic of its own, which is what keeps the scheduled and continuous shapes from drifting apart.

Use a class whenever the activity needs dependencies; a bare module function is only for an activity
with none. The `@activity.defn(name=...)` string is **required** — it is the stable name that goes into
workflow history, schedule actions, and test stubs, so renaming the method must not break a running
schedule.

`myapp/temporal/workflows.py` — orchestration only:

```python
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from myapp.schemas import IngestResult
    from myapp.temporal.activities import FooActivities


@workflow.defn
class FooIngestWorkflow:
    @workflow.run
    async def run(self) -> IngestResult:
        return await workflow.execute_activity(
            FooActivities.run_foo_ingest,
            start_to_close_timeout=timedelta(minutes=10),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
```

**Every activity call declares an explicit timeout and an explicit retry policy — that pair is the
whole reason the engine was earned, and an omitted one silently inherits a default nobody chose.** The
ten minutes and three attempts above are this example's numbers: a timeout is set from the longest
honest run of *that* activity plus headroom, and the attempt count from how the upstream fails — a rate
limit wants several attempts with backoff, a malformed payload wants one. A timeout shorter than the
work kills healthy runs; one much longer than the work turns a hung process into a ten-minute stall.

`with workflow.unsafe.imports_passed_through():` around the non-Temporal imports is required, not
decoration: the workflow sandbox otherwise re-imports those modules per workflow instance, which is
slow and fails outright on anything with import-time state.

`myapp/entrypoints/temporal_worker.py` — the process:

```python
import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from myapp.core.settings import get_settings
from myapp.services.foo_client import FooClient
from myapp.temporal.activities import FooActivities
from myapp.temporal.workflows import FooIngestWorkflow
from myschema.engine import get_engine
from myschema.repositories.entities import EntitiesRepository

TASK_QUEUE = "foo-parser"


async def main() -> None:
    settings = get_settings()
    engine = get_engine()
    client = await Client.connect(
        settings.temporal_address, namespace=settings.temporal_namespace
    )
    activities = FooActivities(
        FooClient(settings.foo_api_url, settings.foo_api_timeout_seconds),
        EntitiesRepository(engine),
        engine,
    )
    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[FooIngestWorkflow],
        activities=[activities.run_foo_ingest],
    )
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
```

**Connection settings carry no defaults.** The Temporal address and namespace are required fields on
the settings class, like the database DSN. A default would let a deployment that forgets them connect
silently to the wrong cluster or namespace instead of failing at startup.

**Task queue names are code, not configuration.** `TASK_QUEUE` is a module constant that the schedule
script and the architecture test both read. Making it environment-driven means a schedule and a worker
can disagree at runtime with nothing to catch it.

## Shape 3 — a continuous stream is not a workflow

A never-ending stream stays a standalone process with its own entrypoint module, under either of the
shapes above. What it needs is not a trigger but a **liveness check**: something outside the process
reads the stream's last observation timestamp and alarms if it is too old. A container healthcheck, a
liveness probe, or a scraped freshness metric with an alert rule all do this, and a service with no
workflow engine should use one of them. Where the engine is already present for other work, a short
**healthcheck workflow** on a schedule is the same check with the same retry and visibility machinery as
everything else (`flat-temporal-workflow`).

So a service can end up with two entrypoint modules:

```text
entrypoints/
├── temporal_worker.py      # registers workflows/activities, serves the task queue
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
  change — under a managed orchestrator the workflow definition leaves the repository and the activity
  becomes the handler. Every rule below holds unchanged, and the run function moves in none of them.
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
3. **A run function takes its dependencies as parameters** — client, repository, engine. Never a
   module-level engine, never a settings singleton read from inside the body: a body that reaches for a
   global cannot be pointed at a test container, so a test of it proves nothing.
4. **Orchestration orchestrates; it does not compute.** Under a durable-execution engine the
   orchestration body is replayed from history, so any parsing, filtering, I/O or database access in it
   produces a different answer on replay and corrupts the run. It invokes units of work and does
   nothing else — `@workflow.run` calling only `execute_activity` under Temporal.
5. **Retry and backoff are declared where the unit of work is invoked, never hand-rolled inside it.**
   Under an engine that is a retry policy on the call (`RetryPolicy` under Temporal); under the plain
   loop it is the guard wrapping one run. A unit of work that sleeps and counts its own attempts has
   two retry policies and the outer one no longer bounds it.
6. **The routing name a worker serves is one module constant per service** — `TASK_QUEUE` under
   Temporal. Never shared with a sibling service, and never read from the environment: a schedule and a
   worker that resolve it from separate environments can disagree at runtime with nothing to catch
   them.
7. **A wrapper that needs dependencies takes them through its constructor**; a bare function is only
   for a wrapper with none. The process definition builds them once and hands them in — a wrapper that
   reaches for a module-level engine puts the service's wiring back into global state, out of the
   process definition's reach and out of a test's.
8. **The wire name of a unit of work is declared explicitly, separately from the symbol implementing
   it** — `@activity.defn(name="...")` under Temporal. Schedules, execution history and test stubs all
   bind to the wire name, so renaming the method must not be able to break a running schedule.
9. **The service's exceptions are translated at the framework boundary**, carrying the message, the
   identifying context and the original type across it — `ApplicationError` under Temporal. An
   untranslated exception reaches the history as an opaque framework failure with the context stripped,
   and the operator reading that history is the person who needed it.
10. **Return aggregates, not lists of items.** Run functions return frozen dataclasses of counters or
    timestamps, so payload and history size stay bounded; the items themselves live in the database.
11. **An orchestration module keeps its non-engine imports out of the engine's sandbox.** An engine
    that re-imports modules per run is slow on anything heavy and fails outright on anything with
    import-time state — under Temporal that is `workflow.unsafe.imports_passed_through()` around every
    non-`temporalio` import in a workflow module.
12. **A continuous stream is a process, not a scheduled run.** Give it its own entrypoint module and
    watch it from outside with a liveness check on the freshness of its last observation. Never model
    each incoming item as an orchestration, and never park the stream inside one long-lived unit of
    work — its retries restart a stream that was meant to resume.
13. **The loop's failure containment is extracted into a named function.** "One failed run does not
    kill the process" is the loop's only testable contract, and a `try/except` written inline inside
    `while True` can only be reached by driving the loop — which needs an artificial escape that
    changes the thing under test.

## Hard stops

- A workflow function is about to call an HTTP client, a bulk-write helper, or any I/O directly → stop,
  move that call into an `@activity.defn` and reach it via `workflow.execute_activity`.
- A run function imports the workflow engine's SDK → stop, the framework belongs in the
  framework-wrapper package (`temporal/` in the worked example); the body must stay callable from a loop
  and a test.
- A workflow engine is being added for work that is merely *scheduled* — no run has to survive a
  restart, no retry has to outlive the process, no sequence runs for hours → stop, use shape 1; a loop,
  a cron entry or a timer is the default and the engine is not yet earned.
- Durability, cross-restart retries or multi-step orchestration is being hand-rolled inside a loop — a
  state table, a lease, an attempt counter, an at-most-once guard → stop, that is a workflow engine
  being reimplemented; adopt one.
- Retry logic is being hand-written inside an activity with sleeps and counters → stop, use
  `RetryPolicy` at the call site.
- `datetime.now()`, `random`, `uuid4()` or any non-deterministic call inside `@workflow.run` → stop,
  use `workflow.now()` and pass deterministic values as arguments.
- An activity returns a list of ids or records → stop, return an aggregate dataclass; history is not a
  data bus.
- A continuous stream is being modelled as a long-running activity or one workflow per item → stop,
  keep the stream as a separate process and add a healthcheck workflow.
- A service exception escapes an activity untranslated → stop, wrap it in `ApplicationError` so the
  context and error type survive.
- The Temporal address, namespace or task queue is being given a default → stop; the first two are
  required settings, and the third is a code constant.
