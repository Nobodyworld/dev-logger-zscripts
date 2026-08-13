"""Validate Markdown links across repository documentation.

Checks:
- Tracked and untracked nonignored Markdown files are selected deterministically by Git.
- Internal relative links resolve to existing files.
- Internal anchor links reference existing files (anchor existence is not validated).
- External HTTP(S) links return an acceptable response after bounded transient retries.

Accepted external status codes: 2xx, 3xx, 401, 403, 405, 429.
"""

from __future__ import annotations

import http.client
import json
import os
import re
import subprocess  # nosec B404
import tempfile
import threading
import time
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import BinaryIO, Sequence
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
GIT_TIMEOUT_SECONDS = 15
GIT_TERMINATE_TIMEOUT_SECONDS = 1
GIT_MAX_OUTPUT_BYTES = 8 * 1024 * 1024
GIT_MAX_STDERR_BYTES = 64 * 1024
MAX_MARKDOWN_PATH_ENTRIES = 20_000
GIT_READ_CHUNK_BYTES = 64 * 1024
EXTERNAL_TIMEOUT_SECONDS = 10
EXTERNAL_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = (0.2, 0.8)
ACCEPTED_EXTERNAL_STATUSES = {401, 403, 405, 429}
TRANSIENT_EXTERNAL_STATUSES = {408, 425, 500, 502, 503, 504}
MAX_FAILURE_REASON_CHARS = 256


@dataclass(frozen=True, slots=True)
class LinkFailure:
    source: str
    link: str
    reason: str


class LinkScopeError(RuntimeError):
    """Raised when the repository documentation scope cannot be established safely."""


@dataclass(slots=True)
class _PathEntryBudget:
    maximum: int
    count: int = 0

    def consume(self) -> None:
        self.count += 1
        if self.count > self.maximum:
            raise LinkScopeError("Git returned too many documentation paths.")


class _GitPathParser:
    """Incrementally validate one NUL-delimited Git path stream."""

    def __init__(self, budget: _PathEntryBudget) -> None:
        self._budget = budget
        self._pending = bytearray()
        self._paths: list[Path] = []
        self._seen: set[str] = set()

    def feed(self, chunk: bytes) -> None:
        self._pending.extend(chunk)
        start = 0
        while True:
            end = self._pending.find(b"\0", start)
            if end < 0:
                break
            self._budget.consume()
            path, key = _decode_git_path(bytes(self._pending[start:end]))
            if key in self._seen:
                raise LinkScopeError("Git returned a duplicate documentation path.")
            self._seen.add(key)
            self._paths.append(path)
            start = end + 1
        if start:
            del self._pending[:start]

    def finish(self) -> list[Path]:
        if self._pending:
            raise LinkScopeError("Git returned an unterminated documentation path list.")
        return self._paths


def _git_environment() -> dict[str, str]:
    environment = os.environ.copy()
    for name in (
        "GIT_ALTERNATE_OBJECT_DIRECTORIES",
        "GIT_CEILING_DIRECTORIES",
        "GIT_COMMON_DIR",
        "GIT_CONFIG_COUNT",
        "GIT_CONFIG_PARAMETERS",
        "GIT_DIR",
        "GIT_DISCOVERY_ACROSS_FILESYSTEM",
        "GIT_INDEX_FILE",
        "GIT_OBJECT_DIRECTORY",
        "GIT_WORK_TREE",
    ):
        environment.pop(name, None)
    for name in tuple(environment):
        if name.startswith(("GIT_CONFIG_KEY_", "GIT_CONFIG_VALUE_")):
            environment.pop(name, None)
    environment.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
            "XDG_CONFIG_HOME": str(Path(tempfile.gettempdir()) / "zscripts-empty-git-config"),
            "LC_ALL": "C",
        }
    )
    return environment


