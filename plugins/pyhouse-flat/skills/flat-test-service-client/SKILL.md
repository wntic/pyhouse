---
name: flat-test-service-client
description: Use when testing one external-service client class with `respx` over real `httpx` transport — URL assembly, the outgoing request, response parsing, timeouts, translation into the service's catalog exception. A unit test needing no database and no container, unlike `flat-test-run-function`, which substitutes this client whole. Not a hexagonal `ICan<Verb>` capability adapter — `hex-test-capability-adapter`.
paths: ["**/tests/**"]
---

# Flat-Layered Test — Service Client

Consult `test-principles` for the testing constitution. Where this skill contradicts `test-principles`, the constitution wins.

One unit-test file per client class, under `services/<service>/tests/unit/`. No database, no container,
no network — `respx` intercepts at the `httpx` transport layer, so everything the client itself does
(URL assembly, headers, `raise_for_status`, JSON parsing, the `except httpx.HTTPError` translation) runs
unchanged. That is why this is a *unit* test despite involving HTTP: nothing crosses a process boundary.

The client has no `Protocol` and needs none. `respx` substitutes the transport, which is somebody else's
boundary — not an abstraction invented to make the code mockable.

## When to use vs. neighbours

- The client wraps a vendor SDK rather than raw `httpx` (a cloud SDK, a database driver) → not `respx`;
  test it against the real thing in a container under that service's `tests/integration/`, or, where
  there is no container for it, against the SDK's own test double if it ships one.
- The filter/normalize function the client's output feeds → a plain unit test with no fixtures; it is
  pure and needs nothing from this skill.
- The run function calling this client → `flat-test-run-function`, which substitutes the *client*, not
  the transport, and does live under `tests/integration/`.
- The catalog exception this client translates *to*, and where it is declared → `exception-catalog`;
  asserting the catalog's own shape is a separate unit test, not this skill.
- Where the client module sits in a flat service's package layout → `flat-layered`.
- The workspace's shared Postgres fixtures → `flat-test-integration-setup`; nothing in this file needs
  one.
- The shared groundwork — the substitution ladder, naming, AAA → `test-principles`.
- The client is an adapter behind a hexagonal `ICan<Verb>` capability port rather than a flat `*_client.py` → `hex-test-capability-adapter`, in the `pyhouse-hex` plugin, whose HTTP-gateway flavor is the same `respx` technique bound to a port.

## Template — pytest, `respx` over `httpx`

`services/foo_parser/tests/unit/test_foo_client.py`:

```python
import httpx
import pytest
import respx

from foo_parser.exceptions import FooClientError
from foo_parser.services.foo_client import FooClient

_BASE_URL = "https://foo.test"


def _client() -> FooClient:
    return FooClient(base_url=_BASE_URL)


@respx.mock
async def test_fetch_returns_the_parsed_payload() -> None:
    respx.get(f"{_BASE_URL}/foos/f1").mock(
        return_value=httpx.Response(200, json={"id": "f1", "name": "alpha"})
    )

    result = await _client().fetch("f1")

    assert result == {"id": "f1", "name": "alpha"}


@respx.mock
async def test_fetch_sends_the_id_in_the_path() -> None:
    route = respx.get(f"{_BASE_URL}/foos/f1").mock(return_value=httpx.Response(200, json={}))

    await _client().fetch("f1")

    assert route.called
    assert route.calls.last.request.url.path == "/foos/f1"


@respx.mock
@pytest.mark.parametrize("status", [400, 404, 500, 503])
async def test_non_2xx_becomes_a_foo_client_error(status: int) -> None:
    respx.get(f"{_BASE_URL}/foos/f1").mock(return_value=httpx.Response(status))

    with pytest.raises(FooClientError) as exc_info:
        await _client().fetch("f1")

    assert "f1" in str(exc_info.value)
    assert isinstance(exc_info.value.__cause__, httpx.HTTPError)


@respx.mock
async def test_a_timeout_becomes_a_foo_client_error() -> None:
    respx.get(f"{_BASE_URL}/foos/f1").mock(side_effect=httpx.ConnectTimeout("timed out"))

    with pytest.raises(FooClientError):
        await _client().fetch("f1")


@respx.mock
async def test_a_200_with_an_unparseable_body_becomes_a_foo_client_error() -> None:
    respx.get(f"{_BASE_URL}/foos/f1").mock(
        return_value=httpx.Response(200, content=b"<html>not json</html>")
    )

    with pytest.raises(FooClientError):
        await _client().fetch("f1")


@respx.mock
async def test_pagination_stops_at_the_last_page() -> None:
    respx.get(f"{_BASE_URL}/foos").mock(
        side_effect=[
            httpx.Response(200, json={"items": [{"id": "f1"}], "next": "cursor-2"}),
            httpx.Response(200, json={"items": [{"id": "f2"}], "next": None}),
        ]
    )

    items = await _client().fetch_batch()

    assert [i["id"] for i in items] == ["f1", "f2"]
```

## Template — failure injection for the client's *callers*

When a caller's test needs this client to fail, it subclasses rather than mocks. This lives in the
caller's test module, not here — it is included so both halves of the pattern are in one place:

```python
class _RaiseFooClient(FooClient):
    async def fetch_batch(self) -> list[dict]:
        raise FooClientError("upstream down")
```

Override exactly the one method that must fail, and nothing else — the rest of the real client stays in
the object, so a signature change breaks the test at call time instead of passing silently.

## Other bindings

- **A transport object handed to the client instead of patched globally** — `httpx.MockTransport`, or a
  local ASGI app served in-process. The client must then accept a transport or a pre-built client, so
  rule 6 widens by one constructor parameter. What the tests assert — the translation, the outgoing
  request, malformed bodies, timeouts — is unchanged, and so is the ban on extracting a `Protocol`.
- **A different HTTP library** — `aiohttp` with `aioresponses`, `requests` with `responses`. The
  interception point and the exception classes the client translates *from* change together; the
  catalogue exception it translates *to*, the cause-chaining requirement and every rule below are
  unchanged.
- **Recorded interactions** — vcrpy cassettes. Response bodies come from a recording rather than a
  literal, which keeps them honest about the vendor's real shape; rule 3 then pins the cassette's
  recorded request. The timeout and malformed-body cases still have to be hand-written, because a
  cassette holds only what actually happened.

## Rules

1. **The transport is stubbed, never the client.** A test that patches `FooClient.fetch` is testing
   nothing; the parsing and translation under test live inside that method.
2. **Assert the translation, not just the type.** Every error status and every transport failure must
   surface as the service's own catalog exception, and the original must still be reachable as that
   exception's cause — that is what raising *from* the original at the boundary buys, and it is the
   thing a careless refactor drops.
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
6. **The base URL is a module constant and is passed in.** Never let the test depend on a settings
   value — construct the client with an explicit `base_url`, which is why the client takes one.
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
- The client builds a transport the test cannot reach → `respx` patches the transport globally, so this
  is fine — but if the client also disables retries or swallows errors internally, fix the client; a
  boundary that hides its failures cannot be tested.
- A test asserts on a live third-party response shape → stop, that is a contract test against someone
  else's uptime; record the shape as a fixture and assert against that.
- The client returns raw `httpx.Response` objects to its caller → stop, the boundary leaks; the client
  owns parsing, and a test cannot pin behaviour that lives in the caller.
- The test constructs the client with no explicit base URL → stop, it is now coupled to the environment.
