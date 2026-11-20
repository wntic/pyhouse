from uuid import uuid4

import pytest

from tasks.domain.task import Task
from tasks.errors import TaskAlreadyDoneError


def test_complete_marks_task_done() -> None:
    task = Task(id=uuid4(), project_id=uuid4(), title="write report")

    assert task.complete().done is True


def test_complete_twice_is_rejected() -> None:
    task = Task(id=uuid4(), project_id=uuid4(), title="write report", done=True)

    with pytest.raises(TaskAlreadyDoneError):
        task.complete()
