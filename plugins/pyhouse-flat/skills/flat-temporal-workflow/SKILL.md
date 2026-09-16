---
name: flat-temporal-workflow
description: Use when a flat-layered service has already earned a workflow engine — `flat-entrypoint` decides that — and one activity per run is no longer enough. Owns the Temporal batch loop with `continue_as_new` carrying its cutoff and running total, guarded heartbeats, stream healthcheck workflows and schedule specs; not the trigger choice itself.
when_to_use: Also when asked about `continue_as_new`, `activity.heartbeat`, a Temporal schedule or cron expression, an overlap or catch-up policy, or a workflow that processes more batches than fit in one run.
paths: ["**/services/**", "**/jobs/**", "**/workflows/**"]
---

# Flat-Layered Temporal Workflow — batch loops, heartbeats, schedules

The shapes a `flat-layered` service reaches for once one activity per run stops being enough — and only
once a workflow engine has been earned at all, which `flat-entrypoint` decides. All of them live in the
package whose declared role is *framework wrapper* — `temporal/` in `flat-layered`'s worked example, the
only package that imports `temporalio` — and all of them wrap run functions from the upstream-pull and
stored-data-pass packages (`ingest/`, `jobs/`) that know nothing about Temporal.

## When to use vs. neighbours

- Choosing between a loop, a schedule and a stream — and whether a workflow engine is warranted at all;
  the single workflow-plus-activity shape; the worker process → `flat-entrypoint`. **Read it first**:
  this skill assumes its shapes and assumes the engine has already been earned there.
- The service's architecture family is not settled — it may not be flat-layered at all →
  `architecture-choice` settles that before any of this applies.
- The run function the activity calls → `flat-layered`, and the write path is
  `flat-schema-package`.
- One scheduled run comfortably fits in one activity → none of this applies; stay on `flat-entrypoint`'s
  default — a plain loop, a cron entry or a timer, with one activity at most behind one workflow.
- The workspace package holding the guarded `heartbeat` helper, and the root around it →
  `flat-monorepo`.
- The service exceptions an activity translates into `ApplicationError`, and the catalog they come from
  → `exception-catalog`.
- The static check that every schedule targets a queue some worker actually serves →
  `test-architecture-rule`.
- Testing orchestration without real sleeps → `flat-test-temporal-workflow`; the activity body and the
  run function behind it → `flat-test-run-function`.

## Batch-loop workflows — Temporal

When one scheduled run must process more items than fit comfortably in a single activity — to limit
history size and bound the blast radius of a retry — use a workflow that calls an activity per batch
and loops:

```python
from datetime import datetime, timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from myapp.schemas import RecheckResult
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
- **Pass `cutoff` into `continue_as_new`.** Otherwise the next run computes a fresh `workflow.now()`
  and re-processes part of the same logical window.
- **Carry the running total too.** `continue_as_new` starts a fresh run with fresh defaults, so a
  total left behind is lost and the final result under-reports the logical run.
- **Two or more arguments go through `args=[...]`.** `workflow.continue_as_new()` takes at most one
  positional argument; `continue_as_new(cutoff, total)` raises `TypeError` *inside* the workflow,
  which fails the workflow task and retries it forever — the run hangs rather than erroring out.
- **`while True` with an explicit counter, not `for … in range(...)`.** The loop must not fall through
  its end: `continue_as_new` never returns, so a trailing `return` after the loop is dead code that
  hides the real control flow — and a `for` loop needs one to satisfy the linter.
- **An empty batch is the termination signal.** The activity returns an aggregate with
  `processed == 0`; the workflow sums the aggregates and returns.
- **One activity per batch, never one activity per item.** A workflow per item, or an activity per
  item, is exactly the shape this avoids.

The aggregate needs to be addable, which is one `__add__` on the result dataclass:

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

## Heartbeats on long activities — Temporal

An activity that runs for minutes must heartbeat. Without it, a worker that dies mid-activity is only
noticed when `start_to_close_timeout` elapses — with a 30-minute timeout that is half an hour of the
workflow showing `Running` with nothing behind it. An activity that never heartbeats also cannot
receive cancellation, so cancelling the workflow and shutting a worker down gracefully both have to cut
it off mid-flight instead of letting it wind down.

Declare the timeout at the call site, beside the others (as in the batch loop above), and beat from the
body's loop.

The body is **also called directly** — by its own test and by a plain loop entrypoint — so it cannot
call `activity.heartbeat()` unguarded: outside an activity context that raises. Put a guarded helper in
the workspace's shared package, so the body keeps one shape for both triggers:

```python
# packages/shared/src/shared/temporal.py
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
from shared.temporal import heartbeat

