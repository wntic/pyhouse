# flat-persistence — the shared plumbing

Topic file of `flat-persistence`. The mechanism-free obligations are rules 3, 4, 5 and 6 in
`SKILL.md`, and `persistence` rules 7, 19 and 20; what follows is the **SQLAlchemy Core + asyncpg +
Alembic** binding that satisfies them.

These are the modules written once per package and then left alone — the one `MetaData`, the component's
own settings class, and the factory building the engine every repository class is handed — plus the
per-change migration revision that reads the metadata back.

## The metadata module — SQLAlchemy Core (once)

One `MetaData`, in a module of its own, carrying the one naming convention `persistence` rule 7 asks
for — never inside a table module, which would make that table the root of the import graph.

`src/myapp/postgres/metadata.py`:

```python
from sqlalchemy import MetaData

metadata = MetaData(
    naming_convention={
        "ix": "ix_%(table_name)s_%(column_0_name)s",
        "uq": "uq_%(table_name)s_%(column_0_name)s",
        "ck": "ck_%(table_name)s_%(constraint_name)s",
        "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
        "pk": "pk_%(table_name)s",
    }
)
```

For a `CheckConstraint`, `name=` is the **suffix** — the convention prepends `ck_<table>_`, so passing a
full name yields `ck_foos_ck_foos_name_non_empty`.

## The settings module — pydantic-settings

This package is a component with configuration of its own, so it declares that configuration here rather
than borrowing a field from the service's class (`flat-layered` rule 7).

`src/myapp/postgres/settings.py`:

```python
from pydantic import SecretStr, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["PostgresSettings"]


class PostgresSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MYAPP_POSTGRES_",
        env_file=".env",  # only where the project keeps a dotenv file for development
        extra="ignore",
    )

    dsn: SecretStr

    @field_validator("dsn")
    @classmethod
    def _use_async_driver(cls, dsn: SecretStr) -> SecretStr:
        scheme, separator, rest = dsn.get_secret_value().partition("://")
        return SecretStr(f"postgresql+asyncpg{separator}{rest}") if scheme in {"postgres", "postgresql"} else dsn
```

The variable holds the platform's connection string; the class normalizes its scheme to the async
driver's (`postgresql+asyncpg://`) in a validator (`python-settings` rule 12), so the deployment never
spells a driver. The connection string carries the password, so it is secret-typed and unwrapped only where the engine
is built (`python-settings` rules 7 and 9). `MYAPP_POSTGRES_` nests under the process's `MYAPP_`, so
`postgres` is a reserved segment there (`naming`); where the package is shared between distributions its
prefix is the shared package's own, and the `## Other bindings` bullet in `SKILL.md` says what else
changes. A second store's package declares its own `<Store>Settings` under `MYAPP_<STORE>_` and never
adds its fields to this one (rule 5). The process definition constructs `PostgresSettings()`, unwraps
`dsn` and hands the value to the engine factory (`flat-layered` rule 6, and rule 3 in `SKILL.md`); the
migration environment is the migration run's process definition and does the same
(`flat-project-setup`).

## Engine factory — SQLAlchemy async, asyncpg

The engine is built by a **factory taking the connection string**, never as a module-level object:
`import myapp.postgres.engine` must not fail in an environment that has set nothing (`python-packaging`
rule 8).

`src/myapp/postgres/engine.py`:

```python
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

__all__ = ["get_engine"]


def get_engine(dsn: str) -> AsyncEngine:
    return create_async_engine(dsn, pool_pre_ping=True)
```

No `@lru_cache` on it: a memoised engine pins a pool past shutdown and past the test that disposes it
(`python-packaging` rule 8).

## Migrations — Alembic

The migration environment and the revision template are laid once, with the project, under
`migrations/postgres/` at the distribution root (`flat-project-setup`). What recurs is one revision per
schema change, authored from the metadata above by `alembic revision --autogenerate -m "<change>"`,
reviewed against `persistence` rule 19 before it is committed, and applied by
`alembic upgrade head`. Autogenerate diffs the metadata against a live database at head, so the draft is made against one only its author
uses — a container of the suite's image, upgraded first — and `alembic upgrade head` reaches a shared
database only as the deploy step.

Both run from the directory holding `alembic.ini` — the distribution's own root, or the owning library's
where several distributions share the store (rule 4) — so whatever applies the history carries
`alembic.ini` beside `migrations/` (rule 6). Alembic takes no lock of its own, so `persistence`
rule 19's one job per deploy is the exclusion. The revision lands in `migrations/postgres/versions/`.
Autogenerate compares
tables, columns, types, nullability, indexes, unique and foreign-key constraints; it does not compare a
`CheckConstraint`, so a change to one is written into the revision by hand.

Where a second store's schema is versioned too, its history sits beside this one in
`migrations/<store>/`, in whatever format that store's migration tool reads, and is applied by that tool
as its own deploy step (rule 6). It never goes into
`migrations/postgres/`, and never into the package under `src/`.
