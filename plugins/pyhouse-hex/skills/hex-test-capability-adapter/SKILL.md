---
name: hex-test-capability-adapter
description: Use when testing the infrastructure adapter behind an `ICan<Verb>` capability port in one of its three flavours — a containerized backend through testcontainers, an HTTP gateway intercepted with `respx` over real `httpx`, or a pure-CPU canonicalizer or renderer — asserting the SDK-error to catalogue-exception translation row by row. Not a repository adapter, which is `hex-test-repository-contract`, and not a token verifier, which is `hex-test-restapi-auth`.
---

# Hex Test — Capability Adapter

Consult `test-principles` for the testing constitution. Where this skill contradicts `test-principles`, the constitution wins.

Produces one test file per capability adapter. Catches what unit-level coverage cannot: real SDK exception shapes, real upstream wire format, real crypto/parsing behavior, and the SDK-exception-to-domain-exception translator's mapping. This is the capability-adapter analogue of `hex-test-repository-contract` for SQLAlchemy repositories.

## When to use vs. neighbours

- A new or modified adapter under `infrastructure/<adapter>/` (not `infrastructure/postgres/repositories/`) → this skill, in whichever of the three flavours the adapter is.
- A repository adapter, relational or client-store → `hex-test-repository-contract`, not this skill. The port tells them apart — `IFooRepository` there, `ICan<Verb>` here.
- The adapter under test itself → `hex-capability-adapter`; the `ICan<Verb>` protocol it satisfies → `hex-domain-ports`.
- A fake of this capability that the unit-test layer consumes → `hex-test-application-handler`. The fake's exception contract must match what the integration test pins here.
- A handler test that consumes such a fake → `hex-test-application-handler`.
- The rollback / container `conftest.py` itself — including "add a testcontainer fixture for Postgres or MinIO" → `hex-test-integration-setup` (one-shot). This skill only consumes the resource fixtures it defines.
- HTTP-layer (route + OpenAPI) → `hex-test-restapi-endpoint`.
- The token-verifier adapter's own test, and every other auth fixture → `hex-test-restapi-auth` (`UNIT.md` for the verifier); it is this skill's pure-CPU flavor bound to auth, and it lives there so auth is taught in one place.
- The catalogue exception the translator raises, or a new row in it → `exception-catalog`.
- Speed targets, the substitution ladder and marker rules → `test-principles`.
- A pure domain entity, value object, enum or service, with no adapter and no IO → `hex-test-domain`.
- A flat-layered service's `*_client.py` stubbed with `respx` → `flat-test-service-client`, in the `pyhouse-flat` plugin; this skill's HTTP-gateway flavor is for an adapter behind an `ICan<Verb>` port, not for a flat client class.

## Template(s) — pytest, testcontainers, respx over httpx

Filename examples (`naming` owns the rule): `test_<tech>_<aggregate_or_area>.py` (containerized / respx) or `test_<tech>_<verb>.py` (CPU).

### Pick the flavor

- **Containerized backend.** Adapter speaks to a service that runs in a Testcontainer (MinIO for S3, Postgres for non-aggregate stores, Redis, Kafka). Drives the real client against the real container; consumes a resource fixture (`s3`, `minio_bucket`, `redis`) from the integration conftest. **Lives under `tests/integration/<adapter>/`.**
- **HTTP gateway with `respx`.** Adapter speaks `httpx` to a third-party HTTP API. Wraps the real `httpx.AsyncClient` with `respx.mock` and asserts the request shape (URL, headers, body) on the way out and the translated response on the way back. The adapter code is real; only the network is intercepted. **Lives under `tests/integration/<adapter>/`.**
- **Pure-CPU.** Adapter does no IO — a canonicalizer, a renderer over in-memory bytes, a verifier. Stdlib + the real parsing / crypto library. No fixtures, no containers. **Lives under `tests/unit/infrastructure/<adapter>/`.**

The flavor mirrors the adapter's template in `hex-capability-adapter` (real-SDK, HTTP gateway, sync pure-CPU). If the spec asks for two flavors in one file, split — one file per adapter, but `unit/` for pure-CPU and `integration/` for IO-bearing means a containerized adapter and a CPU adapter live in different roots regardless.

