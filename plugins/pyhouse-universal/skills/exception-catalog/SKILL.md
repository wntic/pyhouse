---
name: exception-catalog
description: Use when adding an error class or reusing one, translating an SDK or library exception at a boundary, or asking what status code an error maps to. Owns the single catalog file, its root and bare subclasses, the stable codes, the inherited `context` dict, translation with `from exc`, the ban on swallowing a failure, and best-effort compensation as the one case a scope that re-raises stops a second failure. Where the error is logged is `python-style`.
---

# Exception Catalog

Every project in this style has **exactly one file** where its own exceptions are defined. It holds a
root error plus one bare subclass per named error, so the catalog stays auditable in a single read and
nothing raises a type that was invented at the call site.

Where that file sits is the only thing that varies, and one obligation settles it for any project
shape: **one catalog module, at a place every part of the codebase may import from without creating a
cycle, named for what it holds.** The catalog imports nothing of the project's own, so anything may
import it; put it wherever the project's own import direction makes that true. It is a module,
`exceptions.py` — never `exceptions/__init__.py`, because an `__init__.py` holds only imports and
`__all__` (`python-packaging`); `from myapp.exceptions import …` reads the same either way. The root
class is named for the project, and every other class in the file descends from it.

Two worked cases, one per architecture family this catalogue covers:

| Architecture | Catalog file | Root class |
|---|---|---|
| Hexagonal (`hex-architecture`) | `<package>/domain/exceptions.py` | `DomainError` |
| Flat-layered (`flat-layered`) | `<package>/exceptions.py` | `<Service>Error` |

A project in neither family reads the obligation rather than the table, and it answers as easily: a
framework-shaped tree puts the module where every one of the framework's units already imports from,
a distributable package puts it at its own root because the classes its callers catch are part of the
published surface, and a command-line tool puts it above the command modules that raise from it. One
file either way — the reason for a single file is that the catalog stays auditable in one read, and
that reason is not architectural.

The **shape** below is identical in every case, and **`code` is the only required field**.
Everything else is a transport annotation, added when a transport actually reads it and omitted when
none does. `http_status` is the one this catalogue writes out, because an HTTP entrypoint has a central
handler that translates it into a response — but **the trigger is the HTTP surface, not the architecture
family.** A hexagonal service driven only by a CLI, a worker loop or a queue consumer carries the `code`
alone, exactly as a flat-layered worker does; a flat-layered service that does serve HTTP adds
`http_status` exactly as a hexagonal one would.

Where an annotation is warranted it is a deliberate **transport annotation on a domain class**, not a
leak — kept on the class precisely so that no `code`→annotation map exists anywhere. Deriving the value
from the class it belongs to is what keeps this catalogue free of a hand-maintained table that every new
error has to be remembered into; a project whose transport reads nothing omits the attribute instead. A
non-HTTP transport annotates by the same rule under its own name — a process exit code, a gRPC status —
or, far more often, needs nothing and leaves `code` to do the work.

## When to use vs. neighbours

- A new named error is needed to express a rule violation → this skill. **First confirm no existing class
  already serves the rule** — scan `__all__` for a semantic match and read the candidate's body; if one
  fits, reuse it rather than minting a near-duplicate.
- Translating a database `IntegrityError` at a repository boundary → `hex-persistence`, in the
  `pyhouse-hex` plugin, which references this skill for the target class name.
- Translating an HTTP or SDK error inside a client class → `flat-layered`, in the `pyhouse-flat`
  plugin, same relationship.
- Advertising an error's `code` on a REST route → `hex-restapi-endpoint`, in the
  `pyhouse-hex` plugin, which references the new `code`.
- Where the error is logged and by whom → `python-style`.
- Whether an undo step's own failure may be stopped while another failure propagates → this skill,
  **Swallowing, stopping, and best-effort compensation**; the handler shape that runs the undo is the
  architecture family's (`hex-patterns`, in the `pyhouse-hex` plugin, is one).
