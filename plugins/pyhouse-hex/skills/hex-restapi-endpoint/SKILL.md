---
name: hex-restapi-endpoint
description: Use when adding or changing one REST route, or creating a resource's router file `restapi/routers/<resource>.py` — thin JSON routes, multipart upload, streaming download, dishka handler injection, route ordering, and which error codes the route advertises. Owns the per-operation code sets, advertise-only-what-you-produce, and the registry for a status a middleware introduces. The pydantic models are `hex-restapi-schema`; the auth dependency and the `401` / `403` that follow it are `hex-restapi-auth`.
paths: ["**/restapi/**", "**/api/**"]
---

# Hex — REST API Endpoint

Produces one HTTP endpoint for one resource. Routers grow incrementally — this skill adds one route at a time. A "router file" exists once per resource; subsequent endpoint additions extend it.

**Read the sibling `CONTRACTS.md` in this skill's own directory before choosing what a route advertises
in `responses=error_responses(...)`.** It carries the per-operation code sets, the two symbols the
decorator draws on, and the procedure for a status a middleware introduces; only `SKILL.md` is loaded
automatically.

## When to use vs. neighbours

- One new endpoint or modification of an existing one, including the multipart-upload and streaming-download kinds → this skill.
- Pydantic request/response schemas this route maps to and from → `hex-restapi-schema`.
- The `responses=error_responses(...)` declaration and which codes belong in it → this skill, in the sibling `CONTRACTS.md`.
- Defining a new error class whose status then becomes valid for `error_responses(...)`, and boundary translation → `exception-catalog`.
- Attaching an auth dependency to a route, and the `401` / `403` that follow it → `hex-restapi-auth`.
- The shell this router registers into — `restapi/main.py`, the CORS `expose_headers` list a download route extends, the request-size middleware behind a `413` → `hex-restapi-app`.
- The composition root that binds the handler this route injects → `hex-wiring`.
- Application handlers that consume upload bytes or produce download content → `hex-application`; storage capability protocols → `hex-domain-ports`.
- Testing this route through the real app → `hex-test-restapi-endpoint`; the OpenAPI and app-construction properties discovered across all routes → `hex-test-app-invariants`.
- Route, module and helper identifiers → `naming`; `__all__`, the private `_export_filename` helper and the router export → `python-packaging`.

## Template(s) — FastAPI router, dishka-injected

### File location

```
src/myapp/restapi/routers/foos.py
```

One router file per resource holds **all** of that resource's endpoint functions; the file declares the `APIRouter`, defines each endpoint function (ordered per Route ordering), and is registered once in `src/myapp/restapi/main.py` via `app.include_router(...)`. The skeleton below is the whole-file shape; an endpoint function is the per-route shape that follows it.

`route_class=DishkaRoute` on the router is what injects every `FromDishka[...]` parameter below it, so it is declared once per file and no route carries an injection decorator.

### Skeleton — router file

```python
from typing import Annotated
from uuid import UUID

from dishka.integrations.fastapi import DishkaRoute, FromDishka
from fastapi import APIRouter, Depends, Query
from fastapi.responses import Response

from myapp.application.foos import (
    CreateFooCommand,
    CreateFooHandler,
    GetFooHandler,
    GetFooQuery,
    ListFoosHandler,
    ListFoosQuery,
)
from myapp.domain.foos import FooListFilter

from ..schemas import (
    FooCreateRequest,
    FooListResponse,
    FooResponse,
    error_responses,
)

__all__ = ["router"]

router = APIRouter(prefix="/foos", tags=["foos"], route_class=DishkaRoute)
```


**The route templates below are the primary, auth-free form** — every route in an app that declares
no auth, and the public routes of an app that does. Whether an app has auth at all follows from its
routes. An authenticated route adds exactly four things to one of these templates — the auth-dependency
parameter last in the signature, the `domain.auth` + `..dependencies` imports, the `401` (and `403` when
role-gated) codes, and the `caller_id=user.id` argument where the DTO carries it — and nothing else. The
derivation, the dependency choice and the code join are `hex-restapi-auth`'s; one worked authenticated
variant is kept below, under `mixed multipart + JSON`.

