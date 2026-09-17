---
name: flat-test-run-function
description: Use when testing what a flat-layered service's trigger actually runs — the run function end to end against the real datastore with the upstream transport stubbed and an idempotence test every time, the loop's failure-containment contract, the durable-execution wrapper through its own activity harness, and, where an engine was earned, the orchestration above them with every step stubbed by its registered wire name, no datastore and no real sleeping. Not the client's own transport, which is `flat-test-service-client`, and not the storage package's write path, which is `flat-test-persistence`.
when_to_use: Also when asked to test a `run_once` body, a polling loop's error handling, an activity wrapper, a workflow's retry policy, a batch loop's termination, or what a continuation carries across runs.
paths: ["**/tests/**"]
---

# Flat-Layered Test — Run Function

Consult `test-principles` for the testing constitution. Where this skill contradicts `test-principles`, the constitution wins.

A run function is where a flat-layered service composes everything, so its test is the one that catches
wiring: the client's payload actually fits what the storage class stores, the filter drops what it
should, the aggregate counts what happened. **This skill covers three levels of wrapping around that one
call, tested at each** — the body, the trigger, and the orchestration above the trigger. They are one
subject because they are layers of the same invocation; a separate skill for the outermost one would be
a skill named after a workflow engine.

Four forms:

- **The run function** — the body, tested end to end against the real datastore with the upstream
  transport stubbed. Every service has one of these, whatever triggers it.
- **The loop's failure containment** — that one failed run does not kill the process. This is the
  default trigger's test (`flat-entrypoint`).
- **The durable-execution wrapper** — the same body under an engine's unit-of-work decorator, run through
  that engine's own activity harness.
- **The orchestration above it** — every step stubbed by its registered wire name, no datastore at all.

The last two exist only for a service that *earned* an engine; a service on a loop, a cron entry or a
timer writes the first two and stops.

## When to use vs. neighbours

- The HTTP client the body calls → `flat-test-service-client`; this level substitutes that client's
  transport, never the client object itself.
- The tables, helpers and storage class the body writes through → `flat-test-persistence`.
- The container and isolation fixtures → `flat-test-integration-setup`; the code here owns its
  transactions, so it takes the whole-schema wipe.
- Writing the run function, the `guarded` wrapper, the trigger or the orchestration, rather than testing
  it → `flat-entrypoint` and its sibling `DURABLE.md`.
- A pure filter or normalize function the body calls → a unit test with no fixtures; it does not belong
  here.
- The static check that every schedule's queue is served by some worker → `test-architecture-rule`.
- The shared groundwork — the substitution ladder, reliability rules → `test-principles`.

## Template — the run function end to end (pytest, `respx` over `httpx`, real Postgres)

`tests/integration/test_foo_ingest.py`:

```python
import httpx
import pytest
import respx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from myapp.exceptions import FooClientError
from myapp.ingest.foo_ingest import run_once
from myapp.services.foo_client import FooClient
from myapp.storage.foo_storage import FooStorage
from myapp.storage.foo_table import bar_table, foo_table

_BASE_URL = "https://foo.test"


def _client() -> FooClient:
    return FooClient(base_url=_BASE_URL, timeout_seconds=1.0)


@respx.mock
async def test_a_run_lands_its_foos_and_their_labels(
    engine: AsyncEngine, conn: AsyncConnection
) -> None:
    respx.get(f"{_BASE_URL}/foos").mock(
        return_value=httpx.Response(
            200, json={"items": [{"ref": " ALPHA ", "name": "a", "labels": ["amber"]}]}
        )
    )

    await run_once(_client(), FooStorage(engine))

    reference = (await conn.execute(select(foo_table.c.reference))).scalar_one()
    labels = (await conn.execute(select(bar_table.c.label))).scalars().all()
    assert reference == "alpha"
    assert labels == ["amber"]


@respx.mock
async def test_items_the_filter_rejects_are_not_stored(
    engine: AsyncEngine, conn: AsyncConnection
) -> None:
    respx.get(f"{_BASE_URL}/foos").mock(
        return_value=httpx.Response(200, json={"items": [{"ref": None, "name": "a"}]})
    )

    await run_once(_client(), FooStorage(engine))

    assert (await conn.execute(select(func.count()).select_from(foo_table))).scalar_one() == 0


@respx.mock
async def test_a_second_run_over_the_same_batch_writes_no_duplicates(
    engine: AsyncEngine, conn: AsyncConnection
) -> None:
    respx.get(f"{_BASE_URL}/foos").mock(
        return_value=httpx.Response(200, json={"items": [{"ref": "alpha", "name": "a"}]})
    )
    await run_once(_client(), FooStorage(engine))

    await run_once(_client(), FooStorage(engine))

    assert (await conn.execute(select(func.count()).select_from(foo_table))).scalar_one() == 1


@respx.mock
async def test_a_run_reports_what_it_fetched_and_kept(engine: AsyncEngine) -> None:
    respx.get(f"{_BASE_URL}/foos").mock(
        return_value=httpx.Response(
            200,
            json={"items": [{"ref": "alpha", "name": "a"}, {"ref": None, "name": "b"}]},
        )
    )

    result = await run_once(_client(), FooStorage(engine))

    assert (result.fetched, result.kept) == (2, 1)


@respx.mock
async def test_an_upstream_failure_propagates_and_writes_nothing(
    engine: AsyncEngine, conn: AsyncConnection
) -> None:
    respx.get(f"{_BASE_URL}/foos").mock(return_value=httpx.Response(503))

    with pytest.raises(FooClientError):
        await run_once(_client(), FooStorage(engine))

    assert (await conn.execute(select(func.count()).select_from(foo_table))).scalar_one() == 0
```

