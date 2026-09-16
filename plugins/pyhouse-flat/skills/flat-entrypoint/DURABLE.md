# Durable execution — worked with Temporal

The binding for `flat-entrypoint` shape 2. Read this only once a workflow engine has been **earned** —
durability across process death, retries that outlive the process, or orchestration over hours. The
obligations these templates bind are `flat-entrypoint`'s `## Rules` 4–12 and 14–21; nothing here adds an
obligation, and every heading names the stack.

Everything below lives in the package whose declared role is *framework wrapper* — `temporal/` in
`flat-layered`'s worked example, the only package that imports `temporalio` — plus the worker process in
`entrypoints/`, plus one guarded helper named by the architecture firewall's allow-list. The run
functions in `ingest/` and `jobs/` import none of it.

## The unit-of-work wrapper — Temporal activities

`myapp/temporal/activities.py` — one class holding the service's activities, dependencies injected:

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

The activity is a **wrapper**: it calls the run function and translates the service's exceptions. It
holds no logic of its own, which is what keeps the scheduled and continuous shapes from drifting apart.

Use a class whenever the activity needs dependencies; a bare module function is only for an activity
with none. The `@activity.defn(name=...)` string is **required** — it is the stable wire name that goes
into workflow history, schedule actions and test stubs, so renaming the method must not break a running
schedule.

## The orchestration — Temporal workflows

`myapp/temporal/workflows.py` — orchestration only:

```python
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from myapp.schemas.foo import IngestResult
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

**Every activity call declares an explicit timeout and an explicit retry policy — that pair is the whole
reason the engine was earned, and an omitted one silently inherits a default nobody chose.** The ten
minutes and three attempts are this example's numbers: a timeout is set from the longest honest run of
*that* activity plus headroom, and the attempt count from how the upstream fails — a rate limit wants
several attempts with backoff, a malformed payload wants one. A timeout shorter than the work kills
healthy runs; one much longer turns a hung process into a ten-minute stall.

`with workflow.unsafe.imports_passed_through():` around the non-Temporal imports is required, not
decoration: the workflow sandbox otherwise re-imports those modules per workflow instance, which is slow
and fails outright on anything with import-time state.

## The worker process — Temporal

`myapp/entrypoints/temporal_worker.py`:

```python
import asyncio

from temporalio.client import Client
from temporalio.worker import Worker

from myapp.core.settings import get_settings
from myapp.services.foo_client import FooClient
from myapp.storage.engine import get_engine
from myapp.storage.foo_storage import FooStorage
from myapp.temporal.activities import FooActivities
from myapp.temporal.workflows import FooIngestWorkflow

TASK_QUEUE = "foo-ingest"


async def main() -> None:
    settings = get_settings()
    client = await Client.connect(
        settings.temporal_address, namespace=settings.temporal_namespace
    )
    activities = FooActivities(
        FooClient(settings.foo_api_url, settings.foo_api_timeout_seconds),
        FooStorage(get_engine(settings.database_dsn)),
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

**Connection settings carry no defaults.** The address and namespace are required fields on the settings
class, like the datastore's connection string. A default would let a deployment that forgets them connect
silently to the wrong cluster or namespace instead of failing at startup.

**Task queue names are code, not configuration.** `TASK_QUEUE` is a module constant that the schedule
definition and the architecture test both read. Making it environment-driven means a schedule and a
worker can disagree at runtime with nothing to catch it.

## Batch loops — Temporal `continue_as_new`

When one scheduled run must process more items than fit comfortably in a single activity — to limit
history size and bound the blast radius of a retry — use a workflow that calls an activity per batch and
loops:

```python
from datetime import datetime, timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from myapp.schemas.foo import RecheckResult
    from myapp.temporal.activities import FooActivities

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

## Progress reporting — the guarded helper

An activity that runs for minutes must heartbeat. Without it, a worker that dies mid-activity is only
noticed when `start_to_close_timeout` elapses — with a 30-minute timeout that is half an hour of the
workflow showing `Running` with nothing behind it. An activity that never heartbeats also cannot receive
cancellation, so cancelling the workflow and shutting a worker down gracefully both have to cut it off
mid-flight instead of letting it wind down.

Declare `heartbeat_timeout` at the call site, beside the others (as in the batch loop above), and beat
from the body's loop.

The body is **also called directly** — by its own test and by a plain loop entrypoint — so it cannot call
`activity.heartbeat()` unguarded: outside an activity context that raises. The guarded helper lives in
the service's own cross-cutting-setup package, so the body keeps one shape under both triggers:

```python
# myapp/core/durable.py
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
from myapp.core.durable import heartbeat

...
    inserted += await self._flush(batch)
    heartbeat()
```

This module is the one place outside the framework-wrapper package that may import the framework, and
the architecture firewall's allow-list names it explicitly (`flat-layered` rule 9,
`test-architecture-rule`). Where several services share one repository it is promoted to a shared
package — `packages/shared/src/shared/durable.py` — and the allow-list entry moves with it
(`flat-monorepo`).

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
    from myapp.temporal.activities import FooActivities


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

Use `maximum_attempts=1`: the point of a healthcheck is to turn red immediately when the stream is
stale. A retry hides exactly the failure it exists to surface.

## Schedule creation — Temporal schedules

Schedules are infrastructure, created from a versioned script rather than from application code — one
script defining every schedule, re-runnable to reconcile:

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
- **Schedule specs are not environment-driven.** Like task queue names, they are code — and an
  architecture test can then check that the queue each schedule targets is a queue some worker actually
  serves (`test-architecture-rule`).

## Hard stops — the Temporal spellings

`flat-entrypoint`'s hard stops bind whatever the engine. These are the same stops in this SDK's words:

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
- A healthcheck workflow declares retries → stop, the retry hides the staleness it exists to report.
- A schedule is created without `catchup_window`, by hand in the UI, or from inside the worker process →
  stop; it belongs in the versioned script with every policy stated.
- A task queue name or cron expression is read from the environment → stop, both are code; a schedule and
  a worker that disagree at runtime have nothing to catch them.
