# hex-persistence — the revision

Topic file of `hex-persistence`. The mechanism-free obligations are rules 12 and 14 in `SKILL.md`; what follows
is the **Alembic** binding that satisfies it.

The migration tool owns the revision chain: `alembic revision` assigns the id and `down_revision` from
the current head. A schema change is a coordinated pair — the `Table` (`TABLE.md`) and a new revision — landing
in the same commit. A later field change is reconciled by authoring a **new** revision, never by
rewriting a prior one. `--autogenerate` produces only a draft: it misses naming-convention nuance,
partial indexes and seed data, so hand-edit it against the rules in `TABLE.md`. The one-time bootstrap that lets
the chain exist at all is `hex-project-setup`.

**A change that touched both the `Table` and a revision runs `uv run alembic check` itself**, against a
migrated database — it answers `No new upgrade operations detected` when the two sides agree on what
autogenerate compares, and an autogenerate diff when they have drifted. Run it by hand because **nothing
else reports the drift**: lint, type-check and the test suite all stay green through it. Adding an index
only to the `Table` while the migration never creates it leaves a full suite passing. What diverges is
not behaviour — behaviour comes from the migration, which is what actually runs — but the metadata the
code is read through, and the starting point the next revision autogenerates from. *The by-hand run rests
on that invisibility and on nothing else, so it carries its withdrawal condition next to it: if lint,
type-check or the test suite ever goes red on a `Table` that has drifted from its revision, the drift has
a reporter and the by-hand run goes.*

**`alembic check` sees only what autogenerate compares.** Under Alembic's defaults that is tables and
columns added or removed, a column's type and nullability, indexes, unique constraints and foreign keys.
It does **not** compare a check constraint's expression, a server default (unless `compare_server_default`
is enabled), a primary-key change, or a rename, which reads as a drop plus an add. So a check constraint —
a range bound, an allowed-value list — is compared **by hand**: the `Table`'s expression against the
revision's, character for character. Flipping only the `Table`'s range bound passes `alembic check` and the
whole suite alike. Recent Alembic releases add an opt-in check-constraint comparison; where a project
enables it, that part of the by-hand comparison goes.

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

`downgrade()` is mandatory and reverses the operations in the opposite order, because the migration
round-trip test — upgrade, downgrade, upgrade again against a real database (`hex-test-repository-contract`)
— runs it; a `downgrade()` nothing runs is a reverse path nobody has proven.

The revision runs as a deploy step, **before** the new code starts, so it must be compatible with the code
still running (rule 14 in `SKILL.md`): this revision only adds, and a later revision that drops or tightens
what old code reads ships in a release after the one that stopped reading it.

