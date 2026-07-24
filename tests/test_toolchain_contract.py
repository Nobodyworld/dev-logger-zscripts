from __future__ import annotations

import tomllib
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUFF_CONSTRAINT = "ruff==0.15.22"


def test_ruff_formatter_contract_is_exact_and_aligned() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    dev_dependencies = project["project"]["optional-dependencies"]["dev"]
    requirement_lines = {
        line.strip()
        for line in (ROOT / "configs/requirements/dev.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }

    assert RUFF_CONSTRAINT in dev_dependencies
    assert RUFF_CONSTRAINT in requirement_lines
    assert not any(
        dependency.startswith("ruff") and dependency != RUFF_CONSTRAINT for dependency in dev_dependencies
    )
    assert not any(
        dependency.startswith("ruff") and dependency != RUFF_CONSTRAINT for dependency in requirement_lines
    )
