---
name: flat-test-service-client
description: Use when testing one external-service client class with `respx` over real `httpx` transport — URL assembly, the outgoing request, response parsing, timeouts, translation into the service's catalog exception. A unit test needing no database and no container, unlike `flat-test-run-function`, which stubs the same transport under the whole run against a real datastore. Not a hexagonal `ICan<Verb>` capability adapter — `hex-test-capability-adapter`, in the `pyhouse-hex` plugin.
---

# Flat-Layered Test — Service Client

Consult `test-principles` for the testing constitution. Where this skill contradicts `test-principles`, the constitution wins.

One unit-test file per client class, under the distribution's own `tests/unit/`. No database, no
container, no network — `respx` intercepts at the `httpx` transport layer, so everything the client
itself does (URL assembly, headers, `raise_for_status`, JSON parsing, the `except httpx.HTTPError`
translation) runs unchanged. That is why this is a *unit* test despite involving HTTP: nothing crosses a
process boundary.

The client has no `Protocol` and needs none. `respx` substitutes the transport, which is somebody else's
boundary — not an abstraction invented to make the code mockable.

## When to use vs. neighbours

- The client wraps a vendor SDK rather than raw `httpx` (a cloud SDK, a database driver) → not `respx`;
  test it against the real thing in a container under this distribution's `tests/integration/`, or, where
  there is no container for it, against the SDK's own test double if it ships one.
- The filter/normalize function the client's output feeds → a plain unit test with no fixtures; it is
  pure and needs nothing from this skill.
- The run function calling this client → `flat-test-run-function`, which stubs the same transport under
  the whole run against a real datastore, and so lives under `tests/integration/`.
- The catalog exception this client translates *to*, and where it is declared → `exception-catalog`;
  asserting the catalog's own shape is a separate unit test, not this skill.
- Where the client module sits in a flat service's package layout → `flat-layered`.
- The family's shared datastore fixtures → `flat-test-integration-setup`; nothing in this file needs
  one.
- The shared groundwork — the substitution ladder, naming, AAA → `test-principles`.
- The client is an adapter behind a hexagonal `ICan<Verb>` capability port rather than a flat
  `*_client.py` → `hex-test-capability-adapter`, in the `pyhouse-hex` plugin, whose HTTP-gateway flavor
  is the same `respx` technique bound to a port.

## Template — pytest, `respx` over `httpx`

`tests/conftest.py` — the upstream stub and the client over it, in the one conftest above both `unit/`
and `integration/`, because the run-function and wrapper tests use the same pair (`test-principles`,
fixture versus builder):

```python
from collections.abc import AsyncIterator, Iterator

import httpx
import pytest
import respx

from myapp.services.foo_api import FooClient

_FOO_API_URL = "https://foo.test"
_TIMEOUT_SECONDS = 1.0


@pytest.fixture
def foo_api() -> Iterator[respx.MockRouter]:
    with respx.mock(base_url=_FOO_API_URL, assert_all_called=False) as router:
        yield router


@pytest.fixture
async def foo_client(foo_api: respx.MockRouter) -> AsyncIterator[FooClient]:
    async with httpx.AsyncClient(base_url=_FOO_API_URL, timeout=_TIMEOUT_SECONDS) as http:
        yield FooClient(http)
```

`tests/unit/test_foo_client.py`:

```python
import httpx
import pydantic
import pytest
import respx

from myapp.exceptions import FooClientError
from myapp.schemas import FooPayload
from myapp.services.foo_api import FooClient


async def test_fetch_foos_returns_the_parsed_payloads(foo_api: respx.MockRouter, foo_client: FooClient) -> None:
    foo_api.get("/foos").mock(return_value=httpx.Response(200, json={"items": [{"ref": "f1", "name": "alpha"}]}))

    result = await foo_client.fetch_foos()

    assert result == (FooPayload(ref="f1", name="alpha"),)


async def test_fetch_foos_sends_a_get_to_the_collection(foo_api: respx.MockRouter, foo_client: FooClient) -> None:
    route = foo_api.get("/foos").mock(return_value=httpx.Response(200, json={"items": []}))

    await foo_client.fetch_foos()

    assert route.calls.last.request.method == "GET"
    assert route.calls.last.request.url.path == "/foos"


@pytest.mark.parametrize("status", [400, 404, 500, 503])
async def test_non_2xx_becomes_a_foo_client_error(
    foo_api: respx.MockRouter, foo_client: FooClient, status: int
) -> None:
    foo_api.get("/foos").mock(return_value=httpx.Response(status))

    with pytest.raises(FooClientError) as exc_info:
        await foo_client.fetch_foos()

    assert isinstance(exc_info.value.__cause__, httpx.HTTPStatusError)


async def test_a_timeout_becomes_a_foo_client_error(foo_api: respx.MockRouter, foo_client: FooClient) -> None:
    foo_api.get("/foos").mock(side_effect=httpx.ConnectTimeout("timed out"))

    with pytest.raises(FooClientError) as exc_info:
        await foo_client.fetch_foos()

    assert isinstance(exc_info.value.__cause__, httpx.TimeoutException)


@pytest.mark.parametrize(
    "body",
    [b"<html>not json</html>", b'{"items": [{"name": "alpha"}]}'],
    ids=["not-json", "missing-field"],
)
async def test_a_200_with_a_malformed_body_becomes_a_foo_client_error(
    foo_api: respx.MockRouter, foo_client: FooClient, body: bytes
) -> None:
    foo_api.get("/foos").mock(return_value=httpx.Response(200, content=body))

    with pytest.raises(FooClientError) as exc_info:
        await foo_client.fetch_foos()

    assert isinstance(exc_info.value.__cause__, pydantic.ValidationError)
```

