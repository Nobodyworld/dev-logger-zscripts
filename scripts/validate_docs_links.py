"""Validate markdown links across repository documentation.

Checks:
- Internal relative links resolve to existing files.
- Internal anchor links reference existing files (anchor existence is not validated).
- External http/https links return an acceptable response.

Accepted external status codes: 2xx, 3xx, 401, 403, 405, 429.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
IGNORE_PARTS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "artifacts",
    "src/zscripts.egg-info",
}
LINK_RE = re.compile(r"\[[^\]]+\]\(([^)]+)\)")


@dataclass
class LinkFailure:
    source: str
    link: str
    reason: str


def _is_ignored(path: Path) -> bool:
    text = str(path).replace("\\", "/")
    return any(part in text for part in IGNORE_PARTS)


def _iter_markdown_files() -> list[Path]:
    return sorted(path for path in ROOT.rglob("*.md") if not _is_ignored(path.relative_to(ROOT)))


def _normalize_link(raw: str) -> str:
    link = raw.strip().strip("<>")
    if " " in link and not link.startswith(("http://", "https://")):
        # Common markdown pattern: path with optional title -> keep only path part.
        link = link.split(" ", 1)[0]
    return link


def _check_external(url: str) -> str | None:
    request = Request(url, method="HEAD", headers={"User-Agent": "zscripts-link-check/1.0"})
    try:
        with urlopen(request, timeout=10) as response:
            status = getattr(response, "status", 200)
            if status < 400 or status in {401, 403, 405, 429}:
                return None
            return f"HTTP {status}"
    except HTTPError as exc:
        if exc.code in {401, 403, 405, 429}:
            return None
        return f"HTTP {exc.code}"
    except URLError as exc:
        return str(exc.reason)


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

    for file_path in _iter_markdown_files():
        counts["files"] += 1
        text = file_path.read_text(encoding="utf-8", errors="replace")
        for raw_link in LINK_RE.findall(text):
            link = _normalize_link(raw_link)
            if not link or link.startswith(("mailto:", "#")):
                continue
            counts["links"] += 1
            rel_source = str(file_path.relative_to(ROOT)).replace("\\", "/")
            if link.startswith(("http://", "https://")):
                counts["external"] += 1
                reason = _check_external(link)
                if reason:
                    failures.append(LinkFailure(source=rel_source, link=link, reason=reason))
                continue
            counts["internal"] += 1
            reason = _check_internal(file_path, link)
            if reason:
                failures.append(LinkFailure(source=rel_source, link=link, reason=reason))

    return failures, counts


def main() -> int:
    failures, counts = validate_links()
    report = {
        "files_scanned": counts["files"],
        "links_scanned": counts["links"],
        "internal_links": counts["internal"],
        "external_links": counts["external"],
        "failures": [failure.__dict__ for failure in failures],
    }

    quality_dir = ROOT / "artifacts" / "quality"
    quality_dir.mkdir(parents=True, exist_ok=True)
    output_path = quality_dir / "link_validation.json"
    output_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    if failures:
        print(json.dumps(report, indent=2, sort_keys=True))
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
