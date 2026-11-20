from uuid import UUID, uuid4

from tasks.domain.ports import IProjectRepository
from tasks.domain.project import Project


class CreateProjectHandler:
    def __init__(self, projects: IProjectRepository) -> None:
        self._projects = projects

    async def __call__(self, name: str) -> UUID:
        project = Project(id=uuid4(), name=name)
        await self._projects.add(project)
        return project.id
