---
name: hex-test-restapi-endpoint
description: Use when testing one REST endpoint through the real ASGI app — one file per endpoint under `tests/integration/api/<resource>/`, asserting the happy path and validating the success body against its schema, with per-resource fixtures in a sibling `conftest.py`. Not properties discovered across all routes at once (`hex-test-app-invariants`), not the auth half — a token verifier's unit test, 401/403, role rejection, cross-tenant 404 (`hex-test-restapi-auth`) — and not the fixtures themselves (`hex-test-integration-setup`).
---

# Hex Test — REST API Endpoint

Consult `test-principles` for the testing constitution. Where this skill contradicts `test-principles`, the constitution wins.

Produces one integration-test file per endpoint. Self-contained: every test in the file constructs its own state by calling factory fixtures or POSTing through the API; no cross-test state, no shared registries, no cross-file edits when a new endpoint is added.

## When to use vs. neighbours

- A new or modified endpoint added by `hex-restapi-endpoint` → this skill.
- A new resource introduces several endpoints (create + list + get + update + delete) → invoke this skill once per endpoint file; sibling files share a per-resource `conftest.py`.
- The `tests/integration/conftest.py` itself (rollback, container fixtures, `real_app`) → `hex-test-integration-setup` (one-shot).
- The `authed_client` factory and the signing-key fixtures behind it → `hex-test-restapi-auth` (auth apps only).
- Driving a route as an authenticated caller, asserting a role rejection or a cross-tenant 404 → `hex-test-restapi-auth` (auth apps only; this skill is complete without it).
- The token verifier's own unit test — no HTTP, real keys, one case per translation arm → `hex-test-restapi-auth`, not this skill and not `hex-test-capability-adapter`.
- The route-side auth dependency, the role gate and the 401/403 codes a route advertises because of them → `hex-restapi-auth`.
- Cross-cutting "every route's OpenAPI codes match `error_responses(...)`" / CORS / request-size → `hex-test-app-invariants` (one-shot; discovers by walking the app's resolved route contexts and reading `app.openapi()`).
- Repository contract (real DB, no HTTP) → `hex-test-repository-contract`.
- Pure domain unit test → `hex-test-domain`.
- The testing constitution these rules defer to — speed targets, fixture placement, the mocking prohibition → `test-principles`.
- A structural invariant enforced by a grep firewall at compile time rather than over HTTP → `test-architecture-rule`.

## Template(s) — pytest, httpx over an in-process ASGI transport, FastAPI

```
tests/integration/api/<resource>/
├── conftest.py                                  # per-resource fixtures (sibling-shared)
└── test_<verb>_<noun>.py                        # one file per endpoint
```

**The templates below are the primary, auth-free form** — a public route, or any route in an app that
declares no auth. Whether an app has auth follows from its routes (`hex-restapi-auth`). An authenticated
route is the same file driven through an authenticated client instead of the plain one, and
`hex-test-restapi-auth` carries those variants along with the role and tenancy assertions that only exist
when there is a caller to have a role.

### `test_<verb>_<noun>.py` — the endpoint test

```python
import uuid

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from myapp.domain.exceptions import FooConflictError, NotFoundError
from myapp.restapi.schemas import FooResponse


async def test_create_foo_happy_path(real_app: FastAPI, bar_id: uuid.UUID) -> None:
    transport = ASGITransport(app=real_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/foos", json={"name": "alpha", "bar_id": str(bar_id)}
        )

    assert response.status_code == 201
    body = FooResponse.model_validate(response.json())
    assert body.name == "alpha"
    assert body.bar_id == bar_id


async def test_create_foo_duplicate_name_returns_409(
    real_app: FastAPI, bar_id: uuid.UUID
) -> None:
    transport = ASGITransport(app=real_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        payload = {"name": "alpha", "bar_id": str(bar_id)}
        first = await client.post("/foos", json=payload)
        assert first.status_code == 201

        second = await client.post("/foos", json=payload)

    assert second.status_code == 409
    assert second.json()["code"] == FooConflictError.code


async def test_create_foo_unknown_bar_returns_404(real_app: FastAPI) -> None:
    transport = ASGITransport(app=real_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            "/foos", json={"name": "alpha", "bar_id": str(uuid.uuid4())}
        )

    assert response.status_code == 404
    assert response.json()["code"] == NotFoundError.code
```

The plain `AsyncClient` over `real_app` is the sanctioned client for a route with no auth dependency
(Rule 6). Every error path for the same endpoint lives in this file too — the duplicate-name `409`, the
unknown-parent `404` — each asserted by `code` (Rule 9).

### Per-resource `conftest.py` — relational seed factory

A raw `INSERT` is legitimate setup here, and this is the one place in the catalogue where it is: `hex-test-repository-contract` rule 10 bans it only in a test of the repository under test, where seeding behind the subject would prove nothing. An endpoint test's subject is the route, so the fastest honest way to put a row in front of it is to write one. The `make_foo` factory below seeds via a raw SQL `INSERT` through `sf` — that is the **relational-store** variant, valid when the resource is backed by a relational store. A resource backed by a client-style store (redis / a document store / …) has no `sf` and no SQL table: seed it either by **POSTing through the API** (drive the create endpoint, then test against the result) or via the **store's own client** in the fixture. Pick the path from the resource's datastore kind; don't reach for `INSERT INTO` when there is no SQL table.

```python
import uuid
from collections.abc import Awaitable, Callable

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker


@pytest.fixture
async def bar_id(sf: async_sessionmaker[AsyncSession]) -> uuid.UUID:
    bid = uuid.uuid4()
    async with sf() as session:
        await session.execute(
            text("INSERT INTO bars(id, name) VALUES(:id, :name)"),
            {"id": str(bid), "name": "bar"},
        )
        await session.commit()
    return bid

@pytest.fixture
def make_foo(
    sf: async_sessionmaker[AsyncSession], bar_id: uuid.UUID
) -> Callable[..., Awaitable[uuid.UUID]]:
    async def _make(*, name: str | None = None) -> uuid.UUID:
        fid = uuid.uuid4()
        async with sf() as session:
            await session.execute(
                text(
                    "INSERT INTO foos(id, name, bar_id, created_at, updated_at)"
                    " VALUES(:id, :name, :bar_id, now(), now())"
                ),
                {"id": str(fid), "name": name or "foo", "bar_id": str(bar_id)},
            )
            await session.commit()
        return fid
    return _make

@pytest.fixture
async def foo_id(make_foo: Callable[..., Awaitable[uuid.UUID]]) -> uuid.UUID:
    return await make_foo()
```

### Multipart upload — single-test skeleton

```python
import uuid

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from myapp.restapi.schemas import AttachmentResponse

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 8

async def test_upload_attachment_returns_201(
    real_app: FastAPI, foo_id: uuid.UUID
) -> None:
    transport = ASGITransport(app=real_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.post(
            f"/foos/{foo_id}/attachments",
            data={"data": '{"caption": "test"}'},
            files=[("attachments", ("a.png", PNG, "image/png"))],
        )

    assert response.status_code == 201
    AttachmentResponse.model_validate(response.json())
```

### Streaming download — single-test skeleton

```python
import uuid

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


async def test_download_attachment_streams_bytes(
    real_app: FastAPI,
    foo_id: uuid.UUID,
    attachment_id: uuid.UUID,
) -> None:
    transport = ASGITransport(app=real_app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        response = await client.get(f"/foos/{foo_id}/attachments/{attachment_id}")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/png"
    assert response.headers["content-disposition"].startswith("attachment; filename=")
    assert len(response.content) > 0
```

The media type and the disposition mode asserted are the route's own declared ones
(`hex-restapi-endpoint`) — the values the route under test sets, not a fixed download shape.

## Other bindings

- **Another way to drive the app.** An in-process ASGI transport is one; a framework's own test client,
  or a live server on a loopback port, are the others. What changes is how the client is constructed and
  whether the app's start-up events run — an out-of-process server runs them, an in-process transport may
  not, so a test that depends on start-up wiring has to arrange it. One file per endpoint, whole-body
  schema validation, the error-code assertion and per-test factory fixtures are unchanged.
- **Another way to validate the body.** Asserting the response against the OpenAPI document's schema, or
  through a different model library, satisfies rule 2 as well as `model_validate` does. What must survive
  the swap is validating the *whole* body rather than picked fields.

## Rules

Consult `test-principles` for the testing constitution.

1. **One file per endpoint.** Use `naming` for filenames: `test_create_foo.py`, `test_list_foos.py`, `test_delete_foo.py`. Each file holds the happy path + every error path for that one endpoint. No mega-files spanning a whole resource.
2. **Every success body is validated through the route's own declared response schema — the whole body, not picked fields.** `FooResponse.model_validate(response.json())` reds on a field the route dropped, renamed or retyped; a handful of `body["name"] == ...` assertions pass through all three, which is the drift this layer exists to catch. Schema imports follow `python-packaging` (`from myapp.restapi.schemas import FooResponse`).
3. **No cross-cutting registries.** Adding a new endpoint touches exactly one new test file. The discovered global checks — "every route declares its error codes in OpenAPI", and in an auth app "every protected route rejects an anonymous caller" — are owned by `hex-test-app-invariants` and `hex-test-restapi-auth`, and derive their inputs from the app's resolved route contexts and `app.openapi()`; there is no hand-maintained endpoint table to extend.
4. **Endpoint state.** Follow `test-principles` for test isolation. Each test builds its own state via per-resource factory fixtures (`make_foo`) or by POSTing through the API. Since the rollback contract guarantees an empty DB at test start, fixed natural keys (`name="alpha"`) are safe — no `uuid4().hex[:8]` suffix required.
5. **Response assertions.** Follow `test-principles` for assertion strength. `assert len(items) == N`, `assert items[0].id == ...`, `assert response.json()["total"] == 3` — the empty-DB-at-start contract makes these reliable, so a defensive `any(...)` filter only weakens the assertion.
6. **The client matches the route's auth dependency, and it is always entered as a context manager.** A route with no auth dependency is driven by a plain client over `real_app`, as above; a route that attaches one is driven by the authenticated client `hex-test-restapi-auth` owns. Bare-assigning the client instead of entering it leaks the transport either way, and the leak surfaces as an unrelated test failing later in the session.
7. **A caller-scoped assertion belongs with the caller.** Role rejections and cross-tenant reads only exist when a route has a caller — their rules and templates are `hex-test-restapi-auth`'s.
8. **Per-resource fixtures live in the sibling `conftest.py`.** Factory fixtures (`make_foo`) return one fresh row per call. Single-row fixtures (`foo_id`) wrap a factory call. Both are function-scoped; no session-scoped row fixtures, ever.
9. **Error responses are asserted by `code`, not by message.** `assert response.json()["code"] == FooConflictError.code` — message text drifts, the `code` constant is the contract. The actual HTTP status is asserted separately.
10. Test collection and async marker rules → `test-principles`.
11. **Mocking.** Follow `test-principles` for the mocking prohibition. If a test needs to mock, it isn't an integration test; move it to a domain unit test (`hex-test-domain`) or to a handler test over fakes (`hex-test-application-handler`), which is also where a compensating handler's undo is pinned.
12. **A blob-writing test asserts only inside its own namespace, and the namespace reaches the route through the test's infrastructure bindings, never through the route.** `real_app` binds the per-test `S3Settings` (`hex-test-integration-setup`), so a route writes into the test's own bucket with no change to its signature; the test reads that bucket back through the same settings. A route that accepts a prefix, header or parameter only so a test can steer where it writes has grown a test-only input into production.

## Inlined typing / import rules

- `pytest`, `httpx`, `fastapi`, `myapp.restapi.schemas`, `myapp.domain.exceptions`. No `myapp.application.*` or `myapp.infrastructure.*` imports — the test drives over HTTP, not by reaching in.
- Full annotations on every signature, tests included — `-> None` on every test, every fixture parameter typed. `python-style` owns annotation policy and admits no test carve-out.
- No `from __future__ import annotations`.

## Hard stops

- Nothing up-tree provides an isolated session handle, or an app built on the test's own infrastructure bindings (`sf` / `real_app` under this catalogue's binding) → stop, use `hex-test-integration-setup`; the missing thing is the guarantee, not the fixture name.
- Asked to register the new endpoint in a hand-maintained route or expectation table so a global check sees it → stop, use `hex-test-app-invariants`; the global checks derive their inputs from the running app, so a new route joins them with nothing to update.
- A test asserts a role rejection or a cross-tenant 404 here → stop, use `hex-test-restapi-auth`; those assertions need a caller identity this skill does not mint.
- A test uses `unittest.mock` / `MagicMock` / `AsyncMock` / `monkeypatch` → stop, use `test-principles`.
- A test asserts on a response field that is not in the Pydantic response schema → stop, use `hex-restapi-schema` to extend the schema first.
- A test uses `[:4]` or `[:5]` natural-key suffixes "to avoid collisions" → stop, the isolation `hex-test-integration-setup` establishes leaves the store empty at test start; fixed names are fine.
- A test asserts `len(items) == N + 1` to account for "the test's own row plus seed rows" → stop, assert the exact count under `test-principles`; rollback isolation drops everything.
- A test uses a plain `AsyncClient` for a request to a route that attaches an auth dependency → stop, use `hex-test-restapi-auth`'s authenticated client; a plain client on a gated route tests the rejection, not the endpoint.
- A test adds `@pytest.mark.integration` or `@pytest.mark.asyncio` → stop, use `test-principles`.
- A fixture returns the same row across multiple tests (session-scoped row) → stop, use a factory + function-scoped wrapper; rows are per-test.
- The endpoint touches multipart or streaming and its encoding is not stated → stop, use `hex-restapi-endpoint` for the route side first.
