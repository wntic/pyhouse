# Durable execution — the obligations, and one binding (Temporal)

`flat-entrypoint` shape 2. Read this only once a workflow engine has been **earned** — durability across
process death, retries that outlive the process, or orchestration over hours.

This file is self-contained and additive. `flat-entrypoint`'s own rules describe a service whatever
triggers it, and hold here unchanged; the obligations below **exist only once an engine is in play**, so
a service on a loop, a cron entry or a timer can neither satisfy nor violate them. Every heading beneath
them names the stack that binds them.

Everything templated here lives in the package whose declared role is *framework wrapper*
(`flat-layered`), plus the worker process in the process-definition package, plus one guarded helper
module named by the architecture firewall's allow-list. The run functions import none of it.

## Obligations under a durable-execution engine

1. **Orchestration orchestrates; it does not compute.** The orchestration body is replayed from
   history, so any parsing, filtering, I/O or datastore access in it produces a different answer on
   replay and corrupts the run. It invokes units of work and does nothing else.
2. **Inside replayed code the engine's clock is the only clock.** Reading the wall clock, drawing
   randomness, or minting a random identifier makes replay diverge from the recorded history. Take the
   value from the engine, or pass it in as an argument.
3. **An orchestration module keeps its non-engine imports out of the engine's sandbox.** An engine
   that re-imports modules per run is slow on anything heavy and fails outright on anything with
   import-time state.
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
   result under-reports the logical run. Two or more values go through the engine's argument-list form,
   because the single-positional form fails *inside* the run, which retries the failure forever instead
   of surfacing it.
7. **The batch loop ends on an empty batch and returns the summed aggregate**, and it is written as an
   unbounded loop with an explicit counter, never a bounded loop with a trailing `return`. A
   continuation never returns, so that trailing statement is dead code standing where the real control
   flow should be.
8. **The batch ceiling is a named, public module constant** — no leading underscore — so the test that
   asserts the continuation fires reads the same number the loop does instead of hardcoding it a second
   time. An underscore-prefixed name says "do not read this" to the one reader that has to.
9. **A unit of work that runs for minutes reports progress, and the gap the engine will tolerate is
   declared at the call site.** Without progress reports a dead worker goes unnoticed until the whole
   close timeout elapses, and the unit can never be cancelled — so cancelling the run and shutting a
   worker down gracefully both have to cut it off mid-flight. The tolerated gap must exceed the longest
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
    (`flat-entrypoint` rule 7) gets the engine's retry and visibility machinery.
12. **Schedules are code, held in one versioned, re-runnable definition** — never created by hand in a
    console and never from inside the worker process. Each one states its catch-up window, its overlap
    policy and its time zone explicitly: the engine's defaults will replay a year of missed runs after
    an outage, stack overrunning runs, and shift the cadence twice a year with no code change.

## The unit-of-work wrapper — Temporal activities

`myapp/myframework/activities.py` — one class holding the service's activities, dependencies injected.
`myframework/` is this example's name for the framework-wrapper package (`flat-layered`), and
`temporalio` is the framework it wraps:

```python
from temporalio import activity
from temporalio.exceptions import ApplicationError

from myapp.exceptions import MyappError
from myapp.ingest.foo_ingest import run_once
from myapp.schemas.foo import IngestResult
from myapp.services.foo_client import FooClient
from myapp.storage.foo_storage import FooStorage


class FooActivities:
    def __init__(self, client: FooClient, storage: FooStorage) -> None:
        self._client = client
        self._storage = storage

    @activity.defn(name="run_foo_ingest")
    async def run_foo_ingest(self) -> IngestResult:
        try:
            return await run_once(self._client, self._storage)
        except MyappError as exc:
            raise ApplicationError(str(exc), exc.context, type=type(exc).__name__) from exc
```

The activity is a **wrapper**: it calls the run function and translates the service's exceptions
(obligation 5). It holds no logic of its own, which is what keeps the scheduled and continuous shapes
from drifting apart.

