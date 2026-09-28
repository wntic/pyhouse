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
- Which error codes a route advertises for non-auth reasons → `hex-restapi-endpoint`, in its sibling
  `CONTRACTS.md`; registering a status a middleware introduces → `hex-restapi-app`, *Registering a
  middleware's status*.
- `UnauthorizedError` / `ForbiddenError` themselves, and boundary translation → `exception-catalog`.
- Enum and value-object form in general → `hex-domain-model`; the rank-ordered `Role` below is the
  catalogue's worked enum carrying a method over its own values.
- How to write the capability protocol the verifier satisfies → `hex-domain-ports`.
- Adapter form in general — constructor injection, secrets, no logging, no business logic →
  `hex-capability-adapter`; this skill carries only the verifier instance of it.
- What a settings class declares → `python-settings`; binding lifetimes and composition-root declaration order → `hex-wiring`.
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

__all__ = ["CurrentUser"]


@dataclass(frozen=True, slots=True)
class CurrentUser:
    id: str
```

`id` is the credential's subject exactly as the issuer states it. It is converted to the app's own id
type only where the issuer guarantees that form; otherwise a subject the app did not mint would fail
to parse and lock a valid caller out. A rank app adds a `role` (*Rank apps only*, below); a tenant is
added the same way, and which DTO fields are stamped from the identity, and how a handler scopes by
them, are `hex-application`'s.

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

### Template — PyJWT

Placement (`infrastructure/jwt/`, the external tech), constructor injection, secret handling, the
no-logging rule and not importing the port it satisfies (`ICanVerifyToken`) are
`hex-capability-adapter`'s; this is the sync pure-CPU adapter that skill describes in prose, bound to
PyJWT. Translation of the library's parse/verify errors follows `exception-catalog`.

```python
import jwt

from myapp.domain.auth import CurrentUser
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
                options={"require": ["sub"]},
            )
            return CurrentUser(id=claims["sub"])
        except jwt.ExpiredSignatureError as exc:
            raise UnauthorizedError("token expired", {"reason": "expired"}) from exc
        except jwt.InvalidTokenError as exc:
            raise UnauthorizedError(
                "invalid token",
                {"reason": exc.__class__.__name__},
            ) from exc
```

`algorithms=[...]` is a **list of one**, read from settings — never the token's own `alg` header. A
verifier that trusts the header accepts `none` and accepts a symmetric algorithm signed with the public
key it published; the settings-side allowlist validator below is what keeps that list honest.

**The identity is built inside the translated scope.** A token can carry a valid signature and still
not describe a caller — a claim missing, a subject of the wrong type. Each of those is an unverifiable
credential and answers 401 like a bad signature, never a 500. Here `require` turns an absent claim into
the library's own `InvalidTokenError`, and PyJWT (2.10 and later) rejects a non-string `sub` the same
way.

### `infrastructure/jwt/settings.py`

```python
from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["JwtSettings"]

_ALLOWED_ALGORITHMS = frozenset({"RS256", "RS384", "RS512", "ES256", "EdDSA"})


class JwtSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MYAPP_JWT_",
        env_file=".env",  # only where the project keeps a dotenv file for development
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
            raise ValueError(f"JWT algorithm {value!r} is not in the allowlist {sorted(_ALLOWED_ALGORITHMS)}")
        return value

    @field_validator("public_key")
    @classmethod
    def _unescape_pem(cls, value: SecretStr) -> SecretStr:
        return SecretStr(value.get_secret_value().replace("\\n", "\n"))
```

The allowlist is a **rejection validator** in the sense of `python-settings` rule 12: it refuses a value
that would cause silent misbehaviour rather than a loud failure. An `alg` of `none`, or `HS256` against
a published public key, verifies happily and forges every identity in the system; the failure surfaces
as "auth works" rather than as an error, so the only place to catch it is process startup. A service
that is its own issuer may allow one HMAC algorithm with a secret key instead, never alongside a
published public key. The PEM
unescape is the other sanctioned validator purpose — normalization, accepting the env-friendly
single-line form and storing the canonical one. Settings rules, secrets and `SecretStr` handling are
`python-settings`; this file is one instance of them.

### Binding traps — bearer JWS

**Verification trusts configuration, not the token.** The accepted algorithm set is declared in settings
and validated against an allowlist at startup; the token's own header never selects it. That obligation,
the `Authorization` header the dependency below reads and the RFC-7235 challenge the error branch
attaches are **this scheme's own** — an opaque token, a session cookie and a gateway header have none of
the three — so the obligation is stated here, with the template that names the stack, and holds
wherever this binding is in use: the allowlist never widens to `none`, nor to a symmetric algorithm
against a published public key. The header is read and the token decoded only in `get_current_user`
(rule 3); the challenge goes on a 401 alone and freezes no literal realm (rule 9).

## The route dependencies

### `restapi/dependencies.py`

`dependencies.py` is FastAPI's home for shared route dependencies; in this catalogue its only current
content is the auth dependency, so the file is emitted **only** for an app that declares auth. An auth-less app
has no `get_current_user`, no `CurrentUser` import, and routes attach no auth
dependency — hence no `dependencies.py` at all (`hex-restapi-app`). A non-auth shared route dependency,
if one is ever introduced, lives in the same file independent of auth.

```python
from dishka.integrations.fastapi import FromDishka, inject
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from myapp.domain.auth import CurrentUser, ICanVerifyToken
from myapp.domain.exceptions import UnauthorizedError

