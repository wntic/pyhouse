# flat-entrypoint — the HTTP trigger

Topic file of `flat-entrypoint`. The obligations are rule 9 in `SKILL.md`; what follows is the smallest
**FastAPI + uvicorn** wrapper that satisfies them — one route receiving a body and handing it to the
function that does the work. A fuller HTTP shell, with CORS, middleware and a router per resource, is
shown by `hex-restapi-app`, in the `pyhouse-hex` plugin, as an example only; a flat service adds such a
piece when it has the need, not because a shell showed it.

## The app factory — FastAPI (structlog)

`src/myapp/web/app.py` — the framework-wrapper package for this shape, re-exported by
`web/__init__.py`. `build_app` takes the dependencies the process definition built and closes the route
over them, and it logs through the module's logger, bound as `python-logging` shows:

```python
from collections.abc import Awaitable, Callable

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from myapp.exceptions import InvalidPayloadError, MyappError
from myapp.foo_recording import record_foo
from myapp.postgres import FooRepository
from myapp.schemas import FooChangePayload

__all__ = ["build_app"]

log = structlog.get_logger()


_STATUS_BY_ERROR: dict[type[MyappError], int] = {InvalidPayloadError: 422}


def _status_for(exc: MyappError) -> int:
    return next(
        (_STATUS_BY_ERROR[error_class] for error_class in type(exc).__mro__ if error_class in _STATUS_BY_ERROR),
        500,
    )


def _render(exc: MyappError) -> JSONResponse:
    content = jsonable_encoder({"code": exc.code, "message": str(exc), "context": exc.context})
    return JSONResponse(status_code=_status_for(exc), content=content)


def _log_and_render(exc: MyappError) -> JSONResponse:
    if _status_for(exc) >= 500:
        log.error("request_failed", code=exc.code, context=exc.context)
    else:
        log.warning("request_failed", code=exc.code, context=exc.context)
    return _render(exc)


def build_app(repository: FooRepository) -> FastAPI:
    app = FastAPI()

    @app.middleware("http")
    async def _contain_unexpected(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
        try:
            return await call_next(request)
        except Exception:
            log.exception("request_crashed")
            return _render(MyappError("the request failed unexpectedly"))

    @app.exception_handler(MyappError)
    async def _on_catalogue_error(request: Request, exc: MyappError) -> JSONResponse:
        return _log_and_render(exc)

    @app.exception_handler(RequestValidationError)
    async def _on_invalid_request(request: Request, exc: RequestValidationError) -> JSONResponse:
        fields = sorted({".".join(map(str, error["loc"])) for error in exc.errors()})
        return _log_and_render(InvalidPayloadError("the request is invalid", {"fields": fields}))

    @app.post("/foos", status_code=204)
    async def receive_foo(delivery: FooChangePayload) -> None:
        await record_foo(repository, delivery)

    return app
```

**Every failure a route raises leaves in one shape, from this module, logged once.** The catalogue
carries no status; this module maps one from the class (`exception-catalog` rules 6 and 13). A catalogue
error renders as itself, the framework's validation failure as `InvalidPayloadError` (`422`), anything
else as the catalogue root, and `context` is encoded for JSON first, so an identifier in it cannot turn
the answer into a crash. The level follows the status (`python-logging`). The unexpected failure is caught by a middleware because FastAPI's handler for
bare `Exception` re-raises to the server, which logs it a second time.

**The app is built by a factory the process definition calls**, never as a module-level `app`, which
would build its dependencies at import (rule 3) and could not be handed a test container's engine. An
upstream client the work needs is one more argument of `build_app`. A request from a third party is
verified against its raw body before the body is parsed (rule 9); the parsed-parameter signature above
is for a caller the network already trusts.

## The work the route calls

`src/myapp/foo_recording.py` — framework-free, named for its work, writing through the repository's
single-row `upsert` (`flat-persistence`, `REPOSITORY.md`). `FooChangePayload`, in
`schemas/foo_change_payload.py`, is `FooPayload` plus the `changed_at: AwareDatetime` the sender
assigned to the change, the same on every redelivery of it; the work writes that instant, never the
clock, so a redelivery writes what the row already holds (rule 9):

```python
from myapp.postgres import FooRepository
from myapp.schemas import Foo, FooChangePayload, FooExternalId

__all__ = ["record_foo"]


async def record_foo(repository: FooRepository, delivery: FooChangePayload) -> None:
    foo = Foo(external_id=FooExternalId(delivery.id), name=delivery.name, as_of=delivery.changed_at)
    await repository.upsert(foo)
```

Where an older delivery can arrive after a newer one for the same external id, keeping the newer is the
data-access package's job — the marked `where=` in `flat-persistence`'s `REPOSITORY.md` (`persistence`
rules 16 and 17).

## The process definition — uvicorn

`src/myapp/__main__.py`, or a module in `entrypoints/` beside others without its last two lines. The
process's `MyappSettings` declares `http_host: str` and `http_port: int`, required like every tunable
(`flat-layered` rule 9):

```python
import asyncio

import uvicorn

from myapp.logging import configure_logging
from myapp.myapp_settings import MyappSettings
from myapp.postgres import FooRepository, PostgresSettings, create_engine
from myapp.web import build_app


async def _serve() -> None:
    settings = MyappSettings()
    engine = create_engine(PostgresSettings().dsn)
    try:
        app = build_app(FooRepository(engine))
        config = uvicorn.Config(app, host=settings.http_host, port=settings.http_port, log_config=None)
        await uvicorn.Server(config).serve()
    finally:
        await engine.dispose()


def main() -> None:
    configure_logging()
    asyncio.run(_serve())


if __name__ == "__main__":
    main()
```

The server runs on the process's own loop, inside the block that owns the engine, so the engine is
opened and closed on the loop the requests run on; `log_config=None` keeps the server from configuring
logging a second time (`python-logging` rule 3).
