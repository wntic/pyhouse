---
name: hex-capability-adapter
description: Use when implementing an `ICan<Verb>` capability against a real external system — the adapter under `infrastructure/<tech>/` (`s3/`, `jwt/`, `openai/`) as an async SDK client (`aioboto3`), an async HTTP gateway (`httpx`), or sync pure CPU, translating SDK errors into `exception-catalog` classes. Not aggregate CRUD — that is `hex-persistence` or `hex-store-repository`; the protocol is `hex-domain-ports`.
paths: ["**/infrastructure/**"]
---

# Hex — Capability Adapter (infrastructure)

Produces one adapter class that adapts a domain `ICan<Verb>` capability protocol to a concrete external
system. The adapter does not inherit from the protocol — structural subtyping at the injection site is
the contract — and it is the last place the external library's own exceptions exist: translation happens
here, into the classes `exception-catalog` owns.

## When to use vs. neighbours

- Aggregate-root CRUD over a relational store → `hex-persistence`, not this skill.
- Aggregate-root persistence on a key-value, document or vector store → `hex-store-repository`; an injected SDK client alone does not make something a capability.
- The `ICan<Verb>` protocol file this adapter satisfies → `hex-domain-ports`.
- The settings class (`<Tech>Settings`) the adapter consumes → `hex-wiring`.
- The binding that constructs this adapter (almost always process-lifetime) → `hex-wiring`.
- The catalogue exception classes the SDK's own errors are translated into → `exception-catalog`.
- The undo a compensating handler calls on this adapter (`delete` beside `upload`) → an ordinary method that raises on failure, declared on a port by `hex-domain-ports`; the handler-side guard that tolerates its failure is `hex-patterns`'.
- An in-memory test stand-in for this capability (the `Fake<Capability>` flavor) → `hex-test-application-handler`.
- Testing the real adapter — containerized backend, `respx`-intercepted HTTP, or pure CPU → `hex-test-capability-adapter`.
- A token verifier — its port, its adapter and the dependency that resolves it → `hex-restapi-auth`; the form is this skill's sync pure-CPU one, bound there.
- The `infrastructure/<tech>/` folder, the module name and the class name → `hex-conventions` and `naming`.

## Template(s)

### File layout

```
src/myapp/infrastructure/<adapter>/    # <adapter> = the external tech: s3, jwt, openai, …
├── __init__.py            # see python-packaging
└── s3_foo_storage.py      # this skill writes this file
```

`<adapter>` is the external tech the adapter wraps: `s3/`, `jwt/`, `openai/`, `docx/`, `<vendor>/`. Infra groups by tech, not by domain concern. For filename and class naming, see `naming`.

### Template — async SDK client (aioboto3, S3)

```python
from collections.abc import Mapping
from typing import cast

import aioboto3
from botocore.exceptions import ClientError

from myapp.domain.exceptions import (
    NotFoundError, UpstreamError, ValidationError,
)
# No import of the protocols the adapter satisfies (Rule 2).

from .settings import S3Settings

__all__ = ["S3FooStorage"]

_ERROR_CODE_MAP: Mapping[str, type[Exception]] = {
    "NoSuchKey": NotFoundError,
    "NoSuchBucket": NotFoundError,
    "InvalidRequest": ValidationError,
}

def _map_client_error(exc: ClientError, *, key: str) -> Exception:
    code = exc.response.get("Error", {}).get("Code", "")
    target = _ERROR_CODE_MAP.get(code)
    if target is NotFoundError:
        return NotFoundError("object not found", {"key": key, "code": code})
    if target is ValidationError:
        return ValidationError("invalid storage request", {"key": key, "code": code})
    return UpstreamError(
        "storage call failed",
        {"key": key, "code": code or "unknown"},
    )

class S3FooStorage:
    def __init__(self, session: aioboto3.Session, settings: S3Settings) -> None:
        self._session = session
        self._bucket = settings.bucket
        self._endpoint_url = settings.endpoint_url

    async def upload(self, key: str, body: bytes) -> None:
        try:
            async with self._session.client("s3", endpoint_url=self._endpoint_url) as s3:
                await s3.put_object(Bucket=self._bucket, Key=key, Body=body)
        except ClientError as exc:
            raise _map_client_error(exc, key=key) from exc

    async def delete(self, key: str) -> None:
        try:
            async with self._session.client("s3", endpoint_url=self._endpoint_url) as s3:
                await s3.delete_object(Bucket=self._bucket, Key=key)
        except ClientError as exc:
            raise _map_client_error(exc, key=key) from exc

    async def download(self, key: str) -> bytes:
        try:
            async with self._session.client("s3", endpoint_url=self._endpoint_url) as s3:
                response = await s3.get_object(Bucket=self._bucket, Key=key)
                # See python-style for narrowing the SDK's `Any` return to protocol `bytes`.
                return cast(bytes, await response["Body"].read())
        except ClientError as exc:
            raise _map_client_error(exc, key=key) from exc
```

