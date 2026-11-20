from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine

from tasks.api.routes import router
from tasks.settings import DatabaseSettings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    app.state.engine = create_async_engine(DatabaseSettings().url)
    yield
    await app.state.engine.dispose()


def create_app() -> FastAPI:
    app = FastAPI(lifespan=lifespan)
    app.include_router(router)
    return app