...
    inserted += await self._flush(batch)
    heartbeat()
```

Rules:

- **Beat once per unit of progress**, not per item in a hot loop — a batch flush, a completed check.
  The SDK throttles beats, so an occasional extra one is free, but the call itself is not.
- **`heartbeat_timeout` must exceed the longest realistic gap between beats**, including the first one.
  A batch that takes two minutes to assemble needs more than a two-minute timeout, or a healthy run is
  killed and retried.
- **Skip it for a single-statement activity.** An expiry `UPDATE` or a freshness `SELECT` has no
  progress to report; `start_to_close_timeout` alone is the right bound.
- **Carry no details unless a retry actually resumes from them.** Batch loops here resume from a
  database cursor or watermark, so heartbeat details would be state nobody reads.

## Healthcheck workflow for a continuous stream — Temporal

A continuous stream cannot be a workflow (`flat-entrypoint`), but its health should be
visible. Use a short workflow calling one activity that checks the freshness of the stream's last
observation:

```python
from datetime import datetime, timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from myapp.schemas import StreamHealthcheckParams
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
script defining every schedule in the workspace, re-runnable to reconcile:

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
            task_queue="foo-parser",
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

- **Workflow names are passed as strings**, so the script does not import any service package and can
  run from a bare environment.
- **`catchup_window` must be explicit.** The default is one year; after a long outage a missed year of
  backfills is almost never what you want.
- **`overlap=SKIP`** is the equivalent of "at most one instance at a time", and the right default for a
  poll: a run that overruns its interval should skip the next tick, not stack.
- **`time_zone_name` is set explicitly**, and `UTC` unless the schedule genuinely tracks a local
  business day. A schedule that inherits an ambient zone shifts twice a year without a code change.
- **Schedules live in the script, not in the UI.** The script is what restores every schedule after a
  cluster is rebuilt from scratch, and it is the only place a reviewer can see the cadence.
- **Schedule specs are not environment-driven.** Like task queue names, they are code — and an
  architecture test can then check that the queue each schedule targets is a queue some worker
  actually serves.

## Other bindings

- **Another durable-execution engine in place of Temporal.** Restate, DBOS, Step Functions and Azure
  Durable Functions all rebuild a run from a recorded history, so every rule below holds unchanged:
  the continuation still carries its cutoff and its running total, the orchestration still performs no
  I/O, the clock still comes from the engine, a long unit of work still reports progress. What changes
  is spelling — the continuation may be an ordinary tail call rather than a named primitive, the
  schedule a cloud resource in infrastructure code rather than a script. A batch-DAG scheduler
  (Airflow, Dagster, Prefect) keeps the batch-loop and aggregate rules and replaces the continuation
  with a task that re-queues itself.
- **A plain loop, cron entry or timer is not an alternative binding here — it is the default this
  skill's shapes had to be earned against** (`flat-entrypoint`). A service that arrives here with no
  durability, cross-restart retry or long-running orchestration requirement to point at has adopted
  infrastructure it does not need; go back and use the loop.

## Rules

