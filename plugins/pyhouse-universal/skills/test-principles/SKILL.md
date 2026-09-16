---
name: test-principles
description: Use when writing or changing tests and the question is a rule rather than a file — speed budgets, fixture versus module-level builder and which conftest holds it, the substitution ladder and no-mocks contract, assert strength, reliability. The fixture files are `hex-test-integration-setup`'s or `flat-test-integration-setup`'s.
---

# Test — Principles (reference)

Every test skill consults this one. The rules here are the **catalog-level testing constitution** for both hex and flat projects; where another test skill contradicts this constitution, this constitution wins. Reference only — it produces no file.

The obligations below are runner-neutral. Every *spelling* of them is **pytest** — the fixture and
marker decorators, parametrization, path-based collection, and the `[tool.pytest.ini_options]` block
that declares the run. That is this catalogue's binding, not part of the constitution; what moves
under another runner, and what does not, is in `## Other bindings`.

## When to use vs. neighbours

The `hex-*` and `flat-*` names in this list and throughout the skill are forward references into the
`pyhouse-hex` and `pyhouse-flat` plugins; **Reading the family-flavoured sections** below says why
none of them is a dependency.

- Adding or changing any test → this skill **and** the skill that owns that test file; this one is
  reference-only and produces no file.
- Domain unit tests → `hex-test-domain`.
- Handler tests and protocol fakes → `hex-test-application-handler`.
- **Where a fixture lives is this skill's rule; the fixture file is not.** One hexagonal package's
  `tests/integration/conftest.py`, with its containers and isolation fixtures →
  `hex-test-integration-setup`. A uv workspace's shared `myschema_testing.py` pytest plugin — "where
  do my shared fixtures live in the workspace" → `flat-test-integration-setup`.
- A static "no X in Y" invariant → `test-architecture-rule`.
- A skill that owns a test file contradicts something here → fix that skill; this constitution is the
  source of truth.
- Naming a builder, fixture or test function → `naming`.

## Other bindings

- **A different runner** — `unittest` with a plugin set, or any collector of its own. What changes is
  spelling: how a fixture declares its setup, teardown and scope; how one body is run over a set of
  inputs; how a marker is registered and selected; where the run's configuration is declared. What
  does not change is the whole constitution — the layer budget and what each layer may touch, the
  naming contract, the substitution ladders and the no-mocks rule, the AAA shape, assert strength, and
  the isolation and determinism rules. A runner with no fixture lifecycle pays for it in duplicated
  `setUp`/`tearDown`; that is a cost to carry, never a licence to share state between tests.
- **A different async plugin in `pytest-asyncio`'s role** (`anyio`'s pytest plugin). Auto mode and the
  marker ban are one obligation in pytest's spelling: async-ness is declared once, project-wide, never
  per test function. Whatever declares it, it is one declaration.

## Rules

### Moving a rule that a defect paid for

A rule distilled from a real defect travels **verbatim** when it is moved, merged or reworded across these skills — copy the sentence rather than restate it. What carries such a rule is one distinctive phrase or code pattern, the part a plausibly-wrong rewrite would never reproduce by accident; a paraphrase keeps the topic and drops exactly that, so the rule survives as a heading and stops changing anyone's behaviour. If the wording around it has to change, keep that phrase intact inside the new wording.

### The testing pyramid