The idempotence test is the one worth writing first. A service that runs on a schedule over a feed that
mostly repeats has "the second run over the same batch changes nothing" as its central behaviour, and it
is the one a wrong conflict-column list breaks.

The aggregate test matters because that return value is what the trigger reports — the orchestration's
payload under an engine, the loop's own log line otherwise: a body that writes the right rows while
reporting the wrong counts fails silently everywhere a human is looking.

## Template — the loop's failure containment (pytest `caplog`)

The loop entrypoint's contract is that one failed run does not kill the process. Test the containment,
not the loop — a `while True` under test needs an escape, and building one changes the thing being
tested. This is why `guarded` is a named function (`flat-entrypoint`):

```python
async def test_a_failing_run_is_logged_and_does_not_escape(caplog) -> None:
    async def _boom() -> None:
        raise FooClientError("upstream down")

    await guarded(_boom)

    assert "foo_ingest_run_failed" in caplog.text
```

If the `try/except` is still inline inside `while True`, either extract it or leave the loop untested —
do not test a `while True` by monkeypatching `asyncio.sleep` to raise, which asserts the mechanism
instead of the behaviour.

## Template — the durable-execution wrapper (Temporal `ActivityEnvironment`)

`tests/integration/test_activities.py`:

```python
import httpx
import pytest
import respx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine
from temporalio.exceptions import ApplicationError
from temporalio.testing import ActivityEnvironment

from myapp.services.foo_client import FooClient
from myapp.storage.foo_storage import FooStorage
from myapp.storage.foo_table import foo_table
from myapp.temporal.activities import FooActivities

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

Two tests are enough here when the wrapper delegates to the run function, which has its own file. Their
job is to prove the wrapper reaches the body and translates its failures — not to re-run the body's
coverage. The translation test is the one that earns its place: an untranslated exception reaches the
engine's history as an opaque failure with the context stripped, and nothing else in the suite notices.

## Template — the orchestration above it (Temporal time-skipping environment)

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

from myapp.schemas.foo import RecheckResult
from myapp.temporal import workflows as workflows_module
from myapp.temporal.workflows import FooRecheckWorkflow

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

One test is shown; **three are required** for a batch loop (rule 12), and the other two — termination on
an empty batch, and the carried total surviving the continuation — differ from this one only in what the
stub returns and what the assertion reads.

The time-skipping environment is what makes a retry test affordable: a declared backoff is skipped rather
than slept through, so a policy with a one-minute initial interval still asserts in milliseconds. On the
first run it downloads and caches a test-server binary — not a container, but it needs network access
once; cache the directory in CI so later runs are offline.

The loop bound is read from the orchestration module rather than retyped. It is a **public** module
constant because it bounds observable behaviour — how many batches one run performs — so it is part of
the contract, and a test reaching for a private name couples itself to something nothing promises to
keep.

## Other bindings

- **A different upstream-stub mechanism** — a transport handed to the client, a local stub server, a
  recorded cassette (`flat-test-service-client` names the trade-offs). Only how the upstream is pinned
  changes; rule 2's asymmetry — upstream substituted, datastore not — is the thing that must survive,
  because it is what makes this level catch wiring at all.
- **A different durable-execution engine, or none.** Under another engine the wrapper test is still the
  same two tests, reach and translate, against whatever in-process harness that engine ships, and the
  orchestration test changes only in how the environment is started, what key a stub stands in under, and
  how a retry policy is read back. The run-function tests do not change, because the body never imports
  the engine. Where no engine was earned, both files do not exist and the loop's containment test is the
  only trigger-level test.
- **An engine whose harness cannot skip time.** The retry test then asserts the *declared* policy on the
  orchestration's own declaration rather than observing the attempts — a weaker test, and the honest one.
  Waiting out a real backoff is still forbidden, and every other rule is unchanged.
- **A replay harness over recorded histories**, where the engine ships one. It pins determinism across a
  code change, which none of the tests here do, and it cannot pin a *new* orchestration's behaviour
  because there is no history yet. It is an addition to the orchestration file, never a replacement.
- **A different log-capture mechanism** for the containment test — a structured-log capture fixture, an
  injected recording logger. The assertion moves from the captured text to that recorder's events; rule 4
  still holds everywhere else, and the containment test stays the one place a log is the subject.

## Rules

1. **A run function takes what it needs as parameters** — the client, the storage class. A body reaching
   for a module-level engine or a settings value cannot be pointed at the test container, and no test of
   it means anything.
2. **The upstream is substituted at its transport; the datastore is not substituted at all.** That
   asymmetry is what makes this level catch wiring: real columns, real constraints, real conflict
   semantics, with only the vendor's uptime removed. Substituting the client object instead moves the
   client's own request building and error translation out of the test, and substituting the datastore
   removes the only thing this level can prove.
3. **Every run-function test file has an idempotence test.** Second run over the same batch, assert the
   row counts are unchanged.
4. **Assert on rows, and on the returned aggregate** — never on log lines, except in the
   failure-containment test whose subject *is* the log. A run that logged `"ok"` and wrote nothing must
   fail.
5. **A wrapper test proves the wrapper, not the body.** One happy path and one exception translation:
   that the trigger reaches the body, and that a service failure arrives at the engine as a typed failure
   carrying the original's identity rather than an opaque one.
6. **The wrapper body never diverges from the run function** — it calls it and holds no logic of its own.
   A divergence means the scheduled and continuous forms are drifting apart, and the tests must not paper
   over it.
7. **Time is never slept and never waited out.** A `time.sleep` or `asyncio.sleep` in a test is a defect,
   and so is a retry test that sits through the real backoff. Anything involving a timer, a backoff or a
   schedule runs against the engine's time-skipping clock; a policy with a one-minute initial interval
   must still assert in milliseconds.
8. **An orchestration test asserts orchestration only** — that the step ran, that the retry policy is
   what it claims, that the loop terminates and aggregates. No datastore, no transport stub, no
   assertions about stored rows. That is what keeps this form from re-running the first form's coverage.
9. **A stub stands in under the registered wire name the orchestration resolves, not by function
   identity.** The orchestration names its steps by string; a stub that is the right function under the
   wrong name is never reached, and the test then exercises the real body against no datastore
   (`flat-entrypoint` rule 8 requires the wire name be declared separately from the symbol).
10. **Read loop constants from the orchestration module, and make them public there**, never retype the
    number. A bound that decides how many batches one run performs is part of the contract; an underscore
    on it is a lie the test has to reach past.
11. **A run id is generated fresh per test**, so a re-run cannot collide with a retained execution from a
    previous one.
12. **A batch-loop orchestration gets all three loop tests** — termination on an empty batch, the carried
    cutoff, the carried total. Each covers a continuation mistake the others miss, and none is visible
    from the happy path.
13. **Schedule creation is not tested here.** It is a one-off deploy-time script, not application code,
    and a test of it would assert only that the engine's SDK works. What *is* worth pinning statically is
    that every schedule's task queue matches a queue some worker serves — `test-architecture-rule`.

## Hard stops

- `run_once` reaches for a module-level engine instead of taking one → stop, add the parameter; this is a
  change to the run function, and it is the change that makes it testable at all.
- A test drives the `while True` loop directly → stop, extract the guarded single-run call and test that;
  the loop itself is one `await asyncio.sleep` and needs no coverage.
- A test monkeypatches `asyncio.sleep` to break out of a loop → stop, that asserts the mechanism, not the
  behaviour.
- A wrapper test re-asserts everything the run-function test already covers → stop, the two files then
  change together for one reason; keep the wrapper test to the wrapper.
- The wrapper body contains logic the run function does not → stop, move it down; the wrapper holds no
  logic.
- An orchestration test starts a datastore container → stop, the orchestration does no I/O by design; if
  it does, that I/O belongs in a unit of work and the orchestration is wrong.
- An orchestration test stubs the HTTP transport → stop, that means it is reaching the real step body;
  register a stub under the wire name instead.
- An orchestration test re-asserts what a step wrote → stop, that is the run-function file's job;
  duplicating it makes both files change together for one reason.
- A retry is asserted by waiting out the real backoff → stop, use the time-skipping environment.
- A batch-loop test hardcodes the maximum-batches number → stop, read the public constant from the
  orchestration module.
