---
name: hex-test-capability-adapter
description: Use when testing the infrastructure adapter behind an `ICan<Verb>` capability port in one of its three flavours — a containerized backend through testcontainers, an HTTP gateway intercepted with `respx` over real `httpx`, or a pure-CPU parser, renderer or verifier — asserting the SDK-error to catalogue-exception translation row by row. Not a repository adapter, which is `hex-test-repository-contract`, and not a token verifier, which is `hex-test-restapi-auth`.
---

# Hex Test — Capability Adapter

Consult `test-principles` for the testing constitution. Where this skill contradicts `test-principles`, the constitution wins.

Produces one test file per capability adapter. Catches what unit-level coverage cannot: real SDK exception shapes, real upstream wire format, real crypto/parsing behavior, and the SDK-exception-to-domain-exception translator's mapping. This is the capability-adapter analogue of `hex-test-repository-contract` for repository adapters.

## When to use vs. neighbours

- A new or modified adapter under `infrastructure/<adapter>/` (not `infrastructure/postgres/repositories/`) → this skill, in whichever of the three flavours the adapter is.
- A repository adapter, relational or client-store → `hex-test-repository-contract`, not this skill. The port tells them apart — `IFooRepository` there, `ICan<Verb>` here.
- The adapter under test itself → `hex-capability-adapter`; the `ICan<Verb>` protocol it satisfies → `hex-domain-ports`.
- A fake of this capability that the unit-test layer consumes → `hex-test-application-handler`. The fake's exception contract must match what the integration test pins here.
- A handler test that consumes such a fake → `hex-test-application-handler`.
- The rollback / container `conftest.py` itself — including "add a testcontainer fixture" → `hex-test-integration-setup` (one-shot). This skill only consumes the resource fixtures it defines.
- HTTP-layer (route + OpenAPI) → `hex-test-restapi-endpoint`.
- The token-verifier adapter's own test, and every other auth fixture → `hex-test-restapi-auth` (`UNIT.md` for the verifier); it is this skill's pure-CPU flavor bound to auth, and it lives there so auth is taught in one place.
- The catalogue exception the translator raises, or a new row in it → `exception-catalog`.
- Speed targets, the substitution ladder and marker rules → `test-principles`.
- A pure domain entity, value object, enum or service, with no adapter and no IO → `hex-test-domain`.
- A flat-layered service's `*_client.py` stubbed with `respx` → `flat-test-service-client`, in the `pyhouse-flat` plugin; this skill's HTTP-gateway flavor is for an adapter behind an `ICan<Verb>` port, not for a flat client class.

## Template(s) — pytest, respx over httpx

Filename examples (`naming` owns the rule): `test_<tech>_<aggregate_or_area>.py` (containerized / respx) or `test_<tech>_<verb>.py` (CPU).

### Pick the flavor

- **Containerized backend.** Adapter speaks to a service that runs in a Testcontainer (an object store, a broker, a cache). Drives the real client against the real container; consumes the resource fixtures from the integration conftest. **Lives under `tests/integration/<adapter>/`.**
- **HTTP gateway with `respx`.** Adapter speaks `httpx` to a third-party HTTP API. Wraps the real `httpx.AsyncClient` with `respx.mock` and asserts the request shape (URL, headers, body) on the way out and the translated response on the way back. The adapter code is real; only the network is intercepted. Nothing runs, so it is a boundary unit test (`test-principles`) and **lives under `tests/unit/infrastructure/<adapter>/`**, clear of the integration tree's container and migration fixtures.
- **Pure-CPU.** Adapter does no IO — a parser, a renderer over in-memory bytes, a verifier. Stdlib + the real parsing / crypto library. No fixtures, no containers. **Lives under `tests/unit/infrastructure/<adapter>/`.**

The flavor mirrors the adapter's form in `hex-capability-adapter` — an SDK client, an HTTP gateway (the one it templates) or sync pure CPU. If two flavors are asked for in one file, split — one file per adapter, but `integration/` for a test that needs a running backend and `unit/` for everything else means a containerized adapter and a gateway or CPU adapter live in different roots regardless.

### Containerized backend

