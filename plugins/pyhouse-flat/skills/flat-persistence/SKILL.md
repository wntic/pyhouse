---
name: flat-persistence
description: Use when a flat-layered service reads or writes a datastore — its table definitions, its component-owned settings class, the repository class that owns each write's transaction and builds its statements, and where its migration history lives. Owns one data-access package per store named for the store's technology, the constraint-naming convention, the single declared transaction owner per callable, driver-error translation into the service's catalogue with a mandatory fallback, the pure row-to-service-type mapping, chunked writes sized from the driver's bind-parameter cap, conflict resolution left to the store's own write-time or merge-time mechanism, cursor reads over a total order, application-minted time-ordered keys, and one migration directory per store at the distribution root. A hexagonal service's repository adapter behind a port is `hex-persistence`, in the `pyhouse-hex` plugin; the repository root hosting a data-access library several distributions share is `python-workspace`.
when_to_use: Also when asked for a bulk upsert, an `ON CONFLICT` clause, a chunk size, a repository class in a flat service, a second store beside the first, a constraint naming convention, a migration for a flat service or where its files go, paging through a table by cursor, deduplicating writes, or where a service's SQL is allowed to live.
---

# Flat Persistence — one package per store owns the data access

The package a `flat-layered` service keeps its data access in — the *data access* role kind in that
skill's import contract — named for the store's technology: `postgres/` for the relational store the
templates bind. It holds the table definitions, the write path and the mapping from stored rows back to
the service's own types. **No other package in the service constructs a statement or opens a
connection.** The store's migration history is data, not code, and sits at the distribution root under
`migrations/` in a directory named for the same store.

**Which rules below bind depends on four properties of the store, not on its name.** Answer these before
reading the rules, because a rule whose property is absent has nothing to be true about:

| Does the store have… | If no, these do not apply |
|---|---|
| multi-statement transactions | rules 3, 4 — nothing spans statements, so nothing declares an owner |
| named unique constraints | rule 8 — there is no name for three artifacts to agree on |
| a conflict clause on write | rule 12, unless the store has a `MERGE` — otherwise resolution is the store's merge-time mechanism (rule 18) |
| a write readable immediately after it returns | rule 11 — a read-back can only be a separate, later read |

**Rules 1, 2, 5, 6, 7, 9, 14, 15, 17, 18, 19 and 21 hold for any store at all**, SQL or not, and are what
carries across to a columnar store, a document store, a key-value store or a vendor-managed index; rules
16 and 20 hold wherever the schema is versioned by migrations at all, and rule 13 wherever the
service mints keys. Rule 10 holds on any store wherever a
write chunks, but inverts its reason: where a driver caps bind parameters the constant exists to stay under a ceiling,
and on a columnar store that penalises small writes it exists to stay above a floor. The number is the
store's; that it is named once and read by the test is not. A store answering *no* four times is not a
poor fit for this skill — the rules that lapse lapse because their subject does not exist.

The default subject is **one distribution with one store**. **A service with a second store has a second
package** (rule 17): a sibling of `postgres/` named for that store's technology, answering the four
questions above for itself, with its own settings class, connection factory and migration directory.
Where several distributions share one store, the package becomes a library they all depend on and
rule 15 says what that changes.

## When to use vs. neighbours

- The service's own modules and role packages around this one — the settings and logging modules at the
  package root, the clients, the work units → `flat-layered`, which owns the import contract this
  package sits inside, the rule that each configured component declares its own settings class, and the
  no-`Protocol` rule this skill applies to the datastore.
- Several distributions sharing one repository, and where a shared data-access library sits inside it →
  `python-workspace`.
- What triggers a run and hands this package its connection handle → `flat-entrypoint`.
- Testing these tables and the repository class against the real datastore →
  `flat-test-persistence`.
- The container, migration and isolation fixtures those tests run on → `flat-test-integration-setup`.
- The store's dependencies and the relational migration environment laid once, before the first
  revision → `flat-project-setup`; the toolchain → `python-toolchain`.
