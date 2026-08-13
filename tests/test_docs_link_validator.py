from __future__ import annotations

import http.client
import json
import os
import subprocess
import sys
from pathlib import Path
from urllib.error import HTTPError, URLError

import pytest

from scripts import validate_docs_links as validator


class _Response:
    def __init__(self, status: int = 200) -> None:
        self.status = status
        self.closed = False
        self.read_called = False

    def __enter__(self) -> _Response:
        return self

    def __exit__(self, *_args: object) -> None:
        self.close()
        return None

    def close(self) -> None:
        self.closed = True

    def read(self, *_args: object, **_kwargs: object) -> bytes:
        self.read_called = True
        raise AssertionError("The link validator must not read response bodies.")


class _ErrorBody:
    def __init__(self) -> None:
        self.closed = False

    def close(self) -> None:
        self.closed = True


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
    (tmp_path / "xdg-only.md").write_text("# XDG\n", encoding="utf-8")
    (tmp_path / "system-only.md").write_text("# System\n", encoding="utf-8")
    (tmp_path / "info-only.md").write_text("# Info\n", encoding="utf-8")
    (tmp_path / "repo-only.md").write_text("# Ignored\n", encoding="utf-8")
    cache_dir = tmp_path / ".pytest_cache"
    cache_dir.mkdir()
    (cache_dir / "README.md").write_text("# Cache\n", encoding="utf-8")
    nested = tmp_path / "nested"
    nested.mkdir()
    (nested / ".gitignore").write_text("ignored.md\n", encoding="utf-8")
    (nested / "ignored.md").write_text("# Nested ignored\n", encoding="utf-8")
    (nested / "keep.md").write_text("# Nested included\n", encoding="utf-8")

    global_excludes = tmp_path / "global-excludes"
    global_excludes.write_text("global-only.md\n", encoding="utf-8")
    global_config = tmp_path / "global.gitconfig"
    global_config.write_text(
        f"[core]\n\texcludesFile = {global_excludes.as_posix()}\n",
        encoding="utf-8",
    )
    xdg = tmp_path / "xdg"
    (xdg / "git").mkdir(parents=True)
    xdg_excludes = tmp_path / "xdg-excludes"
    xdg_excludes.write_text("xdg-only.md\n", encoding="utf-8")
    (xdg / "git" / "config").write_text(
        f"[core]\n\texcludesFile = {xdg_excludes.as_posix()}\n",
        encoding="utf-8",
    )
    system_excludes = tmp_path / "system-excludes"
    system_excludes.write_text("system-only.md\n", encoding="utf-8")
    system_config = tmp_path / "system.gitconfig"
    system_config.write_text(
        f"[core]\n\texcludesFile = {system_excludes.as_posix()}\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("HOME", str(tmp_path / "home"))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(global_config))
    monkeypatch.setenv("GIT_CONFIG_SYSTEM", str(system_config))
    monkeypatch.setenv("XDG_CONFIG_HOME", str(xdg))

    info_exclude = tmp_path / ".git" / "info" / "exclude"
    info_exclude.write_text("info-only.md\n", encoding="utf-8")

    monkeypatch.setattr(validator, "ROOT", tmp_path)

    first = [path.relative_to(tmp_path).as_posix() for path in validator._iter_markdown_files()]
    second = [path.relative_to(tmp_path).as_posix() for path in validator._iter_markdown_files()]

    assert (
        first
        == second
        == [
            "README.md",
            "global-only.md",
            "info-only.md",
            "nested/keep.md",
            "new.md",
            "system-only.md",
            "tracked-ignored.md",
            "xdg-only.md",
        ]
    )
    assert len(first) == 8


@pytest.mark.parametrize(
    "payload",
    [
        b"../escape.md\0",
        b"/absolute.md\0",
        b"C:/absolute.md\0",
        b"./normalized.md\0",
        b"docs/readme.md",
        b"duplicate.md\0duplicate.md\0",
        b"\xff.md\0",
        b"not-markdown.txt\0",
        b"\0",
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


def test_git_path_parser_is_incremental_and_accepts_exact_shared_entry_limit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    class NoSplitBytes(bytes):
        def split(self, *_args: object, **_kwargs: object) -> list[bytes]:
            raise AssertionError("Whole-payload split must not be used.")

    monkeypatch.setattr(validator, "ROOT", tmp_path)
    budget = validator._PathEntryBudget(2)
    tracked = validator._GitPathParser(budget)
    tracked.feed(NoSplitBytes(b"tracked.md\0"))
    untracked = validator._GitPathParser(budget)
    untracked.feed(NoSplitBytes(b"nested/untracked.md\0"))

    assert [path.relative_to(tmp_path).as_posix() for path in tracked.finish()] == ["tracked.md"]
    assert [path.relative_to(tmp_path).as_posix() for path in untracked.finish()] == ["nested/untracked.md"]
    assert budget.count == 2


def test_git_path_parser_fails_one_entry_beyond_shared_limit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(validator, "ROOT", tmp_path)
    budget = validator._PathEntryBudget(1)
    first = validator._GitPathParser(budget)
    first.feed(b"first.md\0")
    assert first.finish()
    second = validator._GitPathParser(budget)

    with pytest.raises(validator.LinkScopeError, match="too many"):
        second.feed(b"second.md\0")


def test_git_query_contract_is_fixed_no_shell_and_configuration_isolated(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(validator, "ROOT", tmp_path)
    monkeypatch.setenv("GIT_CONFIG_COUNT", "1")
    monkeypatch.setenv("GIT_CONFIG_KEY_0", "core.excludesFile")
    monkeypatch.setenv("GIT_CONFIG_VALUE_0", "machine-ignore")
    monkeypatch.setenv("GIT_DIR", "machine-git-dir")
    processes, invocations = _replace_git_with_python_producer(
        monkeypatch,
        "import sys;sys.stdout.buffer.write(b'path.md\\0')",
    )

    paths = validator._run_git_path_query(("ls-files", "--cached", "-z", "--", "*.md"))

    assert [path.relative_to(tmp_path).as_posix() for path in paths] == ["path.md"]
    assert len(processes) == len(invocations) == 1
    command, kwargs = invocations[0]
    assert command == [
        "git",
        "--no-optional-locks",
        "-c",
        "core.fsmonitor=false",
        "-c",
        "core.quotepath=false",
        "-c",
        "core.excludesFile=",
        "ls-files",
        "--cached",
        "-z",
        "--",
        "*.md",
    ]
    assert kwargs["shell"] is False
    assert kwargs["cwd"] == tmp_path
    environment = kwargs["env"]
    assert isinstance(environment, dict)
    assert environment["GIT_CONFIG_NOSYSTEM"] == "1"
    assert environment["GIT_CONFIG_GLOBAL"] == os.devnull
    assert environment["GIT_TERMINAL_PROMPT"] == "0"
    assert environment["LC_ALL"] == "C"
    assert "GIT_CONFIG_COUNT" not in environment
    assert "GIT_CONFIG_KEY_0" not in environment
    assert "GIT_CONFIG_VALUE_0" not in environment
    assert "GIT_DIR" not in environment
    assert processes[0].poll() is not None


def test_git_bounds_are_conservative_and_explicit() -> None:
    assert validator.GIT_MAX_OUTPUT_BYTES == 8 * 1024 * 1024
    assert validator.MAX_MARKDOWN_PATH_ENTRIES == 20_000
    assert validator.GIT_TIMEOUT_SECONDS == 15
    assert validator.GIT_MAX_STDERR_BYTES == 64 * 1024


def test_git_query_accepts_output_at_exact_byte_limit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    payload = b"a.md\0"
    monkeypatch.setattr(validator, "ROOT", tmp_path)
    monkeypatch.setattr(validator, "GIT_MAX_OUTPUT_BYTES", len(payload))
    processes, _ = _replace_git_with_python_producer(
        monkeypatch,
        f"import sys;sys.stdout.buffer.write({payload!r})",
    )

    paths = validator._run_git_path_query(("ls-files", "--cached", "-z"))

    assert [path.relative_to(tmp_path).as_posix() for path in paths] == ["a.md"]
    assert processes[0].poll() is not None


def test_git_query_terminates_producer_one_byte_over_limit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    payload = b"a.md\0x"
    monkeypatch.setattr(validator, "ROOT", tmp_path)
    monkeypatch.setattr(validator, "GIT_MAX_OUTPUT_BYTES", len(payload) - 1)
    processes, _ = _replace_git_with_python_producer(
        monkeypatch,
        f"import sys,time;sys.stdout.buffer.write({payload!r});sys.stdout.buffer.flush();time.sleep(10)",
    )

    with pytest.raises(validator.LinkScopeError, match="byte limit"):
        validator._run_git_path_query(("ls-files", "--cached", "-z"))

    assert processes[0].poll() is not None


def test_git_query_drains_but_bounds_stderr_capture(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(validator, "ROOT", tmp_path)
    monkeypatch.setattr(validator, "GIT_MAX_STDERR_BYTES", 8)
    processes, _ = _replace_git_with_python_producer(
        monkeypatch,
        "import sys;sys.stderr.buffer.write(b'x'*131072);sys.stderr.buffer.flush();"
        "sys.stdout.buffer.write(b'a.md\\0')",
    )

    paths = validator._run_git_path_query(("ls-files", "--cached", "-z"))

    assert [path.relative_to(tmp_path).as_posix() for path in paths] == ["a.md"]
    assert processes[0].poll() is not None


def test_git_query_timeout_terminates_and_reaps_process(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(validator, "ROOT", tmp_path)
    monkeypatch.setattr(validator, "GIT_TIMEOUT_SECONDS", 0.05)
    processes, _ = _replace_git_with_python_producer(monkeypatch, "import time;time.sleep(10)")

    with pytest.raises(validator.LinkScopeError, match="timed out"):
        validator._run_git_path_query(("ls-files", "--cached", "-z"))

    assert processes[0].poll() is not None


def test_git_cleanup_kills_when_terminate_does_not_reap() -> None:
    class ReluctantProcess:
        def __init__(self) -> None:
            self.terminated = False
            self.killed = False

        def poll(self) -> None:
            return None

        def terminate(self) -> None:
            self.terminated = True

        def kill(self) -> None:
            self.killed = True

        def wait(self, timeout: float | None = None) -> int:
            if timeout is not None and not self.killed:
                raise subprocess.TimeoutExpired("git", timeout)
            return 0

    process = ReluctantProcess()

    validator._terminate_and_reap(process)  # type: ignore[arg-type]

    assert process.terminated is True
    assert process.killed is True


def test_external_check_retries_remote_disconnect_and_falls_back_to_get(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    requests: list[tuple[str, str | None]] = []
    response = _Response()

    def fake_urlopen(request: object, timeout: int) -> _Response:
        assert timeout == validator.EXTERNAL_TIMEOUT_SECONDS
        method = request.get_method()  # type: ignore[attr-defined]
        requests.append((method, request.get_header("Range")))  # type: ignore[attr-defined]
        if len(requests) < validator.EXTERNAL_ATTEMPTS:
            raise http.client.RemoteDisconnected("remote end closed connection")
        return response

    monkeypatch.setattr(validator, "urlopen", fake_urlopen)
    monkeypatch.setattr(validator.time, "sleep", lambda _seconds: None)

    assert validator._check_external("https://example.test") is None
    assert requests == [("HEAD", None), ("HEAD", None), ("GET", "bytes=0-0")]
    assert response.closed is True
    assert response.read_called is False


def test_external_check_retries_remote_disconnect_then_head_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    methods: list[str] = []

    def fake_urlopen(request: object, timeout: int) -> _Response:
        assert timeout == validator.EXTERNAL_TIMEOUT_SECONDS
        methods.append(request.get_method())  # type: ignore[attr-defined]
        if len(methods) == 1:
            raise http.client.RemoteDisconnected("remote end closed connection")
        return _Response()

    monkeypatch.setattr(validator, "urlopen", fake_urlopen)
    monkeypatch.setattr(validator.time, "sleep", lambda _seconds: None)

    assert validator._check_external("https://example.test") is None
    assert methods == ["HEAD", "HEAD"]


@pytest.mark.parametrize(
    "failure",
    [
        TimeoutError("timed out"),
        ConnectionResetError("connection reset"),
        URLError("temporary resolver failure"),
        http.client.HTTPException("malformed transient response"),
    ],
)
def test_external_check_retries_transport_failures_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
    failure: BaseException,
) -> None:
    attempts = 0

    def fake_urlopen(_request: object, timeout: int) -> _Response:
        assert timeout == validator.EXTERNAL_TIMEOUT_SECONDS
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise failure
        return _Response()

    monkeypatch.setattr(validator, "urlopen", fake_urlopen)
    monkeypatch.setattr(validator.time, "sleep", lambda _seconds: None)

    assert validator._check_external("https://example.test") is None
    assert attempts == 2


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
    assert len(reason) <= validator.MAX_FAILURE_REASON_CHARS


def test_external_check_bounds_exhausted_transport_reason(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_urlopen(_request: object, timeout: int) -> _Response:
        assert timeout == validator.EXTERNAL_TIMEOUT_SECONDS
        raise OSError("x" * 2_000)

    monkeypatch.setattr(validator, "urlopen", fake_urlopen)
    monkeypatch.setattr(validator.time, "sleep", lambda _seconds: None)

    reason = validator._check_external("https://example.test")

    assert reason is not None
    assert len(reason) <= validator.MAX_FAILURE_REASON_CHARS
    assert reason.endswith("after 3 attempts")


def test_external_check_retries_transient_http_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = 0
    body = _ErrorBody()

    def fake_urlopen(request: object, timeout: int) -> _Response:
        assert timeout == validator.EXTERNAL_TIMEOUT_SECONDS
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise HTTPError(
                request.full_url,  # type: ignore[attr-defined]
                503,
                "Service Unavailable",
                None,
                body,  # type: ignore[arg-type]
            )
        return _Response()

    monkeypatch.setattr(validator, "urlopen", fake_urlopen)
    monkeypatch.setattr(validator.time, "sleep", lambda _seconds: None)

    assert validator._check_external("https://example.test") is None
    assert attempts == 2
    assert body.closed is True


def test_external_check_returns_permanent_404_without_retry_and_closes_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    attempts = 0
    body = _ErrorBody()

    def fake_urlopen(request: object, timeout: int) -> _Response:
        assert timeout == validator.EXTERNAL_TIMEOUT_SECONDS
        nonlocal attempts
        attempts += 1
        raise HTTPError(
            request.full_url,  # type: ignore[attr-defined]
            404,
            "Not Found",
            None,
            body,  # type: ignore[arg-type]
        )

    monkeypatch.setattr(validator, "urlopen", fake_urlopen)
    monkeypatch.setattr(validator.time, "sleep", lambda _seconds: None)

    assert validator._check_external("https://example.test") == "HTTP 404"
    assert attempts == 1
    assert body.closed is True


def test_external_request_rejects_non_http_scheme_without_opening(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def unexpected_urlopen(*_args: object, **_kwargs: object) -> _Response:
        raise AssertionError("A non-HTTP URL must not reach urlopen.")

    monkeypatch.setattr(validator, "urlopen", unexpected_urlopen)

    assert validator._check_external("file:///outside") == (
        "invalid URL: external URLs must use HTTP or HTTPS"
    )


@pytest.mark.parametrize("status", [401, 403, 405, 429])
def test_external_check_accepts_expected_http_errors_and_closes_them(
    monkeypatch: pytest.MonkeyPatch,
    status: int,
) -> None:
    body = _ErrorBody()

    def fake_urlopen(request: object, timeout: int) -> _Response:
        assert timeout == validator.EXTERNAL_TIMEOUT_SECONDS
        raise HTTPError(
            request.full_url,  # type: ignore[attr-defined]
            status,
            "Accepted validator status",
            None,
            body,  # type: ignore[arg-type]
        )

    monkeypatch.setattr(validator, "urlopen", fake_urlopen)

    assert validator._check_external("https://example.test") is None
    assert body.closed is True


@pytest.mark.parametrize("status", [200, 204, 301, 302])
def test_external_check_accepts_success_and_redirect_responses_without_body_reads(
    monkeypatch: pytest.MonkeyPatch,
    status: int,
) -> None:
    response = _Response(status)
    monkeypatch.setattr(validator, "urlopen", lambda _request, timeout: response)

    assert validator._check_external("https://example.test") is None
    assert response.closed is True
    assert response.read_called is False


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

    assert validator._check_internal(source, "#section") is None
    assert validator._check_internal(source, "target.md#section") is None
    assert validator._check_internal(source, "missing.md") == "target does not exist"
    assert validator._check_internal(source, "../../escape.md") == "resolves outside repository"


def test_internal_link_through_symlink_outside_repository_fails_when_supported(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    docs = tmp_path / "docs"
    docs.mkdir()
    source = docs / "guide.md"
    source.write_text("[Outside](outside.md)\n", encoding="utf-8")
    outside = tmp_path.parent / f"{tmp_path.name}-outside.md"
    outside.write_text("# Outside\n", encoding="utf-8")
    link = docs / "outside.md"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("This host does not permit symlink creation.")

    monkeypatch.setattr(validator, "ROOT", tmp_path)

    assert validator._check_internal(source, "outside.md") == "resolves outside repository"


def test_main_reports_scope_failure_without_traceback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    def fail_scope() -> list[Path]:
        raise validator.LinkScopeError(f"Unable to determine scope at {tmp_path}: {'x' * 1_000}")

    monkeypatch.setattr(validator, "ROOT", tmp_path)
    monkeypatch.setattr(validator, "_iter_markdown_files", fail_scope)

    assert validator.main() == 1

    report_path = tmp_path / "artifacts" / "quality" / "link_validation.json"
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert len(report["scope_error"]) <= validator.MAX_FAILURE_REASON_CHARS
    assert str(tmp_path) not in report["scope_error"]
    assert "<repository>" in report["scope_error"]
    assert report["files_scanned"] == 0
    output = capsys.readouterr().out
    assert str(tmp_path) not in output
    assert "Traceback" not in output
    assert "Report: artifacts/quality/link_validation.json" in output


def _replace_git_with_python_producer(
    monkeypatch: pytest.MonkeyPatch,
    script: str,
) -> tuple[
    list[subprocess.Popen[bytes]],
    list[tuple[list[str], dict[str, object]]],
]:
    original_popen = validator.subprocess.Popen
    processes: list[subprocess.Popen[bytes]] = []
    invocations: list[tuple[list[str], dict[str, object]]] = []

    def producer_popen(command: list[str], **kwargs: object) -> subprocess.Popen[bytes]:
        assert command[0] == "git"
        assert kwargs.get("shell") is False
        invocations.append((command, dict(kwargs)))
        process = original_popen(
            [sys.executable, "-c", script],
            **kwargs,  # type: ignore[arg-type]
        )
        processes.append(process)
        return process

    monkeypatch.setattr(validator.subprocess, "Popen", producer_popen)
    return processes, invocations
