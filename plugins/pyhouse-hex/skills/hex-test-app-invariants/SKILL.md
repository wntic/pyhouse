---
name: hex-test-app-invariants
description: Use when testing a property of the assembled app itself rather than one route's own behaviour — a check that needs no edit when an endpoint is added or removed. Covers the one-shot OpenAPI error-code cross-check against `error_responses(...)`, the CORS preflight, the request-size limit, and the app-construction smoke, each taking its inputs from the running app rather than from a maintained list. A single endpoint's test is `hex-test-restapi-endpoint`; the anonymous-caller probe and every token fixture are `hex-test-restapi-auth`'s.
---

# Hex Test — App Invariants

Consult `test-principles` for the testing constitution. Where this skill contradicts `test-principles`, the constitution wins.

One-shot per project. Two to four integration files under `tests/integration/api/` plus one unit-level app-construction smoke. Each one iterates — or constructs — the running app and asserts a single global property; none of them needs to be edited when an endpoint is added or removed. An app that declares auth gains a fifth discovered invariant — every protected route rejects an anonymous caller — which is `hex-test-restapi-auth`'s.

## When to use vs. neighbours

- Laying the cross-cutting tests for the first time → this skill.
- A per-endpoint integration test → `hex-test-restapi-endpoint`.
- The rollback fixture / containers / `real_app` → `hex-test-integration-setup` (owns `real_app`, which every test here imports).
- The every-protected-route-rejects-an-anonymous-caller probe, and the fixtures that mint tokens → `hex-test-restapi-auth` (auth apps only; nothing here consumes them — see Rule 8).
- The route-side `error_responses(...)` declaration this skill cross-checks the document against → `hex-restapi-endpoint`, in its sibling `CONTRACTS.md`; the 401/403 half of it → `hex-restapi-auth`.
- A grep-firewall static rule → `test-architecture-rule` (compile-time, not runtime).
- The testing constitution — markers, async mode, the mocking prohibition → `test-principles`.

## Template(s) — pytest, FastAPI, httpx over an in-process ASGI transport

```
tests/integration/api/
├── test_openapi_advertises_error_codes.py   # always
├── test_cors.py                             # always
├── test_request_size_limit.py               # only if a size-cap middleware is declared (Hard stops)
└── test_info.py                             # only if an info/health endpoint is declared (Rule 11)
tests/unit/restapi/
└── test_app_constructs.py                   # always — unit-level construct smoke, no DB (Rule 12)
```

### `tests/unit/restapi/test_app_constructs.py`

```python
from myapp.restapi.main import create_app


def test_app_constructs_and_renders_openapi() -> None:
    """Smoke: the composition root + app shell wire up, and the OpenAPI schema
    renders over every route. This is the ONLY place a construct-time failure
    surfaces — a missing framework dependency FastAPI imports at app-build time
    (e.g. `python-multipart` for a Form(...)/UploadFile route, raised at
    create_app, never at type-check), broken middleware wiring, or a route
    whose response schema won't build. mypy / ruff / handler unit tests all
    stay green through these; constructing the app does not."""
    app = create_app()
    assert app.openapi()["paths"]  # forces the full schema build over every route
```

This lives at the **unit** layer, not under `tests/integration/`, on purpose: `create_app` needs **no** database — factories are lazy, so it wires routers/middleware/error-handlers and assembles the composition root without resolving a handler or opening a connection. Placing it under `tests/integration/` would drag that tree's session-autouse `_migrated_db` / `_guard_against_real_db` fixtures and require Postgres, defeating the point — the construct-time defect class must be catchable with no Docker daemon (exactly the environment where mypy/ruff/unit run green and miss it). The test is structural, not a body test: it passes on freshly laid routes (the functions exist with valid signatures; their `NotImplementedError` bodies are never *called* by construction or `openapi()`), so a missing dependency reds it as soon as the routes exist, before their bodies are filled.

### `test_openapi_advertises_error_codes.py`

