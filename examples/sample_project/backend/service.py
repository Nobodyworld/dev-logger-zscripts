"""Service layer for task and project management."""

from __future__ import annotations

from dataclasses import dataclass, field

from .models import Project, Task, User


@dataclass(slots=True)
class TaskService:
    """Service for managing tasks and projects."""

    tasks: dict[str, Task] = field(default_factory=dict)
    projects: dict[str, Project] = field(default_factory=dict)
    users: dict[str, User] = field(default_factory=dict)

    def create_task(
        self,
        title: str,
        description: str | None = None,
        project_id: str = "",
        priority: str = "medium",
    ) -> Task:
        """Create a new task."""
        task = Task(
            title=title,
            description=description or "",
            project_id=project_id,
            priority=priority,
        )
        self.tasks[task.id] = task
        return task

    def get_task(self, task_id: str) -> Task | None:
        """Get a task by ID."""
        return self.tasks.get(task_id)

    def list_tasks(self) -> list[Task]:
        """List all tasks."""
        return list(self.tasks.values())

    def assign_task(self, task_id: str, user_id: str) -> bool:
        """Assign a task to a user."""
        task = self.get_task(task_id)
        if task is None:
            return False
        task.assign_to(user_id)
        return True

    def mark_task_complete(self, task_id: str) -> Task | None:
        """Mark a task as complete."""
        task = self.get_task(task_id)
        if task:
            task.mark_complete()
        return task

    def create_project(self, name: str, description: str | None = None) -> Project:
        """Create a new project."""
        project = Project(name=name, description=description or "")
        self.projects[project.id] = project
        return project

    def get_project(self, project_id: str) -> Project | None:
        """Get a project by ID."""
        return self.projects.get(project_id)

    def list_projects(self) -> list[Project]:
        """List all projects."""
        return list(self.projects.values())

    def add_user(self, username: str, email: str) -> User:
        """Add a new user."""
        user = User(username=username, email=email)
        self.users[user.id] = user
        return user

    def get_user(self, user_id: str) -> User | None:
        """Get a user by ID."""
        return self.users.get(user_id)
