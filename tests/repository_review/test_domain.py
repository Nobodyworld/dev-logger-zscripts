from __future__ import annotations

from dataclasses import replace

import pytest

from zscripts.domain.repository_review import (
    ANALYZER_VERSION,
    RULE_SET_VERSION,
    SCHEMA_VERSION,
    AnalysisEvidence,
    AnalysisState,
    DiagnosticRecord,
    FileRecord,
    ImportRecord,
    ModuleRecord,
    RepositoryRecord,
    ScanLimits,
    SnapshotRecord,
    SymbolRecord,
    canonical_json_bytes,
    stable_digest,
)


def test_stable_digest_and_canonical_json_ignore_mapping_order() -> None:
    first = stable_digest("test", {"b": 2, "a": 1})
    second = stable_digest("test", {"a": 1, "b": 2})

    assert first == second
    assert canonical_json_bytes({"b": 2, "a": 1}) == b'{"a":1,"b":2}\n'
    assert first != stable_digest("other", {"a": 1, "b": 2})


def test_scan_limits_reject_non_positive_values() -> None:
    with pytest.raises(ValueError, match="max_files"):
        ScanLimits(max_files=0)


def test_canonical_evidence_is_sorted_and_redacts_local_paths() -> None:
    evidence = _evidence()
    payload = evidence.canonical_payload()
    serialized = evidence.canonical_bytes()

    assert payload["files"][0]["relative_path"] == "a.py"
    assert payload["files"][1]["relative_path"] == "b.py"
    assert b"C:\\\\Users\\\\private" not in serialized
    assert b"started_at" not in serialized
    assert b"duration_ms" not in serialized
    assert serialized.endswith(b"\n")


def test_timing_changes_do_not_change_core_evidence() -> None:
    evidence = _evidence()
    changed = replace(
        evidence,
        snapshot=replace(
            evidence.snapshot,
            started_at="2099-01-01T00:00:00.000Z",
            completed_at="2099-01-01T00:00:01.000Z",
            duration_ms=999,
        ),
    )

    assert evidence.canonical_bytes() == changed.canonical_bytes()


def _evidence() -> AnalysisEvidence:
    repository = RepositoryRecord(
        repository_id="repository-id",
        display_name="fixture",
        canonical_path=r"C:\Users\private\fixture",
        git_root=r"C:\Users\private\fixture",
        branch="main",
        git_sha="abc",
        dirty=False,
        staged=False,
        untracked=False,
        configuration_digest="config",
        source_roots=(".",),
        test_roots=("tests",),
    )
    files = (
        FileRecord("file-b", "b.py", "hash-b", "python", 2, True, None, "parsed"),
        FileRecord("file-a", "a.py", "hash-a", "python", 1, True, None, "parsed"),
    )
    imports = (ImportRecord("pathlib", "Path", "FilePath", 0),)
    modules = (
        ModuleRecord("module-b", "b", "", "file-b", "b.py", (), imports),
        ModuleRecord("module-a", "a", "", "file-a", "a.py", ("public",), ()),
    )
    symbols = (
        SymbolRecord(
            symbol_id="symbol-a",
            language="python",
            kind="function",
            qualified_name="a.public",
            display_name="public",
            module_name="a",
            file_id="file-a",
            relative_path="a.py",
            start_line=1,
            start_column=0,
            end_line=1,
            end_column=10,
            parent_symbol_id=None,
            visibility="public",
            signature="def public()",
            annotations=(),
            decorators=(),
            docstring_present=False,
            async_flag=False,
            content_fingerprint="fingerprint",
        ),
    )
    diagnostics = (
        DiagnosticRecord(
            diagnostic_id="diagnostic",
            code="TEST",
            severity="warning",
            message="Safe message.",
            relative_path="b.py",
            line=2,
            column=1,
            category="parse_error",
        ),
    )
    snapshot = SnapshotRecord(
        snapshot_id="snapshot-id",
        repository_id=repository.repository_id,
        analyzer_version=ANALYZER_VERSION,
        schema_version=SCHEMA_VERSION,
        rule_set_version=RULE_SET_VERSION,
        state=AnalysisState.COMPLETED,
        source_fingerprint="source",
        file_count=2,
        included_file_count=2,
        module_count=2,
        symbol_count=1,
        started_at="2026-01-01T00:00:00.000Z",
        completed_at="2026-01-01T00:00:01.000Z",
        duration_ms=1,
        truncated=False,
        parse_gap_count=1,
    )
    return AnalysisEvidence(
        repository=repository,
        snapshot=snapshot,
        files=files,
        modules=modules,
        symbols=symbols,
        diagnostics=diagnostics,
    )