- Why this one file is exempt from one-class-per-module → `python-packaging`.
- What the error class itself should be called → `naming`.
- Rendering a caught error as an HTTP response body, and the central handler that does it → `hex-restapi-app`, in the `pyhouse-hex` plugin; this skill owns the class, its `code` and its status, not the rendering.

## File shape (the contract every entry obeys)

- `__all__` **after the imports**, alphabetized — `python-packaging` owns module layout and forbids
  `__all__` above the imports. This file is stdlib-only and has no imports, so it opens the file;
  that is the same rule, not an exception to it.
- The **root** defines `code: str` — and `http_status: int` where the project has an HTTP surface — with
  type annotations and defaults, plus the `__init__` accepting `(message, context=None)` and storing
  `self.context`.
- Every subclass declares its attributes as **bare class attributes**, no type annotation; the type is
  inherited from the root's annotation.
- **No subclass overrides `__init__`.** Every subclass automatically accepts `(message, context=None)`.
- A subclass may inherit from another subclass when it is a genuine refinement, in which case it inherits
  the parent's values unless it overrides them.
- Order: `__all__`, then the root, then direct subclasses, then refinements.

## Template — a flat-layered service catalog

This is also the form to copy when the project is in neither family — the `code`-only catalog, with a
transport annotation added below only if something in the project actually reads one.

```python
# myapp/exceptions.py
__all__ = [
    "FooClientError",
    "MyappError",
    "UpstreamUnavailableError",
    "ValidationError",
]


class MyappError(Exception):
    code: str = "MYAPP_ERROR"

    def __init__(self, message: str, context: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.context: dict[str, object] = context if context is not None else {}


class FooClientError(MyappError):
    code = "FOO_CLIENT_ERROR"


class ValidationError(MyappError):
    code = "VALIDATION_ERROR"


class UpstreamUnavailableError(FooClientError):
    code = "UPSTREAM_UNAVAILABLE"
```

## Template — a hexagonal catalog

Identical, plus `http_status` — shown here because this family most often fronts an HTTP API, and read
by the central error handler. **A hexagonal service with no HTTP surface — a CLI, a worker loop, a queue
consumer — drops the attribute and is otherwise unchanged.**

```python
# myapp/domain/exceptions.py
__all__ = [
    "ConflictError",
    "DomainError",
    "ForbiddenError",
    "InUseError",
    "NotFoundError",
    "UnauthorizedError",
    "UpstreamError",
    "ValidationError",
]


class DomainError(Exception):
    code: str = "DOMAIN_ERROR"
    http_status: int = 500

    def __init__(self, message: str, context: dict[str, object] | None = None) -> None:
        super().__init__(message)
        self.context: dict[str, object] = context if context is not None else {}


class NotFoundError(DomainError):
    code = "NOT_FOUND"
    http_status = 404


class ConflictError(DomainError):
    code = "CONFLICT"
    http_status = 409


class ValidationError(DomainError):
    code = "VALIDATION_ERROR"
    http_status = 422


class UnauthorizedError(DomainError):
    code = "UNAUTHORIZED"
    http_status = 401


class ForbiddenError(DomainError):
    code = "FORBIDDEN"
    http_status = 403


class UpstreamError(DomainError):
    # A dependency the service calls failed — not the caller's request. 502, never 500:
    # 500 says this service is broken, 502 says the thing behind it is.
    code = "UPSTREAM_ERROR"
    http_status = 502


class InUseError(ConflictError):
    code = "IN_USE"
    # http_status omitted — it equals the parent's 409
```

That is the entire class body of each entry. No `__init__`, no fields, no methods.

### A custom subclass and its raise site

Each named error is a bare subclass of `DomainError` — or of the most specific existing parent, when one
is a semantic match (a refinement inherits `http_status` unless it differs):

```python
class FooConflictError(ConflictError):
    code = "FOO_NAME_TAKEN"
```

Custom exceptions still carry `context`. The raise site (in `infrastructure/` or `application/`) passes a `context` dict whose keys express the structured detail:

```python
raise FooConflictError(
    "foo name already exists",
    {"name": foo.name},
)
```

### What `context` carries

