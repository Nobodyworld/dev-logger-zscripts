from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

from scripts import inventory_legacy_helpers as inventory

ROOT = Path(__file__).resolve().parents[1]
INVENTORY_PATH = ROOT / "docs/operations/legacy_helper_inventory.json"


def _payload() -> dict[str, object]:
    return json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))


def _helper_hashes() -> dict[str, str]:
    return {
        path: hashlib.sha256((ROOT / path).read_bytes()).hexdigest()
        for path in inventory.tracked_helper_paths()
    }


def test_inventory_matches_authoritative_tracked_module_set_exactly_once() -> None:
    payload = _payload()
    module_paths = [record["path"] for record in payload["modules"]]  # type: ignore[index]
    result = subprocess.run(
        ["git", "ls-files", "zscripts/helpers"],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    tracked = sorted(line for line in result.stdout.splitlines() if line.endswith(".py"))

    assert module_paths == sorted(module_paths)
    assert len(module_paths) == len(set(module_paths))
    assert module_paths == tracked


def test_inventory_schema_and_enums_are_valid() -> None:
    payload = _payload()
    assert payload["schema_version"] == 1
    assert payload["risk_levels"] == list(inventory.RISK_LEVELS)
    assert payload["disposition_values"] == list(inventory.DISPOSITIONS)

    required = {
        "path",
        "module",
        "domain",
        "source_lines",
        "third_party_imports",
        "internal_imports",
        "relative_imports",
        "obsolete_top_level_helper_imports",
        "repository_root_imports",
        "repository_root_config_references",
        "top_level_executable_statements",
        "filesystem_read",
        "filesystem_write",
        "filesystem_move_or_delete",
        "subprocess_or_shell",
        "network_or_api",
        "environment_access",
        "credential_access",
        "organization_specific",
        "has_main_guard",
        "tests",
        "direct_tests",
        "importing_tests",
        "indirect_tests",
        "domain_tests",
        "documentation",
        "registry_exposed",
        "wheel_included",
        "static_risk",
        "recommended_disposition",
        "recommendation_rationale",
        "dynamic_import_probe",
        "evidence",
    }
    for record in payload["modules"]:  # type: ignore[index]
        assert required <= record.keys()
        assert record["static_risk"] in inventory.RISK_LEVELS
        assert record["recommended_disposition"] in inventory.DISPOSITIONS


def test_regeneration_is_byte_identical_and_deterministic(tmp_path: Path) -> None:
    first = tmp_path / "first.json"
    second = tmp_path / "second.json"

    inventory.write_inventory(inventory.build_inventory(), first)
    inventory.write_inventory(inventory.build_inventory(), second)

    assert first.read_bytes() == second.read_bytes()


def test_inventory_contains_no_local_absolute_paths() -> None:
    serialized = INVENTORY_PATH.read_text(encoding="utf-8")
    assert not re.search(r"(?<![A-Za-z])[A-Za-z]:[\\/]", serialized)
    assert not re.search(r"/(?:Users|home|tmp)/", serialized)


def test_high_risk_synthetic_calls_are_classified_without_execution() -> None:
    result = inventory.classify_source(
        """
import os
import requests
import subprocess
from pathlib import Path

ORGANIZATION_STORAGE_ROOT = "C:/Users/example/Shared Documents"
Path("input.txt").read_text()
Path("output.txt").write_text("data")
Path("old.txt").unlink()
os.getenv("API_TOKEN")
requests.get("https://example.invalid")
"""
    )

    assert result["filesystem_read"] is True
    assert result["filesystem_write"] is True
    assert result["filesystem_move_or_delete"] is True
    assert result["subprocess_or_shell"] is True
    assert result["network_or_api"] is True
    assert result["environment_access"] is True
    assert result["credential_access"] is True
    assert result["organization_specific"] is True
    assert result["top_level_executable_statements"]


def test_main_guard_is_not_an_import_time_side_effect() -> None:
    result = inventory.classify_source(
        """
def main():
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
"""
    )
    assert result["has_main_guard"] is True
    assert result["top_level_executable_statements"] == []


def test_high_risk_modules_are_ineligible_for_dynamic_import_probe() -> None:
    record = {
        "filesystem_write": True,
        "filesystem_move_or_delete": False,
        "subprocess_or_shell": False,
        "network_or_api": False,
        "credential_access": False,
        "organization_specific": False,
        "top_level_executable_statements": [],
    }
    assert inventory.is_dynamic_probe_eligible(record) is False


def test_generation_does_not_modify_helper_source() -> None:
    before = _helper_hashes()
    inventory.build_inventory()
    after = _helper_hashes()
    assert after == before
