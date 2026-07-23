from __future__ import annotations

import hashlib
import json
import re
import tomllib
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CONSUMERS_PATH = ROOT / "docs/operations/legacy_helper_consumers.json"
COMPATIBILITY_PATH = ROOT / "docs/operations/legacy_helper_compatibility.json"
SURFACE_PATH = ROOT / "docs/operations/legacy_helper_surface.json"
NOTICE_PATH = ROOT / "docs/operations/LEGACY_HELPER_DEPRECATION_NOTICE.md"

EXPECTED_SHA = "d3a4eb92ed7f4f1590e7f4ea3ae079edb15a7d35"
EXPECTED_MERGE_TIMESTAMP = "2026-07-23T00:40:54Z"
EXPECTED_THRESHOLD = "2026-10-21T00:40:54Z"
EXPECTED_EVIDENCE_CATEGORIES = {
    "direct_import",
    "direct_invocation",
    "documentation_only_reference",
    "no_current_reference_found",
    "package_reexport",
    "registry_reference",
    "test_only_reference",
}
OWNER_RECOMMENDATIONS = {
    "owner needed before migration",
    "owner needed before shim support",
    "explicit unowned retirement risk may be accepted",
    "no responsible owner identified",
}
EVIDENCE_FIELDS = (
    "current_internal_consumers",
    "self_invocations",
    "historical_consumers",
    "package_reexports",
    "registry_evidence",
    "tests",
    "documentation",
    "automation",
)


def _json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(payload, dict)
    return payload


def _registry() -> dict[str, str]:
    entries: dict[str, str] = {}
    for line in (ROOT / "configs/registry.yaml").read_text(encoding="utf-8").splitlines():
        if line.strip() and not line.lstrip().startswith("#"):
            key, target = line.split(": ", 1)
            entries[key] = target
    return entries


def _helper_source_digest(surface: dict[str, Any]) -> str:
    digest = hashlib.sha256()
    for relative_path in surface["modules"]:
        digest.update(relative_path.encode("utf-8"))
        digest.update(b"\0")
        digest.update((ROOT / relative_path).read_bytes().replace(b"\r\n", b"\n"))
        digest.update(b"\0")
    return digest.hexdigest()


def _git_blob_sha1(path: Path) -> str:
    content = path.read_bytes().replace(b"\r\n", b"\n")
    return hashlib.sha1(f"blob {len(content)}\0".encode() + content).hexdigest()  # noqa: S324


def test_consumer_manifest_is_canonical_and_has_exact_review_surface() -> None:
    content = CONSUMERS_PATH.read_text(encoding="utf-8")
    payload = _json(CONSUMERS_PATH)
    assert content == json.dumps(payload, indent=2, sort_keys=True) + "\n"
    assert payload["schema_version"] == 1
    assert payload["phase"] == "consumer-review"
    assert payload["phase2a_merge_sha"] == EXPECTED_SHA

    points = payload["compatibility_points"]
    compatibility = _json(COMPATIBILITY_PATH)["compatibility_points"]
    assert len(points) == 7
    assert [point["module"] for point in points] == sorted(point["module"] for point in points)
    assert [point["module"] for point in points] == [point["module"] for point in compatibility]
    assert sum(len(point["registry_keys"]) for point in points) == 13
    assert {key for point in points for key in point["registry_keys"]} == set(_registry())
    for point in points:
        assert point["registry_keys"] == sorted(point["registry_keys"])
        assert point["callables"] == sorted(point["callables"])
        assert point["dependencies"] == sorted(point["dependencies"])
        assert point["consumer_review_status"] == "complete"


def test_consumer_evidence_categories_owners_and_public_results_are_bounded() -> None:
    payload = _json(CONSUMERS_PATH)
    assert set(payload["evidence_categories"]) == EXPECTED_EVIDENCE_CATEGORIES
    compatibility = _json(COMPATIBILITY_PATH)
    approved = set(compatibility["approved_owner_identifiers"])
    points = payload["compatibility_points"]
    for point in points:
        assert point["owner"] in {"unassigned", *approved}
        assert point["owner"] == "unassigned"
        assert point["owner_recommendation"] in OWNER_RECOMMENDATIONS
        assert point["public_external_consumers"] == []
        for field in EVIDENCE_FIELDS:
            for evidence in point[field]:
                assert evidence["category"] in EXPECTED_EVIDENCE_CATEGORIES

    public_queries = payload["public_search_evidence"]
    assert len(public_queries) == 27
    assert len({entry["query"] for entry in public_queries}) == 27
    assert sum(entry["query_kind"] == "full_module_path" for entry in public_queries) == 7
    assert sum(entry["query_kind"] == "registry_key" for entry in public_queries) == 13
    assert sum(entry["query_kind"] == "distinctive_import" for entry in public_queries) == 7
    assert len(payload["public_search_non_consumers"]) == 3
    assert {entry["repository"] for entry in payload["public_search_non_consumers"]} == {"duriantaco/skylos"}


