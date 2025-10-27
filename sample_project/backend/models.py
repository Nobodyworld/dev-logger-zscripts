"""Data models backing the sample project service layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from uuid import uuid4


def _now() -> datetime:
    """Return the current timestamp as a timezone-naïve :class:`datetime`."""

    return datetime.now()


def _new_id() -> str:
    """Return a new unique identifier for model instances."""

    return str(uuid4())


@dataclass(slots=True)
class BaseModel:
    """Base model that tracks creation and modification timestamps."""

    id: str = field(init=False)
    created_at: datetime = field(init=False)
    updated_at: datetime = field(init=False)

    def __post_init__(self) -> None:
        # Ensure created and updated timestamps start aligned for determinism in tests.
        now = _now()
        self.id = _new_id()
        self.created_at = now
        self.updated_at = now

    def touch(self) -> None:
        """Update the ``updated_at`` timestamp to ``now``."""

        self.updated_at = _now()


@dataclass(slots=True)
class User(BaseModel):
    """User model representing system users."""

    username: str
    email: str
    is_active: bool = True
    role: str = "user"


@dataclass(slots=True)
class Project(BaseModel):
    """Project model for organising tasks."""

    name: str
    description: str | None = None
    owner_id: str = ""
    status: str = "active"
    tags: list[str] = field(default_factory=list)

    def add_tag(self, tag: str) -> None:
        """Attach *tag* to the project if not already present."""

        if tag not in self.tags:
            self.tags.append(tag)
            self.touch()


@dataclass(slots=True)
class Task(BaseModel):
    """Task model with project relationships."""

    title: str
    description: str | None = None
    project_id: str = ""
    assignee_id: str | None = None
    status: str = "todo"
    priority: str = "medium"
    due_date: datetime | None = None

    def mark_complete(self) -> None:
        """Mark the task as completed."""

        self.status = "done"
        self.touch()

    def assign_to(self, user_id: str) -> None:
        """Assign task to a user and refresh timestamps."""

        self.assignee_id = user_id
        self.touch()
