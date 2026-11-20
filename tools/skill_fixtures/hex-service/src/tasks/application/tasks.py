from uuid import UUID, uuid4

from tasks.domain.ports import IProjectRepository, ITaskRepository
from tasks.domain.task import Task


class AddTaskHandler:
    def __init__(self, projects: IProjectRepository, tasks: ITaskRepository) -> None:
        self._projects = projects
        self._tasks = tasks

    async def __call__(self, project_id: UUID, title: str, assignee_email: str | None = None) -> UUID:
        await self._projects.get(project_id)
        task = Task(id=uuid4(), project_id=project_id, title=title, assignee_email=assignee_email)
        await self._tasks.add(task)
        return task.id


class CompleteTaskHandler:
    def __init__(self, tasks: ITaskRepository) -> None:
        self._tasks = tasks

    async def __call__(self, task_id: UUID) -> None:
        task = await self._tasks.get(task_id)
        await self._tasks.save(task.complete())
