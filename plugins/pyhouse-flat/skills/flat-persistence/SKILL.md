---
name: flat-persistence
description: Use when a flat-layered service reads or writes a SQL store — its table definitions, its bulk write helpers, its own component-owned settings class, and the class that owns a multi-statement write. Owns the constraint-naming convention, the single declared transaction owner per callable, driver-error translation into the service's catalogue with a mandatory fallback, the pure row-to-service-type mapping, chunked writes sized from the driver's bind-parameter cap, explicit conflict resolution, and application-minted time-ordered keys. A hexagonal service's repository adapter behind a port is `hex-persistence`, in the `pyhouse-hex` plugin; the repository root hosting a storage library several distributions share is `python-workspace`.
when_to_use: Also when asked for a bulk upsert, an `ON CONFLICT` clause, a chunk size, a storage or repository class in a flat service, a constraint naming convention, a migration for a flat service, or where a service's SQL is allowed to live.
---

# Flat Persistence — one package owns the data access

The package a `flat-layered` service keeps its data access in — the *data access* role kind in that
skill's import contract, whatever this service names the package. It holds the table definitions, the
write path, the mapping from stored rows back to the service's own types, and the migration history.
**No other package in the service constructs a statement or opens a connection.**

**Precondition — the store speaks SQL.** Which of the rules below bind you then depends on four
properties of that store, not on its name. Answer these before reading the rules, because a rule whose
property is absent has nothing to be true about:

| Does the store have… | If no, these do not apply |
|---|---|
| multi-statement transactions | rules 3, 4 — nothing spans statements, so nothing declares an owner |
| named unique constraints | rule 8 — there is no name for three artifacts to agree on |
| a conflict clause on write | rule 12 — resolution moves into the table's own engine or a later pass |
| a write readable immediately after it returns | rule 11 — a read-back can only be a separate, later read |

**Rules 1, 2, 5, 6, 7, 9, 13, 14 and 15 hold for any store at all**, SQL or not, and are what carries
across to a document store, a key-value store or a vendor-managed index; rule 16 holds wherever the
schema is versioned by migrations at all. Rule 10 holds everywhere but
inverts its reason: where a driver caps bind parameters the constant exists to stay under a ceiling,
and on a columnar store that penalises small writes it exists to stay above a floor. The number is the
store's; that it is named once and read by the test is not.

A store answering *no* four times is not a poor fit for this skill — it is ten rules instead of
sixteen, and the six that lapse lapse because their subject does not exist.

The default subject is **one distribution with its own store**. Where several share one store, the same
package becomes a library they all depend on and one rule below says what that changes.

## When to use vs. neighbours

- The service's own modules and role packages around this one — the settings and logging modules at the
  package root, the clients, the run functions → `flat-layered`, which owns the import contract this
  package sits inside, the rule that each configured component declares its own settings class, and the
  no-`Protocol` rule this skill applies to the datastore.
- Several distributions sharing one repository, and where a shared storage library sits inside it →
  `python-workspace`.
- What triggers a run and hands this package its connection handle → `flat-entrypoint`.
- Testing these tables, helpers and the storage class against the real datastore →
  `flat-test-persistence`.
- The container, migration and isolation fixtures those tests run on → `flat-test-integration-setup`.
- The project's `pyproject.toml`, toolchain and the migration environment laid once, before the first
  revision → `flat-project-setup`.
- The exception classes the translator produces, and what context they carry → `exception-catalog`.
- Module layout, `__all__`, and the `__init__.py` re-exports every table module needs →
  `python-packaging`.
- The declared type a row is mapped into before it leaves this package → `python-style` owns the rule
  that a record crossing a boundary is a declared type; `flat-layered` says which package declares it.
- The service enforces business invariants that must outlive a change of datastore → not this skill, and
  not this family: that is `hex-persistence`, in the `pyhouse-hex` plugin, where the repository sits
  behind a port. `architecture-choice` settles which family applies before either.

## Template(s) — SQLAlchemy Core, asyncpg, Alembic

```
src/myapp/storage/
├── __init__.py        # re-exports the storage class, the settings and the engine helpers
├── metadata.py        # the one MetaData, carrying the naming convention
├── settings.py        # this package's own settings class and its factory
├── engine.py          # the engine factory and the chunked bulk write helpers
├── foo_table.py       # the Table definitions
└── foo_storage.py     # the class that owns a multi-statement write

migrations/
├── env.py             # laid once — `flat-project-setup`
└── versions/          # one revision per schema change
```

