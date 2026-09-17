---
name: hex-test-restapi-auth
description: Use when testing a token verifier, or any other part of a REST service that authenticates its callers — the token-verifier adapter's unit test, the signing-key and token-minting fixtures, the `authed_client` factory, the DI override that makes minted tokens verify, the discovered unauthenticated-route probe, and the role and cross-tenant assertions on an endpoint. Not an endpoint's non-auth half — happy path and schema validation (`hex-test-restapi-endpoint`) — and not another capability adapter's test (`hex-test-capability-adapter`).
when_to_use: Adding the auth fixtures to an integration suite, writing a 401 or 403 endpoint test, minting a JWT inside a test, or asserting that a protected route rejects an anonymous caller.
---

# Hex Test — REST API Auth

Consult `test-principles` for the testing constitution. Where this skill contradicts `test-principles`,
the constitution wins.

Every test the auth machinery needs — the verifier's own unit test and the auth half of the integration
suite — and all of it exists **only for an app that declares auth**
(`hex-restapi-auth`). An auth-less app produces none of these files: no verifier to test, no
`tests/helpers/jwt.py`, no `tests/integration/api/conftest.py`, no `test_unauth_returns_401.py`, and
every endpoint test drives a plain ASGI client. Whether an app has auth follows from its routes, not
from a flag.

## When to use vs. neighbours

- Any other capability adapter's test — containerized, HTTP-gateway with `respx`, or another pure-CPU one → `hex-test-capability-adapter`, which owns the three flavors; the verifier test in `UNIT.md` is its pure-CPU flavor bound to auth.
- The containers, the engine, the rollback `sf` and `real_app` itself → `hex-test-integration-setup`
  (one-shot; `real_app` is defined there and every file here consumes it).
- A per-endpoint test's non-auth half — happy path, schema validation, per-resource fixtures →
  `hex-test-restapi-endpoint`.
- The other discovered invariants — OpenAPI error codes, CORS, request-size limit, the construct smoke →
  `hex-test-discovery-invariants`.
- The route-side dependencies, the verifier and the code sets under test → `hex-restapi-auth`.
- A handler-level authorization rule, tested without HTTP → `hex-test-application-handler`.
- The `Role` enum's own unit test → `hex-test-domain`.
- The testing constitution these rules defer to — fixture placement, the mocking prohibition, speed targets → `test-principles`.

## Template(s) — PyJWT, httpx over ASGI, pytest

```
tests/
├── helpers/
│   └── jwt.py                                   # sign_token(...)
├── unit/
│   └── infrastructure/jwt/
│       └── test_pyjwt_token_verifier.py         # the verifier adapter, no IO, no fixtures
└── integration/
    └── api/
        ├── conftest.py                          # rsa_keypair, jwt_settings, authed_client
        ├── test_unauth_returns_401.py           # the discovered probe
        └── <resource>/
            └── test_<verb>_<noun>.py            # the authenticated endpoint forms
```

Two topic files carry the worked binding — **PyJWT, `cryptography`, httpx over ASGI, FastAPI and
pytest** — on either side of the unit/integration seam:

- **`UNIT.md`** — the verifier adapter's own test: module-scope keypair, real signatures, one case per
  translation arm.
- **`INTEGRATION.md`** — the signer helper, the api conftest and its authenticated client, the DI
  substitution that makes a minted token verify against the real app, the discovered unauthenticated
  probe, and the authenticated endpoint forms.

## Other bindings

