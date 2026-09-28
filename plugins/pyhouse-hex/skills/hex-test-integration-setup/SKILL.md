---
name: hex-test-integration-setup
description: Use when laying or changing the `tests/integration/conftest.py` hierarchy one hexagonal package's suite rests on — session-scoped testcontainers, the Alembic run and the disposable-database guard, savepoint-rollback isolation through the `sf` session factory, each store add-on's fixtures (the key-value store is the worked one), the per-test dishka composition root whose infrastructure providers are overridden, and `real_app` over it where the service has a REST entrypoint — or the same fixtures as one plugin module several hexagonal workspace members share. Maps the whole suite tree and names the skill that writes each file in it. Owns the Postgres container fixture; testing a repository against it is `hex-test-repository-contract`. Not a flat-layered service's fixtures, which are `flat-test-integration-setup`, in the `pyhouse-flat` plugin.
---

# Hex Test — Integration Setup

Consult `test-principles` for the testing constitution. Where this skill contradicts `test-principles`, the constitution wins.

One-shot per project, and everything else in the integration suite depends on it. **This is the relational-store isolation strategy.**

## When to use vs. neighbours

- Laying either conftest for the first time, or changing a fixture in one → this skill.
- A repository contract test → `hex-test-repository-contract` (consumes `sf`).
- An API endpoint test → `hex-test-restapi-endpoint` (consumes `real_app`, the REST add-on, and the store's own fixture where it seeds rows).
- The cross-cutting OpenAPI / CORS / request-size invariants → `hex-test-app-invariants` (consumes `real_app` directly).
- A handler test that runs on in-memory fakes and needs no database at all → `hex-test-application-handler`; none of these fixtures apply to it.
- A capability adapter's own assertions — the respx gateway, the SDK-error translation, the pure-CPU case → `hex-test-capability-adapter`. The session-scoped container its backend needs is still declared here.
- The signing-key and token-minting fixtures, the authenticated client, and the `jwt_settings` override `container` grows in an auth app → `hex-test-restapi-auth`. Only for an app that declares auth; this skill is complete without it.
- The route-side auth dependencies themselves → `hex-restapi-auth`.
- Per-resource row factories (`make_foo`, …) → not this skill; they live in `tests/integration/api/<resource>/conftest.py` next to the tests that use them.
- Which scope a fixture takes, which conftest level it belongs at, builders versus fixtures → `test-principles`, the constitution. This skill is the hexagonal artifact that implements it.
- The same fixtures for a flat-layered service → `flat-test-integration-setup`, in the `pyhouse-flat` plugin. Several hexagonal members of one workspace sharing these fixtures → this skill, under `## Other bindings`.
- The composition root has no `session_factory` binding, or no way to pass extra providers into it → `hex-wiring` first; the substitution seam is `create_container`'s parameter, not something a test can bolt on.
- Turning "the sanctioned handle is the only one opened under `tests/integration/`" into a static grep firewall → `test-architecture-rule`, which owns the firewall mechanism. The obligation itself is this skill's (obligation 2); no firewall for it ships with the catalogue, so a project that wants it machine-checked writes one.

## Template(s) — pytest, testcontainers, dishka

```
tests/
├── conftest.py                       # empty; pytest-asyncio config belongs in pyproject.toml
├── unit/                             # nothing here takes a fixture from integration/
└── integration/
    ├── conftest.py                   # base: Postgres container, guard, migrations, engine, `sf`, `container`
    │                                 # + each add-on's fixtures (the key-value store is the worked one);
    │                                 # `real_app` only with a REST entrypoint
    ├── postgres/                     # repository contract tests — take `sf`, never `real_app`
    └── api/                          # only where the app has an HTTP entrypoint
        ├── conftest.py               # empty unless the app declares auth
        └── <resource>/conftest.py    # per-resource row factories — not this skill's
```

The files that fill that tree belong to the skills that write them, each of which shows its own
fragment: `tests/unit/fakes/` to `hex-test-application-handler`; `tests/unit/test_architecture.py` to
`test-architecture-rule`; `tests/unit/restapi/test_app_constructs.py` and the app-wide files under
`api/` to `hex-test-app-invariants`; `tests/helpers/`, the auth fixtures in `api/conftest.py` and the
anonymous-caller probe to `hex-test-restapi-auth`, only for an app that declares auth; one file per
endpoint under `api/<resource>/` to `hex-test-restapi-endpoint`.

**Read the sibling `CONFTEST.md` before writing or changing any fixture in that hierarchy.** Only this
file is loaded automatically, so open it rather than reconstructing the fixtures from the obligations
below: it carries the base `tests/integration/conftest.py` — relational only, framework-free, ending at the
per-test `container` — and the add-ons a project lays on top of it: each add-on's fixtures (the
key-value store, Redis, is the worked one) with its substitution in `container`, and `real_app` for a
REST entrypoint; then the top-level and api sub-templates with the import rule the root conftest must
obey, and the ten numbered spellings of the obligations under this
binding — the one sanctioned sessionmaker, the savepoint mode, the session/function scope split, and the
disposability marker the container fixture is entitled to set.

