# hex-restapi-endpoint — file-transfer routes

Topic file of `hex-restapi-endpoint`, read before writing an upload or a download route. It states rules
24–33, which hold for file-transfer routes only, and binds them — with rule 19 of `SKILL.md` — to
**FastAPI**. Everything else in `SKILL.md` applies unchanged: the parameter order, the advertised codes,
the route ordering that puts a literal path such as `/import` above `/{id}`.

## `upload` — multipart upload

In the router file, beside `router = APIRouter(...)`, the app's upload ceiling is stated once:

```python
_MAX_UPLOAD_BYTES = 10 * 1024 * 1024


@router.post("/import", status_code=204, responses=error_responses(422))
async def import_foos(
    file: UploadFile,
    handler: FromDishka[ImportFoosHandler],
) -> Response:
    data = await file.read(_MAX_UPLOAD_BYTES + 1)
    if len(data) > _MAX_UPLOAD_BYTES:
        raise ValidationError("upload too large", {"max_bytes": _MAX_UPLOAD_BYTES})
    await handler.execute(ImportFoosCommand(data=data))
    return Response(status_code=204)
```

- `file: UploadFile` is the file part. The route passes bytes on the command; it never parses them.
- The bounded read is rule 28. Where the app declares a request-size middleware (`hex-restapi-app`),
  the route reads `await file.read()`, the constant and the two check lines go, and the decorator adds
  that middleware's `413`.
- The `422` covers both a missing file part and the over-size rejection. A handler that can raise
  more — a conflict, a not-found — adds its codes per `CONTRACTS.md`. An import whose client needs a
  result returns a response model from the resource's schema module instead of the `204`.

Several files arrive as `files: list[UploadFile]`, each read with the same bound and passed on the
command as a sequence of bytes. `ImportFoosHandler` here and `ExportFoosHandler` below are application
handlers written like any other (`hex-application`).

### Mixed multipart + JSON — the only sanctioned `try/except` in a route body

A body that carries a JSON part beside a file arrives as one form field holding a string —
`payload: Annotated[str, Form()]` beside `file: UploadFile` — which the framework does not validate:

```python
try:
    body = FooCreateRequest.model_validate_json(payload)
except PydanticValidationError as exc:
    fields = [".".join(str(part) for part in error["loc"]) for error in exc.errors()]
    raise ValidationError("invalid payload", {"fields": fields}) from exc
```

- **This is the single sanctioned `try/except` in a route body.** The library's exception raised inside
  a route is neither a `MyappError` nor the framework's request-validation error, so uncaught it reaches
  the catch-all handler and answers `500` for the client's malformed input. The context names the
  rejected fields by location and never echoes the input: the library's own message carries each
  rejected value, which may be a secret. Chaining follows `exception-catalog`.
- **Do not generalize it.** A JSON-only route takes `body: <Schema>` and lets the framework's validation
  reach the central handler.

## `download` — streaming binary response

```python
@router.get("/export")
async def export_foos(
    handler: FromDishka[ExportFoosHandler],
) -> StreamingResponse:
    data = await handler.execute(ExportFoosQuery())
    return StreamingResponse(
        iter([data]),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="foos.csv"'},
    )
```

- **Return annotation `-> StreamingResponse`, no `response_model`.** The framework does not serialize
  the body.
- `iter([data])` wraps already-materialized bytes in a single-chunk iterator; a handler that yields an
  `AsyncIterator[bytes]` is passed directly.
- `Content-Disposition: attachment; filename="..."` makes a client save rather than render. The route
  names the file, never the handler; a plain ASCII filename is the default, and RFC 5987 encoding for a
  non-ASCII one is documented inline where used.
- The route takes no input, so it advertises nothing; a filtered export takes query parameters or a
  body and advertises `422` (`CONTRACTS.md`).
- Where browsers call the API cross-origin, `Content-Disposition` is readable by a page's script only
  if the CORS middleware's `expose_headers` lists it (`hex-restapi-app`); the route that sets the header
  adds it to that setting in the same change.

## Rules

### Handler contract for downloads

24. **The handler returns raw bytes** (or an async iterator of bytes for true streaming) — never a wire
    model, a response object, or a file path.
25. **The route does not transform the bytes.** It wraps them in a streaming response and names the
    file.
26. **Authorization, filtering and content generation live in the handler.** The route is a transport
    adapter.

### What never goes in a file-transfer route

27. **Writing the upload to disk.** The route passes bytes to the handler; storage is an
    infrastructure concern (`hex-capability-adapter`).
28. **An unbounded read.** An upload is bounded before it is read: by the app's request-size middleware
    where one is declared, else the route reads with a bound; the route never computes the limit.
29. **A streaming response without its media type.** Clients render by it; a known format never falls
    back to a generic binary type.
30. **Any exception handling beyond the one sanctioned translation** of a JSON part's validation error
    in a mixed multipart + JSON route. Do not extend it.
31. **Serving a path on disk.** All file content originates from the handler's bytes.
32. **A response model on a streaming route.** It is meaningless and misdescribes the response in the
    published document.
33. **A response header a cross-origin page must read, left unexposed.** Where the app declares CORS,
    the route that sets such a header adds it to the CORS middleware's exposed headers
    (`hex-restapi-app`) in the same change.

## Inlined typing / import rules

- `Form`, `UploadFile` from `fastapi`; `Response`, `StreamingResponse` from `fastapi.responses`.
- `from pydantic import ValidationError as PydanticValidationError` — aliased so it does not shadow the
  catalogue's `ValidationError`, imported from `myapp.domain.exceptions` where the route raises it.

## Hard stops

- The route is asked to parse the file content → stop, that is the handler's job (`hex-application`);
  the route passes bytes.