The adapter satisfies **two** capability ports over one technology — `ICanStoreFoos` (`upload` plus
`delete`, one reversible action) and `ICanFetchFoos` (`download`) — because a port holds at most two
methods (`hex-domain-ports`) while nothing limits how many ports one adapter satisfies.

### Template — async HTTP gateway (httpx)

```python
import httpx

from myapp.domain.exceptions import NotFoundError, UpstreamError, ValidationError
from myapp.domain.bars import BarToken  # the protocol (ICanFetchBarToken) is NOT imported — Rule 2

from .settings import BarGatewaySettings

__all__ = ["HttpBarGateway"]

class HttpBarGateway:
    def __init__(self, client: httpx.AsyncClient, settings: BarGatewaySettings) -> None:
        self._client = client
        self._base_url = str(settings.base_url)
        self._api_key = settings.api_key.get_secret_value()

    async def fetch_token(self, subject: str) -> BarToken:
        try:
            response = await self._client.post(
                f"{self._base_url}/tokens",
                headers={"Authorization": f"Bearer {self._api_key}"},
                json={"subject": subject},
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise _map_status(exc, subject=subject) from exc
        except httpx.HTTPError as exc:
            raise UpstreamError(
                "bar gateway unreachable",
                {"subject": subject, "reason": exc.__class__.__name__},
            ) from exc
        payload = response.json()
        return BarToken(value=payload["token"], expires_at=payload["expires_at"])

def _map_status(exc: httpx.HTTPStatusError, *, subject: str) -> Exception:
    status = exc.response.status_code
    if status == 404:
        return NotFoundError("bar subject not found", {"subject": subject, "status": status})
    if status == 400:
        return ValidationError("bar gateway rejected request", {"subject": subject, "status": status})
    return UpstreamError(
        "bar gateway error",
        {"subject": subject, "status": status},
    )
```

### Template — sync pure CPU (stdlib plus a parsing library)

For canonicalizers / renderers / verifiers with no IO that need a third-party library — work the
standard library can do is domain logic, not an adapter (`hex-domain-ports`). For translation of the
library's parse errors, see `exception-catalog`.

```python
from urllib.parse import urlsplit, urlunsplit

import idna

from myapp.domain.bars import CanonicalBarUrl  # the protocol (ICanCanonicalizeBarUrl) is NOT imported — Rule 2
from myapp.domain.exceptions import ValidationError

from .settings import IdnaSettings

__all__ = ["IdnaBarUrlCanonicalizer"]

class IdnaBarUrlCanonicalizer:
    def __init__(self, settings: IdnaSettings) -> None:
        self._allowed_schemes = settings.allowed_schemes

    def canonicalize(self, raw: str) -> CanonicalBarUrl:
        parts = urlsplit(raw.strip())
        if parts.scheme not in self._allowed_schemes:
            raise ValidationError(
                "unsupported url scheme",
                {"scheme": parts.scheme or "", "allowed": sorted(self._allowed_schemes)},
            )
        try:
            host = idna.encode(parts.hostname or "").decode()
        except idna.IDNAError as exc:
            raise ValidationError(
                "host is not a valid internationalized domain name",
                {"host": parts.hostname or "", "reason": exc.__class__.__name__},
            ) from exc
        normalized = urlunsplit(
            (parts.scheme, host, parts.path or "/", parts.query, "")
        )
        return CanonicalBarUrl(value=normalized)
```

