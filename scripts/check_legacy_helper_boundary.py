"""Enforce the non-executing Phase 2A legacy-helper compatibility boundary."""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
import zipfile
from collections import defaultdict
from collections.abc import Sequence
from pathlib import Path, PurePosixPath
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
HELPER_SCOPE = "zscripts/helpers"
SURFACE_PATH = ROOT / "docs/operations/legacy_helper_surface.json"
COMPATIBILITY_PATH = ROOT / "docs/operations/legacy_helper_compatibility.json"
INVENTORY_PATH = ROOT / "docs/operations/legacy_helper_inventory.json"
REGISTRY_PATH = ROOT / "configs/registry.yaml"
EXPECTED_MODULE_COUNT = 154

MAINTAINED_CORE_SCOPES = (
    "zscripts/application",
    "zscripts/domain",
    "zscripts/infrastructure",
    "zscripts/observability",
    "zscripts/extensions",
    "zscripts/schemas",
    "adapters",
    "agents",
)

WINDOW = {
    "start_event": "phase2a_merge",
    "minimum_days": 90,
    "minimum_public_beta_cycles": 1,
    "eligibility_rule": "whichever-is-later",
}

PHASE2B_PROPOSALS = {
    "zscripts.helpers.numpy.array_utils": "migrate",
    "zscripts.helpers.pandas.concat_csvs": "retire-review",
    "zscripts.helpers.pandas.excel_to_json_posts": "migrate",
    "zscripts.helpers.pillow.add_watermark": "migrate",
    "zscripts.helpers.pillow.ratio_image_2": "retire-review",
    "zscripts.helpers.requests.http": "retire-review",
    "zscripts.helpers.web_crawl.html_ops": "migrate",
}

ALLOWED_RISKS = {"low", "moderate", "high", "critical-review"}
ALLOWED_PROPOSALS = {"shim", "migrate", "retire-review"}
WINDOW_KEYS = set(WINDOW)
WINDOW_DATE_RE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
WINDOWS_ABSOLUTE_RE = re.compile(r"(?<![A-Za-z])[A-Za-z]:[\\/]")
POSIX_USER_PATH_RE = re.compile(r"/(?:Users|home|tmp)/")


class BoundaryError(RuntimeError):
    """Raised when a Phase 2A compatibility contract is violated."""


def _git(*arguments: str) -> str:
    result = subprocess.run(
        ["git", *arguments],
        cwd=ROOT,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip()
        raise BoundaryError(f"git {' '.join(arguments)} failed: {detail}")
    return result.stdout


def _tracked_under(scope: str, suffix: str) -> list[str]:
    prefix = f"{scope.rstrip('/')}/"
    return sorted(
        PurePosixPath(line).as_posix()
        for line in _git("ls-files", scope).splitlines()
        if (line == scope or line.startswith(prefix)) and line.endswith(suffix)
    )


def tracked_helper_modules() -> list[str]:
    """Return every tracked helper Python path without importing helper source."""
    return _tracked_under(HELPER_SCOPE, ".py")


def build_surface_payload() -> dict[str, Any]:
    modules = tracked_helper_modules()
    return {
        "schema_version": 1,
        "authoritative_scope": HELPER_SCOPE,
        "phase": "2A",
        "module_count": len(modules),
        "modules": modules,
        "expansion_policy": "owner-approved-security-or-compatibility-exception-only",
    }


def _serialize(payload: object) -> str:
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_serialize(payload), encoding="utf-8", newline="\n")


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise BoundaryError(f"cannot read valid JSON from {path.relative_to(ROOT)}: {exc}") from exc
    if not isinstance(payload, dict):
        raise BoundaryError(f"expected a JSON object in {path.relative_to(ROOT)}")
    return payload


def _assert_no_local_absolute_paths(payload: object, label: str) -> None:
    serialized = _serialize(payload)
    if WINDOWS_ABSOLUTE_RE.search(serialized) or POSIX_USER_PATH_RE.search(serialized):
        raise BoundaryError(f"{label} contains a local absolute path")