`context` is not a free-form debug bag. It carries the **stable identifying inputs of the failed
operation** — the id, key or field the operation was about — plus the upstream code or status where the
failure came from one, and nothing else. Two readers depend on that set: the test at the raise site
asserts on the keys, and the layer that logs the error renders them as its fields, so a key that churns
breaks a test and a dashboard at once.

Three consequences:

- **The raise site and its test agree on one key set**, and that set is as stable as the `code` beside
  it. Renaming a key is the same class of change as renaming the `code`.
- **A key names the input, not the failure.** `{"field": "name", "constraint": "uq_foos_name"}` —
  not `{"detail": "..."}`, `{"msg": "..."}` or a stringified exception.
- **No secret goes in `context`.** A password, token, key or connection string placed there reaches the
  log line and, where the project renders errors, the response body — by construction, because both
  render `context` verbatim. This is the same ban `python-style` states for a log line, and `context` is
  the path around it.

The skill does not enumerate the keys for each class; it fixes what kind of key belongs there and that
the set does not drift.

## Translation at the boundary

A library or SDK exception must not escape the module that called the library. The boundary catches it,
raises the catalog's own type, and **chains the cause**:

```python
try:
    response = await http.get(url)
    response.raise_for_status()
except httpx.HTTPError as exc:
    raise FooClientError(f"failed to fetch foo {foo_id}", {"foo_id": foo_id}) from exc
```

`from exc` is not optional. It preserves `__cause__`, which is what a test asserts to prove the
translation happened rather than the error being manufactured, and what a reader needs to see the real
failure. Suppress it deliberately with `from None` only when the internal cause must not leak — for
instance turning a lookup miss into an authentication failure.

Structured detail rides in `context`, not in new fields, under the key contract above:

```python
raise ConflictError("foo name already exists", {"field": "name", "constraint": "uq_foos_name"})
```

### The fallback is mandatory

A translation that recognises some failures must still answer for the ones it does not. When no case
matches, the boundary **still raises a catalogue class** — the generic upstream or client error, chosen
by what the failure is rather than by what was matched:

```python
except FooSdkError as exc:
    if exc.status == 404:
        raise NotFoundError("foo not found", {"foo_id": str(foo_id)}) from exc
    raise UpstreamError("foo service failed", {"foo_id": str(foo_id), "status": exc.status}) from exc
```

Never return the raw exception, never re-raise it unchanged, and never swallow it with `pass` or a bare
`return None`. An untranslated leak is the failure this whole skill exists to prevent, and it is worse
than the original error: a third-party type crossing a layer defeats every `except` clause written
against the catalogue, so a recognisable conflict is rendered as an unexplained crash and a swallowed
one becomes a silent wrong answer.

### Swallowing, stopping, and best-effort compensation

**To swallow a failure is to catch it and neither re-raise it nor log it as the scope that stops it.**
A swallowed failure leaves no trace: nothing above sees it and nothing records it, so the operation
reads as a success it was not. It is never done. **Stopping a failure is different and legitimate** —
the scope that catches it, logs it once under `python-style`'s allocation and carries on (a loop
containing one failed run and moving to the next) is the scope every failure is traced to, and it is
exactly where the log line belongs.

**Best-effort compensation is the one case where a scope that re-raises also stops a failure.** A scope
that has already caused an externally visible effect — an object uploaded, a message published, a
reservation taken — and then fails on a later step undoes the effect before letting the failure go. The
undo runs **while that failure is already propagating**, and it can fail too. Letting the undo's error
escape would replace the fault that actually happened with a report about the cleanup, so **the undo's
own failure is stopped in the scope that re-raises the original, on three conditions, all required.**

1. **It is stopped only by the scope that caught the original failure and will re-raise it** — the
   only scope that knows a failure is propagating. The undo it calls raises like any other call; a
   method that drops its own failure in case some caller is compensating hides it from every caller
   that is not.
2. **That scope logs one `warning` event naming the failed undo**, with the undo's identifying inputs as
   fields and the undo's error attached. It is the only record that an effect outlived the operation
   that made it; `python-style`'s `LOGGING.md` places the call.
