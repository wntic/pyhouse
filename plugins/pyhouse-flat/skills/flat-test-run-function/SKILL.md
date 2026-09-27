---
name: flat-test-run-function
description: Use when testing what a flat-layered service's trigger actually runs — the run function end to end against the real datastore with the upstream transport stubbed and an idempotence test wherever a run can repeat, the containment contract of a process that outlives one run, and the framework wrapper through its own in-process harness, proving only that the wrapper reaches the body and translates its failures. Where a durable-execution engine was earned, it adds the orchestration level above those, every step stubbed by its registered wire name. Not the client's own transport, which is `flat-test-service-client`, and not the data-access package's write path, which is `flat-test-persistence`.
when_to_use: Also when asked to test a `run_once` body, a polling loop's error handling, a wrapper class, an HTTP route in front of a run function, a workflow's retry policy, a batch loop's termination, or what a continuation carries across runs.
---

# Flat-Layered Test — Run Function

Consult `test-principles` for the testing constitution. Where this skill contradicts `test-principles`, the constitution wins.

A run function is where a flat-layered service composes everything, so its test is the one that catches
wiring: the client's payload actually fits what the repository class stores, and the aggregate counts
what happened. **This skill covers the levels of wrapping around that one
call, tested at each.** They are one subject because they are layers of the same invocation.

One form is always in scope:

- **The run function** — the body, tested end to end against the real datastore with the upstream
  transport stubbed. Every service has one of these, whatever triggers it. A service with no store
  asserts instead on the requests its stubbed transports recorded and on the aggregate the run returns.

**A process that outlives one run — a loop or a consumer — adds the containment test**: that one failed
run does not kill the process. A process that does one run and exits has no guard and no such test
(`flat-entrypoint` rule 8).

**A service with a framework wrapper adds the wrapper test**: the same body under the framework's own
decorator or route, run through whatever in-process harness that framework ships, proving reach and
translation only.

**A service that earned a durable-execution engine adds the orchestration level** — the orchestration
above the wrapper, every step stubbed by its registered wire name, no datastore at all — plus the
obligations that come with it. Those are under `## Rules`, in the subsection that applies only once an
engine has been earned (`flat-entrypoint` rule 1 decides whether it is earned); skip it entirely
otherwise.

## When to use vs. neighbours

- The HTTP client the body calls → `flat-test-service-client`; this level substitutes that client's
  transport, never the client object itself.
- The tables and repository class the body writes through → `flat-test-persistence`.
- The container and isolation fixtures → `flat-test-integration-setup`; the code here owns its
  transactions, so it takes the whole-schema wipe.
- Writing the run function, the `guarded` wrapper or the trigger, rather than testing it →
  `flat-entrypoint`.
- Testing the orchestration level, the batch loop's continuation, or a declared retry policy → still
  this skill, under `## Rules`, and only once an engine has been earned.
- The pure mapping step the body calls (`to_foo`) → a unit test with no fixtures; it does not belong
  here.
- The static check that a schedule's routing name matches one a process actually serves →
  `flat-entrypoint` rule 6.
- The shared groundwork — the substitution ladder, reliability rules, never waiting out real time →
  `test-principles`.

## Template — the run function end to end (pytest, `respx` over `httpx`, real Postgres)

`tests/integration/test_foo_sync.py` — the upstream stub `foo_api` and the client over it,
`foo_client`, are the shared fixtures in `tests/conftest.py` (`flat-test-service-client`):

