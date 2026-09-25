---
name: hex-restapi-app
description: Use when bootstrapping a FastAPI shell once per project, or changing request handling shared by every route — `restapi/main.py`, `restapi/error_handler.py`, `restapi/schemas/errors.py`, app lifecycle, CORS, middleware, central error translation. Not one resource's router (`hex-restapi-endpoint`) or its wire models (`hex-restapi-schema`).
paths: ["**/restapi/**", "**/api/**"]
---

# Hex REST App

The shell every route lands inside, and the middleware layers that wrap it. The shell is laid once per project so subsequent work (`hex-restapi-endpoint`, `hex-restapi-schema`) has somewhere to go; a middleware is added whenever a cross-cutting per-request concern appears. After bootstrap, the only file this skill ever touches again is `restapi/main.py` (when a router needs to be registered or a CORS-exposed header added), and that's normally folded into the consuming skill.

## When to use vs. neighbours

- Laying the FastAPI entrypoint for the first time, or adding a middleware that wraps every route → this skill.
- A new router added afterwards, or logic for one route → `hex-restapi-endpoint`, a thin route over an application handler that also `app.include_router(...)`s itself.
- A resource's request/response models added into the `schemas/` package this skill creates → `hex-restapi-schema`.
- A new domain exception is plumbed → `exception-catalog` (creates/extends `domain/exceptions.py`); the catalog used by `error_responses(...)` derives from `domain.exceptions.__all__` automatically.
- A middleware introducing a new HTTP status → `hex-restapi-endpoint`, the middleware-code path in its `CONTRACTS.md`.
- Authenticating a caller or gating a route on a role → `hex-restapi-auth`; route auth is a FastAPI dependency, not a middleware, and it is optional — this shell is complete without it.
- Which error codes a route advertises → `hex-restapi-endpoint`.
- Constructing or extending the composition root this shell attaches → `hex-wiring`.
- Creating the application handlers routes receive from it → `hex-application`.
- Whether the service should be hexagonal at all → `architecture-choice`; the project substrate, dependencies, lint and initial Alembic setup around this shell → `hex-project-setup`.
- An HTTP service with no rules of its own to protect — internal CRUD over its store, a webhook, a proxy → `flat-entrypoint`'s HTTP trigger shape, in the `pyhouse-flat` plugin, once `architecture-choice` has settled the family.
- Middleware class naming and the `restapi/middleware/` package layout → `naming` and `python-packaging`.
- The app-construction smoke test, the CORS-preflight and request-size-limit checks → `hex-test-app-invariants`.

**This is the app shell; per-resource work lands inside it.** Produced once per project. `hex-restapi-endpoint` and `hex-restapi-schema` add their routers and schema modules into the `main.py` / `schemas/` this skill creates, and the advertised codes and the upload/download kinds in `hex-restapi-endpoint` extend routes the shell hosts — so the shell must already exist when they run. That is a structural precondition (the artifacts depend on the shell), not a fixed run-schedule this skill dictates. **The shell presumes no middleware** — no request-size cap, no request id. `main.py` leaves a placeholder where they are wired in, after CORS, and the middleware section below is the form each one takes.

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
    await app.state.dishka_container.close()

def create_app(container: AsyncContainer | None = None) -> FastAPI:
    app = FastAPI(title="Foo Service", lifespan=_lifespan)

    app.add_middleware(
        CORSMiddleware,
        # Deployment config: set every value from the app's settings, empty until configured.
        allow_origins=[],
        allow_credentials=False,
        allow_methods=[],
        allow_headers=[],
        expose_headers=[],
    )

    # Application middlewares go here, after CORS.

    register_error_handlers(app)

    # Routers added by hex-restapi-endpoint:
    # from .routers.foos import router as foos_router
    # app.include_router(foos_router)

    setup_dishka(container=container or create_container(), app=app)
    return app
