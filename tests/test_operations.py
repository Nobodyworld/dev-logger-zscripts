from __future__ import annotations

from pathlib import Path

import pytest

from zscripts import config, operations


@pytest.fixture()
def sandbox(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    project_root = tmp_path / "project"
    script_dir = project_root / "zscripts"
    project_root.mkdir(parents=True)
    script_dir.mkdir(parents=True)

    log_dir = script_dir / "logs"
    single_dir = log_dir / "logs_single_files"

    patches = {
        "SCRIPT_DIR": script_dir,
        "PROJECT_ROOT": project_root,
        "LOG_DIR": log_dir,
        "BUILD_DIR": log_dir / "build_files",
        "ANALYSIS_DIR": log_dir / "analysis_logs",
        "CONSOLIDATION_DIR": log_dir / "consoli_files",
        "WORK_DIR": log_dir / "logs_files",
        "TREE_LOG_DIR": log_dir / "logs_tree",
        "ALL_LOG_DIR": log_dir / "logs_apps_all",
        "PYTHON_LOG_DIR": log_dir / "logs_apps_pyth",
        "HTML_LOG_DIR": log_dir / "logs_apps_html",
        "CSS_LOG_DIR": log_dir / "logs_apps_css",
        "JS_LOG_DIR": log_dir / "logs_apps_js",
        "BOTH_LOG_DIR": log_dir / "logs_apps_both",
        "SINGLE_LOG_DIR": single_dir,
        "CAPTURE_ALL_PYTHON_LOG": single_dir / "capture_all_pyth.txt",
        "CAPTURE_ALL_HTML_LOG": single_dir / "capture_all_html.txt",
        "CAPTURE_ALL_CSS_LOG": single_dir / "capture_all_css.txt",
        "CAPTURE_ALL_JS_LOG": single_dir / "capture_all_js.txt",
        "CAPTURE_ALL_PYTHON_HTML_LOG": single_dir / "capture_all_python_html.txt",
        "CAPTURE_ALL_LOG": single_dir / "capture_all.txt",
    }

    for name, value in patches.items():
        monkeypatch.setattr(config, name, value, raising=False)

    operations.ensure_log_directories()

    return {
        "project_root": project_root,
        "script_dir": script_dir,
        "log_dir": log_dir,
        "work_dir": config.WORK_DIR,
        "build_dir": config.BUILD_DIR,
        "analysis_dir": config.ANALYSIS_DIR,
        "consolidation_dir": config.CONSOLIDATION_DIR,
    }


def test_generate_app_logs_for_preset_writes_app_log(sandbox: dict[str, Path]) -> None:
    app_dir = sandbox["project_root"] / "demo_app"
    app_dir.mkdir()
    (app_dir / "apps.py").write_text("from django.apps import AppConfig\n", encoding="utf-8")

    output_dir = operations.generate_app_logs_for_preset("python")
    log_file = output_dir / "demo_app.txt"
    assert log_file.exists(), "Expected log file for demo_app to be created."
    contents = log_file.read_text(encoding="utf-8")
    assert "apps.py" in contents


def test_consolidate_file_types_for_preset_creates_file(sandbox: dict[str, Path]) -> None:
    app_dir = sandbox["project_root"] / "demo_app"
    app_dir.mkdir(exist_ok=True)
    (app_dir / "views.py").write_text("def view():\n    return 42\n", encoding="utf-8")

    output_path = operations.consolidate_file_types_for_preset("python")
    assert output_path.exists()
    contents = output_path.read_text(encoding="utf-8")
    assert "# File:" in contents
    assert "return 42" in contents


def test_tree_snapshot_allows_custom_destination(sandbox: dict[str, Path]) -> None:
    destination = sandbox["log_dir"] / "logs_tree" / "custom_tree.txt"
    result = operations.create_tree_snapshot(destination=destination, file_types=[".py"])
    assert result == destination
    assert destination.exists()


def test_convert_and_analyse_workflow(sandbox: dict[str, Path]) -> None:
    work_dir = sandbox["work_dir"]
    work_dir.mkdir(parents=True, exist_ok=True)
    (work_dir / "demo_files.txt").write_text("def foo():\n    return True\n", encoding="utf-8")
    (work_dir / "empty_files.txt").write_text("", encoding="utf-8")

    written_files = operations.convert_work_directory()
    assert len(written_files) == 1
    generated_file = sandbox["build_dir"] / "demo.py"
    assert generated_file.exists()

    analysis_outputs = operations.analyse_build_directory()
    assert len(analysis_outputs) == 1
    analysis_file = sandbox["analysis_dir"] / "demo.txt"
    assert analysis_file.exists()
    assert "foo" in analysis_file.read_text(encoding="utf-8")


def test_consolidate_default_directories_returns_expected_paths(sandbox: dict[str, Path]) -> None:
    sandbox["build_dir"].mkdir(parents=True, exist_ok=True)
    (sandbox["build_dir"] / "module.py").write_text("def bar():\n    pass\n", encoding="utf-8")
    sandbox["analysis_dir"].mkdir(parents=True, exist_ok=True)
    (sandbox["analysis_dir"] / "module.txt").write_text("bar\n", encoding="utf-8")

    results = operations.consolidate_default_directories()
    assert set(results) == {"build", "analysis"}
    for path in results.values():
        assert path.exists()
