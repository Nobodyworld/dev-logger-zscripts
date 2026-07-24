"""Read-only, bounded repository discovery for static Python analysis."""

from __future__ import annotations

import fnmatch
import hashlib
import os

# Git metadata is queried with a fixed executable and argument set.
import subprocess  # nosec B404
import tempfile
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from zscripts.domain.repository_review import (
    DiagnosticRecord,
    FileRecord,
    RepositoryRecord,
    ScanLimits,
    stable_digest,
)

DEFAULT_EXCLUDED_DIRECTORIES: tuple[str, ...] = (
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    "dist",
    "build",
    "coverage",
)
DEFAULT_SENSITIVE_PATTERNS: tuple[str, ...] = (
    ".env",
    ".env.*",
    "*.pem",
    "*.key",
    "credentials*",
    "secrets*",
)

CancellationCheck = Callable[[], bool]
ProgressCallback = Callable[[int, int, str], None]


class AnalysisCancelled(RuntimeError):
    """Raised when cooperative cancellation is requested between files."""


@dataclass(frozen=True, slots=True)
class DiscoveredFile:
    """A metadata record plus ephemeral bytes for an included Python file."""

    record: FileRecord
    content: bytes | None


@dataclass(frozen=True, slots=True)
class DiscoveryResult:
    """Repository metadata and sorted, bounded file discovery evidence."""

    repository: RepositoryRecord
    files: tuple[DiscoveredFile, ...]
    diagnostics: tuple[DiagnosticRecord, ...]
    source_fingerprint: str
    truncated: bool


