from __future__ import annotations

import http.client
import json
import subprocess
from pathlib import Path
from urllib.error import HTTPError

import pytest

from scripts import validate_docs_links as validator


class _Response:
    def __init__(self, status: int = 200) -> None:
        self.status = status

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_args: object) -> None:
        return None


def _git(repository: Path, *arguments: str) -> None:
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=False,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stderr


def _init_repository(repository: Path) -> None:
    _git(repository, "init")
    _git(repository, "config", "user.name", "Zscripts Test")
    _git(repository, "config", "user.email", "zscripts-test@example.invalid")


def test_markdown_scope_uses_repository_gitignore_only(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    _init_repository(tmp_path)
    (tmp_path / ".gitignore").write_text(
        ".pytest_cache/\nrepo-only.md\ntracked-ignored.md\n",
        encoding="utf-8",
    )
    (tmp_path / "README.md").write_text("# Root\n", encoding="utf-8")
    (tmp_path / "tracked-ignored.md").write_text("# Tracked\n", encoding="utf-8")
    _git(tmp_path, "add", ".gitignore", "README.md")
    _git(tmp_path, "add", "-f", "tracked-ignored.md")

    (tmp_path / "new.md").write_text("# New\n", encoding="utf-8")
    (tmp_path / "global-only.md").write_text("# Global\n", encoding="utf-8")
    (tmp_path / "info-only.md").write_text("# Info\n", encoding="utf-8")
    (tmp_path / "repo-only.md").write_text("# Ignored\n", encoding="utf-8")
    cache_dir = tmp_path / ".pytest_cache"
    cache_dir.mkdir()
    (cache_dir / "README.md").write_text("# Cache\n", encoding="utf-8")

    global_excludes = tmp_path / "global-excludes"
    global_excludes.write_text("global-only.md\n", encoding="utf-8")
    global_config = tmp_path / "global.gitconfig"
    global_config.write_text(
        f"[core]\n\texcludesFile = {global_excludes.as_posix()}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(global_config))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path / "xdg"))

    info_exclude = tmp_path / ".git" / "info" / "exclude"
    info_exclude.write_text("info-only.md\n", encoding="utf-8")

    monkeypatch.setattr(validator, "ROOT", tmp_path)

    selected = [path.relative_to(tmp_path).as_posix() for path in validator._iter_markdown_files()]

    assert selected == [
        "README.md",
        "global-only.md",
        "info-only.md",
        "new.md",
        "tracked-ignored.md",
    ]


@pytest.mark.parametrize(
    "payload",
    [
        b"../escape.md\0",
        b"/absolute.md\0",
        b"docs/readme.md",
        b"duplicate.md\0duplicate.md\0",
        b"\xff.md\0",
    ],
)
def test_git_path_decoder_fails_closed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    payload: bytes,
) -> None:
    monkeypatch.setattr(validator, "ROOT", tmp_path)

    with pytest.raises(validator.LinkScopeError):
        validator._decode_git_paths(payload)


def test_external_check_retries_remote_disconnect_and_falls_back_to_get(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    methods: list[str] = []

    def fake_urlopen(request: object, timeout: int) -> _Response:
        assert timeout == validator.EXTERNAL_TIMEOUT_SECONDS
        method = request.get_method()  # type: ignore[attr-defined]
        methods.append(method)
        if len(methods) < validator.EXTERNAL_ATTEMPTS:
            raise http.client.RemoteDisconnected("remote end closed connection")
        return _Response()

    monkeypatch.setattr(validator, "urlopen", fake_urlopen)
    monkeypatch.setattr(validator.time, "sleep", lambda _seconds: None)

    assert validator._check_external("https://example.test") is None
    assert methods == ["HEAD", "HEAD", "GET"]


def test_external_check_returns_bounded_failure_after_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = 0

    def fake_urlopen(_request: object, timeout: int) -> _Response:
        assert timeout == validator.EXTERNAL_TIMEOUT_SECONDS
        nonlocal attempts
        attempts += 1
        raise http.client.RemoteDisconnected("remote end closed connection")

    monkeypatch.setattr(validator, "urlopen", fake_urlopen)
    monkeypatch.setattr(validator.time, "sleep", lambda _seconds: None)

    reason = validator._check_external("https://example.test")

    assert attempts == validator.EXTERNAL_ATTEMPTS
    assert reason == "RemoteDisconnected: remote end closed connection after 3 attempts"


def test_external_check_retries_transient_http_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = 0

    def fake_urlopen(request: object, timeout: int) -> _Response:
        assert timeout == validator.EXTERNAL_TIMEOUT_SECONDS
        nonlocal attempts
        attempts += 1
        if attempts < validator.EXTERNAL_ATTEMPTS:
            raise HTTPError(
                request.full_url,  # type: ignore[attr-defined]
                503,
                "Service Unavailable",
                None,
                None,
            )
        return _Response()

    monkeypatch.setattr(validator, "urlopen", fake_urlopen)
    monkeypatch.setattr(validator.time, "sleep", lambda _seconds: None)

    assert validator._check_external("https://example.test") is None
    assert attempts == validator.EXTERNAL_ATTEMPTS


def test_duplicate_external_urls_are_checked_once(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.md"
    second = tmp_path / "second.md"
    first.write_text("[One](https://example.test)\n", encoding="utf-8")
    second.write_text("[Two](https://example.test)\n", encoding="utf-8")

    calls = 0

    def fake_check(_url: str) -> None:
        nonlocal calls
        calls += 1
        return None

    monkeypatch.setattr(validator, "ROOT", tmp_path)
    monkeypatch.setattr(validator, "_iter_markdown_files", lambda: [first, second])
    monkeypatch.setattr(validator, "_check_external", fake_check)

    failures, counts = validator.validate_links()

    assert failures == []
    assert calls == 1
    assert counts == {"files": 2, "links": 2, "external": 2, "internal": 0}


def test_internal_link_behavior_is_preserved(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    source = docs / "guide.md"
    target = docs / "target.md"
    target.write_text("# Target\n", encoding="utf-8")

    monkeypatch.setattr(validator, "ROOT", tmp_path)

    assert validator._check_internal(source, "target.md#section") is None
    assert validator._check_internal(source, "missing.md") == "target does not exist"
    assert validator._check_internal(source, "../../escape.md") == "resolves outside repository"


def test_main_reports_scope_failure_without_traceback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    def fail_scope() -> list[Path]:
        raise validator.LinkScopeError("Unable to determine documentation scope.")

    monkeypatch.setattr(validator, "ROOT", tmp_path)
    monkeypatch.setattr(validator, "_iter_markdown_files", fail_scope)

    assert validator.main() == 1

    report_path = tmp_path / "artifacts" / "quality" / "link_validation.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["scope_error"] == "Unable to determine documentation scope."
    assert report["files_scanned"] == 0
