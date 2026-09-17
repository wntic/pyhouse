# Testing under a durable-execution engine — the obligations, and one binding (Temporal)

The engine levels of `flat-test-run-function`. Read this only once a workflow engine has been **earned**
(`flat-entrypoint`, and its own sibling `DURABLE.md` for what the engine obliges the code to do).

This file is additive. `flat-test-run-function`'s rules hold here unchanged; the obligations below
**exist only once an engine is in play**, so a service on a loop, a cron entry or a timer can neither
satisfy nor violate them. Every template heading names the stack it binds.

Two forms live here:

- **The wrapper through the engine's activity harness** — `flat-test-run-function`'s wrapper form, bound
  to one engine, with the typed-failure assertion its history makes necessary.
- **The orchestration above it** — every step stubbed by its registered wire name, no datastore at all.

## Obligations at the engine levels

1. **Time is never slept and never waited out.** Anything involving a timer, a backoff or a schedule
   runs against the engine's time-skipping clock; a policy with a one-minute initial interval must still
   assert in milliseconds. The general rule is `test-principles`'; what the engine adds is the clock that
   makes obeying it possible.
2. **An orchestration test asserts orchestration only** — that the step ran, that the retry policy is
   what it claims, that the loop terminates and aggregates. No datastore, no transport stub, no
   assertions about stored rows. That is what keeps this form from re-running the run function's
   coverage.
3. **A stub stands in under the registered wire name the orchestration resolves, not by function
   identity.** The orchestration names its steps by string; a stub that is the right function under the
   wrong name is never reached, and the test then exercises the real body against no datastore
   (`flat-entrypoint`'s `DURABLE.md` obligation 4 requires the wire name be declared separately from the
   symbol).
4. **Read loop constants from the orchestration module, and make them public there**, never retype the
   number. A bound that decides how many batches one run performs is part of the contract; an underscore
   on it is a lie the test has to reach past.
5. **A run id is generated fresh per test**, so a re-run cannot collide with a retained execution from a
   previous one.
6. **A batch-loop orchestration gets all three loop tests** — termination on an empty batch, the carried
   cutoff, the carried total. Each covers a continuation mistake the others miss, and none is visible
   from the happy path.
7. **Schedule creation is not tested here.** It is a one-off deploy-time definition, not application
   code, and a test of it would assert only that the engine's SDK works. What *is* worth pinning
   statically is that every schedule's routing name matches one some process actually serves —
   `test-architecture-rule`.

## The wrapper — Temporal `ActivityEnvironment`

`tests/integration/test_activities.py`:

```python
import httpx
import pytest
import respx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine
from temporalio.exceptions import ApplicationError
from temporalio.testing import ActivityEnvironment

from myapp.myframework.activities import FooActivities
from myapp.services.foo_client import FooClient
from myapp.storage.foo_storage import FooStorage
from myapp.storage.foo_table import foo_table

_BASE_URL = "https://foo.test"


def _activities(engine: AsyncEngine) -> FooActivities:
    return FooActivities(
        FooClient(base_url=_BASE_URL, timeout_seconds=1.0), FooStorage(engine)
    )


@respx.mock
async def test_the_wrapper_performs_one_run(
    engine: AsyncEngine, conn: AsyncConnection
) -> None:
    respx.get(f"{_BASE_URL}/foos").mock(
        return_value=httpx.Response(200, json={"items": [{"ref": "alpha", "name": "a"}]})
    )

    await ActivityEnvironment().run(_activities(engine).run_foo_ingest)

    assert (await conn.execute(select(func.count()).select_from(foo_table))).scalar_one() == 1


@respx.mock
async def test_a_service_error_surfaces_as_a_typed_framework_failure(
    engine: AsyncEngine,
) -> None:
    respx.get(f"{_BASE_URL}/foos").mock(return_value=httpx.Response(503))

    with pytest.raises(ApplicationError) as exc_info:
        await ActivityEnvironment().run(_activities(engine).run_foo_ingest)

    assert exc_info.value.type == "FooClientError"
```

