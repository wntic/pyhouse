# flat-persistence — the repository class

Topic file of `flat-persistence`. The mechanism-free obligations are rules 2, 3, 4, 5, 6, 7 and 18 in
`SKILL.md`; what follows is the **SQLAlchemy async + asyncpg** binding that satisfies them.

The class that owns a write, the translator that turns the driver's error into the service's own, the
pure function that maps rows back into the service's declared types.

## The repository class — SQLAlchemy async (one declared transaction owner)

`src/myapp/postgres/foo_repository.py` — a concrete class, no `Protocol` (rule 2), named for the record
it stores plus `Repository` (`naming`). **Every public method opens and owns its transaction**, which is
this class's declared half of rule 3; the helper it calls accepts the connection and never commits.

```python
from collections.abc import Sequence
from datetime import UTC

from sqlalchemy.engine import RowMapping
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine

from myapp.exceptions import MyappError, StorageUnavailableError, StorageWriteRejectedError
from myapp.schemas import Foo, FooReference

from .engine import bulk_upsert
from .foo_table import foo_table

__all__ = ["FooRepository"]

_DRIVER_ERRORS = (DBAPIError, OSError)
_REFUSED_DATA_CLASSES = frozenset({"22", "23"})  # SQLSTATE classes: data exception, integrity violation


def _to_row(foo: Foo) -> dict[str, object]:
    return {"reference": foo.reference, "name": foo.name, "observed_at": foo.observed_at}


def _to_foo(row: RowMapping) -> Foo:
    observed_at = row["observed_at"]
    return Foo(
        reference=FooReference(row["reference"]),
        name=row["name"],
        observed_at=observed_at if observed_at.tzinfo else observed_at.replace(tzinfo=UTC),
    )


def _translate(exc: DBAPIError | OSError) -> MyappError:
    orig = exc.orig if isinstance(exc, DBAPIError) else None
    driver_error = orig.__cause__ if orig is not None else None
    sqlstate = getattr(driver_error, "sqlstate", None)
    if sqlstate is not None and sqlstate[:2] in _REFUSED_DATA_CLASSES:
        return StorageWriteRejectedError(
            "the datastore rejected the write",
            {"sqlstate": sqlstate, "constraint": getattr(driver_error, "constraint_name", None)},
        )
    return StorageUnavailableError(
        "the datastore could not complete the operation",
        {"sqlstate": sqlstate},
    )


class FooRepository:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    async def record_batch(self, foos: Sequence[Foo]) -> None:
        latest_by_reference = {foo.reference: foo for foo in foos}
        if not latest_by_reference:
            return
        try:
            async with self._engine.begin() as conn:
                await bulk_upsert(
                    conn,
                    foo_table,
                    [_to_row(foo) for foo in latest_by_reference.values()],
                    conflict_columns=["reference"],
                    update_columns=["name", "observed_at"],
                )
        except _DRIVER_ERRORS as exc:
            raise _translate(exc) from exc
```

The class takes its engine as a **constructor argument**, never reaching for the factory itself, so a
test can point it at a container without touching the environment.

`record_batch` is rule 18's worked case: a foo already recorded is resolved by the statement's own
conflict clause, never by asking which references exist before writing. **Two foos in one batch sharing
a reference are collapsed before the statement, the later one winning** — Postgres refuses an
`ON CONFLICT DO UPDATE` that touches one row twice (SQLSTATE `21000`), and would fail the whole batch as
`StorageUnavailableError` over data that was never unavailable. The collapse reads nothing from the
store, so it is not the read-before-write rule 18 forbids. It is keyed on the reference exactly as the
table stores it, because that is the key the constraint sees.

**Where one write spans statements** — a parent and its children, a later statement that needs keys an
earlier one resolved — every statement sits inside this one `engine.begin()`, and the keys come back
through one read-back helper beside `bulk_upsert` in `engine.py` (rules 4 and 11). Split across two
connection blocks, a failure in the later statement leaves the earlier one's rows behind.

**The whole engine block sits inside the `try`, in every public method, a read as much as a write.** Opening
the connection, beginning the transaction and running a read fail with the driver's errors as surely as
a write does, so a `try` placed inside `async with` lets a refused connection, a failed `begin` or a
missing table leave the package as the driver's type. Two types reach the `except`: SQLAlchemy wraps
what the driver raises in its own `DBAPIError`, except a refused connection, which asyncpg reports as the
socket's `OSError` and SQLAlchemy lets through unwrapped — which is why `_DRIVER_ERRORS` names both.

`_translate` **ends by returning a catalogue exception**: the last statement is the fallback, not a
re-raise of the driver's type. Without it every caller's `except` clause ends up written against a
library it was supposed never to import. A refusal of the data — an SQLSTATE in the data-exception or
integrity-violation class — becomes `StorageWriteRejectedError`; everything else, a failed read and a
failed connection among them, becomes `StorageUnavailableError`, a name that holds for a read as well as
a write. It matches on the SQLSTATE and the constraint name the driver reports — never on the error's
text, and never on SQLAlchemy's subclass, which its asyncpg adapter assigns to only some SQLSTATEs — and
puts them, not the stringified error, into `context`. SQLAlchemy wraps the asyncpg exception in an
adapter, and the adapter chains asyncpg's own exception as its `__cause__`, so both are read off that.
The classes are the service's own, declared in its one catalogue (`exception-catalog`). **Where a caller
acts on one particular constraint, that constraint gets a branch of its own ahead of the SQLSTATE-class
check, matched on the generated constraint name (rule 8)** and returning the class the caller catches,
with the offending field and that name in its `context` (rule 6).

**A second repository class in the package shares the driver-error tuple and the fallback rather than
copying them.** Only the constraint branches belong to one class; the tuple, the SQLSTATE classes and
the final two returns are the store's, so when a second class arrives they move into one module of the
package — `errors.py`, exposing a public translator each class calls after checking its own
constraints — instead of travelling into every repository module.

`_to_foo` is a **pure function**, the one every read the class has maps its rows through: no IO, no
logging. It normalizes what the driver hands back — a naive
timestamp's offset — so one unit test pins it and nothing above this package sees a column name.

The conflict column is excluded from `update_columns`: writing back the key you matched on is a no-op at
best and, on a partial index, a way to make the statement fail.