| Layer | Skill | Touches IO? | Target speed (per test) | What it catches |
|-------|-------|-------------|-------------------------|-----------------|
| Domain unit | `hex-test-domain` | No | < 10 ms | Identity equality, `__post_init__` invariants, enum values, pure-logic services, single-rule policies |
| Application handler unit | `hex-test-application-handler` | No (in-memory fakes) | < 50 ms | Handler orchestration, PATCH semantics, normalization, domain-exception propagation, compensating-tx undo |
| App construct smoke | `hex-test-discovery-invariants` | No (constructs the app, no DB) | < 100 ms | Construct-time wiring + framework deps the type/lint/unit layers miss (e.g. `python-multipart`), OpenAPI schema build |
| Repository contract | `hex-test-repository-contract` | Real Postgres via testcontainers, transaction-rollback isolation | < 500 ms | `IntegrityError` translation, constraint-name map, cascades, `onupdate=`, `get_by_*` semantics |
| REST endpoint | `hex-test-restapi-endpoint` | Real app + real Postgres via ASGI | < 1 s | Routing, DI wiring, request/response validation; with `hex-test-restapi-auth` when the app declares auth, also role gating and tenancy scoping |
| Discovery invariants | `hex-test-discovery-invariants` | Real app, no DB calls | < 500 ms | Global properties (every code in OpenAPI matches `error_responses(...)`; CORS; 413) — plus, in an auth app, every protected route rejecting an anonymous caller (`hex-test-restapi-auth`) |
| Architecture | `test-architecture-rule` | None (greps the source tree) | < 100 ms | Static "no X in layer Y" invariants |
| Pure unit | none — the test file stands alone | No | < 10 ms | Filter/normalize functions, `StrEnum` values, the exception catalog, schema validation |
| Service client | `flat-test-service-client` | Stubbed HTTP transport, no socket | < 100 ms | Request shape, response parsing, SDK-error → catalog translation, timeouts |
| Schema contract | `flat-test-schema-package` | Real Postgres via testcontainers | < 500 ms | Constraints, `ON CONFLICT` semantics, `RETURNING`, registry dedup, chunking |
| Run function | `flat-test-run-function` | Real Postgres + stubbed transport | < 2 s | `run_once` wiring end to end, activity bodies |
| Workflow | `flat-test-temporal-workflow` | Time-skipping test server | < 2 s | Orchestration, retry policy, batch-loop and `continue_as_new` semantics |

The shape is the goal: **fast layers run on every save; slow layers run on every commit; the slowest layers run in CI.** If a domain unit test starts touching IO or a repository test starts depending on the FastAPI app, the layer is leaking and the speed budget is gone.

### Reading the family-flavoured sections

This skill is universal and stands alone. `hex-*` and `flat-*` names appear throughout it — in the
routing list at the top, the pyramid table above, the two trees that follow, the two substitution
ladders, the reliability rules and the hard stops. Every one of those names is a *route to the skill
that produces that file*, in the `pyhouse-hex` or `pyhouse-flat` plugin; none of them carries a rule
this skill leaves unstated. With neither family plugin installed the constitution is still complete,
and the names read as forward references. That is why they are written bare here and nowhere else in
`pyhouse-universal` — this one paragraph is the plugin naming for all of them.

Each architecture family gets one worked tree. Both are **illustrations of this skill's own placement
rules**, not a dependency on either family's plugin: where a fixture lives, which conftest in the
hierarchy holds it, what may be autouse and how a down-tree fixture resolves are stated here and bind on
their own. An `OWNED BY <skill>` annotation names the skill that ships that particular *file* in its
family plugin — `pyhouse-hex` or `pyhouse-flat` — so with that plugin absent the annotation is a forward
reference and the placement rule beside it still holds. Read the tree for the family the service is in;
if that is not settled, `architecture-choice` settles it.

### Hex — tests tree and conftest hierarchy (pytest)

