# hex-test-restapi-auth — the integration half

Topic file of `hex-test-restapi-auth`. The obligations are rules 4–18 in `SKILL.md`; what follows is the
**PyJWT + `cryptography` + httpx/ASGI + FastAPI + pytest** binding that satisfies them: the signer, the
fixtures that make a minted token verify against the real app, the discovered probe, and the
authenticated endpoint form.

## `tests/helpers/jwt.py`

```python
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

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
        public_pem=key.public_key()
        .public_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        .decode(),
    )


def sign_token(
    claims: dict[str, object],
    *,
    private_pem: str,
    issuer: str,
    audience: str,
    algorithm: str = "RS256",
    ttl_seconds: int | None = 300,
) -> str:
    now = datetime.now(UTC)
    payload: dict[str, object] = {"iss": issuer, "aud": audience, "iat": int(now.timestamp())}
    if ttl_seconds is not None:
        payload["exp"] = int((now + timedelta(seconds=ttl_seconds)).timestamp())
    return jwt.encode({**payload, **claims}, private_pem, algorithm=algorithm)
```

## `tests/integration/api/conftest.py`

```python
from collections.abc import Callable
from uuid import uuid4

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from pydantic import SecretStr

from myapp.infrastructure.jwt import JwtSettings
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
def authenticated_client(
    real_app: FastAPI,
    rsa_keypair: RsaKeypair,
    jwt_settings: JwtSettings,
) -> Callable[..., AsyncClient]:
    def _factory(**extra_claims: object) -> AsyncClient:
        claims: dict[str, object] = {"sub": str(uuid4()), **extra_claims}
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

A rank app adds `role: Role | None = None` before `**extra_claims`, importing `Role` from
`myapp.domain.auth`, and sets `claims["role"] = role.value` when one is given.

## The `container` substitution this skill adds

`container`, `real_app` and `TestInfrastructureProvider` live in `tests/integration/conftest.py` and are
owned by `hex-test-integration-setup`. An app that declares auth adds one fixture parameter, one
constructor field and one factory — and nothing else:

```python
from myapp.infrastructure.jwt import JwtSettings
```

```python
    jwt_settings: JwtSettings,  # in container's signature; TestInfrastructureProvider(..., jwt_settings=jwt_settings)
```

```python
        self._jwt_settings = jwt_settings  # in TestInfrastructureProvider.__init__(..., jwt_settings: JwtSettings)
```

```python
    @provide(override=True)             # in TestInfrastructureProvider
    def jwt_settings(self) -> JwtSettings:
        return self._jwt_settings
```

That factory is what makes `authenticated_client`-minted tokens verify against the running app. Strip all three
on an auth-less app: nothing binds `JwtSettings`, so a factory claiming to override one fails when the
graph is assembled.

### Fixture-resolution coupling between the two conftests

`container`, up-tree in `tests/integration/conftest.py`, takes `jwt_settings` by name, and a fixture
defined down-tree is visible only to tests under it (`test-principles`, *Where tests and fixtures sit*
rule 2). Without the substitution, every `authenticated_client`-minted token would be verified against the
production public key and answer 401.

The coupling has a cost: `container`, and `real_app` over it, cannot be used from tests outside
`tests/integration/api/` (e.g. `tests/integration/postgres/`), because `jwt_settings` isn't visible
there. Repository contract tests take their store's own fixture and never need it; where another
entrypoint's tests outside `api/` do, `rsa_keypair` and `jwt_settings` move up-tree beside `container`.

## `test_unauthenticated_returns_401.py` — the discovered probe

One file, emitted for an auth app only. It walks every operation off the running app and asserts that
each one not declared public refuses an anonymous caller and a caller holding a token the app did not
issue; adding an endpoint joins it to the probe automatically, and making one public adds it to
`_PUBLIC_OPERATIONS`.

```python
import re

import pytest
from fastapi import FastAPI
from fastapi.routing import APIRoute, RouteContext, iter_route_contexts
from httpx import ASGITransport, AsyncClient

from myapp.domain.exceptions import UnauthorizedError
from myapp.infrastructure.jwt import JwtSettings
from tests.helpers.jwt import generate_rsa_keypair, sign_token