The full file templates live in three topic files beside this one, one per group of artifacts in that
layout. Only this file is loaded automatically, so open the one you need:

- **Read `SETUP.md`** before writing the metadata module, the settings class, the engine factory, a bulk
  write helper or a migration revision — it binds rules 8, 9, 10, 11, 12, 14, 15 and 16.
- **Read `TABLE.md`** before defining a table, a column or a key — it binds rules 8 and 13.
- **Read `STORAGE.md`** before writing the class that owns a write, its error translator or its row
  mapper — it binds rules 2, 3, 4, 5, 6 and 7.

## Other bindings

- **The ORM (declarative mapping plus a session).** Mapped classes replace the table objects and the
  session replaces the connection; the declared transaction owner, the driver-error translation with its
  mandatory fallback, the row mapping, the constraint-name contract and the factory-built engine are all
  unchanged. What you give up is the thing the primary binding is chosen for: with Core the SQL that runs
  is the SQL in the file, so a bulk write's cost is readable at the call site and lazy loading cannot
  appear behind an attribute access. Rule 9 is where this bites — an ORM project writes the bulk path as
  the session's own bulk-insert API, never as mapped objects saved in a loop.
- **Another engine or driver.** The dialect-specific column types, the bind-parameter cap the chunk size
  is computed against, the driver exception the translator matches on and the read-back clause all change
  together; which rules bind at all is the precondition's four questions, not this bullet's. Conflict
  resolution is the one that is not mechanical. A backend with no conflict clause carries rule 12 as a
  `MERGE` or as a lock-and-check where it has either — and where it has neither, resolution is not the
  writer's to do: a columnar store that deduplicates at merge time takes the write as it comes and
  settles it later, so the rule lapses and what replaces it is a table-engine choice made once in the
  schema, not a clause chosen per call. "Nothing to update" must still be a no-op wherever the rule
  applies at all.
- **This package as a separate distribution, shared by several others.** The templates are unchanged,
  the settings class in `SETUP.md` included — it is already this component's own. What changes is where its
  prefix comes from: no longer one service's stem but the shared package's own (`MYSCHEMA_`), because
  every dependant now reads the same variables and none of them owns the component. It also gains its own
  migration command run from its own directory, and a standing restriction that the distributions
  importing it define no table of their own (`python-workspace`).

## Rules

1. **One package owns a service's data access, and nothing outside it constructs a statement or opens a
   connection.** A service's SQL is findable in one place or it is everywhere. This is the positive form
   of `flat-layered` rule 4.
2. **No `Protocol` over the datastore, and that is a decision rather than an omission.** The main
   datastore is a sticky dependency with no nameable alternative the business would plausibly adopt, so
   it never qualifies for an interface however generic it looks (`flat-layered` rule 5). Test doubles come
   from the real backend or from subclassing the concrete class (`test-principles`).
3. **Transaction ownership is one declared decision per callable.** A callable either *accepts* a live
   connection and never commits, or *opens and owns* one for the whole of its work. The two forms are
   mutually exclusive for one callable, and no connection is held in instance state between calls. Which
   form a callable takes is part of its contract: it decides how a caller composes it and which isolation
   fixture its test needs (`flat-test-integration-setup`).
4. **A write spanning more than one statement is one transaction, owned by the callable that spans
   them.** Splitting it across two connection blocks reopens the partial-write race the owning callable
   exists to close, and makes the write untestable inside a rolled-back transaction.
5. **This package's edge is the boundary where a driver error is translated.** Translation with the
   cause chained, and the mandatory fallback when no case matched, are `exception-catalog`'s rules; what
   this skill adds is where they bind — nothing above this package ever sees the driver's type.
6. **The identifying context of a storage error is the offending field and the full constraint name.**
   Which class to pick and what `context` carries are `exception-catalog`'s; here the constraint name is
   the key rule 8 makes predictable, so the caller and the tests can assert on it.
7. **Rows cross this package's boundary as the service's own declared types, and the mapping is a pure
   function this package owns.** No IO, no logging. It normalizes what the driver hands back, including
   giving a naive timestamp its offset, and it is where a natural key is normalized once so one unit test
   can pin the form. Normalize in Python, never inside SQL. The declared-type obligation itself is
   `python-style`'s.
8. **Constraint names are a contract, generated from one convention declared once.** A migration, a
   translator branch and a test must be able to name the same constraint without any of them inventing
   it. This rule and rule 5 are paired: the translator can only match on a name the convention makes
   predictable.
9. **Bulk writes go through one helper, never a per-row statement in a loop** — that is what keeps a
   ten-thousand-row batch to a handful of round trips instead of ten thousand.
