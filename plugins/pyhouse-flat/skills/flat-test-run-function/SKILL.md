---
name: flat-test-run-function
description: Use when testing what a flat-layered service's trigger actually runs — the run function end to end against the real datastore with the upstream transport stubbed and an idempotence test every time, the loop's failure-containment contract, and the framework wrapper through its own in-process harness, proving only that the wrapper reaches the body and translates its failures. Where a durable-execution engine was earned, it adds the orchestration level above those, every step stubbed by its registered wire name. Not the client's own transport, which is `flat-test-service-client`, and not the storage package's write path, which is `flat-test-persistence`.
when_to_use: Also when asked to test a `run_once` body, a polling loop's error handling, a wrapper class, a workflow's retry policy, a batch loop's termination, or what a continuation carries across runs.
---

# Flat-Layered Test — Run Function

Consult `test-principles` for the testing constitution. Where this skill contradicts `test-principles`, the constitution wins.

A run function is where a flat-layered service composes everything, so its test is the one that catches
wiring: the client's payload actually fits what the storage class stores, the filter drops what it
should, the aggregate counts what happened. **This skill covers the levels of wrapping around that one
call, tested at each.** They are one subject because they are layers of the same invocation.

Two forms are always in scope:

- **The run function** — the body, tested end to end against the real datastore with the upstream
  transport stubbed. Every service has one of these, whatever triggers it.
- **The loop's failure containment** — that one failed run does not kill the process. This is the
  default trigger's test (`flat-entrypoint`).

**A service with a framework wrapper adds a third**: the same body under the framework's own decorator,
run through whatever in-process harness that framework ships, proving reach and translation only.

**A service that earned a durable-execution engine adds a fourth** — the orchestration above the
wrapper, every step stubbed by its registered wire name, no datastore at all — plus the obligations that
come with it. Those are under `## Rules`, in the subsection that applies only once an engine has been
earned (`flat-entrypoint` rule 1 owns that test); skip it entirely otherwise.

## When to use vs. neighbours

- The HTTP client the body calls → `flat-test-service-client`; this level substitutes that client's
  transport, never the client object itself.
- The tables, helpers and storage class the body writes through → `flat-test-persistence`.
- The container and isolation fixtures → `flat-test-integration-setup`; the code here owns its
  transactions, so it takes the whole-schema wipe.
- Writing the run function, the `guarded` wrapper or the trigger, rather than testing it →
  `flat-entrypoint`.
- Testing the orchestration level, the batch loop's continuation, or a declared retry policy → still
  this skill, under `## Rules`, and only once an engine has been earned.
- A pure filter or normalize function the body calls → a unit test with no fixtures; it does not belong
  here.
- The static check that a schedule's routing name matches one a process actually serves →
  `test-architecture-rule`.
- The shared groundwork — the substitution ladder, reliability rules, never waiting out real time →
  `test-principles`.

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

The aggregate test matters because that return value is what the trigger reports — a payload, a stored
summary, or the loop's own log line: a body that writes the right rows while reporting the wrong counts
fails silently everywhere a human is looking.

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

## Template — the framework wrapper (the framework's own in-process harness)

A wrapper adapts the run function to a trigger and holds no logic, so its test is **two tests**: that it
reaches the body, and that a service failure arrives at the framework as a typed failure carrying the
original's identity rather than an opaque one. Run it through whatever harness the framework ships for
invoking one unit in-process — no worker, no broker, no scheduler.

Both tests take the same fixtures the run-function file takes, because the wrapper reaches the same
datastore; what they must not do is re-run the body's coverage. The translation test is the one that
earns its place: an untranslated exception reaches the trigger's error surface with the context
stripped, and nothing else in the suite notices.

Under a durable-execution engine that harness is the one the engine ships for running a single unit of
work in-process, and the typed-failure assertion is what its history makes necessary.

## Other bindings

- **A different upstream-stub mechanism** — a transport handed to the client, a local stub server, a
  recorded cassette (`flat-test-service-client` names the trade-offs). Only how the upstream is pinned
  changes; rule 2's asymmetry — upstream substituted, datastore not — is the thing that must survive,
  because it is what makes this level catch wiring at all.