def test_consumer_manifest_has_no_local_paths_or_unapproved_timestamps() -> None:
    content = CONSUMERS_PATH.read_text(encoding="utf-8")
    assert not re.search(r"(?<![A-Za-z])[A-Za-z]:[\\/]", content)
    assert not re.search(r"/(?:Users|home|tmp)/", content)
    assert set(re.findall(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", content)) == {
        EXPECTED_MERGE_TIMESTAMP,
        EXPECTED_THRESHOLD,
    }


def test_phase2b_is_unauthorized_and_window_evidence_is_exact() -> None:
    payload = _json(CONSUMERS_PATH)
    assert payload["phase2b_authorized"] is False
    assert payload["phase2a_merge_timestamp"] == EXPECTED_MERGE_TIMESTAMP
    assert payload["time_threshold"] == EXPECTED_THRESHOLD
    assert payload["deprecation_cycle"] == {
        "completed": False,
        "eligibility_rule": "whichever-is-later",
        "minimum_public_beta_cycles": 1,
        "status": "started",
    }
    content = CONSUMERS_PATH.read_text(encoding="utf-8").lower()
    assert '"phase2b_authorized": true' not in content


def test_deprecation_notice_starts_but_does_not_complete_cycle() -> None:
    notice = NOTICE_PATH.read_text(encoding="utf-8")
    lowered = notice.lower()
    assert "status: notice started; deprecation cycle **not complete**." in lowered
    assert EXPECTED_MERGE_TIMESTAMP in notice
    assert EXPECTED_THRESHOLD in notice
    assert "all **154 tracked helper python modules remain included in the wheel today**" in lowered
    assert "the cycle starts with this notice. it is not complete in this change." in lowered
    assert re.search(r"phase 2b remains separately\s+owner-gated through issue #62", lowered)
    assert "cycle is complete" not in lowered


def test_notice_is_linked_from_all_required_documents() -> None:
    required = (
        ROOT / "README.md",
        ROOT / "docs/INDEX.md",
        ROOT / "docs/helpers/LEGACY_OPTIONAL_HELPERS.md",
        ROOT / "docs/operations/LEGACY_HELPER_COMPATIBILITY.md",
    )
    for path in required:
        assert "LEGACY_HELPER_DEPRECATION_NOTICE.md" in path.read_text(encoding="utf-8")


def test_helper_source_registry_and_package_discovery_remain_frozen() -> None:
    payload = _json(CONSUMERS_PATH)
    scope = payload["scope_contract"]
    surface = _json(SURFACE_PATH)
    assert surface["module_count"] == 154
    assert len(surface["modules"]) == 154
    assert _helper_source_digest(surface) == scope["helper_source_sha256"]
    assert _git_blob_sha1(ROOT / "configs/registry.yaml") == scope["registry_blob_sha1"]

    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    package_find = project["tool"]["setuptools"]["packages"]["find"]
    assert sorted(package_find["include"]) == scope["package_discovery_include"]
    assert sorted(package_find["exclude"]) == scope["package_discovery_exclude"]
    assert "zscripts*" in package_find["include"]
    assert not any("helper" in value.lower() for value in package_find["exclude"])
    assert scope["wheel_inclusion"] == "all-154-temporarily-wheel-included"


def test_torch_contract_remains_exactly_2_9_0() -> None:
    payload = _json(CONSUMERS_PATH)
    scope = payload["scope_contract"]
    project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    helpers_ml = project["project"]["optional-dependencies"]["helpers-ml"]
    requirement_lines = {
        line.strip()
        for line in (ROOT / "configs/requirements/ml.txt").read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }
    assert scope["torch_package_lower_bound"] == "torch>=2.9.0"
    assert scope["torch_exact_pin"] == "torch==2.9.0"
    assert "torch>=2.9.0" in helpers_ml
    assert "torch==2.9.0" in requirement_lines
    assert not any(line.startswith("torch==") and line != "torch==2.9.0" for line in requirement_lines)