10. **Chunk below the driver's bind-parameter limit, and hold the chunk size as a named constant.** One
    statement binds chunk size × columns-per-row parameters, and a batch that crosses the cap fails at
    execute time on size alone, whatever the data says. The number is computed once, from the widest
    table's column count and the driver's cap, and written where the helpers read it — never sprinkled as
    a literal at each call site.
11. **Exactly one helper reads back the rows it wrote, and it does so as one multi-row statement per
    chunk.** Whether a driver's batched-parameter (`executemany`) path returns rows at all differs by
    driver and by library, so a read-back built on it can hand back nothing for most of the batch; one
    multi-row statement per chunk returns every row under any of them. Every other write returns nothing,
    and its caller does not ask.
12. **A conflicting row is resolved explicitly, the key matched on is never among the columns updated,
    and an empty update set resolves to *do nothing*.** The caller names the conflict columns and the
    update columns; writing back the key you matched on is a no-op at best and a statement failure on a
    partial index. "Nothing to update" is a real case and must not become an update with an empty
    assignment list, which is a syntax error.
13. **Every key is a time-ordered identifier minted application-side by one function every table
    shares.** A random identifier scatters rows inserted together across the index for no benefit, and a
    database-side default means the writer cannot know the id it just created without reading it back.
    One table diverging onto a different scheme splits the schema's id policy in two.
14. **This package declares its own connection settings, and engines, sessions and those settings are
    all reached through factories and passed as arguments below the process definition.** Being a
    component with configuration of its own, it states that configuration in one settings class beside
    the package under its own environment prefix (`flat-layered` rule 8) and exposes a factory for it.
    Nothing here builds a settings object, an engine or a session at import time — an object constructed
    at module scope makes merely importing the package fail wherever the environment is incomplete — and
    no module in this package calls either factory: the process definition calls them and hands the
    values down (`flat-layered` rule 7).
15. **Where several distributions share a store, exactly one of them owns its schema and its migration
    history, and every other one depends on it.** Two packages defining tables in one
    database means two migration histories over one schema, and the second one to run decides what the
    first one's tables look like.
16. **Migrations run as a deploy step, before the new code starts, and every schema change is
    compatible with the code still running.** During a deploy the old code keeps serving against the new
    schema, so a change lands in two releases — expand first (add the column, the table, the nullable
    field), contract in a later release once nothing reads what is being removed. Each change is one
    revision whose `downgrade()` reverses its `upgrade()`; the migration round trip the integration suite
    replays is what proves that it does (`flat-test-integration-setup`).

## Hard stops

- A statement is being built or a connection opened outside this package → stop, the call belongs behind
  a method here; that is what makes the service's SQL findable and its writes testable.
- One callable both accepts a connection and opens its own → stop, pick one; a caller cannot compose it
  and a test cannot isolate it.
- A multi-statement write is being split across two separate transactions → stop, that reopens the
  partial-write race; keep it inside one.
- A driver exception is allowed to escape this package, or the translator ends by re-raising it → stop,
  the fallback is mandatory: return a catalogue exception when no case matched.
- A row leaves this package as a bare mapping → stop, map it to the service's declared type here; the
  mapping is this package's, and nothing above it should learn column names.
- A single-row insert path is being written for a batch known to exceed a few hundred rows → stop, use
  the bulk helper.
- A new primary key uses a random UUID or a database-side default → stop, mint a time-ordered identifier
  application-side.
- The `MetaData` is being declared inside a table module → stop, it belongs in its own module; hosting it
  in a table module makes that table the root of the import graph.
- A `MetaData` is created without the naming convention → stop, the constraint names are a contract
  shared by migrations, error handling and tests; backend-assigned names break all three.
- A module-level `engine = create_async_engine(...)` is being added → stop, use the factory; the bare
  object makes importing the module fail wherever the environment is incomplete, and it is the object
  every test skill forbids importing.
- One revision drops or renames something the running release still reads → stop, split it: expand in
  this release, contract in a later one.
- A revision ships without a `downgrade()`, or with one that does not reverse its `upgrade()` → stop,
  write it; the migration round trip fails on it, and that test is the reason it exists.
- The migration environment or the baseline revision is being laid → stop, use `flat-project-setup`;
  this skill owns the revisions that follow it.
- The service has business invariants that must outlive a change of datastore → stop, this family is the
  wrong one; `architecture-choice` decides, and the repository goes behind a port (`hex-persistence`, in
  the `pyhouse-hex` plugin).
