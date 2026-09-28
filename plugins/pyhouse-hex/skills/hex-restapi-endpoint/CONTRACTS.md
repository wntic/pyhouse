# hex-restapi-endpoint — what a route advertises

Topic file of `hex-restapi-endpoint`. The mechanism-free obligations are rules 8–11 in `SKILL.md`; what
follows is the **FastAPI decorators, OpenAPI document** binding that satisfies them.

One declaration a route makes about itself: **which HTTP error codes it can produce**, published into
OpenAPI so the document tells the truth. A code advertised that nothing raises is a lie a client will
plan around; a code produced that nothing advertises is a surprise.

An auth code follows the auth dependency (`hex-restapi-auth` rule 7); everything below is the auth-less
baseline, complete on its own.

## The helper

A route decorates with `error_responses(*codes)` from `restapi/schemas/errors.py` and never writes to
that file; the helper, its status map and middleware registry, and registering a middleware's status are
`hex-restapi-app`'s.

## Standard code sets per operation

A route puts its row's set into `responses=error_responses(...)`. The sets are for a route with **no
auth dependency**; `hex-restapi-auth`'s `ROUTES.md` adds the auth codes.

| Operation | `error_responses(...)` |
|---|---|
| Read, parameterless | nothing (plus `404` if it can not-find) |
| Read by id (`{id}` path param) | `404, 422` |
| List / browse (filter or pagination params) | `422` |
| Create (body) | `422`, plus `409` per uniqueness constraint the aggregate carries |
| Update (`{id}` plus body) | `404, 422`, plus `409` likewise |
| Delete (`{id}` path param) | `404, 422`, plus `409` where another aggregate can reference it (in use) |
| Collection action (a literal path segment) | `422`, plus whatever its handler raises |
| Read with other input (a lookup by a natural key, a search) | `404, 422` |

Where `Foo` references another aggregate by id, create advertises `404` for an id that does not exist
(update already carries it).

FastAPI publishes its own `422`, describing an `HTTPValidationError` body the shell never sends
(`hex-restapi-app`). The decorator's entry replaces it (rule 11), and `hex-test-app-invariants` rule 4
fails a published `422` in any other shape.

**List a code only if the route can actually produce it.** No `409` on a read or on a write the store
cannot reject, and no `413` on a route with no size cap in front of it. The converse holds too: a code
the write path can raise is listed.

## Other bindings

- **Another framework that builds its API document from route declarations** — Litestar, Flask with
  apispec, or a hand-maintained OpenAPI file. Changed: where the declaration is attached, and whether
  the framework injects an input-validation response the decorator cannot see. Unchanged:
  advertise-exactly-what-you-produce, and the allowed-code set taken from the boundary's status map and
  its registry of middleware-introduced statuses.
- **A framework that injects nothing of its own.** Then rule 11 is the only thing putting the
  input-validation status in the document, and the exemption `hex-test-app-invariants` rule 4 makes
  disappears with it — the invariant test can check that code like any other.

## Hard stops

- A route lists a status neither `STATUS_BY_ERROR` nor `MIDDLEWARE_ERRORS` holds → stop; if nothing on
  the route's path can raise it, drop the code (rule 9); a status something does raise earns a class
  first (`exception-catalog`) and its entry in the map, or a registered middleware status
  (`hex-restapi-app`).
- Asked to add branching logic to `restapi/error_handler.py` → stop, use `hex-restapi-app` (rule 3).