`tests/integration/<adapter>/test_<tech>_<aggregate>_<adapter>.py`, driving the real SDK client against
a container the integration conftest starts (`hex-test-integration-setup`, obligation 9; its key-value
add-on is the worked instance of a per-test namespace). One happy-path test per public method, observed by reading the
backend directly; one test per error code the adapter translates, each triggered where the backend
really reports it and asserting the catalogue class and its `context`; and the fallback — a client with
credentials the backend refuses — landing on the upstream error (rule 9). A reversing method the
compensation path calls (a delete) pins success on a key that was never written, where the backend
answers success for it, rather than a not-found it can never raise.

### HTTP gateway with `respx`

```
tests/unit/infrastructure/<adapter>/
└── test_http_<vendor>_gateway.py
```

```python
import json
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import httpx
import pytest
import respx
from pydantic import SecretStr

from myapp.domain.bars import BarToken
from myapp.domain.exceptions import NotFoundError, UpstreamError
from myapp.infrastructure.http import BarGatewaySettings, HttpBarGateway

_BASE_URL = "https://api.bar.example"


@pytest.fixture
def settings() -> BarGatewaySettings:
    return BarGatewaySettings(base_url=_BASE_URL, api_key=SecretStr("test-key"), timeout_seconds=5.0)


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    async with httpx.AsyncClient() as c:
        yield c


@respx.mock
async def test_fetch_token_happy_path(
    client: httpx.AsyncClient,
    settings: BarGatewaySettings,
) -> None:
    route = respx.post(f"{_BASE_URL}/tokens").mock(
        return_value=httpx.Response(200, json={"token": "tok-1", "expires_at": "2030-01-01T00:00:00Z"}),
    )
    adapter = HttpBarGateway(client=client, settings=settings)

    token = await adapter.fetch_token(subject="alice")

    assert token == BarToken(value="tok-1", expires_at=datetime(2030, 1, 1, tzinfo=UTC))
    assert route.called
    request = route.calls.last.request
    assert request.headers["Authorization"] == "Bearer test-key"
    assert json.loads(request.content) == {"subject": "alice"}


@respx.mock
async def test_fetch_token_malformed_body_raises_upstream(
    client: httpx.AsyncClient,
    settings: BarGatewaySettings,
) -> None:
    respx.post(f"{_BASE_URL}/tokens").mock(return_value=httpx.Response(200, json={"token": "tok-1"}))
    adapter = HttpBarGateway(client=client, settings=settings)

    with pytest.raises(UpstreamError) as exc:
        await adapter.fetch_token(subject="alice")

    assert exc.value.context == {"subject": "alice", "reason": "KeyError"}


@respx.mock
async def test_fetch_token_404_raises_not_found(
    client: httpx.AsyncClient,
    settings: BarGatewaySettings,
) -> None:
    respx.post(f"{_BASE_URL}/tokens").mock(return_value=httpx.Response(404))
    adapter = HttpBarGateway(client=client, settings=settings)

    with pytest.raises(NotFoundError) as exc:
        await adapter.fetch_token(subject="missing")

    assert exc.value.context == {"subject": "missing", "status": 404}


@respx.mock
async def test_fetch_token_network_error_raises_upstream(
    client: httpx.AsyncClient,
    settings: BarGatewaySettings,
) -> None:
    respx.post(f"{_BASE_URL}/tokens").mock(side_effect=httpx.ConnectError("boom"))
    adapter = HttpBarGateway(client=client, settings=settings)

    with pytest.raises(UpstreamError) as exc:
        await adapter.fetch_token(subject="alice")

    assert exc.value.context["reason"] == "ConnectError"


@respx.mock
async def test_fetch_token_read_timeout_raises_upstream(
    client: httpx.AsyncClient,
    settings: BarGatewaySettings,
) -> None:
    respx.post(f"{_BASE_URL}/tokens").mock(side_effect=httpx.ReadTimeout("slow"))
    adapter = HttpBarGateway(client=client, settings=settings)

    with pytest.raises(UpstreamError) as exc:
        await adapter.fetch_token(subject="alice")

    assert exc.value.context["reason"] == "ReadTimeout"
```

A `200` whose body lacks a field the domain type needs is the parse arm's case: without the adapter's
translation around the parse, the `KeyError` escapes and the test reds. Every other status row the
adapter maps — a `400` to the validation error, the fallback to the upstream error — is the `404` test
again with its own code, exception and `context` (rule 5).