- The exception classes the translator produces, and what context they carry → `exception-catalog`.
- What the repository class is called → `naming`, whose data-access suffix is `Repository`.
- Module layout, `__all__`, and the `__init__.py` re-exports every table module needs →
  `python-packaging`.
- The declared type a row is mapped into before it leaves this package → `python-style` owns the rule
  that a record crossing a boundary is a declared type; `flat-layered` says which package declares it.
- The service enforces business invariants that must outlive a change of datastore → not this skill, and
  not this family: that is `hex-persistence`, in the `pyhouse-hex` plugin, where the repository sits
  behind a port. `architecture-choice` settles which family applies before either.

## Template(s) — SQLAlchemy Core, asyncpg, Alembic

```
src/myapp/postgres/
├── __init__.py            # re-exports the repository class, the settings and the engine factory
├── metadata.py            # the one MetaData, carrying the naming convention
├── settings.py            # this package's own settings class
├── engine.py              # the engine factory
├── foo_table.py           # the Table definitions
└── foo_repository.py      # the class that owns each write's transaction and builds its statements

alembic.ini                # at the distribution root — `flat-project-setup`
migrations/
└── postgres/
    ├── env.py             # laid once — `flat-project-setup`
    ├── script.py.mako
    └── versions/          # one revision per schema change
```

A second store adds one sibling package and one sibling migration directory, and edits neither of the
first's. `<store>` is that store's technology name — `clickhouse`, `mongodb`, `opensearch`:

```
src/myapp/
├── postgres/
└── <store>/               # its settings class, its connection factory, its repository classes
migrations/
├── postgres/
└── <store>/               # its history, in the format its own migration tool reads
```

The full file templates live in three topic files beside this one, one per group of artifacts in that
layout. Only this file is loaded automatically, so open the one you need:

- **Read `SETUP.md`** before writing the metadata module, the settings class, the engine factory or a
  migration revision — it binds rules 8, 14, 15, 16, 17 and 20.
- **Read `TABLE.md`** before defining a table, a column or a key — it binds rules 8 and 13.
- **Read `REPOSITORY.md`** before writing the repository class, a bulk write, its error translator, its
  row mapper or a write that spans statements — it binds rules 2, 3, 4, 5, 6, 7, 9, 10, 11, 12, 18 and
  21.

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
  `MERGE` where it has one — never as a lock-and-check, which is the read-before-write rule 18 forbids —
  and where it has none, resolution is not the writer's to do: a columnar store that deduplicates at
  merge time takes the write as it comes and settles it later, so rule 12 lapses and rule 18 is met by
  a table-engine choice made once in the schema, not a clause chosen per call. "Nothing to update" must
  still be a no-op wherever rule 12 applies at all.
- **Another store's migration tool.** A store whose schema is versioned keeps its history in
  `migrations/<store>/` and applies it with a tool that already speaks that store — a multi-database
  runner such as `golang-migrate` or Flyway, or the store's own — as a deploy step beside
  `alembic upgrade head`. The directory, the deploy-step ordering and the expand-then-contract discipline
  of rule 16 are unchanged; only the file format and the command differ.
- **This package as a separate distribution, shared by several others.** The templates are unchanged,
  the settings class in `SETUP.md` included — it is already this component's own. What changes is where
  its prefix comes from: no longer one service's stem but the shared package's own
  (`MYSCHEMA_POSTGRES_`), because every dependant now reads the same variables and none of them owns the
  component. It also gains its own migration command run from its own directory, and a standing
  restriction that the distributions importing it define no table of their own (`python-workspace`).

## Rules

1. **One package per store owns a service's data access to it, and nothing outside that package
   constructs a statement or opens a connection.** A service's SQL is findable in one place or it is
   everywhere. This is the positive form of `flat-layered` rule 4.
2. **No `Protocol` over the datastore, and that is a decision rather than an omission.** The main
   datastore is a sticky dependency with no nameable alternative the business would plausibly adopt, so
   it never qualifies for an interface however generic it looks (`flat-layered` rule 3). Test doubles come
   from the real backend or from subclassing the concrete class (`test-principles`).
