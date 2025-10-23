"""Unit tests covering the file system utility helpers exposed by :mod:`zscripts`."""

from __future__ import annotations

import random
import string
from collections.abc import Iterator
from pathlib import Path
from typing import TextIO

import pytest

from zscripts.utils import (
    IgnoreMatcher,
    InvalidIgnorePatternError,
    collect_app_logs,
    consolidate_files,
    create_filtered_tree,
    expand_skip_dirs,
    file_matches_any_pattern,
    format_bytes,
    group_source_files_by_app,
    iter_filtered_tree_lines,
    list_matching_source_files,
    load_gitignore_patterns,
)

# TODO - (coverage) Expand utility tests to cover error handling branches for robustness.


@pytest.fixture()
def sample_project_path(tmp_path: Path) -> Path:
    """Create a temporary project tree with backend and frontend sources."""
    project = tmp_path / "sample"
    project.mkdir()

    backend = project / "backend"
    backend.mkdir()
    (backend / "service.py").write_text("# Backend service\n\ndef hello():\n    return 'world'\n")

    frontend = project / "frontend"
    frontend.mkdir()
    frontend_files = {
        "App.js": "// Vanilla JS app\nconsole.log('hello');\n",
        "App.jsx": "// Frontend app\nconst App = () => <div>Hello</div>;\n",
        "App.mjs": "export const greet = () => 'hello';\n",
        "App.cjs": "module.exports = { greet() { return 'hello'; } };\n",
        "App.ts": "export const add = (a: number, b: number): number => a + b;\n",
        "App.tsx": "// Frontend TSX app\nexport const App = (): JSX.Element => <div>Hello</div>;\n",
        "App.mts": "export const value: number = 1;\n",
        "App.cts": "export const config = { mode: 'cts' };\n",
    }

    for filename, content in frontend_files.items():
        (frontend / filename).write_text(content, encoding="utf-8")

    return project


def test_ignore_matcher_matches_glob_patterns() -> None:
    """Ignore matcher should respect straightforward glob pattern behaviour."""
    matcher = IgnoreMatcher(["*.pyc", "__pycache__/"])
    assert matcher.matches(Path("__pycache__/module.pyc"))
    assert not matcher.matches(Path("module.py"))


def test_ignore_matcher_supports_negation() -> None:
    """Ignore matcher should support negated patterns for allowlisting paths."""
    matcher = IgnoreMatcher(["backend/*", "!backend/service.py"])
    assert not matcher.matches(Path("backend/service.py"))
    assert matcher.matches(Path("backend/other.py"))


