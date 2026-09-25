# flat-persistence — the table

Topic file of `flat-persistence`. The mechanism-free obligations are rules 8 and 13 in `SKILL.md`; what
follows is the **SQLAlchemy Core on Postgres** binding that satisfies them.

## The table — SQLAlchemy Core on Postgres

Every primary key is a **UUIDv7**, minted client-side through the `uuid6` package's `uuid7()` — never
`uuid.uuid4()` and never a database-side `server_default`. UUIDv7 is time-ordered, so ids inserted
together sort and index together; `uuid.uuid4()`'s randomness scatters otherwise-related rows across a
b-tree index for no benefit, and a database-side default means the writer cannot know the id it just
created without reading it back. `uuid6.uuid7()` returns a `uuid.UUID` subclass, so it drops straight
into `Column(..., default=uuid7)`.

`src/myapp/storage/foo_table.py`:

```python
from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    String,
    Table,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
from uuid6 import uuid7

from .metadata import metadata

foo_table = Table(
    "foos",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid7),
    Column("reference", String, nullable=False, unique=True),  # the normalized natural key
    Column("name", String, nullable=False),
    Column("observed_at", DateTime(timezone=True), nullable=False),
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
)

bar_table = Table(
    "bars",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True, default=uuid7),
    Column("foo_id", UUID(as_uuid=True), ForeignKey("foos.id"), nullable=False),
    Column("label", String(64), nullable=False),  # declared width — labels are short
    Column("created_at", DateTime(timezone=True), server_default=func.now(), nullable=False),
    UniqueConstraint("foo_id", "label"),
)
```

The declared width on `label` is a schema fact a test can read off the column to force a failure the
schema itself defines, rather than inventing a value that only happens to be rejected
(`flat-test-persistence`).

A table module's public names are bare `Table` objects, and `metadata.py`'s is a bare `MetaData`, so
neither is wildcarded into the package `__init__` (`python-packaging`, carve-out 3 — `foo_table` would
shadow its own module). Code inside the package reaches them by relative import, code outside by the
module path (`from myapp.storage.foo_table import foo_table`), and the migration environment imports
every table module once for its registration side effect (`flat-project-setup`), so autogenerate sees
the whole schema. `src/myapp/storage/__init__.py` re-exports the modules that declare `__all__`:

```python
from . import engine, foo_storage, settings
from .engine import *
from .foo_storage import *
from .settings import *

__all__ = engine.__all__ + foo_storage.__all__ + settings.__all__
```
