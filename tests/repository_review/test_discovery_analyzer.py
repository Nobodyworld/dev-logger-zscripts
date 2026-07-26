from __future__ import annotations

import shutil
from pathlib import Path

from zscripts.domain.repository_review import ScanLimits
from zscripts.infrastructure.python_analyzer import PythonAnalyzer
from zscripts.infrastructure.repository_discovery import RepositoryDiscovery

FIXTURES = Path(__file__).parents[1] / "fixtures" / "repository_review"


def test_python_analyzer_extracts_packages_imports_and_nested_symbols(
    tmp_path: Path,
) -> None:
    repository = tmp_path / "ordinary"
    shutil.copytree(FIXTURES / "ordinary", repository)

    discovery = RepositoryDiscovery().discover(repository)
    result = PythonAnalyzer().analyze(discovery.files)

    modules = {item.module_name: item for item in result.modules}
    symbols = {item.qualified_name: item for item in result.symbols}
    assert set(modules) == {"pkg", "pkg.module"}
    assert modules["pkg"].public_exports == ("Example", "top_level")
    assert any(
        item.module == "pathlib"
        and item.imported_name == "Path"
        and item.alias == "FilePath"
        and item.line == 7
        and item.column == 0
        for item in modules["pkg.module"].imports
    )
    assert any(
        item.module == "module" and item.imported_name == "Example" and item.level == 1
        for item in modules["pkg"].imports
    )

    example = symbols["pkg.module.Example"]
    method = symbols["pkg.module.Example.method"]
    nested_class = symbols["pkg.module.Example.Nested"]
    nested_function = symbols["pkg.module.Example.method.nested_function"]
    assert example.kind == "class"
    assert example.bases == ("BaseExample", "ProtocolLike")
    assert example.decorators == ("decorator('<string>')",)
    assert example.docstring_present is True
    assert method.kind == "method"
    assert method.async_flag is True
    assert "value: int, /" in method.signature
    assert "*items: object" in method.signature
    assert "option: str = '<string>'" in method.signature
    assert "enabled: bool = True" in method.signature
    assert "**metadata: str" in method.signature
    assert method.parent_symbol_id == example.symbol_id
    assert nested_class.parent_symbol_id == example.symbol_id
    assert nested_function.parent_symbol_id == method.symbol_id
    assert all(item.start_line <= item.end_line for item in result.symbols)
    candidates = {(item.source_symbol_id, item.textual_name) for item in result.type_references}
    assert (method.symbol_id, "cabc.Sequence") in candidates
    assert (nested_function.symbol_id, "FilePath") in candidates
    assert (example.symbol_id, "BaseExample") in candidates


def test_malformed_python_isolated_to_diagnostic(tmp_path: Path) -> None:
    repository = tmp_path / "malformed"
    shutil.copytree(FIXTURES / "malicious", repository)

    result = PythonAnalyzer().analyze(RepositoryDiscovery().discover(repository).files)

    files = {item.relative_path: item for item in result.files}
    assert files["malformed.py"].parse_status == "syntax_error"
    assert files["effects.py"].parse_status == "parsed"
    assert any(
        item.code == "PY_PARSE_ERROR" and item.relative_path == "malformed.py" for item in result.diagnostics
    )
    assert any(item.qualified_name == "effects.public_function" for item in result.symbols)


def test_discovery_records_safe_exclusions_and_resource_limits(tmp_path: Path) -> None:
    repository = tmp_path / "bounded"
    repository.mkdir()
    (repository / ".gitignore").write_text("ignored.py\n", encoding="utf-8")
    (repository / ".env").write_text(
        "TOKEN=do-not-export\n",  # pragma: allowlist secret
        encoding="utf-8",
    )
    (repository / "credentials-prod.py").write_text(
        "SECRET = 'hidden'\n",  # pragma: allowlist secret
        encoding="utf-8",
    )
    (repository / "ignored.py").write_text("def ignored(): ...\n", encoding="utf-8")
    (repository / "binary.py").write_bytes(b"\x00\x01")
    (repository / "large.py").write_text("x = '" + ("a" * 200) + "'\n", encoding="utf-8")
    (repository / "first.py").write_text("def first(): ...\n", encoding="utf-8")
    (repository / "second.py").write_text("def second(): ...\n", encoding="utf-8")
    generated = repository / "node_modules"
    generated.mkdir()
    (generated / "should_not_walk.py").write_text("raise RuntimeError\n", encoding="utf-8")

    result = RepositoryDiscovery(
        limits=ScanLimits(max_files=1, max_file_size_bytes=100, max_total_bytes=100),
    ).discover(repository)

    files = {item.record.relative_path: item.record for item in result.files}
    sensitive = [item for item in files.values() if item.exclusion_reason == "sensitive"]
    assert len(sensitive) == 2
    assert all(item.relative_path.startswith("[sensitive-file-") for item in sensitive)
    assert ".env" not in result.source_fingerprint
    assert "credentials-prod.py" not in result.source_fingerprint
    assert files["ignored.py"].exclusion_reason == "gitignored"
    assert files["binary.py"].exclusion_reason == "binary"
    assert files["large.py"].exclusion_reason == "file_size_limit"
    assert sum(item.included for item in files.values()) == 1
    assert any(item.exclusion_reason == "file_count_limit" for item in files.values())
    assert result.truncated is True
    assert any(
        item.code == "DISCOVERY_DIRECTORY_EXCLUDED" and item.relative_path == "node_modules"
        for item in result.diagnostics
    )


def test_discovery_excludes_symlinks_without_following_them(tmp_path: Path) -> None:
    repository = tmp_path / "symlinked"
    repository.mkdir()
    outside = tmp_path / "outside.py"
    outside.write_text("def outside(): ...\n", encoding="utf-8")
    link = repository / "linked.py"
    try:
        link.symlink_to(outside)
    except OSError:
        return

    result = RepositoryDiscovery().discover(repository)

    record = next(item.record for item in result.files if item.record.relative_path == "linked.py")
    assert record.included is False
    assert record.exclusion_reason == "symlink_escape"
