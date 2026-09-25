---
name: hex-persistence
description: Use when one hexagonal service's own relational layer changes — the `Table` and its constraints, the repository adapter satisfying a domain repository protocol, or the paired Alembic revision. Owns the SQLAlchemy Core templates, the constraint-naming convention all three share, row mapping, and integrity-error translation. Not a flat-layered service's storage package, which owns the same obligations with no port in front of it (`flat-persistence`, in the `pyhouse-flat` plugin), and not a nonrelational store (`hex-store-repository`).
paths: ["**/infrastructure/**", "**/alembic/**", "**/migrations/**"]
---

# Hexagonal Persistence (relational)

The table, the repository that queries it, and the migration that ships it. They live together because
**the constraint names are one contract across all three**: the table declares them through a naming
convention, the repository's integrity-error translator matches on them to produce the right domain
exception, and the revision writes them out in full. Rename one and all three change, in the same
commit.

For a non-relational store — a key-value, cache or document backend — use the client-repository form
instead. The store profile decides which applies (`hex-conventions` block B).

## When to use vs. neighbours

- A persistent table, its columns, constraints or indexes → `TABLE.md`.
- The adapter satisfying a domain repository protocol on a relational store → `REPOSITORY.md`.
- The migration pairing with a schema change → `REVISION.md`.
- The `IFooRepository` protocol file the adapter is written against → `hex-domain-ports`.
- Why the adapter satisfies that protocol structurally and never inherits it → `hex-architecture`.
- The one-time migration bootstrap — config, `env.py`, the baseline revision → `hex-project-setup`.
- A repository on a client-style store — key-value, document, or an index kept beside the authoritative
  store, reached through an injected SDK client instead of the shared engine → `hex-store-repository`.
- Tables, bulk upserts and migrations in a flat-layered service's own storage package, reached
  directly rather than through a port → `flat-persistence`, in the `pyhouse-flat` plugin.
- The settings class and the DI provider that construct this repository → `hex-wiring`.
- The unit-of-work protocol and implementation, when the repository joins multi-repository transactions →
  `hex-patterns`.
- The exception classes the translator raises → `exception-catalog`.
- The integration test that drives this adapter against a real database → `hex-test-repository-contract`.
- A data-only migration (`backfill_*`, `seed_*`) with no DDL → its own revision file; this skill covers
  DDL only.
- Asked for an ORM, a declarative base or relationships → still this skill: the templates here
  are Core, and an ORM project satisfies rules 1–14 through the ORM bullet under `## Other bindings`;
  do not copy a Core template into a mapped class.

## Template(s) — SQLAlchemy Core, asyncpg, Alembic

```
src/myapp/infrastructure/postgres/
├── metadata.py                    # the shared MetaData with naming_convention
├── tables/
│   ├── __init__.py                # import the new module and name it in __all__ (no wildcard)
│   └── foos.py                    # the Table
└── repositories/
    ├── __init__.py                # re-export the new module
    └── foo_repository.py          # the adapter

migrations/versions/
└── 0042_create_foos.py            # authored via `alembic revision`, hand-edited to the rules below
```

The full file templates live in three topic files, one per artifact in that layout. **Read the topic
file for the artifact before writing or changing it** — only this file is loaded automatically:

- **`TABLE.md`** — the naming convention, the table template, and the column, foreign-key, index,
  constraint, child-table and default rules.
- **`REPOSITORY.md`** — the two constructor forms, the session, read, mutation,
  translation and mapping rules, and the shared-mapper extraction threshold.
- **`REVISION.md`** — the revision template, the drift check and the downgrade rule.

## Other bindings

- **The ORM (declarative mapping plus a session).** Mapped classes replace the table objects and the
  session's identity map replaces explicit statements; the port conformance, the transaction-ownership
  split, the integrity-error translation, the row-to-entity mapping and the constraint-name contract are
  all unchanged. What you give up is the thing the primary binding is chosen for: with Core the SQL that
  runs is the SQL in the file, so a query's cost is readable at the call site and lazy loading cannot
  appear behind an attribute access. Under the ORM the mapped class is *not* the domain entity — keep the
  two separate and keep the mapper, or the domain grows a persistence dependency.
- **Another engine or driver.** Rules 1–14 hold; the dialect-specific column types, the SQLSTATE codes
  and the attribute path the translator reads the constraint name through all change together. The skill
  states that coupling where it bites (`REPOSITORY.md`), because it is the one place a driver swap is not
  mechanical.

## Rules

1. **Constraint names are one contract across the three artifacts.** Generate them from a single
   convention declared once, so a name is derivable rather than remembered, and so the translator can
   match on a name the database really holds. Renaming one is a breaking change: table, translator and
   revision change in the same commit.
2. **Column types are a design decision, not a transcription of the entity's fields.** Choose the stored
   type from what the value means and how it will be queried, and record the consequence where it bites —
   an on-delete choice is answered by what the repository's `delete` raises.
3. **Store every timestamp with its offset, defaulted database-side.** A naive timestamp is a defect, and
   an application-side default leaves rows written by a migration without one. An `updated_at` the
   application maintains is set explicitly in the update statement, because a database default for an
   insert does not fire on one.
