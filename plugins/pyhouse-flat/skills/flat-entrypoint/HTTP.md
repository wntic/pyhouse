# flat-entrypoint — the HTTP trigger

Topic file of `flat-entrypoint`. The obligations are rule 9 in `SKILL.md`; what
follows is the **FastAPI + uvicorn** binding that satisfies them, for one route receiving a body and
handing it to one run function.

## The app factory — FastAPI

`src/myapp/web/app.py` — the framework-wrapper package for this shape. `build_app` takes the
dependencies the process definition built and closes the routes over them:

```python
from collections.abc import Awaitable, Callable

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from myapp.exceptions import InvalidPayloadError, MyappError
from myapp.foo_record import record_foo
from myapp.postgres import FooRepository
from myapp.schemas import FooDelivery, RunResult

__all__ = ["build_app"]

logger = structlog.get_logger()


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


def build_app(repository: FooRepository) -> FastAPI:
    app = FastAPI()

    @app.middleware("http")
    async def _contain_unexpected(request: Request, call_next: Callable[[Request], Awaitable[Response]]) -> Response:
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
        return _log_and_render(InvalidPayloadError("the request is invalid", {"fields": fields}))

    @app.post("/foos")
    async def receive_foo(delivery: FooDelivery) -> RunResult:
        return await record_foo(repository, delivery)

    return app
```

**The catalogue is rendered in one place, in one shape.** Once the service answers HTTP its catalogue
root carries the optional `http_status` field and each class sets its own (`exception-catalog`);
the catalogue declares `class InvalidPayloadError(MyappError)` with `code = "INVALID_PAYLOAD"` and
`http_status = 422` for a request body the client got wrong. This module is the only reader of the field. Every failure leaves as `code`,
message and `context` read off an exception: a catalogue error as itself, the framework's validation
failure as `InvalidPayloadError`, and anything else as the catalogue root with its status. The level
follows the kind (`python-logging`): `warning` for a rejection the client caused, `error` for a 5xx.

**The unexpected failure is contained by a middleware, not an exception handler.** FastAPI's handler for
bare `Exception` answers and then re-raises to the server, which logs the same failure a second time; the
middleware stops it, so the one event it logs is the only one.

**The app is built once, by a factory the process definition calls**, never as a module-level `app`:
a module-level app builds its dependencies at import, which is the global wiring rule 3 forbids, and a
test could not hand it a test container's engine. A route whose run function calls an upstream is handed
that client the same way, as one more argument of `build_app`.

A request from a third party is verified in the wrapper (rule 9). Such a route takes the raw request,
verifies it, then validates the body with the delivery model; the parsed-parameter signature above is for
a caller the network already trusts.

## The route's run function

A record a sender delivers — a webhook body, a queue message — carries the instant the sender stamped,
and a run over it writes that, never the clock; a record the service fetches has no such stamp and is
timed by the run. `src/myapp/schemas/foo_delivery.py` declares it beside the wire record, since the
route and the run function both read it, and `schemas/__init__.py` re-exports it (`flat-layered`); the
instant is aware (`python-style`):

```python
from pydantic import AwareDatetime

from .foo_payload import FooPayload

__all__ = ["FooDelivery"]


class FooDelivery(FooPayload):
    sent_at: AwareDatetime
```

`src/myapp/foo_record.py` — framework-free like every run function:

```python
from myapp.postgres import FooRepository
from myapp.schemas import Foo, FooDelivery, FooReference, RunResult

__all__ = ["record_foo"]


async def record_foo(repository: FooRepository, delivery: FooDelivery) -> RunResult:
    foo = Foo(reference=FooReference(delivery.ref), name=delivery.name, observed_at=delivery.sent_at)
    await repository.record_batch([foo])
    return RunResult(recorded=1)
```

An exact redelivery therefore writes what the row already holds (rule 9). Where an older delivery can
arrive after a newer one for the same reference, keeping the newer is the conflict clause's job
(`flat-persistence`).

## The process definition — uvicorn

`src/myapp/settings.py` — the process's own `Settings` class in the shape `flat-layered` shows — holds the
two fields the server binds to, required like every other tunable (`flat-layered` rule 9):
`http_host: str` and `http_port: int`, read from `MYAPP_HTTP_HOST` and `MYAPP_HTTP_PORT`.

`src/myapp/__main__.py` where the server is the service's one process — in `entrypoints/`, beside
others, the same module without its last two lines, `main()` being what its console script calls:

```python
import asyncio

import uvicorn

from myapp.logging import configure_logging
from myapp.postgres import FooRepository, PostgresSettings, get_engine
from myapp.settings import Settings
from myapp.web import build_app


async def _serve() -> None:
    settings = Settings()
    engine = get_engine(PostgresSettings().dsn.get_secret_value())
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

The server is served on the process's own event loop, inside the block that owns the engine, rather than
through `uvicorn.run`, which starts a loop of its own: the engine is then opened and closed on the loop
the app's requests run on, once for the life of the server (`flat-layered` rule 12). `log_config=None`
keeps the server from configuring logging a second time (`python-logging` rule 3).

`src/myapp/web/__init__.py` re-exports `build_app`, and the project adds `fastapi` and `uvicorn` to its
dependencies (`flat-project-setup`).
