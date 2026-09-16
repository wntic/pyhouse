---
name: hex-restapi-app
description: Use when bootstrapping a FastAPI shell once per project, or changing request handling shared by every route — `restapi/main.py`, `restapi/error_handler.py`, `restapi/schemas/errors.py`, app lifecycle, CORS, middleware, central error translation. Not one resource's router (`hex-restapi-endpoint`) or its wire models (`hex-restapi-schema`).
paths: ["**/restapi/**", "**/api/**"]
---

# Hex REST App

The shell every route lands inside, and the middleware layers that wrap it. The shell is laid once per project so subsequent work (`hex-restapi-endpoint`, `hex-restapi-schema`, `hex-restapi-route-contracts`) has somewhere to go; a middleware is added whenever a cross-cutting per-request concern appears. After bootstrap, the only file this skill ever touches again is `restapi/main.py` (when a router needs to be registered or a CORS-exposed header added), and that's normally folded into the consuming skill.

## When to use vs. neighbours

- Laying the FastAPI entrypoint for the first time, or adding a middleware that wraps every route → this skill.
- A new router added afterwards, or logic for one route → `hex-restapi-endpoint`, a thin route over an application handler that also `app.include_router(...)`s itself.
- A resource's request/response models added into the `schemas/` package this skill creates → `hex-restapi-schema`.
- A new domain exception is plumbed → `exception-catalog` (creates/extends `domain/exceptions.py`); the catalog used by `error_responses(...)` derives from `domain.exceptions.__all__` automatically.
- A middleware introducing a new HTTP status → `hex-restapi-route-contracts`, the middleware-code path.
- Authenticating a caller or gating a route on a role → `hex-restapi-auth`; route auth is a FastAPI dependency, not a middleware, and it is optional — this shell is complete without it.
- Which error codes a route advertises → `hex-restapi-route-contracts`.
- Constructing or extending the composition root this shell attaches → `hex-wiring`.
- Creating the application handlers routes receive from it → `hex-application`.
- Whether the service should be hexagonal at all → `architecture-choice`; the project substrate, dependencies, lint and initial Alembic setup around this shell → `hex-project-setup`.
- Middleware class naming and the `restapi/middleware/` package layout → `naming` and `python-packaging`.
- The app-construction smoke test, the CORS-preflight and request-size-limit checks → `hex-test-discovery-invariants`.

**This is the app shell; per-resource work lands inside it.** Produced once per project. `hex-restapi-endpoint` and `hex-restapi-schema` add their routers and schema modules into the `main.py` / `schemas/` this skill creates, and `hex-restapi-route-contracts` and the upload/download kinds in `hex-restapi-endpoint` extend routes the shell hosts — so the shell must already exist when they run. That is a structural precondition (the artifacts depend on the shell), not a fixed run-schedule this skill dictates. **The shell presumes no middleware** — no request-size cap, no request id. `main.py` leaves a placeholder where they are wired in, after CORS, and the middleware section below is the form each one takes.

## Template(s) — FastAPI, dishka-wired

**The shell presumes no authentication.** The templates below are the complete file set for a service with no auth at all — an API behind an authenticating gateway, an mTLS-fronted service, an internal worker-facing API, or simply a public one. The translator is a bare `DomainError` dispatcher with no auth import and no auth branch, and there is no `restapi/dependencies.py`: FastAPI's home for shared route dependencies has no occupant until something needs one. An app that **does** declare auth adds the dependency file and one `isinstance` branch to the translator — both owned by `hex-restapi-auth`, which states what changes here and what does not. Whether an app has auth follows from its routes (some endpoint non-anonymous, or a token-verifier capability wired), never from a separate flag.

```
src/myapp/restapi/
├── __init__.py
├── main.py
├── error_handler.py
└── schemas/
    ├── __init__.py
    └── errors.py
```

### `restapi/main.py`