### Binding traps — pytest, testcontainers, SQLAlchemy savepoints

The savepoint that lets a handler commit inside the test's transaction, the connection the session
factory hangs off are **this stack's own** — a store with no nested
transactions and a suite that provisions no container have none of them — so these stops sit with the
template that names the stack, and they stop wherever this binding is in use.

- Asked to drop `join_transaction_mode="create_savepoint"` → stop, that flag is the whole point — without it the handler's commits either escape or fail.
- The `sf` fixture is bound to the engine directly (skipping the outer connection) → stop, that bypasses rollback and every row a test commits survives into the next one.
- Asked to add a `truncate_all_tables` teardown alongside rollback → stop, rollback alone is sufficient; truncate is the fallback for DBs without nested transactions and is strictly slower.
- The conftest carries an add-on for a store the project does not have → stop, an add-on goes in with its adapter and not before.

## Other bindings

### Provisioning — where the store under test comes from

The obligations below hold under every one of these; what changes is who creates the store, how the
schema gets there, and what the disposability marker is set by.

- **A developer- or CI-supplied store.** The suite starts nothing: connection details come from a
  **dedicated** opt-in variable, and whatever provisioned the store sets the disposability marker. The
  container fixtures go; the guard, the schema step, the isolation handle and the substitution are
  unchanged — and the guard matters *more* here, the one branch that can reach a store the suite did
  not create.
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

- **`dependency-injector`.** The container fixtures, the migration run, the guard and the savepoint-rollback `sf` are unchanged; only the composition-root fixture differs, and it differs in kind rather than in spelling. There is no `TestInfraProvider`: the fixture builds the real container, calls `.override(value)` on each provider **after** construction, and must `.reset_override()` each one in the `finally` block. Because the substitution lands on a live container, an already-resolved singleton may have captured the pre-override value — the classic case is a singleton whose `__init__` snapshots a settings field — so the same `finally` block also calls `.reset()` on every such capturing singleton — an explicit teardown in the fixture that overrode it, never an autouse one, which `test-principles`' closed autouse set does not admit — and `containers.py` has to be audited once to find them. That failure mode does not exist under the primary binding, where the graph is assembled with the test factories already in it.
- **Manual composition.** The composition root is a factory function, so the fixture calls it with the test objects as arguments. No provider classes, no override marking, and teardown is whatever `AsyncExitStack` the factory returned.

### Shared across workspace members

- **One pytest plugin module several hexagonal members load.** Where several members of one workspace
  (`python-workspace`) each need these fixtures, the session-scoped half — containers, guard, migration
  run, engine, and each add-on's container and client — moves into one importable module the root `pyproject.toml` loads with
  `-p <module>`, and each member keeps only what is its own: the per-test isolation handles and
  `container` (with `real_app` where it has a REST entrypoint), which builds that member's composition root. Nothing in the shared module is autouse —
  it loads for every collection, pure-unit runs included — so each member's integration conftest makes
  the guard and the migration run autouse by requesting them. The migration run takes the member's own
  migration directory; the obligations are unchanged.

## Rules

Consult `test-principles` for the testing constitution.

### Scope

- **`tests/integration/conftest.py`** — the containers, the engine, the transaction-rollback `sf` and the
  per-test `container`; `real_app` joins them only with a REST entrypoint. A service without one —
  queue-driven, RPC — has a base conftest that ends at `container` and imports no web framework: a
  framework import there fails every collection of a service that does not install it.
  The contract: every integration test starts with an empty database, and rows the test (and its handler)
  commit are rolled back at teardown.
- **`tests/integration/api/conftest.py`** — created here, empty by default. Its only current occupant is
  the auth fixture set, which is `hex-test-restapi-auth`'s and exists only for an app that declares auth.
- **The autouse pair is the disposable-database guard and the migration run**, both session-scoped and
  both in the base conftest, for a relational app — the closed autouse set `test-principles` allows.
  Everything else, `sf`, `container` and `real_app` included, is requested by name.

**This is the relational-store isolation strategy.** The engine, the Alembic migration run, and the savepoint-rollback `sf` all assume a relational store — the per-test transaction that ROLLBACKs is a SQL-database mechanism. An app whose only datastore is client-style (redis / a document store / …) has no engine, no migration chain, and cannot use savepoint rollback; it isolates by **per-test namespace + teardown** instead (the key-value add-on in `CONFTEST.md` is exactly that pattern). Lay the Postgres machinery only when the app has a relational store.