### Containerized backend (S3 / MinIO via the `s3` fixture)

```
tests/integration/<adapter>/
└── test_<tech>_<aggregate>_<adapter>.py
```

```python
import pytest
from aioboto3 import Session
from botocore.exceptions import ClientError

from myapp.domain.exceptions import NotFoundError, UpstreamError
from myapp.infrastructure.s3.s3_foo_storage import S3FooStorage
from myapp.infrastructure.s3.settings import StorageSettings

async def test_upload_then_head_object_succeeds(
    s3_session: Session,
    storage_settings: StorageSettings,
) -> None:
    adapter = S3FooStorage(session=s3_session, settings=storage_settings)
    await adapter.upload(key="foos/alpha", body=b"payload")

    async with s3_session.client("s3", endpoint_url=str(storage_settings.endpoint_url)) as s3:
        head = await s3.head_object(Bucket=storage_settings.bucket, Key="foos/alpha")
    assert head["ContentLength"] == len(b"payload")

async def test_delete_removes_object(
    s3_session: Session,
    storage_settings: StorageSettings,
) -> None:
    adapter = S3FooStorage(session=s3_session, settings=storage_settings)
    await adapter.upload(key="foos/alpha", body=b"payload")

    await adapter.delete(key="foos/alpha")

    # Verify at the backend, not through the adapter — but name the SDK's own error
    # class. A bare `pytest.raises(Exception)` passes on a typo in the bucket name, a
    # closed session, or an expired credential, and would call the delete a success.
    async with s3_session.client("s3", endpoint_url=str(storage_settings.endpoint_url)) as s3:
        with pytest.raises(ClientError) as exc:
            await s3.head_object(Bucket=storage_settings.bucket, Key="foos/alpha")
    assert exc.value.response["Error"]["Code"] in {"404", "NoSuchKey"}

async def test_delete_missing_object_raises_not_found(
    s3_session: Session,
    storage_settings: StorageSettings,
) -> None:
    adapter = S3FooStorage(session=s3_session, settings=storage_settings)

    with pytest.raises(NotFoundError) as exc:
        await adapter.delete(key="foos/never-uploaded")

    assert exc.value.context["key"] == "foos/never-uploaded"
    assert exc.value.context["code"] == "NoSuchKey"

async def test_upload_to_nonexistent_bucket_raises_upstream_error(
    s3_session: Session,
    storage_settings: StorageSettings,
) -> None:
    bad_settings = storage_settings.model_copy(update={"bucket": "does-not-exist"})
    adapter = S3FooStorage(session=s3_session, settings=bad_settings)

    with pytest.raises((NotFoundError, UpstreamError)) as exc:
        await adapter.upload(key="foos/x", body=b"x")

    assert "code" in exc.value.context
```

### HTTP gateway with `respx`

```
tests/integration/<adapter>/
└── test_http_<vendor>_gateway.py
```

