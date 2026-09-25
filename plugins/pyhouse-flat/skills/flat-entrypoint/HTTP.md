# flat-entrypoint — the HTTP trigger

Topic file of `flat-entrypoint`. The obligations are rule 9 and the HTTP hard stops in `SKILL.md`; what
follows is the **FastAPI + uvicorn** binding that satisfies them, for the worked example's run
functions.

## The app factory — FastAPI

`src/myapp/web/app.py` — the framework-wrapper package for this shape. `build_app` takes the
dependencies the process definition built and closes the routes over them:

```python
from collections.abc import Awaitable, Callable
from typing import Annotated

import structlog
from fastapi import FastAPI, Path, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from myapp.exceptions import MyappError, ValidationError
from myapp.ingest.foo_ingest import run_once
from myapp.jobs import find_foo
from myapp.schemas import Foo, IngestResult
from myapp.services import FooClient
from myapp.storage import FooStorage

__all__ = ["build_app"]

logger = structlog.get_logger()

_REFERENCE_MAX_LENGTH = 256


def _response(exc: MyappError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.http_status,
        content={"code": exc.code, "message": str(exc), "context": exc.context},
    )


def _log_and_render(exc: MyappError) -> JSONResponse:
    if exc.http_status >= 500:
        logger.error("request_failed", code=exc.code, context=exc.context)
    else:
        logger.warning("request_failed", code=exc.code, context=exc.context)
    return _response(exc)


def build_app(client: FooClient, storage: FooStorage) -> FastAPI:
    app = FastAPI()

    @app.middleware("http")
    async def _contain_unexpected(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        try:
            return await call_next(request)
        except Exception:
            logger.exception("request_crashed")
            return _response(MyappError("the request failed unexpectedly"))

    @app.exception_handler(MyappError)
    async def _on_catalogue_error(request: Request, exc: MyappError) -> JSONResponse:
        return _log_and_render(exc)

    @app.exception_handler(RequestValidationError)
    async def _on_invalid_request(request: Request, exc: RequestValidationError) -> JSONResponse:
        fields = sorted({".".join(map(str, error["loc"])) for error in exc.errors()})
        return _log_and_render(ValidationError("the request is invalid", {"fields": fields}))

    @app.post("/runs")
    async def trigger_run() -> IngestResult:
        return await run_once(client, storage)

    @app.get("/foos/{reference}")
    async def read_foo(reference: Annotated[str, Path(max_length=_REFERENCE_MAX_LENGTH)]) -> Foo:
        return await find_foo(storage, reference)

    return app
```

**The catalogue is rendered in one place, in one shape.** Once the service answers HTTP its catalogue
root carries `http_status`, and every failure leaves as `code`, message and `context` read off an
exception (`exception-catalog`; the classes and their statuses are in `flat-layered`'s `CATALOG.md`): a
catalogue error as itself, the framework's validation failure as the
catalogue's validation error, and anything else as the catalogue root with status 500. The level follows
the kind (`python-style`): `warning` for a rejection the client caused, `error` for a 5xx — an upstream
failure or a crash.

**The unexpected failure is contained by a middleware, not an exception handler.** FastAPI's handler for
bare `Exception` answers and then re-raises to the server, which logs the same failure a second time; the
middleware stops it, so the one event it logs is the only one.

**The app is built once, by a factory the process definition calls**, never as a module-level `app`:
a module-level app builds its dependencies at import, which is the global wiring rule 3 forbids, and a
test could not hand it a test container's engine.

## The read's run function

`src/myapp/jobs/foo_lookup.py` — in the work-unit package for already-stored data:

```python
from myapp.schemas import Foo
from myapp.storage import FooStorage

__all__ = ["find_foo"]


async def find_foo(storage: FooStorage, reference: str) -> Foo:
    return await storage.get_by_reference(reference)
```

`src/myapp/jobs/__init__.py` re-exports it, because its name is its own. A module whose run function
shares a name with another's — two `run_once`s — stays out of the re-export and is imported from its own
module (`python-packaging`):

```python
from . import foo_lookup
from .foo_lookup import *

__all__ = foo_lookup.__all__
```

## The process definition — uvicorn

`src/myapp/settings.py` gains the two fields the server binds to, required like every other tunable
(`flat-layered` rule 10):

```python
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="MYAPP_")

    foo_api_url: str
    foo_api_timeout_seconds: float
    http_host: str
    http_port: int


def get_settings() -> Settings:
    return Settings()
```

`src/myapp/entrypoints/foo_http.py` — the only place a settings factory is called, exactly as for the
loop:

```python
import uvicorn

from myapp.services import FooClient
from myapp.settings import get_settings
from myapp.storage import FooStorage, get_engine, get_storage_settings
from myapp.web import build_app


def main() -> None:
    settings = get_settings()
    storage = FooStorage(get_engine(get_storage_settings().dsn.get_secret_value()))
    client = FooClient(settings.foo_api_url, settings.foo_api_timeout_seconds)
    app = build_app(client, storage)

    uvicorn.run(app, host=settings.http_host, port=settings.http_port)


if __name__ == "__main__":
    main()
```

`src/myapp/web/__init__.py` re-exports `build_app` the same way, and the project adds `fastapi` and
`uvicorn` to its dependencies (`flat-project-setup`).
