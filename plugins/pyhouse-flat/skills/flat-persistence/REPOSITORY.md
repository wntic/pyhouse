# flat-persistence — the repository class

Topic file of `flat-persistence`. The mechanism-free obligations are rules 1, 2, 3, 4 and 10 in
`SKILL.md`, and `persistence` rules 1, 2, 4–8 and 15–17; what follows is the **SQLAlchemy async +
asyncpg** binding that satisfies them.

The class that owns a write and builds its statements, the translator that turns the driver's error
into the service's own, the pure function that maps rows back into the service's declared types.

## The repository class — SQLAlchemy async (one declared transaction owner)

`src/myapp/postgres/foo_repository.py` — a concrete class, no `Protocol` (rule 1), named for the record
it stores plus `Repository` (`naming`). **Every public method opens and owns its transaction**, which is
this class's declared half of `persistence` rule 1, and it builds the statements it runs.

```python
from collections.abc import Sequence

from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncEngine

from myapp.exceptions import MyappError, StorageUnavailableError, StorageWriteRejectedError
from myapp.schemas import Foo

from .foo_table import foo_table

__all__ = ["FooRepository"]

_DRIVER_ERRORS = (DBAPIError, OSError)
_REFUSED_DATA_CLASSES = frozenset({"22", "23"})
_BIND_PARAMETER_CAP = 32767
_CHUNK_SIZE = _BIND_PARAMETER_CAP // len(foo_table.columns)


class FooRepository:
    def __init__(self, engine: AsyncEngine, *, chunk_size: int = _CHUNK_SIZE) -> None:
        self._engine = engine
        self._chunk_size = chunk_size

    async def record_batch(self, foos: Sequence[Foo]) -> None:
        latest_by_reference = {foo.reference: foo for foo in foos}
        rows = [
            {"reference": foo.reference, "name": foo.name, "observed_at": foo.observed_at}
            for foo in latest_by_reference.values()
        ]
        try:
            async with self._engine.begin() as conn:
                for start in range(0, len(rows), self._chunk_size):
                    statement = insert(foo_table).values(rows[start : start + self._chunk_size])
                    await conn.execute(
                        statement.on_conflict_do_update(
                            index_elements=[foo_table.c.reference],
                            set_={"name": statement.excluded.name, "observed_at": statement.excluded.observed_at},
                        )
                    )
        except _DRIVER_ERRORS as exc:
            raise _translate(exc) from exc


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
```

**The batch is optional.** A method that takes one `Foo` — a webhook's `record(foo)` — runs one
`insert(foo_table).values(...).on_conflict_do_update(...)` inside its `engine.begin()`: no cap, no chunk
constant, no `chunk_size` argument, no collapse and no loop — those exist only where a method takes a
batch — while the ordering guard stays wherever the stamp guards the write (`persistence` rule 16).

The class takes its engine as a **constructor argument**, never reaching for the factory itself, so a
test can point it at a container without touching the environment. The chunk size defaults to the named
constant and is keyword-only, so a test can cross a chunk boundary with five rows.

**The chunk size is computed once, from the driver's cap and the table's width, never written as a
literal** (rule 3): 32,767 bind parameters under asyncpg, because the Postgres wire protocol carries the
count in a 16-bit field, divided by the columns one row binds. The cap is the store's and the width the
table's: with one class the cap sits beside the statement, and with a second it moves to `engine.py`
(below). Each chunk is one multi-row statement (rule 2), and its conflict clause is derived from that
same statement's `excluded` row, so the update set names the incoming values of the row that conflicted
(`persistence` rule 15). The set is declared here, per write, and never holds the key matched on; a
write with nothing to update on conflict says `on_conflict_do_nothing()` instead, because a `DO UPDATE` with an empty `SET`
is a syntax error.

`record_batch` is `persistence` rule 17's worked case: a foo already recorded is resolved by the
statement's own conflict clause, never by asking which references exist before writing. **Two foos in
one batch sharing a reference are collapsed before the statement** — the newest by the ordering stamp
winning where that stamp guards the write, the later one otherwise or among equals (`persistence`
rules 16 and 17) — because Postgres refuses an `ON CONFLICT DO UPDATE` that touches one row twice
(SQLSTATE `21000`), and would fail the whole batch as `StorageUnavailableError` over data that was never
unavailable. It is keyed on the reference exactly as the
table stores it, because that is the key the constraint sees. An empty batch runs no statement.

**Where one write spans statements** — a parent and its children, a later statement that needs keys an
earlier one resolved — every statement sits inside this one `engine.begin()`, and the keys come back
from the earlier statement's own `.returning(...)`, collected chunk by chunk (`persistence` rule 2,
and rule 4 in `SKILL.md`). Under an empty update set `DO NOTHING` returns no row for the conflict it
skipped, so a write whose keys are read back declares a non-empty one.

**The whole engine block sits inside the `try`, in every public method, a read as much as a write**
(`persistence` rule 4). Two types reach the `except`: SQLAlchemy wraps
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
check, matched on the full generated constraint name (`persistence` rule 7)** and returning the class
the caller catches, with the offending field and that name in its `context` (`persistence` rule 6).

**A second repository class shares the store's translation** (`persistence` rule 5): the tuple, the
SQLSTATE classes and the final two returns move into `errors.py`, exposing a public translator each
class calls after checking its own constraints, and the bind-parameter cap moves to `engine.py` as a
public `BIND_PARAMETER_CAP` beside `get_engine`, each class dividing it by its own table's width.

Where the class reads, every read maps its rows through one **pure function** (`_to_foo`,
`persistence` rule 8), so one unit test pins it and nothing above this package sees a column name.