__all__ = ["get_current_user"]

_bearer_scheme = HTTPBearer(auto_error=False)


@inject
async def get_current_user(
    verifier: FromDishka[ICanVerifyToken],
    creds: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> CurrentUser:
    if creds is None or creds.scheme.lower() != "bearer":
        raise UnauthorizedError("Missing bearer token", {"reason": "missing_credentials"})
    return verifier.verify(creds.credentials)
```

The bearer scheme is declared **once** at module level. `get_current_user` receives the verifier by
its port type — never instantiate verifiers in routes or dependencies. **The `@inject` decorator is
required here even though the routers carry `route_class=DishkaRoute`**: that route class injects route
functions, not the `Depends` functions behind them (`hex-restapi-endpoint`). The verifier arrives typed,
so nothing is cast.

### Rank apps only — the role gate

Where some route gates on rank, four things are added; an app whose routes only authenticate has none
of them. `CurrentUser` gains `role: Role`. The verifier requires the claim (`"require": ["sub",
"role"]`), builds `CurrentUser(id=claims["sub"], role=Role(claims["role"]))`, and gains one arm —
`except ValueError` → `UnauthorizedError("invalid token claims", {"reason": "invalid_claims"})` —
because a role the app does not declare is an unverifiable credential, never a 500.
`domain/auth/role.py` holds the ladder:

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

The self-reference is quoted because the name is not bound until the class statement finishes and the
catalogue bans `from __future__ import annotations` (`python-style`). `LOWER` and `HIGHER` are
**placeholder ranks**, the way `Foo` is the placeholder aggregate: substitute the app's own members,
however many it has; a route template names the slot — `Role.<MIN_RANK>` — never a member. Its unit
test covers `satisfies` at, above and below the bar (`hex-test-domain`).

`restapi/dependencies.py` gains the gate below `get_current_user`, and `require_role` joins its
`__all__`. The gate is a callable class, not a closure, so the role it gates on is a typed attribute:

```python
from fastapi import Depends

from myapp.domain.auth import CurrentUser, Role
from myapp.domain.exceptions import ForbiddenError


class _RoleDependency:
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

## The error-handler auth branch

`hex-restapi-app`'s primary `error_handler.py` is the auth-less one. An app that declares auth uses the
**authenticated** variant instead: the `UnauthorizedError` import is added and the translator grows its
one `isinstance` branch, attaching the RFC-7235 challenge. Nothing else in the file changes, and
`hex-restapi-app` rule 3 caps it at **at most one** branch.

```python
from myapp.domain.exceptions import MyappError, UnauthorizedError, ValidationError
```

```python
        headers: dict[str, str] = {}
        if isinstance(exc, UnauthorizedError):
            headers["WWW-Authenticate"] = "Bearer"
        return JSONResponse(status_code=exc.http_status, content=body, headers=headers or None)
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
how an authenticated route is derived from an auth-free one, and the coordinated
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

- **JWKS endpoint.** The issuer publishes its key set rather than one key: the adapter fetches it and
  caches the keys by `kid`, selecting the verifying key by the token's `kid` and never by its `alg`.
  The port, the identity, the gate and the codes are unchanged.
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
11. **A rank ladder is the app's own** — a rank-ordered enum with a rank-satisfaction method, whose
    members and their number belong to the app; a route template names the slot, never a member.
12. **Auth-derived values come from the resolved identity, never from the request.** Which DTO fields
    they are, and how a handler scopes by them, are `hex-application`'s.
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
- Domain imports absolute (`from myapp.domain.auth import CurrentUser`). The verifier adapter
  **never** imports the protocol it satisfies — structural subtyping at the DI site is the contract
  (`hex-capability-adapter`'s rule that an adapter neither inherits nor imports its protocol).
- Full annotations on every dependency, the callable class's `__call__`, and the verifier's methods. No
  `from __future__ import annotations` (`python-style`).

## Package wiring

`domain/auth/` is a subdomain package — its `__init__.py` re-exports `CurrentUser` and
`ICanVerifyToken` (and `Role` in a rank app), which every `from myapp.domain.auth import ...` above resolves against — and
`infrastructure/jwt/` an infrastructure one; both follow `python-packaging`, with the layer placement
in `hex-architecture`. `restapi/dependencies.py` sits in the entrypoint package `hex-restapi-app` creates, under that package's entrypoint carve-out.

## Hard stops

- The app declares no auth (every endpoint anonymous, no token-verifier capability) → stop, produce none
  of this; there is no `dependencies.py`, no `domain/auth/`, no `UnauthorizedError`, and every route is
  auth-free by construction.
- `domain/exceptions.py` has no `UnauthorizedError` / `ForbiddenError` → stop, use `exception-catalog`
  first; both classes are its to define.
- The translator is asked to branch on more than the unauthorized class → stop, encode new behaviour
  via subclass `code` / `http_status` (`hex-restapi-app` rule 3 caps it at one branch).
- The verifier is asked to log, retry or cache → stop, use `hex-capability-adapter`; an adapter is thin.
- Asked for authorization finer than a single role rank — per-row ownership, a policy matrix, a third
  kind of auth dependency → stop, use `hex-application`; the handler raises `ForbiddenError`.
- The composition root binds no verifier → stop, use `hex-wiring` to declare it before the dependency
  asks for it.
