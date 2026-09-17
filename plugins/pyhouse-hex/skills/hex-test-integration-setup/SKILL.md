---
name: hex-test-integration-setup
description: Use when laying or changing the `tests/integration/conftest.py` hierarchy one hexagonal package's suite rests on — session-scoped testcontainers, the Alembic run and the disposable-database guard, savepoint-rollback isolation through the `sf` session factory, and `real_app` on a dishka composition root whose infrastructure providers are overridden. Owns the Postgres container fixture; testing a repository against it is `hex-test-repository-contract`. Not a flat-layered service's own `tests/integration/conftest.py`, or the plugin module several workspace members share instead — that is `flat-test-integration-setup`, in the `pyhouse-flat` plugin.
---

# Hex Test — Integration Setup

Consult `test-principles` for the testing constitution. Where this skill contradicts `test-principles`, the constitution wins.

One-shot per project, and everything else in the integration suite depends on it. **This is the relational-store isolation strategy.**

## When to use vs. neighbours

- Laying either conftest for the first time, or changing a fixture in one → this skill.
- A repository contract test → `hex-test-repository-contract` (consumes `sf`).
- An API endpoint test → `hex-test-restapi-endpoint` (consumes `sf` and `real_app`).
- The cross-cutting OpenAPI / CORS / request-size invariants → `hex-test-discovery-invariants` (consumes `real_app` directly).
- A handler test that runs on in-memory fakes and needs no database at all → `hex-test-application-handler`; none of these fixtures apply to it.
- A capability adapter's own assertions — the respx gateway, the SDK-error translation, the pure-CPU case → `hex-test-capability-adapter`. The session-scoped container its backend needs is still declared here.
- The signing-key and token-minting fixtures, the authenticated client, and the `jwt_settings` override `real_app` grows in an auth app → `hex-test-restapi-auth`. Only for an app that declares auth; this skill is complete without it.
- The route-side auth dependencies themselves → `hex-restapi-auth`.
- Per-resource row factories (`make_foo`, `foo_id`, …) → not this skill; they live in `tests/integration/api/<resource>/conftest.py` next to the tests that use them.
- Which scope a fixture takes, which conftest level it belongs at, builders versus fixtures → `test-principles`, the constitution. This skill is the hexagonal artifact that implements it.
- The same fixtures for a flat-layered service — one service's own conftest, or one plugin module shared by many workspace members → `flat-test-integration-setup`, in the `pyhouse-flat` plugin.
- The composition root has no `session_factory` binding, or no way to pass extra providers into it → `hex-wiring` first; the substitution seam is `create_container`'s parameter, not something a test can bolt on.
- The grep that enforces "`sf` is the only sessionmaker under `tests/integration/`" → `test-architecture-rule`.

## Template(s) — pytest, testcontainers, dishka

```
tests/
├── conftest.py                       # empty; pytest-asyncio config belongs in pyproject.toml
└── integration/
    ├── conftest.py                   # containers, guard, migration run, engine, `sf`, `real_app`
    └── api/
        ├── conftest.py               # empty unless the app declares auth
        └── <resource>/conftest.py    # per-resource row factories — not this skill's
```

**Read the sibling `CONFTEST.md` before writing or changing any fixture in that hierarchy.** Only this
file is loaded automatically, so open it rather than reconstructing the fixtures from the obligations
below: it carries the full `tests/integration/conftest.py`, the top-level and api sub-templates with the
import rule the root conftest must obey, and the eleven numbered spellings of the obligations under this
binding — the one sanctioned sessionmaker, the savepoint mode, the session/function scope split, and the
disposability marker the container fixture is entitled to set.

## Other bindings

### Provisioning — where the store under test comes from

The obligations below hold under every one of these; what changes is who creates the store, how the
schema gets there, and what the disposability marker is set by.

- **A developer- or CI-supplied store.** The suite starts nothing: connection details come from a
  **dedicated** opt-in variable, and whatever provisioned the store sets the disposability marker. The
  container fixtures go; the guard, the schema step, the isolation handle and the substitution are
  unchanged — and the guard matters *more* here, the one branch that can reach a store the suite did
  not create. The template's external branch is this binding, written in.
- **An in-process store.** An embedded engine — a file-backed or in-memory relational database, an
  embedded key-value store — inside the test process. No container and no opt-in variable; it is
  disposable by construction, so the fixture that creates it sets the marker, and the schema step runs
  in-process rather than as a subprocess. The isolation obligation is unchanged, its mechanism may not
  be: an engine without nested transactions isolates by a fresh store per test rather than by undo.
