"""Presentation helpers that emulate REST-style views for the sample project."""

from __future__ import annotations

from collections.abc import Mapping
from typing import cast

from .service import TaskService


class TaskView:
    """REST-style view for task operations."""

    def __init__(self, service: TaskService):
        self.service = service

    def get_tasks(self, project_id: str | None = None) -> list[dict[str, object]]:
        """Get all tasks, optionally filtered by project."""
        tasks = self.service.list_tasks()
        if project_id:
            tasks = [t for t in tasks if t.project_id == project_id]

        result: list[dict[str, object]] = []
        for task in tasks:
            result.append(
                {
                    "id": task.id,
                    "title": task.title,
                    "description": task.description,
                    "status": task.status,
                    "priority": task.priority,
                    "assignee_id": task.assignee_id,
                    "project_id": task.project_id,
                    "created_at": task.created_at.isoformat(),
                    "updated_at": task.updated_at.isoformat(),
                }
            )
        return result

    def create_task(self, data: Mapping[str, object]) -> dict[str, object]:
        """Create a new task from request data."""
        task = self.service.create_task(
            title=cast(str, data["title"]),
            description=cast(str | None, data.get("description")),
            project_id=cast(str, data.get("project_id", "")),
            priority=cast(str, data.get("priority", "medium")),
        )

        assignee_value = data.get("assignee_id")
        if assignee_value is not None:
            assignee_id = cast(str, assignee_value)
            self.service.assign_task(task.id, assignee_id)

        return {
            "id": task.id,
            "title": task.title,
            "status": task.status,
            "created_at": task.created_at.isoformat(),
        }

    def update_task_status(self, task_id: str, status: str) -> dict[str, object]:
        """Update a task's status."""
        if status == "done":
            task = self.service.mark_task_complete(task_id)
        else:
            task = self.service.get_task(task_id)
            if task:
                task.status = status
                task.updated_at = task.created_at  # Simplified

        return {"id": task.id, "status": task.status} if task else {}


class ProjectView:
    """View for project operations."""

    def __init__(self, service: TaskService):
        self.service = service

    def get_projects(self) -> list[dict[str, object]]:
        """Get all projects."""
        projects = self.service.list_projects()
        result: list[dict[str, object]] = []
        for project in projects:
            result.append(
                {
                    "id": project.id,
                    "name": project.name,
                    "description": project.description,
                    "status": project.status,
                    "tags": list(project.tags),
                    "created_at": project.created_at.isoformat(),
                }
            )
        return result

    def create_project(self, data: Mapping[str, object]) -> dict[str, object]:
        """Create a new project."""
        project = self.service.create_project(
            name=cast(str, data["name"]),
            description=cast(str | None, data.get("description")),
        )

        return {
            "id": project.id,
            "name": project.name,
            "status": project.status,
        }
