---
name: persistence
description: Use when code reads or writes a datastore, in any project whatever its architecture, and the question is an obligation rather than a file — who owns a transaction, where a driver error is translated and what its context carries, how constraint and table names are derived, how rows map back, which stored type a value gets, how a conflicting or older write is resolved, how a paged read resumes, how a schema change ships safely, and whether data-access code logs. Owns these store-generic rules and which of them bind given the store's properties; it binds no library and writes no file. The data-access files that satisfy them are the architecture family's — `flat-persistence` in the `pyhouse-flat` plugin, `hex-persistence` or `hex-store-repository` in the `pyhouse-hex` plugin — and the error classes, translation with the cause chained and its fallback are `exception-catalog`'s.
when_to_use: Also when asked whether a repository may commit, why a partial write happened, what a constraint should be named, whether to use a database enum type, whether a timestamp column needs a timezone, how to stop a stale update overwriting a newer one, how to deduplicate writes, how to page through a table without skipping rows, whether a migration is safe to deploy, or whether a repository should log.
---

# Persistence — the store-generic obligations

The obligations every program meets where it keeps data in a store, whatever its architecture family
and whatever the store. Each is stated so that it survives a change of driver, store or family; none
binds a library. The file that satisfies them — a table, a repository class, a revision — is written
under the project's own data-access skill: the architecture family's where one is installed, the
project's own layout where none is. **Which identifier a new row gets is not here**: the identity
scheme is the family's, because the two families answer it differently for reasons of their own.

## When to use vs. neighbours

- A flat-layered service's data-access package, its tables, its repository classes and where its
  migration history lives → `flat-persistence`, in the `pyhouse-flat` plugin, which binds these rules
  to one stack.
- A hexagonal service's relational adapter behind a port, its paired revision and its unit of work →
  `hex-persistence`, in the `pyhouse-hex` plugin; an aggregate on a key-value or document store →
  `hex-store-repository`, in the same plugin.
- The error classes a translation produces, translation with the cause chained, the mandatory
  fallback, and what `context` may and may not carry → `exception-catalog`.
- Which scope logs a failure the data-access code raised, and the event a success earns →
  `python-logging`.
- The declared type a row is mapped into, and which builtin holds an instant, an identifier or an
  exact decimal in memory → `python-style`.
- The store's connection settings, and where they are built → `python-settings`.
- What the repository class, a column or a constraint is called → `naming`; that a table name is
  derived by one declared rule is here (rule 11).
- Which identifier a new row gets and where it is minted → the architecture family — `hex-application`,
  in the `pyhouse-hex` plugin, and `flat-persistence`, in the `pyhouse-flat` plugin, are examples.
- Whether two stores, or two data-access packages, should be one → `coupling`.
- Several distributions sharing one store, and which of them owns its schema → `python-workspace`.
- Testing data-access code against a real store → `test-principles`, and the family's own test skill.

## Which rules bind — the store's properties

A rule whose property the store lacks has nothing to be true about. Answer these once per store,
before reading the rules:

| Does the store have… | If no, these do not apply |
|---|---|
| multi-statement transactions | rules 1, 2 — nothing spans statements, so nothing declares an owner |
| named constraints | rule 5, and the constraint name in rule 4 — there is no name for three artifacts to agree on |
| a conflict clause on write | rule 12, unless the store has a `MERGE` — otherwise resolution, rule 12's ordering guard included, is the store's merge-time mechanism (rule 13) |
| a declared schema — typed columns, constraints, secondary indexes | rules 8–11 — the record's shape is still a design decision, made where the store makes it |
| a schema versioned by migrations | rules 15, 16 |

**Rules 3, 4, 6, 7, 13, 14 and 17 hold for any store at all**, SQL or not — a columnar store, a document
store, a key-value store or a vendor-managed index. A store answering *no* to every question is not a
poor fit for this skill: the rules that lapse lapse because their subject does not exist.

## Rules

### Transactions

1. **Transaction ownership is one declared decision per callable.** A callable either *accepts* a live
   connection or transactional handle and never commits or rolls back, or *opens and owns* one for the
   whole of its work. The two forms are mutually exclusive for one callable, and no connection is held
   in instance state between calls. A joining callable is handed the open handle, never a factory: one
   that opens its own is in a different transaction, and the defect shows up as a partial write rather
   than an error. Which form a callable takes is part of its contract: it decides how a caller composes
   it and which isolation its test needs.
2. **Where one write spans more than one statement, it is one transaction, owned by the callable that
   spans them.** Splitting it across two connection blocks reopens the partial-write race the owning
   callable exists to close.

### Driver errors and constraint names

3. **The data-access edge is where a driver error is translated, on every public method.**
   Translation with the cause chained, the mandatory fallback and the choice of the most specific class
   are `exception-catalog`'s rules 8–10; what this rule adds is where they bind — nothing above the
   data-access code ever sees the driver's type, and that covers a read, and the opening of the
   connection and the transaction, which fail with the driver's errors as surely as a write does.
4. **The identifying context of a storage error is the offending field and the full constraint name,
   plus the store's own error code where it reports one.** What `context` may carry is
   `exception-catalog`'s rule 11; a library's class name is not one of these — it names the driver, not
   the failure, and changes with the driver. The constraint name is the one rule 5 generates, so the
   caller and the tests can assert on it.
5. **Constraint names are a contract, generated from one convention declared once.** A migration, a
   translator branch and a test must be able to name the same constraint without any of them inventing
   it; names left to the backend break all three. The translator matches on the full name the convention
   generates, never on a fragment of it — a fragment also matches a sibling constraint and reports the
   wrong field. Renaming one is a breaking change: the schema definition, the translator and the revision
   change in the same commit. The convention is declared in a module of its own that every table module
   imports — never inside a table module, which would make that table the root of the import graph.