Use a class whenever the activity needs dependencies; a bare module function is only for an activity
with none. The `@activity.defn(name=...)` string is **required** — it is obligation 4's wire name, the
one that goes into workflow history, schedule actions and test stubs, so renaming the method must not
break a running schedule.

## The orchestration — Temporal workflows

`myapp/myframework/workflows.py` — orchestration only:

```python
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from myapp.schemas.foo import IngestResult
    from myapp.myframework.activities import FooActivities


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

**Every activity call declares an explicit timeout and an explicit retry policy — that pair is the whole
reason the engine was earned, and an omitted one silently inherits a default nobody chose.** The ten
minutes and three attempts are this example's numbers: a timeout is set from the longest honest run of
*that* activity plus headroom, and the attempt count from how the upstream fails — a rate limit wants
several attempts with backoff, a malformed payload wants one. A timeout shorter than the work kills
healthy runs; one much longer turns a hung process into a ten-minute stall.

`with workflow.unsafe.imports_passed_through():` around the non-Temporal imports is this SDK's spelling
of obligation 3, and it is required rather than decoration: the workflow sandbox otherwise re-imports
those modules per workflow instance, which is slow and fails outright on anything with import-time state.

## The worker process — Temporal

`myapp/entrypoints/myframework_worker.py`:

```python
import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from myapp.myframework.activities import FooActivities
from myapp.myframework.workflows import FooIngestWorkflow
from myapp.services.foo_client import FooClient
from myapp.settings import get_settings
from myapp.storage.engine import get_engine
from myapp.storage.foo_storage import FooStorage
from myapp.storage.settings import get_storage_settings

TASK_QUEUE = "foo-ingest"


