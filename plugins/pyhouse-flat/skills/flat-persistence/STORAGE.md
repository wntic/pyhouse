# flat-persistence — the storage class

Topic file of `flat-persistence`. The mechanism-free obligations are rules 2, 3, 4, 5, 6 and 7 in
`SKILL.md`; what follows is the **SQLAlchemy async + asyncpg** binding that satisfies them.

The class that owns a write, the translator that turns the driver's error into the service's own, and the
pure function that maps rows back into the service's declared types.

## The storage class — SQLAlchemy async (one declared transaction owner)

`src/myapp/storage/foo_storage.py` — a concrete class, no `Protocol` (rule 2). **Every public method opens
and owns its transaction**, which is this class's declared half of rule 3; the helpers it calls accept
the connection and never commit.

```python
from collections.abc import Sequence
from datetime import UTC
from uuid import UUID

from sqlalchemy import select
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

__all__ = ["FooStorage", "normalize_reference"]

_DRIVER_ERRORS = (DBAPIError, OSError)  # asyncpg reports a refused connection as the socket's OSError
_REFUSED_DATA_CLASSES = frozenset({"22", "23"})  # SQLSTATE classes: data exception, integrity violation


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
    driver_error = orig.__cause__ if orig is not None else None  # asyncpg's own exception
    sqlstate = getattr(driver_error, "sqlstate", None)
    constraint = getattr(driver_error, "constraint_name", None)
    if constraint == "uq_foos_reference":
        return FooAlreadyRecordedError(
            "a foo with this reference is already recorded",
            {"field": "reference", "constraint": constraint},
        )
    if sqlstate is not None and sqlstate[:2] in _REFUSED_DATA_CLASSES:
        return StorageWriteRejectedError("the datastore rejected the write", {"constraint": constraint})
    return StorageUnavailableError("the datastore could not complete the operation", {"sqlstate": sqlstate})


class FooStorage:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def record_batch(self, foos: Sequence[Foo]) -> None:
        """Owns the transaction: the foos and their labels land together or not at all."""
        if not foos:
            return
        try:
            async with self._engine.begin() as conn:
                written = await bulk_upsert_returning(
                    conn,
                    foo_table,
                    [_to_row(foo) for foo in foos],
                    conflict_columns=["reference"],
                    update_columns=["name", "observed_at"],
                    returning_columns=["id", "reference"],
                )
                foo_id_by_reference = {row["reference"]: row["id"] for row in written}
                await bulk_upsert(
                    conn,
                    bar_table,
                    [
                        {
                            "foo_id": foo_id_by_reference[normalize_reference(foo.reference)],
                            "label": label,
                        }
                        for foo in foos
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
```

The class takes its engine as a **constructor argument**, never reaching for the factory itself, so a
test can point it at a container without touching the environment.

`record_batch` is the worked case of rule 4: the second write needs an id the first one produced, so the
two statements sit inside **one** `engine.begin()`. Split across two connection blocks, a failure in the
second leaves parentless rows behind.

`record_new` is the write for a caller that must not overwrite: a plain insert, so a reference already
recorded fails on `uq_foos_reference` and reaches the caller as `FooAlreadyRecordedError` — the branch of
`_translate` that `record_batch`, which resolves that conflict itself, can never reach.

`update_columns=[]` on the second write resolves to *do nothing*: a label already recorded for that foo is
not an error, and an update with an empty assignment list is a syntax error.

**The whole engine block sits inside the `try`, in every public method, the read included.** Opening
the connection, beginning the transaction and running a read fail with the driver's errors as surely as
a write does, so a `try` placed inside `async with` lets a refused connection, a failed `begin` or a
missing table leave the package as the driver's type. `get_by_reference` raises `FooNotFoundError` after
the block, because an absent row is not a driver failure. Two types reach the `except`: SQLAlchemy wraps
what the driver raises in its own `DBAPIError`, except a refused connection, which asyncpg reports as the
socket's `OSError` and SQLAlchemy lets through unwrapped.

`_translate` **ends by returning a catalogue exception**: the last statement is the fallback, not a
re-raise of the driver's type. Without it every caller's `except` clause ends up written against a
library it was supposed never to import. The one constraint a caller acts on becomes
`FooAlreadyRecordedError`; any other refusal of the data — an SQLSTATE in the data-exception or
integrity-violation class — becomes `StorageWriteRejectedError`; everything else, a failed read and a
failed connection among them, becomes `StorageUnavailableError`, a name that holds for a read as well as
a write. It matches on the constraint name and the SQLSTATE the driver reports — never on the error's
text, and never on SQLAlchemy's subclass, which its asyncpg adapter assigns to only some SQLSTATEs — and
puts the name or the SQLSTATE, not the stringified error, into `context`. SQLAlchemy wraps the asyncpg
exception in an adapter, so both are read off the original that the adapter chains as its cause. The classes and their
statuses are the service's catalogue, stated once in `flat-layered`'s `CATALOG.md`.

`_to_foo` is a **pure function**: no IO, no logging. It normalizes what the driver hands back — the
natural key's one form, a naive timestamp's offset — so one unit test pins both and nothing above this
package sees a column name.

The conflict column is excluded from `update_columns`: writing back the key you matched on is a no-op at
best and, on a partial index, a way to make the statement fail.