```python
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from dishka import AsyncContainer
from dishka.integrations.fastapi import setup_dishka
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from myapp.containers import create_container

from .error_handler import register_error_handlers

__all__ = ["create_app"]

@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncGenerator[None]:
    yield
    # One line, whatever the app's datastores are. Closing the composition root
    # runs the release half of every resource factory that declared one — the
    # relational engine's dispose, a client store's close — in reverse order of
    # construction. An app that opens nothing disposable still closes cleanly,
    # so there is no variant of this teardown and nothing to keep in step with
    # `containers.py`.
    await app.state.dishka_container.close()

def create_app(container: AsyncContainer | None = None) -> FastAPI:
    app = FastAPI(title="Foo Service", lifespan=_lifespan)

    app.add_middleware(
        CORSMiddleware,
        # Every CORS value is deployment config, not a code constant — set all four
        # from the app's settings/env. Empty defaults = no cross-origin until
        # configured; never bake a dev origin like "http://localhost:3000". A "*"
        # default is the same undeclared decision as a baked origin, made where the
        # deployment can no longer make it — and with allow_credentials=True a "*"
        # origin is the one combination browsers refuse outright.
        allow_origins=[],
        allow_credentials=False,
        allow_methods=[],
        allow_headers=[],
        # Empty by default. A route that needs the browser to read a non-default
        # response header adds it here — e.g. a file-download route adds
        # "Content-Disposition" (see hex-restapi-endpoint). Don't pre-list it.
        expose_headers=[],
    )

    # Custom application middlewares are added here, AFTER CORS. Starlette wraps the last-added outermost, so the last middleware
    # listed is the request's outermost layer; CORS (added above) sits innermost.
    # None are presumed — not even a request-size cap.

    register_error_handlers(app)

    # Routers added by hex-restapi-endpoint:
    # from .routers.foos import router as foos_router
    # app.include_router(foos_router)

    setup_dishka(container=container or create_container(), app=app)
    return app
```

Notes:

- **`lifespan` is the resource-teardown hook**, and closing the composition root is the whole of it. Each long-lived handle declares its own release beside its construction (`hex-wiring`), so this file never names a datastore and never grows a per-app variant.
- **`setup_dishka` is called last**, after the routers are included: it attaches the composition root to the app (as `app.state.dishka_container`) and installs the middleware that opens and closes a per-request scope. Every construction path must reach it before the app is served.
- **The `container` parameter is the test seam.** `hex-test-integration-setup` passes a composition root built with test bindings; production passes nothing and gets `create_container()`.
- **The router-include block is a placeholder.** Subsequent `hex-restapi-endpoint` invocations add their own `app.include_router(...)` line.

### `restapi/error_handler.py`

```python
import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from myapp.domain.exceptions import DomainError

from .schemas.errors import ErrorResponse

__all__ = ["register_error_handlers"]

log = structlog.get_logger()

def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
        level = log.warning if exc.http_status < 500 else log.error
        level(
            "domain_error",
            code=exc.code,
            http_status=exc.http_status,
            path=request.url.path,
            method=request.method,
            context=exc.context,
        )
        return JSONResponse(
            status_code=exc.http_status,
            content=ErrorResponse(
                code=exc.code,
                message=str(exc),
                context=exc.context,
            ).model_dump(),
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        log.error(
            "unhandled_error",
            error=exc.__class__.__name__,
            path=request.url.path,
            method=request.method,
            exc_info=exc,
        )
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                code="INTERNAL_ERROR",
                message="Internal server error",
                context={},
            ).model_dump(),
        )
```

The translator stays minimal forever. New domain exceptions plug in without touching this file — the
handler dispatches on the attributes defined by `exception-catalog`. The block above is the primary
form and has **no** `isinstance` branch at all, because an app with no auth has no `UnauthorizedError`
in its catalog to branch on.

**This handler is the only place a hexagonal app logs an error.** `python-style`'s allocation table gives
the entrypoint that row — the domain may not log at all, the application layer logs successes only, and
infrastructure logs the low-level cause, never the translated exception. Without the calls above a
generated app logs domain failures nowhere. The **level rule** lives in `python-style` beside that table
(4xx → `warning`, 5xx → `error`, non-`DomainError` → `error`); this file owns only the **call** that
implements it, because the call is framework-shaped and the rule is not.

`INTERNAL_ERROR` is the one response `code` not minted by `exception-catalog`, and deliberately so: by
definition no catalogue class was raised. It is a constant of this template, not a new catalogue entry.

