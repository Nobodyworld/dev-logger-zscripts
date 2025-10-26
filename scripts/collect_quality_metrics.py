"""Collect repository health metrics (coverage, complexity, dependencies, build)."""

from __future__ import annotations

import argparse
import ast
import compileall
import json
import statistics
import time
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

PACKAGE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PACKAGE = PACKAGE_ROOT / "zscripts"
DEFAULT_COVERAGE = PACKAGE_ROOT / "reports" / "coverage.json"


@dataclass(frozen=True)
class ComplexityResult:
    module: str
    average: float
    maximum: float
    count: int


def _iter_python_files(directory: Path) -> Iterable[Path]:
    for path in sorted(directory.rglob("*.py")):
        if "__pycache__" in path.parts:
            continue
        yield path


class _ComplexityVisitor(ast.NodeVisitor):
    """Compute cyclomatic complexity for a function body."""

    def __init__(self) -> None:
        self.score = 1

    def generic_visit(self, node: ast.AST) -> None:  # type: ignore[override]
        super().generic_visit(node)

    # Decision points that increase complexity counts.
    def visit_If(self, node: ast.If) -> None:  # noqa: N802 - ast hook
        self.score += 1
        self.generic_visit(node)

    def visit_For(self, node: ast.For) -> None:  # noqa: N802 - ast hook
        self.score += 1
        self.generic_visit(node)

    def visit_While(self, node: ast.While) -> None:  # noqa: N802 - ast hook
        self.score += 1
        self.generic_visit(node)

    def visit_AsyncFor(self, node: ast.AsyncFor) -> None:  # noqa: N802 - ast hook
        self.score += 1
        self.generic_visit(node)

    def visit_With(self, node: ast.With) -> None:  # noqa: N802 - ast hook
        self.score += 1
        self.generic_visit(node)

    def visit_AsyncWith(self, node: ast.AsyncWith) -> None:  # noqa: N802 - ast hook
        self.score += 1
        self.generic_visit(node)

    def visit_Try(self, node: ast.Try) -> None:  # noqa: N802 - ast hook
        self.score += len(node.handlers)
        if node.orelse:
            self.score += 1
        if node.finalbody:
            self.score += 1
        self.generic_visit(node)

    def visit_IfExp(self, node: ast.IfExp) -> None:  # noqa: N802 - ast hook
        self.score += 1
        self.generic_visit(node)

    def visit_BoolOp(self, node: ast.BoolOp) -> None:  # noqa: N802 - ast hook
        # ``and`` / ``or`` chain contributes ``len(values) - 1`` decision points.
        self.score += max(len(node.values) - 1, 0)
        self.generic_visit(node)

    def visit_comprehension(self, node: ast.comprehension) -> None:  # noqa: N802 - ast hook
        # Account for implicit loop in comprehensions.
        self.score += 1
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:  # noqa: N802 - ast hook
        # Nested function definitions are handled separately.
        return None

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:  # noqa: N802 - ast hook
        return None

    def visit_ClassDef(self, node: ast.ClassDef) -> None:  # noqa: N802 - ast hook
        return None


def _function_complexity(node: ast.AST) -> int:
    visitor = _ComplexityVisitor()
    if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
        for statement in node.body:
            visitor.visit(statement)
    return visitor.score


def _collect_complexity(package: Path) -> list[ComplexityResult]:
    results: list[ComplexityResult] = []
    for path in _iter_python_files(package):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue
        scores = [
            _function_complexity(node)
            for node in ast.walk(tree)
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef)
        ]
        if not scores:
            continue
        average = statistics.fmean(scores)
        maximum = max(scores)
        results.append(
            ComplexityResult(
                module=str(path.relative_to(PACKAGE_ROOT)),
                average=average,
                maximum=maximum,
                count=len(scores),
            )
        )
    return results


@dataclass(frozen=True)
class DependencyResult:
    module: str
    internal: int
    external: int
    depth_samples: list[int]