def validate_surface_payload(
    payload: dict[str, Any], tracked_modules: list[str] | None = None
) -> dict[str, int]:
    modules = payload.get("modules")
    if not isinstance(modules, list) or not all(isinstance(item, str) for item in modules):
        raise BoundaryError("surface modules must be a JSON string array")
    if len(modules) != len(set(modules)):
        raise BoundaryError("surface baseline contains duplicate module paths")
    if modules != sorted(modules):
        raise BoundaryError("surface baseline module paths are not sorted")
    if any(PurePosixPath(item).as_posix() != item for item in modules):
        raise BoundaryError("surface baseline paths must use repository-relative POSIX form")
    if any(not item.startswith(f"{HELPER_SCOPE}/") or not item.endswith(".py") for item in modules):
        raise BoundaryError("surface baseline contains a path outside tracked helper Python scope")
    if payload.get("module_count") != len(modules):
        raise BoundaryError("surface module_count does not match the modules array")
    if len(modules) != EXPECTED_MODULE_COUNT:
        raise BoundaryError(
            f"Phase 2A surface must contain {EXPECTED_MODULE_COUNT} modules; found {len(modules)}"
        )
    expected_metadata = {
        "schema_version": 1,
        "authoritative_scope": HELPER_SCOPE,
        "phase": "2A",
        "expansion_policy": "owner-approved-security-or-compatibility-exception-only",
    }
    for key, expected in expected_metadata.items():
        if payload.get(key) != expected:
            raise BoundaryError(f"surface {key} must be {expected!r}")
    tracked = tracked_helper_modules() if tracked_modules is None else tracked_modules
    added = sorted(set(tracked) - set(modules))
    missing = sorted(set(modules) - set(tracked))
    if added or missing:
        raise BoundaryError(f"helper surface drift: added={added}, missing={missing}")
    _assert_no_local_absolute_paths(payload, "surface baseline")
    return {"tracked_modules": len(tracked), "baseline_modules": len(modules)}


def check_surface(path: Path = SURFACE_PATH) -> dict[str, int]:
    return validate_surface_payload(_load_json(path))


