from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from tasks.api.deps import add_task_handler, complete_task_handler, create_project_handler
from tasks.application.projects import CreateProjectHandler
from tasks.application.tasks import AddTaskHandler, CompleteTaskHandler

router = APIRouter()


class CreateProjectBody(BaseModel):
    name: str


class AddTaskBody(BaseModel):
    title: str
    assignee_email: str | None = None


class Created(BaseModel):
    id: UUID


@router.post("/projects", status_code=201)
async def create_project(
    body: CreateProjectBody, handler: Annotated[CreateProjectHandler, Depends(create_project_handler)]
) -> Created:
    return Created(id=await handler(body.name))


@router.post("/projects/{project_id}/tasks", status_code=201)
async def add_task(
    project_id: UUID, body: AddTaskBody, handler: Annotated[AddTaskHandler, Depends(add_task_handler)]
) -> Created:
    return Created(id=await handler(project_id, body.title, body.assignee_email))


@router.post("/tasks/{task_id}/complete", status_code=204)
async def complete_task(
    task_id: UUID, handler: Annotated[CompleteTaskHandler, Depends(complete_task_handler)]
) -> None:
    await handler(task_id)
