---
name: flat-test-temporal-workflow
description: Use when testing Temporal orchestration only — activity bodies stubbed by registered name, no database or container — covering retry policy under time skipping and a batch loop's termination, carried cutoff and carried total across `continue_as_new`. Only for a service that earned an engine; the activity body it never runs is `flat-test-run-function`.
paths: ["**/tests/**"]
---

# Flat-Layered Test — Temporal Workflow

Consult `test-principles` for the testing constitution. Where this skill contradicts `test-principles`, the constitution wins.

This skill applies only to a service that **earned** a durable-execution engine — durability across
process death, retries that outlive the process, or orchestration over hours (`flat-entrypoint`). The
default trigger is a loop, a cron entry or a timer, and it has no workflow to test.

Workflow tests live under `services/<service>/tests/unit/` — **no database, no HTTP stub, no
container**. A workflow does no I/O by design, so a workflow test that starts a Postgres container is
testing the wrong thing and paying seconds for it.

The rule that keeps this level cheap: **a workflow test asserts orchestration and nothing else** — that
the activity was called, with the timeout and retry policy declared, and that the loop's control flow is
what it claims. What the activity *does* is already pinned by `flat-test-run-function`, and
duplicating it inside a workflow test buys nothing.

## When to use vs. neighbours

- The activity body, and the run function it calls → `flat-test-run-function`.
- Writing the workflow this file exercises — continuation with a carried cutoff, guarded heartbeats,
  healthcheck workflows → `flat-temporal-workflow`.
- The tables the activity writes through → `flat-test-schema-package`.
- The service runs on a loop, a cron entry or a timer — the default — → none of this applies; the
  trigger's test is the containment test in `flat-test-run-function`.
- Whether the service has earned an engine at all → `flat-entrypoint`.
- Schedule creation → not tested at all; the static "every schedule's task queue is served by some
  worker" rule is `test-architecture-rule`. See the rules below.
- The shared groundwork — naming, AAA, reliability → `test-principles`.

## Template — a stub activity (Temporal name registration)

The workflow refers to an activity by the string in `@activity.defn(name=...)`. A stub stands in for it
by declaring the **same name**, not by being the same function:

```python
@activity.defn(name="run_foo_ingest")
async def _stub_run_foo_ingest() -> IngestResult:
    return IngestResult(fetched=1, kept=1)
```

That is the whole substitution mechanism at this level, and it is why the name is required rather than
inferred (`flat-entrypoint`).

## Template — a single-activity workflow (Temporal time-skipping environment)

`services/foo_parser/tests/unit/test_workflows.py`:

```python
import uuid

import pytest
from temporalio import activity
from temporalio.client import WorkflowFailureError
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from foo_parser.schemas import IngestResult
from foo_parser.temporal.workflows import FooIngestWorkflow

_TASK_QUEUE = "test-queue"


async def test_the_workflow_runs_the_ingest_activity_and_returns_its_result() -> None:
    calls: list[None] = []

    @activity.defn(name="run_foo_ingest")
    async def _stub() -> IngestResult:
        calls.append(None)
        return IngestResult(fetched=3, kept=2)

    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=_TASK_QUEUE,
            workflows=[FooIngestWorkflow],
            activities=[_stub],
        ):
            result = await env.client.execute_workflow(
                FooIngestWorkflow.run, id=str(uuid.uuid4()), task_queue=_TASK_QUEUE
            )

    assert len(calls) == 1
    assert result == IngestResult(fetched=3, kept=2)


async def test_the_activity_is_retried_up_to_the_declared_maximum() -> None:
    attempts: list[int] = []

    @activity.defn(name="run_foo_ingest")
    async def _always_fails() -> IngestResult:
        attempts.append(activity.info().attempt)
        raise RuntimeError("boom")

    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=_TASK_QUEUE,
            workflows=[FooIngestWorkflow],
            activities=[_always_fails],
        ):
            with pytest.raises(WorkflowFailureError):
                await env.client.execute_workflow(
                    FooIngestWorkflow.run, id=str(uuid.uuid4()), task_queue=_TASK_QUEUE
                )

    assert attempts == [1, 2, 3]
```