### `list` (paginated read) — pagination shape mirrors `hex-domain-model`

Use the **`limit`/`offset`** template when the matching `hex-domain-model` uses limit/offset paging. Use the **`cursor`** template when it uses a cursor. The two forms are mutually exclusive — never both.

**A page size is always bounded and always defaulted** — an unbounded `limit` lets one request ask for the whole table. The *ceiling* and the *default* are the app's decision, not this skill's, so they are named module-level constants in the router file rather than literals in a signature: `Query(...)` bounds are evaluated when the route function is defined, so they cannot be injected per request, and a named constant is what lets one app state its number once and reuse it across every paginated route. `100` and `50` below are **this example's numbers**; an app picks a ceiling its list query can serve in one round trip. `ge=1` on the page size and `ge=0` on the offset are not tunable — a zero-row page and a negative offset are meaningless at any ceiling.

```python
# In the router file, beside `router = APIRouter(...)`:
_MAX_PAGE_SIZE = 100
_DEFAULT_PAGE_SIZE = 50
```

`limit`/`offset`:

```python
@router.get("", response_model=FooListResponse, responses=error_responses(422))
async def list_foos(
    handler: FromDishka[ListFoosHandler],
    limit: Annotated[int, Query(ge=1, le=_MAX_PAGE_SIZE)] = _DEFAULT_PAGE_SIZE,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> FooListResponse:
    result = await handler.execute(
        ListFoosQuery(filter=FooListFilter(limit=limit, offset=offset)),
    )
    return FooListResponse(
        items=[FooResponse(...) for foo in result.items],
        total=result.total,
        limit=limit,
        offset=offset,
    )
```

`cursor`:

```python
@router.get("", response_model=FooListResponse, responses=error_responses(422))
async def list_foos(
    handler: FromDishka[ListFoosHandler],
    cursor: Annotated[str | None, Query()] = None,
    limit: Annotated[int, Query(ge=1, le=_MAX_PAGE_SIZE)] = _DEFAULT_PAGE_SIZE,
) -> FooListResponse:
    result = await handler.execute(
        ListFoosQuery(filter=FooListFilter(cursor=cursor, limit=limit)),
    )
    return FooListResponse(
        items=[FooResponse(...) for foo in result.items],
        next_cursor=result.next_cursor,
        limit=limit,
    )
```

The `hex-restapi-schema`-produced `FooListResponse` must match the chosen pagination shape (either `total/limit/offset` or `next_cursor/limit`).

### `get` (single read)

```python
@router.get("/{id}", response_model=FooResponse, responses=error_responses(404, 422))
async def get_foo(
    id: UUID,
    handler: FromDishka[GetFooHandler],
) -> FooResponse:
    foo = await handler.execute(GetFooQuery(id=id))
    return FooResponse(...)
```

### `create` (with post-write read-back)

```python
@router.post(
    "",
    response_model=FooResponse,
    status_code=201,
    responses=error_responses(409, 422),
)
async def create_foo(
    body: FooCreateRequest,
    handler: FromDishka[CreateFooHandler],
    get_handler: FromDishka[GetFooHandler],
) -> FooResponse:
    new_id = await handler.execute(
        CreateFooCommand(name=body.name),
    )
    foo = await get_handler.execute(GetFooQuery(id=new_id))
    return FooResponse(...)
```

### `update` (PATCH with read-back)

```python
@router.patch(
    "/{id}",
    response_model=FooResponse,
    responses=error_responses(404, 409, 422),
)
async def update_foo(
    id: UUID,
    body: FooUpdateRequest,
    handler: FromDishka[UpdateFooHandler],
    get_handler: FromDishka[GetFooHandler],
) -> FooResponse:
    await handler.execute(
        UpdateFooCommand(id=id, name=body.name),
    )
    foo = await get_handler.execute(GetFooQuery(id=id))
    return FooResponse(...)
```