```

Notes:

- **`lifespan` is the resource-teardown hook**, and closing the composition root is the whole of it. Each long-lived handle declares its own release beside its construction (`hex-wiring`) and runs in reverse order of construction, so this file never names a datastore and never grows a per-app variant; an app that opens nothing disposable still closes cleanly.
- **Every CORS value is deployment config, not a code constant.** The empty defaults mean no cross-origin access until the settings supply it. Never bake a dev origin such as `http://localhost:3000`; a `"*"` default is the same undeclared decision made where the deployment can no longer make it, and with `allow_credentials=True` it is the one combination browsers refuse outright. `expose_headers` starts empty too: a route that needs the browser to read a non-default response header adds it — a file-download route adds `"Content-Disposition"` (`hex-restapi-endpoint`).
- **Application middlewares are added after CORS, and none are presumed** — not even a request-size cap. Starlette wraps the last-added outermost, so the last one listed is the request's outermost layer and CORS sits innermost (rule 10).
- **`setup_dishka` is called last**, after the routers are included: it attaches the composition root to the app (as `app.state.dishka_container`) and installs the middleware that opens and closes a per-request scope. Every construction path must reach it before the app is served.
- **The `container` parameter is the test seam.** `hex-test-integration-setup` passes a composition root built with test bindings; production passes nothing and gets `create_container()`.
- **The router-include block is a placeholder.** Subsequent `hex-restapi-endpoint` invocations add their own `app.include_router(...)` line.

### `restapi/error_handler.py`

```python
import structlog
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from myapp.domain.exceptions import DomainError, ValidationError

from .schemas.errors import ErrorResponse

__all__ = ["register_error_handlers"]

log = structlog.get_logger()

def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def _handle_domain_error(request: Request, exc: DomainError) -> JSONResponse:
        level = log.warning if exc.http_status < 500 else log.error
        level(
            "request_failed",
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

    @app.exception_handler(RequestValidationError)
    async def _handle_invalid_request(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        fields = [".".join(str(part) for part in error["loc"]) for error in exc.errors()]
        translated = ValidationError("request validation failed", {"fields": fields})
        return await _handle_domain_error(request, translated)

    @app.exception_handler(Exception)
    async def _handle_unexpected(request: Request, exc: Exception) -> JSONResponse:
        log.error(
            "request_crashed",
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

**The framework's own input rejection is translated, not left in the framework's shape.** FastAPI
rejects a malformed path parameter, query parameter or body before any route runs, and by default
answers with its own `{"detail": [...]}` body — a second error shape beside the `ErrorResponse` every
route advertises for the input-validation status (`hex-restapi-endpoint`). The request-validation
handler turns that rejection into the catalogue's `ValidationError` and hands it to the domain handler,
so it is rendered and logged in the one place everything else is (`exception-catalog`), with the
catalogue's code and status. `context` names the rejected fields by location (`body.name`,
`path.id`) and never echoes the input values, which may carry a secret. It is a translation of the
framework's exception into the catalogue, not a branch in the translator, so rule 3's cap is untouched.
This is why the shell needs `ValidationError` in the catalogue alongside `DomainError`.

**This handler is the only place a hexagonal app logs an error.** `python-style`'s allocation table gives
the entrypoint that row — the domain and infrastructure never log, and the application layer logs
successes only. Without the calls above a generated app logs failures nowhere. The **level rule** lives in `python-style` beside that table
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

# Codes no DomainError class produces; INTERNAL_ERROR is the unhandled-exception code.
MIDDLEWARE_ERRORS: dict[str, int] = {"INTERNAL_ERROR": 500}

# Only the statuses whose OpenAPI wording this app overrides; empty by default.
DESCRIPTION_OVERRIDES: dict[int, str] = {}

def _describe(code: int) -> str:
    if code in DESCRIPTION_OVERRIDES:
        return DESCRIPTION_OVERRIDES[code]
    try:
        return HTTPStatus(code).phrase
    except ValueError:
        # A vendor-specific status the stdlib does not know: the number, not invented wording.
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
    # Exactly FastAPI's `responses=` type; a narrower value type fails strict mypy at the decorator.
    out: dict[int | str, dict[str, Any]] = {
        c: {"model": ErrorResponse, "description": _describe(c)}
        for c in codes
    }
    return out
```

The domain-side registry is **derived dynamically** from `domain.exceptions.__all__`. Adding a new `DomainError` subclass automatically widens the allowed `error_responses(...)` codes — no manual append, no `domain/error_catalog.py` to maintain.

