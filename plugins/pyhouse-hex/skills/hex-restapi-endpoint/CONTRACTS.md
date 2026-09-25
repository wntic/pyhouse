# hex-restapi-endpoint — what a route advertises

Topic file of `hex-restapi-endpoint`. The mechanism-free obligations are rules 8–13 in `SKILL.md`; what
follows is the **FastAPI decorators, OpenAPI document** binding that satisfies them.

One declaration a route makes about itself: **which HTTP error codes it can produce**, published into
OpenAPI so the document tells the truth. A code advertised that nothing raises is a lie a client will
plan around; a code produced that nothing advertises is a surprise. The app-wide invariant that compares
the decorator against the OpenAPI spec fails on exactly that mismatch.

Auth codes are the one part of a route's set that follows from something other than the operation — they
follow from the attached auth dependency, which is `hex-restapi-auth`'s. Everything below is the
auth-less baseline, complete on its own.

## The two symbols

The error catalogue and boundary translation follow `exception-catalog`; `hex-restapi-app` creates
`register_error_handlers` in `restapi/error_handler.py`. Routes only **advertise** which codes they can
raise, so OpenAPI documents the contract.

Domain exception classes register themselves: `error_responses(...)` derives its allowed-code list from
`domain.exceptions.__all__` at import time. Adding a subclass (`exception-catalog`) is enough — there is
no registry to append to.

Two symbols come from `errors.py` — created once by `hex-restapi-app`, which is their single source of
truth — and only one of them is ever written here:

- **`error_responses(*codes: int) -> dict[int | str, dict[str, Any]]`** — the helper that goes on a route
  decorator. It validates each code against the known set —
  `{cls.http_status for cls in domain.exceptions.__all__} ∪ set(MIDDLEWARE_ERRORS.values())` — and raises
  `ValueError` on an unknown one, so OpenAPI can never advertise a status nothing produces.
- **`MIDDLEWARE_ERRORS: dict[str, int]`** — the **only** manually-maintained registry in `errors.py`, and
  the sole write target on this path. `hex-restapi-app` creates it carrying `INTERNAL_ERROR`; a row is
  added when a middleware introduces a status with no `DomainError` behind it, such as a size cap →
  `{"PAYLOAD_TOO_LARGE": 413}`.

## Standard code sets per operation

The sets below are for a route with **no auth dependency** — every route in an app that declares no auth,
and the public routes of an app that does. `401` and `403` are auth codes, not universal: they join the
set only when a route attaches an auth dependency, and `hex-restapi-auth` owns that join. The `422`
never drops: it is an input-validation code, not an auth code (rule 13). This is load-bearing rather
than cosmetic: `error_responses(...)` validates against the known set, and an auth-less app has no
`UnauthorizedError` class, so a stray `401` raises `ValueError`.

| Operation | `error_responses(...)` |
|---|---|
| Read, parameterless | nothing (plus `404` if it can not-find) |
| Read by id (`{id}` path param) | `404, 422` |
| List / browse (filter or pagination params) | `422` |
| Create (body) | `409, 422` (plus `404` if the body references another aggregate by id) |
| Update (`{id}` plus body) | `404, 409, 422` |
| Delete (`{id}` path param) | `404, 409, 422` — `409` covers in-use |
| Static collection action (a literal path segment) | `422` |
| Lookup / detect (a read with input) | `404, 422` |
| Multipart upload | add `413` to whichever set applies |

**Advertise `422` on every route carrying ANY validated input** — a path param, query, filter or
pagination params, or a body. Any of them can be rejected before the handler runs, and the shell renders
that rejection as an `ErrorResponse` carrying the catalogue's validation code (`hex-restapi-app`).
FastAPI publishes a `422` of its own for every such operation, but it describes the framework's default
`HTTPValidationError` body, which the shell never sends; the decorator's `error_responses(..., 422)`
entry replaces it, so the published document names the body the client actually receives. Do not expect
a test to catch a miss — the `test_openapi_advertises_error_codes` invariant (`hex-test-app-invariants`)
exempts exactly this code, because the framework inserts an entry for it where the decorator cannot see
it. The rule stands on the document telling the truth, not on a red run. That is why Read-by-id and Delete carry `422` despite having no body:
the `{id}` path param alone produces it. Only a parameterless, body-less route — a `GET /me` or a health
probe — omits it. The trap is reading `422` as "body validation"; it is *any-input* validation.

**List a code only if the route can actually produce it.** No `409` on a read, no `413` on a route with no
size cap in front of it, and no auth code on a route with no auth dependency. The converse holds too: a
code the write path can raise is listed. Where the repository translates a reference to a missing
aggregate into the catalogue's not-found class (`hex-persistence`), a create or update whose body names
that aggregate by id can answer `404`, and advertises it.

## Procedure — routine route

1. Choose the code set from the table.
2. Add `responses=error_responses(<codes>)` to the route decorator.

The catalog is dynamic; nothing further is registered.

## Procedure — a middleware-introduced code

1. Confirm the status genuinely has no `DomainError` behind it — the body comes from middleware, before
   the exception handler runs. Otherwise the answer is `exception-catalog`, not this path.
2. Append `("CODE_STRING", <http_status>)` to `MIDDLEWARE_ERRORS` in `restapi/schemas/errors.py` — the
   only hand-edit to that `hex-restapi-app`-owned file.
3. Nothing to do for the description: `hex-restapi-app`'s helper looks the standard phrase up from
   `http.HTTPStatus`. Only if this app must word that status differently does it get a
   `DESCRIPTION_OVERRIDES` entry in the same file.
4. Have the middleware emit an `ErrorResponse`-shaped body with the same `code` string.

## Other bindings

- **Another framework that builds its API document from route declarations** — Litestar, Flask with
  apispec, or a hand-maintained OpenAPI file. Changed: where the declaration is attached, and whether
  the framework injects an input-validation response the decorator cannot see. Unchanged:
  advertise-exactly-what-you-produce, the allowed-code set derived from the exception catalogue, and the
  one hand-maintained registry for middleware-introduced statuses.
- **A framework that injects nothing of its own.** Then rule 13 is the only thing putting the
  input-validation status in the document, and the exemption noted above disappears with it — the
  invariant test can check that code like any other.

## Hard stops

- A route lists a status no `DomainError` subclass produces and that is not in `MIDDLEWARE_ERRORS` → stop,
  define the exception first or take the middleware path.
- Asked to add branching logic to `restapi/error_handler.py` → stop, the translator stays minimal;
  new behaviour is encoded by subclassing, or by `http_status` / `code` on the new class.