#### `error_handler.py` — authenticated variant (the app declares auth)

An app that declares auth adds the `UnauthorizedError` import and the translator's single `isinstance`
branch, which attaches the RFC-7235 `WWW-Authenticate` challenge. Nothing else in the file changes, and
rule 3 below caps the file at **at most one** branch. The variant itself, with the realm rule that goes
with it → `hex-restapi-auth`.

### `restapi/schemas/errors.py`

```python
from http import HTTPStatus
from typing import Any

from pydantic import BaseModel, Field

from myapp.domain import exceptions as _domain_exceptions
from myapp.domain.exceptions import DomainError

__all__ = ["DESCRIPTION_OVERRIDES", "ErrorResponse", "MIDDLEWARE_ERRORS", "error_responses"]

class ErrorResponse(BaseModel):
    code: str
    message: str
    context: dict[str, object] = Field(default_factory=dict)

# Codes emitted outside the domain catalogue — no DomainError class produces them.
# INTERNAL_ERROR is always present: the unhandled-exception handler returns it when no
# catalogue class was raised at all. The status 500 is already derivable (DomainError
# defaults to it); the CODE STRING is not, and it is a wire contract clients key on, so
# it is registered here rather than invented at the call site (`exception-catalog` rule 1).
# The hex-restapi-route-contracts middleware-code path adds an entry when a declared
# middleware introduces a code (e.g. a size-cap middleware → PAYLOAD_TOO_LARGE 413).
MIDDLEWARE_ERRORS: dict[str, int] = {"INTERNAL_ERROR": 500}

# The OpenAPI description of a status is the standard reason phrase, looked up per
# status rather than listed: a status this app never used before needs no edit here.
# This dict is EMPTY by default and holds only the statuses whose wording this app
# must override — a deliberate deviation, never a restatement of the standard phrase.
DESCRIPTION_OVERRIDES: dict[int, str] = {}

def _describe(code: int) -> str:
    if code in DESCRIPTION_OVERRIDES:
        return DESCRIPTION_OVERRIDES[code]
    try:
        return HTTPStatus(code).phrase
    except ValueError:
        # A status the stdlib does not know — a vendor-specific code from a
        # middleware. Fall back to the number rather than inventing wording.
        return str(code)

def _all_known_statuses() -> set[int]:
    domain_statuses: set[int] = set()
    for name in _domain_exceptions.__all__:
        cls = getattr(_domain_exceptions, name)
        if isinstance(cls, type) and issubclass(cls, DomainError):
            domain_statuses.add(cls.http_status)
    return domain_statuses | set(MIDDLEWARE_ERRORS.values())

def error_responses(*codes: int) -> dict[int | str, dict[str, Any]]:
    known = _all_known_statuses()
    unknown = [c for c in codes if c not in known]
    if unknown:
        raise ValueError(
            f"HTTP statuses not produced by any DomainError or middleware: {unknown}"
        )
    # `dict[int | str, dict[str, Any]]` is exactly FastAPI's `responses=` parameter type —
    # a narrower `dict[str, object]` value trips a strict-mypy arg-type error at the decorator.
    out: dict[int | str, dict[str, Any]] = {
        c: {"model": ErrorResponse, "description": _describe(c)}
        for c in codes
    }
    return out
```

The domain-side registry is **derived dynamically** from `domain.exceptions.__all__`. Adding a new `DomainError` subclass automatically widens the allowed `error_responses(...)` codes — no manual append, no `domain/error_catalog.py` to maintain.

Status descriptions are **looked up, not listed** — `HTTPStatus(code).phrase` names every standard status, so adding a `DomainError` with a status no route used before needs no edit to this file. `DESCRIPTION_OVERRIDES` exists for the app that must word one status differently; it starts empty and an entry equal to the standard phrase is noise.

This file is the **single source of truth** for the error wire-shape, the `error_responses(...)` helper, the description lookup, and `MIDDLEWARE_ERRORS`. `hex-restapi-route-contracts` only *references* it and appends to `MIDDLEWARE_ERRORS` on the rare middleware-code path — it never restates this template (the two copies once drifted; do not reintroduce a second copy).

### `restapi/schemas/__init__.py`