The stub and the client are fixtures, not module-level builders, because each has an end — the stub's
interception is lifted and the transport closed at teardown — and they sit in `tests/conftest.py`
rather than in each test module because three files at two levels take them. The client fixture builds
its `httpx.AsyncClient` exactly as the process definition does — base URL and timeout from constants in
place of settings — and **requests the stub**, so no test can hold the client without the interception
under it (rule 8). `assert_all_called=False` is rule 7, stated where the stub is made.

The error tests assert the translated class and its chained cause. `fetch_foos` takes no input, so its
`context` is empty; a method that takes one also asserts the `context` key set the raise site and its
test agree on — never the message text, which is free to change (`exception-catalog`). The malformed-body
cases cover both halves of parsing: a body that is not JSON, and JSON that does not fit the payload.

## Template — failure injection for the client's *callers*

When a caller's test needs this client to fail, it subclasses rather than mocks. This lives in the
caller's test module, not here — it is included so both halves of the pattern are in one place:

```python
class _RaiseFooClient(FooClient):
    async def fetch_foos(self) -> tuple[FooPayload, ...]:
        raise FooClientError("upstream down")
```

It is constructed like the real client, over an `httpx.AsyncClient` the caller's test builds and closes
— `_RaiseFooClient(http)` — which the overridden method never uses.

Override exactly the one method that must fail, and nothing else — the rest of the real client stays in
the object, so a signature change breaks the test at call time instead of passing silently.

## Other bindings

- **A stub transport instead of a global patch** — `httpx.MockTransport`, or a local ASGI app served
  in-process, passed as `transport=` to the `httpx.AsyncClient` the test hands the client. The client
  already takes its transport pre-built, so nothing in it changes. What the tests assert — the
  translation, the outgoing request, malformed bodies, timeouts — is unchanged, and so is the ban on
  extracting a `Protocol`.
- **A different HTTP library** — `aiohttp` with `aioresponses`, `requests` with `responses`. The
  interception point and the exception classes the client translates *from* change together; the
  catalogue exception it translates *to*, the cause-chaining requirement and every rule below are
  unchanged.
- **Recorded interactions** — vcrpy cassettes. Response bodies come from a recording rather than a
  literal, which keeps them honest about the vendor's real shape; rule 3 then pins the cassette's
  recorded request. The timeout and malformed-body cases still have to be hand-written, because a
  cassette holds only what actually happened.

## Rules

1. **The transport is stubbed, never the client.** A test that patches `FooClient.fetch_foos` is testing
   nothing; the parsing and translation under test live inside that method.
2. **Assert the translation, not just the type.** Every error status and every transport failure must
   surface as the service's own catalog exception — carrying the identifying input in its `context`
   where the call takes one — and the original must still be reachable as that exception's cause: that
   is what raising *from* the original at the boundary buys, and it is the thing a careless refactor
   drops. Assert on `context`, never on the message text.
3. **Pin the request, not only the response.** At least one test asserts what the client actually sent —
   path, query, headers, body — read back from what the stub recorded (`route.calls.last.request` here).
   A client that parses a canned response correctly while requesting the wrong URL passes every
   response-shaped test.
4. **Input coverage is parametrized; a differing behaviour gets its own named test.** Four error statuses
   against one behaviour is input coverage and belongs in one parametrized test (`pytest.mark.parametrize`
   here). A 404 that must return `None` instead of raising is a *different* behaviour and gets its own
   name, because the name is the spec line.
5. **Malformed responses are part of the contract.** A 200 with a body the client cannot parse must fail
   as the catalog exception, not as a bare `KeyError` or `JSONDecodeError` escaping to the caller.
6. **The base URL is a constant beside the fixture that builds the client, and is passed in.** Never let
   the test depend on a settings value — hand the client an HTTP client built with an explicit
   `base_url`, which is why the client is handed its transport rather than building one.
7. **Never assert that every stubbed route was called** (`assert_all_called` here). It pins how many
   requests the client happens to make, so an added prefetch or a dropped retry reddens a test that was
   about neither; assert the calls the behaviour requires.
8. **Every test in the file intercepts the transport; none may reach a real host.** A test that escapes
   the stub — an unmatched URL, a client that builds a transport the stub does not cover — is
   non-deterministic, slow, and fails in CI on the day the vendor has an outage.

## Hard stops

- A test patches a method of the class under test → stop, stub the transport, or subclass for a
  *caller's* injection; patching the subject leaves nothing tested.
- A `Protocol` is being extracted so the client can be substituted → stop, forbidden by the flat-layered
  style; the transport stub already substitutes at the right seam.
- The client swallows a transport or parsing failure internally, returning a default instead of raising
  → stop, fix the client; a boundary that hides its failures cannot be tested, and its caller cannot
  tell a failure from an empty answer.
- A test asserts on a live third-party response shape → stop, that is a contract test against someone
  else's uptime; record the shape as a fixture and assert against that.
- The client returns raw `httpx.Response` objects to its caller → stop, the boundary leaks; the client
  owns parsing, and a test cannot pin behaviour that lives in the caller.
- The test builds the client's transport with no explicit base URL, or through a settings factory → stop,
  it is now coupled to the environment.