```python
import httpx
import respx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from myapp.foo_api import FooClient
from myapp.foo_sync import run_once
from myapp.postgres import FooRepository
from myapp.postgres.foo_table import foo_table
from myapp.schemas import RunResult

_SENT_AT = "2024-01-01T00:00:00Z"
_TWO_FOOS = {
    "items": [{"ref": "alpha", "name": "a", "sent_at": _SENT_AT}, {"ref": "beta", "name": "b", "sent_at": _SENT_AT}]
}


async def test_a_run_records_what_it_fetched(
    foo_api: respx.MockRouter, foo_client: FooClient, engine: AsyncEngine, conn: AsyncConnection
) -> None:
    foo_api.get("/foos").mock(return_value=httpx.Response(200, json=_TWO_FOOS))

    await run_once(foo_client, FooRepository(engine))

    query = select(foo_table.c.reference, foo_table.c.name).order_by(foo_table.c.reference)
    rows = (await conn.execute(query)).all()
    assert [tuple(row) for row in rows] == [("alpha", "a"), ("beta", "b")]


async def test_a_second_run_over_the_same_batch_writes_no_duplicates(
    foo_api: respx.MockRouter, foo_client: FooClient, engine: AsyncEngine, conn: AsyncConnection
) -> None:
    foo_api.get("/foos").mock(return_value=httpx.Response(200, json=_TWO_FOOS))
    await run_once(foo_client, FooRepository(engine))

    await run_once(foo_client, FooRepository(engine))

    assert (await conn.execute(select(func.count()).select_from(foo_table))).scalar_one() == 2


async def test_a_run_reports_what_it_recorded(
    foo_api: respx.MockRouter, foo_client: FooClient, engine: AsyncEngine
) -> None:
    foo_api.get("/foos").mock(return_value=httpx.Response(200, json=_TWO_FOOS))

    result = await run_once(foo_client, FooRepository(engine))

    assert result == RunResult(recorded=2)
```

The idempotence test is the one worth writing first. A service that runs on a schedule over a feed that
mostly repeats has "the second run over the same batch changes nothing" as its central behaviour, and it
is the one a wrong conflict-column list breaks.

The aggregate test matters because that return value is what the trigger reports — a payload, a stored
summary, or the loop's own log line: a body that writes the right rows while reporting the wrong counts
fails silently everywhere a human is looking.

## Template — the containment of a process that outlives one run (pytest)

Only where the service runs a loop or a consumer. Its contract is that one failed run does not kill
the process. Test the containment, not the loop — a `while True` under test needs an escape, and
building one changes the thing being tested. This is why `guarded` is a named function in a module of its own (`flat-entrypoint`), and why it
returns whether the run succeeded: the assertion is on that value, never on what was logged. It needs no
datastore, so it lives in `tests/unit/test_containment.py`, one file for the one guard every process
shares:

```python
from myapp.containment import guarded
from myapp.exceptions import FooClientError


async def test_a_failing_run_is_contained() -> None:
    async def _boom() -> None:
        raise FooClientError("upstream down")

    assert await guarded("foo_sync", _boom) is False


async def test_a_succeeding_run_is_reported_as_such() -> None:
    async def _ok() -> None:
        return None

    assert await guarded("foo_sync", _ok) is True
```

The failing case returning at all is the containment; `False` pins that the guard saw the failure
rather than some other path returning early, and the succeeding case pins that it does not report every
run as failed.

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

### The HTTP shape — FastAPI, driven in-process through `httpx.ASGITransport`

`tests/integration/test_foo_http.py` — the app built by the same factory the process definition calls,
over the suite's own engine, driven on the test's event loop:

```python
from collections.abc import AsyncIterator

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from myapp.exceptions import InvalidPayloadError
from myapp.postgres import FooRepository
from myapp.web import build_app


@pytest.fixture
async def http(engine: AsyncEngine) -> AsyncIterator[httpx.AsyncClient]:
    app = build_app(FooRepository(engine))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://app") as client:
        yield client


async def test_a_posted_foo_reaches_the_run_function(http: httpx.AsyncClient) -> None:
    response = await http.post("/foos", json={"ref": "alpha", "name": "a", "sent_at": "2024-01-01T00:00:00Z"})

    assert response.json() == {"recorded": 1}


async def test_a_malformed_body_arrives_as_an_invalid_request(http: httpx.AsyncClient) -> None:
    response = await http.post("/foos", json={"name": "a"})

    assert response.status_code == 422
    assert response.json()["code"] == InvalidPayloadError.code
```