Two tests are enough when the wrapper delegates to the run function, which has its own file
(`flat-test-run-function` rule 5). The translation test is the one that earns its place: an untranslated
exception reaches the engine's history as an opaque failure with the context stripped, and the operator
reading that history is the person who needed it.

## The orchestration — Temporal time-skipping environment

`tests/unit/test_workflows.py` — **no datastore, no transport stub, no container**. The orchestration
does no I/O by design, so a test of it that starts a container is testing the wrong thing and paying
seconds for it.

A step is substituted by **registering a stub under the wire name the orchestration resolves**, not by
being the same function:

```python
import uuid
from datetime import datetime

from temporalio import activity
from temporalio.testing import WorkflowEnvironment
from temporalio.worker import Worker

from myapp.myframework import workflows as workflows_module
from myapp.myframework.workflows import FooRecheckWorkflow
from myapp.schemas.foo import RecheckResult

_TASK_QUEUE = "test-queue"
_CUTOFF = datetime(2024, 1, 1, 12, 0, 0)


async def test_every_batch_receives_the_cutoff_the_continuation_carried() -> None:
    cutoffs: list[datetime] = []
    max_batches = workflows_module.MAX_BATCHES_PER_RUN

    @activity.defn(name="recheck_batch")
    async def _batches(cutoff: datetime) -> RecheckResult:
        cutoffs.append(cutoff)
        if len(cutoffs) <= max_batches:
            return RecheckResult(processed=1, matched=0)
        return RecheckResult(processed=0, matched=0)

    async with await WorkflowEnvironment.start_time_skipping() as env:
        async with Worker(
            env.client,
            task_queue=_TASK_QUEUE,
            workflows=[FooRecheckWorkflow],
            activities=[_batches],
        ):
            result = await env.client.execute_workflow(
                FooRecheckWorkflow.run, _CUTOFF, id=str(uuid.uuid4()), task_queue=_TASK_QUEUE
            )

    assert set(cutoffs) == {_CUTOFF}
    assert result.processed == max_batches
```

One test is shown; **three are required** for a batch loop (obligation 6), and the other two —
termination on an empty batch, and the carried total surviving the continuation — differ from this one
only in what the stub returns and what the assertion reads.

The time-skipping environment is what makes a retry test affordable: a declared backoff is skipped rather
than slept through. On the first run it downloads and caches a test-server binary — not a container, but
it needs network access once; cache the directory in CI so later runs are offline.

The loop bound is read from the orchestration module rather than retyped (obligation 4).

## Other bindings

- **Another durable-execution engine.** The wrapper test is still the same two tests, reach and
  translate, against whatever in-process harness that engine ships; the orchestration test changes only
  in how the environment is started, what key a stub stands in under, and how a retry policy is read
  back. The run-function tests do not change, because the body never imports the engine.
- **An engine whose harness cannot skip time.** The retry test then asserts the *declared* policy on the
  orchestration's own declaration rather than observing the attempts — a weaker test, and the honest one.
  Waiting out a real backoff is still forbidden, and every other obligation is unchanged.
- **A replay harness over recorded histories**, where the engine ships one. It pins determinism across a
  code change, which none of the tests here do, and it cannot pin a *new* orchestration's behaviour
  because there is no history yet. It is an addition to the orchestration file, never a replacement.

## Hard stops

- An orchestration test starts a datastore container → stop, the orchestration does no I/O by design; if
  it does, that I/O belongs in a unit of work and the orchestration is wrong.
- An orchestration test stubs the HTTP transport → stop, that means it is reaching the real step body;
  register a stub under the wire name instead.
- An orchestration test re-asserts what a step wrote → stop, that is the run-function file's job;
  duplicating it makes both files change together for one reason.
- A retry is asserted by waiting out the real backoff → stop, use the time-skipping environment.
- A batch-loop test hardcodes the maximum-batches number → stop, read the public constant from the
  orchestration module.
- A batch-loop orchestration ships with only the happy-path test → stop, write all three; a continuation
  that drops the cutoff or the total is invisible from the happy path.
- A schedule definition is being unit-tested → stop, it is deploy-time infrastructure; pin the routing
  name statically instead (`test-architecture-rule`).
