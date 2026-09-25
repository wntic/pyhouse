# hex-test-restapi-auth — the verifier's unit test

Topic file of `hex-test-restapi-auth`. The obligations are rules 1–4 in `SKILL.md`; what follows is the
**PyJWT + `cryptography` + pytest** binding that satisfies them. This is
`hex-test-capability-adapter`'s pure-CPU flavour, bound to the token verifier.

## `tests/unit/infrastructure/jwt/test_pyjwt_token_verifier.py`

The verifier is a pure-CPU capability adapter, so it takes `hex-test-capability-adapter`'s pure-CPU
flavor: `tests/unit/infrastructure/<adapter>/`, module-level helpers rather than fixtures, no container,
and **one test per `raise` site**. Real crypto — a real keypair, real signatures — never a pre-baked
token string the library never produced.

```python
from uuid import UUID

import pytest
from cryptography.hazmat.primitives import serialization
from pydantic import SecretStr
from cryptography.hazmat.primitives.asymmetric import rsa

from myapp.domain.auth import CurrentUser, Role
from myapp.domain.exceptions import UnauthorizedError
from myapp.infrastructure.jwt.pyjwt_token_verifier import PyJwtTokenVerifier
from myapp.infrastructure.jwt.settings import JwtSettings

from tests.helpers.jwt import sign_token

def _keypair() -> tuple[str, str]:
    private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem_private = private.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode()
    pem_public = private.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode()
    return pem_private, pem_public

_PRIVATE_PEM, _PUBLIC_PEM = _keypair()

_SETTINGS = JwtSettings(
    algorithm="RS256",
    public_key=SecretStr(_PUBLIC_PEM),
    issuer="test-issuer",
    audience="test-audience",
)

_CALLER_ID = "11111111-1111-1111-1111-111111111111"

def _token(
    *,
    claims: dict[str, object] | None = None,
    issuer: str | None = None,
    audience: str | None = None,
    ttl_seconds: int = 300,
) -> str:
    return sign_token(
        {"sub": _CALLER_ID, "role": Role.HIGHER.value} if claims is None else claims,
        private_pem=_PRIVATE_PEM,
        issuer=issuer or _SETTINGS.issuer,
        audience=audience or _SETTINGS.audience,
        algorithm=_SETTINGS.algorithm,
        ttl_seconds=ttl_seconds,
    )

def test_verify_valid_token_returns_current_user() -> None:
    verifier = PyJwtTokenVerifier(settings=_SETTINGS)

    result = verifier.verify(_token())

    assert result == CurrentUser(id=UUID(_CALLER_ID), role=Role.HIGHER)

def test_verify_expired_token_raises_unauthorized_error() -> None:
    verifier = PyJwtTokenVerifier(settings=_SETTINGS)

    with pytest.raises(UnauthorizedError) as exc:
        verifier.verify(_token(ttl_seconds=-3600))

    assert exc.value.context == {"reason": "expired"}

def test_verify_wrong_audience_raises_unauthorized_error() -> None:
    verifier = PyJwtTokenVerifier(settings=_SETTINGS)

    with pytest.raises(UnauthorizedError) as exc:
        verifier.verify(_token(audience="other-audience"))

    assert exc.value.context["reason"] == "InvalidAudienceError"

def test_verify_wrong_issuer_raises_unauthorized_error() -> None:
    verifier = PyJwtTokenVerifier(settings=_SETTINGS)

    with pytest.raises(UnauthorizedError) as exc:
        verifier.verify(_token(issuer="other-issuer"))

    assert exc.value.context["reason"] == "InvalidIssuerError"

def test_verify_tampered_signature_raises_unauthorized_error() -> None:
    verifier = PyJwtTokenVerifier(settings=_SETTINGS)

    with pytest.raises(UnauthorizedError) as exc:
        verifier.verify(_token()[:-4] + "AAAA")

    assert exc.value.context["reason"] in {
        "InvalidSignatureError", "DecodeError",
    }

def test_verify_token_missing_role_raises_unauthorized_error() -> None:
    verifier = PyJwtTokenVerifier(settings=_SETTINGS)

    with pytest.raises(UnauthorizedError) as exc:
        verifier.verify(_token(claims={"sub": _CALLER_ID}))

    assert exc.value.context["reason"] == "MissingRequiredClaimError"

def test_verify_non_uuid_subject_raises_unauthorized_error() -> None:
    verifier = PyJwtTokenVerifier(settings=_SETTINGS)

    with pytest.raises(UnauthorizedError) as exc:
        verifier.verify(_token(claims={"sub": "not-a-uuid", "role": Role.HIGHER.value}))

    assert exc.value.context == {"reason": "invalid_claims"}

def test_verify_undeclared_role_raises_unauthorized_error() -> None:
    verifier = PyJwtTokenVerifier(settings=_SETTINGS)

    with pytest.raises(UnauthorizedError) as exc:
        verifier.verify(_token(claims={"sub": _CALLER_ID, "role": "NOT_A_ROLE"}))

    assert exc.value.context == {"reason": "invalid_claims"}
```

The last three are the identity-building arms: a token can carry a valid signature and still not
describe a caller. An absent claim lands on the library's own invalid-token arm; a subject that is not
an identifier and a role the app does not declare land on the claim-parsing arm. Both value cases are
kept because each is a different parse that could be moved outside the translated scope on its own.

`sign_token` is the same helper the integration fixtures use — one signer for the whole suite, so a
change to the claim shape cannot leave the unit and integration paths minting different tokens. `_token`
takes named overrides rather than `**kwargs`, so every call stays fully typed with no type-ignore
(`python-style`).

