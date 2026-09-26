# hex-restapi-endpoint — file-transfer routes

Topic file of `hex-restapi-endpoint`. The mechanism-free obligations are rules 19 and 24–32 in
`SKILL.md`; what follows is the **FastAPI** binding that satisfies them.

## `upload` — multipart upload

### Pure file upload — one file

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

### Multiple optional uploads

```python
attachments: list[UploadFile] | None = (None,)
...
attachment_inputs: list[CreateFooAttachment] = []
for f in attachments or []:
    raw = await f.read()
    attachment_inputs.append(CreateFooAttachment(data=raw, mime=f.content_type or ""))
```

- The parameter type `list[UploadFile] | None = None` handles "no files attached" cleanly.
- Build a list of application input dataclasses inside the route; capture both `data` and `f.content_type or ""`. The empty-string fallback is deliberate — domain validates the mime and an empty value triggers a clear `ValidationError` rather than `None` slipping through.

### Mixed multipart + JSON — the only sanctioned `try/except` in a route body

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
    responses=error_responses(401, 403, 404, 409, 413, 422),
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
        fields = [".".join(str(part) for part in error["loc"]) for error in exc.errors()]
        raise ValidationError("invalid payload", {"fields": fields}) from exc
    ...
```

Rules:

- `data: Annotated[str, Form()]` receives the JSON blob as a string. Pydantic does not automatically validate it because the parameter type is `str` — validation is explicit.
- `<Schema>.model_validate_json(data)` parses and validates.
- **The `try/except PydanticValidationError → raise ValidationError(...) from exc` is the single sanctioned `try/except` in a route body** in this codebase. The context names the rejected fields by location and never echoes the input: the library's own message carries each rejected value, which may be a secret, so it is not passed on. It exists because Pydantic's exception raised inside a route is neither a `DomainError` nor the framework's request-validation error, so uncaught it reaches the catch-all handler and answers `500 INTERNAL_ERROR` for what is the client's malformed input. **Use this pattern verbatim — no other forms of error catching belong in a route.**
- Exception chaining follows `exception-catalog`.

This pattern is reserved for the multipart+JSON case. **Do not generalize it.** A JSON-only route uses `body: <Schema>` and lets FastAPI's normal validation flow through the central handler.

## `download` — streaming binary response

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

### `_export_filename` helper

```python
def _export_filename(ext: str) -> str:
    ts = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return f"myapp-foos-{ts}.{ext}"
```

- **Name it `_<purpose>_filename`** — module-level, underscore-prefixed because it is private to the
  router module and must not be re-exported. Identifier choice otherwise follows `naming`; the
  private-export rule follows `python-packaging`.
- The filename format — timestamp style, prefix, ASCII vs RFC 5987 — is an app-level choice; keep it consistent within one app.
- Filename construction lives in the route, not the handler. The handler returns content; the route names the artifact.

### CORS `expose_headers`

`Content-Disposition` is not a default CORS-exposed header, so a browser strips it from the response visible to JS. **If the app has CORS configured** (`hex-restapi-app`), a download route must ensure its response header is in the CORS middleware's `expose_headers` list — the bootstrap leaves that list **empty** by default, so a download route adds `"Content-Disposition"` (and any other non-default header it sets, e.g. `X-Total-Count`) there:

```python
expose_headers = (["Content-Disposition"],)
```

An app with no CORS configured has no such list to extend. **Verify `expose_headers` whenever you add a headered download response** (when CORS is enabled).
