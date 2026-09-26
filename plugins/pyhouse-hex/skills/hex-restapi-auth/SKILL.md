---
name: hex-restapi-auth
description: Use when an HTTP entrypoint must authenticate its caller or gate a route on a role. Owns the caller identity, the token-verifier port and adapter, the `get_current_user` / `require_role` route dependencies, the role-rank gate, the RFC-7235 challenge, and the 401/403 codes a route advertises because of them — a route's other error codes are `hex-restapi-endpoint`'s.
when_to_use: Adding auth to a REST service, choosing between an authenticated and a role-gated route, wiring a token verifier, or deciding what an authenticated route advertises in OpenAPI.
paths: ["**/restapi/**", "**/api/**"]
---

# Hex REST — Auth

Authentication and transport-level authorization for a hexagonal REST service. Everything here is
**optional**: a service behind an authenticating gateway, an mTLS-fronted API, or an internal
worker-facing API declares no auth and never loads this skill. The REST core (`hex-restapi-app`,
`hex-restapi-endpoint`, `hex-restapi-schema`) is complete without it.

**Auth is conditional, not presumed.** An app has auth when some endpoint is non-anonymous, or a
token-verifier capability is wired — there is no separate flag for it. "Adding auth" means adding the
artifacts below; an app whose every endpoint is anonymous has **no auth layer at all**, which is the
absence of the feature rather than "skipping auth".

The principle this binds: **the entrypoint authenticates the caller, resolves a caller identity, and
passes it inward as ordinary data on a command or query DTO.** No layer below the entrypoint knows how
authentication happened. Authorization that is a *business* rule is a domain concern; authorization that
is a *transport* rule — a single role-rank check — belongs here.

## When to use vs. neighbours

- The app shell, middleware, the central error translator and `schemas/errors.py` → `hex-restapi-app`.
- A route's signature and body, including multipart and streaming routes → `hex-restapi-endpoint`.
- Which error codes a route advertises for non-auth reasons, and the registry for a status a middleware
  introduces → `hex-restapi-endpoint`, in its sibling `CONTRACTS.md`.
- `UnauthorizedError` / `ForbiddenError` themselves, and boundary translation → `exception-catalog`.
- The `Role` enum's rank-ordered `StrEnum` form, and `CurrentUser` as a value object →
  `hex-domain-model`.
- How to write the capability protocol the verifier satisfies → `hex-domain-ports`.
- Adapter form in general — constructor injection, secrets, no logging, no business logic →
  `hex-capability-adapter`; this skill carries only the verifier instance of it.
- Settings classes, binding lifetimes and composition-root declaration order → `hex-wiring`.
- Authorization finer than a single role-rank check → `hex-application`; the handler raises
  `ForbiddenError`.
- The fixtures that mint tokens, the `authed_client`, and the unauthenticated-probe invariant →
  `hex-test-restapi-auth`.
- A login or token-refresh request/response model, or any other per-resource wire schema → `hex-restapi-schema`; this skill owns the dependencies, not the bodies.

## The caller identity