```python
from fastapi import FastAPI
from fastapi.routing import APIRoute, RouteContext, iter_route_contexts

# FastAPI publishes a `422` on any operation whose input it validates — a path param, a query
# param, a body — whether or not the decorator declared one, and the decorator side of this
# comparison cannot see it. Without this exemption the test reds on every route that takes any
# input at all: measured on a live app, `GET /foos/{id}: decorator=[401, 404] spec=[401, 404,
# 422] extra=[422]`, while the parameterless route on the same app matched. So it is the one code
# allowed to stand in the document undeclared, and the only one. Declaring it anyway stays the
# house style (`hex-restapi-endpoint`): a declared `422` is published and matches either way.
_FRAMEWORK_VALIDATION_CODE = 422

def _declared_codes(app: FastAPI) -> dict[tuple[str, str], set[int]]:
    """For each (METHOD, path), the set of HTTP error codes the route
    declares in OpenAPI via `responses=error_responses(...)`."""
    spec = app.openapi()
    out: dict[tuple[str, str], set[int]] = {}
    for path, methods in spec["paths"].items():
        for method, op in methods.items():
            if method.upper() == "HEAD":
                continue
            codes = {int(c) for c in op.get("responses", {}) if c.isdigit() and int(c) >= 400}
            out[(method.upper(), path)] = codes
    return out

def _api_operations(app: FastAPI) -> list[RouteContext]:
    """Every API operation the app serves, one route context each.

    Walked with `iter_route_contexts` and NOT by filtering `app.routes` for
    `APIRoute`: a FastAPI that defers `include_router` leaves a router
    placeholder in `app.routes` and not one `APIRoute`, so the filtering walk
    finds zero on a live version of the framework — measured. The context walk
    is the one FastAPI's own OpenAPI generator uses, and it finds the
    operations whether the framework expanded the routers or not. It also
    reports each route under its EFFECTIVE path — the one the document keys
    on — so an include-time prefix does not desynchronise the two sides."""
    return [
        context
        for context in iter_route_contexts(app.routes)
        if isinstance(context.route, APIRoute)
    ]

def _expected_codes_from_route(context: RouteContext) -> set[int]:
    """The set of error codes the route's decorator advertised. FastAPI
    stores them on `responses` as the dict produced by `error_responses(...)`.
    `responses` is a route internal mypy may not see, the same way `dependant`
    is — reach it via `getattr`; present at runtime."""
    responses = getattr(context, "responses", {})
    return {code for code in responses if isinstance(code, int) and code >= 400}

async def test_every_route_advertises_what_its_decorator_declared(
    real_app: FastAPI,
) -> None:
    operations = _api_operations(real_app)
    # The failure this file must not have is silence: a walk that discovers no
    # operation compares no operation, and `mismatches == []` then passes green
    # having proved nothing. Measured on a live FastAPI, so this is not a
    # precaution — it is the shape the previous walk actually degenerated into.
    assert operations, "no API operation was discovered, so nothing was compared"

    declared = _declared_codes(real_app)
    mismatches: list[str] = []

    for context in operations:
        path = context.path
        if path is None:
            continue
        for method in context.methods or set():  # Starlette types `methods` as set[str] | None
            if method == "HEAD":
                continue
            spec_codes = declared.get((method, path), set())
            decorator_codes = _expected_codes_from_route(context)
            missing = decorator_codes - spec_codes
            extra = spec_codes - decorator_codes - {_FRAMEWORK_VALIDATION_CODE}
            if missing or extra:
                mismatches.append(
                    f"{method} {path}: decorator={sorted(decorator_codes)} "
                    f"spec={sorted(spec_codes)} missing={sorted(missing)} extra={sorted(extra)}"
                )

    assert mismatches == [], "OpenAPI / decorator mismatch:\n" + "\n".join(mismatches)
```

### `test_cors.py`

```python
from typing import Any, cast

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


def _configured_origin(app: FastAPI) -> str | None:
    """Read a real allowed origin off the app's CORS middleware, instead of
    hardcoding one. Returns None when the app configures no CORS."""
    # Starlette types `Middleware.cls` as `_MiddlewareFactory[P]` and `.kwargs`
    # as `P.kwargs` (effectively untyped) — match by class name and `cast` the
    # kwargs to a dict to read off them under strict mypy (no `# type: ignore`).
    for mw in app.user_middleware:
        if getattr(mw.cls, "__name__", "") == "CORSMiddleware":
            origins = cast(dict[str, Any], mw.kwargs).get("allow_origins", [])
            return origins[0] if origins else None
    return None


async def test_cors_preflight_echoes_a_configured_origin(real_app: FastAPI) -> None:
    origin = _configured_origin(real_app)
    if origin is None:
        pytest.skip("app configures no CORS allow_origins")

    async with AsyncClient(
        transport=ASGITransport(app=real_app),
        base_url="http://testserver",
    ) as client:
        response = await client.options(
            "/",
            headers={"Origin": origin, "Access-Control-Request-Method": "GET"},
        )

    assert response.headers.get("access-control-allow-origin") == origin
```

### `test_request_size_limit.py`

```python
from typing import Any, cast

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient


def _max_request_bytes(app: FastAPI) -> int | None:
    """The configured cap of the request-size middleware, read off the app.
    Returns None when the app declares no such middleware (the kwarg name
    matches the middleware's config field — see hex-restapi-app)."""
    # See `_configured_origin` in test_cors.py — `Middleware.cls` / `.kwargs`
    # are effectively untyped; match by class name and `cast` the kwargs.
    for mw in app.user_middleware:
        if getattr(mw.cls, "__name__", "") == "MaxRequestSizeMiddleware":
            max_bytes = cast(dict[str, Any], mw.kwargs).get("max_bytes")
            return max_bytes if isinstance(max_bytes, int) else None
    return None


async def test_oversize_payload_returns_413(real_app: FastAPI) -> None:
    limit = _max_request_bytes(real_app)
    if limit is None:
        pytest.skip("app declares no request-size middleware")

    payload = b"x" * (limit + 1)
    async with AsyncClient(
        transport=ASGITransport(app=real_app),
        base_url="http://testserver",
    ) as client:
        response = await client.post(
            "/foos",
            content=payload,
            headers={"Content-Type": "application/octet-stream"},
        )

    assert response.status_code == 413
```

### `test_info.py`

```python
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

async def test_info_endpoint_is_public_and_returns_200(real_app: FastAPI) -> None:
    async with AsyncClient(
        transport=ASGITransport(app=real_app),
        base_url="http://testserver",
    ) as client:
        response = await client.get("/info")

    assert response.status_code == 200
```

## Other bindings

- **Another web framework.** Every rule here survives the swap; two mechanisms do not. The route walk
  (rule 2) becomes whatever that framework's own document generator iterates, and the exemption of rule 4
  has to be re-derived by measuring a live app — carrying `422` across because it is written here is how
  this test starts lying. Reading the CORS origin and the size cap off the running app rather than
  freezing them stays the rule; only the attribute they are read from is the framework's.
- **A framework that generates no API document.** The cross-check then has nothing to compare against and
  that file is not written. The construct smoke, the CORS preflight and the size-limit probe still are,
  and rule 3 — a walk that discovers nothing is a failure — matters more, not less.

## Rules

Consult `test-principles` for the testing constitution.

1. **Every test discovers its inputs from `real_app`** — never from a hand-written `_endpoints()` / `_EXPECTED` / `RESOURCES` table. The cost of adding a new endpoint must be zero in this directory.
2. **Walk the routes the way the framework's own document generator does, never a hand-rolled filter over the app's route list.** A filter that keeps only the framework's route class finds *zero* operations on a FastAPI that defers `include_router` — measured — and an empty walk passes green (rule 3). The generator's own walk (`iter_route_contexts(app.routes)`) also reports each route under its EFFECTIVE path, include-time prefix and all, so both sides of a comparison key on the same string.
3. **A walk that discovers nothing is a failure, not a pass.** Every file here asserts the walk returned operations before comparing them; `mismatches == []` over an empty walk passes green having proved nothing, and that is the shape a previous walk actually degenerated into.
4. **OpenAPI cross-check compares decorator-declared codes to spec codes.** The `iter_route_contexts(app.routes)` walk of Rule 2 supplies the *key* the two sides meet on — the effective path, include-time prefix and all — and only the key. The decorator side comes off the route context: `responses`, a route internal reached with `getattr`, is FastAPI's authoritative store of what the `responses=error_responses(...)` decorator put there. The document side comes out of `app.openapi()`, read per `(METHOD, path)`; the route context does not carry it. The two are compared exactly **except** for the validation code the framework inserts on its own — FastAPI publishes a `422` on any operation whose input it validates, whether or not the decorator declared one, and the decorator side cannot see it. The template keeps that one code in `_FRAMEWORK_VALIDATION_CODE` and subtracts it from the `extra` set; comparing without the exemption reds every route that takes any input at all, measured. Bounded that way, the test catches decorator mismatches and genuine framework drift both. **Exempt exactly what the framework inserts unasked, and nothing else** — every code added to that exemption is a code this test stops checking, and the list is re-derived per framework by measuring a live app, never copied.
5. **Each file holds one invariant.** Don't merge `test_cors.py` and `test_request_size_limit.py` even though both are tiny — failures in one don't mask the other, and the file names form the spec.
6. **CORS test uses an OPTIONS preflight.** Asserting on a GET response's `Access-Control-Allow-Origin` is a softer test; the preflight is the one browsers actually consult.
7. **Request-size test uses raw bytes**, not JSON-encoded data, to bypass schema validation and hit the middleware directly. Otherwise the response is `422` (validation) before the middleware sees the body.
8. **No authenticated client here.** Every test in this skill reads OpenAPI or route metadata, or probes an unauthenticated path. A test here that needs a token is either the auth probe (`hex-test-restapi-auth`) or a per-endpoint concern (`hex-test-restapi-endpoint`).
9. **Test markers and async mode** → `test-principles`.
10. **Parametrize from the discovered list at collection time — one reported case per discovered item, never a loop inside a single test.** A loop stops at the first failure and says nothing about the items it never reached, so one broken route hides the rest. The runner's collection hook (`pytest_generate_tests`) is what can read a list discovered at import time; a fixture cannot feed parametrization.
11. **Emit only the files the app's features justify.** `test_openapi_advertises_error_codes.py` and `test_cors.py` are always produced; `test_request_size_limit.py` only with a size-cap middleware; `test_info.py` only with an info or health endpoint. A file whose module-level imports name something the app does not have fails at collection time and takes down the whole `tests/integration/api/` package — which is also why the auth probe is `hex-test-restapi-auth`'s and is emitted only by an app that declares auth.
12. **`test_app_constructs.py` is the always-emitted, unit-level construct smoke.** It is the one file this skill places at `tests/unit/restapi/`, not `tests/integration/api/`, because it needs no database (factories are lazy — `create_app` builds the composition root but resolves nothing, so it opens nothing) and must run with no Docker daemon — the environment where the other gates pass and a construct-time dependency gap (`python-multipart`, …) slips through. Construct via `create_app()` directly (no `real_app` fixture), assert `app.openapi()["paths"]`. Sync, no fixtures, no `await`. It is structural (green on freshly laid routes), so every app gets it, auth or not.

## Inlined typing / import rules

- `pytest`, `fastapi`, `fastapi.routing`, `httpx`, `myapp.restapi.main`.
- Full annotations on every helper.
- No `from __future__ import annotations`.

## Hard stops

- Spec asks to maintain a hand-rolled list of `(method, path, codes)` to compare against → stop, the whole point is discovery from `real_app` / `app.openapi()`.
- Spec asks to add a `@pytest.mark.integration` marker → stop, use `test-principles`.
- Spec asks to fold a per-endpoint test into one of these files → stop, these files hold discovered global properties only; a single endpoint's behaviour belongs to `hex-test-restapi-endpoint`.
- Spec compares the OpenAPI spec to a hardcoded `_EXPECTED` table → stop, derive expectations from the route context's `responses` so the source of truth is the decorator.
- Nothing up-tree builds the app on the test's own infrastructure bindings — the `real_app` fixture under this catalogue's binding, owned by `hex-test-integration-setup` → stop, the suite cannot collect without it. (No authenticated client is consumed here — Rule 8 — so the absence of the auth fixture set does not block this skill.)
- Spec hardcodes a CORS origin (e.g. `http://localhost:3000`) in `test_cors.py` → stop, read a configured origin off `real_app`'s `CORSMiddleware` and `pytest.skip` when none is configured; never freeze the source app's dev origin or assume `allow_credentials`.
- Spec hardcodes the request-size limit (e.g. 10 MiB) in `test_request_size_limit.py`, or presumes the middleware is always present → stop, read the cap off the app's `MaxRequestSizeMiddleware` and compute `limit + 1`; `pytest.skip` when no size middleware is declared (it is a per-app `restapi.middlewares` entry, not universal).
- Project has no `/info` (or `/health`) endpoint and the spec sets `info_endpoint = none` → stop, produce four files, skip `test_info.py`.
- Spec asks for an authentication probe here → stop, use `hex-test-restapi-auth`; it owns that invariant and is emitted only by an app that declares auth.
- Spec proposes placing `test_app_constructs.py` under `tests/integration/` (next to the other app-wide invariants) → stop, it stays at `tests/unit/restapi/`: under `tests/integration/` the session-autouse `_migrated_db` / `_guard_against_real_db` fixtures would force Postgres on a check that opens no connection, so it could no longer run without a Docker daemon — the one place the construct-time defect class is catchable.
- Spec makes the construct smoke `async` / gives it `real_app` or any DB fixture → stop, it constructs via `create_app()` directly and is plain sync; needing a fixture means it is no longer the Docker-less unit smoke.
