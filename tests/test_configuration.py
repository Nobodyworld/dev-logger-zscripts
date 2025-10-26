"""Tests for configuration loading and overrides."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from zscripts import get_default_config
from zscripts.configuration import (
    ConfigurationError,
    load_toolkit_config,
    parse_override_pairs,
)


def test_load_toolkit_config_from_toml(tmp_path: Path) -> None:
    config_file = tmp_path / "settings.toml"
    config_file.write_text(
        "\n".join(
            [
                "timeout_seconds = 45",
                "dangerous_mode = true",
                "default_adapter = 'docker'",
                "allowed_paths = ['~/logs', './out']",
                "redact_patterns = ['foo', 'bar']",
                "examples_path = './custom_examples'",
                "telemetry_enabled = true",
                "telemetry_host = '0.0.0.0'",
                "telemetry_port = 9100",
                "log_level = 'debug'",
                "log_format = 'json'",
                "report_format = 'markdown'",
                "report_redact = true",
                "extensions = ['pkg.module', 'another.ext']",
            ]
        ),
        encoding="utf-8",
    )

    config = load_toolkit_config(path=config_file, overrides={}, base=get_default_config())

    assert config.timeout_seconds == 45
    assert config.dangerous_mode is True
    assert config.default_adapter == "docker"
    assert config.allowed_paths == (
        Path("~/logs").expanduser(),
        Path("./out"),
    )
    assert config.redact_patterns == ("foo", "bar")
    assert config.examples_path == Path("./custom_examples")
    assert config.telemetry_enabled is True
    assert config.telemetry_host == "0.0.0.0"
    assert config.telemetry_port == 9100
    assert config.log_level == "DEBUG"
    assert config.log_format == "json"
    assert config.report_format == "markdown"
    assert config.report_redact is True
    assert config.extensions == ("pkg.module", "another.ext")


def test_load_toolkit_config_from_json(tmp_path: Path) -> None:
    config_file = tmp_path / "settings.json"
    config_file.write_text(
        json.dumps(
            {
                "timeout_seconds": 90,
                "default_adapter": "go",
                "allowed_paths": ["examples", "~/logs"],
            }
        ),
        encoding="utf-8",
    )

    config = load_toolkit_config(path=config_file, overrides={}, base=get_default_config())

    assert config.timeout_seconds == 90
    assert config.default_adapter == "go"
    assert config.allowed_paths[1] == Path("~/logs").expanduser()


def test_cli_overrides_take_precedence(tmp_path: Path) -> None:
    config_file = tmp_path / "settings.toml"
    config_file.write_text("timeout_seconds = 10", encoding="utf-8")

    overrides = parse_override_pairs(
        [
            "timeout_seconds=20",
            "dangerous_mode=false",
            "examples_path=~/alt_examples",
            "extensions=foo.bar, baz.qux",
            "report_format=markdown",
            "report_redact=true",
        ]
    )

    config = load_toolkit_config(path=config_file, overrides=overrides, base=get_default_config())

    assert config.timeout_seconds == 20
    assert config.dangerous_mode is False
    assert config.examples_path == Path("~/alt_examples").expanduser()
    assert config.extensions == ("foo.bar", "baz.qux")
    assert config.report_format == "markdown"
    assert config.report_redact is True


def test_allowed_paths_string_is_split_on_delimiters(tmp_path: Path) -> None:
    config_file = tmp_path / "settings.toml"
    config_file.write_text("allowed_paths = '~/logs:./dist'", encoding="utf-8")

    config = load_toolkit_config(path=config_file, overrides={}, base=get_default_config())

    assert tuple(config.allowed_paths) == (
        Path("~/logs").expanduser(),
        Path("./dist"),
    )


def test_unknown_key_raises_configuration_error(tmp_path: Path) -> None:
    config_file = tmp_path / "settings.toml"
    config_file.write_text("mystery = 5", encoding="utf-8")

    with pytest.raises(ConfigurationError):
        load_toolkit_config(path=config_file, overrides={}, base=get_default_config())


def test_overrides_with_unknown_key_raise_configuration_error() -> None:
    with pytest.raises(ConfigurationError):
        load_toolkit_config(
            path=None,
            overrides={"mystery": "value"},
            base=get_default_config(),
        )


def test_invalid_log_format_raises(tmp_path: Path) -> None:
    config_file = tmp_path / "settings.toml"
    config_file.write_text("log_format = 'xml'", encoding="utf-8")

    with pytest.raises(ConfigurationError):
        load_toolkit_config(path=config_file, overrides={}, base=get_default_config())


def test_invalid_report_format_raises(tmp_path: Path) -> None:
    config_file = tmp_path / "settings.toml"
    config_file.write_text("report_format = 'pdf'", encoding="utf-8")

    with pytest.raises(ConfigurationError):
        load_toolkit_config(path=config_file, overrides={}, base=get_default_config())


def test_parse_override_pairs_requires_key_value() -> None:
    with pytest.raises(ConfigurationError):
        parse_override_pairs(["not-a-pair"])


def test_parse_override_pairs_rejects_empty_key() -> None:
    with pytest.raises(ConfigurationError):
        parse_override_pairs(["=value"])


def test_boolean_overrides_accept_string_variants(tmp_path: Path) -> None:
    config_file = tmp_path / "settings.toml"
    config_file.write_text("telemetry_enabled = false", encoding="utf-8")

    overrides = parse_override_pairs(["telemetry_enabled=On", "dangerous_mode=off"])
    config = load_toolkit_config(path=config_file, overrides=overrides, base=get_default_config())

    assert config.telemetry_enabled is True
    assert config.dangerous_mode is False


def test_missing_configuration_file_raises(tmp_path: Path) -> None:
    missing = tmp_path / "nope.toml"

    with pytest.raises(ConfigurationError):
        load_toolkit_config(path=missing, overrides={}, base=get_default_config())


def test_directory_configuration_path_raises(tmp_path: Path) -> None:
    with pytest.raises(ConfigurationError):
        load_toolkit_config(path=tmp_path, overrides={}, base=get_default_config())


def test_configuration_disallows_empty_allowed_paths(tmp_path: Path) -> None:
    config_file = tmp_path / "settings.toml"
    config_file.write_text("allowed_paths = ''", encoding="utf-8")

    with pytest.raises(ConfigurationError):
        load_toolkit_config(path=config_file, overrides={}, base=get_default_config())


def test_configuration_rejects_invalid_json(tmp_path: Path) -> None:
    config_file = tmp_path / "settings.json"
    config_file.write_text("{ not: valid }", encoding="utf-8")

    with pytest.raises(ConfigurationError):
        load_toolkit_config(path=config_file, overrides={}, base=get_default_config())


def test_configuration_rejects_non_mapping_payload(tmp_path: Path) -> None:
    config_file = tmp_path / "settings.json"
    config_file.write_text("[]", encoding="utf-8")

    with pytest.raises(ConfigurationError):
        load_toolkit_config(path=config_file, overrides={}, base=get_default_config())


def test_configuration_rejects_negative_ports(tmp_path: Path) -> None:
    config_file = tmp_path / "settings.toml"
    config_file.write_text("telemetry_port = -1", encoding="utf-8")

    with pytest.raises(ConfigurationError):
        load_toolkit_config(path=config_file, overrides={}, base=get_default_config())


def test_configuration_rejects_bool_as_integer(tmp_path: Path) -> None:
    config_file = tmp_path / "settings.toml"
    config_file.write_text("telemetry_port = true", encoding="utf-8")

    with pytest.raises(ConfigurationError):
        load_toolkit_config(path=config_file, overrides={}, base=get_default_config())


def test_base_config_is_not_mutated(tmp_path: Path) -> None:
    base = get_default_config()
    config_file = tmp_path / "settings.toml"
    config_file.write_text("timeout_seconds = 5", encoding="utf-8")

    updated = load_toolkit_config(path=config_file, overrides={}, base=base)

    assert updated.timeout_seconds == 5
    assert base.timeout_seconds == get_default_config().timeout_seconds


def test_configuration_rejects_unsupported_format(tmp_path: Path) -> None:
    config_file = tmp_path / "settings.yaml"
    config_file.write_text("timeout_seconds: 5", encoding="utf-8")

    with pytest.raises(ConfigurationError):
        load_toolkit_config(path=config_file, overrides={}, base=get_default_config())


def test_configuration_rejects_non_iterable_allowed_paths(tmp_path: Path) -> None:
    config_file = tmp_path / "settings.toml"
    config_file.write_text("allowed_paths = 1", encoding="utf-8")

    with pytest.raises(ConfigurationError):
        load_toolkit_config(path=config_file, overrides={}, base=get_default_config())


def test_configuration_rejects_invalid_redact_patterns(tmp_path: Path) -> None:
    config_file = tmp_path / "settings.toml"
    config_file.write_text("redact_patterns = 42", encoding="utf-8")

    with pytest.raises(ConfigurationError):
        load_toolkit_config(path=config_file, overrides={}, base=get_default_config())


def test_configuration_rejects_examples_path_non_string(tmp_path: Path) -> None:
    config_file = tmp_path / "settings.toml"
    config_file.write_text("examples_path = ''", encoding="utf-8")

    with pytest.raises(ConfigurationError):
        load_toolkit_config(path=config_file, overrides={}, base=get_default_config())


def test_configuration_rejects_numeric_bool_outside_range(tmp_path: Path) -> None:
    config_file = tmp_path / "settings.toml"
    config_file.write_text("dangerous_mode = 2", encoding="utf-8")

    with pytest.raises(ConfigurationError):
        load_toolkit_config(path=config_file, overrides={}, base=get_default_config())


def test_configuration_rejects_invalid_extension_sequence(tmp_path: Path) -> None:
    config_file = tmp_path / "settings.toml"
    config_file.write_text("extensions = 7", encoding="utf-8")

    with pytest.raises(ConfigurationError):
        load_toolkit_config(path=config_file, overrides={}, base=get_default_config())
