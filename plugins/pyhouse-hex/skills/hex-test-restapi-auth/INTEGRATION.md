# hex-test-restapi-auth — the integration half

Topic file of `hex-test-restapi-auth`. The obligations are rules 5–24 in `SKILL.md`; what follows is the
**PyJWT + `cryptography` + httpx/ASGI + FastAPI + pytest** binding that satisfies them: the signer, the
fixtures that make a minted token verify against the real app, the discovered unauthenticated probe, and
the authenticated endpoint forms.

## `tests/helpers/jwt.py`

```python
import datetime as _dt
from dataclasses import dataclass
from uuid import uuid4

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

__all__ = ["RsaKeypair", "generate_rsa_keypair", "sign_token"]

@dataclass(frozen=True)
class RsaKeypair:
    private_pem: str
    public_pem: str

def generate_rsa_keypair() -> RsaKeypair:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    return RsaKeypair(
        private_pem=key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode(),
        public_pem=key.public_key().public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        ).decode(),
    )

def sign_token(
    claims: dict[str, object],
    *,
    private_pem: str,
    issuer: str,
    audience: str,
    algorithm: str = "RS256",
    ttl_seconds: int = 300,
) -> str:
    now = _dt.datetime.now(_dt.UTC)
    payload = {
        "iss": issuer,
        "aud": audience,
        "iat": int(now.timestamp()),
        "exp": int((now + _dt.timedelta(seconds=ttl_seconds)).timestamp()),
        "jti": uuid4().hex,
        **claims,
    }
    return jwt.encode(payload, private_pem, algorithm=algorithm)
```

## `tests/integration/api/conftest.py`

```python
from collections.abc import Callable
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from myapp.domain.auth import Role
from myapp.infrastructure.jwt.settings import JwtSettings
from tests.helpers.jwt import RsaKeypair, generate_rsa_keypair, sign_token

@pytest.fixture(scope="session")
def rsa_keypair() -> RsaKeypair:
    return generate_rsa_keypair()

@pytest.fixture(scope="session")
def jwt_settings(rsa_keypair: RsaKeypair) -> JwtSettings:
    return JwtSettings(
        algorithm="RS256",
        public_key=SecretStr(rsa_keypair.public_pem),
        issuer="test-issuer",
        audience="test-audience",
    )

@pytest.fixture
def authed_client(
    real_app: FastAPI,
    rsa_keypair: RsaKeypair,
    jwt_settings: JwtSettings,
) -> Callable[..., AsyncClient]:
    """Factory that mints a fresh JWT and returns an `AsyncClient` bound to
    `real_app`. Each call mints a new token; the client is an async context
    manager — always use `async with authed_client(...) as client:` so the
    underlying ASGI transport is closed at the end of the test."""

    def _factory(
        role: Role,
        **extra_claims: object,
    ) -> AsyncClient:
        # Mint only what the identity type declares (subject + rank). Anything
        # further this app's identity carries (a tenant id, a display name, …) is
        # the caller's to pass via **extra_claims — never bake one app's identity
        # model in here.
        claims = {
            "sub": str(uuid4()),
            "role": role.value,
            **extra_claims,
        }
        token = sign_token(
            claims,
            private_pem=rsa_keypair.private_pem,
            issuer=jwt_settings.issuer,
            audience=jwt_settings.audience,
            algorithm=jwt_settings.algorithm,
        )
        transport = ASGITransport(app=real_app)
        return AsyncClient(
            transport=transport,
            base_url="http://testserver",
            headers={"Authorization": f"Bearer {token}"},
        )

    return _factory
```

## The `real_app` substitution this skill adds

`real_app` and `TestInfraProvider` live in `tests/integration/conftest.py` and are owned by
`hex-test-integration-setup`. An app that declares auth adds one fixture parameter, one constructor
field and one factory — and nothing else:

```python
from myapp.infrastructure.jwt.settings import JwtSettings
```

```python
    jwt_settings: JwtSettings,          # in real_app's signature, passed to TestInfraProvider
```

```python
    @provide(override=True)             # in TestInfraProvider
    def jwt_settings(self) -> JwtSettings:
        return self._jwt_settings
```

That factory is what makes `authed_client`-minted tokens verify against the running app. Strip all three
on an auth-less app: nothing binds `JwtSettings`, so a factory claiming to override one fails when the
graph is assembled.

