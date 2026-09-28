---
name: hex-capability-adapter
description: Use when implementing an `ICan<Verb>` capability against a real external system — the adapter under `infrastructure/<tech>/` wrapping an SDK client, an HTTP gateway or a pure-CPU library, translating the library's own errors into `exception-catalog` classes. Not aggregate CRUD — that is `hex-persistence` or `hex-store-repository`; the protocol is `hex-domain-ports`.
paths: ["**/infrastructure/**"]
---

# Hex — Capability Adapter (infrastructure)

Produces one adapter class that adapts a domain `ICan<Verb>` capability protocol to a concrete external
system. The adapter does not inherit from the protocol — structural subtyping at the injection site is
the contract — and it is the last place the external library's own exceptions exist: translation happens
here, into the classes `exception-catalog` owns.

## When to use vs. neighbours

- Aggregate-root CRUD over a relational store → `hex-persistence`, not this skill.
- Aggregate-root persistence on a key-value or document store, or an index kept beside it → `hex-store-repository`; an injected SDK client alone does not make something a capability.
- The `ICan<Verb>` protocol file this adapter satisfies → `hex-domain-ports`.
- The obligations the settings class (`<Tech>Settings`) the adapter consumes must meet → `python-settings`; the HTTP gateway's own is shown here, beside it.
- The lifetime and declaration-order rules the adapter's binding follows, and the base composition root it merges into → `hex-wiring`; the binding itself is shown here, beside the adapter.
- The catalogue exception classes the SDK's own errors are translated into → `exception-catalog`.
- The undo a compensating handler calls on this adapter (`delete` beside `upload`) → an ordinary method that raises on failure, declared on a port by `hex-domain-ports`; the handler-side guard that tolerates its failure is `hex-application`'s (Compensation).
- An in-memory test stand-in for this capability (the `Fake<Capability>` flavor) → `hex-test-application-handler`.
- Testing the real adapter — containerized backend, `respx`-intercepted HTTP, or pure CPU → `hex-test-capability-adapter`.
- A token verifier — its port, its adapter and the dependency that resolves it → `hex-restapi-auth`; it is a pure-CPU adapter in this skill's sense, bound there.
- The `infrastructure/<tech>/` folder, the module name and the class name → `hex-conventions` and `naming`.

## Template — httpx, pydantic-settings, dishka

### File layout

```
src/myapp/infrastructure/<adapter>/    # <adapter> = the external tech the adapter speaks
├── __init__.py            # see python-packaging
├── settings.py            # the adapter's settings class — python-settings
└── <tech>_<role>.py       # this skill writes this file
```

`<adapter>` is the external tech the adapter wraps: `http/`, `jwt/`, `<vendor>/`. Infra groups by tech, not by domain concern. For filename and class naming, see `naming`.

### Template — async HTTP gateway (httpx)

In `infrastructure/http/http_foo_classifier.py`: the directory names the technology the adapter speaks —
HTTP — not the `Foo` concern it serves (rule 4), and its settings class sits beside it.

```python
import httpx

from myapp.domain.exceptions import UpstreamError, ValidationError
from myapp.domain.foos import Foo, FooKind

from .settings import FooClassifierSettings

__all__ = ["HttpFooClassifier"]


class HttpFooClassifier:
    def __init__(self, client: httpx.AsyncClient, settings: FooClassifierSettings) -> None:
        self._client = client
        self._base_url = settings.base_url

    async def classify(self, foo: Foo) -> FooKind:
        foo_id = str(foo.id)
        try:
            response = await self._client.post(f"{self._base_url}/classifications", json={"name": foo.name})
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            status = exc.response.status_code
            if status == 400:
                raise ValidationError("foo classifier rejected foo", {"foo_id": foo_id, "status": status}) from exc
            raise UpstreamError("foo classifier failed", {"foo_id": foo_id, "status": status}) from exc
        except httpx.HTTPError as exc:
            raise UpstreamError(
                "foo classifier unreachable", {"foo_id": foo_id, "reason": exc.__class__.__name__}
            ) from exc
        try:
            return FooKind(response.json()["kind"])
        except (KeyError, TypeError, ValueError) as exc:
            raise UpstreamError(
                "foo classifier returned a malformed body", {"foo_id": foo_id, "reason": exc.__class__.__name__}
            ) from exc
```

A `200` is not a result until its body has been read: a body that is not JSON, lacks the field, or
carries a value the domain type rejects raises from the parse, and the parse sits inside a translated
scope of its own so that failure arrives as `UpstreamError` like any other upstream fault (rule 9).