```python
import httpx
import pytest
import respx

from myapp.domain.bars import BarToken
from myapp.domain.exceptions import NotFoundError, UpstreamError, ValidationError
from myapp.infrastructure.bar.http_bar_gateway import HttpBarGateway
from myapp.infrastructure.bar.settings import BarGatewaySettings

_BASE_URL = "https://api.bar.example"

@pytest.fixture
def settings() -> BarGatewaySettings:
    return BarGatewaySettings(base_url=_BASE_URL, api_key="test-key")

@pytest.fixture
async def client() -> httpx.AsyncClient:
    async with httpx.AsyncClient() as c:
        yield c

@respx.mock
async def test_fetch_token_happy_path(
    client: httpx.AsyncClient, settings: BarGatewaySettings,
) -> None:
    route = respx.post(f"{_BASE_URL}/tokens").mock(
        return_value=httpx.Response(200, json={"token": "tok-1", "expires_at": "2030-01-01T00:00:00Z"}),
    )
    adapter = HttpBarGateway(client=client, settings=settings)

    token = await adapter.fetch_token(subject="alice")

    assert token == BarToken(value="tok-1", expires_at="2030-01-01T00:00:00Z")
    assert route.called
    request = route.calls.last.request
    assert request.headers["Authorization"] == "Bearer test-key"
    assert request.read() == b'{"subject": "alice"}'

@respx.mock
async def test_fetch_token_404_raises_not_found(
    client: httpx.AsyncClient, settings: BarGatewaySettings,
) -> None:
    respx.post(f"{_BASE_URL}/tokens").mock(return_value=httpx.Response(404))
    adapter = HttpBarGateway(client=client, settings=settings)

    with pytest.raises(NotFoundError) as exc:
        await adapter.fetch_token(subject="missing")

    assert exc.value.context == {"subject": "missing", "status": 404}

@respx.mock
async def test_fetch_token_400_raises_validation(
    client: httpx.AsyncClient, settings: BarGatewaySettings,
) -> None:
    respx.post(f"{_BASE_URL}/tokens").mock(return_value=httpx.Response(400))
    adapter = HttpBarGateway(client=client, settings=settings)

    with pytest.raises(ValidationError) as exc:
        await adapter.fetch_token(subject="malformed")

    assert exc.value.context == {"subject": "malformed", "status": 400}

@respx.mock
async def test_fetch_token_503_raises_upstream(
    client: httpx.AsyncClient, settings: BarGatewaySettings,
) -> None:
    respx.post(f"{_BASE_URL}/tokens").mock(return_value=httpx.Response(503))
    adapter = HttpBarGateway(client=client, settings=settings)

    with pytest.raises(UpstreamError) as exc:
        await adapter.fetch_token(subject="alice")

    assert exc.value.context == {"subject": "alice", "status": 503}

@respx.mock
async def test_fetch_token_network_error_raises_upstream(
    client: httpx.AsyncClient, settings: BarGatewaySettings,
) -> None:
    respx.post(f"{_BASE_URL}/tokens").mock(side_effect=httpx.ConnectError("boom"))
    adapter = HttpBarGateway(client=client, settings=settings)

    with pytest.raises(UpstreamError) as exc:
        await adapter.fetch_token(subject="alice")

    assert exc.value.context["reason"] == "ConnectError"
```

### Pure-CPU canonicalizer / renderer

```
tests/unit/infrastructure/<adapter>/
└── test_<tech>_<verb>.py
```

```python
import pytest

from myapp.domain.bars import CanonicalBarUrl
from myapp.domain.exceptions import ValidationError
from myapp.infrastructure.idna.idna_bar_url_canonicalizer import IdnaBarUrlCanonicalizer
from myapp.infrastructure.idna.settings import CanonicalizerSettings

_SETTINGS = CanonicalizerSettings(allowed_schemes=frozenset({"http", "https"}))

def test_canonicalize_returns_canonical_url() -> None:
    canonicalizer = IdnaBarUrlCanonicalizer(settings=_SETTINGS)

    result = canonicalizer.canonicalize("  https://example.com/a?b=1#frag  ")

    assert result == CanonicalBarUrl(value="https://example.com/a?b=1")

def test_canonicalize_punycodes_an_international_host() -> None:
    canonicalizer = IdnaBarUrlCanonicalizer(settings=_SETTINGS)

    result = canonicalizer.canonicalize("https://bücher.example/")

    assert result == CanonicalBarUrl(value="https://xn--bcher-kva.example/")

def test_canonicalize_unsupported_scheme_raises_validation_error() -> None:
    canonicalizer = IdnaBarUrlCanonicalizer(settings=_SETTINGS)

    with pytest.raises(ValidationError) as exc:
        canonicalizer.canonicalize("ftp://example.com/a")

    assert exc.value.context["scheme"] == "ftp"

def test_canonicalize_invalid_host_raises_validation_error() -> None:
    canonicalizer = IdnaBarUrlCanonicalizer(settings=_SETTINGS)

    with pytest.raises(ValidationError) as exc:
        canonicalizer.canonicalize("https://-bad-.example/")

    assert exc.value.context["host"] == "-bad-.example"
    assert exc.value.context["reason"] in {
        "IDNAError", "InvalidCodepoint", "IDNABidiError",
    }
```

The last two tests are the adapter's two `raise` sites — its own guard and the library's `IDNAError`
arm — which is Rule 20 applied to a canonicalizer: one test per arm, each asserting the `context` key
that arm sets. The `reason` set is open because the library raises `IDNAError` subclasses whose exact
name is not a contract; what is pinned is that the failure arrives as the catalogue's own exception.