- **Opaque token plus an introspection endpoint** (`hex-restapi-auth`'s first alternative). Rules 1–24
  hold unchanged. What changes: there is no keypair and no signer, so the session-scoped fixture becomes
  a stub introspection server and the "mint a fresh token per call" rule becomes "register a fresh
  token with the stub per call". Rule 12's no-mocking line moves down a level — the verifier still runs
  for real; the *upstream* is the seam the test controls.
- **Gateway- or mTLS-authenticated** (no verifier in the app). The verifier unit test and `UNIT.md`
  disappear entirely; the authenticated client sets the trusted header instead of a bearer credential,
  and the probe asserts that a request arriving *without* it is rejected — which is the test that the
  app is unreachable except through the gateway.
- **`dependency-injector` as the wiring mechanism.** Only the substitution in the api conftest changes,
  the way `hex-test-integration-setup`'s bullet describes; the fixtures, the probe and every assertion
  are untouched.

## Rules

Consult `test-principles` for the testing constitution, and `hex-test-capability-adapter` for the three
capability-adapter test flavors — the verifier takes its pure-CPU one.

### The verifier's unit test

1. **Real keys, real signatures, no mocking of the library.** Generate a keypair at module scope and
   sign with the real library. A hand-written token string the library never produced proves nothing
   about the library's behaviour, which is the whole subject.
2. **One test per `raise` site in the verifier** — every arm of the library's failure family the adapter
   catches, plus any guard it raises itself — and each asserts the `context` key that arm sets. Skipping
   arms is how "the translator handles expiry but not audience" ships, and the count is checkable: a
   verifier with five raise sites has five cases.
3. **One signer for the whole suite.** The unit test and the integration fixtures mint tokens through
   the same helper, so a change to the claim shape cannot leave them disagreeing.
4. **Module-level settings and keys, never fixtures.** A pure-CPU adapter has no lifecycle; it is
   constructed inline in each test.

### The authenticated client

5. **One sanctioned authenticated client, and every test goes through it.** Building a client against
   the real app and attaching a credential header by hand is forbidden in any test file — a hand-rolled
   header is how the claim shape drifts between tests. A client with no credential is allowed in exactly
   two places: the unauthenticated probe, and an app with no auth at all
   (`hex-test-restapi-endpoint`'s public template).
6. **The client factory is entered as a context manager, never assigned.** Bare assignment leaks the
   transport and surfaces later as a consumed-client error or resource-warning noise in a run that has
   nothing to do with the test that leaked it. The scoped form is non-negotiable.
7. **Each call mints a fresh token.** Tokens are not reused across tests, calls, or roles. A test that
   needs two roles in one body calls `authed_client(...)` twice.
8. **Mint only what the identity type declares; pass everything else via `extra_claims`.** The factory
   bakes in the subject and the rank and nothing more — the two fields the domain identity carries in
   every app (`hex-restapi-auth`). Anything further this app's identity carries (a tenant id, a display
   name, …) is the caller's to pass via `extra_claims`, pinned only when a test must share it with a
   fixture row (don't reuse such a value across unrelated tests). Never hardcode one app's identity
   model into the factory, and never name a claim key outside the binding files.
9. **The keypair and the verifier settings are session-scoped.** Generating an RSA key is expensive
   (~100 ms); generating per test would dominate suite wall time. The client factory stays
   function-scoped — each test's transport must be closed at teardown.
10. **The credential the fixture mints is produced the way production's is verified**, off the same
    settings object the fixture built — same algorithm, same issuer, same audience. Substituting a
    cheaper algorithm "for speed" tests a path production does not run, and it is the substitution that
    hides an algorithm-confusion bug rather than catching it.
11. **The client's base URL is a sentinel host, not a loopback address.** The in-process transport never
    reaches the network either way, but a loopback URL makes test traffic indistinguishable from real
    traffic in a CI log — and indistinguishable from a test that accidentally does reach the network.
12. **No mocking of verification.** The verifier in `real_app` validates the token end-to-end against the
    public key these fixtures provided — that *is* the integration contract under test.
13. **No global token cache.** Per-test mint is fast (~1 ms) and avoids "this test passed because the
    previous test's token was still cached" failures.
14. **Helpers live in `tests/helpers/`, not in `conftest.py`.** A test that needs `sign_token(...)` for
    an edge case (expired token, invalid issuer) imports the helper directly. The helper is a plain
    function — no fixtures wrap it.

### The discovered probe

15. **Protected-route detection is structural, not by name.** Enumerate the operations the framework
    itself resolved — not a filter over the app's raw route list, which on a framework that defers
    router inclusion finds zero operations, measured — and identify the auth dependency by **callable
    identity**, importing it, rather than by matching its function name as a string. A renamed
    dependency then breaks the import, which is loud; a name match would silently stop finding it.
16. **The probe substitutes path placeholders with valid-shaped dummies, by pattern and never by a
    name list.** A test for `GET /foos/{id}` with literal `{id}` in the URL hits the router as 404
    instead of triggering auth. UUID-shaped placeholders (`00000000-...`) route correctly and the
    request reaches the auth dependency. Substitute **every** `{...}` segment with one regex: an
    enumerated tuple of parameter names silently stops covering the route that introduces a new one,
    and the probe then passes by not reaching the dependency at all — the exact failure this test
    exists to catch.
17. **The probe discovers its inputs from the app**, never from a hand-written `_endpoints()` /
    `_EXPECTED` / `RESOURCES` table. The cost of adding a new endpoint must be zero here.
18. **An empty discovery is a failure, not a skip.** The companion net test asserts the walk found
    operations *and* found protected ones, because an empty parametrization reports "got empty parameter
    set" and leaves the run green — silence indistinguishable from an app with no protected routes.
19. **Assert the code constant and the challenge scheme, never their literals.** The rejection body is
    asserted against the domain exception's own code attribute, so renaming the code moves both sides
    together; the challenge is asserted on its scheme only. The realm is app-specific and is never
    frozen in an assertion.
20. **This whole file is auth-gated**, the way an info-endpoint test is endpoint-gated. Its module-level
    imports of the route dependency and the domain exception exist only in an app that declares auth; in
    an all-anonymous app the file would fail to import at collection time and take the whole
    `tests/integration/api/` package down with it.

### Endpoint-level assertions

21. **A role-gated route is tested from below the bar as well as above it.** A happy path at the
    required rank, and a rejection at a lower one; a route whose gate is never exercised from below is
    a gate nothing proves.
22. **Cross-tenant reads return 404, not 403.** When a resource is tenant-scoped — the endpoint reads
    rows owned by a tenant other than the caller's — answering 403 leaks existence ("this resource
    exists but you can't see it"), so the route must return 404. Tenancy is derived from the auth claim
    plus the repository's owner filter, not from a declared field; test the 404 path explicitly whenever
    the resource is tenant-scoped.
23. **Error responses are asserted by `code`, not by message** (`hex-test-restapi-endpoint`). The HTTP
    status is asserted separately.
24. **A role ladder in a test is the app's own.** `INTEGRATION.md` uses the catalogue's placeholder
    pair `Role.LOWER` / `Role.HIGHER` (`hex-restapi-auth`); substitute the app's own members, and
    however many of them it has.

## Inlined typing / import rules

- The verifier unit test adds `cryptography.hazmat.*`, `myapp.domain.auth`, `myapp.domain.exceptions`
  and `myapp.infrastructure.jwt.*`; no `myapp.application.*` and no `myapp.restapi.*` — it drives the
  adapter directly.
- The api conftest adds `httpx`, `jwt` (PyJWT), `cryptography.hazmat.*`, `myapp.domain.auth` and
  `myapp.infrastructure.jwt.settings`; full annotations on the factory and its `_factory` closure.
- The probe adds `pytest`, `fastapi`, `fastapi.routing`, `httpx`, `myapp.restapi.main`,
  `myapp.restapi.dependencies`, and `myapp.domain.exceptions` for the `UnauthorizedError.code`
  constant it asserts against. It never imports `myapp.containers`: `create_app()` builds the real
  composition root itself, and no factory runs at collection time.
- Full annotations on every fixture, helper and test — `-> None` on every test. `python-style` owns
  annotation policy and admits no test carve-out.
- No `from __future__ import annotations`.

## Hard stops

- Spec asks to mock the token library, or to feed the verifier a hand-written token string → stop, sign
  a real token with a real key; the library's behaviour is the subject of the test.
- Spec tests only the verifier's happy path → stop, cover every `raise` site with its `context` key
  (Rule 2); a translator arm nothing exercises is the gap this test exists to close.
- Spec puts the verifier's unit test under `tests/integration/` or gives it a fixture → stop, it is
  pure-CPU: `tests/unit/infrastructure/<adapter>/`, module-level helpers, no container
  (`hex-test-capability-adapter`).
- Spec adds a second token signer beside `sign_token` → stop, one signer for the whole suite, or the
  unit and integration paths drift apart.
- The app has no auth (every endpoint anonymous) → stop, produce none of these files, and strip the
  `jwt_settings` parameter from `real_app` and its field and factory from `TestInfraProvider`. An
  auth-less app binds no `JwtSettings`, so a factory claiming to override one fails when the graph is
  assembled.
- Nothing up-tree builds the app on the test's own infrastructure bindings (`real_app` under this
  catalogue's binding) → stop, use `hex-test-integration-setup`; the suite cannot collect without it.
- Spec proposes a session-scoped `authed_client` "to speed up tests" → stop, the factory is
  function-scoped because each test's transport must be closed at teardown; the cost is negligible.
- Spec asks to mock the verifier → stop, the integration test signs a real token against the same
  keypair the verifier validates.
- Spec uses `HS256` in tests while production uses `RS256` (or vice versa) → stop, the algorithm matches
  production.
- Spec writes the bearer header by hand inside a test → stop, use `authed_client(...)` so role, tenant
  and claim shape are uniform.
- Spec hardcodes `Authorization: Bearer <literal-jwt>` for "expired token" or "invalid claim" tests →
  stop, mint the test-specific token via `sign_token(...)` from the helper.
- Spec uses `AsyncClient(transport=ASGITransport(...))` directly for an authenticated request → stop,
  drive it through `authed_client(...)`.
- Spec substitutes path placeholders from a fixed list of parameter names rather than by pattern → stop,
  a route with a name the list does not carry is silently skipped.
- Spec writes the probe against a hardcoded URL with literal placeholders (`/foos/{id}`) → stop,
  substitute UUID-shaped dummies so the route resolves before the auth dependency runs.
- Spec uses string matching to identify "protected" routes (`if "auth" in route.name`) → stop, walk the
  route contexts and compare `context.dependant.dependencies` callables by identity.
- Spec asks to fold a new per-endpoint unauthenticated test into the probe (e.g. "test that POST /foos
  returns 401 unauth") → stop, the parametrized probe already covers it via discovery; add the endpoint
  and it joins the suite automatically.
- Spec freezes the `WWW-Authenticate` challenge to a specific realm (`Bearer realm="myapp"`) → stop, only
  the scheme is load-bearing; the realm is app-specific.
- Spec pins the rejection body code to a literal string (`"UNAUTHORIZED"`) → stop, assert against the
  domain exception's `.code` constant.
- Spec adds an `authed_client` fixture to the root `tests/conftest.py` → stop, it belongs in
  `tests/integration/api/conftest.py`; a root-level app fixture makes every unit test pay the
  infrastructure import chain (`hex-test-integration-setup`).
- Spec adds a per-resource row factory inside the api conftest → stop, those live in
  `tests/integration/api/<resource>/conftest.py`.
