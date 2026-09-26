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
truth — and a route only reads them:

- **`error_responses(*codes: int) -> dict[int | str, dict[str, Any]]`** — the helper that goes on a route
  decorator. It validates each code against the known set —
  `{cls.http_status for cls in domain.exceptions.__all__} ∪ set(MIDDLEWARE_ERRORS.values())` — and raises
  `ValueError` on an unknown one, so OpenAPI can never advertise a status nothing produces.
- **`MIDDLEWARE_ERRORS: dict[str, int]`** — the **only** manually-maintained registry in `errors.py`.
  A middleware status is registered by `hex-restapi-app` before a route advertises it; a route never
  writes to it.

## Standard code sets per operation

The sets below are for a route with **no auth dependency**; `hex-restapi-auth`'s `ROUTES.md` adds the
auth codes. The `422` never drops: it is an input-validation code, not an auth code (rule 13).

| Operation | `error_responses(...)` |
|---|---|
| Read, parameterless | nothing (plus `404` if it can not-find) |
| Read by id (`{id}` path param) | `404, 422` |
| List / browse (filter or pagination params) | `422` |
| Create (body) | `422`, plus `409` per uniqueness constraint the aggregate carries |
| Update (`{id}` plus body) | `404, 422`, plus `409` likewise |
| Delete (`{id}` path param) | `404, 422`, plus `409` where another aggregate can reference it (in use) |
| Collection action (a literal path segment) | `422`, plus whatever its handler raises |
| Lookup / detect (a read with input) | `404, 422` |
| Multipart upload | whichever set applies; add `413` only where a size-cap middleware is declared |

Where `Foo` references another aggregate by id, create advertises `404` for an id that does not exist
(update already carries it).

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

**List a code only if the route can actually produce it.** No `409` on a read or on a write the store
cannot reject, no `413` on a route with no size cap in front of it, and no auth code on a route with no
auth dependency. The converse holds too: a code the write path can raise is listed.

## Procedure — routine route

1. Choose the code set from the table.
2. Add `responses=error_responses(<codes>)` to the route decorator.

The catalog is dynamic; nothing further is registered. A status a middleware introduces is registered
by `hex-restapi-app` (its `## Middleware`) before any route advertises it.

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

- A route lists a status no `MyappError` subclass produces and that is not in `MIDDLEWARE_ERRORS` → stop,
  define the exception first (`exception-catalog`) or register the middleware's status (`hex-restapi-app`).
- Asked to add branching logic to `restapi/error_handler.py` → stop, the translator stays minimal;
  new behaviour is encoded by subclassing, or by `http_status` / `code` on the new class.