Status descriptions are **looked up, not listed** — `HTTPStatus(code).phrase` names every standard status, so adding a `DomainError` with a status no route used before needs no edit to this file. `DESCRIPTION_OVERRIDES` exists for the app that must word one status differently; it starts empty and an entry equal to the standard phrase is noise.

`MIDDLEWARE_ERRORS` registers the codes emitted outside the domain catalogue, where no `DomainError` class produces them. `INTERNAL_ERROR` is always present: the unhandled-exception handler returns it when no catalogue class was raised at all. Its status is already derivable (`DomainError` defaults to 500); its **code string** is not, and a code is a stable wire contract clients key on (`exception-catalog`), so it is registered here rather than invented at the call site. `hex-restapi-endpoint`'s middleware-code path adds an entry when a declared middleware introduces a code — a size-cap middleware's `PAYLOAD_TOO_LARGE` → 413.

This file is the **single source of truth** for the error wire-shape, the `error_responses(...)` helper, the description lookup, and `MIDDLEWARE_ERRORS`. `hex-restapi-endpoint` only *references* it and appends to `MIDDLEWARE_ERRORS` on the rare middleware-code path — it never restates this template.

### `restapi/schemas/__init__.py`

```python
from . import errors
from .errors import *

__all__ = errors.__all__
```

Per-resource schema modules (e.g. `foos.py`) are added later by `hex-restapi-schema`. Each holds one resource's request and response models together — a closed set of declarations named for what it describes, which `python-packaging` lets share a module — and package updates follow `python-packaging`.

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

### How this binding spells the middleware obligations — raw ASGI, Starlette

Each line below is one obligation from `## Rules` in this stack's spelling; none of them is an
obligation of its own.

- **Raw ASGI callable, never a `starlette.middleware.base.BaseHTTPMiddleware` subclass** — that class
  buffers the whole body, which breaks streaming and the size cap. Reaching for
  `BaseHTTPMiddleware` → stop, write the raw ASGI class.
- **Exact shape** (rule 7). `__init__(self, app: ASGIApp, <config…>)` stores `app` plus the config on
  `self`; `async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None`. Configuration
  arrives as constructor keyword arguments passed at `app.add_middleware(Cls, **config)`, and the
  constructor validates them there.
- **Pass non-`http` scopes straight through** (rule 8) —
  `if scope["type"] != "http": await self._app(scope, receive, send); return`. Lifespan and websocket
  scopes must not be intercepted.
- **Reject before the wrapped app** (rule 9) — `return` **before** `await self._app(...)`, with the body
  built from `ErrorResponse`.
- **Starlette wraps the last-added outermost** (rule 10). Each `app.add_middleware(...)` call wraps the
  app as a new **outermost** layer, so the **last** one added is the first to see a request and the last
  to touch a response. A size cap is therefore added **last**.

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

### Middleware

- **A framework with its own middleware abstraction** — Litestar, Django, or a decorator-based hook.
  Unchanged: transport-only scope, configuration fixed and validated at wiring time, the shared error
  body with a registered code, and a deliberate order. What changes: the class shape and how
  non-matching traffic is passed through, and whether the framework's own base class buffers the body —
  the reason the primary binding refuses one here.
- **A reverse proxy or gateway in front of the app.** A concern that is purely about bytes on the wire —
  a size ceiling, a request id — may live there instead of in the app, and then no middleware is written
  at all. Unchanged: the status it returns still needs a registered code if a client can see it
  (`hex-restapi-endpoint`), and the app keeps its own defence in depth where the edge can be
  bypassed.

### Dependency injection

- **`dependency-injector`.** The shell, the middleware order, the error handlers and the schemas are unchanged. What changes is the two ends of the composition root: `create_app` attaches it to `app.state` itself rather than calling an integration's setup function, and `_lifespan` must dispose each long-lived handle **by name** (`await container.engine().dispose()`) — which means this file grows a per-app teardown variant and has to be kept in step with what `containers.py` actually opened. That coupling is the reason the primary binding closes the composition root instead.

## Rules

