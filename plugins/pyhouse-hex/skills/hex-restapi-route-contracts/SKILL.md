---
name: hex-restapi-route-contracts
description: Use when choosing which HTTP error codes a route advertises — a modifier on the `responses=error_responses(...)` argument of a decorator `hex-restapi-endpoint` already wrote. Owns the per-operation code sets, advertise-only-what-you-produce, and the `MIDDLEWARE_ERRORS` registry. A `401` or `403` follows an auth dependency and is `hex-restapi-auth`'s.
paths: ["**/restapi/**", "**/api/**"]
---

# Hex REST — Route Contracts

One declaration a route makes about itself: **which HTTP error codes it can produce**, published into
OpenAPI so the document tells the truth. A code advertised that nothing raises is a lie a client will
plan around; a code produced that nothing advertises is a surprise. The discovery invariant that compares
the decorator against the OpenAPI spec fails on exactly that mismatch.

Auth codes are the one part of a route's set that follows from something other than the operation — they
follow from the attached auth dependency, which is `hex-restapi-auth`'s. Everything below is the
auth-less baseline, complete on its own.

## When to use vs. neighbours

- Choosing a route's code set, or adding `responses=error_responses(...)` to a decorator `hex-restapi-endpoint` already wrote →
  this skill.
- Writing the endpoint's signature and body, including multipart or streaming routes → `hex-restapi-endpoint`.
- Defining a new error class whose status becomes valid for `error_responses(...)` → `exception-catalog`.
- Creating `restapi/error_handler.py` or `restapi/schemas/errors.py` → `hex-restapi-app`.
- Attaching an auth dependency, and the `401` / `403` a route advertises because of it →
  `hex-restapi-auth`.
- The container this skill sits on → `hex-wiring`; the handlers, including authorization finer than a single role-rank check that raises `ForbiddenError` → `hex-application`.
- The `test_openapi_advertises_error_codes` cross-check that fails when the decorator and the published document disagree → `hex-test-discovery-invariants`.
- The request or response body model whose fields the successful code returns → `hex-restapi-schema`; this skill declares only the error codes.

## Template(s) — FastAPI decorators, OpenAPI document

### The advertised error codes

The error catalogue and boundary translation follow `exception-catalog`; `hex-restapi-app` creates
`register_error_handlers` in `restapi/error_handler.py`. Routes only **advertise** which codes they can
raise, so OpenAPI documents the contract.

Domain exception classes register themselves: `error_responses(...)` derives its allowed-code list from
`domain.exceptions.__all__` at import time. Adding a subclass (`exception-catalog`) is enough — there is
no registry to append to.

Two symbols come from `errors.py`, and only one of them is ever written here:

- **`error_responses(*codes: int) -> dict[int | str, dict[str, Any]]`** — the helper that goes on a route
  decorator. It validates each code against the known set —
  `{cls.http_status for cls in domain.exceptions.__all__} ∪ set(MIDDLEWARE_ERRORS.values())` — and raises
  `ValueError` on an unknown one, so OpenAPI can never advertise a status nothing produces.
- **`MIDDLEWARE_ERRORS: dict[str, int]`** — the **only** manually-maintained registry in `errors.py`, and
  this skill's sole write target. `hex-restapi-app` creates it carrying `INTERNAL_ERROR`; a row is added
  when a middleware introduces a status with no `DomainError` behind it, such as a size cap →
  `{"PAYLOAD_TOO_LARGE": 413}`.

#### Standard code sets per operation

The sets below are for a route with **no auth dependency** — every route in an app that declares no auth,
and the public routes of an app that does. `401` and `403` are auth codes, not universal: they join the
set only when a route attaches an auth dependency, and `hex-restapi-auth` owns that join. The `422`
never drops: it is an input-validation code, not an auth code (see the rule below). This is load-bearing
rather than cosmetic: `error_responses(...)` validates against the known set, and an auth-less app has no
`UnauthorizedError` class, so a stray `401` raises `ValueError`.

| Operation | `error_responses(...)` |
|---|---|
| Read, parameterless | nothing (plus `404` if it can not-find) |
| Read by id (`{id}` path param) | `404, 422` |
| List / browse (filter or pagination params) | `422` |
| Create (body) | `409, 422` |
| Update (`{id}` plus body) | `404, 409, 422` |
| Delete (`{id}` path param) | `404, 409, 422` — `409` covers in-use |
| Static collection action (a literal path segment) | `422` |
| Lookup / detect (a read with input) | `404, 422` |
| Multipart upload | add `413` to whichever set applies |