def _parse_registry() -> dict[str, tuple[str, str]]:
    try:
        lines = REGISTRY_PATH.read_text(encoding="utf-8").splitlines()
    except OSError as exc:
        raise BoundaryError(f"cannot read configs/registry.yaml: {exc}") from exc
    registry: dict[str, tuple[str, str]] = {}
    for number, raw in enumerate(lines, start=1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if ": " not in line:
            raise BoundaryError(f"registry line {number} is not a flat key/value mapping")
        key, target = line.split(": ", 1)
        if key in registry:
            raise BoundaryError(f"duplicate registry key: {key}")
        if ":" not in target:
            raise BoundaryError(f"registry target lacks module:callable form at line {number}")
        module, callable_name = target.rsplit(":", 1)
        registry[key] = (module, callable_name)
    return registry


def _inventory_records() -> dict[str, dict[str, Any]]:
    payload = _load_json(INVENTORY_PATH)
    records = payload.get("modules")
    if not isinstance(records, list):
        raise BoundaryError("legacy helper inventory modules must be an array")
    by_module: dict[str, dict[str, Any]] = {}
    for record in records:
        if not isinstance(record, dict) or not isinstance(record.get("module"), str):
            raise BoundaryError("legacy helper inventory contains an invalid module record")
        by_module[record["module"]] = record
    return by_module


def build_compatibility_payload() -> dict[str, Any]:
    registry = _parse_registry()
    inventory = _inventory_records()
    grouped: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for key, (module, callable_name) in registry.items():
        grouped[module].append((key, callable_name))
    if set(grouped) != set(PHASE2B_PROPOSALS):
        raise BoundaryError(
            "registry-exposed modules differ from reviewed Phase 2A compatibility points: "
            f"registry={sorted(grouped)}, reviewed={sorted(PHASE2B_PROPOSALS)}"
        )

    points: list[dict[str, Any]] = []
    for module in sorted(grouped):
        if module not in inventory:
            raise BoundaryError(f"registry module is absent from merged inventory: {module}")
        evidence = inventory[module]
        points.append(
            {
                "registry_keys": sorted(key for key, _ in grouped[module]),
                "module": module,
                "callables": sorted(callable_name for _, callable_name in grouped[module]),
                "compatibility_status": "temporary-compatibility",
                "behavioral_support": False,
                "shim_policy": "none-in-phase-2a",
                "phase2b_proposal": PHASE2B_PROPOSALS[module],
                "owner": "unassigned",
                "static_risk": evidence["static_risk"],
                "third_party_imports": evidence["third_party_imports"],
                "import_time_side_effects": bool(evidence["top_level_executable_statements"]),
                "compatibility_window": dict(WINDOW),
            }
        )
    return {
        "schema_version": 1,
        "phase": "2A",
        "source_registry": "configs/registry.yaml",
        "source_inventory": "docs/operations/legacy_helper_inventory.json",
        "compatibility_point_count": len(points),
        "approved_owner_identifiers": [],
        "default_policy": {
            "applies_to": "all-tracked-helper-modules-except-explicit-compatibility-points",
            "compatibility_status": "legacy-unsupported",
            "behavioral_support": False,
            "wheel_inclusion": "temporarily-wheel-included",
            "shim_policy": "none-in-phase-2a",
            "phase2b_requires_owner_approval": True,
        },
        "compatibility_points": points,
    }


def validate_compatibility_payload(payload: dict[str, Any]) -> dict[str, int]:
    if payload.get("schema_version") != 1 or payload.get("phase") != "2A":
        raise BoundaryError("compatibility manifest must use schema 1 and phase 2A")
    expected_default = build_compatibility_payload()["default_policy"]
    if payload.get("default_policy") != expected_default:
        raise BoundaryError("compatibility default policy does not match the approved Phase 2A contract")
    approved_owners = payload.get("approved_owner_identifiers")
    if not isinstance(approved_owners, list) or not all(
        isinstance(owner, str) and owner for owner in approved_owners
    ):
        raise BoundaryError("approved_owner_identifiers must be a string array")
    if approved_owners != sorted(set(approved_owners)):
        raise BoundaryError("approved_owner_identifiers must be unique and sorted")

    points = payload.get("compatibility_points")
    if not isinstance(points, list) or len(points) != 7:
        raise BoundaryError("compatibility manifest must contain exactly seven explicit modules")
    modules = [point.get("module") for point in points if isinstance(point, dict)]
    if len(modules) != 7 or modules != sorted(modules) or len(modules) != len(set(modules)):
        raise BoundaryError("compatibility modules must be seven unique sorted strings")
    if payload.get("compatibility_point_count") != len(points):
        raise BoundaryError("compatibility_point_count does not match compatibility_points")

    expected_points = {
        point["module"]: point for point in build_compatibility_payload()["compatibility_points"]
    }
    allowed_owners = {"unassigned", *approved_owners}
    seen_registry_keys: set[str] = set()
    for point in points:
        if not isinstance(point, dict):
            raise BoundaryError("compatibility point must be a JSON object")
        module = point["module"]
        expected = expected_points.get(module)
        if expected is None:
            raise BoundaryError(f"unexpected compatibility module: {module}")
        for key, expected_value in expected.items():
            if key == "owner":
                continue
            if point.get(key) != expected_value:
                raise BoundaryError(f"compatibility field drift for {module}: {key}")
        if point.get("owner") not in allowed_owners:
            raise BoundaryError(f"unapproved owner for {module}: {point.get('owner')!r}")
        if point.get("static_risk") not in ALLOWED_RISKS:
            raise BoundaryError(f"invalid static risk for {module}")
        if point.get("phase2b_proposal") not in ALLOWED_PROPOSALS:
            raise BoundaryError(f"invalid Phase 2B proposal for {module}")
        window = point.get("compatibility_window")
        if not isinstance(window, dict) or set(window) != WINDOW_KEYS or window != WINDOW:
            raise BoundaryError(f"invalid compatibility window for {module}")
        registry_keys = point.get("registry_keys")
        if not isinstance(registry_keys, list):
            raise BoundaryError(f"registry_keys must be an array for {module}")
        seen_registry_keys.update(registry_keys)

    registry_keys = set(_parse_registry())
    if seen_registry_keys != registry_keys:
        raise BoundaryError(
            f"compatibility registry coverage drift: missing={sorted(registry_keys - seen_registry_keys)}, "
            f"extra={sorted(seen_registry_keys - registry_keys)}"
        )
    serialized = _serialize(payload)
    if WINDOW_DATE_RE.search(serialized):
        raise BoundaryError("compatibility manifest must not invent a fixed Phase 2B calendar date")
    _assert_no_local_absolute_paths(payload, "compatibility manifest")
    return {"compatibility_points": len(points), "registry_keys": len(registry_keys)}


def check_compatibility(path: Path = COMPATIBILITY_PATH) -> dict[str, int]:
    return validate_compatibility_payload(_load_json(path))


def _is_forbidden_import(name: str | None) -> bool:
    return bool(
        name
        and (
            name == "helpers"
            or name.startswith("helpers.")
            or name == "zscripts.helpers"
            or name.startswith("zscripts.helpers.")
        )
    )


def find_core_import_violations(source: str, path: str = "<synthetic>") -> list[str]:
    try:
        tree = ast.parse(source, filename=path)
    except SyntaxError as exc:
        raise BoundaryError(f"syntax error in maintained core file {path}:{exc.lineno}: {exc.msg}") from exc
    violations: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if _is_forbidden_import(alias.name):
                    violations.add(f"{path}:{node.lineno}: import {alias.name}")
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and _is_forbidden_import(node.module):
            violations.add(f"{path}:{node.lineno}: from {node.module} import ...")
        elif isinstance(node, ast.Call):
            call_name = None
            if isinstance(node.func, ast.Name):
                call_name = node.func.id
            elif isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name):
                call_name = f"{node.func.value.id}.{node.func.attr}"
            if call_name in {"__import__", "importlib.import_module"} and node.args:
                first = node.args[0]
                if isinstance(first, ast.Constant) and isinstance(first.value, str):
                    if _is_forbidden_import(first.value):
                        violations.add(f"{path}:{node.lineno}: dynamic import {first.value}")
    return sorted(violations)