The retry test is what `start_time_skipping()` is for. The declared backoff between attempts is skipped
rather than slept through, so a policy with a one-minute initial interval still asserts in milliseconds
— which is the only way this test is worth having at all.

On the first run the time-skipping environment downloads and caches a test-server binary. That is not a
container, but it does need network access for the initial download; cache the directory in CI so
subsequent runs are offline.

## Template — a batch-loop workflow (Temporal time-skipping environment)

A workflow that processes batches in a loop needs tests that pin the **loop semantics**, not the batch
contents (`flat-temporal-workflow` owns the shape being tested):

```python
from datetime import datetime

from foo_parser.schemas import RecheckResult
from foo_parser.temporal import workflows as workflows_module
from foo_parser.temporal.workflows import FooRecheckWorkflow

_CUTOFF = datetime(2024, 1, 1, 12, 0, 0)


async def test_the_loop_stops_on_an_empty_batch_and_sums_the_results() -> None:
    calls: list[datetime] = []

    @activity.defn(name="recheck_batch")
    async def _two_batches(cutoff: datetime) -> RecheckResult:
        calls.append(cutoff)
        if len(calls) == 1:
            return RecheckResult(processed=10, matched=3)
        return RecheckResult(processed=0, matched=0)

    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=_TASK_QUEUE,
            workflows=[FooRecheckWorkflow],
            activities=[_two_batches],
        ):
            result = await env.client.execute_workflow(
                FooRecheckWorkflow.run, _CUTOFF, id=str(uuid.uuid4()), task_queue=_TASK_QUEUE
            )

    assert result == RecheckResult(processed=10, matched=3)


async def test_every_batch_receives_the_same_cutoff() -> None:
    cutoffs: list[datetime] = []

    @activity.defn(name="recheck_batch")
    async def _two_batches_then_empty(cutoff: datetime) -> RecheckResult:
        cutoffs.append(cutoff)
        if len(cutoffs) < 3:
            return RecheckResult(processed=1, matched=0)
        return RecheckResult(processed=0, matched=0)

    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=_TASK_QUEUE,
            workflows=[FooRecheckWorkflow],
            activities=[_two_batches_then_empty],
        ):
            await env.client.execute_workflow(
                FooRecheckWorkflow.run, _CUTOFF, id=str(uuid.uuid4()), task_queue=_TASK_QUEUE
            )

    assert set(cutoffs) == {_CUTOFF}


async def test_the_loop_continues_as_new_after_the_maximum_batches() -> None:
    max_batches = workflows_module.MAX_BATCHES_PER_RUN
    extra_batches = 1
    responses = iter(
        [RecheckResult(processed=1, matched=0)] * (max_batches + extra_batches)
        + [RecheckResult(processed=0, matched=0)]
    )
    calls: list[datetime] = []

    @activity.defn(name="recheck_batch")
    async def _always_nonempty(cutoff: datetime) -> RecheckResult:
        calls.append(cutoff)
        return next(responses)

    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=_TASK_QUEUE,
            workflows=[FooRecheckWorkflow],
            activities=[_always_nonempty],
        ):
            result = await env.client.execute_workflow(
                FooRecheckWorkflow.run, _CUTOFF, id=str(uuid.uuid4()), task_queue=_TASK_QUEUE
            )

    assert len(calls) == max_batches + extra_batches + 1
    assert set(calls) == {_CUTOFF}
    assert result.processed == max_batches + extra_batches
```

What those three pin, and why each is worth its seconds:

- **Termination.** The loop stops when a batch returns `processed == 0`, and the workflow returns the
  summed aggregate rather than the last batch's.