**Advertise `422` on every route carrying ANY validated input** — a path param, query, filter or
pagination params, or a body. FastAPI auto-injects a `422` request-validation response into the OpenAPI
for *every* such operation, so declaring it keeps the published document **honest**: a client reading the
schema sees the same failure set whether it comes from the decorator or from the framework, and nobody has
to know which half put it there. Do not expect a test to catch a miss — the
`test_openapi_advertises_error_codes` invariant (`hex-test-discovery-invariants`) exempts exactly this code,
because the framework inserts it where the decorator cannot see it. The rule stands on the document
telling the truth, not on a red run. That is why Read-by-id and Delete carry `422` despite having no body:
the `{id}` path param alone produces it. Only a parameterless, body-less route — a `GET /me` or a health
probe — omits it. The trap is reading `422` as "body validation"; it is *any-input* validation.

**List a code only if the route can actually produce it.** No `409` on a read, no `413` on a route with no
size cap in front of it, and no auth code on a route with no auth dependency.

#### Procedure — routine route

1. Choose the code set from the table.
2. Add `responses=error_responses(<codes>)` to the route decorator.

The catalog is dynamic; nothing further is registered.

#### Procedure — a middleware-introduced code

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
- **A framework that injects nothing of its own.** Then rule 7 is the only thing putting the
  input-validation status in the document, and the exemption noted in the template section disappears
  with it — the invariant test can check that code like any other.

## Rules

This skill produces no file. `error_responses` lives in `restapi/schemas/errors.py`, created once by
`hex-restapi-app`, which is its single source of truth.

1. **Routes only advertise.** Error catalogue and boundary translation → `exception-catalog`;
   logging → `python-style`. A route never builds an error response itself: one translator owns the
   error body's shape, and a hand-built body is the copy that drifts from it.
2. **Advertise exactly what the route can produce.** The set follows from the operation — which domain
   exceptions its handler can raise, which middleware sits in front of it, and whether it takes any
   validated input. A code that cannot occur is removed; a code that can occur and is missing makes the
   published document wrong in the direction clients notice last.
3. **Never hand-write the advertisement mapping** — `responses={404: {...}}` typed out at the decorator.
   Always go through the helper, because the helper is what checks the code against the set of codes
   something can actually produce; a hand-written entry is the one path by which a status nothing raises
   reaches the document.
4. **Error catalogue and boundary translation** → `exception-catalog`.
5. **`MIDDLEWARE_ERRORS` is the only manually-maintained registry.** Everything domain-side derives from
   `domain.exceptions.__all__`.
6. **A middleware-introduced status is registered before it is advertised.** The helper validates against
   the known set, so an unregistered status fails loudly at import rather than reaching the document.
7. **A route taking any validated input advertises the input-validation status.** Path parameter, query
   parameter, filter, pagination or body — any of them can be rejected before the handler runs, so the
   document must say so. It is *any-input* validation, not body validation: a lone `{id}` produces it,
   and only a parameterless, body-less route omits it. Where the framework publishes that response on
   its own, the decorator still names it, so the document reads the same whichever half put it there.

## Hard stops

- Spec lists a status no `DomainError` subclass produces and that is not in `MIDDLEWARE_ERRORS` → stop,
  define the exception first or take the middleware path.
- Spec asks a route to catch a domain exception and translate it → stop, use `exception-catalog`.
- Spec asks to add branching logic to `restapi/error_handler.py` → stop, the translator stays minimal;
  new behaviour is encoded by subclassing, or by `http_status` / `code` on the new class.
- Spec advertises `401` or `403` on a route that attaches no auth dependency → stop, those codes follow
  the dependency; see `hex-restapi-auth`, and in an auth-less app there is no class behind them at all.
- Spec proposes a third auth dependency type, or any other auth machinery → stop, use `hex-restapi-auth`;
  this skill owns advertisement only.
- Spec omits `422` on a route that takes a path param, query param, filter or body → stop, the framework
  publishes it either way and the document must say so.