```python
from . import errors
from .errors import *

__all__ = errors.__all__
```

Per-resource schema modules (e.g. `foos.py`) are added later by `hex-restapi-schema`; package updates follow `python-packaging`.

### `restapi/__init__.py`

```python
```

Empty file — see the entrypoint carve-out in `hex-architecture`.

## Middleware

ASGI middleware follows `naming` and `python-packaging` under `restapi/middleware/`, handling a
cross-cutting request/response concern that belongs to no single route — a correlation id, a body-size
cap, rate limiting, timing. That list is open, not a fixed catalog.

Two shapes, picked by whether the middleware ever stops a request. Both share the same skeleton — the
non-`http` passthrough, `app` plus config on `self` — and differ only in whether `__call__` grows a reject
branch.

### Middleware — pass-through (observes or annotates, never short-circuits)

```python
import uuid

from starlette.types import ASGIApp, Receive, Scope, Send
from structlog.contextvars import bind_contextvars, clear_contextvars

__all__ = ["RequestIdMiddleware"]


class RequestIdMiddleware:
    def __init__(self, app: ASGIApp, header: str) -> None:
        self._app = app
        self._header = header.lower().encode()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        incoming = dict(scope["headers"]).get(self._header, b"").decode()
        request_id = incoming or str(uuid.uuid4())
        bind_contextvars(request_id=request_id)
        try:
            await self._app(scope, receive, send)
        finally:
            clear_contextvars()
```

### Middleware — short-circuit with an error (rejects before the route runs)

```python
from starlette.types import ASGIApp, Receive, Scope, Send

from ..schemas.errors import ErrorResponse

__all__ = ["MaxRequestSizeMiddleware"]

_PAYLOAD_TOO_LARGE = 413


class MaxRequestSizeMiddleware:
    def __init__(self, app: ASGIApp, max_bytes: int) -> None:
        self._app = app
        self._max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return
        declared = dict(scope["headers"]).get(b"content-length")
        if declared and int(declared) > self._max_bytes:
            await _send_error(send, _PAYLOAD_TOO_LARGE, "PAYLOAD_TOO_LARGE", "Request body too large")
            return
        await self._app(scope, receive, send)


async def _send_error(send: Send, status: int, code: str, message: str) -> None:
    body = ErrorResponse(code=code, message=message).model_dump_json().encode()
    await send(
        {"type": "http.response.start", "status": status,
         "headers": [(b"content-type", b"application/json")]}
    )
    await send({"type": "http.response.body", "body": body})
```

The cap reads the **declared** `Content-Length` and rejects before the body is read, so nothing is
buffered. It does not catch a chunked upload that omits the header, or a client that lies about its
length; that absolute byte ceiling is an **edge** concern — a reverse proxy's `client_max_body_size` —
and this middleware is the app-layer defence in depth on top of it.

## Other bindings

- **`dependency-injector`.** The shell, the middleware order, the error handlers and the schemas are unchanged. What changes is the two ends of the composition root: `create_app` attaches it to `app.state` itself rather than calling an integration's setup function, and `_lifespan` must dispose each long-lived handle **by name** (`await container.engine().dispose()`) — which means this file grows a per-app teardown variant and has to be kept in step with what `containers.py` actually opened. That coupling is the reason the primary binding closes the composition root instead.

## Rules

1. **One-shot.** This skill runs once per project. After bootstrap, this file set is stable; updates to `main.py` go through whichever skill needs them (typically `hex-restapi-endpoint` appending an `include_router(...)` line).
2. **The catalog is dynamic.** Never reintroduce `domain/error_catalog.py`. The registry derives from `domain.exceptions.__all__` at import time.
3. **The translator stays minimal.** `restapi/error_handler.py` has **at most one** `isinstance` branch — the primary template this skill publishes has none, and an app that declares auth adds exactly one, for the RFC-7235 challenge (`hex-restapi-auth`). All other behavior comes from the `DomainError` subclass's `code` / `http_status`.
4. **Resource teardown is triggered in `lifespan` and declared in the composition root.** `main.py` closes the composition root once; *what* that releases is decided where each resource is constructed (`hex-wiring`). `main.py` never names a datastore, so it never falls out of step with the ones the app actually opened.
5. **Routes receive their dependencies by type** (`hex-restapi-endpoint`); `main.py` neither resolves anything nor exposes the composition root for others to resolve from. Never module-level resolution.

