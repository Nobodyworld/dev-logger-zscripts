"""Automation entry points for linting and testing zscripts."""

from __future__ import annotations

import nox

PYTHON_VERSIONS = ["3.11"]


@nox.session(python=PYTHON_VERSIONS)
def tests(session: nox.Session) -> None:
    """Run the pytest suite."""

    session.install("-e", ".", "pytest")
    session.run("pytest")


@nox.session(python=PYTHON_VERSIONS)
def lint(session: nox.Session) -> None:
    """Run ruff linting."""

    session.install("ruff")
    session.run("ruff", "check", "--fix", "--exit-non-zero-on-fix")