3. **Transaction ownership is one declared decision per callable.** A callable either *accepts* a live
   connection and never commits, or *opens and owns* one for the whole of its work. The two forms are
   mutually exclusive for one callable, and no connection is held in instance state between calls. Which
   form a callable takes is part of its contract: it decides how a caller composes it and which isolation
   fixture its test needs (`flat-test-integration-setup`).
4. **Where one write spans more than one statement, it is one transaction, owned by the callable that
   spans them.** Splitting it across two connection blocks reopens the partial-write race the owning
   callable exists to close.
5. **This package's edge is the boundary where a driver error is translated.** Translation with the
   cause chained, and the mandatory fallback when no case matched, are `exception-catalog`'s rules; what
   this skill adds is where they bind — nothing above this package ever sees the driver's type, and
   that covers every public method: a read, and the opening of the connection and the transaction, fail
   with the driver's errors as surely as a write does.
6. **The identifying context of a storage error is the offending field and the full constraint name.**
   Which class to pick and what `context` carries are `exception-catalog`'s; here the constraint name is
   the key rule 8 makes predictable, so the caller and the tests can assert on it.
7. **Rows cross this package's boundary as the service's own declared types, and the mapping is a pure
   function this package owns.** No IO, no logging. It normalizes what the driver hands back, including
   giving a naive timestamp its offset. Where a natural key is normalized, it is normalized once, here,
   so one unit test can pin the form — in Python, never inside SQL, and only where the key's source
   defines the spellings it merges as one key; a key whose source tells them apart is stored as it
   arrives. The declared-type obligation itself is `python-style`'s.
8. **Constraint names are a contract, generated from one convention declared once.** A migration, a
   translator branch and a test must be able to name the same constraint without any of them inventing
   it; names left to the backend break all three. This rule and rule 5 are paired: the translator can
   only match on a name the convention makes predictable. The convention is declared in a module of its
   own that every table module imports — never inside a table module, which would make that table the
   root of the import graph.
9. **Where a method takes a batch, its write is one multi-row statement per chunk, never a per-row
   statement in a loop** — that is what keeps a ten-thousand-row batch to a handful of round trips
   instead of ten thousand.
10. **Where a write chunks, chunk below the driver's bind-parameter limit, and hold the chunk size as a
    named constant.** One statement binds chunk size × columns-per-row parameters, and a batch that
    crosses the cap fails at execute time on size alone, whatever the data says. The number is computed once, from the driver's
    cap and the column count of the table the statement writes, and named beside the statement that
    reads it — never sprinkled as a literal at each call site.
11. **Where a later statement needs keys an earlier one resolved, the earlier statement reads back the
    rows it wrote, as one multi-row statement per chunk.** Whether a driver's batched-parameter
    (`executemany`) path returns rows at all differs by driver and by library, so a read-back built on it
    can hand back nothing for most of the batch. Every other write returns nothing.
12. **A conflicting row is resolved explicitly, the key matched on is never among the columns updated,
    and an empty update set resolves to *do nothing*.** The write names its conflict columns and its
    update columns; writing back the key you matched on is a no-op at best and a statement failure on a
    partial index. "Nothing to update" is a real case and must not become an update with an empty
    assignment list, which is a syntax error. Where an older write can arrive after a newer one for the
    same key, the update is guarded by the row's ordering stamp — a version or an instant fixed when the
    change was made or observed, the same on every delivery of it, never the time of a delivery attempt
    or of the write — so an input stamped older than what it would replace never replaces it.
13. **Every surrogate key this service mints is a time-ordered identifier minted application-side by one
    function every table shares.** A random identifier scatters rows inserted together across the index for no benefit, and a
    database-side default means the writer cannot know the id it just created without reading it back.
    One table diverging onto a different scheme splits the schema's id policy in two.
14. **This package declares its own connection settings, and those settings and the engine built from
    them reach everything below the process definition as arguments.** Being a component with
    configuration of its own, it states that configuration in one settings class inside the package
    (`flat-layered` rule 7, `python-settings`), and builds its engine through a factory that takes the
    connection string. Nothing here builds a settings object, an engine or a session at import time
    (`python-packaging` rule 8), and no module in this package constructs its settings class or calls
    the engine factory: the process definition does both and hands the values down (`flat-layered`
    rule 6).
