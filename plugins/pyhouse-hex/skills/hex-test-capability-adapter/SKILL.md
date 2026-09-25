---
name: hex-test-capability-adapter
description: Use when testing the infrastructure adapter behind an `ICan<Verb>` capability port in one of its three flavours — a containerized backend through testcontainers, an HTTP gateway intercepted with `respx` over real `httpx`, or a pure-CPU canonicalizer or renderer — asserting the SDK-error to catalogue-exception translation row by row. Not a repository adapter, which is `hex-test-repository-contract`, and not a token verifier, which is `hex-test-restapi-auth`.
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
- The rollback / container `conftest.py` itself — including "add a testcontainer fixture for Postgres or MinIO" → `hex-test-integration-setup` (one-shot). This skill only consumes the resource fixtures it defines.
- HTTP-layer (route + OpenAPI) → `hex-test-restapi-endpoint`.
- The token-verifier adapter's own test, and every other auth fixture → `hex-test-restapi-auth` (`UNIT.md` for the verifier); it is this skill's pure-CPU flavor bound to auth, and it lives there so auth is taught in one place.
- The catalogue exception the translator raises, or a new row in it → `exception-catalog`.
- Speed targets, the substitution ladder and marker rules → `test-principles`.
- A pure domain entity, value object, enum or service, with no adapter and no IO → `hex-test-domain`.
- A flat-layered service's `*_client.py` stubbed with `respx` → `flat-test-service-client`, in the `pyhouse-flat` plugin; this skill's HTTP-gateway flavor is for an adapter behind an `ICan<Verb>` port, not for a flat client class.

## Template(s) — pytest, testcontainers + aioboto3 over MinIO, respx over httpx, idna

Filename examples (`naming` owns the rule): `test_<tech>_<aggregate_or_area>.py` (containerized / respx) or `test_<tech>_<verb>.py` (CPU).

### Pick the flavor

- **Containerized backend.** Adapter speaks to a service that runs in a Testcontainer (MinIO for S3, Postgres for non-aggregate stores, Redis, Kafka). Drives the real client against the real container; consumes the resource fixtures (`s3_session`, `s3_settings`, `redis`) from the integration conftest. **Lives under `tests/integration/<adapter>/`.**
- **HTTP gateway with `respx`.** Adapter speaks `httpx` to a third-party HTTP API. Wraps the real `httpx.AsyncClient` with `respx.mock` and asserts the request shape (URL, headers, body) on the way out and the translated response on the way back. The adapter code is real; only the network is intercepted. Nothing runs, so it is a boundary unit test (`test-principles`) and **lives under `tests/unit/infrastructure/<adapter>/`**, clear of the integration tree's container and migration fixtures.
- **Pure-CPU.** Adapter does no IO — a canonicalizer, a renderer over in-memory bytes, a verifier. Stdlib + the real parsing / crypto library. No fixtures, no containers. **Lives under `tests/unit/infrastructure/<adapter>/`.**

The flavor mirrors the adapter's template in `hex-capability-adapter` (real-SDK, HTTP gateway, sync pure-CPU). If two flavors are asked for in one file, split — one file per adapter, but `integration/` for a test that needs a running backend and `unit/` for everything else means a containerized adapter and a gateway or CPU adapter live in different roots regardless.

### Containerized backend (S3 / MinIO via `s3_session` and `s3_settings`)

```
tests/integration/<adapter>/
└── test_<tech>_<aggregate>_<adapter>.py
```

`s3_settings` names a bucket created for this test alone and removed after it
(`hex-test-integration-setup`), so keys need no per-test prefix and nothing another test wrote is
visible here.

