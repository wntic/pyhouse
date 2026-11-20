from collections.abc import AsyncIterator
from typing import Annotated

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncConnection

from tasks.application.projects import CreateProjectHandler
from tasks.application.tasks import AddTaskHandler, CompleteTaskHandler
from tasks.infrastructure.persistence.project_repository import SqlProjectRepository
from tasks.infrastructure.persistence.task_repository import SqlTaskRepository


async def connection(request: Request) -> AsyncIterator[AsyncConnection]:
    async with request.app.state.engine.begin() as conn:
        yield conn


Connection = Annotated[AsyncConnection, Depends(connection)]


def create_project_handler(conn: Connection) -> CreateProjectHandler:
    return CreateProjectHandler(SqlProjectRepository(conn))


def add_task_handler(conn: Connection) -> AddTaskHandler:
    return AddTaskHandler(SqlProjectRepository(conn), SqlTaskRepository(conn))


def complete_task_handler(conn: Connection) -> CompleteTaskHandler:
    return CompleteTaskHandler(SqlTaskRepository(conn))
