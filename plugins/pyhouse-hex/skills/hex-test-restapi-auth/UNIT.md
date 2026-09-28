# hex-test-restapi-auth — the verifier's unit test

Topic file of `hex-test-restapi-auth`. The obligations are rules 1–3 in `SKILL.md`; what follows is the
**PyJWT + `cryptography` + pytest** binding that satisfies them. This is
`hex-test-capability-adapter`'s pure-CPU flavour, bound to the token verifier.

## `tests/unit/infrastructure/jwt/test_pyjwt_token_verifier.py`

```python
import pytest
from pydantic import SecretStr

from myapp.domain.auth import CurrentUser
from myapp.domain.exceptions import UnauthorizedError
from myapp.infrastructure.jwt import JwtSettings, PyJwtTokenVerifier
from tests.helpers.jwt import generate_rsa_keypair, sign_token

_KEYPAIR = generate_rsa_keypair()

_SETTINGS = JwtSettings(
    algorithm="RS256",
    public_key=SecretStr(_KEYPAIR.public_pem),
    issuer="test-issuer",
    audience="test-audience",
)

_SUBJECT = "test-subject"


def _token(
    *,
    claims: dict[str, object] | None = None,
    issuer: str | None = None,
    audience: str | None = None,
    ttl_seconds: int | None = 300,
) -> str:
    return sign_token(
        {"sub": _SUBJECT} if claims is None else claims,
        private_pem=_KEYPAIR.private_pem,
        issuer=issuer or _SETTINGS.issuer,
        audience=audience or _SETTINGS.audience,
        algorithm=_SETTINGS.algorithm,
        ttl_seconds=ttl_seconds,
    )


def test_verify_valid_token_returns_current_user() -> None:
    verifier = PyJwtTokenVerifier(settings=_SETTINGS)

    result = verifier.verify(_token())

    assert result == CurrentUser(id=_SUBJECT)


def test_verify_expired_token_raises_unauthorized_error() -> None:
    verifier = PyJwtTokenVerifier(settings=_SETTINGS)

    with pytest.raises(UnauthorizedError) as exc:
        verifier.verify(_token(ttl_seconds=-3600))

    assert exc.value.context == {"reason": "expired"}


def test_verify_wrong_audience_raises_unauthorized_error() -> None:
    verifier = PyJwtTokenVerifier(settings=_SETTINGS)

    with pytest.raises(UnauthorizedError) as exc:
        verifier.verify(_token(audience="other-audience"))

    assert exc.value.context == {"reason": "invalid"}


def test_verify_wrong_issuer_raises_unauthorized_error() -> None:
    verifier = PyJwtTokenVerifier(settings=_SETTINGS)

    with pytest.raises(UnauthorizedError) as exc:
        verifier.verify(_token(issuer="other-issuer"))

    assert exc.value.context == {"reason": "invalid"}


def test_verify_tampered_signature_raises_unauthorized_error() -> None:
    verifier = PyJwtTokenVerifier(settings=_SETTINGS)

    with pytest.raises(UnauthorizedError) as exc:
        verifier.verify(_token()[:-4] + "AAAA")

    assert exc.value.context == {"reason": "invalid"}


def test_verify_token_missing_subject_raises_unauthorized_error() -> None:
    verifier = PyJwtTokenVerifier(settings=_SETTINGS)

    with pytest.raises(UnauthorizedError) as exc:
        verifier.verify(_token(claims={}))

    assert exc.value.context == {"reason": "invalid"}


def test_verify_token_without_expiry_raises_unauthorized_error() -> None:
    verifier = PyJwtTokenVerifier(settings=_SETTINGS)

    with pytest.raises(UnauthorizedError) as exc:
        verifier.verify(_token(ttl_seconds=None))

    assert exc.value.context == {"reason": "invalid"}
```

The subject is the issuer's opaque string and the verifier passes it through unparsed, so there is no
subject-format case to test. An absent claim lands on the library's own invalid-token arm: a token can
carry a valid signature and still not describe a caller. Every case on that arm asserts the same stable
`reason`, never the library's class name (`hex-restapi-auth`).

### Rank apps only — the role claim

Where a route gates on rank (`hex-restapi-auth`), the verifier also requires and parses `role`, which
adds a check of its own. `_token`'s default claims and the happy-path expectation grow the role
(`{"sub": _SUBJECT, "role": Role.HIGHER.value}`, `CurrentUser(id=_SUBJECT, role=Role.HIGHER)`, with
`Role` imported beside `CurrentUser`), and two cases join the module:

```python
def test_verify_token_missing_role_raises_unauthorized_error() -> None:
    verifier = PyJwtTokenVerifier(settings=_SETTINGS)

    with pytest.raises(UnauthorizedError) as exc:
        verifier.verify(_token(claims={"sub": _SUBJECT}))

    assert exc.value.context == {"reason": "invalid"}


def test_verify_undeclared_role_raises_unauthorized_error() -> None:
    verifier = PyJwtTokenVerifier(settings=_SETTINGS)

    with pytest.raises(UnauthorizedError) as exc:
        verifier.verify(_token(claims={"sub": _SUBJECT, "role": "NOT_A_ROLE"}))

    assert exc.value.context == {"reason": "invalid_claims"}
```

A role the app does not declare lands on the claim-parsing arm, which an app without rank does not have.

`sign_token` is the same helper the integration fixtures use — one signer for the whole suite, so a
change to the claim shape cannot leave the unit and integration paths minting different tokens. `_token`
takes named overrides rather than `**kwargs`, so every call stays fully typed with no type-ignore
(`python-style`).

