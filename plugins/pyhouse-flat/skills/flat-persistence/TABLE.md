# flat-persistence — the table

Topic file of `flat-persistence`. The mechanism-free obligations are rule 2 in `SKILL.md`, and
`persistence` rules 7, 9 and 13; what follows is the **SQLAlchemy Core on Postgres** binding that
satisfies them.

## The table — SQLAlchemy Core on Postgres

Every primary key is a **UUIDv7**, minted client-side through the `uuid6` package's `uuid7()` — never
`uuid.uuid4()` and never a database-side `server_default`. UUIDv7 is time-ordered, so ids inserted
together sort and index together; `uuid.uuid4()`'s randomness scatters otherwise-related rows across a
b-tree index for no benefit, and a database-side default means the writer cannot know the id it just
created without reading it back. `uuid6.uuid7()` returns a `uuid.UUID` subclass, so it drops straight
into `Column(..., default=uuid7)`. A table another project owns declares its key as the owner defined it, with no default.

`src/myapp/postgres/foo_table.py`:

```python
from sqlalchemy import Column, DateTime, String, Table
from sqlalchemy.dialects.postgresql import UUID
from uuid6 import uuid7

from .metadata import metadata

foo_table = Table(
    "foos",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid7),
    Column("reference", String, nullable=False, unique=True),
    Column("name", String, nullable=False),
    Column("observed_at", DateTime(timezone=True), nullable=False),
)
```

`foos` is the plural snake-case of the record the table holds — the one derivation a project declares
once (`persistence` rule 13). `reference` is the natural key the source hands over, stored as it
arrives; its unique constraint is the one the writes resolve conflicts on, and the convention names it
`uq_foos_reference`.

A table module's public names are bare `Table` objects, and `metadata.py`'s is a bare `MetaData`, so
neither is wildcarded into the package `__init__` (`python-packaging`, carve-out 3 — `foo_table` would
shadow its own module). Code inside the package reaches them by relative import, code outside by the
module path (`from myapp.postgres.foo_table import foo_table`), and the migration environment imports
every table module once for its registration side effect (`flat-project-setup`), so autogenerate sees
the whole schema. `src/myapp/postgres/__init__.py` re-exports the modules that declare `__all__`:

```python
from . import engine, foo_repository, settings
from .engine import *
from .foo_repository import *
from .settings import *

__all__ = engine.__all__ + foo_repository.__all__ + settings.__all__
```