def test_ignore_matcher_raises_on_invalid_pattern(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ignore matcher should raise a helpful error for invalid regex patterns."""
    import re

    original_compile = re.compile

    def failing_compile(pattern: str, flags: int = 0):  # type: ignore[override]
        if "sentinel" in pattern:
            raise re.error("unterminated character set")
        return original_compile(pattern, flags)

    monkeypatch.setattr("zscripts.utils.re.compile", failing_compile)

    with pytest.raises(InvalidIgnorePatternError):
        IgnoreMatcher(["sentinel"])


def test_ignore_matcher_case_normalisation() -> None:
    """Ignore matcher should treat paths case-insensitively when configured."""
    matcher = IgnoreMatcher(["frontend/app.js"], case_sensitive=False)
    assert matcher.matches(Path("frontend/App.js"))


def test_collect_app_logs_ignores_symlinks(
    sample_project_path: Path, tmp_path: Path
) -> None:
    """Log collection should ignore symlinked files that escape the project root."""
    outside_file = tmp_path / "outside.py"
    outside_file.write_text("print('outside')\n", encoding="utf-8")
    (sample_project_path / "backend" / "escape.py").symlink_to(outside_file)

    log_dir = tmp_path / "logs"
    stats = collect_app_logs(sample_project_path, log_dir, {".py"}, [])

    backend_log = log_dir / "backend.txt"
    content = backend_log.read_text(encoding="utf-8")
    assert "escape.py" not in content
    assert "service.py" in content
    assert stats.files_skipped == 0
    assert stats.files_written >= 1


def test_collect_app_logs_collects_javascript_family(
    sample_project_path: Path, tmp_path: Path
) -> None:
    """Log collection should capture every supported JavaScript-family file."""
    log_dir = tmp_path / "logs"
    stats = collect_app_logs(
        sample_project_path,
        log_dir,
        {".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts"},
        [],
    )

    frontend_log = log_dir / "frontend.txt"
    content = frontend_log.read_text(encoding="utf-8")
    assert "App.js" in content
    assert "App.jsx" in content
    assert "App.mjs" in content
    assert "App.cjs" in content
    assert "App.ts" in content
    assert "App.tsx" in content
    assert "App.mts" in content
    assert "App.cts" in content
    assert stats.files_written == 8
    assert stats.files_skipped == 0
    assert stats.bytes_written > 0


def test_consolidate_files_handles_uppercase_extensions(
    sample_project_path: Path, tmp_path: Path
) -> None:
    """File consolidation should handle uppercase extensions transparently."""
    uppercase_file = sample_project_path / "backend" / "UPPER.PY"
    uppercase_file.write_text("print('upper')\n", encoding="utf-8")

    output_path = tmp_path / "consolidated.txt"
    stats = consolidate_files(sample_project_path, output_path, {".py"}, [])

    content = output_path.read_text(encoding="utf-8")
    assert "service.py" in content
    assert "UPPER.PY" in content
    assert stats.files_written >= 2
    assert stats.files_skipped == 0
    assert stats.bytes_written > 0


def test_create_filtered_tree_without_contents(
    sample_project_path: Path, tmp_path: Path
) -> None:
    """Filtered tree should omit file contents when requested."""
    output_path = tmp_path / "tree.txt"
    stats = create_filtered_tree(sample_project_path, output_path, [], include_content=False)

    content = output_path.read_text(encoding="utf-8")
    assert "backend" in content
    assert "frontend" in content
    assert "Backend service" not in content
    assert stats.lines_emitted > 0
    assert stats.bytes_written > 0


def test_iter_filtered_tree_lines_emits_truncation_marker(tmp_path: Path) -> None:
    """Tree iterator should append a truncation marker when byte limits are hit."""
    project_root = tmp_path / "proj"
    project_root.mkdir()
    target = project_root / "data.txt"
    target.write_text("abcdefghijklmnopqrstuvwxyz", encoding="utf-8")

    lines = list(
        iter_filtered_tree_lines(
            project_root,
            [],
            include_content=True,
            max_bytes=5,
        )
    )

    assert any("… (content truncated" in line for line in lines)
    summary_line = next(line for line in lines if line.startswith("Summary:"))
    assert "1 file" in summary_line
    assert any(line.startswith("Note:") for line in lines)


def test_iter_filtered_tree_lines_reports_summary_without_contents(
    tmp_path: Path,
) -> None:
    """Tree iterator should summarise directories even without file contents."""
    project_root = tmp_path / "proj"
    project_root.mkdir()
    (project_root / "dir").mkdir()
    (project_root / "dir" / "alpha.txt").write_text("alpha", encoding="utf-8")

    lines = list(
        iter_filtered_tree_lines(
            project_root,
            [],
            include_content=False,
        )
    )

    summary_line = next(line for line in lines if line.startswith("Summary:"))
    assert "1 directory" in summary_line
    assert "1 file" in summary_line
    assert format_bytes(5) in summary_line


def test_load_gitignore_patterns_includes_skip_dirs(
    sample_project_path: Path,
) -> None:
    """Gitignore loader should include patterns sourced from project files."""
    gitignore = sample_project_path / ".gitignore"
    gitignore.write_text("node_modules\n", encoding="utf-8")

    patterns = load_gitignore_patterns(sample_project_path)
    assert "node_modules" in patterns


def test_load_gitignore_patterns_preserves_user_order(tmp_path: Path) -> None:
    """Gitignore loader should retain user-defined pattern ordering."""
    project_root = tmp_path / "repo"
    project_root.mkdir()

    patterns = load_gitignore_patterns(
        project_root,
        skip_dirs=["alpha"],
        user_ignore_patterns=["first", "second", "third"],
    )

    first_index = patterns.index("first")
    second_index = patterns.index("second")
    third_index = patterns.index("third")
    assert first_index < second_index < third_index


def test_collect_app_logs_closes_handles_on_read_error(
    sample_project_path: Path,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Log collection should close all file handles even after read errors."""
    output_dir = tmp_path / "logs"
    opened_handles: list[TextIO] = []

    original_open = Path.open

    def tracking_open(self: Path, *args, **kwargs):  # type: ignore[override]
        handle = original_open(self, *args, **kwargs)
        mode = kwargs.get("mode")
        if args:
            mode = args[0]
        if isinstance(mode, str) and any(flag in mode for flag in ("w", "a", "x")):
            opened_handles.append(handle)
        return handle

    monkeypatch.setattr(Path, "open", tracking_open)

    original_read_text = Path.read_text

    def flaky_read_text(self: Path, *args, **kwargs):  # type: ignore[override]
        if self.name == "service.py":
            raise OSError("simulated failure")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", flaky_read_text)

    stats = collect_app_logs(sample_project_path, output_dir, {".py"}, [])

    assert stats.files_skipped == 1
    assert opened_handles, "expected at least one log handle to be opened"
    assert all(handle.closed for handle in opened_handles)


def test_load_gitignore_patterns_includes_info_exclude(tmp_path: Path) -> None:
    """Gitignore loader should respect repository-level info exclude entries."""
    project_root = tmp_path / "project"
    (project_root / ".git" / "info").mkdir(parents=True)
    (project_root / ".git" / "info" / "exclude").write_text("cache/\n", encoding="utf-8")

    patterns = load_gitignore_patterns(project_root)
    assert "cache/" in patterns


def test_load_gitignore_patterns_respects_overrides(tmp_path: Path) -> None:
    """Gitignore loader should merge skip dirs and user ignore overrides."""
    custom_root = tmp_path / "project"
    custom_root.mkdir()

    patterns = load_gitignore_patterns(
        custom_root,
        skip_dirs=["custom"],
        user_ignore_patterns=["build-artifacts", "  redundant  "],
    )

    assert "custom" in patterns
    assert "*/custom" in patterns
    assert "build-artifacts" in patterns
    assert "redundant" in patterns


def test_load_gitignore_patterns_rejects_invalid_user_entries(
    tmp_path: Path,
) -> None:
    """Gitignore loader should enforce string-only user ignore patterns."""
    project_root = tmp_path / "root"
    project_root.mkdir()

    with pytest.raises(TypeError):
        load_gitignore_patterns(project_root, user_ignore_patterns=["ok", 2])  # type: ignore[list-item]


def test_load_gitignore_patterns_rejects_control_characters(tmp_path: Path) -> None:
    """Gitignore loader should reject patterns containing control characters."""
    project_root = tmp_path / "root"
    project_root.mkdir()

    with pytest.raises(ValueError):
        load_gitignore_patterns(project_root, user_ignore_patterns=["bad\npattern"])


def test_load_gitignore_patterns_requires_directory(tmp_path: Path) -> None:
    """Gitignore loader should require the root path to be a directory."""
    file_root = tmp_path / "file.txt"
    file_root.write_text("content", encoding="utf-8")

    with pytest.raises(NotADirectoryError):
        load_gitignore_patterns(file_root)


def test_load_gitignore_patterns_requires_existing_path(tmp_path: Path) -> None:
    """Gitignore loader should require the target path to exist."""
    missing_root = tmp_path / "missing"

    with pytest.raises(FileNotFoundError):
        load_gitignore_patterns(missing_root)


def test_expand_skip_dirs_generates_variants_fuzz() -> None:
    """Fuzz-test that skip dir expansion generates expected pattern variants."""
    rng = random.Random(2)
    alphabet = string.ascii_lowercase
    for _ in range(50):
        skip_dirs: list[str] = []
        for _ in range(rng.randint(0, 5)):
            length = rng.randint(1, 4)
            token = "".join(rng.choice(alphabet) for _ in range(length))
            if rng.random() < 0.5:
                token = f"/{token}/"
            skip_dirs.append(token)
        patterns = expand_skip_dirs(skip_dirs)

        for skip_dir in skip_dirs:
            cleaned = skip_dir.strip("/")
            if not cleaned:
                continue
            assert cleaned in patterns
            assert f"{cleaned}/" in patterns
            assert f"*/{cleaned}" in patterns


def test_expand_skip_dirs_preserves_variant_order() -> None:
    """Skip dir expansion should preserve input ordering across variants."""
    patterns = expand_skip_dirs(["beta", "alpha"])

    assert patterns.index("beta") < patterns.index("alpha")
    assert patterns.index("beta/") < patterns.index("alpha/")


def test_expand_skip_dirs_requires_string_entries() -> None:
    """Skip dir expansion should raise when encountering non-string entries."""
    class CustomIterable:
        def __iter__(self) -> Iterator[object]:
            yield "valid"
            yield 1

    with pytest.raises(TypeError):
        expand_skip_dirs(CustomIterable())


def test_group_source_files_by_app_returns_sorted(
    sample_project_path: Path,
) -> None:
    """Grouping helper should return deterministic ordering by application."""
    mapping = group_source_files_by_app(
        sample_project_path,
        {".py", ".js", ".jsx", ".mjs", ".cjs", ".ts", ".tsx", ".mts", ".cts"},
        [],
    )

    assert set(mapping) == {"backend", "frontend"}
    assert mapping["backend"] == [Path("backend/service.py")]
    assert mapping["frontend"] == [
        Path("frontend/App.cjs"),
        Path("frontend/App.cts"),
        Path("frontend/App.js"),
        Path("frontend/App.jsx"),
        Path("frontend/App.mjs"),
        Path("frontend/App.mts"),
        Path("frontend/App.ts"),
        Path("frontend/App.tsx"),
    ]


def test_list_matching_source_files_produces_relative_paths(
    sample_project_path: Path,
) -> None:
    """Source file listing should return sorted, relative paths."""
    extra = sample_project_path / "backend" / "extra.PY"
    extra.write_text("print('extra')\n", encoding="utf-8")

    files = list_matching_source_files(sample_project_path, {".py"}, [])

    assert files == sorted(files, key=lambda path: path.as_posix())
    assert Path("backend/extra.PY") in files


def test_file_matches_any_pattern_accepts_strings() -> None:
    """Pattern helper should accept string paths without requiring Path objects."""
    assert file_matches_any_pattern("backend/service.py", ["backend/*.py"])


def test_iter_filtered_tree_lines_supports_dry_run_preview(
    sample_project_path: Path,
) -> None:
    """Tree iterator should yield a preview when used in dry-run contexts."""
    lines = list(
        iter_filtered_tree_lines(
            sample_project_path,
            [],
            include_content=False,
        )
    )

    assert lines[0] == sample_project_path.resolve().as_posix()
    assert any("backend" in line for line in lines)


def test_iter_filtered_tree_lines_rejects_negative_limits(
    sample_project_path: Path,
) -> None:
    """Tree iterator should reject negative byte limits with a ValueError."""
    with pytest.raises(ValueError):
        list(
            iter_filtered_tree_lines(
                sample_project_path,
                [],
                include_content=False,
                max_bytes=-1,
            )
        )