1. **Orchestration orchestrates; it does not compute.** No I/O, no parsing, no database access in the
   replayed body — `@workflow.run` under Temporal. Replayed code that touches the outside world
   produces a different answer the second time and corrupts the run it was meant to make durable.
2. **Inside replayed code the engine's clock is the only clock.** Reading the wall clock, drawing
   randomness, or minting a random identifier makes replay diverge from the recorded history. Take the
   value from the engine (`workflow.now()`) or pass it in as an argument.
3. **A continuation carries every value the next run needs** — the cutoff *and* the running total. A
   continuation starts a fresh run with fresh defaults, so a cutoff left behind means the next run
   recomputes it and reprocesses part of the same window, and a total left behind means the final
   result under-reports the logical run. Two or more values go through the engine's argument-list form
   (`args=[...]` under Temporal), because the single-positional form fails *inside* the run, which
   retries the failure forever instead of surfacing it.
4. **The batch loop ends on an empty batch and returns the summed aggregate**, and it is written as an
   unbounded loop with an explicit counter, never a bounded `for` with a trailing `return`. A
   continuation never returns, so that trailing statement is dead code standing where the real control
   flow should be.
5. **The batch ceiling is a named, public module constant** — no leading underscore — so the test that
   asserts the continuation fires reads the same number the loop does instead of hardcoding it a second
   time. An underscore-prefixed name says "do not read this" to the one reader that has to.
6. **A unit of work that runs for minutes reports progress, and the gap the engine will tolerate is
   declared at the call site.** Without progress reports a dead worker goes unnoticed until the whole
   close timeout elapses, and the unit can never be cancelled — so cancelling the run and shutting a
   worker down gracefully both have to cut it off mid-flight. The tolerated gap must exceed the longest
   realistic interval between reports, the first one included.
7. **Progress reporting goes through a guarded helper, never the framework call directly.** The same
   body is called from a plain loop and from its own test, where the raw call raises because there is
   no framework context — the guard is what lets the body keep one shape under every trigger.
8. **A healthcheck declares no retries.** Its whole job is to turn red the moment the thing it watches
   is stale; a retry hides exactly the failure it exists to surface.
9. **Schedules are code, held in one versioned, re-runnable definition** — never created by hand in a
   console and never from inside the worker process. Each one states its catch-up window, its overlap
   policy and its time zone explicitly: the engine's defaults will replay a year of missed runs after
   an outage, stack overrunning runs, and shift the cadence twice a year with no code change.
10. **Aggregates, not lists.** Every value returned across the framework boundary is a frozen dataclass
    of counters or timestamps; the records themselves live in the database, and execution history is
    not a data bus.

## Hard stops

- `continue_as_new` is called with two positional arguments → stop, use `args=[...]`; the `TypeError`
  happens inside the workflow and retries forever instead of failing.
- The batch loop is a `for … in range(...)` with a trailing `return` → stop, use `while True` with a
  counter; `continue_as_new` never returns and the trailing statement is dead code.
- `continue_as_new` is called without the cutoff → stop, the next run recomputes `workflow.now()` and
  re-processes the same window.
- `continue_as_new` is called without the running total → stop, the result under-reports the logical
  run.
- A multi-minute activity declares `start_to_close_timeout` and no `heartbeat_timeout` → stop, add
  both; otherwise a dead worker goes unnoticed for the whole timeout and the activity can never be
  cancelled.
- A body calls `activity.heartbeat()` directly → stop, use the shared guarded helper; the unguarded
  call raises when the body runs from a loop or a test.
- A healthcheck workflow declares retries → stop, the retry hides the staleness it exists to report.
- A schedule is created without `catchup_window` → stop, the one-year default will replay a year of
  missed runs after an outage.
- A schedule is created by hand in the UI, or from inside the worker process → stop, it belongs in the
  versioned script; the worker registers workflows and serves them, nothing more.
- A task queue name or cron expression is read from the environment → stop, both are code; a schedule
  and a worker that disagree at runtime have nothing to catch them.