3. **The original failure is re-raised unchanged**, and only the undo call sits inside the inner
   `try` — never the original operation, and never a bare `except: pass`.

```python
try:
    await self._foos.add(foo)
except Exception:
    try:
        await self._blobs.delete(blob_key)
    except Exception as undo_exc:
        log.warning("foo_blob_undo_failed", blob_key=blob_key, exc_info=undo_exc)
    raise
```

The bare `raise` re-raises the original: the inner handler has finished, so the failure being handled
is the outer one again. Everywhere else a scope that re-raises logs nothing, and a failure it
catches is either re-raised, translated, or stopped and logged by the scope that stops it — never
dropped. A translation's unmatched branch raises; it does not get to stop anything.

## Rules

1. **Never define an exception outside the catalog file.** Not beside the code that raises it, not in a
   client module, not in a test helper. New classes are added to the catalog or not at all.
2. **Never inherit from bare `Exception` or a stdlib exception** except for the root itself. Everything
   else inherits from the root or one of its subclasses.
3. **`code` is a stable contract.** Once shipped, never rename or reassign one — clients, dashboards and
   alerts key on it. If the meaning changes, add a new class with a new code and deprecate the old one
   separately.
4. **Subclasses do not override `__init__`.** Structured detail goes through the inherited `context` dict
   at the raise site.
5. **Subclass attributes use bare assignment.** `code = "X"`, not `code: str = "X"`.
6. **An inherited value is not restated.** Set `http_status` only when it differs from the parent's.
7. **`code` values are `SCREAMING_SNAKE_CASE`**, and every one is unique across the catalog.
8. **Every library exception is translated at its boundary, with `from exc`.** A third-party type
   reaching a caller is a leak.
9. **Prefer the most specific existing class.** A refinement beats its parent; a near-duplicate of an
   existing class is a reuse, not a new entry.
10. **The fallback is mandatory.** A translation that matches some failures still raises a catalogue
    class for the ones it does not — never the raw exception returned or re-raised, never a `pass`. A
    partial translation is an untranslated leak with extra steps.
11. **`context` carries the operation's stable identifying inputs**, plus the upstream code or status
    where there is one. The raise site and its test agree on that key set and it does not churn, because
    the test asserts on it and the layer that logs the error renders it as fields.
12. **No secret in `context`.** A token, key, password or connection string placed there reaches the log
    line, and the response body where the project renders one, by construction — both render `context`
    verbatim. `python-style` bans the same values from a log line; this is the path around it.
13. **A caught error is rendered in exactly one place, off the exception's own attributes.** Whatever
    the project shows the outside world — a response body, a message on stderr and an exit code, a
    failure record — one scope produces it, and it produces it by reading `code`, `str(exc)` and
    `context` from the class rather than by mapping a class onto a rendering. That is what keeps a
    hand-maintained `code`→rendering table from reappearing: a new class renders correctly the day it
    is added, with no second edit. Where the entrypoint serves HTTP, that scope is the central handler,
    its response status is `exc.http_status`, and the `ErrorResponse` body carries `code=exc.code`,
    `message=str(exc)` and `context=exc.context` — the custom raise above renders HTTP 409 with
    `{"code": "FOO_NAME_TAKEN", "message": "foo name already exists", "context": {"name": foo.name}}`.
    A project whose only caller is its own importer — a distributed package — renders nothing and lets
    the class reach that caller intact, which is the same rule with the rendering scope outside the
    project. The rule is complete here; the hexagonal family's handler and response-schema templates
    that implement it are in `hex-restapi-app`, in the `pyhouse-hex` plugin.
14. **One class for every credential rejection, and a second for the distinct permission case.** A bad,
    missing, expired or unverifiable credential raises `UnauthorizedError`, wherever the verification
    happens; a caller who is known and is not permitted raises `ForbiddenError`. Do not mint a second,
    parallel class for the credential case under any name — everything the project does with that
    condition is written once against one class, and a second spelling silently skips all of it. The
    HTTP binding is the visible instance of that cost, not its reason: a central handler's RFC-7235
    `WWW-Authenticate` branch keys on `UnauthorizedError` alone, so a parallel class renders as a plain
    failure with no challenge. **Both classes are conditional on the project verifying a credential at
    all** — one that verifies nobody, because something in front of it did or because it has no caller
    to authenticate, omits them from the catalog entirely, the same way a project with no HTTP surface
    omits `http_status` (see the hard stop below). The hexagonal family's binding for an entrypoint
    that verifies credentials itself is `hex-restapi-auth`, in the `pyhouse-hex` plugin.