- **A different log-capture mechanism** for the containment test — a structured-log capture fixture, an
  injected recording logger. The assertion moves from the captured text to that recorder's events; rule 4
  still holds everywhere else, and the containment test stays the one place a log is the subject.
- **No framework wrapper at all.** A service triggered by a loop, a cron entry or a timer writes the
  first two forms and stops; nothing is missing, because there is no wrapper to prove.
- **An engine whose harness cannot skip time.** The retry test then asserts the *declared* policy on the
  orchestration's own declaration rather than observing the attempts — a weaker test, and the honest one.
  Waiting out a real backoff is still forbidden, and every obligation below is unchanged.
- **A replay harness over recorded histories**, where the engine ships one. It pins determinism across a
  code change, which none of the tests here do, and it cannot pin a *new* orchestration's behaviour
  because there is no history yet. It is an addition to the orchestration test file, never a
  replacement.

## Rules

1. **A run function takes what it needs as parameters** — the client, the storage class. A body reaching
   for a module-level engine or a settings value cannot be pointed at the test container, and no test of
   it means anything.
2. **The upstream is substituted at its transport; the datastore is not substituted at all.** That
   asymmetry is what makes this level catch wiring: real columns, real constraints, real conflict
   semantics, with only the vendor's uptime removed. Substituting the client object instead moves the
   client's own request building and error translation out of the test, and substituting the datastore
   removes the only thing this level can prove.
3. **Where a run can repeat over the same input, its test file pins what the second run does.** A
   scheduled pass over a feed that mostly repeats, and any run a trigger may retry after a partial
   failure, both meet that condition — run twice, assert the observable state is unchanged. A run whose
   input is consumed once, or that is by construction never repeated, has nothing to pin and the test
   would assert a coincidence.
4. **Assert on rows, and on the returned aggregate** — never on log lines, except in the
   failure-containment test whose subject *is* the log. A run that logged `"ok"` and wrote nothing must
   fail.
5. **A wrapper test proves the wrapper, not the body.** One happy path and one exception translation:
   that the trigger reaches the body, and that a service failure arrives at the framework as a typed
   failure carrying the original's identity rather than an opaque one.
6. **The wrapper body never diverges from the run function** — it calls it and holds no logic of its own.
   A divergence means two triggers of the same work are drifting apart, and the tests must not paper
   over it.

### Once a durable-execution engine is earned

An engine is earned by `flat-entrypoint` rule 1 and by nothing else. These obligations cover the
orchestration level that only an engine has; the rules above hold unchanged beneath them, and a service
on a loop, a cron entry or a timer can neither satisfy nor violate them. The run-function tests do not
change under any engine, because the body never imports one.

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
   (`flat-entrypoint`'s durable obligation 4 requires the wire name be declared separately from the
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
- A test of the run function substitutes the datastore → stop, that removes the only thing this level can
  prove; substitute the upstream transport and keep the real store.
- An orchestration, a continuation or a declared retry policy is about to be tested with no engine in
  the service → stop, that level exists only once an engine has been earned (`flat-entrypoint` rule 1).

### Under a durable-execution engine

- An orchestration test starts a datastore container → stop, the orchestration does no I/O by design; if
  it does, that I/O belongs in a unit of work and the orchestration is wrong.
- An orchestration test stubs the HTTP transport → stop, that means it is reaching the real step body;
  register a stub under the wire name instead.
- An orchestration test re-asserts what a step wrote → stop, that is the run-function file's job;
  duplicating it makes both files change together for one reason.
- A retry is asserted by waiting out the real backoff → stop, use the engine's time-skipping clock.
- A batch-loop test hardcodes the maximum-batches number → stop, read the public constant from the
  orchestration module.
- A batch-loop orchestration ships with only the happy-path test → stop, write all three; a continuation
  that drops the cutoff or the total is invisible from the happy path.
- A schedule definition is being unit-tested → stop, it is deploy-time infrastructure; pin the routing
  name statically instead (`test-architecture-rule`).