Its settings class, in `infrastructure/http/settings.py` beside it. The adapter reads the base URL; the
composition root reads the timeout when it builds the shared `httpx.AsyncClient` (`hex-wiring`).

```python
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["FooClassifierSettings"]


class FooClassifierSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MYAPP_FOO_CLASSIFIER_",
        env_file=".env",  # only where the project keeps a dotenv file for development
        extra="ignore",
    )

    base_url: str
    timeout_seconds: float
```

**A timeout is a per-integration decision.** It is set from the integration's own observed latency plus
headroom, and bounded above by what the caller can wait for — a request-path adapter whose timeout
exceeds the app's own request timeout can never fire usefully. What the template does fix is that the
timeout is a **settings field**, read once by the composition root and injected — never a constant
hardcoded inside the adapter. It is a tunable with no single right value, so it carries no default
(`python-settings` rule 5).

A pure-CPU adapter over a third-party library — a parser, a renderer, a verifier — has no client to
inject, only settings; it still translates the library's own failure into a catalogue exception and
returns a domain type. Work the standard library can do is domain logic, not an adapter
(`hex-domain-ports`).

### The composition-root binding — dishka

The adapter is an add-on to the base composition root in `hex-wiring`'s `CONTAINER.md`, which binds no
adapter. A project that has one merges its binding into the base: each line into the provider class of
the same name, after the lines already there. It is process-lifetime — an adapter keeps no state across
calls (rule 13).

The HTTP gateway: the settings provider, one shared client closed after its yield — the timeout is read
here, where the client is built — and the adapter bound to its port.

```python
from collections.abc import AsyncIterator

import httpx
from dishka import Provider, Scope, provide

from myapp.domain.foos import ICanClassifyFoos
from myapp.infrastructure.http import FooClassifierSettings, HttpFooClassifier


class SettingsProvider(Provider):
    scope = Scope.APP

    @provide
    def foo_classifier_settings(self) -> FooClassifierSettings:
        return FooClassifierSettings()


class InfrastructureProvider(Provider):
    scope = Scope.APP

    @provide
    async def http_client(self, settings: FooClassifierSettings) -> AsyncIterator[httpx.AsyncClient]:
        async with httpx.AsyncClient(timeout=settings.timeout_seconds) as client:
            yield client

    foo_classifier = provide(HttpFooClassifier, provides=ICanClassifyFoos)
```

## Other bindings

- **An object store.** The bucket is read from settings, the SDK's error codes map to
  `NotFoundError`/`ValidationError` with an `UpstreamError` fallback, and one adapter may satisfy the
  store port and the fetch port together (`AnyOf`).
- **Another vendor SDK for the same capability** — a different mail provider or model API.
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

1. **One adapter class per module**, named for the concrete technology it wraps (`HttpFooClassifier`, not
   `FooClassifier`), so two implementations of one port can coexist. Module structure is
   `python-packaging`'s; the names are `naming`'s.
2. **The adapter does not inherit the protocol it satisfies, and does not import it.** Satisfaction is
   structural and is checked where the adapter is injected; an import of the protocol leaves a dead
   unused import and gains nothing.
3. **Method signatures match the protocol exactly** — parameter names, keyword-only markers and
   async/sync mode included. A near-match satisfies no structural check and fails at the injection site,
   not at the adapter.