The in-process transport runs the app on the test's own event loop, which is the loop the
session-scoped engine was opened on (`flat-test-integration-setup`); a harness that runs the app on a
loop of its own, as FastAPI's synchronous `TestClient` does, would hand that engine's connections to a
second loop. Where a route's run function also calls an upstream, the fixture takes `foo_client` and
hands it to `build_app` as well; `respx` intercepts that client's outbound transport and leaves the
in-process one alone.

## Other bindings

- **A different upstream-stub mechanism** — a transport handed to the client, a local stub server, a
  recorded cassette (`flat-test-service-client` names the trade-offs). Only how the upstream is pinned
  changes; rule 2's asymmetry — upstream substituted, datastore not — is the thing that must survive,
  because it is what makes this level catch wiring at all.
- **Another web framework's harness for the HTTP shape** — Starlette's, Litestar's or aiohttp's own
  in-process client. The two wrapper tests and what they assert are unchanged; the harness must drive the
  app on the loop the suite's engine lives on.
- **No framework wrapper at all.** A service triggered by a loop, a cron entry or a timer writes the
  run-function tests, and the containment test where the process outlives one run, and stops; nothing is missing, because there is no wrapper to prove.
- **An engine whose harness cannot skip time.** The retry test then asserts the *declared* policy on the
  orchestration's own declaration rather than observing the attempts — a weaker test, and the honest one.
  Waiting out a real backoff is still forbidden, and every obligation below is unchanged.
- **A replay harness over recorded histories**, where the engine ships one. It pins determinism across a
  code change, which none of the tests here do, and it cannot pin a *new* orchestration's behaviour
  because there is no history yet. It is an addition to the orchestration test file, never a
  replacement.

## Rules

1. **A run function takes what it needs as parameters** — `flat-entrypoint` rule 3, which is what lets
   this level point it at the test container.
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
4. **Assert on rows, and on the returned aggregate** — never on log lines (`test-principles`). A run that
   logged `"ok"` and wrote nothing must fail, and a process's containment is asserted on what its guard
   returns. A service with no store asserts on the requests the stubbed transport recorded and on the
   aggregate.
5. **A wrapper test proves the wrapper, not the body.** One happy path and one exception translation:
   that the trigger reaches the body, and that a service failure arrives at the framework as a typed
   failure carrying the original's identity rather than an opaque one.
6. **The wrapper body never diverges from the run function** — it calls it and holds no logic of its own.
   A divergence means two triggers of the same work are drifting apart, and the tests must not paper
   over it.
7. **A run that fans out over independent units is tested with one unit failing inside its write**,
   asserting that the other units' rows landed and that the run's failure names the failed unit
   (`flat-entrypoint` rules 11 and 13).

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
4. **A run id is generated fresh per test**, so a re-run cannot collide with a retained execution from a
   previous one.
5. **A batch-loop orchestration is tested against `flat-entrypoint`'s durable obligation 6**: one test
   that the loop ends on an empty batch, and one that a continuation carries every value the next run
   reads, each seeded so that a dropped value changes the observed result. Neither mistake is visible
   from the happy path.
6. **Schedule creation is not tested here.** It is a one-off deploy-time definition, not application
   code, and a test of it would assert only that the engine's SDK works. What *is* worth pinning
   statically is that every schedule's routing name matches one some process actually serves —
   `flat-entrypoint` rule 6.

## Hard stops

- `run_once` reaches for a module-level engine instead of taking one → stop, use `flat-entrypoint`
  rule 3 and add the parameter.
- A run-once process gets a containment test → stop, it has no guard; its failure is its exit status.
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
- A batch-loop orchestration ships with only the happy-path test → stop, test the empty-batch end and
  the carried values (`flat-entrypoint` durable obligation 6); a continuation that drops a value is
  invisible from the happy path.
- A schedule definition is being unit-tested → stop, it is deploy-time infrastructure; pin the routing
  name statically instead (`flat-entrypoint` rule 6).