async def main() -> None:
    settings = get_settings()
    client = await Client.connect(
        settings.temporal_address, namespace=settings.temporal_namespace
    )
    activities = FooActivities(
        FooClient(settings.foo_api_url, settings.foo_api_timeout_seconds),
        FooStorage(get_engine(get_storage_settings().dsn)),
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

**Connection settings carry no defaults.** The address and namespace are required fields on the process's
own settings class, like the connection string on the storage package's. A default would let a deployment
that forgets them connect silently to the wrong cluster or namespace instead of failing at startup.

**Under this engine the task queue is the single source `flat-entrypoint` rule 6 requires, and it is
code.** The schedule definition below and the architecture test both read `TASK_QUEUE` from this module.
That holds because the schedule is code in the same repository; a broker addressed by a per-deployment
URL keeps its name in settings instead, and the rule is satisfied either way as long as there is one
source.

## Batch loops — Temporal `continue_as_new`

When one scheduled run must process more items than fit comfortably in a single activity — to limit
history size and bound the blast radius of a retry — use a workflow that calls an activity per batch and
loops (obligations 6, 7 and 8):

```python
from datetime import datetime, timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from myapp.schemas.foo import RecheckResult
    from myapp.myframework.activities import FooActivities

MAX_BATCHES_PER_RUN = 100


@workflow.defn
class FooRecheckWorkflow:
    @workflow.run
    async def run(
        self,
        run_start: datetime | None = None,
        carried: RecheckResult | None = None,
    ) -> RecheckResult:
        cutoff = run_start if run_start is not None else workflow.now()
        total = carried if carried is not None else RecheckResult(processed=0, matched=0)
        batches = 0
        while True:
            batch = await workflow.execute_activity(
                FooActivities.recheck_batch,
                cutoff,
                start_to_close_timeout=timedelta(minutes=30),
                heartbeat_timeout=timedelta(minutes=1),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )
            if batch.processed == 0:
                return total
            total = total + batch
            batches += 1
            if batches >= MAX_BATCHES_PER_RUN:
                workflow.continue_as_new(args=[cutoff, total])
```

Every line of that control flow is load-bearing:

- **`workflow.now()`, not `datetime.now()`.** The latter is non-deterministic and breaks replay.
- **Pass `cutoff` into `continue_as_new`.** Otherwise the next run computes a fresh `workflow.now()` and
  re-processes part of the same logical window.
- **Carry the running total too.** `continue_as_new` starts a fresh run with fresh defaults, so a total
  left behind is lost and the final result under-reports the logical run.
- **Two or more arguments go through `args=[...]`.** `workflow.continue_as_new()` takes at most one
  positional argument; `continue_as_new(cutoff, total)` raises `TypeError` *inside* the workflow, which
  fails the workflow task and retries it forever — the run hangs rather than erroring out.
- **`while True` with an explicit counter, not `for … in range(...)`.** `continue_as_new` never returns,
  so a trailing `return` after the loop is dead code hiding the real control flow — and a `for` loop
  needs one to satisfy the linter.
- **An empty batch is the termination signal.** The activity returns an aggregate with `processed == 0`;
  the workflow sums the aggregates and returns.
- **One activity per batch, never one activity per item.** A workflow per item, or an activity per item,
  is exactly the shape this avoids.

The aggregate has to be addable, which is one `__add__` on the result dataclass:

```python
from dataclasses import dataclass


@dataclass(frozen=True)
class RecheckResult:
    processed: int
    matched: int

    def __add__(self, other: "RecheckResult") -> "RecheckResult":
        return RecheckResult(
            processed=self.processed + other.processed,
            matched=self.matched + other.matched,
        )
```

## Progress reporting — the guarded helper, on Temporal heartbeats

An activity that runs for minutes must heartbeat (obligation 9). Without it, a worker that dies
mid-activity is only noticed when `start_to_close_timeout` elapses — with a 30-minute timeout that is
half an hour of the workflow showing `Running` with nothing behind it. An activity that never heartbeats
also cannot receive cancellation, so cancelling the workflow and shutting a worker down gracefully both
have to cut it off mid-flight instead of letting it wind down.

Declare `heartbeat_timeout` at the call site, beside the others (as in the batch loop above), and beat
from the body's loop.

The body is **also called directly** — by its own test and by a plain loop entrypoint — so it cannot call
`activity.heartbeat()` unguarded: outside an activity context that raises. Obligation 10's helper lives
in one named module at the root of the distribution's own package, so the body keeps one shape under
both triggers:

```python
# myapp/durable.py
from temporalio import activity


def heartbeat(*details: object) -> None:
    """Beat if running inside an activity; a no-op when the body is called directly."""
    try:
        activity.heartbeat(*details)
    except RuntimeError:
        pass  # not in an activity context — the body is being run from a loop or a test
```

Then, in the run function:

```python
from myapp.durable import heartbeat

...
    inserted += await self._flush(batch)
    heartbeat()
```

This module is the one place outside the framework-wrapper package that may import the framework, and
the architecture firewall's allow-list names it explicitly (`flat-layered` rule 9,
`test-architecture-rule`). Where several distributions share one repository it is promoted to a library
they both depend on — `myschema`-style, owned by neither — and the allow-list entry moves with it.

- **Beat once per unit of progress**, not per item in a hot loop — a batch flush, a completed check. The
  SDK throttles beats, so an occasional extra one is free, but the call itself is not.
- **`heartbeat_timeout` must exceed the longest realistic gap between beats**, including the first one. A
  batch that takes two minutes to assemble needs more than a two-minute timeout, or a healthy run is
  killed and retried.
- **Skip it for a single-statement activity.** An expiry `UPDATE` or a freshness `SELECT` has no progress
  to report; `start_to_close_timeout` alone is the right bound.
- **Carry no details unless a retry actually resumes from them.** Batch loops here resume from a stored
  cursor or watermark, so heartbeat details would be state nobody reads.

## Healthcheck workflow for a continuous stream — Temporal

A continuous stream cannot be a workflow (`flat-entrypoint` shape 3), but its health should be visible.
Use a short workflow calling one activity that checks the freshness of the stream's last observation:

```python
from datetime import datetime, timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from myapp.schemas.foo import StreamHealthcheckParams
    from myapp.myframework.activities import FooActivities


@workflow.defn
class FooStreamHealthcheckWorkflow:
    @workflow.run
    async def run(self, params: StreamHealthcheckParams) -> datetime:
        return await workflow.execute_activity(
            FooActivities.check_stream_freshness,
            params,
            start_to_close_timeout=timedelta(minutes=5),
            retry_policy=RetryPolicy(maximum_attempts=1),
        )
```