15. **Where several distributions share a store, exactly one of them owns its schema and its migration
    history** — `python-workspace` rule 3. A service reading a store another project owns declares only
    the tables it reads, carries no migration history for them, and its suite creates that schema from
    its metadata (`flat-test-integration-setup`, `## Other bindings`).
16. **Migrations run as a deploy step, before the new code starts, and every schema change is
    compatible with the code still running.** During a deploy the old code keeps serving against the new
    schema, so a change lands in two releases — expand first (add the column, the table, the nullable
    field), contract in a later release once nothing reads what is being removed. Each change is one
    revision whose `downgrade()` reverses its `upgrade()`; the migration round trip the integration suite
    replays is what proves that it does (`flat-test-integration-setup`).
17. **A service with more than one store keeps one data-access package per store, each named for its
    store's technology, with its own settings class and prefix, its own connection factory and its own
    migration directory.** Two stores never share a package, a settings class or a history: they differ
    in which rules above bind, in their drivers' failure types and in how their schema changes, and one
    package holding both turns every one of those differences into a branch inside it. Work
    that writes to both is handed both packages' objects by the process definition, like any other
    dependency. No transaction spans two stores. A unit writing to both writes first the store the other
    refers to, and each write is idempotent by its key, so retrying after a failure between them
    completes the unit.
18. **Deduplication and conflict resolution belong to the store's own write-time or merge-time
    mechanism, never to an application read-before-write per row.** Where the write can resolve a
    conflict, rule 12 says how; where the store deduplicates at merge time, the table's engine is chosen
    for it once, in the schema, and a read that must see one row per key before the merge asks the store
    for its deduplicated view. Looking up which rows already exist before inserting each chunk costs a
    round trip the store never needed, and it still admits the duplicates two concurrent runs write
    between one run's read and its write. **A column aggregated across writes is resolved the same way, in
    the write or the merge, never by reading it first.** **Inputs sharing one key are collapsed by that
    key before the statement is built** — the last one winning, or aggregated as the conflict clause
    would — because a store resolving conflicts per statement may refuse to touch one row twice within
    it. Collapsing a batch already in memory reads nothing from the store and is bounded by the batch, so
    it is not the read-before-write this rule forbids.
19. **A read resumed from a cursor orders by a total order, and the cursor carries every column of it.**
    A limited read resumed from the last row's value of a column that is not unique skips every row
    sharing that value beyond the page's edge — rows written in one batch share one timestamp, so a single
    boundary drops thousands of them with no error. Order by the column plus a unique tiebreaker and
    resume strictly after the pair (keyset pagination), or do not limit the read.
20. **A store's migration history is data at the distribution root, one directory per store named for
    it — never inside the package under `src/` — and it ships with whatever applies it.** A built
    distribution carries the package and not the root, so the deployable that runs migrations carries the
    directory itself: an image copies `migrations/` beside the installed package, or the migration job
    runs from the source tree. It is applied by an existing migration tool for that store wherever one
    exists. A hand-written runner is written only where none fits; it then lives in that store's
    data-access package, takes the migration directory as a parameter rather than finding it through the
    package's import path, and does what a tool would — records each applied version in the store itself,
    applies in order, stops at the first failure, and never runs twice at once. That exclusion is a lock
    the store provides where it has one, the migration tool's own where it takes one, or else the deploy
    mechanism's: migrations run as one dedicated job per deploy, never from every replica at start-up.

21. **Each repository class builds its own statements from its own declared type.** What several
    classes in one package share is the store's — the driver-error translation and its fallback, the
    bind-parameter cap — never a write helper taking a table, rows as mappings and conflict columns,
    which moves every class's statement out of the class that owns it and its rows back to untyped
    mappings.

## Hard stops

- The relational migration environment or a baseline revision is being laid → stop, use
  `flat-project-setup`; this skill owns the revisions that follow it.
- The service has business invariants that must outlive a change of datastore → stop, this family is the
  wrong one; `architecture-choice` decides, and the repository goes behind a port (`hex-persistence`, in
  the `pyhouse-hex` plugin).