1. **One-shot.** This skill runs once per project. After bootstrap, this file set is stable; updates to `main.py` go through whichever skill needs them (typically `hex-restapi-endpoint` appending an `include_router(...)` line).
2. **The catalog is dynamic.** Never reintroduce `domain/error_catalog.py`. The registry derives from `domain.exceptions.__all__` at import time.
3. **The translator stays minimal.** `restapi/error_handler.py` has **at most one** `isinstance` branch — the primary template this skill publishes has none, and an app that declares auth adds exactly one, for the RFC-7235 challenge (`hex-restapi-auth`). All other behavior comes from the `DomainError` subclass's `code` / `http_status`. The framework's own rejection of malformed input is translated into the catalogue's validation class and rendered by the same handler, so a route's advertised input-validation response is the body the client actually receives.
4. **Resource teardown is triggered in `lifespan` and declared in the composition root.** `main.py` closes the composition root once; *what* that releases is decided where each resource is constructed (`hex-wiring`). `main.py` never names a datastore, so it never falls out of step with the ones the app actually opened.
5. **Routes receive their dependencies by type** (`hex-restapi-endpoint`); `main.py` neither resolves anything nor exposes the composition root for others to resolve from. Never module-level resolution.

6. **A middleware is transport-level and nothing else.** Bytes, headers, timing, the logging context.
   Anything that needs a domain entity, a repository or an application handler is not a middleware.
   Naming and module layout follow `naming` and `python-packaging`, under `restapi/middleware/`.
7. **A middleware's configuration is fixed and validated at wiring time.** It holds the wrapped
   application plus its configuration and nothing else, built once; every per-request value — the
   request id, the declared content length — is a local, never stored on the instance. A bad
   configuration value fails when the app is assembled, not mid-request.
8. **A middleware acts only on the kind of traffic it is for, and passes every other kind through
   untouched.** An HTTP concern must not intercept the framework's startup, shutdown or non-HTTP
   connections; a middleware that swallows one of those breaks a part of the app it was never about.
9. **A middleware that rejects a request emits the app's own error body, with a registered code.** Same
   `{"code", "message", "context"}` shape the central translator emits, built through the shared schema
   rather than hand-rolled, carrying the status it owns and a **stable** machine-readable code — the
   API contract and `MIDDLEWARE_ERRORS` in `schemas/errors.py` key on that string
   (`hex-restapi-endpoint`). A middleware that does not reject always reaches the wrapped app.
10. **The order middlewares see a request in is chosen, not inherited.** Which one sees the raw request
    first is a decision the app makes — a size cap has to see it before anything has read the body —
    and it is written according to whatever wrapping rule the framework applies to the order they are
    registered in. The relative order is the consuming app's decision; that it was decided is not.

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

- Asked to add `domain/error_catalog.py` → stop, reject as obsolete; the catalog is dynamic.
- Asked to attach business logic to lifespan → stop, reserve lifespan for infrastructure teardown only: disposing the resources the app's datastores opened.
- Asked to make the translator branch on a second exception class → stop, encode new behavior via subclass `code`/`http_status` instead; the one sanctioned branch is the auth challenge (`hex-restapi-auth`). The request-validation handler in the template is not such a branch: it translates the framework's input rejection into the catalogue's `ValidationError` and hands it to the domain handler, so it stays.
- `domain/exceptions.py` does not exist yet → stop, use `exception-catalog` bootstrap first.
- `myapp/containers.py` does not exist yet → stop, use `hex-wiring` first.
- `lifespan` is asked to dispose a named engine or client → stop, declare that release beside the resource's construction in `hex-wiring`; `lifespan` closes the composition root and nothing else.
- A concern is for one route rather than all → stop, use `hex-restapi-endpoint` plus a handler.
- A middleware needs a domain entity, a repository or an application handler → stop, use `hex-application` for application logic.
- A middleware authenticates or authorizes → stop, use `hex-restapi-auth`; caller authentication is a route dependency, not a middleware.
- A middleware introduces an HTTP status with no domain exception behind it → stop, use `hex-restapi-endpoint`, the middleware-code path in its `CONTRACTS.md`, to register the code.
