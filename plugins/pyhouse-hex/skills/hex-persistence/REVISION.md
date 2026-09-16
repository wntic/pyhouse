# hex-persistence — the revision

Topic file of `hex-persistence`. The mechanism-free obligation is rule 12 in `SKILL.md`; what follows
is the **Alembic** binding that satisfies it.

The migration tool owns the revision chain: `alembic revision` assigns the id and `down_revision` from
the current head. A schema change is a coordinated pair — the `Table` (`TABLE.md`) and a new revision — landing
in the same commit. A later field change is reconciled by authoring a **new** revision, never by
rewriting a prior one. `--autogenerate` produces only a draft: it misses naming-convention nuance,
partial indexes and seed data, so hand-edit it against the rules in `TABLE.md`. The one-time bootstrap that lets
the chain exist at all is `hex-project-setup`.

**A change that touched both the `Table` and a revision runs `uv run alembic check` itself**, against a
migrated database — it answers `No new upgrade operations detected` when the two sides agree, and an
autogenerate diff when they have drifted. Run it by hand because **nothing else reports the drift**: lint,
type-check and the test suite all stay green through it. Flipping only a `Table`'s range bound while
leaving the migration correct leaves a full suite passing. What diverges is not behaviour — behaviour
comes from the migration, which is what actually runs — but the metadata the code is read through, and
the starting point the next revision autogenerates from. *The by-hand run rests on that invisibility and
on nothing else, so it carries its withdrawal condition next to it: if lint, type-check or the test suite
ever goes red on a `Table` that has drifted from its revision, the drift has a reporter and the by-hand
run goes.*

```python
# migrations/versions/0042_create_foos.py  (id + down_revision assigned by `alembic revision`)
"""create foos"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision: str = "0042"
down_revision: str | None = "0041"
branch_labels: Sequence[str] | None = None
depends_on: Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "foos",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.Text, nullable=False),
        sa.Column(
            "bar_id",
            UUID(as_uuid=True),
            sa.ForeignKey("bars.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("name"),
        # A check constraint's `name` is the SUFFIX: the convention prepends `ck_foos_`; a full name doubles.
        sa.CheckConstraint("char_length(name) > 0", name="name_non_empty"),
    )
    op.create_index("ix_foos_bar_id", "foos", ["bar_id"])
    op.create_index("ix_foos_created_at", "foos", ["created_at"])


def downgrade() -> None:
    op.drop_index("ix_foos_created_at", table_name="foos")
    op.drop_index("ix_foos_bar_id", table_name="foos")
    op.drop_table("foos")
```

`downgrade()` is mandatory and reverses the operations in the opposite order — the test environment uses
it.