### Rows and stored values

6. **Rows cross the data-access boundary as the program's own declared types, and the mapping is a pure
   function the data-access code owns.** No IO. It normalizes what the driver hands back, including
   giving a naive timestamp its offset. Where a natural key is normalized, it is normalized once, here,
   so one unit test can pin the form — in Python, never inside the store's query language, and only
   where the key's source defines the spellings it merges as one key; a key whose source tells them
   apart is stored as it arrives. The declared-type obligation itself is `python-style`'s.
7. **Every instant is stored with its offset.** A naive stored timestamp is a defect, whatever the
   in-memory type was (`python-style`). A default the store fills in is used only where the store is
   what stamps the row — a creation instant, which a row written by a migration then gets too; an
   instant fixed with the change, such as rule 12's ordering stamp, is written by the writer and never
   defaulted. A modification instant the program maintains is set in the update itself, because a
   store default fires only on insert.

### Schema

8. **Column types are a design decision, not a transcription of the record's fields.** Choose the stored
   type from what the value means and how it will be queried, and record the consequence where it
   bites — an on-delete choice is answered by what the data-access code's delete raises.
9. **A closed value set is a constraint over a text column, not a database enum type.** It then matches
   the program's own enum (`python-style` rule 12), and widening the set is an ordinary migration rather
   than a type alteration.
10. **Index what is filtered, joined and sorted on.** A foreign key gets no index for free, and a paged
    read's ordering column is as load-bearing as its filter's.
11. **A table name is derived from the record it holds by one rule the project declares once** —
    singular or plural, the same derivation for every table — so a name is derivable rather than
    remembered, and no table's name is chosen on its own. A table another project owns keeps the name
    its owner gave it.

### Conflicts, ordering and paged reads

12. **A conflicting row is resolved explicitly, the key matched on is never among the columns updated,
    and an empty update set resolves to *do nothing*.** The write names its conflict columns and its
    update columns; writing back the key you matched on is a no-op at best and a statement failure on a
    partial index. "Nothing to update" is a real case and must not become an update with an empty
    assignment list, which is a syntax error. Where an older write can arrive after a newer one for the
    same key, the update is guarded by the row's ordering stamp — a version or an instant fixed when the
    change was made or observed, the same on every delivery of it, never the time of a delivery attempt
    or of the write — so an input stamped older than what it would replace never replaces it, in the row
    or in a batch collapsed by key (rule 13).
13. **Deduplication and conflict resolution belong to the store's own write-time or merge-time
    mechanism, never to an application read-before-write per row.** Where the write can resolve a
    conflict, rule 12 says how; where the store deduplicates at merge time, the table's engine is chosen
    for it once, in the schema — keeping the newest by rule 12's ordering stamp wherever an older write
    can arrive after a newer one — and a read that must see one row per key before the merge asks the
    store for its deduplicated view. Looking up which rows already exist before inserting each chunk
    costs a round trip the store never needed, and it still admits the duplicates two concurrent runs
    write between one run's read and its write. **A column aggregated across writes is resolved the same
    way, in the write or the merge, never by reading it first.** **Inputs sharing one key are collapsed
    by that key before the statement is built** — the newest by rule 12's ordering stamp winning wherever
    that stamp guards the write, the last otherwise, or aggregated as the conflict clause would — because
    a store resolving conflicts per statement may refuse to touch one row twice within it. Collapsing a
    batch already in memory reads nothing from the store and is bounded by the batch, so it is not the
    read-before-write this rule forbids.
14. **A read resumed from a cursor orders by a total order, and the cursor carries every column of it.**
    A limited read resumed from the last row's value of a column that is not unique skips every row
    sharing that value beyond the page's edge — rows written in one batch share one timestamp, so a
    single boundary drops thousands of them with no error. Order by the column plus a unique tiebreaker
    and resume strictly after the pair (keyset pagination), or do not limit the read.

### Schema changes

15. **Migrations run as a deploy step, before the new code starts, and every schema change is compatible
    with the code still running.** During a deploy the old code keeps serving against the new schema, so
    a change that needs both halves lands in two releases, never in one revision. Expand first — add the
    table, or the column nullable or with a default the store fills in — while the old code keeps
    working against it. Contract in a later release, once nothing running reads or writes what is
    removed or tightened — a column dropped or renamed, a `NOT NULL` added, a constraint narrowed. A
    column added `NOT NULL` with no default passes a schema diff and a round trip over an empty
    database, then fails the deploy on a populated table.
16. **Each schema change is one new revision whose downgrade reverses its upgrade, in the opposite
    order, and a round trip proves it.** The suite runs the history up, down to the base and up again
    against a real store; a downgrade nothing runs is a reverse path nobody has proven. A later change is
    a new revision, never an edit to a shipped one, and a revision a tool generated is a draft, reviewed
    against rule 15 before it is committed.

### Logging

17. **Data-access code never logs.** A failure is translated (rule 3) and propagates to the scope that
    stops it, which logs it once; a success is the caller's to log (`python-logging`).

## Hard stops

- Choosing or adding the error class a translation raises → stop, use `exception-catalog`.
- Deciding which identifier a new row gets, or where it is minted → stop, that is the architecture
  family's identity scheme (`hex-application`, in the `pyhouse-hex` plugin; `flat-persistence`, in the
  `pyhouse-flat` plugin); this skill states no id policy.
- Deciding where a data-access package sits, or what its files are → stop, use the architecture
  family's data-access skill (`flat-persistence`, in the `pyhouse-flat` plugin; `hex-persistence` or
  `hex-store-repository`, in the `pyhouse-hex` plugin), or the project's own layout where none applies.
