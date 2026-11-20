from dataclasses import dataclass, replace
from uuid import UUID

from tasks.errors import TaskAlreadyDoneError


@dataclass(frozen=True, slots=True)
class Task:
    id: UUID
    project_id: UUID
    title: str
    assignee_email: str | None = None
    done: bool = False

    def complete(self) -> "Task":
        if self.done:
            raise TaskAlreadyDoneError("task is already done", task_id=str(self.id))
        return replace(self, done=True)
