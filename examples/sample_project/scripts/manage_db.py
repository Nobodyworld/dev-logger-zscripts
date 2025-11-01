"""CLI entry point for managing the sample project's in-memory database."""

from __future__ import annotations

import argparse
import logging
import sys
from collections.abc import Callable
from pathlib import Path
from typing import cast

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from sample_project.backend.service import TaskService  # noqa: E402

LOGGER = logging.getLogger("sample_project.manage_db")
ERROR_ID_INVALID_DIRECTION = "DB001"
ERROR_ID_RUNTIME = "DB999"


class DatabaseManager:
    """Manages database operations for the Task Management System."""

    def __init__(self, service: TaskService) -> None:
        self.service = service

    def create_tables(self) -> None:
        """Create database tables (simplified for in-memory storage)."""

        LOGGER.info("event=create_tables status=started")
        self.service.tasks.clear()
        self.service.projects.clear()
        self.service.users.clear()
        LOGGER.info("event=create_tables status=completed")

    def drop_tables(self) -> None:
        """Drop database tables."""

        LOGGER.info("event=drop_tables status=started")
        self.service.tasks.clear()
        self.service.projects.clear()
        self.service.users.clear()
        LOGGER.info("event=drop_tables status=completed")

    def migrate(self, direction: str = "up") -> None:
        """Run database migrations."""

        if direction not in {"up", "down"}:
            raise ValueError(f"Invalid migration direction: {direction}")

        LOGGER.info("event=migrate direction=%s", direction)

    def seed(self) -> None:
        """Seed database with sample data."""

        LOGGER.info("event=seed status=started")

        users = [
            self.service.add_user("Alice Johnson", "alice@example.com"),
            self.service.add_user("Bob Smith", "bob@example.com"),
            self.service.add_user("Carol Williams", "carol@example.com"),
        ]

        projects = [
            self.service.create_project(
                "Task Management System",
                "A comprehensive task and project management application",
            ),
            self.service.create_project(
                "API Development",
                "RESTful API development for backend services",
            ),
        ]

        tasks = [
            self.service.create_task(
                "Implement user authentication",
                "Add login/logout functionality with JWT tokens",
                projects[0].id,
                "high",
            ),
            self.service.create_task(
                "Design database schema",
                "Create ER diagram and define table relationships",
                projects[0].id,
                "medium",
            ),
            self.service.create_task(
                "Create API endpoints",
                "Implement CRUD operations for tasks and projects",
                projects[1].id,
                "high",
            ),
            self.service.create_task(
                "Add input validation",
                "Implement comprehensive input validation and error handling",
                projects[1].id,
                "medium",
            ),
        ]

        self.service.assign_task(tasks[0].id, users[0].id)
        self.service.assign_task(tasks[1].id, users[1].id)
        self.service.assign_task(tasks[2].id, users[2].id)
        self.service.mark_task_complete(tasks[1].id)

        LOGGER.info(
            "event=seed status=completed users=%d projects=%d tasks=%d",
            len(users),
            len(projects),
            len(tasks),
        )

    def reset(self) -> None:
        """Reset database to clean state."""

        LOGGER.info("event=reset status=started")
        self.drop_tables()
        self.create_tables()
        LOGGER.info("event=reset status=completed")

    def status(self) -> None:
        """Show database status and statistics."""

        LOGGER.info(
            "event=status users=%d projects=%d tasks=%d",
            len(self.service.users),
            len(self.service.projects),
            len(self.service.tasks),
        )


def _configure_logging(verbose: bool) -> None:
    """Initialise logging with INFO or DEBUG verbosity."""

    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(levelname)s %(name)s %(message)s")


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser shared across invocations."""

    parser = argparse.ArgumentParser(
        description="Database management for Task Management System",
    )
    parser.add_argument(
        "command",
        choices=["create", "drop", "migrate", "seed", "reset", "status"],
        help="Database command to execute",
    )
    parser.add_argument(
        "--direction",
        choices=["up", "down"],
        default="up",
        help="Migration direction (default: up)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    return parser


def dispatch(manager: DatabaseManager, command: str, direction: str) -> None:
    """Execute the requested *command* on *manager* with optional *direction*."""

    commands: dict[str, Callable[[], None]] = {
        "create": manager.create_tables,
        "drop": manager.drop_tables,
        "seed": manager.seed,
        "reset": manager.reset,
        "status": manager.status,
        "migrate": lambda: manager.migrate(direction),
    }
    commands[command]()


def main(argv: list[str] | None = None) -> int:
    """Entrypoint used by the ``manage_db`` script and tests."""

    parser = build_parser()
    args = parser.parse_args(argv)
    verbose_flag = cast(bool, getattr(args, "verbose", False))
    _configure_logging(verbose_flag)

    service = TaskService()
    manager = DatabaseManager(service)

    command = cast(str, args.command)
    direction = cast(str, args.direction)

    try:
        dispatch(manager, command, direction)
    except ValueError as exc:
        LOGGER.error(
            "event=command_failed error_id=%s command=%s reason=%s",
            ERROR_ID_INVALID_DIRECTION,
            command,
            exc,
        )
        return 2
    except Exception as exc:  # pragma: no cover - defensive logging
        LOGGER.exception("event=command_failed error_id=%s command=%s", ERROR_ID_RUNTIME, command)
        raise SystemExit(1) from exc

    LOGGER.info("event=command_completed command=%s", command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
