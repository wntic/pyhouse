# hex-persistence — the revision

Topic file of `hex-persistence`. The mechanism-free obligations are rule 4 in `SKILL.md` and
`persistence` rules 19 and 20; what follows is the **Alembic** binding that satisfies them.

The migration tool owns the revision chain: `alembic revision` assigns the id and `down_revision` from
the current head — the two placeholders below are what it fills in, never values to type. A schema
change is a coordinated pair — the `Table` (`TABLE.md`) and a new revision — landing in the same commit
(rule 4). `--autogenerate` produces only a draft (`persistence` rule 20): it misses naming-convention
nuance and partial indexes, so hand-edit it against the rules in `TABLE.md`. The one-time bootstrap that
lets the chain exist at all is `hex-project-setup`.

A change that touched both the `Table` and a revision runs `uv run alembic check` against a migrated
database, since nothing else — lint, type-check or the suite — reports the two drifting apart. It
compares only what autogenerate compares, so a check constraint's expression, a server default and a
rename are compared against the revision by hand.

The revision, in `migrations/versions/<revision>_create_foos.py`:

```python
"""create foos"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "<revision>"
down_revision: str | None = "<current head>"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "foos",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("name"),
        sa.CheckConstraint("char_length(name) > 0", name="name_non_empty"),
    )
    op.create_index("ix_foos_created_at", "foos", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_foos_created_at", table_name="foos")
    op.drop_table("foos")
```

A check constraint's `name` is the suffix, as in the `Table`: the convention prepends `ck_foos_`, so a
full name there comes out doubled.

`downgrade()` reverses the operations in the opposite order (`persistence` rule 20); the round trip
that proves it is `hex-test-repository-contract`'s. This revision only adds, so it is the expand half
`persistence` rule 19 lets ship alone.