- **A fresh schema (or database) per session on a shared server.** The session creates a uniquely-named
  schema inside a long-lived server and drops it at session end. That creation is what makes the target
  disposable, so it sets the marker; the schema step targets the new namespace and the per-test handle
  sits inside it unchanged. Reach for this where a container is not available to the suite but a server
  is.

### Dependency injection

- **`dependency-injector`.** The container fixtures, the migration run, the guard and the savepoint-rollback `sf` are unchanged; only `real_app` differs, and it differs in kind rather than in spelling. There is no `TestInfraProvider`: the fixture builds the real container, calls `.override(value)` on each provider **after** construction, and must `.reset_override()` each one in the `finally` block. Because the substitution lands on a live container, an already-resolved singleton may have captured the pre-override value — the classic case is a singleton whose `__init__` snapshots a settings field — so the fixture set grows an autouse teardown that calls `.reset()` on every such capturing singleton, and `containers.py` has to be audited once to find them. That failure mode does not exist under the primary binding, where the graph is assembled with the test factories already in it.
- **Manual composition.** The composition root is a factory function, so the fixture calls it with the test objects as arguments. No provider classes, no override marking, and teardown is whatever `AsyncExitStack` the factory returned.

## Rules

Consult `test-principles` for the testing constitution.

### Scope

- **`tests/integration/conftest.py`** — the containers, the engine, and the transaction-rollback `sf`.
  The contract: every integration test starts with an empty database, and rows the test (and its handler)
  commit are rolled back at teardown.
- **`tests/integration/api/conftest.py`** — created here, empty by default. Its only current occupant is
  the auth fixture set, which is `hex-test-restapi-auth`'s and exists only for an app that declares auth.

**This is the relational-store isolation strategy.** The engine, the Alembic migration run, and the savepoint-rollback `sf` all assume a relational store — the per-test transaction that ROLLBACKs is a SQL-database mechanism. An app whose only datastore is client-style (qdrant / redis / …) has no engine, no migration chain, and cannot use savepoint rollback; it isolates by **per-test namespace + best-effort cleanup** instead (the `s3_prefix` block in `CONFTEST.md` is exactly that pattern). Lay the Postgres machinery only when the app has a relational store.

**What this skill owns, exactly: every session-scoped fixture, for every store kind.** Containers,
engines, migration runs and long-lived clients belong here because one container per session is the
guarantee the whole setup rests on, and a fixture duplicated into a store-kind conftest breaks it. The
**per-test** half — a fresh collection, key-prefix, database or bucket path, and its teardown — belongs
in the sibling `tests/integration/<store-kind>/conftest.py`, next to the tests that consume it
(`hex-test-repository-contract`). `s3_prefix` in `CONFTEST.md` is the per-test half shown there only
because blob storage has no store-kind conftest of its own in this template.

- Per-resource row factories (`make_foo`, `make_bar`, …) → not this skill; declare them in `tests/integration/api/<resource>/conftest.py` next to the tests that use them.
- Cross-cutting "OpenAPI codes match `error_responses(...)`" / CORS / request-size invariants → `hex-test-discovery-invariants`; the every-protected-route-rejects-an-anonymous-caller probe → `hex-test-restapi-auth`.

### `real_app` is usable only from `tests/integration/api/`

In an app that declares auth, `real_app` consumes a settings fixture defined **down-tree**, in
`tests/integration/api/conftest.py`. Pytest resolves fixture names by walking the conftest hierarchy from
the running test outward, so that only works for tests under `tests/integration/api/`. That is fine —
repository contract tests use `sf` directly and never construct the FastAPI app. The mechanism, and the
override that depends on it, are `hex-test-restapi-auth`'s.

### The obligations

Stated without a mechanism, because both halves of this file vary: provisioning varies by binding
(above) and isolation varies by what the store can undo. Every binding of this file delivers these.

1. **Each test starts against an empty store and leaves nothing behind.** The undo is automatic — a
   property of the handle the test was given, not a teardown someone remembers to write — and it
   covers writes the *subject* made, not only the test's own.
2. **One sanctioned handle, and nothing reaches the store around it.** Every test, fixture and
   substituted infrastructure binding goes through the handle this file provides. A handle a test
   opens for itself writes outside the isolation boundary, so its rows survive into the next test and
   the failure surfaces somewhere else entirely.
3. **The expensive resource is per session; the isolated unit is per test.** Starting the store,
   establishing the schema and building the pool happen once per run; what each test owns alone is the
   cheap thing — a transaction, a namespace, a schema. Reversing either end is a defect: a per-test
   store costs seconds a test, a per-session isolated unit serialises the suite.
4. **The suite refuses to run against a store nothing declared disposable.** This suite rewrites
   schema and wipes rows, so disposability is **declared** by whatever provisioned the store — never
   deduced from a port number, a substring of the name or any other property of the connection, because
   the deduction is wrong in exactly the case that matters.