```
tests/
├── conftest.py                                  # empty; pytest-asyncio mode lives in pyproject.toml
├── helpers/
│   └── jwt.py                                   # sign_token(...) — OWNED BY hex-test-restapi-auth; auth apps only
├── unit/
│   ├── fakes/
│   │   └── fake_foo_repository.py              # protocol fake; imports follow python-packaging
│   ├── domain/                                  # domain unit tests
│   ├── application/                             # handler unit tests
│   ├── restapi/                                 # test_app_constructs.py — construct smoke, no DB (hex-test-discovery-invariants)
│   └── test_architecture.py                     # grep firewalls
└── integration/
    ├── conftest.py                              # OWNED BY hex-test-integration-setup
    │                                            #   - postgres_container (session) — relational apps
    │                                            #   - db_settings (session) — relational apps
    │                                            #   - _migrated_db, _guard_against_real_db, _engine (session) — relational apps
    │                                            #   - _outer_connection, sf (function) — relational apps
    │                                            #   - real_app (function) — consumes jwt_settings from down-tree WHEN the app has auth
    │                                            #   - minio_container, storage_settings (session) — blob-store apps only
    │                                            #   - s3_prefix (function), _cleanup_bucket_at_session_end — blob-store apps only
    ├── postgres/                                # repository contract tests; uses `sf` only
    │   └── test_foo_repository.py
    └── api/
        ├── conftest.py                          # created by hex-test-integration-setup; empty unless the app declares auth
        │                                        #   - rsa_keypair (session) — OWNED BY hex-test-restapi-auth; auth apps only
        │                                        #   - jwt_settings (session) — OWNED BY hex-test-restapi-auth; consumed by real_app; auth apps only
        │                                        #   - authed_client (function; consumes real_app) — OWNED BY hex-test-restapi-auth; auth apps only
        ├── test_unauth_returns_401.py           # OWNED BY hex-test-restapi-auth; auth apps only
        ├── test_openapi_advertises_error_codes.py
        ├── test_cors.py
        ├── test_request_size_limit.py
        ├── test_info.py
        └── <resource>/
            ├── conftest.py                      # per-resource fixtures (make_foo, foo_id, bar_id)
            │                                    # owned by the team adding the resource;
            │                                    # not by any single skill
            └── test_<verb>_<noun>.py            # one file per endpoint
```

The coupling point is deliberate and load-bearing:

1. **A fixture may consume a setting defined down-tree** — the canonical case being `real_app` (in `tests/integration/conftest.py`) consuming `jwt_settings` from down-tree `tests/integration/api/conftest.py`, **when the app declares auth**. Pytest's fixture resolution walks the conftest hierarchy from the *consuming test* outward, so a test under `tests/integration/api/` resolves the down-tree `jwt_settings` before pytest binds it into `real_app`. The down-tree-resolution mechanism is the universal, load-bearing point; the `jwt_settings` instance is **conditional** — an auth-less app has no such fixture and `real_app` does not consume or override it (the fixture and the override belong to `hex-test-restapi-auth`). Either way **`real_app` is only usable from tests under `tests/integration/api/`** — repository contract tests don't need it.

Fake modules and imports follow `python-packaging`.

**No autouse fixtures except**: the session-scoped DB guard, the session-scoped migration runner, and the session-end bucket cleanup. Each autouse is documented; no one ever adds a "convenience" autouse.

### Flat — tests tree and conftest hierarchy (pytest, uv workspace)

Read `myschema` here as the catalogue's placeholder for **the shared library a workspace's services
import** — the package that owns the database schema, whatever the workspace calls it — and `foo_parser`
as one such service. Substitute both; no rule below depends on the names.

**A flat service that ships on its own is the same tree with one member.** It has no root `tests/`
and no cross-member plugin: its tests sit at `tests/unit/` and `tests/integration/` exactly as the
hex tree above shows, the grep firewall moves into `tests/unit/test_architecture.py`, and what is a
shared pytest plugin below is an ordinary `tests/integration/conftest.py`. Every placement rule in
this section is unchanged; only the number of members is.

Tests live **beside the member they cover** — `packages/<pkg>/tests/` and `services/<svc>/tests/`, each
split into `unit/` and `integration/`. A member can then be read, reviewed or extracted together with
the tests that pin it, and `uv run --package <pkg> pytest packages/<pkg>/tests` selects exactly one
member's suite.

One thing belongs to no member and stays at the repo root: **`tests/test_architecture.py`**, the grep
firewall, whose subject is the workspace itself rather than anything in it. (`test-architecture-rule`
owns both placements and says which applies.)

The datastore fixtures every member shares live in a **pytest plugin module** beside the tests of the
package that owns the schema — `packages/myschema/tests/myschema_testing.py` — loaded by
`addopts = "-p myschema_testing"` plus `pythonpath = ["packages/myschema/tests"]` in the root
`pyproject.toml`. A plugin, not a conftest, because a plugin is registered **once per session**: every
member shares one container, where a conftest copied into each member's `tests/` starts one container
per member. Beside the tests, not inside `src/`: it is test-support code and has no business shipping in
the wheel. Nothing in the plugin is autouse. `flat-test-integration-setup` owns the module.