`CurrentUser` is what the entrypoint resolves and what every auth-derived DTO field is stamped from.
It is a domain value object under a cross-cutting subdomain package (`domain/auth/`, per
`hex-domain-ports`' placement rule for cross-cutting capabilities).

### `domain/auth/current_user.py`

```python
from dataclasses import dataclass
from uuid import UUID

from .role import Role

__all__ = ["CurrentUser"]

@dataclass(frozen=True, slots=True)
class CurrentUser:
    id: UUID
    role: Role
```

A multi-tenant app adds the tenant as a further field (`tenant_id: UUID`), and the route stamps it onto
the DTO exactly like `caller_id`. Value-object form follows `hex-domain-model`.

### `domain/auth/role.py`

```python
from enum import StrEnum

__all__ = ["Role"]

_RANK = {"LOWER": 0, "HIGHER": 1}

class Role(StrEnum):
    LOWER = "LOWER"
    HIGHER = "HIGHER"

    def satisfies(self, required: "Role") -> bool:
        return _RANK[self.value] >= _RANK[required.value]
```

The self-reference is quoted — `required: "Role"` — because the name is not bound until the class
statement finishes and the catalogue bans `from __future__ import annotations` (`python-style`).

`LOWER` and `HIGHER` are **placeholder ranks**, the way `Foo` is the placeholder aggregate: substitute
the app's own members, and however many of them it has. The rank-ordered `StrEnum` with `satisfies` is
the shape. Enum form and the `_RANK` module constant follow `hex-domain-model`.

A route template names the slot rather than a member — `Role.<MIN_RANK>` — and the concrete member comes
from the route's own requirement against the app's `Role`.

## The token-verifier port

### `domain/auth/i_can_verify_token.py`

```python
from typing import Protocol

from .current_user import CurrentUser

__all__ = ["ICanVerifyToken"]

class ICanVerifyToken(Protocol):
    def verify(self, token: str) -> CurrentUser: ...
```

Signature verification is pure CPU, so the method is **sync**, not async — the capability-shape rule in
`hex-domain-ports`. **The port names no claim.** Its contract is credential in, identity out; which
keys, headers or certificate fields a scheme yields, and how they map onto the identity's fields, is the
adapter's alone (rule 13).

## The verifier adapter

### Template — PyJWT, sync pure-CPU form

Placement (`infrastructure/jwt/`, the external tech), constructor injection, secret handling and the
no-logging rule are `hex-capability-adapter`'s; this is that skill's sync pure-CPU form bound to PyJWT.
Translation of the library's parse/verify errors follows `exception-catalog`.

```python
from uuid import UUID

import jwt

from myapp.domain.auth import CurrentUser, Role  # the protocol (ICanVerifyToken) is NOT imported
from myapp.domain.exceptions import UnauthorizedError

from .settings import JwtSettings

__all__ = ["PyJwtTokenVerifier"]

class PyJwtTokenVerifier:
    def __init__(self, settings: JwtSettings) -> None:
        self._public_key = settings.public_key.get_secret_value()
        self._algorithm = settings.algorithm
        self._issuer = settings.issuer
        self._audience = settings.audience

    def verify(self, token: str) -> CurrentUser:
        try:
            claims = jwt.decode(
                token,
                self._public_key,
                algorithms=[self._algorithm],
                issuer=self._issuer,
                audience=self._audience,
                options={"require": ["sub", "role"]},
            )
            return CurrentUser(id=UUID(claims["sub"]), role=Role(claims["role"]))
        except jwt.ExpiredSignatureError as exc:
            raise UnauthorizedError("token expired", {"reason": "expired"}) from exc
        except jwt.InvalidTokenError as exc:
            raise UnauthorizedError(
                "invalid token",
                {"reason": exc.__class__.__name__},
            ) from exc
        except (AttributeError, TypeError, ValueError) as exc:
            raise UnauthorizedError("invalid token claims", {"reason": "invalid_claims"}) from exc
```

`algorithms=[...]` is a **list of one**, read from settings — never the token's own `alg` header. A
verifier that trusts the header accepts `none` and accepts a symmetric algorithm signed with the public
key it published; the settings-side allowlist validator below is what keeps that list honest.

**The identity is built inside the translated scope.** A token can carry a valid signature and still
not describe a caller — a claim missing, a subject that is not an identifier, a role the app does not
declare. Each of those is an unverifiable credential and answers 401 like a bad signature, never a
500. Here `require` turns an absent claim into the library's own `InvalidTokenError`, and the last arm
catches what building the identity raises on a claim of the wrong shape — `ValueError` from a string
`UUID(...)` or `Role(...)` cannot parse, `AttributeError` or `TypeError` from `UUID(...)` handed a
non-string. PyJWT 2.10 and later reject a non-string `sub` themselves; the arm keeps the verifier
correct without depending on that.

### `infrastructure/jwt/settings.py`

```python
from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["JwtSettings"]

_ALLOWED_ALGORITHMS = frozenset({"RS256", "RS384", "RS512", "ES256", "EdDSA"})

class JwtSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MYAPP_JWT_",
        env_file=".env",
        extra="ignore",
    )

    algorithm: str = "RS256"
    public_key: SecretStr
    issuer: str
    audience: str

    @field_validator("algorithm")
    @classmethod
    def _reject_unlisted_algorithm(cls, value: str) -> str:
        if value not in _ALLOWED_ALGORITHMS:
            raise ValueError(
                f"JWT algorithm {value!r} is not in the allowlist {sorted(_ALLOWED_ALGORITHMS)}"
            )
        return value

    @field_validator("public_key")
    @classmethod
    def _unescape_pem(cls, value: SecretStr) -> SecretStr:
        return SecretStr(value.get_secret_value().replace("\\n", "\n"))
```

The allowlist is a **rejection validator** in `hex-wiring`'s sense: it refuses a value that would cause
silent misbehaviour rather than a loud failure. An `alg` of `none`, or `HS256` against a published
public key, verifies happily and forges every identity in the system; the failure surfaces as "auth
works" rather than as an error, so the only place to catch it is process startup. The PEM
unescape is the other sanctioned validator purpose — normalization, accepting the env-friendly
single-line form and storing the canonical one. Settings rules, secrets and `SecretStr` handling are
`hex-wiring`'s; this file is one instance of them.

### Binding traps — bearer JWS

**Verification trusts configuration, not the token.** The accepted algorithm set is declared in settings
and validated against an allowlist at startup; the token's own header never selects it. That obligation,
the `Authorization` header the dependency below reads and the RFC-7235 challenge the error branch
attaches are **this scheme's own** — an opaque token, a session cookie and a gateway header have none of
the three — so these stops sit with the template that names the stack, and they stop wherever this
binding is in use.

- The algorithm is taken from the token's `alg` header, or the allowlist is widened to include `none` or a
  symmetric algorithm against a published public key → stop, the accepted set is configuration and is
  validated at startup.
- A route is asked to read the `Authorization` header directly → stop, that is what the bearer scheme
  is for.
- Asked to decode the token anywhere but `get_current_user` → stop, no `jwt.decode` in a route, no
  manual header parsing.
- Asked for `WWW-Authenticate` on a 403 → stop, that header is 401-specific by RFC 7235.
- A literal realm (`Bearer realm="myapp"`) is frozen as the contract → stop, only the scheme is
  load-bearing; the realm is app-specific and comes from settings, or is omitted.

## The route dependencies

### `restapi/dependencies.py`

`dependencies.py` is FastAPI's home for shared route dependencies; in this catalogue its only current
content is the auth pair, so the file is emitted **only** for an app that declares auth. An auth-less app
has no `get_current_user`/`require_role`, no `CurrentUser`/`Role` import, and routes attach no auth
dependency — hence no `dependencies.py` at all (`hex-restapi-app`). A non-auth shared route dependency,
if one is ever introduced, lives in the same file independent of auth.

```python
from dishka.integrations.fastapi import FromDishka, inject
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from myapp.domain.auth import CurrentUser, ICanVerifyToken, Role
from myapp.domain.exceptions import ForbiddenError, UnauthorizedError

__all__ = ["get_current_user", "require_role"]

_bearer_scheme = HTTPBearer(auto_error=False)

@inject
async def get_current_user(
    verifier: FromDishka[ICanVerifyToken],
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> CurrentUser:
    if creds is None or creds.scheme.lower() != "bearer":
        raise UnauthorizedError("Missing bearer token", {"reason": "missing_credentials"})
    return verifier.verify(creds.credentials)

class _RoleDependency:
    """A role-gated route dependency. A callable CLASS, not a closure, so the gated role is a
    TYPED attribute (`required_role`) rather than a `# type: ignore`-stashed function attribute.
    FastAPI inspects `__call__` like any callable."""

    def __init__(self, required: Role) -> None:
        self.required_role = required

    def __call__(self, user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not user.role.satisfies(self.required_role):
            raise ForbiddenError(
                "Insufficient role",
                {"required": self.required_role.value, "actual": user.role.value},
            )
        return user

def require_role(required: Role) -> _RoleDependency:
    return _RoleDependency(required)
```

The bearer scheme is declared **once** at module level. `get_current_user` receives the verifier by
its port type — never instantiate verifiers in routes or dependencies. **The `@inject` decorator is
required here even though the routers carry `route_class=DishkaRoute`**: that route class injects route
functions, not the `Depends` functions behind them (`hex-restapi-endpoint`). The verifier arrives typed,
so nothing is cast. `require_role` returns a `_RoleDependency` instance — a callable class so the gated
role rides as a typed attribute (see `python-style`).

## The error-handler auth branch

`hex-restapi-app`'s primary `error_handler.py` is the auth-less one. An app that declares auth uses the
**authenticated** variant instead: the `UnauthorizedError` import is added and the translator grows its
one `isinstance` branch, attaching the RFC-7235 challenge. Nothing else in the file changes, and
`hex-restapi-app` rule 3 caps it at **at most one** branch.

```python
from myapp.domain.exceptions import DomainError, UnauthorizedError, ValidationError
```

```python
        headers: dict[str, str] = {}
        if isinstance(exc, UnauthorizedError):
            headers["WWW-Authenticate"] = "Bearer"
        return JSONResponse(
            status_code=exc.http_status,
            content=ErrorResponse(
                code=exc.code,
                message=str(exc),
                context=exc.context,
            ).model_dump(),
            headers=headers or None,
        )
```

The challenge carries the `Bearer` scheme alone, which is the load-bearing part (RFC 7235) and what
`hex-test-restapi-auth` asserts. A realm is optional and app-specific: an app that wants one reads it
from its settings — never a literal frozen into the template (rule 9).

`401` says *who are you* — the credential was missing, malformed, expired or unverifiable, so the client
may retry with a better one, and RFC 7235 obliges the response to say how. `403` says *I know who you
are and you may not* — retrying with the same credential is pointless, and there is no challenge to
issue. Those are two different answers, not two spellings of one; `exception-catalog` owns both classes.

## The route's auth dependency and codes

**Read `ROUTES.md` before writing or changing any route in an app that declares auth** — only this
file is loaded automatically. It is the half consulted every time a route is written: the decision
table for which dependency an operation takes, the `_`-vs-`user` binding rule and the stamp-from-the-identity rule,
the four things that derive an authenticated route from an auth-free one, and the coordinated
advertisement rule joining the chosen dependency to the codes the route declares.

## The composition-root wiring

The verifier and its settings are two bindings in the composition root — an add-on a project that
declares auth merges into `hex-wiring`'s base, each line into the provider class of the same name.
Placement follows `hex-wiring`'s declaration order: settings first, then long-lived infrastructure — a verifier is process-lifetime
(stateless, parses its key once).

```python
from dishka import Provider, Scope, provide

from myapp.domain.auth import ICanVerifyToken
from myapp.infrastructure.jwt import JwtSettings, PyJwtTokenVerifier


class SettingsProvider(Provider):
    scope = Scope.APP

    @provide
    def jwt_settings(self) -> JwtSettings:
        return JwtSettings()


class InfrastructureProvider(Provider):
    scope = Scope.APP

    jwt_verifier = provide(PyJwtTokenVerifier, provides=ICanVerifyToken)
```

`ICanVerifyToken` — the port, not the adapter class — is what `get_current_user` asks for and what
`hex-test-restapi-auth` substitutes, so the adapter can be swapped without touching either. Lifetimes,
ordering and the settings lifecycle follow `hex-wiring`.

## Other bindings

- **Opaque token + introspection endpoint.** The port, `CurrentUser`, `require_role`, the dependency
  pair and the whole advertisement half are unchanged. What changes: the adapter does IO, so the
  capability method becomes `async` (`hex-domain-ports`' async capability shape) and the provider is
  built on an HTTP client rather than a key; the adapter form is `hex-capability-adapter`'s async
  HTTP-gateway one. A network call per request also makes a cache a real question — which the adapter
  may not answer itself — `hex-capability-adapter`'s adapters-are-thin rule (no retries, no caching); it
  is a separate wrapper.
- **Session cookie.** `HTTPBearer` is replaced by reading a signed cookie, and the RFC-7235 branch goes
  away — a cookie scheme has no `WWW-Authenticate` challenge, so a 401 carries no header. Everything
  else — the port, the identity, the role gate, the two dependencies, the code sets — is unchanged.
- **Gateway- or mTLS-authenticated.** The gateway has already authenticated, so there is no verifier and
  no port; `get_current_user` builds `CurrentUser` from a trusted header or the peer certificate. The
  gate, the codes and the 401/403 split stand. The load-bearing extra rule: the app must be unreachable
  except through the gateway, or the trusted header is a forgery primitive.
- **`dependency-injector` as the wiring mechanism.** The port, the adapter, the dependency pair and the
  codes are unchanged. What changes is two lines of `dependencies.py`: `get_current_user` takes
  `request: Request` instead of the injected parameter, drops `@inject`, and reaches the verifier by the
  binding's **attribute name** off the app state — which resolves untyped, so the result has to be
  narrowed with a `cast` to keep the `-> CurrentUser` contract. `hex-wiring`'s mapping table has the
  rest.

## Rules

1. **The entrypoint authenticates; nothing below it knows how.** The caller identity crosses inward as
   ordinary data on a command or query DTO — never a request object, a header, a token string or a
   framework dependency. `hex-application` owns the DTO field.
2. **One name for credential rejection.** Every missing, malformed, expired or unverifiable credential
   raises the catalogue's single unauthorized class, and the challenge branch keys on that one class; a
   second parallel class for the same case silently skips the challenge (`exception-catalog`).
3. **Identity is resolved once, at one place.** A route never parses the authorization header, decodes a
   token, or constructs a verifier. The verifier reaches the dependency from the composition root, by
   its port type, like anything else.
4. **The gate is a declared dependency, not code in the route body.** No hand-rolled rank comparison
   after the identity is bound. A rule more nuanced than a single role rank is a handler concern; the
   handler raises the forbidden class.
5. **The required rank is visible at the call site.** `require_role(Role.X)` is called inline at each
   route; do not memoize it at module level (`_gate = require_role(Role.HIGHER)`) — the role is the most
   important detail in a route review.
6. **The auth dependency is the last parameter.** Path, body, injected handlers and query parameters come first;
   identity last.
7. **Two dependencies, and they are exhaustive**: authenticate-only, and authenticate-plus-rank. Do not
   combine the authenticate-only form with a role check — use the rank form.
8. **The advertised codes match the chosen dependency.** Authenticate-only advertises the
   unauthenticated code; rank-gated advertises the unauthenticated **and** the forbidden code; no
   dependency advertises neither. A code no route can produce is a lie in the published document
   (`hex-restapi-endpoint`).
9. **A challenge, where the scheme defines one, carries the scheme and nothing else.** The realm is
   app-specific: drive it from settings or omit it, and never freeze a literal realm in a template or a
   test. The challenge belongs to the unauthenticated response alone — a forbidden response has no
   challenge to issue, and a scheme that defines no challenge sends none at all.
10. **In an app that has auth, authentication is the default for a non-public route.** A "trusted
    internal" route that skips auth is forbidden; internal-only access is enforced at the network or
    gateway layer. This does **not** manufacture auth on an app that has none.
11. **A rank ladder is the app's own.** Ranks are declared as a rank-ordered enum with a
    rank-satisfaction method; the member names and their number belong to the app. A route template
    names the slot (`Role.<MIN_RANK>`), and the ladder shown anywhere in this catalogue is the
    placeholder pair `Role.LOWER` / `Role.HIGHER` — never a member carried over from some app.
12. **Auth-derived values come from the resolved identity, never from the request.** Actor, tenant and
    anything else the credential carries are stamped from the identity object; reading a tenant id from
    the path, query or body lets a client choose another tenant's scope.
13. **The identity type is a domain type.** The verifier returns it; the credential's own wire shape —
    a claims mapping, an introspection payload, a header set — never leaves the adapter, and no layer
    above it sees one.

## Inlined typing / import rules

- **No cast at the injection boundary.** The verifier arrives as `FromDishka[ICanVerifyToken]`, which
  is a real annotation the checker follows, so `get_current_user` honours its `-> CurrentUser` contract
  with no `cast` and no `# type: ignore`. A cast here means something is being reached through an
  untyped attribute — fix the injection instead.
- `Depends` from `fastapi`; `HTTPAuthorizationCredentials`, `HTTPBearer` from
  `fastapi.security`.
- Domain imports absolute (`from myapp.domain.auth import CurrentUser, Role`). The verifier adapter
  **never** imports the protocol it satisfies — structural subtyping at the DI site is the contract
  (`hex-capability-adapter`'s rule that an adapter neither inherits nor imports its protocol).
- Full annotations on every dependency, the callable class's `__call__`, and the verifier's methods. No
  `from __future__ import annotations` (`python-style`).

## Package wiring

`domain/auth/` is a subdomain package — its `__init__.py` re-exports `CurrentUser`, `Role` and
`ICanVerifyToken`, which every `from myapp.domain.auth import ...` above resolves against — and
`infrastructure/jwt/` an infrastructure one; both follow `python-packaging`, with the layer placement
in `hex-architecture`. `restapi/dependencies.py` sits in the entrypoint package `hex-restapi-app` creates, under that package's entrypoint carve-out.

## Hard stops

- The app declares no auth (every endpoint anonymous, no token-verifier capability) → stop, produce none
  of this; there is no `dependencies.py`, no `domain/auth/`, no `UnauthorizedError`, and every route is
  auth-free by construction.
- `domain/exceptions.py` has no `UnauthorizedError` / `ForbiddenError` → stop, use `exception-catalog`
  first; both classes are its to define.
- A **third** auth dependency type is proposed → stop, the two above are exhaustive; express a
  finer-grained rule in the handler instead.
- A role-gated route advertises `401` but not `403` → stop, the advertised codes must match the chosen
  dependency.
- A route is asked to inline a role check after `get_current_user` → stop, use `require_role(...)`.
- Asked for a custom verifier per route → stop, the verifier is bound in `containers.py`; routes use
  the standard dependency.
- A second exception class is minted for the credential case under any name → stop, use
  `exception-catalog`'s single unauthorized class; the challenge branch keys on it.
- The translator is asked to branch on more than the unauthorized class → stop, encode new behaviour
  via subclass `code` / `http_status` (`hex-restapi-app` rule 3 caps it at one branch).
- The verifier is asked to log, retry or cache → stop, use `hex-capability-adapter`; an adapter is thin.
- Asked to omit auth on a non-public route of an app that **does** have auth → stop, authenticated is
  the default and only routes the app declares public skip it.
- Asked for authorization finer than a single role rank — per-row ownership, a policy matrix → stop,
  use `hex-application`; the handler raises `ForbiddenError`.
- The tenant id is put in the path, query or body → stop, stamp it from the resolved identity.
- The composition root binds no verifier → stop, use `hex-wiring` to declare it before the dependency
  asks for it.