4. **The module sits in a directory named for the external technology it wraps** (`http/`, `jwt/`, the
   vendor's own token), never one named for the domain concern it serves. One technology, one directory:
   that is what makes "which of our adapters talk to this vendor" answerable by listing a folder.

### Constructor

5. **The client and the settings arrive by injection, never by construction.** Both are built once by
   the composition root (`hex-wiring`) and handed in; a method that builds its own client
   (`httpx.AsyncClient(...)`, an SDK's own client factory) defeats connection pooling and cannot be replaced in a
   test without patching the library.
6. **Stash the fields the methods use, not the settings object** — unless several methods read several
   fields. The constructor signature is then an honest statement of what the adapter actually depends
   on, and a test can build it without assembling a settings object.
7. **Where the adapter sends a secret, it is unwrapped once, in the adapter's constructor**
   (`settings.api_key.get_secret_value()` under a settings library with a secret type), held on a
   private attribute and never unwrapped again per call — the point of use `python-settings` rule 9
   names. A secret never reaches a log line (`python-logging`) and never reaches an exception's `context`
   (rule 10), because `context` is rendered into the error response and logged verbatim.

### Exception translation

8. **Translate at the boundary, chaining the cause.** Catch the library's own exception family inside the
   adapter and raise a catalogue exception `from` it. The catalogue and the cause-chaining rule are
   `exception-catalog`'s.
9. **The library's exception type never escapes the adapter, and neither does a bare `Exception`.** No
   SDK error, HTTP status error or parse error crosses into `application/` or an entrypoint — the
   application layer catches only `MyappError`. Where the request does not say which external errors a
   method raises, derive the mapping from the library's documented exception family: the specific cases
   are judgement, the broad catch-and-translate fallback (rule 10) is not — no method is left able to
   raise an untranslated external exception.
10. **The fallback, the most specific class, the identifying `context` and the no-secret ban are
    `exception-catalog`'s rules**, applied here without change. What they come to in an adapter: the
    fallback is `UpstreamError` for a network or third-party failure (5xx, unknown codes), and that
    includes the upstream rejecting the adapter's **own** configured credential (an upstream 401 or 403,
    or the SDK's own rejected-credential code) — the caller's request was sound, and a 401 would
    challenge the caller to re-authenticate over a fault only the service's operator can fix;
    `UnauthorizedError` only where the adapter verifies a credential the caller presented (a token
    verifier, `hex-restapi-auth`); `NotFoundError` when the object or subject does not exist; `ValidationError` only when the upstream rejected the inputs as malformed; `context` carries
    the key, subject or id plus the upstream's own code or status, and never the token or key. An adapter
    never swallows a failure, and never stops one either — a failed undo during compensation is stopped
    in the calling handler (`hex-application`, Compensation), which logs it; an adapter cannot.

### No business logic, no logging

11. **Adapters are thin.** No retries, no caching, no batching, no domain reasoning. Retry and backoff
    belong to the client's own policy (configured where the client is built) or to a dedicated wrapper
    class, so that the adapter stays one call wide and its failure modes stay readable.
12. **An adapter never logs.** Not the call, not the failure: the central error handler owns failure logs
    and the calling handler owns success logs, so a line here is a second entry for one event.
13. **No instance state across calls** beyond constructor-injected handles. An adapter is then safe to
    bind at process lifetime and share across concurrent requests.

### Compensating-transaction contract

14. **Mutating capabilities expose both the forward operation and the undo.** A storage adapter has `upload` *and* `delete`; a publisher that supports retraction has `publish` *and* `retract`. The catch-and-undo logic lives in the application handler (`hex-application`, Compensation), not in the adapter. The adapter's job is to make the undo callable; like every other method it raises a catalogue exception when it fails, and the handler decides whether that failure may be tolerated.

## Inlined typing / import rules

- Domain imports absolute (`from myapp.domain.foos import Foo, FooKind` — the domain types the signatures name). **Never import the capability protocol the adapter satisfies** (`ICanStoreFoos`, `ICanClassifyFoos`, …) — structural subtyping needs no import (Rule 2); importing it is a dead F401. Sibling modules within the same `infrastructure/<adapter>/` package use relative imports (`from .settings import FooClassifierSettings`).
- No `from __future__ import annotations`. Full annotations on every method.
- `X | None` over `Optional`. `Mapping[K, V]` / `Sequence[T]` (from `collections.abc`) for read-only views.
- **A raw SDK value typed `Any` is narrowed with `cast`, never silenced.** An SDK return that mypy sees as `Any` (an untyped client method, a body read the SDK does not type) flowing into a typed protocol return is a `[no-any-return]`/`[return-value]` error — fix it with `cast(<protocol-return-type>, …)` at the boundary, the same way a route dependency casts a container-resolved value (`hex-restapi-auth`). An adapter can always restate the vendor type, so an inline ignore never meets `python-style`'s last-resort test here.
- SDK types stay inside the adapter; method signatures use domain types or primitives only.
- No `Any` except at the immediate raw-SDK-payload boundary (e.g. `payload: dict[str, Any] = response.json()` — convert to the domain type on the next line).

## Package wiring

For package wiring, see `python-packaging`; for infrastructure placement, see `hex-architecture`.

## Hard stops

- The adapter is asked to carry relational aggregate CRUD — a table, the statements against it and the
  migration that ships it → stop, that is a repository and not a capability; use `hex-persistence`, or
  `hex-store-repository` for an aggregate held in a key-value or document store.