## Other bindings

- **Another interception mechanism, or none.** A stub server on a loopback port, recorded cassettes, or a
  transport substituted into the real client all hold the adapter real while the socket is not, which is
  all rules 8, 9 and 16–19 ask for; what changes is how the interception is installed and how the
  outgoing request is read back. What no mechanism excuses: replacing the client object the adapter
  holds is a mock of the code under test, and the SDK-shape defects this file exists to catch stop being
  catchable.
- **A pre-provisioned backend instead of a disposable container.** A compose service or an instance the
  CI job supplies serves the containerized flavour; the fixture then reads an endpoint from a dedicated
  opt-in variable rather than starting anything. The per-test namespace and its teardown (rule 14) get
  *more* load-bearing, not less — a shared instance keeps whatever a test leaves behind.

## Rules

Consult `test-principles` for the testing constitution and `exception-catalog` for the error catalogue and boundary translation.

### Form

1. **One test file per adapter.** Consult `naming` for naming; the template paths show the adapter-specific forms.
2. **Path follows the flavor, and the flavor follows whether the test needs something running.** A test that needs a live backend or an intercepted socket is an integration test (`tests/integration/<adapter>/`); a pure-CPU adapter that touches nothing is a unit test (`tests/unit/infrastructure/<adapter>/`). Putting a pure-CPU test under `integration/` makes the whole unit run pay for infrastructure it never uses.
3. **Module-level helpers, not fixtures, for settings / keypairs / canonical inputs** in CPU tests. Construct once at module scope.

### Coverage

4. **Every public method gets a happy-path test.** Drive the adapter; assert the observable side effect (object exists in S3, response matches schema, return value equals literal).
5. **Every row of the adapter's `exception_map` gets a dedicated test.** The bug class "translator handles error code X but not Y" only surfaces when each row is exercised. Skipping translator rows is the most common gap.
6. **`assert exc.value.context["<key>"] == <value>` on every translated exception.** This is the capability-adapter analogue of the `context["constraint"]` rule in `hex-test-repository-contract`. The fake-based handler test cannot verify this — only this test can.
7. **A verification probe that reads the backend directly names the SDK's own error class**, never a bare `Exception`, and asserts the error code that distinguishes "absent" from "unreachable" or "unauthorized". This is the one place an SDK exception is legitimate in a test — the probe is not going through the adapter, so there is nothing translated to assert on. Asserting on an adapter call still follows the hard stop below: the translated `DomainError` subclass, never the SDK's class.
8. **For HTTP gateways, also assert the request shape** at least once: URL, method, headers (especially `Authorization`), and body. This pins the wire contract against the upstream, not just the error translation.
9. **A failure that never reaches the upstream is covered too, and lands on the upstream error.** The HTTP-gateway flavor needs a connect-refused and a read-timeout case (`ConnectError` / `ReadTimeout` here) asserting `UpstreamError`; the containerized flavor needs a wrong-container or wrong-credential case asserting the fallback translation. Every `exception_map` row can pass while the transport arm is unexercised, which is the arm that fires in a real outage.

### Real, not mocked

10. **Use the real SDK client.** Consult `test-principles` for the prohibition on mocks. The SDK is the boundary; mocking it defeats the test's purpose (catching mismatches between assumed and actual SDK exception shapes).
11. **Intercepting the network is not mocking the subject.** The client object and the adapter both stay real; only the socket is replaced — the HTTP analogue of running the real store in a container. Handing the adapter a stand-in client instead crosses back into mocking the code under test.
12. **No fake / in-memory implementation of the protocol in this test.** Fakes are for handler unit tests (`hex-test-application-handler`). This test exercises the real adapter — that's the whole point.

### Containerized flavor specifics