### Fixture-resolution coupling between the two conftests

`real_app` (defined up-tree in `tests/integration/conftest.py`) declares `jwt_settings` as one of its
parameters and hands it to `TestInfraProvider`. Pytest resolves that name by
walking the conftest hierarchy from the running test outward — for tests under `tests/integration/api/`,
the `jwt_settings` fixture produced in the api conftest is visible. Without this substitution, every
`authed_client`-minted token would be signed with the test keypair but verified against the production
public key the real composition root would build — every authenticated test would fail with 401.

The coupling has a cost: `real_app` cannot be used from tests outside `tests/integration/api/` (e.g.
`tests/integration/postgres/`), because `jwt_settings` isn't visible there. That's fine — repository
contract tests use `sf` directly and never construct the FastAPI app. `test-principles` records the
down-tree-resolution mechanism as the universal point; the `jwt_settings` instance is the conditional
one.

## `test_unauth_returns_401.py` — the discovered probe

One file, emitted for an auth app only. It discovers every protected route off the running app and
asserts each one rejects an anonymous caller; adding an endpoint joins it to the suite automatically.

```python
import re

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute, RouteContext, iter_route_contexts
from httpx import ASGITransport, AsyncClient

from myapp.domain.exceptions import UnauthorizedError
from myapp.restapi.dependencies import get_current_user

def _api_operations(app: FastAPI) -> list[RouteContext]:
    """Every API operation the app serves, one resolved route context each.

    `include_router(...)` keeps each included router as a single entry in
    `app.routes`; `iter_route_contexts` resolves those entries into one context
    per operation. Two things the probe depends on are resolved onto that
    context: `path_format`, the path a client must actually request (the
    `include_router(prefix=...)` one, with a path converter's suffix already
    stripped), and the dependency tree with whatever
    `include_router(..., dependencies=[...])` added — so router-level auth is
    seen here."""
    return [
        context for context in iter_route_contexts(app.routes)
        if isinstance(context.original_route, APIRoute)
    ]

def _depends_on(dependant: object, target: object) -> bool:
    """True iff `target` is called anywhere in the dependency tree, at any
    depth. FastAPI nests a dependency's own dependencies under it, so a check
    of the first level misses every route that reaches the target indirectly."""
    for dep in getattr(dependant, "dependencies", []):
        if dep.call is target or _depends_on(dep, target):
            return True
    return False

def _is_protected(route: RouteContext) -> bool:
    """A route is protected iff `get_current_user` is in its dependency tree —
    attached directly, or beneath `require_role(...)`, whose gate depends on it
    (see hex-restapi-auth). Identity, not a name or an attribute, is the test.
    Public routes (info, health, OpenAPI itself) are naturally excluded.

    `dependant` is a FastAPI route internal rather than part of its documented
    surface; the context resolves it for the operation, include-time
    dependencies included."""
    return _depends_on(route.dependant, get_current_user)

def _protected_routes(app: FastAPI) -> list[tuple[str, str]]:
    out: list[tuple[str, str]] = []
    for route in _api_operations(app):
        if not _is_protected(route):
            continue
        for method in sorted(route.methods or ()):
            if method == "HEAD":
                continue
            out.append((method, route.path_format or ""))
    return out

async def test_the_walk_found_protected_routes_to_probe(real_app: FastAPI) -> None:
    """The net under the parametrized probe below, and the reason it is a test
    of its own: an empty parameter set does not fail, it SKIPS — pytest's
    `empty_parameter_set_mark` defaults to `skip`, so it reports `got empty
    parameter set` and the run stays green. A walk that discovers nothing
    therefore takes this whole file out of the run in silence, and the silence
    is indistinguishable from an app with no protected routes. This net runs
    whatever the walk returns, and it tells the two apart."""
    assert _api_operations(real_app), "no API operation was discovered, so nothing was probed"
    assert _protected_routes(real_app), (
        "API operations were discovered but none of them is protected, in an app that "
        "declares auth — either the auth dependency is not wired or the walk missed it"
    )

async def test_protected_route_returns_401_without_token(
    method: str, path: str, real_app: FastAPI
) -> None:
    # `method` / `path` are parametrized by `pytest_generate_tests` below.
    async with AsyncClient(
        transport=ASGITransport(app=real_app),
        base_url="http://testserver",
    ) as client:
        # Substitute EVERY braced path segment, whatever it is named — a fixed list
        # of parameter names silently skips the route that introduces a fourth.
        url = re.sub(r"\{[^{}]+\}", "00000000-0000-0000-0000-000000000000", path)
        response = await client.request(method, url)

    assert response.status_code == 401
    body = response.json()
    # The code CONSTANT is the contract, not its literal string — assert against
    # the domain exception's own `.code` (mirrors `hex-test-restapi-endpoint`'s
    # assert-errors-by-code rule).
    assert body["code"] == UnauthorizedError.code
    # Only the challenge SCHEME is load-bearing (RFC 7235). The realm is app-specific;
    # assert the scheme is present, never freeze a `realm="<app>"` string.
    assert response.headers.get("WWW-Authenticate", "").startswith("Bearer")

def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    """Discover protected routes at collection time by importing `create_app`
    once. Keeps test parametrization tied to the actual route graph instead
    of a hand-maintained list."""
    if "method" in metafunc.fixturenames and "path" in metafunc.fixturenames:
        from myapp.restapi.main import create_app

        app = create_app()
        cases = _protected_routes(app)
        metafunc.parametrize("method,path", cases, ids=[f"{m} {p}" for m, p in cases])
```