6. **Middleware naming and module layout** follow `naming` and `python-packaging`, under `restapi/middleware/`. It is a **raw ASGI
   callable**, never a `starlette.middleware.base.BaseHTTPMiddleware` subclass — that buffers the whole
   body and breaks streaming and the size cap.
7. **Exact ASGI shape.** `__init__(self, app: ASGIApp, <config…>)` stores `app` plus the config on `self`;
   `async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None`. Configuration arrives
   as constructor keyword arguments, passed at `app.add_middleware(Cls, **config)`, and the constructor
   validates them at wiring time so a bad value fails on startup rather than mid-request.
8. **Pass non-`http` scopes straight through** —
   `if scope["type"] != "http": await self._app(scope, receive, send); return`. Lifespan and websocket
   scopes must not be intercepted.
9. **A middleware that rejects a request emits an `ErrorResponse`-shaped JSON body** —
   `{"code": "<STABLE_STRING>", "message": "…", "context": {}}` — with the status it owns, and `return`s
   **before** `await self._app(...)`. A pass-through always reaches that call. Keep the code string
   stable: the API contract and `MIDDLEWARE_ERRORS` in `schemas/errors.py` key on it
   (`hex-restapi-route-contracts`).
10. **No business or domain logic.** A middleware is transport-level — bytes, headers, timing, the
    structlog context. Anything needing a domain entity, a repository or an application handler is not a
    middleware.
11. **`self` holds only `app` plus config**, built once at wiring time. Any per-request value is a local
    inside `__call__` — the request id, the declared content length — never an instance attribute.
12. **Ordering is significant: Starlette wraps the last-added outermost.** Each `app.add_middleware(...)`
    call wraps the app as a new **outermost** layer, so the **last** one added is the first to see a
    request and the last to touch a response. A middleware that must see the raw request before anything
    else — a size cap — is therefore added **last**. The relative order is the consuming app's decision.

## Inlined typing / import rules

- Middleware: ASGI types from `starlette.types` (`ASGIApp`, `Scope`, `Receive`, `Send`; add `Message` only
  when `__call__` wraps `receive` / `send`).
- A middleware that rejects emits its body through the shared
  `ErrorResponse` schema (`from ..schemas.errors import ErrorResponse`) — never hand-roll the
  `{"code", "message", "context"}` dict, so the wire shape stays single-sourced.
- Typing and logging follow `python-style`.

## Package wiring

For `restapi/__init__.py` and `restapi/middleware/__init__.py`, follow `python-packaging`, with the entrypoint carve-out in `hex-architecture`.

## Hard stops

- The spec asks to add `domain/error_catalog.py` → stop, reject as obsolete; the catalog is dynamic.
- Asked to attach business logic to lifespan → stop, reserve lifespan for infrastructure teardown only: disposing the resources the app's datastores opened.
- The spec asks the translator to branch on a second exception class → stop, encode new behavior via subclass `code`/`http_status` instead; the one sanctioned branch is the auth challenge (`hex-restapi-auth`).
- `domain/exceptions.py` does not exist yet → stop, use `exception-catalog` bootstrap first.
- `myapp/containers.py` does not exist yet → stop, use `hex-wiring` first.
- Spec asks `lifespan` to dispose a named engine or client → stop, declare that release beside the resource's construction in `hex-wiring`; `lifespan` closes the composition root and nothing else.
- A concern is for one route rather than all → stop, use `hex-restapi-endpoint` plus a handler.
- A middleware needs a domain entity, a repository or an application handler → stop, use `hex-application` for application logic.
- A middleware authenticates or authorizes → stop, use `hex-restapi-auth`; caller authentication is a route dependency, not a middleware.
- Reaching for `BaseHTTPMiddleware` → stop, use the raw ASGI class; `BaseHTTPMiddleware` buffers the body
  and breaks the size cap and streaming downloads.
- A middleware introduces an HTTP status with no domain exception behind it → stop, use `hex-restapi-route-contracts`, the middleware-code path, to register the code.
