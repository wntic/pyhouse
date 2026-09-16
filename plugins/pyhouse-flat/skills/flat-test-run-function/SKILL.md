---
name: flat-test-run-function
description: Use when testing a flat service's `run_once` body end to end — real Postgres, upstream transport stubbed, an idempotence test every time — plus the loop's failure-containment test and the Temporal activity wrapper. Not the workflow's orchestration (`flat-test-temporal-workflow`) and not the client's transport (`flat-test-service-client`).
paths: ["**/tests/**"]
---

# Flat-Layered Test — Run Function

Consult `test-principles` for the testing constitution. Where this skill contradicts `test-principles`, the constitution wins.

A run function in `ingest/` or `jobs/` is where a flat-layered service composes everything, so its test
is the one that catches wiring: the client's output shape actually fits the table's columns, the filter
drops what it should, the kind reaches the registry. Three forms:

- **`run_once`** — the body, tested end to end against the real database with the upstream transport
  stubbed. Every service has one of these, whatever triggers it.
- **The loop's failure containment** — that one failed run does not kill the process. This is the
  default trigger's test (`flat-entrypoint`).
- **The durable-execution wrapper** — the same body under an engine's activity decorator, run through
  that engine's activity test harness. Only for a service that *earned* an engine; a service on a loop,
  a cron entry or a timer writes the first two and stops.

## When to use vs. neighbours

- The HTTP client the body calls → `flat-test-service-client`; this level substitutes that client's
  transport, never the client object itself.
- The tables, helpers and repository the body writes through → `flat-test-schema-package`.
- The container and isolation fixtures → `flat-test-integration-setup`.
- A Temporal **workflow** — orchestration, retry policy, batch loops → 
  `flat-test-temporal-workflow`. Nothing about workflows belongs here.
- Writing the run function, the `guarded` wrapper or the trigger itself, rather than testing it →
  `flat-entrypoint`.
- A pure filter or normalize function the body calls → a unit test with no fixtures; it does not belong
  here.
- The shared groundwork — the substitution ladder, reliability rules → `test-principles`.

## Template — `run_once` end to end (pytest, `respx` over `httpx`, real Postgres)

`services/foo_parser/tests/integration/test_foo_ingest.py`:

```python
import httpx
import pytest
import respx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from myschema.repositories.entities import EntitiesRepository
from myschema.tables.foo import foo_filtered_table, foo_raw_table
from myschema.tables.registry import entities_table, entity_kinds_table
from foo_parser.exceptions import FooClientError
from foo_parser.ingest.foo_ingest import run_once
from foo_parser.services.foo_client import FooClient

_BASE_URL = "https://foo.test"


def _client() -> FooClient:
    return FooClient(base_url=_BASE_URL)


@respx.mock
async def test_a_run_lands_raw_filtered_and_registry_rows(
    engine: AsyncEngine, conn: AsyncConnection
) -> None:
    respx.get(f"{_BASE_URL}/foos").mock(
        return_value=httpx.Response(200, json={"items": [{"id": "f1", "url": "HTTP://A.test/x"}]})
    )

    await run_once(_client(), EntitiesRepository(engine), engine)

    assert (await conn.execute(select(func.count()).select_from(foo_raw_table))).scalar_one() == 1
    identity = (await conn.execute(select(foo_filtered_table.c.identity))).scalar_one()
    kinds = (await conn.execute(select(entity_kinds_table.c.kind))).scalars().all()
    assert identity == "http://a.test/x"
    assert kinds == ["foo"]


@respx.mock
async def test_rows_the_filter_rejects_reach_raw_but_not_filtered(
    engine: AsyncEngine, conn: AsyncConnection
) -> None:
    respx.get(f"{_BASE_URL}/foos").mock(
        return_value=httpx.Response(200, json={"items": [{"id": "f1", "url": None}]})
    )

    await run_once(_client(), EntitiesRepository(engine), engine)

    assert (await conn.execute(select(func.count()).select_from(foo_raw_table))).scalar_one() == 1
    assert (
        await conn.execute(select(func.count()).select_from(foo_filtered_table))
    ).scalar_one() == 0


@respx.mock
async def test_a_second_run_over_the_same_batch_writes_no_duplicates(
    engine: AsyncEngine, conn: AsyncConnection
) -> None:
    respx.get(f"{_BASE_URL}/foos").mock(
        return_value=httpx.Response(200, json={"items": [{"id": "f1", "url": "http://a.test/x"}]})
    )
    await run_once(_client(), EntitiesRepository(engine), engine)

    await run_once(_client(), EntitiesRepository(engine), engine)

    assert (await conn.execute(select(func.count()).select_from(entities_table))).scalar_one() == 1


@respx.mock
async def test_a_run_reports_what_it_fetched_and_kept(engine: AsyncEngine) -> None:
    respx.get(f"{_BASE_URL}/foos").mock(
        return_value=httpx.Response(
            200,
            json={"items": [{"id": "f1", "url": "http://a.test/x"}, {"id": "f2", "url": None}]},
        )
    )

    result = await run_once(_client(), EntitiesRepository(engine), engine)

    assert (result.fetched, result.kept) == (2, 1)


@respx.mock
async def test_an_upstream_failure_propagates_and_writes_nothing(
    engine: AsyncEngine, conn: AsyncConnection
) -> None:
    respx.get(f"{_BASE_URL}/foos").mock(return_value=httpx.Response(503))

    with pytest.raises(FooClientError):
        await run_once(_client(), EntitiesRepository(engine), engine)

    assert (await conn.execute(select(func.count()).select_from(foo_raw_table))).scalar_one() == 0
```