```
tests/
└── test_architecture.py               # OWNED BY test-architecture-rule
packages/myschema/
├── src/myschema/…
└── tests/
    ├── myschema_testing.py            # THE shared plugin — session: postgres_container, db_dsn,
    │                                  # _migrated_db, engine; function: conn, truncate_all
    │                                  # OWNED BY flat-test-integration-setup
    ├── unit/
    │   └── test_<thing>.py            # pure helpers only — no engine, no connection
    └── integration/
        ├── conftest.py                # only what this package adds — truncate_all made autouse
        └── test_<table>_writes.py     # flat-test-schema-package
services/foo_parser/
├── src/foo_parser/…
└── tests/
    ├── unit/
    │   ├── test_foo_client.py         # flat-test-service-client
    │   ├── test_filters.py            # pure unit
    │   └── test_workflows.py          # flat-test-temporal-workflow
    └── integration/
        └── test_foo_ingest.py         # flat-test-run-function
```

**Nothing in the shared plugin is autouse.** It is loaded for every collection in the workspace,
pure-unit runs included, so an autouse fixture there would start a container for tests that asked for
none. Ordering is carried by the dependency chain instead — `engine` requires the migration run, which
requires the safety guard — and the whole-schema TRUNCATE, `truncate_all`, is *defined* in the plugin
but made autouse one level down, in the integration conftest of each package that commits.

`pytest` collects by path. There is no `@pytest.mark.integration` and no `@pytest.mark.asyncio` —
`pytest-asyncio` runs in auto mode, declared once in the root `pyproject.toml`, which also sets
`--import-mode=importlib`: with tests per member and no `__init__.py` files, two members both having a
`test_exceptions.py` collide under pytest's default prepend mode.

### Fixture vs. builder

| | Builder (module-level `def`) | Fixture (`@pytest.fixture`) |
|--|------------------------------|------------------------------|
| Use for | Constructing one domain object with sensible defaults | Shared infrastructure or mutable factories that touch real state |
| Lives in | The same test module that uses it, or a per-resource conftest | A conftest at the appropriate level of the hierarchy |
| Examples | `_make_foo(**overrides) -> Foo`, `_foo(name="alpha") -> Foo`, `_policy(existing_keys=...)` | `sf`, `real_app`, `authed_client`, `make_foo` (per-resource factory that hits the real DB) |
| Why | Builders are pure-Python; calling them in a fixture adds ceremony without value. Fixtures live in conftests; importing a builder across files duplicates plumbing. | Fixtures handle setup/teardown lifecycle (sessions, transactions, ASGI transports) — that's what they're for. |

**Rule:** if the thing you're constructing has no setup or teardown beyond its `__init__`, write a module-level `def`, not a fixture. The producer skills (`hex-test-domain`, `hex-test-application-handler`) follow this rule.

Flat examples:

| | Builder (module-level `def`) | Fixture (`@pytest.fixture`) |
|--|------------------------------|------------------------------|
| Use for | One row dict, one schema instance, one client with defaults | Anything with a lifecycle: engines, connections, containers, transports |
| Lives in | The test module that uses it | A conftest at the right level |
| Examples | `_row(identity="a") -> dict`, `_make_payload(**overrides)` | `engine`, `conn`, `db_dsn` |

### Fixture scope rules

- **Session-scoped fixtures** — the expensive, stateless-across-tests ones the app's features require: the postgres container + engine + connection settings (`db_settings` / `db_dsn`) + test-DB guard + migration runner (relational apps), the minio container (blob-store apps), the signing keypair + verifier settings (auth apps only — `hex-test-restapi-auth`). Anything expensive to construct and stateless across tests; a feature the app doesn't have contributes none of these.
- **Function-scoped fixtures** — everything else. `sf`, `real_app`, `authed_client` (auth apps only), all row factories (`make_foo`, `make_bar`, …), `s3_prefix`, `conn`. Per-test rows are non-negotiable: rollback isolation or `truncate_all` requires them.
- **No `module`-scoped or `class`-scoped fixtures.** Two scopes are enough — one for what is expensive and stateless across tests, one for everything else — and every scope beyond them is state shared with tests that never asked for it, in a grouping (the file, the class) that exists for readability rather than for lifecycle. A test that passes alone and fails beside its neighbours is the cost.
- **Autouse placement is per family** — see the explicitly labelled conftest hierarchies above. In flat projects the guard and migration runner are explicit dependencies, and only `truncate_all` is made autouse, in member integration conftests.

