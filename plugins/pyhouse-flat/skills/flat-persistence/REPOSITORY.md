# flat-persistence — the repository class

Topic file of `flat-persistence`. The mechanism-free obligations are rules 2, 3, 4, 5, 6, 7, 18 and 19 in
`SKILL.md`; what follows is the **SQLAlchemy async + asyncpg** binding that satisfies them.

The class that owns a write, the translator that turns the driver's error into the service's own, the
pure function that maps rows back into the service's declared types, and a read resumed from a cursor.

## The repository class — SQLAlchemy async (one declared transaction owner)

`src/myapp/postgres/foo_repository.py` — a concrete class, no `Protocol` (rule 2), named for the record
it stores plus `Repository` (`naming`). **Every public method opens and owns its transaction**, which is
this class's declared half of rule 3; the helpers it calls accept the connection and never commit.

```python
from collections.abc import Sequence
from datetime import UTC
from uuid import UUID

from sqlalchemy import select, tuple_
from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine

from myapp.exceptions import (
    FooAlreadyRecordedError,
    FooNotFoundError,
    MyappError,
    StorageUnavailableError,
    StorageWriteRejectedError,
)
from myapp.schemas import Foo

from .engine import bulk_upsert, bulk_upsert_returning
from .foo_table import bar_table, foo_table

__all__ = ["FooRepository", "normalize_reference"]

_DRIVER_ERRORS = (DBAPIError, OSError)
_REFUSED_DATA_CLASSES = frozenset({"22", "23"})  # SQLSTATE classes: data exception, integrity violation
_FOO_ORDER = (foo_table.c.observed_at, foo_table.c.id)


def normalize_reference(reference: str) -> str:
    """The one normalized form of the natural key, used on the way in and on the way out."""
    return reference.strip().lower()


def _to_row(foo: Foo) -> dict[str, object]:
    return {
        "reference": normalize_reference(foo.reference),
        "name": foo.name,
        "observed_at": foo.observed_at,
    }


def _to_foo(rows: Sequence[RowMapping]) -> Foo:
    head = rows[0]
    observed_at = head["observed_at"]
    return Foo(
        id=head["id"],
        reference=normalize_reference(head["reference"]),
        name=head["name"],
        observed_at=observed_at if observed_at.tzinfo else observed_at.replace(tzinfo=UTC),
        labels=tuple(sorted(row["label"] for row in rows if row["label"] is not None)),
    )


def _translate(exc: DBAPIError | OSError) -> MyappError:
    orig = exc.orig if isinstance(exc, DBAPIError) else None
    driver_error = orig.__cause__ if orig is not None else None
    sqlstate = getattr(driver_error, "sqlstate", None)
    constraint = getattr(driver_error, "constraint_name", None)
    if constraint == "uq_foos_reference":
        return FooAlreadyRecordedError(
            "a foo with this reference is already recorded",
            {"field": "reference", "constraint": constraint},
        )
    if sqlstate is not None and sqlstate[:2] in _REFUSED_DATA_CLASSES:
        return StorageWriteRejectedError("the datastore rejected the write", {"constraint": constraint})
    return StorageUnavailableError(
        "the datastore could not complete the operation",
        {"sqlstate": sqlstate},
    )


class FooRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def record_batch(self, foos: Sequence[Foo]) -> None:
        """Owns the transaction: the foos and their labels land together or not at all."""
        latest_by_reference = {normalize_reference(foo.reference): foo for foo in foos}
        if not latest_by_reference:
            return
        try:
            async with self._engine.begin() as conn:
                written = await bulk_upsert_returning(
                    conn,
                    foo_table,
                    [_to_row(foo) for foo in latest_by_reference.values()],
                    conflict_columns=["reference"],
                    update_columns=["name", "observed_at"],
                    returning_columns=["id", "reference"],
                )
                foo_id_by_reference = {row["reference"]: row["id"] for row in written}
                await bulk_upsert(
                    conn,
                    bar_table,
                    [
                        {"foo_id": foo_id_by_reference[reference], "label": label}
                        for reference, foo in latest_by_reference.items()
                        for label in foo.labels
                    ],
                    conflict_columns=["foo_id", "label"],
                    update_columns=[],
                )
        except _DRIVER_ERRORS as exc:
            raise _translate(exc) from exc

    async def record_new(self, foo: Foo) -> None:
        """Owns the transaction: a reference already recorded is refused, never updated."""
        try:
            async with self._engine.begin() as conn:
                inserted = await conn.execute(foo_table.insert().values(_to_row(foo)).returning(foo_table.c.id))
                foo_id: UUID = inserted.scalar_one()
                await bulk_upsert(
                    conn,
                    bar_table,
                    [{"foo_id": foo_id, "label": label} for label in foo.labels],
                    conflict_columns=["foo_id", "label"],
                    update_columns=[],
                )
        except _DRIVER_ERRORS as exc:
            raise _translate(exc) from exc

    async def get_by_reference(self, reference: str) -> Foo:
        try:
            async with self._engine.connect() as conn:
                result = await conn.execute(
                    select(foo_table, bar_table.c.label)
                    .join(bar_table, bar_table.c.foo_id == foo_table.c.id, isouter=True)
                    .where(foo_table.c.reference == normalize_reference(reference))
                )
                rows = result.mappings().all()
        except _DRIVER_ERRORS as exc:
            raise _translate(exc) from exc
        if not rows:
            raise FooNotFoundError("no foo with this reference", {"reference": reference})
        return _to_foo(rows)

    async def list_after(self, after: Foo | None, limit: int) -> list[Foo]:
        """The next `limit` foos in (observed_at, id) order, strictly after `after`."""
        page = select(foo_table.c.id).order_by(*_FOO_ORDER).limit(limit)
        if after is not None:
            page = page.where(tuple_(*_FOO_ORDER) > tuple_(after.observed_at, after.id))
        page_ids = page.subquery()
        try:
            async with self._engine.connect() as conn:
                result = await conn.execute(
                    select(foo_table, bar_table.c.label)
                    .join(page_ids, page_ids.c.id == foo_table.c.id)
                    .join(bar_table, bar_table.c.foo_id == foo_table.c.id, isouter=True)
                    .order_by(*_FOO_ORDER)
                )
                rows = result.mappings().all()
        except _DRIVER_ERRORS as exc:
            raise _translate(exc) from exc
        rows_by_id: dict[UUID, list[RowMapping]] = {}
        for row in rows:
            rows_by_id.setdefault(row["id"], []).append(row)
        return [_to_foo(foo_rows) for foo_rows in rows_by_id.values()]
```