## `test_<verb>_<noun>.py` — the authenticated endpoint forms

The endpoint-test file's shape, its one-file-per-endpoint rule, schema validation and per-resource
fixtures are `hex-test-restapi-endpoint`'s. These are the auth-carrying variants of that shape, and the
`Role.LOWER` / `Role.HIGHER` ladder they name is the catalogue's **placeholder** pair
(`hex-restapi-auth`) — substitute the app's own members, and however many of them it has.

### JSON mutation, role-gated

```python
import uuid
from collections.abc import Callable

from httpx import AsyncClient

from myapp.domain.auth import Role
from myapp.restapi.schemas import FooResponse

async def test_create_foo_happy_path(
    authed_client: Callable[..., AsyncClient], bar_id: uuid.UUID
) -> None:
    async with authed_client(role=Role.HIGHER) as client:
        response = await client.post("/foos", json={"name": "alpha", "bar_id": str(bar_id)})

    assert response.status_code == 201
    body = FooResponse.model_validate(response.json())
    assert body.name == "alpha"
    assert body.bar_id == bar_id

async def test_create_foo_forbidden_for_lower_role(
    authed_client: Callable[..., AsyncClient], bar_id: uuid.UUID
) -> None:
    async with authed_client(role=Role.LOWER) as client:
        response = await client.post("/foos", json={"name": "alpha", "bar_id": str(bar_id)})

    assert response.status_code == 403
```

### GET, tenant-scoped, cross-tenant returns 404 (not 403)

For a tenant-scoped resource the per-resource `conftest.py` carries a `tenant_id` fixture, and its
`foo_id` fixture seeds the row owned by that tenant; a test that needs both takes both, each under its
own type, rather than one fixture handing back an unnamed pair.

```python
import uuid
from collections.abc import Callable

from httpx import AsyncClient

from myapp.domain.auth import Role
from myapp.restapi.schemas import FooResponse

async def test_get_foo_returns_payload(
    authed_client: Callable[..., AsyncClient], foo_id: uuid.UUID, tenant_id: uuid.UUID
) -> None:
    # The tenancy keyword is this app's own claim name, forwarded via authed_client's
    # **extra_claims (the factory has no tenant parameter — see Rule 8).
    async with authed_client(role=Role.LOWER, tenant_id=tenant_id) as client:
        response = await client.get(f"/foos/{foo_id}")

    assert response.status_code == 200
    FooResponse.model_validate(response.json())

async def test_get_foo_in_other_tenant_returns_404(
    authed_client: Callable[..., AsyncClient], foo_id: uuid.UUID
) -> None:
    other_tenant = uuid.uuid4()

    async with authed_client(role=Role.LOWER, tenant_id=other_tenant) as client:
        response = await client.get(f"/foos/{foo_id}")

    assert response.status_code == 404  # NOT 403 — prevents enumeration
```

An authenticated multipart or streaming test is the same substitution: take
`hex-test-restapi-endpoint`'s skeleton and drive it through `async with authed_client(role=…) as
client:` instead of the plain client.