```python
import pytest
from aioboto3 import Session
from botocore.exceptions import ClientError

from myapp.domain.exceptions import NotFoundError, UpstreamError
from myapp.infrastructure.s3 import S3FooStorage, S3Settings

async def test_upload_then_head_object_succeeds(
    s3_session: Session,
    s3_settings: S3Settings,
) -> None:
    adapter = S3FooStorage(session=s3_session, settings=s3_settings)

    await adapter.upload(key="foos/alpha", body=b"payload")

    async with s3_session.client("s3", endpoint_url=str(s3_settings.endpoint_url)) as s3:
        head = await s3.head_object(Bucket=s3_settings.bucket, Key="foos/alpha")
    assert head["ContentLength"] == len(b"payload")

async def test_delete_removes_object(
    s3_session: Session,
    s3_settings: S3Settings,
) -> None:
    adapter = S3FooStorage(session=s3_session, settings=s3_settings)
    await adapter.upload(key="foos/alpha", body=b"payload")

    await adapter.delete(key="foos/alpha")

    # The probe names the SDK's own error class and the absent-object code (rule 7).
    async with s3_session.client("s3", endpoint_url=str(s3_settings.endpoint_url)) as s3:
        with pytest.raises(ClientError) as exc:
            await s3.head_object(Bucket=s3_settings.bucket, Key="foos/alpha")
    assert exc.value.response["Error"]["Code"] == "404"

async def test_delete_missing_object_is_a_no_op(
    s3_session: Session,
    s3_settings: S3Settings,
) -> None:
    adapter = S3FooStorage(session=s3_session, settings=s3_settings)

    await adapter.delete(key="foos/never-uploaded")

async def test_download_missing_object_raises_not_found(
    s3_session: Session,
    s3_settings: S3Settings,
) -> None:
    adapter = S3FooStorage(session=s3_session, settings=s3_settings)

    with pytest.raises(NotFoundError) as exc:
        await adapter.download(key="foos/never-uploaded")

    assert exc.value.context == {"key": "foos/never-uploaded", "code": "NoSuchKey"}

async def test_upload_to_missing_bucket_raises_not_found(
    s3_session: Session,
    s3_settings: S3Settings,
) -> None:
    missing = s3_settings.model_copy(update={"bucket": f"{s3_settings.bucket}-missing"})
    adapter = S3FooStorage(session=s3_session, settings=missing)

    with pytest.raises(NotFoundError) as exc:
        await adapter.upload(key="foos/x", body=b"x")

    assert exc.value.context == {"key": "foos/x", "code": "NoSuchBucket"}

async def test_upload_with_rejected_credentials_raises_upstream_error(
    s3_settings: S3Settings,
) -> None:
    rejected = Session(aws_access_key_id="rejected", aws_secret_access_key="rejected")
    adapter = S3FooStorage(session=rejected, settings=s3_settings)

    with pytest.raises(UpstreamError) as exc:
        await adapter.upload(key="foos/x", body=b"x")

    assert exc.value.context == {"key": "foos/x", "code": "InvalidAccessKeyId"}
```

**Delete is idempotent, so its missing-key case asserts success.** S3's `DeleteObject` answers `204`
whether or not the key existed, so the backend reports no absent-object code on that path, and a test
demanding `NotFoundError` from it can never pass. What the case pins is that the adapter adds no
existence check of its own: the undo a compensating handler calls (`hex-patterns`) must succeed on a
key whose upload never landed. The not-found row is exercised where the backend really reports one — a
read of an absent key (`NoSuchKey`) and a write to an absent bucket (`NoSuchBucket`). The
rejected-credential case is the fallback row (rule 9): its code maps to nothing specific, so it lands on
`UpstreamError`.

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
from myapp.domain.exceptions import NotFoundError, UpstreamError, ValidationError
from myapp.infrastructure.bar import BarGatewaySettings, HttpBarGateway

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
    client: httpx.AsyncClient, settings: BarGatewaySettings,
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
    client: httpx.AsyncClient, settings: BarGatewaySettings,
) -> None:
    respx.post(f"{_BASE_URL}/tokens").mock(return_value=httpx.Response(200, json={"token": "tok-1"}))
    adapter = HttpBarGateway(client=client, settings=settings)

    with pytest.raises(UpstreamError) as exc:
        await adapter.fetch_token(subject="alice")

    assert exc.value.context == {"subject": "alice", "reason": "KeyError"}

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

@respx.mock
async def test_fetch_token_read_timeout_raises_upstream(
    client: httpx.AsyncClient, settings: BarGatewaySettings,
) -> None:
    respx.post(f"{_BASE_URL}/tokens").mock(side_effect=httpx.ReadTimeout("slow"))
    adapter = HttpBarGateway(client=client, settings=settings)

    with pytest.raises(UpstreamError) as exc:
        await adapter.fetch_token(subject="alice")

    assert exc.value.context["reason"] == "ReadTimeout"