### Test naming

- **Test file**: mirror the source file with a `test_` prefix. `application/foos/create_foo_handler.py` → `tests/unit/application/test_create_foo_handler.py`.
- **Test function**: `test_<rule_being_pinned>` in snake_case. `test_assigns_uuid_and_stores`, `test_duplicate_name_raises_conflict`, `test_partial_update_leaves_unspecified_fields_untouched`. The name **is** the spec line — reading the file's `def test_*` list reads as a list of behaviors.
- **Flat test files** mirror the source file inside their own member’s tree: `services/foo_parser/src/foo_parser/services/foo_client.py` → `services/foo_parser/tests/unit/test_foo_client.py`.
- Builder, failure-injection subclass, and other identifier names → `naming`.

### The acceptance-criteria marker

A test that pins an observable acceptance criterion carries a machine-selectable tag naming that
criterion, so a reader can go from a criterion to its proof and back without grepping prose. Under
this binding that tag is `@pytest.mark.ac("<criterion-slug>")`, where the slug is the criterion's own
identifier — lowercase, hyphen-separated, naming the behaviour
the criterion states rather than the code that implements it:

```python
@pytest.mark.ac("duplicate-name-rejected")
async def test_duplicate_name_raises_conflict(sf: async_sessionmaker[AsyncSession]) -> None:
    ...
```

Rules for it:

- **One marker per criterion, on the test that proves it.** A criterion proven by two tests carries the
  marker on both; a test that pins no criterion carries none.
- **The marker is not a category.** It does not replace the file's placement or its name — it records
  *which stated criterion this test is the evidence for*, so a reader can go from a criterion to its proof
  and back.
- **Register it** in `pyproject.toml` under `[tool.pytest.ini_options] markers` — an unregistered marker
  is a `PytestUnknownMarkWarning`, and warnings are errors here (`-W error` — a warning is a failure,
  Reliability rules), so it fails the run.
- **`pytest -m ac` selects every criterion-pinning test**, which is what makes the marker worth carrying.
  The selection spans the whole suite, tests written long ago included, and that is the intended reach:
  every value is a phrase that says what it stands for, so a particular criterion is looked up by its
  own slug and the answer does not depend on which tests happen to be selected alongside it.

### When to parametrize — and when not to

**Use `@pytest.mark.parametrize`** when:

- The parameter set is **discovered from the running system** — every protected route in `app.routes`, every operation in `app.openapi()`. `hex-test-discovery-invariants` is the canonical example.
- The test is **input-domain coverage**: a single behavior verified against many inputs (10 invalid emails, 20 valid date formats). The behavior is one thing; the inputs vary.
- Adding a new parameter would extend, not duplicate, an existing test set.

**Do not parametrize** when:

- Each case is a distinct rule whose **name forms part of the spec**. `test_assigns_uuid_and_stores` and `test_duplicate_name_raises_conflict` are different behaviors; collapsing them into `@pytest.mark.parametrize("scenario, expected", [...])` hides the spec lines in tuples.
- The case differs in setup or assertions, not just input values.
- The test is in `tests/unit/domain/` covering `__post_init__` invariants — those are individual rules.

The rule of thumb: if you can read the parametrize ids out loud and they sound like a list of behaviors, parametrize is fine. If you can't (because the ids would be `0`, `1`, `2`), the cases are different rules and want different `def test_*` names.

### AAA structure (Arrange / Act / Assert)

Every test follows three visually-separated blocks. **Separated by blank lines, never by comments** —
`# Arrange` / `# Act` / `# Assert` are structural labels, which `python-style` bans and deletes. The
phases are the shape of the code, not an annotation on it:

```python
async def test_assigns_uuid_and_stores() -> None:
    repo = FakeFooRepository()
    handler = CreateFooHandler(repo=repo)

    foo_id = await handler.execute(CreateFooCommand(caller_id=_CALLER, name="alpha"))

    stored = await repo.get_by_id(foo_id)
    assert stored.name == "alpha"
```

Flat example:

```python
async def test_records_a_bar_for_a_new_foo(engine: AsyncEngine, conn: AsyncConnection) -> None:
    repo = FooRepository(engine)

    await repo.record_batch([_row(name="alpha")])

    names = (await conn.execute(select(bars_table.c.name))).scalars().all()
    assert names == ["alpha"]
```

Rules:

1. **Blank lines separate the three blocks.** Comments follow `python-style`.
2. **One Act per test.** If a test has two `handler.execute(...)` calls, the second one is part of Arrange (setup) for an assertion about the first. When in doubt, split into two tests.
3. **One assertion subject per test.** Multiple `assert` statements that all check the same returned object are fine (`assert stored.name == "alpha"; assert stored.created_at >= ...`). Multiple assertions across different objects often means two tests in one.
4. **Arrange constructs valid state.** Don't write defensive `try/except` in Arrange — if the setup fails, the test fails, and that's the right outcome.

### Assert strength — pin the contract, not a coincidence

**Fixed natural keys are fine.** With an empty database per test, `identity="alpha"` needs no random
suffix, and `assert len(rows) == 2` is correct — no defensive `any(...)` filters, no `+1` for the
test's own row.

**Pin the contract, not a coincidence.** Assert the returned state or observable effect that proves the behavior, including exact values and counts the contract guarantees. A successful call alone does not prove that the intended state was written.

**Never assert on what the subject logged.** A log line is a side effect of a successful run, not the
contract: a subject that logs the right event and writes nothing must red, and it passes every test
that watches the log instead of the result. Event names are also a stable operational contract that
dashboards key on (`python-style`), so a test asserting on one couples the suite to the observability
surface and reddens on a rename that broke nothing. Assert the returned value and the persisted
state. Which layer may log at all, and what a line may carry → `python-style`.

Artifact-specific coverage for domain behavior → `hex-test-domain`; repository contracts → `hex-test-repository-contract` or `flat-test-schema-package`; request shape and error translation → `flat-test-service-client`. Pin the observable contract those tests own.

### No-mocks contract

| Tool | Forbidden? | Notes |
|------|-----------|-------|
| `unittest.mock.MagicMock` | yes | always |
| `unittest.mock.AsyncMock` | yes | always |
| `unittest.mock.patch` | yes | always |

`monkeypatch.setenv` is allowed inside settings-parsing tests, which exercise the env-reading code
itself, and nowhere else. Dependency substitution follows the explicitly labelled family ladders below.

### Hex — substitution ladder

A fake satisfying a domain `Protocol` is the canonical substitution mechanism.

| Tool | Forbidden? | Notes |
|------|-----------|-------|
| `pytest.MonkeyPatch.setattr` (`monkeypatch.setattr`) | yes | never patch handler dependencies |
| `monkeypatch.setenv` | conditional | only inside env-parsing tests (`tests/unit/infrastructure/test_*_settings.py`); never used to drive handler tests |
| Hand-written fakes (`FakeFooRepository`) | preferred | the canonical substitution mechanism |
| Inline `_RaiseXxxRepo(FakeFooRepository)` subclass | preferred | one-off failure injection at the test module scope |

The rationale: mocks describe *what was called*; fakes describe *what state would result*. The state-based assertion catches whole classes of bug the call-based assertion can't. Mocks also encode interface details that drift independently of the protocol — a refactor that adds a parameter to `repo.create(...)` silently breaks no `MagicMock` test, but a hand-written fake fails compile-time.

### Flat — substitution ladder

There are no `Protocol` ports here, so "use a fake" is not an available answer. **The rungs are the
rule; the libraries in them are this binding's examples.** Each rung down buys isolation and pays
realism, so take the highest rung that can reach the case.

