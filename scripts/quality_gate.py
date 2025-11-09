"""Automation script enforcing linting, typing, testing, and coverage gates."""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
COVERAGE_THRESHOLD = 85


def run_command(cmd: Sequence[str]) -> int:
    print("$", " ".join(cmd))
    proc = subprocess.run(cmd, cwd=ROOT)
    if proc.returncode != 0:
        print(f"Command {' '.join(cmd)} failed with exit code {proc.returncode}")
    return proc.returncode


def collect_coverage() -> int:
    tests_dir = ROOT / "tests"
    test_files = sorted(str(path.relative_to(ROOT)) for path in tests_dir.glob("*.py"))
    if not test_files:
        print("No targeted tests found for coverage analysis.")
        return 0

    coverage_dir = ROOT / "artifacts" / "coverage"
    raw_dir = coverage_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    for stale in raw_dir.glob("*.cover"):
        stale.unlink()
    trace_cmd = [
        sys.executable,
        "-m",
        "trace",
        "--count",
        f"--coverdir={raw_dir}",
        "--module",
        "pytest",
        *test_files,
    ]
    print("$", " ".join(trace_cmd))
    proc = subprocess.run(trace_cmd, cwd=ROOT, capture_output=True, text=True)
    (raw_dir / "trace.log").write_text(
        proc.stdout + ("\n" + proc.stderr if proc.stderr else ""), encoding="utf-8"
    )
    if proc.returncode != 0:
        print(proc.stderr)
        return proc.returncode

    summary_cmd = [
        sys.executable,
        str(ROOT / "scripts" / "trace_coverage_summary.py"),
        str(raw_dir),
    ]
    print("$", " ".join(summary_cmd))
    summary_proc = subprocess.run(summary_cmd, cwd=ROOT)
    if summary_proc.returncode != 0:
        print("Coverage summary generation failed")
        return summary_proc.returncode

    summary_path = coverage_dir / "summary.json"
    summary = json.loads(summary_path.read_text(encoding="utf-8"))
    modules = summary.get("modules", [])
    if not modules:
        print("Warning: no modules captured in coverage summary")
        return 1
    minimum = min(module["coverage"] for module in modules)
    print(f"Minimum helpers.web_crawl coverage: {minimum}%")
    if minimum < COVERAGE_THRESHOLD:
        print(
            f"Coverage threshold not met: required {COVERAGE_THRESHOLD}%, observed {minimum}%"
        )
        return 1
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skip-bandit", action="store_true", help="Skip Bandit security scan")
    args = parser.parse_args(argv)

    status = 0
    status |= run_command(
        [sys.executable, "-m", "ruff", "check", "helpers", "scripts", "tests"]
    ) or 0
    status |= run_command(
        [
            sys.executable,
            "-m",
            "mypy",
            "helpers/web_crawl/crawler.py",
            "helpers/web_crawl/extensions.py",
            "helpers/web_crawl/telemetry.py",
            "helpers/web_crawl/health.py",
        ]
    ) or 0
    status |= run_command([sys.executable, "-m", "pytest", "-q"]) or 0
    if not args.skip_bandit:
        if importlib.util.find_spec("bandit") is None:
            print("Bandit not installed; skipping security scan")
        else:
            status |= run_command(
                [sys.executable, "-m", "bandit", "-q", "-r", "helpers/web_crawl"]
            ) or 0
    if status != 0:
        return status
    status |= collect_coverage() or 0
    return status


if __name__ == "__main__":  # pragma: no cover - CLI entry point
    raise SystemExit(main(sys.argv[1:]))