A pure-CPU adapter has no client to inject — only its settings. It is still an adapter: it translates the
library's own failure (`IDNAError`) into a catalogue exception at the boundary, and it returns a domain
type rather than a raw string.

## Other bindings

- **Another vendor SDK for the same capability** — a different object store, mail provider or model API.
  The client type, its exception family and the code/status vocabulary change together; the port
  conformance, the inject-client-plus-settings constructor, the translate-before-it-escapes rule and the
  context keys are unchanged. Budget the swap as one new error map, not a new adapter shape.
- **A different async HTTP client.** The call and the exception family change; the status-to-catalogue
  mapping, the fallback and the thinness rules do not.
- **A sync-only SDK inside an async service.** The port stays async and the adapter runs the blocking
  call on a worker thread (`asyncio.to_thread`) — calling it inline blocks the event loop for every other
  request. Translation, context and no-instance-state are unchanged.

## Rules

### Form

1. **One adapter class per module**, named for the concrete technology it wraps (`S3FooStorage`, not
   `FooStorage`), so two implementations of one port can coexist. Module structure is
   `python-packaging`'s; the names are `naming`'s.
2. **The adapter does not inherit the protocol it satisfies, and does not import it.** Satisfaction is
   structural and is checked where the adapter is injected; an import of the protocol leaves a dead
   unused import and gains nothing.
3. **Method signatures match the protocol exactly** — parameter names, keyword-only markers and
   async/sync mode included. A near-match satisfies no structural check and fails at the injection site,
   not at the adapter.
4. **The module sits in a directory named for the external technology it wraps** (`s3/`, `openai/`, the
   vendor's own token), never one named for the domain concern it serves. One technology, one directory:
   that is what makes "which of our adapters talk to this vendor" answerable by listing a folder.

### Constructor

5. **The client and the settings arrive by injection, never by construction.** Both are built once by
   the composition root (`hex-wiring`) and handed in; a method that builds its own client
   (`boto3.client(...)`, `httpx.AsyncClient(...)`) defeats connection pooling and cannot be replaced in a
   test without patching the library.
6. **Stash the fields the methods use, not the settings object** — unless several methods read several
   fields. The constructor signature is then an honest statement of what the adapter actually depends
   on, and a test can build it without assembling a settings object.
7. **A secret is unwrapped once, in the constructor** (`settings.api_key.get_secret_value()` under a
   settings library with a secret type), never on each call. A secret never reaches a log line
   (`python-style`) and never reaches an exception's `context` (rule 10).

### Exception translation

8. **Translate at the boundary, chaining the cause.** Catch the library's own exception family inside the
   adapter and raise a catalogue exception `from` it. The catalogue and the cause-chaining rule are
   `exception-catalog`'s.
9. **The library's exception type never escapes the adapter.** No SDK error, HTTP status error or parse
   error crosses into `application/` or an entrypoint — the application layer catches only `DomainError`.
10. **The fallback, the most specific class, the identifying `context` and the no-secret ban are
    `exception-catalog`'s rules**, applied here without change. What they come to in an adapter: the
    fallback is `UpstreamError` for a network or third-party failure (5xx, unknown codes), and that
    includes the upstream rejecting the adapter's **own** configured credential (`InvalidAccessKeyId`,
    `SignatureDoesNotMatch`, an upstream 401 or 403) — the caller's request was sound, and a 401 would
    challenge the caller to re-authenticate over a fault only the service's operator can fix;
    `UnauthorizedError` only where the adapter verifies a credential the caller presented (a token
    verifier, `hex-restapi-auth`); `NotFoundError` when the object or subject does not exist; `ValidationError` only when the upstream rejected the inputs as malformed; `context` carries
    the key, subject or id plus the upstream's own code or status, and never the token or key. An adapter
    never swallows a failure, and never stops one either — a failed undo during compensation is stopped
    in the calling handler (`hex-patterns`), which logs it; an adapter cannot.