```

A `200` whose body lacks a field the domain type needs is the parse arm's case: without the adapter's
translation around the parse, the `KeyError` escapes and the test reds.

The outgoing body is compared as parsed JSON, never as bytes: separators and key order are the
client library's serialisation choice, not the upstream's contract, and a byte comparison breaks on a
library upgrade that changed nothing on the wire that matters.

### Pure-CPU canonicalizer / renderer

```
tests/unit/infrastructure/<adapter>/
└── test_<tech>_<verb>.py
```

```python
import pytest

from myapp.domain.bars import CanonicalBarUrl
from myapp.domain.exceptions import ValidationError
from myapp.infrastructure.idna import IdnaBarUrlCanonicalizer, IdnaSettings

_SETTINGS = IdnaSettings(allowed_schemes=frozenset({"http", "https"}))

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
arm — which is Rule 21 applied to a canonicalizer: one test per arm, each asserting the `context` key
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
2. **Path follows the flavor, and the flavor follows whether the test needs something running.** A test that needs a live backend is an integration test (`tests/integration/<adapter>/`). A test whose socket is intercepted, and a pure-CPU adapter that touches nothing, need nothing running and are unit tests (`tests/unit/infrastructure/<adapter>/`) — the intercepted one is `test-principles`' boundary unit. Putting either under `integration/` makes it inherit that tree's container and migration fixtures and pay for infrastructure it never uses.
3. **Module-level helpers, not fixtures, for settings / keypairs / canonical inputs** in CPU tests. Construct once at module scope.

### Coverage

4. **Every public method gets a happy-path test.** Drive the adapter; assert the observable side effect (object exists in S3, response matches schema, return value equals literal).
5. **Every row of the adapter's `exception_map` gets a dedicated test.** The bug class "translator handles error code X but not Y" only surfaces when each row is exercised. A row the backend never actually reports on a given call — S3's delete of an absent key answers success — is exercised on a call where it does, and the call that cannot raise it pins its success instead.
6. **`assert exc.value.context["<key>"] == <value>` on every translated exception.** This is the capability-adapter analogue of the `context["constraint"]` rule in `hex-test-repository-contract`. The fake-based handler test cannot verify this — only this test can.
7. **A verification probe that reads the backend directly names the SDK's own error class**, never a bare `Exception`, and asserts the error code that distinguishes "absent" from "unreachable" or "unauthorized". This is the one place an SDK exception is legitimate in a test — the probe is not going through the adapter, so there is nothing translated to assert on. Asserting on an adapter call still follows the hard stop below: the translated `DomainError` subclass, never the SDK's class.
8. **For HTTP gateways, also assert the request shape** at least once: URL, method, headers (especially `Authorization`), and body. This pins the wire contract against the upstream, not just the error translation.
9. **A failure that never reaches the upstream is covered too, and lands on the upstream error.** The HTTP-gateway flavor needs a connect-refused and a read-timeout case (`ConnectError` / `ReadTimeout` here) asserting `UpstreamError`; the containerized flavor needs a wrong-container or wrong-credential case asserting the fallback translation. Every `exception_map` row can pass while the transport arm is unexercised, which is the arm that fires in a real outage.

### Real, not mocked

10. **Use the real SDK client.** Consult `test-principles` for the prohibition on mocks. The SDK is the boundary; mocking it defeats the test's purpose (catching mismatches between assumed and actual SDK exception shapes).
11. **Intercepting the network is not mocking the subject.** The client object and the adapter both stay real; only the socket is replaced — the HTTP analogue of running the real store in a container. Handing the adapter a stand-in client instead crosses back into mocking the code under test.
12. **No fake / in-memory implementation of the protocol in this test.** Fakes are for handler unit tests (`hex-test-application-handler`). This test exercises the real adapter — that's the whole point.

### Containerized flavor specifics

13. **Take the resource fixture, not raw settings.** Containerized adapters need a live client (`s3_session`, `redis`) and settings naming the test's own namespace (`s3_settings`). Both come from the integration conftest — session scope for the container and the client, function scope for the namespace. The one exception is the rejected-credential case (rule 9), which builds a client with credentials the backend refuses.
14. **Isolate by a per-test namespace with teardown; there is no rollback at this layer.** A blob store, a cache or a queue has no nested transaction to discard, so each test owns a fresh prefix, key namespace or bucket, created before it and dropped after it. This is not a choice to leave open — left open, two projects answer it two ways and the second leaks state between tests. The split of ownership is by scope: the session-scoped container and client are `hex-test-integration-setup`'s, and the per-test namespace and its teardown live beside the tests that consume it (the same split `hex-test-repository-contract` rule 15 makes) — which for a blob store is that same integration conftest, because `real_app` substitutes the per-test bucket too.
15. **Don't bypass the adapter to drive setup.** For success assertions, you may inspect the backend directly (`s3.head_object`) — that is the observation. But for setup that exists to drive the test, go through the adapter (`adapter.upload(...)` then `adapter.delete(...)`).