The idempotence test is the one worth writing first. A producer runs on a schedule over a feed that
mostly repeats, so "the second run over the same batch changes nothing" is its central behaviour, and it
is the one a wrong `conflict_columns` list breaks.

The aggregate test matters because that return value is what the trigger reports — the workflow's
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

## Template — the activity wrapper (Temporal `ActivityEnvironment`)

`services/foo_parser/tests/integration/test_activities.py`:

```python
import httpx
import pytest
import respx
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine
from temporalio.exceptions import ApplicationError
from temporalio.testing import ActivityEnvironment

from myschema.repositories.entities import EntitiesRepository
from myschema.tables.registry import entities_table
from foo_parser.services.foo_client import FooClient
from foo_parser.temporal.activities import FooActivities

_BASE_URL = "https://foo.test"


def _activities(engine: AsyncEngine) -> FooActivities:
    return FooActivities(FooClient(base_url=_BASE_URL), EntitiesRepository(engine), engine)


@respx.mock
async def test_the_activity_performs_one_run(
    engine: AsyncEngine, conn: AsyncConnection
) -> None:
    respx.get(f"{_BASE_URL}/foos").mock(
        return_value=httpx.Response(200, json={"items": [{"id": "f1", "url": "http://a.test/x"}]})
    )

    await ActivityEnvironment().run(_activities(engine).run_foo_ingest)

    assert (await conn.execute(select(func.count()).select_from(entities_table))).scalar_one() == 1


@respx.mock
async def test_a_service_error_surfaces_as_an_application_error(engine: AsyncEngine) -> None:
    respx.get(f"{_BASE_URL}/foos").mock(return_value=httpx.Response(503))

    with pytest.raises(ApplicationError) as exc_info:
        await ActivityEnvironment().run(_activities(engine).run_foo_ingest)

    assert exc_info.value.type == "FooClientError"
```

Two tests are enough here when the activity delegates to `run_once`, which has its own file. Their job
is to prove the wrapper reaches the body and translates its failures — not to re-run the body's
coverage. The translation test is the one that earns its place: an untranslated exception reaches
Temporal as an opaque failure with the context stripped, and nothing else in the suite notices.

## Other bindings

- **A different upstream-stub mechanism** — a transport handed to the client, a local stub server, a
  recorded cassette (`flat-test-service-client` names the trade-offs). Only how the upstream is pinned
  changes; rule 2's asymmetry — upstream substituted, datastore not — is the thing that must survive,
  because it is what makes this level catch wiring at all.
- **A different durable-execution engine, or none.** Under another engine the wrapper test is still the
  same two tests, reach and translate, against whatever in-process activity harness that engine ships;
  the `run_once` tests do not change, because the body never imports the engine. Where no engine was
  earned the wrapper file does not exist and the loop's containment test is the only trigger-level test.
- **A different log-capture mechanism** for the containment test — a structured-log capture fixture, an
  injected recording logger. The assertion moves from the captured text to that recorder's events; rule 4
  still holds everywhere else, and the containment test stays the one place a log is the subject.

## Rules

1. **A run function takes what it needs as parameters** — the client, the repository, the engine. A body
   reaching for a module-level engine or a settings value cannot be pointed at the test container, and no
   test of it means anything.
2. **The upstream is substituted at its transport; the datastore is not substituted at all.** That
   asymmetry is what makes this level catch wiring: real columns, real constraints, real upsert
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
7. **Time is never slept.** A `time.sleep` or `asyncio.sleep` in a test is a defect.

## Hard stops

- `run_once` reaches for a module-level engine instead of taking one → stop, add the parameter; this is a
  change to the run function, and it is the change that makes it testable at all.
- A test drives the `while True` loop directly → stop, extract the guarded single-run call and test that;
  the loop itself is one `await asyncio.sleep` and needs no coverage.
- A test monkeypatches `asyncio.sleep` to break out of a loop → stop, that asserts the mechanism, not the
  behaviour.
- A wrapper test re-asserts everything the `run_once` test already covers → stop, the two files then
  change together for one reason; keep the wrapper test to the wrapper.
- A workflow is being exercised in this file → stop, workflows belong to
  `flat-test-temporal-workflow`; they need no database and starting one here wastes seconds.
- The wrapper body contains logic the run function does not → stop, move it down; the wrapper holds no
  logic.