### No business logic, no logging

11. **Adapters are thin.** No retries, no caching, no batching, no domain reasoning. Retry and backoff
    belong to the client's own policy (configured where the client is built) or to a dedicated wrapper
    class, so that the adapter stays one call wide and its failure modes stay readable.
12. **An adapter never logs.** Not the call, not the failure: the central error handler owns failure logs
    and the calling handler owns success logs, so a line here is a second entry for one event.
13. **No instance state across calls** beyond constructor-injected handles. An adapter is then safe to
    bind at process lifetime and share across concurrent requests.

### Compensating-transaction contract

14. **Mutating capabilities expose both the forward operation and the undo.** A storage adapter has `upload` *and* `delete`; a publisher that supports retraction has `publish` *and* `retract`. The catch-and-undo logic lives in the application handler (see `hex-patterns`), not in the adapter. The adapter's job is to make the undo callable; like every other method it raises a catalogue exception when it fails, and the handler decides whether that failure may be tolerated.

## Inlined typing / import rules

- Domain imports absolute (`from myapp.domain.bars import BarToken` — the entities/VOs the signatures name). **Never import the capability protocol the adapter satisfies** (`ICanStoreFoos`, `ICanFetchBarToken`, …) — structural subtyping needs no import (Rule 2); importing it is a dead F401. Sibling modules within the same `infrastructure/<adapter>/` package use relative imports (`from .settings import S3Settings`).
- No `from __future__ import annotations`. Full annotations on every method.
- `X | None` over `Optional`. `Mapping[K, V]` / `Sequence[T]` (from `collections.abc`) for read-only views.
- **A raw SDK value typed `Any` is narrowed with `cast`, never silenced.** An SDK return that mypy sees as `Any` (`response["Body"].read()`, an untyped client method) flowing into a typed protocol return is a `[no-any-return]`/`[return-value]` error — fix it with `cast(<protocol-return-type>, …)` at the boundary, the same way a route dependency casts a container-resolved value (`hex-restapi-auth`). An inline `# type: ignore[...]` on the adapter body is never sanctioned: it hides the next genuine type error in that expression too.
- SDK types stay inside the adapter; method signatures use domain types or primitives only.
- No `Any` except at the immediate raw-SDK-payload boundary (e.g. `payload: dict[str, Any] = response.json()` — convert to the domain type on the next line).

## Package wiring

For package wiring, see `python-packaging`; for infrastructure placement, see `hex-architecture`.

## Hard stops

- The adapter is asked to carry relational aggregate CRUD — a table, the statements against it and the
  migration that ships it → stop, that is a repository and not a capability; use `hex-persistence`.
- The adapter is asked to inherit from `ICanX` explicitly → stop, structural subtyping is the contract.
- The adapter is asked to log → stop, adapters do not log; the central error handler owns failure logs.
- The adapter is asked to retry, cache, or batch internally → stop, configure that on the client where
  the client is built, or extract a separate wrapper class.
- The adapter is asked to construct its own SDK client (`boto3.client(...)`, `httpx.AsyncClient()`) →
  stop, both the client and the settings are injected by the composition root.
- The adapter is asked to raise an SDK exception type or bare `Exception` → stop, every external
  exception is translated into a catalogue exception at the boundary (`exception-catalog` owns the
  catalogue).
- A secret is about to be placed in an exception's `context` or a log field → stop, `context` is rendered
  into the error response and logged verbatim.
- The change does not say which external errors a fallible method raises → stop, derive the mapping from
  the library's documented exception family and apply the mandatory fallback: `UpstreamError` for a
  network or third-party failure, the upstream rejecting the adapter's own credential included, and
  `UnauthorizedError` only for a caller's credential the adapter verifies (rule 10). The specific cases are
  judgement; the broad catch-and-translate fallback is not — never leave a method able to raise an
  untranslated external exception.