15. **The two roots name their upstream failure differently, deliberately.** Hexagonal has
    `UpstreamError`, a direct child of `DomainError`: any dependency failure, rendered `502`. Flat-layered
    has `UpstreamUnavailableError`, a refinement of the *client* class for one upstream — and in the
    worker case that family usually serves, no `http_status`, because nothing renders it. They are not two spellings of one class and neither
    renames to the other; a project has one root and therefore only ever meets one of them.
16. **A failure is never swallowed** — caught and neither re-raised nor logged by the scope that
    stops it. A swallowed failure reads as a success; a failure stopped and logged once by the scope
    that handles it is not swallowed. **Best-effort compensation is the one case where a scope that
    re-raises also stops a failure:** while a failure is already propagating, an undo step's own failure
    is stopped by the scope that caught the original — that scope logs one `warning` event naming the
    failed undo and its identifying inputs, then re-raises the original failure unchanged. The undo's
    error must not replace the fault that happened, and the warning is the only trace that an effect
    was left behind. Never a bare `except: pass`.

## Inlined typing / import rules

- Stdlib-only in the catalog — no third-party imports. No `from __future__ import annotations`.
- The root's class attributes carry annotations; subclasses do not re-annotate.
- The root's `__init__` is fully annotated, including `-> None`.
- `context` is `dict[str, object]`, not `dict[str, Any]` — `object` forces narrowing at the point of
  consumption (`python-style`).

## Hard stops

- A new exception type is being defined outside the catalog file → stop, add it there first.
- A second catalog is being added because some package cannot import the first one → stop, the catalog
  is placed where every part of the codebase may import it; move the one file rather than splitting it.
- The catalog's classes are being written into an `exceptions/__init__.py` → stop, make it the module
  `exceptions.py`; an `__init__.py` holds only imports and `__all__`.
- A subclass is being given an `__init__` override or extra fields → stop, use the inherited `context`.
- A library exception is re-raised without `from exc` → stop, the cause is lost and the translation
  becomes unprovable.
- A library or SDK exception type escapes the module that called the library → stop, translate it.
- A translation's unmatched branch returns the raw exception, re-raises it unchanged, or swallows it with
  `pass` → stop, the fallback raises a catalogue class; a partial translation still leaks.
- A failure caught and dropped — `pass`, a bare `return`, a default value — with no re-raise and no log
  line from the scope that stops it → stop; that is a swallow, and it reads as a success. Re-raise it,
  translate it, or stop it and log it once.
- A scope that re-raises the original also logging a failure other than a failed undo under
  best-effort compensation → stop; a re-raising scope stays silent, and the undo is the one exception.
- A method drops its own failure because a caller might be compensating (a `*_best_effort` variant
  that catches internally) → stop, let it raise; the undo's failure is stopped by the scope that
  caught the original failure, the only one that knows a failure is propagating.
- An undo's failure is raised in place of the original, or the original is lost behind it → stop,
  stop the undo's failure under best-effort compensation and re-raise the original.
- A `context` key invented at the raise site that no test asserts on, or a key renamed on a shipped
  class → stop, the key set is a contract between the raise site, its test and the log line.
- A password, token, API key or connection string being put in `context` → stop, it is rendered verbatim
  into the log line and the error response.
- A shipped `code` is being changed → stop, that breaks every client keyed on it; add a new class.
- The new class would duplicate an existing one's semantics → stop and reuse the existing one.
- The error is being logged at the raise site *and* re-raised → stop, one entry per event
  (`python-style`).
- `http_status` is being added to a project with no HTTP surface → stop, nothing reads it; the `code`
  is the contract.
