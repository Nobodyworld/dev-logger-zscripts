import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def run(cmd: list[str]) -> int:
    """Run a command in the repo root and echo it."""
    print("$", " ".join(cmd))
    return subprocess.call(cmd, cwd=str(ROOT))


def run_env(cmd: list[str], env: dict[str, str] | None = None) -> int:
    """Run a command with an augmented environment at repo root."""
    print("$", " ".join(cmd))
    proc_env = os.environ.copy()
    if env:
        proc_env.update(env)
    return subprocess.call(cmd, cwd=str(ROOT), env=proc_env)


def fmt() -> int:
    """Format code with black and auto-fix lint with ruff."""
    code = 0
    code |= run([sys.executable, "-m", "black", "zscripts", "scripts", "--quiet"]) or 0
    code |= run([sys.executable, "-m", "ruff", "check", "--fix", "zscripts", "scripts"]) or 0
    return code


def lint() -> int:
    """Run ruff checks without applying fixes."""
    return run([sys.executable, "-m", "ruff", "check", "zscripts", "scripts"]) or 0


def test() -> int:
    """Run simple smoke tests under tests/ with PYTHONPATH set to repo root."""
    tests_dir = ROOT / "tests"
    if not tests_dir.exists():
        print("No tests/ directory found.")
        return 0
    env = {"PYTHONPATH": str(ROOT)}
    code = 0
    for path in sorted(tests_dir.glob("*.py")):
        code |= run_env([sys.executable, str(path)], env=env) or 0
    return code


def check() -> int:
    """Environment sanity checks (env vars, required files)."""
    missing: list[str] = []
    required_files = [
        ROOT / "README.md",
        ROOT / "docs" / "STYLE-GUIDE.md",
        ROOT / "docs" / "TASKLIST.md",
        ROOT / "pyproject.toml",
    ]
    for rf in required_files:
        if not rf.exists():
            missing.append(str(rf.relative_to(ROOT)))

    org_root = os.environ.get("ORGANIZATION_STORAGE_ROOT", "")
    if not org_root:
        print("Note: ORGANIZATION_STORAGE_ROOT is not set; org_path() will default to CWD.")

    if missing:
        print("Missing required files:")
        for m in missing:
            print(" -", m)
        return 1

    print("Environment looks good.")
    return 0


def all_tasks() -> int:
    """Run formatting, linting, and tests in sequence."""
    code = 0
    code |= fmt() or 0
    code |= lint() or 0
    code |= test() or 0
    return code


def gate() -> int:
    """Run the automated quality gate pipeline."""
    return run([sys.executable, str(ROOT / "scripts" / "quality_gate.py")]) or 0


def main() -> int:
    """Entry point for dev tasks (fmt|lint)."""
    if len(sys.argv) < 2:
        print("Usage: python scripts/tasks.py [fmt|lint|test|check|all|gate]")
        return 2
    task = sys.argv[1]
    if task == "fmt":
        return fmt()
    if task == "lint":
        return lint()
    if task == "test":
        return test()
    if task == "check":
        return check()
    if task == "all":
        return all_tasks()
    if task == "gate":
        return gate()
    print(f"Unknown task: {task}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
