# hex-wiring — the settings classes

Topic file of `hex-wiring`. The mechanism-free obligations are `### Rules — settings` in
`SKILL.md`; what follows is the **pydantic-settings** binding that satisfies them, worked on two
classes: the relational engine's and one non-engine integration's. Every other settings class the
templates read sits beside the adapter that reads it (settings rule 12), listed at the end.

## Template — pydantic-settings, relational database

A **relational-engine** example. Its connection-pool fields (`port`, `pool_size`,
`max_overflow`, `pool_pre_ping`, `echo`) and the `dsn` are **relational-only** — they mean nothing for an
API key, a blob store, a key-value store or an observability backend. Never copy them into a non-engine
settings class.

```python
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["DbSettings"]

class DbSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MYAPP_DB_",
        env_file=".env",
        extra="ignore",
    )

    host: str
    port: int = 5432
    user: str
    password: SecretStr
    name: str

    pool_size: int = 10
    max_overflow: int = 5
    pool_pre_ping: bool = True
    echo: bool = False

    @property
    def dsn(self) -> str:
        return (
            f"postgresql+asyncpg://{self.user}:{self.password.get_secret_value()}"
            f"@{self.host}:{self.port}/{self.name}"
        )
```

**Pool sizing is a deployment decision.** `pool_size=10` and `max_overflow=5` suit a single-process
web app; a worker running one long job wants far
fewer, and a fleet of processes has to multiply its pool by its replica count against the server's
connection ceiling. `port` defaults to the driver's own well-known port; `pool_pre_ping=True` and
`echo=False` are the two that are **not** taste — pre-ping costs one cheap round trip and buys immunity
to connections the server closed underneath the pool, and `echo=True` in production writes every
statement, parameters included, into the log. Set the sizes from the deployment; keep the last two.

## Template — pydantic-settings, a non-engine integration (S3-compatible blob store)

Most integrations need a credential plus an endpoint or a resource name and maybe a knob or two — no
pool, no port, no DSN. This is that shape, worked on the settings class the S3 adapter
(`hex-capability-adapter`) consumes, in `infrastructure/s3/settings.py` (`hex-conventions` derives the
path and the name). The endpoint is required, so the same class reaches a hosted store and an
S3-compatible one; the adapter reads `bucket` and `endpoint_url`, and the composition root builds the SDK
session from the two credential fields.

```python
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["S3Settings"]

class S3Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MYAPP_S3_",
        env_file=".env",
        extra="ignore",
    )

    endpoint_url: str
    access_key: str
    secret_key: SecretStr
    bucket: str
```

## Where the other settings classes are

Each is written in the same form — the three `model_config` keys above, its own prefix, the fields its
consumer reads and nothing else — and each is shown beside what reads it:

- `BarGatewaySettings` and `IdnaSettings` — beside the HTTP gateway and the idna canonicalizer in
  `hex-capability-adapter`.
- `RedisSettings` — beside the key-value repository in `hex-store-repository`.
- `JwtSettings` — beside the token verifier in `hex-restapi-auth`.
- `ExportSettings` — in `CONTAINER.md`, beside the provider of the tunable value object that is its one
  consumer.

Every one of them has its factory in the composition root — in `CONTAINER.md`, or for `JwtSettings`
in the binding `hex-restapi-auth` adds to it.
