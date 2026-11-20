class TasksError(Exception):
    code = "tasks_error"

    def __init__(self, message: str, **context: object) -> None:
        super().__init__(message)
        self.context = context


class NotFoundError(TasksError):
    code = "not_found"


class ProjectNameTakenError(TasksError):
    code = "project_name_taken"


class TaskAlreadyDoneError(TasksError):
    code = "task_already_done"