4. **A closed value set is a constraint over a text column, not a database enum type.** It then matches
   the domain's own enum, and widening the set is an ordinary migration rather than a type alteration.
   The same reasoning bans length-bounded text: a length limit is a domain rule the domain enforces, not
   a storage decision that should need a migration to change.
5. **Index what you filter, join and sort on.** A foreign key gets no index for free, and a list
   endpoint's ordering column is as load-bearing as its filter's.
6. **The adapter satisfies the port structurally and never inherits it.** Signatures match the protocol
   exactly — keyword-only markers and async/sync mode included — and the module does not import the
   protocol, which would leave a dead unused import.
7. **One owner of the transaction, chosen per class.** A standalone adapter opens its own unit of work
   and commits only on a mutation; a unit-of-work-managed one receives a live one and never commits or
   rolls back. The two forms are mutually exclusive for one class, and no session is held in instance
   state between methods.
8. **The read contract is the port's.** Fetch-by-identity raises rather than returning nothing, a
   secondary lookup may return an optional, a list returns a sequence ordered by *the caller's* chosen
   sort, a count returns an integer. A hardcoded default order that ignores the filter's sort is a bug,
   not a default.
9. **Every driver error is translated before it escapes the adapter, and the fallback is mandatory.** The
   translator ends by returning a catalogue exception when no specific case matched; it never returns or
   re-raises the driver's own type. Letting it leak breaks the no-framework-exceptions-across-layers rule
   and turns what should be a conflict response into a 500.
10. **Pick the most specific catalogue exception, and give it identifying context.** A domain subclass
    beats a generic conflict, and "still referenced" beats "conflict" for a foreign key on delete. The
    context carries the offending field and the full constraint name, because the entrypoint and the
    tests both assert on them.
11. **Row-to-entity mapping is a pure function** — no IO, no logging — and it normalizes what the driver
    hands back, including giving a naive timestamp its offset. A helper lives at module level when more
    than one method or helper uses it, and as a private method when exactly one does.
12. **A schema change is a coordinated pair in one commit** — the table definition and one new migration.
    A later change is authored as a *new* migration, never by rewriting a shipped one, and generated
    migration output is a draft to hand-edit, not a result. The reverse operation is mandatory and
    reverses in the opposite order, because the migration round-trip test runs it — upgrade, downgrade,
    upgrade again against a real database.
13. **Extract a shared integrity-error mapper on repetition, never preemptively**, and migrate every
    existing repository in the commit that introduces it — partial adoption causes drift.
14. **Migrations run as a deploy step before the new code starts, and every schema change is compatible
    with the code still running.** Expand first: add what the new code needs while the old code keeps
    working against it. Contract later: dropping, renaming or tightening anything the old code still
    reads or writes — a column removed, a `NOT NULL` added, a constraint narrowed — ships in a later
    release, once no running code depends on it. A change that needs both halves is two revisions in two
    releases, never one.

## Inlined typing / import rules

Table module:

- The schema-construction names from the library root; dialect-specific types from the dialect module;
  the shared metadata imported relatively from `..metadata`.

Repository module:

- Domain imports absolute (`from myapp.domain.foos import Foo`); the table relative
  (`from ..tables.foos import foos_table`). **Never import the protocol the adapter satisfies** — a dead
  unused import, and structural subtyping needs none.
- Import only the domain exceptions this repository actually raises, not the whole catalogue.
- Type the driver's row so the mapper needs no ignore comment. Under the primary binding that is
  `.mappings()` → `RowMapping` accessed by key (`row["id"]`); never type a row as `object` with attribute
  access, which forces an ignore at every column. Where the library's own typing is too loose to read a
  field off — the affected-row count is the standing case — **narrow once with a cast, never silence with
  an ignore**.
- Parameters keep their domain types; never downcast to `dict`.

Both:

- No `from __future__ import annotations` (`python-style`). Full annotations on every method. No comments
  unless the *why* is non-obvious (`python-style`).

## Package wiring

`tables/__init__.py` must import the new table module and name it in `__all__` —
`from . import foos` beside `__all__ = ["foos"]` — otherwise migration autogenerate cannot see the table,
and the linter reads the bare import as unused and removes it. A table module's public name is a bare object, not a class, so it is
not wildcarded into the package (`python-packaging` carve-out 3); the repository imports it from its own
module (`from ..tables.foos import foos_table`). `repositories/__init__.py` re-exports the new adapter
class with the usual `from . import foo_repository` + wildcard. Mechanics: `python-packaging`.

## Hard stops

- Asked for a database `ENUM` type → stop, use a text column plus a check constraint (rule 4).
- Asked for length-bounded varchars → stop, use unbounded text plus the domain's own length rule
  (rule 4).
- A constraint name changes → stop, that is a breaking change; the table, the repository's
  translator and the revision all change in the same commit.
- The repository is asked to commit inside the unit-of-work-managed form → stop, that breaks atomicity.
- The repository is asked to log → stop, a repository never logs; the central error handler or the
  calling handler owns that (`python-style`).
- Asked for id generation inside the repository → stop, the application handler generates ids.
- The change includes a data migration (`backfill_*`, `seed_*`) → stop, that is a separate revision file; this
  skill covers DDL only.