### `delete` (204)

```python
@router.delete(
    "/{id}",
    status_code=204,
    responses=error_responses(404, 409, 422),
)
async def delete_foo(
    id: UUID,
    handler: FromDishka[DeleteFooHandler],
) -> Response:
    await handler.execute(DeleteFooCommand(id=id))
    return Response(status_code=204)
```

### Static collection path — a collection-level action (204)

A route whose path segment is a **literal, not a parameter**: a bulk update, a reorder, a nested-collection read. Which action a resource has is the resource's own business; this template fixes only the shape, and the load-bearing part of it is the route's **position in the file** — see the ordering note below. `/bulk` below is the example's action.

```python
@router.patch(
    "/bulk",
    status_code=204,
    responses=error_responses(422),
)
async def bulk_update_foos(
    body: FooBulkUpdateRequest,
    handler: FromDishka[BulkUpdateFoosHandler],
) -> Response:
    await handler.execute(BulkUpdateFoosCommand(updates=body.updates))
    return Response(status_code=204)
```

### Route ordering — FastAPI declaration order

FastAPI resolves a request against the routes **in declaration order**, which makes the reachability
obligation (rule 18) a property of where a route sits in the file. `/bulk` is captured by `/{id}` if
`/{id}` was declared first — `"bulk"` matches the `{id}` path, fails its UUID validation, and the
request answers `422` before any handler runs; the static route is never reached.

**Declare every static collection-level path (`/bulk`, `/export`, `/bars`) above the `/{id}` route** —
any non-parameterized sibling of `/{id}`, whatever the method. When extending an existing router file,
place a new static endpoint **above** the `update` / `get_by_id` / `delete` routes for `/{id}`.

- Static collection path would be declared after `/{id}` in the file → stop, reorder.

A framework that resolves by specificity instead has no such stop: the obligation is unchanged, and
nothing in the file's layout can violate it.

File transfer breaks the otherwise-uniform CRUD shape: routes accept multipart bodies or return raw bytes. The conventions below must be repeated verbatim in any new file-transfer route — they encode several non-obvious rules and the single route-body `try/except` exemption.

**Auth follows the idiom above:** the upload and download templates below are the auth-free form, and the
mixed multipart + JSON one is kept as this skill's single worked **authenticated** variant, so the
interaction between a gated route and its advertised codes has somewhere to be read. The auth dependency
is never a frozen role; it is the slot `hex-restapi-auth` fills.

### `upload` — multipart upload

#### Pure file upload — one file

```python
@router.post(
    "/import/xlsx",
    response_model=ImportFoosResponse,
    responses=error_responses(413, 422),
)
async def import_xlsx(
    file: UploadFile,
    handler: FromDishka[ImportFoosXlsxHandler],
    bar_id: UUID = Form(...),
) -> ImportFoosResponse:
    data = await file.read()
    result = await handler.execute(
        ImportFoosXlsxCommand(bar_id=bar_id, file_data=data),
    )
    return ImportFoosResponse(...)
```

Rules:

- `file: UploadFile` for the file part. Companion scalar/UUID fields use `= Form(...)` — they share the same multipart envelope.
- `await file.read()` loads the body into memory. This is bounded **only** when the app declares a request-size cap middleware (`hex-restapi-app`'s `MaxRequestSizeMiddleware`), which rejects oversize requests before the route runs. A request-size cap is the app's own choice, not a given: if the app declares none, the body is unbounded and `file.read()` is **not** safe — the app must add a size cap (or the route must stream-and-bound the read) before relying on it. The templates here assume the app declares such a cap.
- **Advertise `413`** in `responses=error_responses(...)` **only when the app declares a request-size cap middleware** — 413 is produced by that middleware (its code registered in `MIDDLEWARE_ERRORS`), not by a domain exception, so an app without one has no 413 to advertise, and the OpenAPI discovery check (`hex-test-app-invariants`) would reject the orphan code. The `413` shown in the decorator templates is present because those templates assume a size-capped app; drop it for an app that declares no size middleware.
- The route does not parse the file — pass bytes to the handler via the command DTO (`file_data: bytes`).

#### Multiple optional uploads

```python
attachments: list[UploadFile] | None = None,
...
attachment_inputs: list[CreateFooAttachment] = []
for f in attachments or []:
    raw = await f.read()
    attachment_inputs.append(CreateFooAttachment(data=raw, mime=f.content_type or ""))
```

- The parameter type `list[UploadFile] | None = None` handles "no files attached" cleanly.
- Build a list of application input dataclasses inside the route; capture both `data` and `f.content_type or ""`. The empty-string fallback is deliberate — domain validates the mime and an empty value triggers a clear `ValidationError` rather than `None` slipping through.

#### Mixed multipart + JSON — the only sanctioned `try/except` in a route body

**This is the one worked AUTHENTICATED template in this skill, and it requires `hex-restapi-auth`.** It
is role-gated, so it advertises `403` as well as `401`: the advertised codes must match the chosen
dependency, and a role-gated route that advertises `401` but not `403` is a hard stop in
`hex-restapi-auth`. Drop the dependency, the two auth codes and the `domain.auth`/`..dependencies`
imports for the public form.

```python
@router.post(
    "",
    status_code=201,
    response_model=FooResponse,
    responses=error_responses(401, 403, 409, 413, 422),
)
async def create_foo(
    data: Annotated[str, Form()],
    handler: FromDishka[CreateFooHandler],
    attachments: list[UploadFile] | None = None,
    user: CurrentUser = Depends(require_role(Role.<MIN_RANK>)),
) -> FooResponse:
    try:
        payload = CreateFooPayload.model_validate_json(data)
    except PydanticValidationError as exc:
        raise ValidationError(str(exc)) from exc
    ...
```

Rules:

- `data: Annotated[str, Form()]` receives the JSON blob as a string. Pydantic does not automatically validate it because the parameter type is `str` — validation is explicit.
- `<Schema>.model_validate_json(data)` parses and validates.
- **The `try/except PydanticValidationError → raise ValidationError(str(exc)) from exc` is the single sanctioned `try/except` in a route body** in this codebase. It exists because Pydantic's exception raised inside a route is neither a `DomainError` nor the framework's request-validation error, so uncaught it reaches the catch-all handler and answers `500 INTERNAL_ERROR` for what is the client's malformed input. **Use this pattern verbatim — no other forms of error catching belong in a route.**
- Exception chaining follows `exception-catalog`.

This pattern is reserved for the multipart+JSON case. **Do not generalize it.** A JSON-only route uses `body: <Schema>` and lets FastAPI's normal validation flow through the central handler.

### `download` — streaming binary response

```python
@router.post("/export", responses=error_responses(422))
async def export_foos(
    body: ExportFoosFilterRequest,
    handler: FromDishka[ExportFoosHandler],
) -> StreamingResponse:
    data = await handler.execute(ExportFoosQuery(filter=_to_filter(body)))
    filename = _export_filename("csv")  # the extension this export actually produces
    return StreamingResponse(
        iter([data]),
        # The real content type the handler produces — csv / pdf / xlsx / … — not a
        # fixed format frozen from one app. Don't fall back to octet-stream for a known type.
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
```

Rules:

- **Return annotation: `-> StreamingResponse`.** No `response_model` — FastAPI does not serialize the body.
- `StreamingResponse(iter([bytes]), media_type=..., headers={...})` is the canonical shape. `iter([data])` wraps already-materialized bytes in a single-chunk iterator. If the handler produces a true `AsyncIterator[bytes]`, pass it directly without `iter([...])`.
- **`media_type` is the real content type** (xlsx / docx / pdf MIME). Don't use `application/octet-stream` for known formats — clients render based on this.
- `Content-Disposition: attachment; filename="..."` triggers download instead of inline. Filename is double-quoted; a plain ASCII filename is the simplest default, and if you need RFC 5987 encoding for non-ASCII, document it inline.

#### `_export_filename` helper

```python
def _export_filename(ext: str) -> str:
    ts = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return f"myapp-foos-{ts}.{ext}"
```

- **Name it `_<purpose>_filename`** — module-level, underscore-prefixed because it is private to the
  router module and must not be re-exported. Identifier choice otherwise follows `naming`; the
  private-export rule follows `python-packaging`.
- The shape shown (UTC timestamp `YYYYMMDD-HHMMSS`, a `myapp-foos` prefix, an extension parameter) is a reasonable default, not a fixed canon. The exact filename format — timestamp style, prefix, ASCII vs RFC 5987 — is an app-level choice; keep it consistent within one app, but don't freeze this particular shape as mandatory across apps.
- Filename construction lives in the route, not the handler. The handler returns content; the route names the artifact.

#### CORS `expose_headers`

`Content-Disposition` is not a default CORS-exposed header, so a browser strips it from the response visible to JS. **If the app has CORS configured** (`hex-restapi-app`), a download route must ensure its response header is in the CORS middleware's `expose_headers` list — the bootstrap leaves that list **empty** by default, so a download route adds `"Content-Disposition"` (and any other non-default header it sets, e.g. `X-Total-Count`) there:

```python
expose_headers=["Content-Disposition"],
```

An app with no CORS configured has no such list to extend. **Verify `expose_headers` whenever you add a headered download response** (when CORS is enabled).

## Other bindings

- **`dependency-injector`.** Everything above the signature is unchanged — decorators, status codes, route ordering, the no-`try/except` rule, read-back. What changes is that the route takes `request: Request` back and, inside the body, reaches the composition root hanging off the app state and calls the binding whose **attribute name** is the snake_case form of the handler class. That spelling becomes a contract with `hex-wiring` that nothing enforces. The router then needs no `route_class`.
- **A route-scoped injection decorator instead of the router's route class.** Where a route cannot go through the router — a websocket handler, or a `Depends` factory such as the auth dependency in `hex-restapi-auth` — the same `FromDishka[...]` parameter is injected by decorating that function with `@inject`. Use it only there; a decorator on an ordinary HTTP route means the router is missing its `route_class`.

## Rules

### Router file

1. **One module per resource.** File naming follows `naming`.
2. **Only `router` is public**; export mechanics follow `python-packaging`.
3. **`prefix` matches the file name's resource**; casing follows `naming`.
4. **`tags=[...]` echoes the resource word.**
5. **The auth imports are conditional.** `from myapp.domain.auth import CurrentUser, Role` and `from ..dependencies import get_current_user, require_role` appear **only** when the app declares auth (`hex-restapi-auth`) and this resource has ≥1 authenticated route. An auth-less app — or a router whose every route is public — omits both imports entirely; importing them would reference a `domain/auth` module and a `dependencies.py` that an auth-less app does not have. The skeleton above is the auth-free form.

### Parameter order (load-bearing for readability, not FastAPI)

6. **Parameters go in one order** — path params (`id: UUID`), then body (`body: FooCreateRequest`), then injected handlers (`handler: FromDishka[CreateFooHandler]`), which carry no default and so must precede every defaulted parameter anyway, then query params with defaults (`limit`, `offset`), and the auth dependency **last** (`_` or `user`) when the route has one — `hex-restapi-auth`.

### Status codes (defaults)

7. **The operation fixes the success status and the return type.**

| Operation | Decorator | Return type |
|-----------|-----------|-------------|
| `GET` list | default 200 | `FooListResponse` |
| `GET` single | default 200 | `FooResponse` |
| `POST` create | `status_code=201` | `FooResponse` (read-back) |
| `PATCH` update | default 200 | `FooResponse` (read-back) |
| `PATCH` collection action (`/bulk`, …) | `status_code=204` | `Response(status_code=204)` |
| `DELETE` | `status_code=204` | `Response(status_code=204)` |

For 204 endpoints, the function return annotation is `-> Response` and the body is `return Response(status_code=204)`. **Do not return `None`** — the 204 then lives in the decorator alone, and a decorator that loses its `status_code=204` answers 200 with a JSON `null` body instead of failing visibly.

### What the route advertises

The per-operation code sets, the helper and the middleware registry are in the sibling `CONTRACTS.md`.

8. **Routes only advertise.** A route never builds an error response itself: one translator owns the error body's shape, and a hand-built body is the copy that drifts from it. The error catalogue and boundary translation are `exception-catalog`'s; logging is `python-style`'s.
9. **Advertise exactly what the route can produce.** The set follows from the operation — which domain exceptions its handler can raise, which middleware sits in front of it, and whether it takes any validated input. A code that cannot occur is removed; a code that can occur and is missing makes the published document wrong in the direction clients notice last.
10. **Never hand-write the advertisement mapping** — `responses={404: {...}}` typed out at the decorator. Always go through the helper, because the helper is what checks the code against the set of codes something can actually produce; a hand-written entry is the one path by which a status nothing raises reaches the document.
11. **One hand-maintained registry, and only one.** A status a middleware introduces, with no domain exception behind it, is the only kind registered by hand; everything domain-side derives from the error catalogue's own exported set.
12. **A middleware-introduced status is registered before it is advertised.** The helper validates against the known set, so an unregistered status fails loudly at import rather than reaching the document.
13. **A route taking any validated input advertises the input-validation status.** Path parameter, query parameter, filter, pagination or body — any of them can be rejected before the handler runs, so the document must say so. It is *any-input* validation, not body validation: a lone `{id}` produces it, and only a parameterless, body-less route omits it. Where the framework publishes a response of its own for that status, the decorator still names it: the framework's entry describes the framework's error body, not the one the app sends.

### Handler injection

```python
handler: FromDishka[ListFoosHandler],
```

14. **The handler is named by its type, not by a container attribute.** The composition root (`hex-wiring`) decides what satisfies `ListFoosHandler`; the route never spells a binding's name, so renaming a handler class is a single rename that the type checker follows.
15. **The annotation is the concrete handler class**, which is also what gives the type checker `execute`.
16. **Never resolve at module level, and never hold a container reference in the module.** Injection happens per request; a module-level resolution captures state too early and defeats the per-test composition root.
17. **For create/update with read-back**, take `handler` and `get_handler` as two separate injected parameters with distinct names.

### Route reachability

18. **Every route the file declares must be the one a matching request actually reaches.** A path a more general sibling can also match is dead, and it fails silently — the wrong handler runs and answers, so there is no routing error to see. Where the framework resolves paths by a rule the file's own layout can violate — declaration order, a first-match table — satisfying that rule is part of writing the route. The FastAPI spelling and its stop are under `### Route ordering` above.

### What never goes in a route

19. **No `try/except`.** Domain exceptions propagate to the central error handler. The only sanctioned exception is the mixed multipart+JSON parse above.
20. **No logging.** Logging ownership follows `python-style`.
21. **No business logic, no policy checks, no domain construction beyond mapping body→command.**
22. **No infrastructure imports.** Only `application/*` and `domain/*` types.
23. **No `Depends` factories at module level.** The one exception is the auth pair (`hex-restapi-auth`), and even there `require_role` is called inline at each route rather than memoized.

### Handler contract for downloads

24. **The handler returns raw bytes** (or an `AsyncIterator[bytes]` for true streaming). It does not return a Pydantic model, a Response, or a file path.
25. **The route does not transform the bytes** — it only wraps them in `StreamingResponse` and attaches the filename / `Content-Disposition`.
26. **Authorization, filtering, and content generation all live in the handler.** The route is a transport adapter.

### What never goes in a file-transfer route

27. **Writing the upload to disk inside the route.** Pass bytes (or an `UploadFile`) to the handler; storage is an infrastructure concern (`hex-capability-adapter`).
28. **Computing or enforcing a per-route size limit.** `MaxRequestSizeMiddleware` is the single chokepoint. If a specific route needs a tighter cap, add it as an application-layer rule that raises `ValidationError` after parsing.
29. **Streaming without `media_type`.** Browsers and clients rely on it.
30. **Catching exceptions other than the one sanctioned `PydanticValidationError → ValidationError` translation in the mixed multipart + JSON route.** Do not extend the `try/except`.
31. **Returning `FileResponse` from a path on disk.** All file content originates from the handler's bytes. The API does not serve filesystem paths.
32. **`response_model` on a streaming route.** Meaningless and confuses OpenAPI.

## Inlined typing / import rules

- `Annotated` from `typing`; `UUID` from `uuid`; `datetime`, `UTC` from `datetime` for download filenames.
- `DishkaRoute`, `FromDishka` from `dishka.integrations.fastapi`. `Request` is **not** imported unless a route genuinely reads the raw request; reaching the composition root is not such a reason.
- `APIRouter`, `Depends`, `Query`, `UploadFile`, `Form` from `fastapi`; `Response`, `StreamingResponse` from `fastapi.responses`.
- Application handlers imported through the subpackage (`from myapp.application.foos import ...`) — see `python-packaging` for the collapsed-import convention.
- `error_responses` from `..schemas`. On an authenticated route only, `get_current_user` / `require_role` from `..dependencies` (`hex-restapi-auth`).
- `from pydantic import ValidationError as PydanticValidationError` — alias so the import doesn't shadow the domain `ValidationError`.
- Full annotations on every parameter and on the return type; no `from __future__ import annotations` (`python-style`).

## Package wiring

### When the router file is new

After adding the route(s), register the router in `src/myapp/restapi/main.py`:

```python
from .routers.foos import router as foos_router

app.include_router(foos_router)
```

## Hard stops

- The route is asked to reach a composition root off `request.app.state`, or to name a binding rather than a type → stop, declare the handler as a `FromDishka[<Handler>]` parameter.
- The route is asked to log → stop, use `python-style` for logging ownership.
- Asked for a `try/except` in the route body → stop, use the mixed multipart+JSON template only for that sanctioned case.
- The route is asked to construct a domain entity → stop, that's the handler's job; the route maps body fields to a command.
- Response schema requires fields the command/query result doesn't provide → stop, add a read-back via `GetFooHandler` (or extend the result DTO via `hex-application`).

- Asked for a `try/except` other than the mixed multipart + JSON one → stop, no other `try/except` belongs in a route body.
- The route is asked to compute file size limits → stop, that's the middleware's job.
- The route is asked to parse the file content → stop, that's the handler's job; the route passes bytes.
- A download response header beyond `Content-Disposition` is added without updating CORS `expose_headers` (when CORS is configured) → stop, update both in the same change.
- A route is asked to catch a domain exception and translate it → stop, use `exception-catalog`.
- A route that attaches no auth dependency advertises `401` or `403` → stop, those codes follow the dependency; see `hex-restapi-auth`, and in an auth-less app there is no class behind them at all.
- A third auth dependency type, or any other auth machinery, is proposed → stop, use `hex-restapi-auth`; this skill declares the codes a route advertises, not the auth layer behind them.
- The input-validation status is omitted on a route that takes a path param, query param, filter or body → stop. Where the framework publishes that response itself — FastAPI does — its entry describes the framework's error body rather than the app's, so the decorator names it too; where the framework publishes nothing of its own, the decorator is the only thing documenting the status at all.
