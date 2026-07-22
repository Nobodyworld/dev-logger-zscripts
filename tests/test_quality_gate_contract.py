from __future__ import annotations

import re
import tomllib
from pathlib import Path

import yaml

from scripts import quality_gate

ROOT = Path(__file__).resolve().parents[1]


def _read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def test_workflow_keeps_quality_job_and_delegates_each_operation() -> None:
    workflow = yaml.safe_load(_read(".github/workflows/ci.yml"))
    jobs = workflow["jobs"]
    assert "quality" in jobs
    assert jobs["quality"]["timeout-minutes"] == 30
    assert workflow["permissions"] == {"contents": "read"}

    calls: list[str] = []
    for step in jobs["quality"]["steps"]:
        for line in str(step.get("run", "")).splitlines():
            match = re.fullmatch(r"\s*python scripts/quality_gate\.py ([a-z-]+)\s*", line)
            if match:
                calls.append(match.group(1))
    assert calls == list(quality_gate.QUALITY_OPERATIONS)

    upload = jobs["quality"]["steps"][-1]
    assert upload["if"] == "always()"
    assert upload["with"]["path"] == "reports/"
    for step in jobs["quality"]["steps"]:
        if "uses" in step:
            assert re.search(r"@[0-9a-f]{40}$", step["uses"])


def test_make_profiles_delegate_to_the_canonical_script() -> None:
    makefile = _read("Makefile")
    for target in ("check", "quality", "release"):
        pattern = rf"(?m)^{target}:\n\t\$\(QUALITY_GATE\) {target}$"
        assert re.search(pattern, makefile), f"make {target} does not delegate canonically"
    assert "MYPY_TARGETS" not in makefile


def test_supported_mypy_targets_have_one_authoritative_definition() -> None:
    assert quality_gate.MYPY_TARGETS
    drift_surfaces = "\n".join(
        _read(path) for path in ("Makefile", ".github/workflows/ci.yml", ".pre-commit-config.yaml")
    )
    for target in quality_gate.MYPY_TARGETS:
        assert target not in drift_surfaces


def test_yaml_and_toml_contracts_parse_with_real_parsers() -> None:
    pre_commit = yaml.safe_load(_read(".pre-commit-config.yaml"))
    local = next(repo for repo in pre_commit["repos"] if repo["repo"] == "local")
    commit_hook = next(hook for hook in local["hooks"] if hook["id"] == "conventional-commit-message")
    assert commit_hook["entry"] == "python scripts/validate_commit_message.py"
    assert commit_hook["stages"] == ["commit-msg"]
    assert "npx --yes" not in _read(".pre-commit-config.yaml")

    project = tomllib.loads(_read("pyproject.toml"))
    assert any(item.startswith("PyYAML") for item in project["project"]["optional-dependencies"]["dev"])


def test_active_scripts_do_not_invoke_black_or_nonexistent_helpers() -> None:
    for script in (ROOT / "scripts").glob("*.py"):
        source = script.read_text(encoding="utf-8").lower()
        assert not re.search(r"(?:-m\s+black|[\"']black[\"'])", source), script.name
    gate_source = _read("scripts/quality_gate.py")
    assert '"helpers' not in gate_source
    assert "'helpers" not in gate_source


def test_documented_profiles_match_the_implementation() -> None:
    contributing = _read("CONTRIBUTING.md")
    for name, operations in quality_gate.PROFILES.items():
        expected = f"`{name}`: " + ", ".join(f"`{operation}`" for operation in operations)
        assert expected in contributing


def test_obsolete_runners_are_removed_from_active_contracts() -> None:
    assert not (ROOT / "scripts/dev_start.py").exists()
    assert not (ROOT / "scripts/tasks.py").exists()
    assert not (ROOT / "scripts/agent_guard.py").exists()
    assert not (ROOT / "scripts/run_pytest_with_trace.py").exists()
    assert not (ROOT / "scripts/trace_coverage_summary.py").exists()
    active_docs = (
        "README.md",
        "CONTRIBUTING.md",
        "scripts/README.md",
        "tests/README.md",
        "docs/architecture/ARCHITECTURE_OVERVIEW.md",
        "docs/automation/AUTOMATION.md",
        "docs/automation/AUTOMATION_ROLES.md",
        "docs/guides/GITHUB_ACTIONS_USAGE.md",
        "docs/operations/BASELINE.md",
        "docs/operations/INCIDENT_RESPONSE.md",
    )
    content = "\n".join(_read(path) for path in active_docs)
    assert "scripts/dev_start.py" not in content
    assert "scripts/tasks.py" not in content
