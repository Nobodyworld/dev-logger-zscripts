from __future__ import annotations

import ast
import builtins
import copy
import json
import re
import tomllib
import zipfile
from pathlib import Path

import pytest
import yaml

from scripts import check_legacy_helper_boundary as boundary

ROOT = Path(__file__).resolve().parents[1]
SURFACE_PATH = ROOT / "docs/operations/legacy_helper_surface.json"
COMPATIBILITY_PATH = ROOT / "docs/operations/legacy_helper_compatibility.json"


def _json(path: Path) -> dict[str, object]:
    return json.loads(path.read_text(encoding="utf-8"))


def test_surface_baseline_is_complete_sorted_unique_and_exact() -> None:
    payload = _json(SURFACE_PATH)
    modules = payload["modules"]
    assert isinstance(modules, list)
    assert len(modules) == 154
    assert modules == sorted(set(modules))
    assert "zscripts/helpers/registry.py" in modules
    assert modules == boundary.tracked_helper_modules()
    assert boundary.validate_surface_payload(payload) == {
        "tracked_modules": 154,
        "baseline_modules": 154,
    }


def test_surface_regeneration_is_byte_identical() -> None:
    first = boundary._serialize(boundary.build_surface_payload())
    second = boundary._serialize(boundary.build_surface_payload())
    assert first == second
    assert first.encode() == SURFACE_PATH.read_bytes().replace(b"\r\n", b"\n")


@pytest.mark.parametrize("mutation", ["duplicate", "unsorted", "count"])
def test_surface_validator_rejects_malformed_module_lists(mutation: str) -> None:
    payload = copy.deepcopy(_json(SURFACE_PATH))
    modules = payload["modules"]
    assert isinstance(modules, list)
    if mutation == "duplicate":
        modules.append(modules[0])
        payload["module_count"] = len(modules)
    elif mutation == "unsorted":
        modules[0], modules[1] = modules[1], modules[0]
    else:
        payload["module_count"] = 153
    with pytest.raises(boundary.BoundaryError):
        boundary.validate_surface_payload(payload)


def test_compatibility_manifest_schema_and_default_policy() -> None:
    payload = _json(COMPATIBILITY_PATH)
    assert payload["schema_version"] == 1
    assert payload["phase"] == "2A"
    assert payload["compatibility_point_count"] == 7
    default = payload["default_policy"]
    assert default == {
        "applies_to": "all-tracked-helper-modules-except-explicit-compatibility-points",
        "behavioral_support": False,
        "compatibility_status": "legacy-unsupported",
        "phase2b_requires_owner_approval": True,
        "shim_policy": "none-in-phase-2a",
        "wheel_inclusion": "temporarily-wheel-included",
    }
    assert 154 - int(payload["compatibility_point_count"]) == 147
    assert boundary.validate_compatibility_payload(payload) == {
        "compatibility_points": 7,
        "registry_keys": 13,
    }


def test_registry_yaml_keys_resolve_to_exactly_seven_manifest_modules() -> None:
    registry = yaml.safe_load((ROOT / "configs/registry.yaml").read_text(encoding="utf-8"))
    payload = _json(COMPATIBILITY_PATH)
    points = payload["compatibility_points"]
    assert isinstance(points, list)
    assert len({point["module"] for point in points}) == 7
    point_by_key = {key: point for point in points for key in point["registry_keys"]}
    assert set(point_by_key) == set(registry)
    for key, target in registry.items():
        module, callable_name = target.rsplit(":", 1)
        assert point_by_key[key]["module"] == module
        assert callable_name in point_by_key[key]["callables"]


def test_compatibility_owners_and_window_follow_approval() -> None:
    payload = _json(COMPATIBILITY_PATH)
    approved = set(payload["approved_owner_identifiers"])
    points = payload["compatibility_points"]
    assert isinstance(points, list)
    for point in points:
        assert point["owner"] in {"unassigned", *approved}
        assert point["compatibility_status"] == "temporary-compatibility"
        assert point["behavioral_support"] is False
        assert point["shim_policy"] == "none-in-phase-2a"
        assert point["compatibility_window"] == boundary.WINDOW


def test_compatibility_manifest_has_no_fixed_phase2b_date() -> None:
    content = COMPATIBILITY_PATH.read_text(encoding="utf-8")
    assert not re.search(r"\b\d{4}-\d{2}-\d{2}\b", content)
    assert "phase2b_date" not in content
    assert "not_before_date" not in content


def test_maintained_core_has_no_legacy_helper_imports() -> None:
    result = boundary.check_core_boundary()
    assert result["maintained_core_modules"] > 0
    assert result["helper_import_violations"] == 0


@pytest.mark.parametrize(
    "source",
    [
        "import zscripts.helpers",
        "from zscripts.helpers import registry",
        "import helpers",
        "from helpers import utilities",
        "import importlib\nimportlib.import_module('zscripts.helpers.numpy')",
        "__import__('helpers.utilities')",
    ],
)
def test_boundary_rejects_static_and_literal_dynamic_helper_imports(source: str) -> None:
    ast.parse(source)
    assert boundary.find_core_import_violations(source)


def test_torch_contract_remains_at_approved_2_9_0() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    helpers_ml = project["project"]["optional-dependencies"]["helpers-ml"]
    assert "torch>=2.9.0" in helpers_ml
    requirement_lines = {
        line.strip()
        for line in (ROOT / "configs/requirements/ml.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }
    assert "torch==2.9.0" in requirement_lines
    assert not any(line.startswith("torch==") and line != "torch==2.9.0" for line in requirement_lines)


def test_wheel_member_check_requires_all_surface_modules(tmp_path: Path) -> None:
    wheel = tmp_path / "phase2a-test.whl"
    with zipfile.ZipFile(wheel, "w") as archive:
        for module in boundary.tracked_helper_modules():
            archive.writestr(module, b"")
    assert boundary.check_wheel(wheel) == {
        "helper_modules_included": 154,
        "helper_modules_missing": 0,
    }


def test_boundary_checks_never_import_helper_source(monkeypatch: pytest.MonkeyPatch) -> None:
    original_import = builtins.__import__

    def guarded_import(name: str, *args: object, **kwargs: object) -> object:
        if name == "helpers" or name.startswith("helpers.") or name.startswith("zscripts.helpers"):
            raise AssertionError(f"boundary check imported helper source: {name}")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    boundary.check_surface()
    boundary.check_compatibility()
    boundary.check_core_boundary()


def test_phase2a_keeps_helper_package_discovery_and_has_no_exclusion() -> None:
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    package_find = project["tool"]["setuptools"]["packages"]["find"]
    assert "zscripts*" in package_find["include"]
    assert not any("helper" in value.lower() for value in package_find["exclude"])
    payload = _json(COMPATIBILITY_PATH)
    assert all(point["shim_policy"] == "none-in-phase-2a" for point in payload["compatibility_points"])


def test_canonical_gate_and_precommit_enforce_phase2a_contracts() -> None:
    from scripts import quality_gate

    expected = ("helper-surface", "helper-boundary", "helper-compatibility")
    assert quality_gate.HELPER_CONTRACT_OPERATIONS == expected
    assert all(operation in quality_gate.CHECK_OPERATIONS for operation in expected)
    assert all(operation in quality_gate.QUALITY_OPERATIONS for operation in expected)
    pre_commit = yaml.safe_load((ROOT / ".pre-commit-config.yaml").read_text(encoding="utf-8"))
    local = next(repo for repo in pre_commit["repos"] if repo["repo"] == "local")
    hook_ids = {hook["id"] for hook in local["hooks"]}
    assert set(expected) <= hook_ids