The class takes its engine as a **constructor argument**, never reaching for the factory itself, so a
test can point it at a container without touching the environment.

`record_batch` is the worked case of rule 4: the second write needs an id the first one produced, so the
two statements sit inside **one** `engine.begin()`. Split across two connection blocks, a failure in the
second leaves parentless rows behind. It is also rule 18's: a foo already recorded is resolved by the
statement's own conflict clause, never by asking which references exist before writing. **Two foos in one
batch whose references normalize to one key are collapsed before the first statement, the later one
winning** — Postgres refuses an `ON CONFLICT DO UPDATE` that touches one row twice (SQLSTATE `21000`),
and would fail the whole batch as `StorageUnavailableError` over data that was never unavailable. The
collapse is keyed on the normalized form, because that is the key the constraint sees; it reads nothing
from the store, so it is not the read-before-write rule 18 forbids.

`record_new` is the write for a caller that must not overwrite: a plain insert, so a reference already
recorded fails on `uq_foos_reference` and reaches the caller as `FooAlreadyRecordedError` — the branch of
`_translate` that `record_batch`, which resolves that conflict itself, can never reach.

`update_columns=[]` on the second write resolves to *do nothing*: a label already recorded for that foo is
not an error, and an update with an empty assignment list is a syntax error.

**The whole engine block sits inside the `try`, in every public method, the reads included.** Opening
the connection, beginning the transaction and running a read fail with the driver's errors as surely as
a write does, so a `try` placed inside `async with` lets a refused connection, a failed `begin` or a
missing table leave the package as the driver's type. `get_by_reference` raises `FooNotFoundError` after
the block, because an absent row is not a driver failure. Two types reach the `except`: SQLAlchemy wraps
what the driver raises in its own `DBAPIError`, except a refused connection, which asyncpg reports as the
socket's `OSError` and SQLAlchemy lets through unwrapped — which is why `_DRIVER_ERRORS` names both.

`_translate` **ends by returning a catalogue exception**: the last statement is the fallback, not a
re-raise of the driver's type. Without it every caller's `except` clause ends up written against a
library it was supposed never to import. The one constraint a caller acts on becomes
`FooAlreadyRecordedError`; any other refusal of the data — an SQLSTATE in the data-exception or
integrity-violation class — becomes `StorageWriteRejectedError`; everything else, a failed read and a
failed connection among them, becomes `StorageUnavailableError`, a name that holds for a read as well as
a write. It matches on the constraint name and the SQLSTATE the driver reports — never on the error's
text, and never on SQLAlchemy's subclass, which its asyncpg adapter assigns to only some SQLSTATEs — and
puts the name or the SQLSTATE, not the stringified error, into `context`. SQLAlchemy wraps the asyncpg
exception in an adapter, and the adapter chains asyncpg's own exception as its `__cause__`, so both are
read off that. The classes and their statuses are the service's catalogue, stated once in
`flat-layered`'s `CATALOG.md`.

**A second repository class in the package shares the driver-error tuple and the fallback rather than
copying them.** Only the constraint branches belong to one class; the tuple, the SQLSTATE classes and
the final two returns are the store's, so when a second class arrives they move into one module of the
package — `errors.py`, exposing a public translator each class calls after checking its own
constraints — instead of travelling into every repository module.

`_to_foo` is a **pure function**: no IO, no logging. It normalizes what the driver hands back — the
natural key's one form, a naive timestamp's offset — so one unit test pins both and nothing above this
package sees a column name.

The conflict column is excluded from `update_columns`: writing back the key you matched on is a no-op at
best and, on a partial index, a way to make the statement fail.

`list_after` is rule 19's worked case, for a job that walks everything stored in bounded pages and
resumes where it left off. The order is `(observed_at, id)` — the timestamp a caller cares about plus
the unique key that breaks its ties — and the next page starts strictly after the last foo's pair, so
rows written in one batch with one timestamp are neither skipped at a page edge nor read twice. The
limit applies to foos in a subquery before the label join, because a limit on the joined rows would cut
one foo's labels in half. The caller passes the last foo of the previous page back as `after`, so the
cursor is the whole of the order, never the timestamp alone.