The outgoing body is compared as parsed JSON, never as bytes: separators and key order are the
client library's serialisation choice, not the upstream's contract, and a byte comparison breaks on a
library upgrade that changed nothing on the wire that matters.

### Pure-CPU

`tests/unit/infrastructure/<adapter>/test_<tech>_<verb>.py`. The worked instance is the token verifier's
test in `hex-test-restapi-auth`'s `UNIT.md`: module-level settings and inputs, the adapter built inline
in each test, real library calls, and one test per `raise` site asserting its `context` key (rule 21).

## Other bindings

- **Another interception mechanism, or none.** A stub server on a loopback port, recorded cassettes, or a
  transport substituted into the real client all hold the adapter real while the socket is not, which is
  all rules 8, 9 and 16–19 ask for; what changes is how the interception is installed and how the
  outgoing request is read back. What no mechanism excuses: replacing the client object the adapter
  holds is a mock of the code under test, and the SDK-shape defects this file exists to catch stop being
  catchable.
- **A pre-provisioned backend instead of a disposable container.** Provisioning is
  `hex-test-integration-setup`'s (`## Other bindings`). The per-test namespace and its teardown (rule
  14) get *more* load-bearing, not less — a shared instance keeps whatever a test leaves behind.

## Rules

Consult `test-principles` for the testing constitution and `exception-catalog` for the error catalogue and boundary translation.

### Form

1. **One test file per adapter.** Consult `naming` for naming; the template paths show the adapter-specific forms.
2. **Path follows the flavor, and the flavor follows whether the test needs something running.** A test that needs a live backend is an integration test (`tests/integration/<adapter>/`). A test whose socket is intercepted, and a pure-CPU adapter that touches nothing, need nothing running and are unit tests (`tests/unit/infrastructure/<adapter>/`) — the intercepted one is `test-principles`' boundary unit. Putting either under `integration/` makes it inherit that tree's container and migration fixtures and pay for infrastructure it never uses.
3. **Module-level helpers, not fixtures, for settings / keypairs / fixed inputs** in CPU tests. Construct once at module scope.

### Coverage

4. **Every public method gets a happy-path test.** Drive the adapter; assert the observable side effect (the object exists in the backend, the request matches the upstream's contract, the return value equals a literal).
5. **Every row of the adapter's error mapping (`_map_status` in the template) gets a dedicated test.** The bug class "translator handles error code X but not Y" only surfaces when each row is exercised. A row the backend never actually reports on a given call — an object store's delete of an absent key answers success — is exercised on a call where it does, and the call that cannot raise it pins its success instead.
6. **`assert exc.value.context["<key>"] == <value>` on every translated exception.** This is the capability-adapter analogue of the `context["constraint"]` rule in `hex-test-repository-contract`. The fake-based handler test cannot verify this — only this test can.
7. **A verification probe that reads the backend directly names the SDK's own error class**, as the narrowest class the probe can raise (`test-principles` *Assert strength* recipe 6), and asserts the error code that distinguishes "absent" from "unreachable" or "unauthorized". This is the one place an SDK exception is legitimate in a test — the probe is not going through the adapter, so there is nothing translated to assert on. Asserting on an adapter call still follows the hard stop below: the translated `MyappError` subclass, never the SDK's class.
8. **For HTTP gateways, also assert the request shape** at least once: URL, method, headers (especially `Authorization`), and body. This pins the wire contract against the upstream, not just the error translation.
9. **A failure that never reaches the upstream is covered too, and lands on the upstream error.** The HTTP-gateway flavor needs a connect-refused and a read-timeout case (`ConnectError` / `ReadTimeout` here) asserting `UpstreamError`; the containerized flavor needs a wrong-container or wrong-credential case asserting the fallback translation. Every row of the adapter's error mapping (`_map_status` in the template) can pass while the transport arm is unexercised, which is the arm that fires in a real outage.

### Real, not mocked

10. **Use the real SDK client.** Consult `test-principles` for the prohibition on mocks. The SDK is the boundary; mocking it defeats the test's purpose (catching mismatches between assumed and actual SDK exception shapes).
11. **Intercepting the network is not mocking the subject.** The client object and the adapter both stay real; only the socket is replaced — the HTTP analogue of running the real store in a container. Handing the adapter a stand-in client instead crosses back into mocking the code under test.
12. **No fake / in-memory implementation of the protocol in this test.** Fakes are for handler unit tests (`hex-test-application-handler`). This test exercises the real adapter — that's the whole point.

### Containerized flavor specifics

13. **Take the resource fixture, not raw settings.** Containerized adapters need a live client and settings naming the test's own namespace (the key-value add-on's `redis_client`, for one). Both come from the integration conftest — session scope for the container and the client, function scope for the namespace. The one exception is the rejected-credential case (rule 9), which builds a client with credentials the backend refuses.
14. **Isolate by a per-test namespace with teardown; there is no rollback at this layer.** An object store, a cache or a queue has no nested transaction to discard. Which fixture owns the per-test namespace and which the session-scoped container and client → `hex-test-integration-setup` (obligation 9 and its scope split).
15. **Don't bypass the adapter to drive setup.** For success assertions, you may inspect the backend directly — that is the observation. But for setup that exists to drive the test, go through the adapter (`adapter.upload(...)` then `adapter.delete(...)`).

