from uuid import UUID

from sqlalchemy import insert, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from tasks.domain.project import Project
from tasks.errors import NotFoundError, ProjectNameTakenError
from tasks.infrastructure.persistence.tables import projects


class SqlProjectRepository:
    def __init__(self, connection: AsyncConnection) -> None:
        self._connection = connection

    async def add(self, project: Project) -> None:
        try:
            await self._connection.execute(insert(projects).values(id=project.id, name=project.name))
        except IntegrityError as exc:
            raise ProjectNameTakenError("project name is taken", name=project.name) from exc

    async def get(self, project_id: UUID) -> Project:
        row = (await self._connection.execute(select(projects).where(projects.c.id == project_id))).first()
        if row is None:
            raise NotFoundError("project not found", project_id=str(project_id))
        return Project(id=row.id, name=row.name)
