# hex-wiring — the settings classes

Topic file of `hex-wiring`. The mechanism-free obligations are `### Rules — settings` in
`SKILL.md`; what follows is the **pydantic-settings** binding that satisfies them, worked on the
relational engine's class. Every other settings class the templates read sits beside the adapter that
reads it (settings rule 12), listed at the end.

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

## Where the other settings classes are

Most integrations need a credential plus an endpoint or a resource name and maybe a knob or two — no
pool, no port, no DSN. Each is written in the same form as `DbSettings` — the three `model_config` keys
above, its own prefix, the fields its consumer reads and nothing else — and each is shown beside what
reads it:

- `S3Settings`, `BarGatewaySettings` and `IdnaSettings` — beside the S3 storage, the HTTP gateway and
  the idna canonicalizer in `hex-capability-adapter`. `S3Settings` is the plainest non-engine shape.
- `RedisSettings` — beside the key-value repository in `hex-store-repository`.
- `JwtSettings` — beside the token verifier in `hex-restapi-auth`.
- `ExportSettings` — in `CONTAINER.md`, beside the provider of the tunable value object that is its one
  consumer.

Every one of them has its factory in the composition root. `DbSettings` and `ExportSettings` have
theirs in the base in `CONTAINER.md`; each other class has its factory in the binding shown beside its
adapter, which a project merges into that base.