class RepositoryDiscovery:
    """Discover files without importing source or executing repository commands."""

    def __init__(
        self,
        *,
        limits: ScanLimits | None = None,
        configured_excludes: Sequence[str] = (),
    ) -> None:
        self.limits = limits or ScanLimits()
        self.configured_excludes = tuple(
            sorted({item.strip() for item in configured_excludes if item.strip()})
        )
        self.configuration_digest = stable_digest(
            "repository-review-configuration",
            {
                "limits": {
                    "max_files": self.limits.max_files,
                    "max_file_size_bytes": self.limits.max_file_size_bytes,
                    "max_total_bytes": self.limits.max_total_bytes,
                    "max_source_lines": self.limits.max_source_lines,
                    "max_source_bytes": self.limits.max_source_bytes,
                },
                "default_directories": list(DEFAULT_EXCLUDED_DIRECTORIES),
                "default_sensitive_patterns": list(DEFAULT_SENSITIVE_PATTERNS),
                "configured_excludes": list(self.configured_excludes),
            },
        )

    def discover(
        self,
        repository_path: Path,
        *,
        cancelled: CancellationCheck | None = None,
        progress: ProgressCallback | None = None,
    ) -> DiscoveryResult:
        """Return deterministic discovery evidence for ``repository_path``."""

        cancellation = cancelled or (lambda: False)
        root = self._validate_root(repository_path)
        git_root = self._locate_git_root(root)
        analysis_root = git_root or root
        directory_diagnostics: tuple[DiagnosticRecord, ...] = ()
        if git_root is not None:
            candidates = self._git_candidates(analysis_root)
        else:
            candidates, directory_diagnostics = self._walk_candidates(analysis_root)
        candidates = tuple(sorted(set(candidates)))
        ignore_patterns = self._load_gitignore_patterns(analysis_root) if git_root is None else ()

        discovered: list[DiscoveredFile] = []
        diagnostics: list[DiagnosticRecord] = list(directory_diagnostics)
        included_count = 0
        included_bytes = 0
        truncated = False

        for index, relative in enumerate(candidates, start=1):
            self._raise_if_cancelled(cancellation)
            if progress is not None:
                progress(index - 1, len(candidates), relative)
            absolute = analysis_root / PurePosixPath(relative)
            record, content, limit_truncated, diagnostic = self._inspect_candidate(
                analysis_root=analysis_root,
                absolute=absolute,
                relative=relative,
                ignore_patterns=ignore_patterns,
                included_count=included_count,
                included_bytes=included_bytes,
            )
            discovered.append(DiscoveredFile(record=record, content=content))
            if record.included:
                included_count += 1
                included_bytes += record.size_bytes
            if limit_truncated:
                truncated = True
            if diagnostic is not None:
                diagnostics.append(diagnostic)

        if progress is not None:
            progress(len(candidates), len(candidates), "")

        source_roots, test_roots = self._identify_roots(discovered)
        repository = self._repository_record(
            analysis_root,
            git_root=git_root,
            source_roots=source_roots,
            test_roots=test_roots,
        )
        source_fingerprint = stable_digest(
            "repository-review-source",
            [
                {
                    "path": item.record.relative_path,
                    "hash": item.record.content_hash,
                    "size": item.record.size_bytes,
                    "included": item.record.included,
                    "reason": item.record.exclusion_reason,
                }
                for item in discovered
            ],
        )
        return DiscoveryResult(
            repository=repository,
            files=tuple(discovered),
            diagnostics=tuple(sorted(diagnostics, key=lambda item: item.diagnostic_id)),
            source_fingerprint=source_fingerprint,
            truncated=truncated,
        )

    @staticmethod
    def _validate_root(repository_path: Path) -> Path:
        try:
            root = repository_path.expanduser().resolve(strict=True)
        except (OSError, RuntimeError) as exc:
            raise ValueError("Repository path does not exist or cannot be resolved.") from exc
        if not root.is_dir():
            raise ValueError("Repository path must identify a directory.")
        return root

    @staticmethod
    def _locate_git_root(root: Path) -> Path | None:
        for candidate in (root, *root.parents):
            marker = candidate / ".git"
            if marker.is_dir() or marker.is_file():
                return candidate
        return None

    def _git_candidates(self, root: Path) -> tuple[str, ...]:
        payload = self._run_git(
            root,
            "ls-files",
            "--cached",
            "--others",
            "--exclude-standard",
            "-z",
        )
        return tuple(
            self._normalize_relative(item)
            for item in payload.split("\0")
            if item and self._is_safe_relative(item)
        )

    def _walk_candidates(
        self,
        root: Path,
    ) -> tuple[tuple[str, ...], tuple[DiagnosticRecord, ...]]:
        candidates: list[str] = []
        diagnostics: list[DiagnosticRecord] = []
        for directory, dirnames, filenames in os.walk(root, followlinks=False):
            directory_path = Path(directory)
            safe_directories: list[str] = []
            for name in sorted(dirnames):
                candidate = directory_path / name
                relative = self._relative_posix(root, candidate)
                if name in DEFAULT_EXCLUDED_DIRECTORIES:
                    diagnostics.append(
                        self._diagnostic(
                            "DISCOVERY_DIRECTORY_EXCLUDED",
                            "A generated, cached, or repository-internal directory was excluded.",
                            relative,
                            "exclusion",
                        )
                    )
                    continue
                if self._matches_configured_exclude(relative):
                    diagnostics.append(
                        self._diagnostic(
                            "DISCOVERY_DIRECTORY_CONFIGURED_EXCLUDE",
                            "A directory matched a configured exclusion.",
                            relative,
                            "exclusion",
                        )
                    )
                    continue
                if candidate.is_symlink():
                    diagnostics.append(
                        self._diagnostic(
                            "DISCOVERY_DIRECTORY_SYMLINK",
                            "A directory symlink was excluded.",
                            relative,
                            "exclusion",
                        )
                    )
                    continue
                safe_directories.append(name)
            dirnames[:] = safe_directories
            for filename in sorted(filenames):
                candidate = directory_path / filename
                candidates.append(self._relative_posix(root, candidate))
        return (
            tuple(candidates),
            tuple(sorted(diagnostics, key=lambda item: item.diagnostic_id)),
        )

    def _inspect_candidate(
        self,
        *,
        analysis_root: Path,
        absolute: Path,
        relative: str,
        ignore_patterns: Sequence[str],
        included_count: int,
        included_bytes: int,
    ) -> tuple[FileRecord, bytes | None, bool, DiagnosticRecord | None]:
        reason = self._pre_read_exclusion(
            analysis_root=analysis_root,
            absolute=absolute,
            relative=relative,
            ignore_patterns=ignore_patterns,
        )
        try:
            size = absolute.lstat().st_size
        except OSError:
            return (
                self._excluded(relative, 0, "unreadable"),
                None,
                False,
                self._diagnostic(
                    "DISCOVERY_UNREADABLE",
                    "A repository file could not be read.",
                    relative,
                    "exclusion",
                ),
            )
        if reason is not None:
            safe_relative = self._safe_excluded_path(relative, reason)
            return self._excluded(safe_relative, size, reason), None, False, None
        if size > self.limits.max_file_size_bytes:
            return (
                self._excluded(relative, size, "file_size_limit"),
                None,
                True,
                self._diagnostic(
                    "RESOURCE_FILE_SIZE_LIMIT",
                    "A repository file exceeded the configured size limit.",
                    relative,
                    "truncation",
                ),
            )
        if included_count >= self.limits.max_files:
            return (
                self._excluded(relative, size, "file_count_limit"),
                None,
                True,
                self._diagnostic(
                    "RESOURCE_FILE_COUNT_LIMIT",
                    "The configured file-count limit was reached.",
                    None,
                    "truncation",
                ),
            )
        if included_bytes + size > self.limits.max_total_bytes:
            return (
                self._excluded(relative, size, "total_byte_limit"),
                None,
                True,
                self._diagnostic(
                    "RESOURCE_TOTAL_BYTE_LIMIT",
                    "The configured total-byte limit was reached.",
                    None,
                    "truncation",
                ),
            )
        try:
            content = absolute.read_bytes()
        except OSError:
            return (
                self._excluded(relative, size, "unreadable"),
                None,
                False,
                self._diagnostic(
                    "DISCOVERY_UNREADABLE",
                    "A repository file could not be read.",
                    relative,
                    "exclusion",
                ),
            )
        if self._is_binary(content):
            return self._excluded(relative, size, "binary"), None, False, None
        content_hash = hashlib.sha256(content).hexdigest()
        file_id = stable_digest(
            "repository-review-file",
            {"path": relative, "content_hash": content_hash},
        )
        return (
            FileRecord(
                file_id=file_id,
                relative_path=relative,
                content_hash=content_hash,
                language="python",
                size_bytes=size,
                included=True,
                exclusion_reason=None,
                parse_status="pending",
            ),
            content,
            False,
            None,
        )

    def _pre_read_exclusion(
        self,
        *,
        analysis_root: Path,
        absolute: Path,
        relative: str,
        ignore_patterns: Sequence[str],
    ) -> str | None:
        name = PurePosixPath(relative).name
        if self._matches_sensitive(name):
            return "sensitive"
        if any(part in DEFAULT_EXCLUDED_DIRECTORIES for part in PurePosixPath(relative).parts):
            return "generated_or_cached"
        if self._matches_configured_exclude(relative):
            return "configured"
        if self._matches_gitignore(relative, ignore_patterns):
            return "gitignored"
        if absolute.is_symlink():
            try:
                resolved = absolute.resolve(strict=True)
            except (OSError, RuntimeError):
                return "symlink_unresolved"
            if not resolved.is_relative_to(analysis_root):
                return "symlink_escape"
            return "symlink"
        if absolute.suffix.lower() != ".py":
            return "unsupported_language"
        if not absolute.is_file():
            return "not_regular_file"
        return None

    def _repository_record(
        self,
        root: Path,
        *,
        git_root: Path | None,
        source_roots: tuple[str, ...],
        test_roots: tuple[str, ...],
    ) -> RepositoryRecord:
        branch: str | None = None
        git_sha: str | None = None
        dirty = False
        staged = False
        untracked = False
        identity_material: object = {"kind": "directory", "name": root.name.casefold()}
        if git_root is not None:
            branch = self._optional_git(git_root, "branch", "--show-current") or None
            git_sha = self._optional_git(git_root, "rev-parse", "HEAD") or None
            status = self._optional_git(
                git_root,
                "status",
                "--porcelain=v1",
                "-z",
                "--untracked-files=normal",
            )
            entries = tuple(item for item in status.split("\0") if item)
            dirty = bool(entries)
            staged = any(len(item) >= 2 and item[0] not in {" ", "?"} for item in entries)
            untracked = any(item.startswith("??") for item in entries)
            remote = self._optional_git(git_root, "config", "--get", "remote.origin.url")
            first_commit = self._optional_git(
                git_root,
                "rev-list",
                "--max-parents=0",
                "--reverse",
                "HEAD",
            ).splitlines()
            identity_material = {
                "kind": "git",
                "name": root.name.casefold(),
                "remote_digest": hashlib.sha256(remote.encode("utf-8")).hexdigest() if remote else None,
                "first_commit": first_commit[0] if first_commit else None,
            }
        repository_id = stable_digest("repository-review-repository", identity_material)
        return RepositoryRecord(
            repository_id=repository_id,
            display_name=root.name,
            canonical_path=str(root),
            git_root=str(git_root) if git_root is not None else None,
            branch=branch,
            git_sha=git_sha,
            dirty=dirty,
            staged=staged,
            untracked=untracked,
            configuration_digest=self.configuration_digest,
            source_roots=source_roots,
            test_roots=test_roots,
        )

    @staticmethod
    def _identify_roots(files: Sequence[DiscoveredFile]) -> tuple[tuple[str, ...], tuple[str, ...]]:
        included_paths = [PurePosixPath(item.record.relative_path) for item in files if item.record.included]
        source_roots: set[str] = set()
        test_roots: set[str] = set()
        for path in included_paths:
            if path.parts and path.parts[0] in {"tests", "test"}:
                test_roots.add(path.parts[0])
                continue
            if path.parts and path.parts[0] in {"src", "lib"}:
                source_roots.add(path.parts[0])
                continue
            source_roots.add(".")
        return tuple(sorted(source_roots)), tuple(sorted(test_roots))

    @staticmethod
    def _load_gitignore_patterns(root: Path) -> tuple[str, ...]:
        ignore_file = root / ".gitignore"
        try:
            content = ignore_file.read_bytes()[:65_536].decode("utf-8", errors="replace")
        except OSError:
            return ()
        return tuple(
            line.strip()
            for line in content.splitlines()
            if line.strip() and not line.lstrip().startswith("#") and not line.startswith("!")
        )

    @staticmethod
    def _matches_gitignore(relative: str, patterns: Sequence[str]) -> bool:
        path = PurePosixPath(relative)
        for raw_pattern in patterns:
            pattern = raw_pattern.replace("\\", "/").lstrip("/")
            if pattern.endswith("/"):
                directory = pattern.rstrip("/")
                if directory in path.parts:
                    return True
            if "/" in pattern:
                if fnmatch.fnmatchcase(relative, pattern):
                    return True
            elif any(fnmatch.fnmatchcase(part, pattern) for part in path.parts):
                return True
        return False

    def _matches_configured_exclude(self, relative: str) -> bool:
        return any(
            fnmatch.fnmatchcase(relative, pattern)
            or fnmatch.fnmatchcase(PurePosixPath(relative).name, pattern)
            for pattern in self.configured_excludes
        )

    @staticmethod
    def _matches_sensitive(name: str) -> bool:
        folded = name.casefold()
        return any(fnmatch.fnmatchcase(folded, pattern.casefold()) for pattern in DEFAULT_SENSITIVE_PATTERNS)

    @staticmethod
    def _is_binary(content: bytes) -> bool:
        sample = content[:8_192]
        if b"\0" in sample:
            return True
        if not sample:
            return False
        try:
            sample.decode("utf-8")
        except UnicodeDecodeError:
            return True
        return False

    @staticmethod
    def _excluded(relative: str, size: int, reason: str) -> FileRecord:
        return FileRecord(
            file_id=stable_digest(
                "repository-review-file",
                {"path": relative, "excluded": reason, "size": size},
            ),
            relative_path=relative,
            content_hash=None,
            language="python" if relative.lower().endswith(".py") else "other",
            size_bytes=size,
            included=False,
            exclusion_reason=reason,
            parse_status="not_parsed",
        )

    @staticmethod
    def _safe_excluded_path(relative: str, reason: str) -> str:
        if reason != "sensitive":
            return relative
        path_digest = hashlib.sha256(relative.encode("utf-8")).hexdigest()[:12]
        return f"[sensitive-file-{path_digest}]"

    @staticmethod
    def _diagnostic(
        code: str,
        message: str,
        relative_path: str | None,
        category: str,
    ) -> DiagnosticRecord:
        payload = {
            "code": code,
            "message": message,
            "path": relative_path,
            "category": category,
        }
        return DiagnosticRecord(
            diagnostic_id=stable_digest("repository-review-diagnostic", payload),
            code=code,
            severity="warning",
            message=message,
            relative_path=relative_path,
            line=None,
            column=None,
            category=category,
        )

    @staticmethod
    def _raise_if_cancelled(cancelled: CancellationCheck) -> None:
        if cancelled():
            raise AnalysisCancelled("Repository analysis was cancelled.")

    @staticmethod
    def _relative_posix(root: Path, path: Path) -> str:
        return path.relative_to(root).as_posix()

    @staticmethod
    def _normalize_relative(path: str) -> str:
        return PurePosixPath(path.replace("\\", "/")).as_posix()

    @staticmethod
    def _is_safe_relative(path: str) -> bool:
        pure = PurePosixPath(path.replace("\\", "/"))
        return not pure.is_absolute() and ".." not in pure.parts

    @classmethod
    def _run_git(cls, root: Path, *arguments: str) -> str:
        no_hooks = Path(tempfile.gettempdir()) / "zscripts-no-git-hooks"
        command = [
            "git",
            "--no-optional-locks",
            "-c",
            "core.fsmonitor=false",
            "-c",
            f"core.hooksPath={no_hooks}",
            "-C",
            str(root),
            *arguments,
        ]
        environment = os.environ.copy()
        environment.update(
            {
                "GIT_TERMINAL_PROMPT": "0",
                "GIT_CONFIG_NOSYSTEM": "1",
                "LC_ALL": "C",
            }
        )
        # Only fixed, allowlisted Git metadata commands reach this helper.
        result = subprocess.run(  # nosec B603
            command,
            check=False,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=15,
            env=environment,
        )
        if result.returncode:
            raise ValueError("Git metadata could not be read safely.")
        return result.stdout.rstrip("\r\n")

    @classmethod
    def _optional_git(cls, root: Path, *arguments: str) -> str:
        try:
            return cls._run_git(root, *arguments)
        except (OSError, subprocess.SubprocessError, ValueError):
            return ""


__all__ = [
    "AnalysisCancelled",
    "DEFAULT_EXCLUDED_DIRECTORIES",
    "DEFAULT_SENSITIVE_PATTERNS",
    "DiscoveredFile",
    "DiscoveryResult",
    "RepositoryDiscovery",
]