def tracked_core_python_paths() -> list[str]:
    paths = {path for scope in MAINTAINED_CORE_SCOPES for path in _tracked_under(scope, ".py")}
    return sorted(paths)


def check_core_boundary() -> dict[str, int]:
    paths = tracked_core_python_paths()
    violations: list[str] = []
    for path in paths:
        source = (ROOT / PurePosixPath(path)).read_text(encoding="utf-8")
        violations.extend(find_core_import_violations(source, path))
    if violations:
        raise BoundaryError("maintained core imports legacy helpers:\n" + "\n".join(violations))
    return {"maintained_core_modules": len(paths), "helper_import_violations": 0}


def check_wheel(wheel_path: Path, surface_path: Path = SURFACE_PATH) -> dict[str, int]:
    surface = _load_json(surface_path)
    validate_surface_payload(surface)
    try:
        with zipfile.ZipFile(wheel_path.resolve()) as archive:
            members = set(archive.namelist())
    except (OSError, zipfile.BadZipFile) as exc:
        raise BoundaryError(f"cannot inspect wheel {wheel_path}: {exc}") from exc
    modules = surface["modules"]
    missing = [module for module in modules if module not in members]
    if missing:
        raise BoundaryError(f"wheel is missing baseline helper modules: {missing}")
    return {"helper_modules_included": len(modules), "helper_modules_missing": 0}


def check_helper_immutability(base_sha: str) -> dict[str, int]:
    committed = [
        line
        for line in _git("diff", "--name-only", f"{base_sha}...HEAD", "--", HELPER_SCOPE).splitlines()
        if line
    ]
    worktree = [line for line in _git("status", "--porcelain", "--", HELPER_SCOPE).splitlines() if line]
    if committed or worktree:
        raise BoundaryError(f"helper source changes detected: committed={committed}, worktree={worktree}")
    return {"helper_source_changes": 0}


def _print_result(name: str, result: dict[str, int]) -> None:
    details = ", ".join(f"{key}={value}" for key, value in sorted(result.items()))
    print(f"Legacy helper {name} check passed: {details}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="operation", required=True)
    surface = subparsers.add_parser("surface")
    surface.add_argument("--write", action="store_true")
    compatibility = subparsers.add_parser("compatibility")
    compatibility.add_argument("--write", action="store_true")
    subparsers.add_parser("boundary")
    wheel = subparsers.add_parser("wheel")
    wheel.add_argument("--wheel", type=Path, required=True)
    immutability = subparsers.add_parser("immutability")
    immutability.add_argument("--base-sha", required=True)
    arguments = parser.parse_args(argv)

    try:
        if arguments.operation == "surface":
            if arguments.write:
                write_json(SURFACE_PATH, build_surface_payload())
            _print_result("surface", check_surface())
        elif arguments.operation == "compatibility":
            if arguments.write:
                write_json(COMPATIBILITY_PATH, build_compatibility_payload())
            _print_result("compatibility", check_compatibility())
        elif arguments.operation == "boundary":
            _print_result("core boundary", check_core_boundary())
        elif arguments.operation == "wheel":
            _print_result("wheel", check_wheel(arguments.wheel))
        elif arguments.operation == "immutability":
            _print_result("immutability", check_helper_immutability(arguments.base_sha))
    except BoundaryError as exc:
        parser.exit(1, f"legacy helper boundary failed: {exc}\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