# Operations that answer an anonymous caller on purpose; every other one is probed.
_PUBLIC_OPERATIONS: frozenset[tuple[str, str]] = frozenset()

_UNTRUSTED_KEYPAIR = generate_rsa_keypair()


def _api_operations(app: FastAPI) -> list[RouteContext]:
    return [context for context in iter_route_contexts(app.routes) if isinstance(context.original_route, APIRoute)]


def _operations(app: FastAPI) -> list[tuple[str, str]]:
    return [
        (method, context.path_format or "")
        for context in _api_operations(app)
        for method in sorted(context.methods or ())
        if method != "HEAD"
    ]


def _protected_operations(app: FastAPI) -> list[tuple[str, str]]:
    return [operation for operation in _operations(app) if operation not in _PUBLIC_OPERATIONS]


def _requestable(path: str) -> str:
    return re.sub(r"\{[^{}]+\}", "00000000-0000-0000-0000-000000000000", path)


async def test_the_walk_found_operations_to_probe(real_app: FastAPI) -> None:
    """An empty parametrization skips rather than fails, so this net runs whatever the walk finds."""
    operations = set(_operations(real_app))
    assert operations, "no API operation was discovered, so nothing was probed"
    assert _PUBLIC_OPERATIONS <= operations, f"declared public but not served: {_PUBLIC_OPERATIONS - operations}"


async def test_protected_operation_refuses_an_anonymous_caller(method: str, path: str, real_app: FastAPI) -> None:
    # `method` / `path` are parametrized by `pytest_generate_tests` below.
    async with AsyncClient(transport=ASGITransport(app=real_app), base_url="http://testserver") as client:
        response = await client.request(method, _requestable(path))

    assert response.status_code == 401
    assert response.json()["code"] == UnauthorizedError.code
    assert response.headers.get("WWW-Authenticate", "").startswith("Bearer")


async def test_protected_operation_refuses_an_untrusted_token(
    method: str,
    path: str,
    real_app: FastAPI,
    jwt_settings: JwtSettings,
) -> None:
    token = sign_token(
        {"sub": "untrusted"},
        private_pem=_UNTRUSTED_KEYPAIR.private_pem,
        issuer=jwt_settings.issuer,
        audience=jwt_settings.audience,
        algorithm=jwt_settings.algorithm,
    )
    async with AsyncClient(
        transport=ASGITransport(app=real_app),
        base_url="http://testserver",
        headers={"Authorization": f"Bearer {token}"},
    ) as client:
        response = await client.request(method, _requestable(path))

    assert response.status_code == 401
    assert response.json()["code"] == UnauthorizedError.code


def pytest_generate_tests(metafunc: pytest.Metafunc) -> None:
    if "method" in metafunc.fixturenames and "path" in metafunc.fixturenames:
        from myapp.restapi.main import create_app

        cases = _protected_operations(create_app())
        metafunc.parametrize("method,path", cases, ids=[f"{method} {path}" for method, path in cases])
```

## `test_<verb>_<noun>.py` — the authenticated endpoint form

The endpoint-test file's shape, its one-file-per-endpoint rule, body assertions and per-resource
fixtures are `hex-test-restapi-endpoint`'s. This is the auth-carrying variant of that shape.

### JSON mutation

```python
from collections.abc import Callable

from httpx import AsyncClient


async def test_create_foo_returns_the_created_foo(authenticated_client: Callable[..., AsyncClient]) -> None:
    async with authenticated_client() as client:
        response = await client.post("/foos", json={"name": "alpha"})

    assert response.status_code == 201
    assert response.json()["name"] == "alpha"
```

A rank app passes `role=` and adds the below-the-bar case (rule 17), asserting `ForbiddenError.code`;
on a mutation that rejection also shows nothing was written — read it back as an allowed caller
(`authenticated_client(...)` twice, rule 6). Its `Role.LOWER` / `Role.HIGHER` are the catalogue's
**placeholder** pair (`hex-restapi-auth`) — substitute the app's own members, however many it has.