- **The carried cutoff.** Every batch — across the `continue_as_new` boundary — receives the identical
  cutoff. A `continue_as_new` that dropped it would recompute `workflow.now()` and re-process the
  window, and no other test would notice.
- **The carried total.** After `continue_as_new` the final result still counts every batch. A total left
  behind makes the run under-report, which looks like a data problem rather than a control-flow bug.

The third test reads `MAX_BATCHES_PER_RUN` from the workflow module rather than repeating the number.
Hardcoding it makes the test pass against a stale constant the day someone tunes it. The limit is a
**public** module constant, not an underscore-prefixed one: it bounds observable behaviour — how many
batches one run performs — so it is part of the workflow's contract, and a test reaching for a private
name couples itself to something nothing promises to keep.

## Other bindings

- **Another durable-execution engine** — Restate, DBOS, a managed step orchestrator. What changes: how
  the test environment is started, what key a stub stands in under, and how a retry policy is declared
  and read back. What does not: the orchestration-only assertion scope, the fresh-id-per-test rule, the
  three loop tests, reading the loop bound from the module, and the ban on real sleeping.
- **An engine whose harness cannot skip time.** The retry test then asserts the *declared* policy on the
  workflow's own declaration rather than observing the attempts — a weaker test, and the honest one.
  Waiting out a real backoff is still forbidden, and every other rule is unchanged.
- **A replay harness over recorded histories**, where the engine ships one. It pins determinism across a
  code change, which none of the tests here do, and it cannot pin a *new* workflow's behaviour because
  there is no history yet. It is an addition to this file, never a replacement for it.

## Rules

1. **A workflow test asserts orchestration only** — that the activity ran, that the retry policy is what
   it claims, that the loop terminates and aggregates. No database, no transport stub, no assertions
   about parsed rows.
2. **A stub stands in under the registered name the workflow resolves, not by function identity.** The
   workflow names its steps by string; a stub that is the right function under the wrong name is never
   reached, and the test then exercises the real body against no database.
3. **Time is skipped, never slept.** Anything involving a timer, a backoff or a schedule runs against the
   engine's time-skipping clock (`WorkflowEnvironment.start_time_skipping()` here). A `time.sleep` or
   `asyncio.sleep` in a test is a defect, and so is a retry test that waits out the real backoff — a
   policy with a one-minute initial interval must still assert in milliseconds.
4. **Read loop constants from the workflow module, and make them public there**, never retype the number.
   A bound that decides how many batches one run performs is part of the contract; an underscore on it is
   a lie the test has to reach past.
5. **A workflow id is generated fresh per test** (`str(uuid.uuid4())` here), so a re-run cannot collide
   with a retained execution from a previous one.
6. **A batch-loop workflow gets all three loop tests** — termination, carried cutoff, carried total.
   Each covers a `continue_as_new` mistake the others miss.
7. **Schedule creation is not tested here.** It is a one-off deploy-time script, not application code,
   and a test of it would assert only that the engine's SDK works. What *is* worth pinning statically is that
   every schedule's task queue matches a queue some worker serves —
   `test-architecture-rule`.

## Hard stops

- A workflow test starts a Postgres container → stop, the workflow does no I/O by design; if it does, the
  I/O belongs in an activity and the workflow is wrong.
- A workflow test stubs the HTTP transport → stop, that means it is reaching the real activity body;
  register a stub activity by name instead.
- A workflow test re-asserts what the activity wrote → stop, that is the run-function file's job;
  duplicating it makes both files change together for one reason.
- A test asserts a Temporal retry by waiting out the real backoff → stop, use the time-skipping
  environment.
- A batch-loop test hardcodes the maximum-batches number → stop, import the constant.
- A batch-loop workflow has only a termination test → stop, the `continue_as_new` cases are exactly where
  the bugs live and neither is visible from the happy path.
- A test reuses a fixed workflow id across tests → stop, generate one per test.
