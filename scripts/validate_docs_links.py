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
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")
GIT_TIMEOUT_SECONDS = 15
EXTERNAL_TIMEOUT_SECONDS = 10
EXTERNAL_ATTEMPTS = 3
RETRY_BACKOFF_SECONDS = (0.2, 0.8)
ACCEPTED_EXTERNAL_STATUSES = {401, 403, 405, 429}
TRANSIENT_EXTERNAL_STATUSES = {408, 425, 500, 502, 503, 504}


@dataclass(frozen=True, slots=True)
class LinkFailure:
    source: str
    link: str
    reason: str


class LinkScopeError(RuntimeError):
    """Raised when the repository documentation scope cannot be established safely."""


def _git_environment() -> dict[str, str]:
    environment = os.environ.copy()
    environment.update(
        {
            "GIT_CONFIG_NOSYSTEM": "1",
            "GIT_CONFIG_GLOBAL": os.devnull,
            "GIT_TERMINAL_PROMPT": "0",
        }
    )
    return environment


def _decode_git_paths(payload: bytes) -> list[Path]:
    if not payload:
        return []
    if not payload.endswith(b"\0"):
        raise LinkScopeError("Git returned an unterminated documentation path list.")

    root = ROOT.resolve()
    decoded: list[Path] = []
    seen: set[str] = set()

    for raw_path in payload[:-1].split(b"\0"):
        try:
            text = raw_path.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise LinkScopeError("Git returned a non-UTF-8 documentation path.") from exc

        pure_path = PurePosixPath(text)
        if not text or pure_path.is_absolute() or text.startswith("/") or ".." in pure_path.parts:
            raise LinkScopeError("Git returned an unsafe documentation path.")

        local_path = ROOT.joinpath(*pure_path.parts)
        try:
            local_path.resolve(strict=False).relative_to(root)
        except ValueError as exc:
            raise LinkScopeError("Git returned a documentation path outside the repository.") from exc

        if local_path.suffix.lower() != ".md":
            raise LinkScopeError("Git returned a non-Markdown documentation path.")

        relative_key = pure_path.as_posix()
        if relative_key in seen:
            raise LinkScopeError("Git returned a duplicate documentation path.")
        seen.add(relative_key)
        decoded.append(local_path)

    return decoded


def _run_git_path_query(arguments: list[str]) -> list[Path]:
    command = ["git", "-c", "core.quotepath=false", *arguments]
    try:
        result = subprocess.run(
            command,
            cwd=ROOT,
            env=_git_environment(),
            check=False,
            capture_output=True,
            timeout=GIT_TIMEOUT_SECONDS,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise LinkScopeError("Unable to enumerate documentation paths with Git.") from exc

    if result.returncode != 0:
        raise LinkScopeError(
            f"Git documentation path enumeration failed with exit code {result.returncode}."
        )
    return _decode_git_paths(result.stdout)


def _iter_markdown_files() -> list[Path]:
    tracked = _run_git_path_query(["ls-files", "--cached", "-z", "--", "*.md"])
    untracked = _run_git_path_query(
        [
            "ls-files",
            "--others",
            "--exclude-per-directory=.gitignore",
            "-z",
            "--",
            "*.md",
        ]
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
    return f"{type(exc).__name__}: {normalized}"


def _request_external(url: str, method: str) -> int:
    headers = {"User-Agent": "zscripts-link-check/1.0"}
    if method == "GET":
        headers["Range"] = "bytes=0-0"
    request = Request(url, method=method, headers=headers)
    with urlopen(request, timeout=EXTERNAL_TIMEOUT_SECONDS) as response:
        return int(getattr(response, "status", 200))


def _check_external(url: str) -> str | None:
    last_reason = "unknown transport failure"

    for attempt in range(EXTERNAL_ATTEMPTS):
        method = "GET" if attempt == EXTERNAL_ATTEMPTS - 1 else "HEAD"
        try:
            status = _request_external(url, method)
            if status < 400 or status in ACCEPTED_EXTERNAL_STATUSES:
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
            return f"invalid URL: {' '.join(str(exc).split())}"
        except (URLError, http.client.HTTPException, OSError) as exc:
            last_reason = _transport_reason(exc)

        if attempt < EXTERNAL_ATTEMPTS - 1:
            time.sleep(RETRY_BACKOFF_SECONDS[attempt])

    return f"{last_reason} after {EXTERNAL_ATTEMPTS} attempts"


def _check_internal(source: Path, link: str) -> str | None:
    target = link.split("#", 1)[0]
    if not target:
        return None
    resolved = (source.parent / target).resolve()
    try:
        resolved.relative_to(ROOT)
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
        scope_error = str(exc)

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

    if failures or scope_error is not None:
        print(json.dumps(report, indent=2, sort_keys=True))
        print(f"Report: {output_path}")
        return 1

    print(
        "Link validation passed: "
        f"{counts['links']} links across {counts['files']} markdown files "
        f"({counts['internal']} internal, {counts['external']} external)."
    )
    print(f"Report: {output_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