def _collect_dependencies(package: Path) -> list[DependencyResult]:
    results: list[DependencyResult] = []
    prefix = package.name
    for path in _iter_python_files(package):
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except (OSError, SyntaxError):
            continue
        internal = 0
        external = 0
        depth_samples: list[int] = []
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    name = alias.name
                    if name.startswith(f"{prefix}."):
                        internal += 1
                        depth_samples.append(name.count(".") + 1)
                    else:
                        external += 1
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                if node.level and not module:
                    internal += 1
                    depth_samples.append(node.level)
                elif module.startswith(prefix):
                    internal += 1
                    depth_samples.append(module.count(".") + 1)
                else:
                    external += 1
        if internal or external:
            results.append(
                DependencyResult(
                    module=str(path.relative_to(PACKAGE_ROOT)),
                    internal=internal,
                    external=external,
                    depth_samples=depth_samples,
                )
            )
    return results


def _measure_compile_time(package: Path) -> float:
    start = time.perf_counter()
    compileall.compile_dir(str(package), quiet=1, force=True)
    return time.perf_counter() - start


def _measure_package_size(package: Path) -> int:
    return sum(path.stat().st_size for path in package.rglob("*") if path.is_file())


def _load_coverage(path: Path) -> float | None:
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError:
        return None
    totals = data.get("totals", {})
    percent = totals.get("percent_covered")
    if isinstance(percent, int | float):
        return float(percent)
    return None


def _summarise_complexity(results: list[ComplexityResult]) -> dict[str, object]:
    if not results:
        return {"average": 0.0, "max": 0.0, "modules": []}
    averages = [item.average for item in results]
    maxima = sorted(results, key=lambda item: item.maximum, reverse=True)[:5]
    return {
        "average": statistics.fmean(averages),
        "max": maxima[0].maximum if maxima else 0.0,
        "modules": [
            {
                "module": item.module,
                "average": round(item.average, 2),
                "max": item.maximum,
            }
            for item in maxima
        ],
    }


def _summarise_dependencies(results: list[DependencyResult]) -> dict[str, object]:
    if not results:
        return {"internal_ratio": 0.0, "external_ratio": 0.0, "average_depth": 0.0}
    internal = sum(item.internal for item in results)
    external = sum(item.external for item in results)
    total = internal + external
    depth_samples = [sample for item in results for sample in item.depth_samples]
    average_depth = statistics.fmean(depth_samples) if depth_samples else 0.0
    internal_ratio = internal / total if total else 0.0
    external_ratio = external / total if total else 0.0
    return {
        "internal_ratio": round(internal_ratio, 3),
        "external_ratio": round(external_ratio, 3),
        "average_depth": round(average_depth, 2),
        "totals": {"internal": internal, "external": external},
    }


def collect_metrics(package: Path, coverage_path: Path) -> dict[str, object]:
    complexity = _collect_complexity(package)
    dependencies = _collect_dependencies(package)
    coverage = _load_coverage(coverage_path)
    compile_time = _measure_compile_time(package)
    size_bytes = _measure_package_size(package)
    return {
        "coverage_percent": coverage,
        "complexity": _summarise_complexity(complexity),
        "dependencies": _summarise_dependencies(dependencies),
        "compile_time_seconds": round(compile_time, 3),
        "package_size_bytes": size_bytes,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", type=Path, default=DEFAULT_PACKAGE, help="Root package to analyse")
    parser.add_argument("--coverage", type=Path, default=DEFAULT_COVERAGE, help="Path to coverage JSON output")
    parser.add_argument("--output", type=Path, help="Optional file to write JSON metrics")
    args = parser.parse_args()

    metrics = collect_metrics(args.package, args.coverage)
    payload = json.dumps(metrics, indent=2, sort_keys=True)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(payload + "\n", encoding="utf-8")
    else:
        print(payload)


if __name__ == "__main__":
    main()