| Rung | What is substituted | When |
|------|---------------------|------|
| 1 | **Nothing — the real dependency**, started and disposed by the suite | Any schema or run-function test. Always the default. Here: Postgres through testcontainers. |
| 2 | **The transport underneath the dependency**, leaving the dependency's own code running | Any service-client test. Only the socket is replaced, so the client's request building, response parsing and error translation all still execute. Here: `respx` under a real `httpx` client. |
| 3 | **One method of the concrete class**, through a subclass overriding exactly the method that must fail | One-off failure injection, at test-module scope and underscore-prefixed: `class _RaiseFooClient(FooClient): async def fetch_batch(self): raise FooClientError("boom")`. |
| 4 | **An attribute on the concrete class the caller constructs internally**, patched for the test | Last resort, and only where the caller builds its own dependency with no parameter to pass. Here: `monkeypatch.setattr`. |
| — | **A `Protocol` extracted so something becomes mockable** | **Never** — that is the anticipatory abstraction the flat-layered style exists to avoid. |

**The ladder is violated by skipping, not by using a low rung.** Rung 4 where the dependency is
already a constructor parameter, rung 3 where the failure can be produced through the transport stub,
rung 2 where the real datastore is already running for the rest of the file — each of those is a test
that bought isolation nobody needed and paid realism for it. The check is one question at the point
of substitution: *what stopped the rung above from reaching this case?* If the answer is "nothing, it
was quicker", climb back up.

Rung 4 is the one difference from a ports-and-adapters project, which forbids patching a dependency
outright because it always has a fake to reach for instead. Here it is sanctioned because sometimes
there is genuinely nothing else — but it stays rung 4, below the subclass, and a test reaching for it
is a hint that the caller wants a constructor parameter.

### Settings and shared resources (flat)

Settings classes and engines are built behind `get_*` factories, not as module-level instances
(`flat-layered`, `flat-schema-package`). That is what makes them testable: a test never mutates
a singleton and never reassigns a module attribute. It constructs what it needs, or takes the `engine`
fixture, and passes it in.

Where a placeholder value is needed so an import can succeed at all, set it once in the root
`pyproject.toml` with pytest-env's `D:` prefix, which sets a **default** rather than an override:

```toml
[tool.pytest.ini_options]
env = ["D:MYSCHEMA_DSN=postgresql+asyncpg://test:test@localhost:1/placeholder"]
```

Without the `D:` prefix the value **overrides** a real exported one, so any opt-in path that points the
suite at an external database would never see the real value. The placeholder only has to parse;
integration tests reach the container through the `engine` fixture.

### Reliability rules (local-vs-CI parity)

1. **The suite provisions the state it runs against, and no test depends on a machine-specific
   setup.** Dev and CI run the same way, so a green run on one machine predicts a green run on the
   next: the datastore and the object store are started and thrown away by the suite itself —
   testcontainers in this binding. Pointing the suite at an **already-provisioned throwaway**
   datastore is the one sanctioned alternative, and it is guarded on both sides: opt in through a
   dedicated variable, never an ambient one, and refuse any database whose name is not on a declared
   throwaway list (`flat-test-integration-setup` carries both guards). An *unguarded* "developer's
   local Postgres" mode → stop; the suite TRUNCATEs every table it can see, and the variable that
   would divert it is exported by tools that know nothing about this suite.
2. **Every test starts with an empty database.** Either the outer-transaction rollback or
   `truncate_all` guarantees it — `hex-test-integration-setup` and `flat-test-integration-setup` say which applies.
3. **The suite's result does not depend on the order it was collected in.** Each test constructs the
   state it asserts on rather than inheriting a predecessor's. Run it once in a randomized order and
   once in file order and get the same result — under this binding, `pytest-randomly` supplies the
   randomization and `-p no:randomly` the fixed order.
4. **A test never waits out real time.** A test that looks like it needs a wait needs the right
   `await` on the event it is actually waiting for; a test that needs the clock to move forward
   advances the clock its runtime exposes rather than letting one pass — a workflow runtime's
   time-skipping test environment is the worked case (`flat-test-temporal-workflow`). Sleeping makes
   the suite slower than the behaviour it pins and hides the race that will surface in CI, and
   patching a sleep so a loop exits is the same defect wearing a different hat. A runtime that
   exposes no clock control is a reason to pin the policy — the delays computed, the attempts made —
   rather than to sit through it.
