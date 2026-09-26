# hex-persistence — the `Table`

Topic file of `hex-persistence`. The mechanism-free obligations are rules 1–5 in `SKILL.md`; what
follows is the **SQLAlchemy Core + Postgres** binding that satisfies them.

Column types are a **design decision** — a JSON column, an array column, a check constraint, a foreign
key — not a mechanical transcription of the entity's fields. That is why the column-type rules come
first.

## Naming convention (load-bearing — do not deviate)

Defined once in `infrastructure/postgres/metadata.py`:

```python
# src/myapp/infrastructure/postgres/metadata.py
from sqlalchemy import MetaData

__all__ = ["metadata"]

metadata = MetaData(
    naming_convention={
        "ix": "ix_%(column_0_label)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
)
```

The names it generates are exactly what the repository's translator (`REPOSITORY.md`) matches on:

- PK: `pk_foos`
- unique on `name`: `uq_foos_name`
- index on `bar_id`: `ix_foos_bar_id`
- FK `foos.bar_id → bars.id`: `fk_foos_bar_id_bars`
- check with `name="name_non_empty"`: `ck_foos_name_non_empty`

**For a `CheckConstraint`, `name=` is the suffix** — the convention prepends `ck_<table>_`. Pick a
stable, descriptive suffix.

## Template — table file

```python
# src/myapp/infrastructure/postgres/tables/foos.py
from sqlalchemy import CheckConstraint, Column, DateTime, ForeignKey, Table, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from ..metadata import metadata

__all__ = ["foos_table"]

foos_table: Table = Table(
    "foos",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("name", Text, nullable=False, unique=True),
    Column(
        "bar_id",
        UUID(as_uuid=True),
        ForeignKey("bars.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    ),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now(), index=True),
    Column("updated_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
    CheckConstraint("char_length(name) > 0", name="name_non_empty"),
)
```

`index=True` on a column is the single-column index with no `name=`: the convention names it
`ix_foos_bar_id` and `ix_foos_created_at`, exactly what the revision writes out.

## Template — append-only table with a store-generated key

A record nothing addresses by an application-minted id — an audit trail, an event log — takes a key the
store generates, and the repository inserts without one (`hex-patterns`' audit repository):

```python
# src/myapp/infrastructure/postgres/tables/audit_events.py
from sqlalchemy import BigInteger, Column, DateTime, Identity, Table, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func

from ..metadata import metadata

__all__ = ["audit_events_table"]

audit_events_table: Table = Table(
    "audit_events",
    metadata,
    Column("id", BigInteger, Identity(), primary_key=True),
    Column("subject_id", UUID(as_uuid=True), nullable=False, index=True),
    Column("action", Text, nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False, server_default=func.now()),
)
```

The convention names its key `pk_audit_events` and its index `ix_audit_events_subject_id`. Its revision
is an ordinary one (`REVISION.md`), writing the key as `sa.Column("id", sa.BigInteger, sa.Identity(),
primary_key=True)` and creating the index by that name.

## Rules — column types

- **UUID:** `UUID(as_uuid=True)` from the dialect module. Never plain `UUID()`.
- **Timestamps:** `DateTime(timezone=True)` with `server_default=func.now()` for `created_at` /
  `updated_at`. Never naive.
- **Text:** `Text`, not `String(n)`. No length-bounded varchars — a length limit is a domain
  constraint, enforced by a check constraint the domain owns, not a storage decision that should need a
  migration to change.
- **Integers:** `Integer`; `SmallInteger` only when the domain is genuinely bounded.
- **Booleans:** `Boolean`.
- **Enums:** `Text` plus a `CheckConstraint` listing the valid values — **not** a database `ENUM` type.
  This matches the domain `StrEnum`, and changing the value set is then an ordinary check-constraint
  migration rather than a type alteration.

## Rules — FK `ondelete`

- `RESTRICT` — the target is a **referenced lookup**. The repository translates the resulting
  `IntegrityError` to `InUseError`.
- `CASCADE` — the target is the **parent of an owned child** (`foo_children.foo_id → foos.id`).
- `SET NULL` — only when the column is nullable and absence carries domain meaning. Rare.

Pick once, and document the consequence in the repository's `delete`.

## Rules — indexes

- Index every FK column you filter or join on. The library does **not** create FK indexes automatically.
- Index columns used in a list endpoint's `ORDER BY` and in a filter record's `WHERE`.
- Single-column index name: `ix_<table>_<col>`. A composite index is named explicitly with the same
  prefix.
- **A bare string argument to `Index` is a COLUMN NAME, not an expression.**
  `Index("ix_foos_name_lower", "lower(name)")` makes the library look for a column literally named
  `lower(name)` and raise at `MetaData` construction — lint and type-check stay green, only constructing
  the table catches it. A **functional index** wraps the SQL:
  `Index("ix_foos_name_lower", text("lower(name)"))`.
- **About to pass a SQL expression to an index or a check constraint as a bare string → stop, wrap it.**
  It raises at table-construct time with lint and type-check green.

## Rules — constraint names (load-bearing)

- **In the `Table`, pass no `name=` for a primary key, an FK, or a single-column unique or index** — the
  convention builds the right name out of the table and that one column.
- **A composite unique constraint carries an explicit `name=`.** The convention interpolates the
  **first** column only, so an auto-name silently drops the rest: `UniqueConstraint("foo_id", "position")`
  and `UniqueConstraint("foo_id", "kind")` on one table both come out `uq_<table>_foo_id` — two different
  constraints under a single name, and the translator left matching a name the database does not hold. A
  composite index is named explicitly for the same reason. **A composite unique constraint or index
  written without an explicit `name=` → stop, name it** — the two collide otherwise.
- **Always pass `name=` (the suffix) for a `CheckConstraint`** so the convention can prepend
  `ck_<table>_`. Writing the full name yields `ck_foos_ck_foos_name_non_empty`.
- **The same rules hold inside a revision's `op.create_table`.** `env.py` hands the shared metadata to
  the migration tool as `target_metadata`, so `op.create_table` builds on the convention exactly as the
  `Table` does.
- Renaming one is a breaking change: the repository's map changes in the same commit.

## Rules — junction and owned-children tables

- **Junction table:** a composite primary key across both FKs and no surrogate `id`; both columns
  `primary_key=True`; index the non-leading FK column.
- **Owned-children table:** a surrogate `id`, an FK to the parent with `ondelete="CASCADE"`, and a unique
  constraint on the natural identity —
  `UniqueConstraint("foo_id", "position", name="uq_foo_children_foo_position")`.

## Rules — server vs application defaults

- `created_at` / `updated_at` use `server_default=func.now()`, so existing rows behave correctly during a
  migration.
- Application-managed `updated_at` on update: the repository sets it explicitly with `func.now()` in the
  `UPDATE`. A server default fires only on `INSERT`.
- A domain-meaningful default uses `server_default="…"`, and the value stays **identical** between the
  table definition and the revision.

