from typing import Protocol
from uuid import UUID

from tasks.domain.project import Project
from tasks.domain.task import Task


class IProjectRepository(Protocol):
    async def add(self, project: Project) -> None: ...

    async def get(self, project_id: UUID) -> Project: ...


class ITaskRepository(Protocol):
    async def add(self, task: Task) -> None: ...

    async def get(self, task_id: UUID) -> Task: ...

    async def save(self, task: Task) -> None: ...

    async def list_for_project(self, project_id: UUID) -> list[Task]: ...