5. **Datetimes asserted with `>=`, not `==`.** Postgres `now()` can return identical timestamps within a transaction; clock-based equality flakes.
6. **UUIDs used in assertions are constructed inside the test**, not pulled from `uuid.uuid4()` at module scope (except `_CALLER` which is conventional and irrelevant to assertion shape).
7. **No environment-dependent values.** Tests must not read `os.environ` or check `os.getenv("CI")` to alter behavior. The container fixture handles the local/CI fork once, and it does so on a **dedicated opt-in variable**, never on an ambient one like `CI`.
8. **Where a test sits is what decides which layer it belongs to — not a tag on it, and not a tag on
   its event loop.** A test under a member's `unit/` is a unit test because of where it is, and
   async-ness is declared once for the project rather than per function. Two tags can disagree with
   the tree; one tree cannot disagree with itself. Under this binding that means no
   `@pytest.mark.integration` and no `@pytest.mark.asyncio`, with `pytest-asyncio` in auto mode
   declared once in `pyproject.toml`.
9. **A warning is a failure, not a line in the tail of the output.** `[tool.pytest.ini_options]` carries `filterwarnings` with `"error"` as its first entry — the same table that already holds `asyncio_mode` and `markers` — so a warning raised anywhere in the run turns the suite red. This is part of what "green" means: no extra command, no second run, nothing anyone has to remember to read.
   The price is that a deprecation from a library the project cannot fix reddens the suite too, so an exception is written as one narrow entry after `"error"` — `"ignore:<message>:<Category>:<module>"`, scoped as tightly as the warning allows — and it carries its reason beside it in a comment: whose warning it is, why the project cannot remove it at the source, and what will retire the entry. An exception without a reason is the rule switched off. A warning raised from the project's own `src/` never goes on that list; it gets fixed. Suppression conventions → `python-style`.

## Hard stops

- A hex domain or handler unit test imports from `myapp.infrastructure.*` → stop, unit tests use fakes; reach for `tests/integration/` if the real adapter is what's under test.
- A hex test exercises the HTTP surface from `tests/unit/` → stop, use `hex-test-restapi-endpoint`; the app-construct smoke belongs to `hex-test-discovery-invariants`.
- A test uses `MagicMock` / `AsyncMock` / `patch` → stop, follow the applicable family’s substitution ladder.
- A test adds `@pytest.mark.integration` or `@pytest.mark.asyncio` → stop, neither is used.
- A test reads `os.environ` to fork behavior → stop, the isolation fixture handles environment differences once.
- A test asserts that the subject logged something — an event name, a level, a captured record → stop, a log line is a side effect of success, not the contract; assert the returned value and the persisted state.
- A test asserts `len(items) == N + 1` "to account for the test's own row plus seed rows" → stop, rollback or truncation isolation drops everything; exact equality is correct.
- A test uses `uuid4().hex[:4]` or `[:5]` natural-key suffixes "to avoid collisions" → stop, rollback or truncation isolation makes the DB empty; fixed values like `"alpha"` are fine.
- A "convenience" autouse fixture is proposed → stop, the per-family autouse lists above are closed. New autouse fixtures cause spooky-action-at-a-distance.
- A producer skill says something this skill forbids → stop, the producer skill is wrong; fix it. This skill is the source of truth.
- In flat projects, a `Protocol` is being extracted so a test can substitute something → stop, that is forbidden by the
  flat-layered style itself; stub the transport, subclass, or use the real backend.
- A test under a member's `tests/unit/` opens an engine or a connection → stop, it belongs under that
  member's `tests/integration/`.
- A test mutates or reassigns a settings or engine factory's cached value → stop, take the `engine`
  fixture and pass it in; the code under test accepts it as a parameter for exactly this reason.
- An autouse fixture is added to **the shared plugin** → stop, it would run for every unit test in the
  workspace; make it an explicit dependency, or make it autouse one level down, in a member's
  integration conftest.
- Flat shared datastore fixtures are put in a root `conftest.py` → stop, they belong in the shared
  pytest plugin module (`flat-test-integration-setup`). A root conftest would share correctly, but it
  puts test infrastructure at the workspace root and reaches members only from above.
- A settings test constructs its settings class without disabling dotenv loading → stop,
  pydantic-settings resolves the dotenv path against the process working directory, so the test passes
  or fails depending on which directory pytest was started from.
- A placeholder env value is declared without pytest-env's `D:` prefix → stop, it will override real
  exported values rather than defaulting.