13. **Take the resource fixture, not raw settings.** Containerized adapters need a live client (`s3_session`, `redis`). The fixture comes from the integration conftest, scoped session for the container and function for per-test isolation.
14. **Isolate by a per-test namespace with teardown; there is no rollback at this layer.** A blob store, a cache or a queue has no nested transaction to discard, so each test owns a fresh prefix, key namespace or bucket, created before it and dropped after it. This is not a choice to defer to the spec — deferred, two projects answer it two ways and the second leaks state between tests. The split of ownership is by scope: the session-scoped container and client are `hex-test-integration-setup`'s, the per-test namespace and its teardown live beside these tests (the same split `hex-test-repository-contract` rule 15 makes).
15. **Don't bypass the adapter to drive setup.** For success assertions, you may inspect the backend directly (`s3.head_object`) — that is the observation. But for setup that exists to drive the test, go through the adapter (`adapter.upload(...)` then `adapter.delete(...)`).

### HTTP-gateway flavor specifics — interception binding: respx over httpx

16. **Install the interception for the whole test, never around one block inside it.** The decorator form (`@respx.mock`) covers fixture setup and adapter construction as well as the act; a context manager opened mid-test leaves any request made outside it going to the real network, which fails opaquely or — worse — reaches the real upstream.
17. **Each stubbed route matches one exact method-and-URL, never a catch-all.** A pattern broad enough to also match a request the test did not intend — a retry, a token refresh, a second endpoint — answers it too, and the test then passes without ever proving the call it was written for went where it should.
18. **Every happy-path test asserts the stubbed route was actually hit.** An interception layer answers whatever arrives and reports success by default, so an adapter that never made the call — an un-awaited coroutine is the standing case — passes a test that only checks the return value.
19. **Trigger a transport failure with a transport-level error, not a status code.** Only a raised connect or timeout error (`side_effect=httpx.ConnectError(...)`) reaches the adapter's transport-error arm; every status-code test lands on the response arm and leaves that branch unexercised.

### CPU flavor specifics

20. **Real parsing, real crypto.** Drive the actual library: feed a canonicalizer real inputs and assert literal outputs; for a verifier, generate a real key at module scope and sign with the real library. Never hand the adapter a pre-baked value the library never produced.
21. **One `test_*` per `raise` site in the adapter** — each library-exception arm *and* each guard the adapter raises itself. Each test triggers exactly one, and asserts the `context` key that arm sets. Skipping arms is the most common gap (Rule 5).
22. **No fixtures.** Pure-CPU adapters are constructed in-line in each test from module-level settings. They have no lifecycle.

## Inlined typing / import rules

- `pytest`, `respx` (HTTP flavor), `httpx`, the real parsing / crypto library (CPU flavor), the real SDK, `myapp.domain.*`, `myapp.infrastructure.<adapter>.*`. No `myapp.application.*`, no `myapp.restapi.*`.
- Full annotations on every test signature. Resource-fixture types (`Session`, `httpx.AsyncClient`) come from the SDK / library, not the project.
- No `from __future__ import annotations`.

## Hard stops

- Nothing session-scoped up-tree provides the live backend a containerized flavor drives (`s3_session`, `redis`, … under this catalogue's binding) → stop, use `hex-test-integration-setup` to extend the fixtures first; what the flavor needs is the running backend, not a particular fixture name.
- Spec asks for `unittest.mock` / `MagicMock` of the SDK client → stop, use `test-principles` for substitution rules; the SDK boundary is exactly what this test exists to verify.
- Spec asks to mock the adapter itself → stop, use `hex-test-application-handler`.
- Spec asks for `@pytest.mark.integration` or `@pytest.mark.asyncio` → stop, use `test-principles` for marker rules.
- Spec asks to assert `pytest.raises(<SdkExceptionClass>)` directly → stop, use `exception-catalog` for boundary translation; assert the translated `DomainError` subclass.
- Spec asks to assert on a translated exception without checking `context` keys → stop, check the context keys; the context map is the load-bearing contract this test exists to pin.
- Spec asks for a happy-path test only with no error-translation cases → stop, cover the exception map row-by-row.
- Spec includes FastAPI / `httpx.AsyncClient` over `ASGITransport` / DI container references → stop, use `hex-test-restapi-endpoint`.
- CPU adapter spec asks to use `respx` or a container → stop, check the adapter classification; pure-CPU code needs neither, and an adapter with IO is mis-classified.
- Spec asks for a token-verifier test here → stop, use `hex-test-restapi-auth`; the flavor is this skill's, the example is not, and duplicating it teaches auth twice.