5. **The schema the tests assume is established once, by the project's own schema path.** The suite
   does not hand-build tables; it runs the same migration or schema-creation path production runs, so a
   schema change that was never migrated reds here rather than in production.
6. **Substitution happens before the composition root is built, never after.** The test's
   infrastructure objects are in the graph from the start, so nothing production-side can have resolved
   and captured a pre-substitution value, and there is no reset or teardown ordering to get right.
7. **A substituted binding is the fixture object itself, under the exact type the production binding
   declares.** No wrapper, no adapter — the type is what binds it.
8. **Whatever the composition root opened, the fixture closes.** One close call in the fixture's
   `finally`, releasing the test's resources in reverse order.
9. **A store with no undo isolates by namespace instead.** Where nothing can be rolled back — a blob
   store, most client-style stores — each test owns a freshly-named namespace and asserts only inside
   it; cleanup is best-effort at session end, so a test that asserts on global contents is asserting on
   other tests.
10. **The isolation guarantee is what licenses strong assertions.** Because the store is empty at test
    start, fixed natural keys need no unique suffix and exact counts are correct — no defensive
    `any(...)` filters, no `+1` for the test's own row.
### The authenticated client

- **An authenticated client is not this skill's.** The single sanctioned authenticated client, the
  signing keypair, the token-minting helper and their rules → `hex-test-restapi-auth`. A raw
  `AsyncClient` over `real_app` is sanctioned here only for an app with no auth, and for the
  unauthenticated probes in `hex-test-discovery-invariants` / `hex-test-restapi-auth`.
- **No `localhost` / `127.0.0.1` base URL.** `http://testserver` is the convention; the ASGI transport
  short-circuits the network anyway, but `testserver` makes route logs distinguishable from real
  traffic in CI logs.

## Inlined typing / import rules

- `pytest`, `dishka`, `sqlalchemy.ext.asyncio`, `subprocess`, `os`, `sys`, stdlib `collections.abc` — and the project's `infrastructure.postgres.*` + `infrastructure.s3.*`.
- `create_container` and `create_app` are imported **inside** the `real_app` fixture body, never at module level (see the root-conftest note in `CONFTEST.md`).
- Full annotations on every fixture signature. `AsyncIterator[T]` for yielding fixtures with cleanup.
- No `from __future__ import annotations`.

## Hard stops

- The composition root has no `session_factory` binding, or no way to pass extra providers into it → stop, use `hex-wiring` first; the substitution seam is `create_container`'s parameter, not something a test can bolt on.
- Spec asks to substitute a binding on a composition root that is already built — an `.override()`-style call inside a test → stop, build a second composition root with a substituting provider instead.
- Spec asks to keep `function`-scoped engine (one engine per test) → stop, that's the old slow model; engine is session-scoped, only the connection is function-scoped.
- Spec asks to drop `join_transaction_mode="create_savepoint"` → stop, that flag is the whole point — without it the handler's commits either escape or fail.
- Spec asks for session-scoped row fixtures (`make_foo` returning the same id across tests) → stop, rows are per-test; factories return fresh rows per call.
- Spec asks the `sf` fixture to bind to the engine directly (skipping the outer connection) → stop, that bypasses rollback and reintroduces every old failure mode.
- Spec infers "this must be a test database" from the port number, a `test` substring in the database name, or any other property of the DSN → stop, the guard takes an explicit marker set by whatever provisioned the database; a deduction passes for a real database that happens to match and the suite then migrates over it.
- Spec asks to add a `truncate_all_tables` teardown alongside rollback → stop, rollback alone is sufficient; truncate is the fallback for DBs without nested transactions and is strictly slower.
- Project does not use S3 / MinIO but spec includes the bucket fixtures → stop, strip the storage block; no need to start MinIO every session.
- The app has no relational store — a qdrant/redis-only app, say → stop, omit the Postgres engine / Alembic / savepoint-`sf` machinery; there is no SQL transaction to roll back. Isolate the client stores by per-test namespace + session-end cleanup (the `s3_prefix` pattern), not by this fixture.
- The app has no auth (every endpoint anonymous) but `real_app` carries a verifier-settings substitution → stop, strip the fixture parameter and the factory in `TestInfraProvider`. An auth-less app binds no verifier settings, so a factory claiming to override one fails when the graph is assembled; whether an app has auth follows from its routes (`hex-restapi-auth`), it is not a universal.
- Spec puts a token-minting fixture, a signing keypair or an authenticated client in either conftest this skill owns → stop, use `hex-test-restapi-auth`; they belong to the auth-only fixture set.
- Spec adds a per-resource row factory inside this conftest → stop, those live in `tests/integration/api/<resource>/conftest.py`.