### HTTP-gateway flavor specifics — interception binding: respx over httpx

16. **The interception is active before any request is made, never opened around one block mid-test.** The decorator form (`@respx.mock`) covers the whole test body — adapter construction and the act; it does not cover fixtures, which run before the decorated function is entered, so a fixture that itself issues requests enters `respx.mock` itself. A context manager opened mid-test leaves any request made outside it going to the real network, which fails opaquely or — worse — reaches the real upstream.
17. **Each stubbed route matches one exact method-and-URL, never a catch-all.** A pattern broad enough to also match a request the test did not intend — a retry, a token refresh, a second endpoint — answers it too, and the test then passes without ever proving the call it was written for went where it should.
18. **Every happy-path test asserts the stubbed route was actually hit.** An interception layer answers whatever arrives and reports success by default, so an adapter that never made the call — an un-awaited coroutine is the standing case — passes a test that only checks the return value.
19. **Trigger a transport failure with a transport-level error, not a status code.** Only a raised connect or timeout error (`side_effect=httpx.ConnectError(...)`) reaches the adapter's transport-error arm; every status-code test lands on the response arm and leaves that branch unexercised.

### CPU flavor specifics

20. **Real parsing, real crypto.** Drive the actual library: feed a canonicalizer real inputs and assert literal outputs; for a verifier, generate a real key at module scope and sign with the real library. Never hand the adapter a pre-baked value the library never produced.
21. **One `test_*` per `raise` site in the adapter** — each library-exception arm *and* each guard the adapter raises itself. Each test triggers exactly one, and asserts the `context` key that arm sets (Rule 6).
22. **No fixtures.** Pure-CPU adapters are constructed in-line in each test from module-level settings. They have no lifecycle.

## Inlined typing / import rules

- `pytest`, `respx` (HTTP flavor), `httpx`, the real parsing / crypto library (CPU flavor), the real SDK, `myapp.domain.*`, `myapp.infrastructure.<adapter>` — imported from the package, not its inner module (`python-packaging`). No `myapp.application.*`, no `myapp.restapi.*`.
- Full annotations on every test signature, and a yielding fixture is annotated `AsyncIterator[T]` / `Iterator[T]`. Resource-fixture types (`Session`, `httpx.AsyncClient`) come from the SDK / library, not the project.
- No `from __future__ import annotations`.

## Hard stops

- Nothing up-tree provides the live backend a containerized flavor drives (`s3_session` / `s3_settings`, `redis`, … under this catalogue's binding) → stop, use `hex-test-integration-setup` to extend the fixtures first; what the flavor needs is the running backend, not a particular fixture name.
- Asked for `unittest.mock` / `MagicMock` of the SDK client → stop, use `test-principles` for substitution rules; the SDK boundary is exactly what this test exists to verify.
- Asked to mock the adapter itself → stop, use `hex-test-application-handler`.
- Asked for `@pytest.mark.integration` or `@pytest.mark.asyncio` → stop, use `test-principles` for marker rules.
- Asked to assert `pytest.raises(<SdkExceptionClass>)` directly → stop, use `exception-catalog` for boundary translation; assert the translated `DomainError` subclass.
- Asked to assert on a translated exception without checking `context` keys → stop, check the context keys; the context map is the load-bearing contract this test exists to pin.
- Asked for a happy-path test only with no error-translation cases → stop, cover the exception map row-by-row.
- A test references FastAPI, `httpx.AsyncClient` over `ASGITransport` or the DI container → stop, use `hex-test-restapi-endpoint`.
- A pure-CPU adapter's test is given `respx` or a container → stop, check the adapter classification; pure-CPU code needs neither, and an adapter with IO is mis-classified.
- Asked for a token-verifier test here → stop, use `hex-test-restapi-auth`; the flavor is this skill's, the example is not, and duplicating it teaches auth twice.