def _decode_git_path(raw_path: bytes) -> tuple[Path, str]:
    try:
        text = raw_path.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise LinkScopeError("Git returned a non-UTF-8 documentation path.") from exc

    pure_path = PurePosixPath(text)
    normalized = pure_path.as_posix()
    if (
        not text
        or pure_path.is_absolute()
        or normalized != text
        or normalized == "."
        or ".." in pure_path.parts
        or re.match(r"^[A-Za-z]:", text)
        or (os.name == "nt" and "\\" in text)
    ):
        raise LinkScopeError("Git returned an unsafe documentation path.")

    root = ROOT.resolve()
    local_path = ROOT.joinpath(*pure_path.parts)
    try:
        local_path.resolve(strict=False).relative_to(root)
    except ValueError as exc:
        raise LinkScopeError("Git returned a documentation path outside the repository.") from exc
    if local_path.suffix.lower() != ".md":
        raise LinkScopeError("Git returned a non-Markdown documentation path.")
    return local_path, normalized


def _decode_git_paths(payload: bytes) -> list[Path]:
    parser = _GitPathParser(_PathEntryBudget(MAX_MARKDOWN_PATH_ENTRIES))
    parser.feed(payload)
    return parser.finish()


def _terminate_and_reap(process: subprocess.Popen[bytes]) -> None:
    if process.poll() is not None:
        process.wait()
        return
    try:
        process.terminate()
    except OSError:
        pass
    try:
        process.wait(timeout=GIT_TERMINATE_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        try:
            process.kill()
        except OSError:
            pass
        process.wait()


def _read_bounded_stderr(
    stream: BinaryIO,
    capture: bytearray,
    truncated: threading.Event,
    failed: threading.Event,
) -> None:
    try:
        while chunk := stream.read(GIT_READ_CHUNK_BYTES):
            remaining = GIT_MAX_STDERR_BYTES - len(capture)
            if remaining > 0:
                capture.extend(chunk[:remaining])
            if len(chunk) > max(remaining, 0):
                truncated.set()
    except OSError:
        failed.set()


def _run_git_path_query(
    arguments: Sequence[str],
    *,
    budget: _PathEntryBudget | None = None,
) -> list[Path]:
    command = [
        "git",
        "--no-optional-locks",
        "-c",
        "core.fsmonitor=false",
        "-c",
        "core.quotepath=false",
        "-c",
        "core.excludesFile=",
        *arguments,
    ]
    try:
        process = subprocess.Popen(  # nosec B603
            command,
            cwd=ROOT,
            env=_git_environment(),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            shell=False,
        )
    except OSError as exc:
        raise LinkScopeError("Unable to enumerate documentation paths with Git.") from exc

    stdout = process.stdout
    stderr = process.stderr
    if stdout is None or stderr is None:  # pragma: no cover - PIPE guarantees both streams
        _terminate_and_reap(process)
        raise LinkScopeError("Unable to enumerate documentation paths with Git.")

    parser = _GitPathParser(budget or _PathEntryBudget(MAX_MARKDOWN_PATH_ENTRIES))
    paths: list[Path] = []
    stdout_failures: list[BaseException] = []
    output_exceeded = threading.Event()
    stdout_failed = threading.Event()
    stderr_failed = threading.Event()
    stderr_truncated = threading.Event()
    stderr_capture = bytearray()

    def read_stdout() -> None:
        observed_bytes = 0
        try:
            while observed_bytes <= GIT_MAX_OUTPUT_BYTES:
                remaining = GIT_MAX_OUTPUT_BYTES + 1 - observed_bytes
                chunk = stdout.read(min(GIT_READ_CHUNK_BYTES, remaining))
                if not chunk:
                    paths.extend(parser.finish())
                    return
                observed_bytes += len(chunk)
                if observed_bytes > GIT_MAX_OUTPUT_BYTES:
                    output_exceeded.set()
                    return
                parser.feed(chunk)
        except (OSError, LinkScopeError) as exc:
            stdout_failures.append(exc)
            stdout_failed.set()

    stdout_reader = threading.Thread(target=read_stdout, daemon=True)
    stderr_reader = threading.Thread(
        target=_read_bounded_stderr,
        args=(stderr, stderr_capture, stderr_truncated, stderr_failed),
        daemon=True,
    )
    stdout_reader.start()
    stderr_reader.start()

    deadline = time.monotonic() + GIT_TIMEOUT_SECONDS
    timed_out = False
    while (
        process.poll() is None
        and not output_exceeded.is_set()
        and not stdout_failed.is_set()
        and not stderr_failed.is_set()
    ):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            timed_out = True
            break
        try:
            process.wait(timeout=min(0.05, remaining))
        except subprocess.TimeoutExpired:
            continue

    if timed_out or output_exceeded.is_set() or stdout_failed.is_set() or stderr_failed.is_set():
        _terminate_and_reap(process)
    else:
        process.wait()

    stdout_reader.join(timeout=GIT_TERMINATE_TIMEOUT_SECONDS)
    stderr_reader.join(timeout=GIT_TERMINATE_TIMEOUT_SECONDS)
    readers_alive = stdout_reader.is_alive() or stderr_reader.is_alive()
    if readers_alive:
        _terminate_and_reap(process)
    stdout.close()
    stderr.close()
    if readers_alive:
        stdout_reader.join(timeout=GIT_TERMINATE_TIMEOUT_SECONDS)
        stderr_reader.join(timeout=GIT_TERMINATE_TIMEOUT_SECONDS)

    if timed_out:
        raise LinkScopeError("Git documentation path enumeration timed out.")
    if output_exceeded.is_set():
        raise LinkScopeError("Git documentation path enumeration exceeded its byte limit.")
    if readers_alive or stderr_failed.is_set():
        raise LinkScopeError("Unable to capture Git documentation path output safely.")
    if stdout_failures:
        failure = stdout_failures[0]
        if isinstance(failure, LinkScopeError):
            raise failure
        raise LinkScopeError("Unable to read Git documentation path output safely.") from failure
    if process.returncode:
        suffix = " and truncated stderr" if stderr_truncated.is_set() else ""
        raise LinkScopeError(
            "Git documentation path enumeration failed with exit code "
            f"{process.returncode}, {len(stderr_capture)} captured stderr bytes{suffix}."
        )
    return paths


def _iter_markdown_files() -> list[Path]:
    budget = _PathEntryBudget(MAX_MARKDOWN_PATH_ENTRIES)
    tracked = _run_git_path_query(
        ("ls-files", "--cached", "-z", "--", "*.md"),
        budget=budget,
    )
    untracked = _run_git_path_query(
        (
            "ls-files",
            "--others",
            "--exclude-per-directory=.gitignore",
            "-z",
            "--",
            "*.md",
        ),
        budget=budget,
    )

    selected: dict[str, Path] = {}
    for path in [*tracked, *untracked]:
        key = path.relative_to(ROOT).as_posix()
        if key in selected:
            raise LinkScopeError("Git returned a duplicate documentation path across scopes.")
        selected[key] = path

    return [selected[key] for key in sorted(selected)]


def _normalize_link(raw: str) -> str:
    link = raw.strip().strip("<>")
    if " " in link and not link.startswith(("http://", "https://")):
        # Common Markdown pattern: path with optional title -> keep only path part.
        link = link.split(" ", 1)[0]
    return link


def _transport_reason(exc: BaseException) -> str:
    detail: object = exc.reason if isinstance(exc, URLError) else exc
    normalized = " ".join(str(detail).split())
    if not normalized:
        normalized = type(exc).__name__
    return _bounded_reason(f"{type(exc).__name__}: {normalized}")


def _bounded_reason(reason: str, maximum: int = MAX_FAILURE_REASON_CHARS) -> str:
    normalized = " ".join(reason.split())
    if len(normalized) <= maximum:
        return normalized
    return normalized[: maximum - 3] + "..."


def _bounded_scope_error(exc: LinkScopeError) -> str:
    reason = str(exc)
    for path in {ROOT, ROOT.resolve()}:
        for rendered in {str(path), path.as_posix()}:
            if rendered:
                reason = re.sub(re.escape(rendered), "<repository>", reason, flags=re.IGNORECASE)
    return _bounded_reason(reason)


def _request_external(url: str, method: str) -> int:
    if not url.startswith(("http://", "https://")):
        raise ValueError("external URLs must use HTTP or HTTPS")
    headers = {"User-Agent": "zscripts-link-check/1.0"}
    if method == "GET":
        headers["Range"] = "bytes=0-0"
    request = Request(url, method=method, headers=headers)
    with urlopen(request, timeout=EXTERNAL_TIMEOUT_SECONDS) as response:  # nosec B310
        return int(getattr(response, "status", 200))


def _check_external(url: str) -> str | None:
    last_reason = "unknown transport failure"

    for attempt in range(EXTERNAL_ATTEMPTS):
        method = "GET" if attempt == EXTERNAL_ATTEMPTS - 1 else "HEAD"
        try:
            status = _request_external(url, method)
            if 200 <= status < 400 or status in ACCEPTED_EXTERNAL_STATUSES:
                return None
            last_reason = f"HTTP {status}"
            if status not in TRANSIENT_EXTERNAL_STATUSES:
                return last_reason
        except HTTPError as exc:
            try:
                if exc.code in ACCEPTED_EXTERNAL_STATUSES:
                    return None
                last_reason = f"HTTP {exc.code}"
                if exc.code not in TRANSIENT_EXTERNAL_STATUSES:
                    return last_reason
            finally:
                exc.close()
        except ValueError as exc:
            return _bounded_reason(f"invalid URL: {exc}")
        except (
            URLError,
            http.client.HTTPException,
            TimeoutError,
            ConnectionResetError,
            OSError,
        ) as exc:
            last_reason = _transport_reason(exc)

        if attempt < EXTERNAL_ATTEMPTS - 1:
            time.sleep(RETRY_BACKOFF_SECONDS[attempt])

    suffix = f" after {EXTERNAL_ATTEMPTS} attempts"
    return _bounded_reason(last_reason, MAX_FAILURE_REASON_CHARS - len(suffix)) + suffix


def _check_internal(source: Path, link: str) -> str | None:
    target = link.split("#", 1)[0]
    if not target:
        return None
    resolved = (source.parent / target).resolve()
    try:
        resolved.relative_to(ROOT.resolve())
    except ValueError:
        return "resolves outside repository"
    if not resolved.exists():
        return "target does not exist"
    return None


def validate_links() -> tuple[list[LinkFailure], dict[str, int]]:
    failures: list[LinkFailure] = []
    counts = {"files": 0, "links": 0, "external": 0, "internal": 0}
    external_results: dict[str, str | None] = {}

    for file_path in _iter_markdown_files():
        counts["files"] += 1
        text = file_path.read_text(encoding="utf-8", errors="replace")
        for raw_link in LINK_RE.findall(text):
            link = _normalize_link(raw_link)
            if not link or link.startswith(("mailto:", "#")):
                continue
            counts["links"] += 1
            rel_source = file_path.relative_to(ROOT).as_posix()
            if link.startswith(("http://", "https://")):
                counts["external"] += 1
                if link not in external_results:
                    external_results[link] = _check_external(link)
                reason = external_results[link]
                if reason:
                    failures.append(LinkFailure(source=rel_source, link=link, reason=reason))
                continue
            counts["internal"] += 1
            reason = _check_internal(file_path, link)
            if reason:
                failures.append(LinkFailure(source=rel_source, link=link, reason=reason))

    return failures, counts


def _write_report(report: dict[str, object]) -> Path:
    quality_dir = ROOT / "artifacts" / "quality"
    quality_dir.mkdir(parents=True, exist_ok=True)
    output_path = quality_dir / "link_validation.json"
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return output_path


def main() -> int:
    scope_error: str | None = None
    failures: list[LinkFailure] = []
    counts = {"files": 0, "links": 0, "external": 0, "internal": 0}

    try:
        failures, counts = validate_links()
    except LinkScopeError as exc:
        scope_error = _bounded_scope_error(exc)

    report: dict[str, object] = {
        "files_scanned": counts["files"],
        "links_scanned": counts["links"],
        "internal_links": counts["internal"],
        "external_links": counts["external"],
        "failures": [asdict(failure) for failure in failures],
    }
    if scope_error is not None:
        report["scope_error"] = scope_error

    output_path = _write_report(report)
    report_display = output_path.relative_to(ROOT).as_posix()

    if failures or scope_error is not None:
        print(json.dumps(report, indent=2, sort_keys=True))
        print(f"Report: {report_display}")
        return 1

    print(
        "Link validation passed: "
        f"{counts['links']} links across {counts['files']} markdown files "
        f"({counts['internal']} internal, {counts['external']} external)."
    )
    print(f"Report: {report_display}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
