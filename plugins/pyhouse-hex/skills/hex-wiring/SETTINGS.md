# hex-wiring — the settings classes

Topic file of `hex-wiring`. The mechanism-free obligations are `### Rules — settings` in
`SKILL.md`; what follows is the **pydantic-settings** binding that satisfies them.

## Template — pydantic-settings, relational database

A **relational-engine** example. Its connection-pool fields (`port`, `pool_size`,
`max_overflow`, `pool_pre_ping`, `echo`) and the `dsn` are **relational-only** — they mean nothing for an
API key, a blob store, a vector store or an observability backend. Never copy them into a non-engine
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

## Template — pydantic-settings, generic integration (API key, blob store, vector store, observability)

Most integrations need a credential plus an endpoint or model name and maybe a knob or two — no pool, no
port, no DSN. This is the shape for everything that is not a relational engine:

```python
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["FooApiSettings"]

class FooApiSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="MYAPP_FOO_",
        env_file=".env",
        extra="ignore",
    )

    api_key: SecretStr
    base_url: str = "https://api.foo.example"
    timeout_seconds: int = 30
```

**A timeout is a per-integration decision.** It is set from the
integration's own observed latency plus headroom, and bounded above by what the caller can wait for — a
request-path adapter whose timeout exceeds the app's own request timeout can never fire usefully. What
the template does fix is that the timeout is a **settings field**, read once by the composition root and
injected — never a constant hardcoded inside the adapter. Whether it carries a default at all is rule 1
and rule 2's question: default it only if one value is safe for every deployment, and make it required
otherwise.

## Template — pydantic-settings, S3-compatible blob store

The settings class the S3 adapter (`hex-capability-adapter`) consumes, in `infrastructure/s3/settings.py`
(`hex-conventions` derives the path and the name). The endpoint is required, so the same class reaches
a hosted store and an S3-compatible one; the adapter reads `bucket` and `endpoint_url`, and the
composition root builds the SDK session from the two credential fields.

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

## Template — pydantic-settings, the other classes the adapter templates read

One class per consuming technology, each in that technology's `settings.py`, with the fields the
adapter or the composition root reads and nothing else. Each sets the settings-file key in its
`model_config` exactly as `DbSettings` does, beside the prefix shown.

```python
# src/myapp/infrastructure/idna/settings.py
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["IdnaSettings"]

class IdnaSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MYAPP_IDNA_", extra="ignore")

    allowed_schemes: frozenset[str]
```

```python
# src/myapp/infrastructure/http/settings.py
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["BarGatewaySettings"]

class BarGatewaySettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MYAPP_BAR_", extra="ignore")

    base_url: str
    api_key: SecretStr
    timeout_seconds: float
```

```python
# src/myapp/infrastructure/qdrant/settings.py
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["QdrantSettings"]

class QdrantSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MYAPP_QDRANT_", extra="ignore")

    url: str
    foos_collection: str
    api_key: SecretStr | None = None
```

```python
# src/myapp/infrastructure/redis/settings.py
from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["RedisSettings"]

class RedisSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MYAPP_REDIS_", extra="ignore")

    url: SecretStr
    foos_key_prefix: str
```

```python
# src/myapp/infrastructure/export/settings.py
from pydantic_settings import BaseSettings, SettingsConfigDict

__all__ = ["ExportSettings"]

class ExportSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MYAPP_EXPORT_", extra="ignore")

    max_rows: int
```

`IdnaSettings.allowed_schemes` is read from a JSON list (`MYAPP_IDNA_ALLOWED_SCHEMES='["http","https"]'`).
The Redis URL is a secret because it carries the password. The Qdrant key is the one optional secret: a
store that runs unauthenticated has none, and `None` there is a declared mode rather than a missing
credential (settings rule 6). `ExportSettings` has no adapter behind it — its one consumer is the factory
of `FooExportTunable` (`hex-domain-model`) — so its package is named for itself (`hex-conventions`).