### HTTP-gateway flavor specifics

16. The interception is active before any request is made → `test-principles`, *Intercepting HTTP* rule 1.
17. Each stubbed route matches one exact method and URL → `test-principles`, *Intercepting HTTP* rule 2.
18. Every happy-path test asserts the route it exercises was hit, on that route's own call record (`route.called` here) → `test-principles`, *Intercepting HTTP* rule 3.
19. A transport failure is triggered with a transport-level error, not a status code → `test-principles`, *Intercepting HTTP* rule 4. Rule 9 names the two cases this flavor needs.

### CPU flavor specifics

20. **Real parsing, real crypto.** Drive the actual library: feed a parser real inputs and assert literal outputs; for a verifier, generate a real key at module scope and sign with the real library. Never hand the adapter a pre-baked value the library never produced.
21. **One `test_*` per `raise` site in the adapter** — each library-exception arm *and* each guard the adapter raises itself. Each test triggers exactly one, and asserts the `context` key that arm sets (Rule 6).
22. **No fixtures.** Pure-CPU adapters are constructed in-line in each test from module-level settings. They have no lifecycle.

## Inlined typing / import rules

- `pytest`, `respx` (HTTP flavor), `httpx`, the real parsing / crypto library (CPU flavor), the real SDK, `myapp.domain.*`, `myapp.infrastructure.<adapter>` — imported from the package, not its inner module (`python-packaging`). No `myapp.application.*`, no `myapp.restapi.*`.
- Full annotations on every test signature, and a yielding fixture is annotated `AsyncIterator[T]` / `Iterator[T]`. Resource-fixture types (`Session`, `httpx.AsyncClient`) come from the SDK / library, not the project.
- No `from __future__ import annotations`.

## Hard stops

- Nothing up-tree provides the live backend a containerized flavor drives (the key-value add-on's fixtures, for one) → stop, use `hex-test-integration-setup` to extend the fixtures first; what the flavor needs is the running backend, not a particular fixture name.
- Asked for a mock of the SDK client, or for a layer or async marker → stop, use `test-principles`; the SDK boundary is exactly what this test exists to verify.
- Asked to mock the adapter itself → stop, use `hex-test-application-handler`.
- Asked to assert `pytest.raises(<SdkExceptionClass>)` directly → stop, use `exception-catalog` for boundary translation; assert the translated `MyappError` subclass.
- Asked to assert on a translated exception without checking `context` keys → stop, check the context keys; the context map is the load-bearing contract this test exists to pin.
- Asked for a happy-path test only with no error-translation cases → stop, cover the exception map row-by-row.
- A test references FastAPI, `httpx.AsyncClient` over `ASGITransport` or the DI container → stop, use `hex-test-restapi-endpoint`.
- A pure-CPU adapter's test is given `respx` or a container → stop, check the adapter classification; pure-CPU code needs neither, and an adapter with IO is mis-classified.
- Asked for a token-verifier test here → stop, use `hex-test-restapi-auth`; the flavor is this skill's, the example is not, and duplicating it teaches auth twice.