**What this skill owns, exactly: every session-scoped fixture, for every store kind.** Containers,
engines, migration runs and long-lived clients belong here because one container per session is the
guarantee the whole setup rests on, and a fixture duplicated into a store-kind conftest breaks it. The
**per-test** half — a fresh collection, key-prefix, database or bucket path, and its teardown — belongs
in the sibling `tests/integration/<store-kind>/conftest.py`, next to the tests that consume it
(`hex-test-repository-contract`) — **unless `container` binds it too**, in which case it sits up-tree
beside the session half so a route under test reaches it. The worked add-on in `CONFTEST.md` is that
case: the key-value store's per-test client, whose teardown empties the suite's own container, is bound
by `container`, so an entrypoint never reaches a store the environment names.

- Per-resource row factories (`make_foo`, `make_bar`, …) → not this skill; declare them in `tests/integration/api/<resource>/conftest.py` next to the tests that use them.
- Cross-cutting "OpenAPI codes match `error_responses(...)`" / CORS / request-size invariants → `hex-test-app-invariants`; the every-protected-route-rejects-an-anonymous-caller probe → `hex-test-restapi-auth`.

### In an auth app, `container` is usable only from `tests/integration/api/`

In an app that declares auth, `container` consumes the verifier settings fixture defined down-tree in
`tests/integration/api/conftest.py`, and an app without auth substitutes none; the override, its cost and
when those fixtures move up-tree are `hex-test-restapi-auth`'s.

### The obligations

Stated without a mechanism, because both halves of this file vary: provisioning varies by binding
(above) and isolation varies by what the store can undo. Every binding of this file delivers these.

1. **Each test starts against an empty store and leaves nothing behind.** The undo is automatic — a
   property of the handle the test was given, not a teardown someone remembers to write — and it
   covers writes the *subject* made, not only the test's own. A row a test depends on is made per test
   too: a fixture handing the same row to several tests sits outside the undo.
2. **One sanctioned handle, and nothing reaches the store around it.** Every test, fixture and
   substituted infrastructure binding goes through the handle this file provides. A handle a test
   opens for itself writes outside the isolation boundary, so its rows survive into the next test and
   the failure surfaces somewhere else entirely.
3. **The expensive resource is per session; the isolated unit is per test.** Starting the store,
   establishing the schema and building the pool happen once per run; what each test owns alone is the
   cheap thing — a transaction, a namespace, a schema. Reversing either end is a defect: a per-test
   store that takes seconds to start costs seconds a test, a per-session isolated unit serialises the
   suite. A file-backed or in-process store created per test is `test-principles` reliability rule 2's
   cheap case, not a reversal.
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
9. **A store with no undo isolates by namespace instead.** Where nothing can be rolled back — an object
   store, most client-style stores — each test owns a namespace, created or emptied before it and
   dropped or emptied after it, and asserts only inside it; a test that asserts on contents outside its
   namespace is asserting on other tests. Where the adapter's namespace is fixed in code, the namespace
   a test owns is a whole store the suite itself started, emptied after each test.
10. **The isolation guarantee is what licenses strong assertions.** Because the store is empty at test
    start, fixed natural keys need no unique suffix and exact counts are correct — no defensive
    `any(...)` filters, no `+1` for the test's own row.

### The authenticated client

- **An authenticated client is not this skill's.** The single sanctioned authenticated client, the
  signing keypair, the token-minting helper and their rules → `hex-test-restapi-auth`. A raw
  `AsyncClient` over `real_app` is sanctioned here only for an app with no auth, and for the
  unauthenticated probes in `hex-test-app-invariants` / `hex-test-restapi-auth`.
- **No `localhost` / `127.0.0.1` base URL.** `http://testserver` is the convention; the ASGI transport
  short-circuits the network anyway, but `testserver` makes route logs distinguishable from real
  traffic in CI logs.

## Inlined typing / import rules

- `pytest`, `dishka`, `sqlalchemy.ext.asyncio`, `subprocess`, `os`, `sys`, stdlib `collections.abc` and `typing` — and the project's `infrastructure.postgres.*`. The REST add-on adds `fastapi`, and only it. The key-value add-on adds `redis.asyncio` only.
- `create_container` and `create_app` are imported **inside** the `container` and `real_app` fixture bodies, never at module level (see the root-conftest note in `CONFTEST.md`).
- Full annotations on every fixture signature. `AsyncIterator[T]` for yielding fixtures with cleanup.
- No `from __future__ import annotations`.

## Hard stops

- The composition root has no `session_factory` binding, or no way to pass extra providers into it → stop, use `hex-wiring` first; the substitution seam is `create_container`'s parameter, not something a test can bolt on.
- A token-minting fixture, a signing keypair or an authenticated client is put in either conftest this skill owns → stop, use `hex-test-restapi-auth`; they belong to the auth-only fixture set.
- A per-resource row factory (`make_foo`, …) is added inside either conftest this skill owns → stop, use `hex-test-restapi-endpoint`; those live in `tests/integration/api/<resource>/conftest.py`, next to the tests that use them.
