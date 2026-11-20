from uuid import UUID

from sqlalchemy import Row, insert, select, update
from sqlalchemy.ext.asyncio import AsyncConnection

from tasks.domain.task import Task
from tasks.errors import NotFoundError
from tasks.infrastructure.persistence.tables import tasks


class SqlTaskRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def add(self, task: Task) -> None:
        await self._connection.execute(
            insert(tasks).values(
                id=task.id,
                project_id=task.project_id,
                title=task.title,
                assignee_email=task.assignee_email,
                done=task.done,
            )
        )

    async def get(self, task_id: UUID) -> Task:
        row = (await self._connection.execute(select(tasks).where(tasks.c.id == task_id))).first()
        if row is None:
            raise NotFoundError("task not found", task_id=str(task_id))
        return _task(row)

    async def save(self, task: Task) -> None:
        await self._connection.execute(
            update(tasks)
            .where(tasks.c.id == task.id)
            .values(title=task.title, assignee_email=task.assignee_email, done=task.done)
        )

    async def list_for_project(self, project_id: UUID) -> list[Task]:
        rows = await self._connection.execute(select(tasks).where(tasks.c.project_id == project_id))
        return [_task(row) for row in rows]


def _task(row: Row) -> Task:
    return Task(
        id=row.id, project_id=row.project_id, title=row.title, assignee_email=row.assignee_email, done=row.done
    )