`maximum_attempts=1` is obligation 11 in this SDK: the point of a healthcheck is to turn red immediately
when the stream is stale, and a retry hides exactly the failure it exists to surface.

## Schedule creation — Temporal schedules

Obligation 12 in this SDK: schedules are infrastructure, created from a versioned script rather than from
application code — one script defining every schedule, re-runnable to reconcile:

```python
# scripts/temporal_schedules.py
from datetime import timedelta

from temporalio.client import (
    Client,
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleOverlapPolicy,
    SchedulePolicy,
    ScheduleSpec,
)

client = await Client.connect(address, namespace=namespace)
await client.create_schedule(
    "foo-ingest",
    Schedule(
        action=ScheduleActionStartWorkflow(
            "FooIngestWorkflow",
            id="foo-ingest-run",
            task_queue="foo-ingest",
        ),
        spec=ScheduleSpec(
            cron_expressions=["*/5 * * * *"],
            time_zone_name="UTC",
        ),
        policy=SchedulePolicy(
            overlap=ScheduleOverlapPolicy.SKIP,
            catchup_window=timedelta(minutes=10),
        ),
    ),
)
```

- **Workflow names are passed as strings**, so the script imports no service package and can run from a
  bare environment.
- **`catchup_window` must be explicit.** The default is one year; after a long outage a missed year of
  backfills is almost never what you want.
- **`overlap=SKIP`** is the equivalent of "at most one instance at a time", and the right default for a
  poll: a run that overruns its interval should skip the next tick, not stack.
- **`time_zone_name` is set explicitly**, and `UTC` unless the schedule genuinely tracks a local business
  day. A schedule that inherits an ambient zone shifts twice a year without a code change.
- **Schedules live in the script, not in the UI.** The script is what restores every schedule after a
  cluster is rebuilt from scratch, and it is the only place a reviewer can see the cadence.
- **The queue a schedule targets is read from the same source the worker reads.** An architecture test
  can then check that every schedule targets a queue some worker actually serves
  (`test-architecture-rule`).

## Hard stops — under any durable-execution engine

- An orchestration body is about to call an HTTP client, a write helper, or any I/O directly → stop,
  move that call into a unit of work and invoke it from the orchestration.
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
- A healthcheck run declares retries → stop, the retry hides the staleness it exists to report.
- A service exception escapes the framework boundary untranslated → stop, wrap it so the context and the
  error type survive.
- The engine's address or namespace is being given a default → stop, both are required settings; a
  deployment that forgets one must fail at startup rather than reach the wrong cluster.

## Hard stops — the Temporal spellings

The same stops in this SDK's words:

- `continue_as_new` is called with two positional arguments → stop, use `args=[...]`; the `TypeError`
  happens inside the workflow and retries forever instead of failing.
- `continue_as_new` is called without the cutoff, or without the running total → stop; the next run
  recomputes `workflow.now()` and re-processes the window, or the result under-reports the logical run.
- The batch loop is a `for … in range(...)` with a trailing `return` → stop, use `while True` with a
  counter.
- A multi-minute activity declares `start_to_close_timeout` and no `heartbeat_timeout` → stop, add both.
- A body calls `activity.heartbeat()` directly → stop, use the guarded helper.
- `datetime.now()`, `random` or `uuid4()` appears inside `@workflow.run` → stop, use `workflow.now()` and
  pass deterministic values as arguments.
- A non-`temporalio` import in a workflow module sits outside
  `workflow.unsafe.imports_passed_through()` → stop, the sandbox re-imports it per workflow instance.
- A schedule is created without `catchup_window`, by hand in the UI, or from inside the worker process →
  stop; it belongs in the versioned script with every policy stated.
- A task queue name or cron expression is read from the environment while the schedule is code here →
  stop, both are code; a schedule and a worker that disagree at runtime have nothing to catch them.
