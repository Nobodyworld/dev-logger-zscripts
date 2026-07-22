"""Canonical cross-platform contributor, CI, and release quality gates."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
import venv
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
REPORTS_DIR = ROOT / "reports"
QUALITY_SUMMARY = REPORTS_DIR / "quality-summary.json"
COVERAGE_REPORT = REPORTS_DIR / "coverage.json"
COVERAGE_THRESHOLD = 85

MYPY_TARGETS: tuple[str, ...] = (
    "zscripts/application",
    "zscripts/config.py",
    "zscripts/configuration.py",
    "zscripts/observability/logging.py",
    "zscripts/observability/metrics.py",
    "zscripts/observability/health.py",
    "zscripts/observability/instrumentation.py",
    "zscripts/extensions/scaffolding.py",
    "zscripts/schemas",
)

EXPECTED_ADAPTERS = ("ci", "docker", "dotnet", "go", "java", "javascript", "python", "rust")

CHECK_OPERATIONS: tuple[str, ...] = ("format-check", "lint", "type", "bandit", "tests")
QUALITY_OPERATIONS: tuple[str, ...] = (
    "format-check",
    "lint",
    "type",
    "bandit",
    "audit",
    "binary",
    "tests",
    "coverage",
    "docs",
    "editable-smoke",
    "wheel",
    "zipapp",
    "diagnostics",
)
RELEASE_OPERATIONS: tuple[str, ...] = (
    *QUALITY_OPERATIONS,
    "redaction",
    "gitleaks-worktree",
    "gitleaks-history",
    "clean",
)


class GateFailure(RuntimeError):
    """A quality operation failed with an actionable exit code."""

    def __init__(self, message: str, returncode: int = 1) -> None:
        super().__init__(message)
        self.returncode = returncode


def _display(command: Sequence[str]) -> str:
    return " ".join(f'"{item}"' if " " in item else item for item in command)


def _run(
    command: Sequence[str],
    *,
    cwd: Path = ROOT,
    capture_output: bool = False,
    output_path: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    print(f"$ {_display(command)}", flush=True)
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as stream:
            result = subprocess.run(
                command,
                cwd=cwd,
                check=False,
                text=True,
                stdout=stream,
                stderr=None,
            )
    else:
        result = subprocess.run(
            command,
            cwd=cwd,
            check=False,
            text=True,
            capture_output=capture_output,
        )
    if result.returncode:
        if capture_output:
            if result.stdout:
                print(result.stdout, end="")
            if result.stderr:
                print(result.stderr, end="", file=sys.stderr)
        raise GateFailure(
            f"Command failed with exit code {result.returncode}: {_display(command)}",
            result.returncode,
        )
    return result


def _python_module(module: str, *arguments: str) -> list[str]:
    return [sys.executable, "-m", module, *arguments]


def _simple(command: Sequence[str]) -> Callable[[], dict[str, object] | None]:
    def runner() -> None:
        _run(command)

    return runner


def _run_coverage() -> dict[str, object]:
    _run(_python_module("coverage", "erase"))
    _run(_python_module("coverage", "run", "-m", "pytest"))
    _run(_python_module("coverage", "report", f"--fail-under={COVERAGE_THRESHOLD}"))
    _run(_python_module("coverage", "json", "-o", str(COVERAGE_REPORT)))
    coverage = json.loads(COVERAGE_REPORT.read_text(encoding="utf-8"))
    percent = float(coverage["totals"]["percent_covered"])
    return {"coverage_percent": percent, "coverage_threshold": COVERAGE_THRESHOLD}


def _console_script(environment: Path, name: str) -> Path:
    scripts_dir = environment / ("Scripts" if os.name == "nt" else "bin")
    suffix = ".exe" if os.name == "nt" else ""
    candidate = scripts_dir / f"{name}{suffix}"
    if not candidate.exists():
        raise GateFailure(f"Expected console script is missing: {candidate}")
    return candidate


def _assert_adapter_order(output: str) -> None:
    try:
        payload = json.loads(output)
        actual = tuple(item["identifier"] for item in payload)
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise GateFailure(f"Adapter output was not the expected JSON inventory: {exc}") from exc
    if actual != EXPECTED_ADAPTERS:
        raise GateFailure(f"Unexpected adapter order: expected {EXPECTED_ADAPTERS}, found {actual}")


def _run_editable_smoke() -> dict[str, object]:
    console = _console_script(Path(sys.prefix), "zscripts")
    with tempfile.TemporaryDirectory(prefix="zscripts-editable-smoke-") as directory:
        outside_checkout = Path(directory)
        _run(
            [sys.executable, "-c", "import zscripts; print(zscripts.__file__)"],
            cwd=outside_checkout,
        )
        _run(
            [str(console), "guardrails"],
            cwd=outside_checkout,
            output_path=REPORTS_DIR / "guardrails-editable.json",
        )
        _run(
            [sys.executable, "-m", "zscripts", "guardrails"],
            cwd=outside_checkout,
            output_path=REPORTS_DIR / "guardrails-module.json",
        )
        adapters = _run(
            [str(console), "adapters", "--format", "json"],
            cwd=outside_checkout,
            capture_output=True,
        )
        _assert_adapter_order(adapters.stdout)
    return {"adapter_order": list(EXPECTED_ADAPTERS)}


def _run_wheel_smoke() -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="zscripts-wheel-smoke-") as directory:
        smoke_root = Path(directory)
        wheel_dir = smoke_root / "dist"
        _run(_python_module("build", "--wheel", "--outdir", str(wheel_dir)))
        wheels = list(wheel_dir.glob("*.whl"))
        if len(wheels) != 1:
            raise GateFailure(f"Expected exactly one wheel, found {len(wheels)} in {wheel_dir}")

        environment = smoke_root / "venv"
        venv.EnvBuilder(with_pip=True).create(environment)
        python = _console_script(environment, "python")
        _run([str(python), "-m", "pip", "install", "--upgrade", "pip"], cwd=smoke_root)
        _run([str(python), "-m", "pip", "install", str(wheels[0])], cwd=smoke_root)
        _run(
            [
                str(python),
                "-c",
                "import zscripts, jsonschema, adapters, agents, scripts; "
                "print(zscripts.__file__); print(jsonschema.__file__); print('runtime imports passed')",
            ],
            cwd=smoke_root,
        )
        console = _console_script(environment, "zscripts")
        _run(
            [str(console), "guardrails"],
            cwd=smoke_root,
            output_path=REPORTS_DIR / "guardrails-wheel.json",
        )
        _run(
            [str(python), "-m", "zscripts", "guardrails"],
            cwd=smoke_root,
            output_path=REPORTS_DIR / "guardrails-wheel-module.json",
        )
        adapters = _run(
            [str(console), "adapters", "--format", "json"],
            cwd=smoke_root,
            capture_output=True,
        )
        _assert_adapter_order(adapters.stdout)
    return {"adapter_order": list(EXPECTED_ADAPTERS), "isolated_install": True}


def _run_zipapp_smoke() -> dict[str, object]:
    _run([sys.executable, "scripts/build_artifact.py"])
    bundle = ROOT / "artifacts" / "build" / "zscripts.pyz"
    _run(
        [sys.executable, str(bundle), "guardrails"],
        output_path=REPORTS_DIR / "guardrails-zipapp.json",
    )
    adapters = _run(
        [sys.executable, str(bundle), "adapters", "--format", "json"],
        capture_output=True,
    )
    _assert_adapter_order(adapters.stdout)
    (REPORTS_DIR / "adapters-zipapp.json").write_text(adapters.stdout, encoding="utf-8")
    return {"adapter_order": list(EXPECTED_ADAPTERS)}


def _run_redaction_validation() -> dict[str, object]:
    fixture = ROOT / "examples" / "raw_to_report" / "raw.log"
    output = REPORTS_DIR / "redaction-report.json"
    _run(
        [
            sys.executable,
            "-m",
            "zscripts",
            "--adapter",
            "ci",
            "report",
            "--input",
            str(fixture),
            "--format",
            "json",
            "--redact",
            "--output",
            str(output),
        ]
    )
    content = output.read_text(encoding="utf-8")
    fixture_value = "not-a-real-secret-redaction-fixture-1234567890abcdef"
    if fixture_value in content:
        raise GateFailure("Report redaction validation failed: fixture secret remained in output")
    if "[REDACTED]" not in content:
        raise GateFailure("Report redaction validation failed: expected redaction marker was absent")
    return {"fixture_secret_removed": True, "redaction_marker_present": True}


def _require_gitleaks() -> str:
    executable = shutil.which("gitleaks")
    if executable is None:
        raise GateFailure(
            "Gitleaks is required for the release profile but was not found on PATH. "
            "Install Gitleaks and rerun the release gate."
        )
    return executable


def _run_gitleaks_worktree() -> dict[str, object]:
    _run([_require_gitleaks(), "detect", "--no-git", "--source", ".", "--redact", "--verbose"])
    tracked = _run(["git", "ls-files"], capture_output=True).stdout.splitlines()
    return {"tracked_files": len(tracked)}


def _run_gitleaks_history() -> dict[str, object]:
    count = int(_run(["git", "rev-list", "--count", "HEAD"], capture_output=True).stdout.strip())
    print(f"Scanning full Git history ({count} commits).")
    _run([_require_gitleaks(), "detect", "--source", ".", "--redact", "--verbose"])
    return {"commit_count": count}


def _run_clean_worktree() -> dict[str, object]:
    _run(["git", "diff", "--check"])
    status = _run(["git", "status", "--porcelain"], capture_output=True).stdout.strip()
    if status:
        raise GateFailure(f"Release gate requires a clean worktree; found:\n{status}")
    return {"clean": True}


Operation = Callable[[], dict[str, object] | None]

OPERATIONS: dict[str, Operation] = {
    "format-check": _simple(_python_module("ruff", "format", "--check", ".")),
    "lint": _simple(_python_module("ruff", "check", ".")),
    "type": _simple(_python_module("mypy", *MYPY_TARGETS)),
    "bandit": _simple(_python_module("bandit", "-q", "-r", "zscripts", "examples/sample_project")),
    "audit": _simple(_python_module("pip_audit", "--timeout", "60")),
    "binary": _simple([sys.executable, "scripts/no_binaries.py"]),
    "tests": _simple(_python_module("pytest")),
    "coverage": _run_coverage,
    "docs": _simple([sys.executable, "scripts/validate_docs_links.py"]),
    "editable-smoke": _run_editable_smoke,
    "wheel": _run_wheel_smoke,
    "zipapp": _run_zipapp_smoke,
    "diagnostics": _simple(
        [
            sys.executable,
            "-m",
            "scripts.diagnostics_probe",
            "--include-metrics",
            "--output",
            str(REPORTS_DIR / "diagnostics.json"),
            "--fail-on-status",
            "degraded",
        ]
    ),
    "redaction": _run_redaction_validation,
    "gitleaks-worktree": _run_gitleaks_worktree,
    "gitleaks-history": _run_gitleaks_history,
    "clean": _run_clean_worktree,
}

PROFILES: dict[str, tuple[str, ...]] = {
    "check": CHECK_OPERATIONS,
    "quality": QUALITY_OPERATIONS,
    "release": RELEASE_OPERATIONS,
}


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _execute_operation(name: str) -> tuple[int, dict[str, Any]]:
    start = time.perf_counter()
    result: dict[str, Any] = {"operation": name}
    try:
        details = OPERATIONS[name]() or {}
    except GateFailure as exc:
        result.update(
            status="failed",
            duration_seconds=round(time.perf_counter() - start, 3),
            error=str(exc),
        )
        _write_json(REPORTS_DIR / f"quality-{name}.json", result)
        print(str(exc), file=sys.stderr)
        return exc.returncode, result
    result.update(
        status="passed",
        duration_seconds=round(time.perf_counter() - start, 3),
        details=details,
    )
    _write_json(REPORTS_DIR / f"quality-{name}.json", result)
    return 0, result


def _run_profile(name: str) -> int:
    started = time.perf_counter()
    results: list[dict[str, Any]] = []
    returncode = 0
    for operation in PROFILES[name]:
        print(f"\n== {operation} ==", flush=True)
        returncode, result = _execute_operation(operation)
        results.append(result)
        if returncode:
            break
    payload = {
        "profile": name,
        "status": "passed" if returncode == 0 else "failed",
        "coverage_threshold": COVERAGE_THRESHOLD,
        "operations": results,
        "duration_seconds": round(time.perf_counter() - started, 3),
    }
    _write_json(QUALITY_SUMMARY, payload)
    return returncode


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=(*OPERATIONS, *PROFILES))
    args = parser.parse_args(argv)
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    if args.operation in PROFILES:
        return _run_profile(args.operation)
    return _execute_operation(args.operation)[0]


if __name__ == "__main__":
    raise SystemExit(main())
