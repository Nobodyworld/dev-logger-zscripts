from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path

import pytest

from zscripts import config
from zscripts.config import Config, get_config, get_file_group_resolver, load_config, resolve_paths


def test_config_loading_returns_expected_types() -> None:
    config = get_config()
    assert isinstance(config, Config)
    assert isinstance(config.skip, tuple)
    assert isinstance(config.file_types, Mapping)
    assert isinstance(config.user_ignore_patterns, frozenset)
    assert isinstance(config.directories, Mapping)
    assert isinstance(config.collection_logs, Mapping)
    assert isinstance(config.single_targets, Mapping)


def test_load_config_merges_with_defaults(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text(
        '{"skip": ["custom"],"directories": {"log_root": "custom_logs"}}',
        encoding="utf-8",
    )

    config = load_config(config_path)
    assert "custom" in config.skip
    # Defaults should still be present alongside overrides
    assert "custom_logs" == config.directories["log_root"]
    assert "models.py" in config.file_types


def test_load_config_rejects_invalid_types(tmp_path: Path) -> None:
    invalid_config = tmp_path / "invalid.json"
    invalid_config.write_text('{"skip": "not-a-list"}', encoding="utf-8")

    with pytest.raises(RuntimeError):
        load_config(invalid_config)


def test_load_config_warns_on_duplicate_entries(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text('{"skip": ["dup", "dup", "dup "]}', encoding="utf-8")

    with pytest.warns(RuntimeWarning, match="Duplicate entries ignored"):
        loaded = load_config(config_path)

    assert "dup" in loaded.skip


def test_resolve_paths_returns_expected_structure(tmp_path: Path) -> None:
    config = get_config()
    resolved = resolve_paths(config, base_dir=tmp_path)

    assert resolved.log_dir == tmp_path / config.directories.get("log_root", "logs")
    assert resolved.python_log_dir.parent == resolved.log_dir
    assert resolved.capture_all_log.parent == resolved.single_log_dir


def test_resolve_paths_rejects_escape(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text('{"directories": {"log_root": "../escape"}}', encoding="utf-8")

    loaded = load_config(config_path)

    with pytest.raises(RuntimeError):
        resolve_paths(loaded, base_dir=tmp_path)


def test_config_to_dict_round_trip() -> None:
    config = get_config()
    serialized = config.to_dict()

    assert set(serialized) == {
        "skip",
        "file_types",
        "user_ignore_patterns",
        "directories",
        "collection_logs",
        "single_targets",
    }
    assert isinstance(serialized["skip"], list)
    assert isinstance(serialized["file_types"], dict)
    assert serialized["user_ignore_patterns"] == sorted(serialized["user_ignore_patterns"])


def test_file_group_resolver_returns_copy() -> None:
    resolver = get_file_group_resolver()
    resolver["new.py"] = "new"
    assert "new.py" not in get_config().file_types


def test_config_mappings_are_immutable() -> None:
    config = get_config()

    with pytest.raises(TypeError):
        config.file_types["sample.py"] = "sample"

    with pytest.raises(TypeError):
        config.directories["extra"] = "value"

    with pytest.raises(TypeError):
        config.collection_logs["alt"] = "override"


def test_to_dict_returns_mutable_copies() -> None:
    config = get_config()
    serialized = config.to_dict()

    serialized["directories"]["new_dir"] = "value"
    assert "new_dir" not in config.directories


def test_environment_override_loads_custom_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    custom_config = tmp_path / "custom.json"
    custom_config.write_text('{"skip": ["env-skip"]}', encoding="utf-8")

    monkeypatch.setenv("ZSCRIPTS_CONFIG_PATH", str(custom_config))
    config._get_default_config.cache_clear()
    config._get_default_paths.cache_clear()

    loaded = load_config()
    assert "env-skip" in loaded.skip

    config._get_default_config.cache_clear()
    config._get_default_paths.cache_clear()


def test_unknown_keys_raise_helpful_error(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    config_path.write_text('{"unexpected": 1}', encoding="utf-8")

    with pytest.raises(RuntimeError, match="Unknown configuration keys"):
        load_config(config_path)
