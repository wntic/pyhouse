from sqlalchemy import Boolean, Column, ForeignKey, MetaData, String, Table, Uuid

metadata = MetaData(
    naming_convention={
        "pk": "pk_%(table_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
    }
)

projects = Table(
    "projects",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("name", String(200), nullable=False, unique=True),
)

tasks = Table(
    "tasks",
    metadata,
    Column("id", Uuid, primary_key=True),
    Column("project_id", Uuid, ForeignKey("projects.id"), nullable=False),
    Column("title", String(500), nullable=False),
    Column("assignee_email", String(320), nullable=True),
    Column("done", Boolean, nullable=False, default=False),
)
