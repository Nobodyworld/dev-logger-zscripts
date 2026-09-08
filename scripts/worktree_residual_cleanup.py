"""Inventory and remove an explicitly approved residual Git worktree directory.

Inventory is read-only. Apply is intentionally fail-closed: it requires an exact
reviewed manifest, verifies preservation and worktree registration, rechecks
raw file/link content immediately before removal, and never uses recursive or
forced deletion.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import string
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Iterable

SCHEMA_VERSION = 1
HASH_CHUNK_SIZE = 1024 * 1024
DEFAULT_MAX_ENTRIES = 200_000
DEFAULT_MAX_FILE_BYTES = 1024 * 1024 * 1024


class CleanupError(RuntimeError):
    """A residual-cleanup safety gate failed."""


@dataclass(frozen=True, slots=True)
class EntryRecord:
    path: str
    kind: str
    size: int | None = None
    sha256: str | None = None
    target_sha256: str | None = None


def _canonical(path: str | os.PathLike[str]) -> str:
    return os.path.normcase(os.path.abspath(os.fspath(path)))


def _native_path(path: str) -> str:
    """Use Windows extended-length syntax without changing non-Windows paths."""
    if os.name != "nt":
        return path
    absolute = os.path.abspath(path)
    if absolute.startswith("\\\\?\\"):
        return absolute
    if absolute.startswith("\\\\"):
        return "\\\\?\\UNC\\" + absolute[2:]
    return "\\\\?\\" + absolute


def _is_reparse(st: os.stat_result) -> bool:
    if stat.S_ISLNK(st.st_mode):
        return True
    attributes = getattr(st, "st_file_attributes", 0)
    flag = getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    return bool(attributes & flag)


def _is_directory_reparse(st: os.stat_result) -> bool:
    if os.name != "nt":
        return False
    attributes = getattr(st, "st_file_attributes", 0)
    flag = getattr(stat, "FILE_ATTRIBUTE_DIRECTORY", 0x10)
    return bool(attributes & flag)


def _relative_parts(relative: str) -> tuple[str, ...]:
    if not relative or "\\" in relative:
        raise CleanupError(f"Invalid manifest path: {relative!r}")
    parsed = PurePosixPath(relative)
    if parsed.is_absolute() or any(part in {"", ".", ".."} for part in parsed.parts):
        raise CleanupError(f"Invalid manifest path: {relative!r}")
    return parsed.parts


def _paths_overlap(first: str, second: str) -> bool:
    try:
        common = os.path.commonpath([first, second])
    except ValueError:
        return False
    return common in {first, second}


def _assert_no_overlap(root: str, owned_parent: str, protected_roots: Iterable[str]) -> None:
    target = _canonical(root)
    parent = _canonical(owned_parent)
    try:
        common = os.path.commonpath([target, parent])
    except ValueError as exc:
        raise CleanupError("Residual root and owned parent are on incompatible volumes") from exc
    if common != parent or target == parent:
        raise CleanupError("Residual root must be a strict descendant of --owned-parent")

    target_real = _canonical(os.path.realpath(root))
    for protected in protected_roots:
        candidate = _canonical(protected)
        candidate_real = _canonical(os.path.realpath(protected))
        if _paths_overlap(target, candidate) or _paths_overlap(target_real, candidate_real):
            raise CleanupError(f"Residual root overlaps a protected root: {protected!r}")


def _assert_plain_root(root: str) -> None:
    try:
        st = os.stat(_native_path(root), follow_symlinks=False)
    except FileNotFoundError:
        return
    if _is_reparse(st):
        raise CleanupError("Residual root itself must not be a link/reparse point")
    if not stat.S_ISDIR(st.st_mode):
        raise CleanupError("Residual root must be a directory")


def _assert_plain_owned_chain(root: str, owned_parent: str) -> None:
    """Reject a reparse point anywhere from the owned parent through the root."""
    parent = os.path.abspath(owned_parent)
    target = os.path.abspath(root)
    try:
        parent_stat = os.stat(_native_path(parent), follow_symlinks=False)
    except OSError as exc:
        raise CleanupError(f"Owned parent is unavailable: {owned_parent!r}: {exc}") from exc
    if _is_reparse(parent_stat) or not stat.S_ISDIR(parent_stat.st_mode):
        raise CleanupError("Owned parent must be a plain directory, not a link/reparse point")

    relative = os.path.relpath(target, parent)
    parts = tuple(part for part in relative.split(os.sep) if part not in {"", "."})
    if any(part == ".." for part in parts):
        raise CleanupError("Residual root escaped the owned parent")

    current = parent
    for part in parts:
        current = os.path.join(current, part)
        try:
            current_stat = os.stat(_native_path(current), follow_symlinks=False)
        except FileNotFoundError:
            return
        except OSError as exc:
            raise CleanupError(f"Owned path chain is unavailable: {current!r}: {exc}") from exc
        if _is_reparse(current_stat) or not stat.S_ISDIR(current_stat.st_mode):
            raise CleanupError(f"Owned path chain contains a link/reparse point: {current!r}")


def _assert_plain_directory_chain(root: str, parts: tuple[str, ...]) -> None:
    """Reject a parent component that became a link or reparse point."""
    _assert_plain_root(root)
    current = root
    for part in parts:
        current = os.path.join(current, part)
        try:
            st = os.stat(_native_path(current), follow_symlinks=False)
        except OSError as exc:
            relative = PurePosixPath(*parts).as_posix()
            raise CleanupError(f"Directory chain changed before access: {relative!r}: {exc}") from exc
        if _is_reparse(st) or not stat.S_ISDIR(st.st_mode):
            relative = PurePosixPath(*parts).as_posix()
            raise CleanupError(f"Directory chain is no longer plain: {relative!r}")


def _hash_file(path: str, *, max_file_bytes: int) -> tuple[int, str]:
    digest = hashlib.sha256()
    size = 0
    with open(_native_path(path), "rb") as stream:
        while chunk := stream.read(HASH_CHUNK_SIZE):
            size += len(chunk)
            if size > max_file_bytes:
                raise CleanupError(f"File exceeds max_file_bytes: {path!r}")
            digest.update(chunk)
    return size, digest.hexdigest()


def _hash_link_target(path: str) -> str:
    try:
        target = os.readlink(_native_path(path))
    except OSError as exc:
        raise CleanupError(f"Unable to read link/reparse target: {path!r}: {exc}") from exc
    return hashlib.sha256(os.fsencode(target)).hexdigest()


def scan_entries(
    root: str,
    *,
    max_entries: int = DEFAULT_MAX_ENTRIES,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
) -> list[EntryRecord]:
    """Return an exact, non-mutating inventory without following links."""
    _assert_plain_root(root)
    if not os.path.exists(_native_path(root)):
        return []

    records: list[EntryRecord] = []
    stack: list[tuple[str, tuple[str, ...]]] = [(root, ())]
    while stack:
        directory, relative_parts = stack.pop()
        _assert_plain_directory_chain(root, relative_parts)
        try:
            with os.scandir(_native_path(directory)) as iterator:
                children = sorted(iterator, key=lambda item: item.name)
        except OSError as exc:
            raise CleanupError(f"Unable to enumerate directory: {directory!r}: {exc}") from exc

        pending: list[tuple[str, tuple[str, ...]]] = []
        for child in children:
            if len(records) >= max_entries:
                raise CleanupError("Inventory exceeds max_entries")
            child_path = os.path.join(directory, child.name)
            parts = (*relative_parts, child.name)
            relative = PurePosixPath(*parts).as_posix()
            try:
                st = os.stat(_native_path(child_path), follow_symlinks=False)
            except OSError as exc:
                raise CleanupError(f"Unable to inspect entry: {relative!r}: {exc}") from exc

            if _is_reparse(st):
                records.append(
                    EntryRecord(
                        path=relative,
                        kind="reparse",
                        target_sha256=_hash_link_target(child_path),
                    )
                )
            elif stat.S_ISDIR(st.st_mode):
                records.append(EntryRecord(path=relative, kind="directory"))
                pending.append((child_path, parts))
            elif stat.S_ISREG(st.st_mode):
                size, digest = _hash_file(child_path, max_file_bytes=max_file_bytes)
                records.append(EntryRecord(path=relative, kind="file", size=size, sha256=digest))
            else:
                records.append(EntryRecord(path=relative, kind="unsupported"))
        stack.extend(reversed(pending))

    return sorted(records, key=lambda item: item.path.encode("utf-8", "surrogatepass"))


def _run_git(repo: str, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", repo, *arguments],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode:
        detail = result.stderr.strip() or result.stdout.strip() or "git command failed"
        raise CleanupError(detail)
    return result.stdout


def registered_worktrees(repo: str) -> set[str]:
    output = _run_git(repo, "worktree", "list", "--porcelain", "-z")
    return {
        _canonical(record.removeprefix("worktree "))
        for record in output.split("\0")
        if record.startswith("worktree ")
    }


def build_inventory(
    root: str,
    *,
    repo: str,
    owned_parent: str,
    protected_roots: Iterable[str] = (),
    max_entries: int = DEFAULT_MAX_ENTRIES,
    max_file_bytes: int = DEFAULT_MAX_FILE_BYTES,
) -> dict[str, Any]:
    """Build the read-only review artifact. It is never approved automatically."""
    protected = [os.path.abspath(path) for path in protected_roots]
    _assert_no_overlap(root, owned_parent, protected)
    _assert_plain_owned_chain(root, owned_parent)
    _assert_plain_root(root)
    exists = os.path.exists(_native_path(root))
    entries = scan_entries(root, max_entries=max_entries, max_file_bytes=max_file_bytes) if exists else []
    return {
        "schema_version": SCHEMA_VERSION,
        "root": os.path.abspath(root),
        "owned_parent": os.path.abspath(owned_parent),
        "repo": os.path.abspath(repo),
        "protected_roots": protected,
        "exists": exists,
        "registered_worktree": _canonical(root) in registered_worktrees(repo),
        "limits": {"max_entries": max_entries, "max_file_bytes": max_file_bytes},
        "entries": [asdict(entry) for entry in entries],
        "approval": {
            "approved": False,
            "created_by_current_slice": False,
            "inactive_confirmed": False,
            "note": "",
        },
        "preservation": {"ref": "", "head": ""},
    }


def _load_manifest(path: str) -> dict[str, Any]:
    try:
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CleanupError(f"Unable to read manifest: {exc}") from exc
    if not isinstance(payload, dict):
        raise CleanupError("Manifest root must be a JSON object")
    return payload


def _manifest_records(manifest: dict[str, Any]) -> list[EntryRecord]:
    if manifest.get("schema_version") != SCHEMA_VERSION:
        raise CleanupError("Unsupported manifest schema_version")
    values = manifest.get("entries")
    if not isinstance(values, list):
        raise CleanupError("Manifest entries must be a list")
    records: list[EntryRecord] = []
    allowed = {"path", "kind", "size", "sha256", "target_sha256"}
    for value in values:
        if not isinstance(value, dict) or set(value) - allowed:
            raise CleanupError("Manifest entry has an invalid shape")
        try:
            record = EntryRecord(**value)
        except TypeError as exc:
            raise CleanupError("Manifest entry has an invalid shape") from exc
        _relative_parts(record.path)
        if record.kind not in {"file", "directory", "reparse"}:
            raise CleanupError(f"Unsupported manifest kind: {record.kind!r}")
        records.append(record)
    if len({record.path for record in records}) != len(records):
        raise CleanupError("Manifest contains duplicate paths")
    return records


def _verify_approval(manifest: dict[str, Any]) -> None:
    approval = manifest.get("approval")
    if not isinstance(approval, dict):
        raise CleanupError("Manifest approval block is required")
    if approval.get("approved") is not True:
        raise CleanupError("Manifest has not been explicitly approved")
    if approval.get("created_by_current_slice") is not True:
        raise CleanupError("Current-slice ownership has not been confirmed")
    if approval.get("inactive_confirmed") is not True:
        raise CleanupError("Inactive-use status has not been confirmed")
    if not isinstance(approval.get("note"), str) or not approval["note"].strip():
        raise CleanupError("Manifest approval note is required")


def _verify_preservation(manifest: dict[str, Any]) -> None:
    repo = manifest.get("repo")
    preservation = manifest.get("preservation")
    if not isinstance(repo, str) or not repo or not isinstance(preservation, dict):
        raise CleanupError("Manifest repo and preservation block are required")
    ref = preservation.get("ref")
    expected = preservation.get("head")
    if (
        not isinstance(ref, str)
        or not ref
        or not isinstance(expected, str)
        or len(expected) != 40
        or any(character not in string.hexdigits for character in expected)
    ):
        raise CleanupError("Preservation ref and 40-character hexadecimal head are required")
    actual = _run_git(repo, "rev-parse", "--verify", f"{ref}^{{commit}}").strip()
    if actual != expected:
        raise CleanupError(f"Preservation ref mismatch: expected {expected}, found {actual}")


def _live_records(manifest: dict[str, Any]) -> list[EntryRecord]:
    limits = manifest.get("limits", {})
    if not isinstance(limits, dict):
        raise CleanupError("Manifest limits must be an object")
    max_entries = limits.get("max_entries", DEFAULT_MAX_ENTRIES)
    max_file_bytes = limits.get("max_file_bytes", DEFAULT_MAX_FILE_BYTES)
    if not isinstance(max_entries, int) or max_entries <= 0:
        raise CleanupError("Manifest max_entries must be a positive integer")
    if not isinstance(max_file_bytes, int) or max_file_bytes <= 0:
        raise CleanupError("Manifest max_file_bytes must be a positive integer")
    return scan_entries(str(manifest["root"]), max_entries=max_entries, max_file_bytes=max_file_bytes)


def _verify_apply_gates(manifest: dict[str, Any]) -> list[EntryRecord]:
    expected = _manifest_records(manifest)
    root = manifest.get("root")
    parent = manifest.get("owned_parent")
    repo = manifest.get("repo")
    protected = manifest.get("protected_roots", [])
    inventory_exists = manifest.get("exists")
    inventory_registered = manifest.get("registered_worktree")
    if not isinstance(root, str) or not root:
        raise CleanupError("Manifest root is required")
    if not isinstance(parent, str) or not parent:
        raise CleanupError("Manifest owned_parent is required")
    if not isinstance(repo, str) or not repo:
        raise CleanupError("Manifest repo is required")
    if not isinstance(protected, list) or not all(isinstance(path, str) for path in protected):
        raise CleanupError("Manifest protected_roots must be a list of paths")
    if not isinstance(inventory_exists, bool):
        raise CleanupError("Manifest exists field must be boolean")
    if inventory_registered is not False:
        raise CleanupError("Approved inventory must have been captured after worktree unregistration")
    if not inventory_exists and expected:
        raise CleanupError("An absent inventory cannot contain entries")

    _assert_no_overlap(root, parent, protected)
    _assert_plain_owned_chain(root, parent)
    _assert_plain_root(root)
    _verify_approval(manifest)
    _verify_preservation(manifest)
    if _canonical(root) in registered_worktrees(repo):
        raise CleanupError("Residual root is still registered as a Git worktree")

    live_exists = os.path.exists(_native_path(root))
    if not inventory_exists and live_exists:
        raise CleanupError("Residual root appeared after the approved absent inventory")
    if not live_exists:
        return expected
    if any(record.path == ".git" or record.path.startswith(".git/") for record in expected):
        raise CleanupError("Residual contains .git metadata; raw residual deletion is prohibited")
    if _live_records(manifest) != expected:
        raise CleanupError("Live residual contents do not exactly match the approved manifest")
    return expected


def _revalidate(root: str, expected: EntryRecord) -> tuple[os.stat_result, str]:
    parts = _relative_parts(expected.path)
    _assert_plain_directory_chain(root, parts[:-1])
    path = os.path.join(root, *parts)
    try:
        st = os.stat(_native_path(path), follow_symlinks=False)
    except OSError as exc:
        raise CleanupError(f"Entry changed before removal: {expected.path!r}: {exc}") from exc

    if expected.kind == "reparse":
        if not _is_reparse(st) or _hash_link_target(path) != expected.target_sha256:
            raise CleanupError(f"Reparse entry changed before removal: {expected.path!r}")
    elif expected.kind == "file":
        if _is_reparse(st) or not stat.S_ISREG(st.st_mode):
            raise CleanupError(f"File entry changed type before removal: {expected.path!r}")
        size, digest = _hash_file(path, max_file_bytes=max(DEFAULT_MAX_FILE_BYTES, expected.size or 0))
        if size != expected.size or digest != expected.sha256:
            raise CleanupError(f"File entry changed before removal: {expected.path!r}")
    elif expected.kind == "directory":
        if _is_reparse(st) or not stat.S_ISDIR(st.st_mode):
            raise CleanupError(f"Directory entry changed before removal: {expected.path!r}")
    return st, path


def _remove_reparse(path: str, st: os.stat_result) -> None:
    native = _native_path(path)
    if _is_directory_reparse(st):
        os.rmdir(native)
        return
    try:
        os.unlink(native)
    except IsADirectoryError:
        os.rmdir(native)
    except PermissionError:
        if os.name != "nt":
            raise
        os.rmdir(native)


def apply_manifest(manifest: dict[str, Any]) -> str:
    """Remove only entries in an exact approved manifest, then the empty root."""
    expected = _verify_apply_gates(manifest)
    root = str(manifest["root"])
    if not os.path.exists(_native_path(root)):
        return "already-absent"

    files_and_links = [record for record in expected if record.kind != "directory"]
    directories = [record for record in expected if record.kind == "directory"]

    for record in sorted(files_and_links, key=lambda item: item.path.count("/"), reverse=True):
        st, path = _revalidate(root, record)
        try:
            if record.kind == "reparse":
                _remove_reparse(path, st)
            else:
                os.unlink(_native_path(path))
        except OSError as exc:
            raise CleanupError(f"Removal stopped at {record.path!r}: {exc}") from exc

    for record in sorted(directories, key=lambda item: item.path.count("/"), reverse=True):
        _st, path = _revalidate(root, record)
        try:
            os.rmdir(_native_path(path))
        except OSError as exc:
            raise CleanupError(f"Removal stopped at {record.path!r}: {exc}") from exc

    try:
        os.rmdir(_native_path(root))
    except OSError as exc:
        raise CleanupError(f"Residual root was not empty after approved removals: {exc}") from exc
    return "removed"


def _write_json(payload: dict[str, Any], output: str | None) -> None:
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if output:
        Path(output).write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)

    inventory = subparsers.add_parser("inventory", help="write a read-only inventory")
    inventory.add_argument("root")
    inventory.add_argument("--repo", required=True)
    inventory.add_argument("--owned-parent", required=True)
    inventory.add_argument("--protected-root", action="append", default=[])
    inventory.add_argument("--output")
    inventory.add_argument("--max-entries", type=int, default=DEFAULT_MAX_ENTRIES)
    inventory.add_argument("--max-file-bytes", type=int, default=DEFAULT_MAX_FILE_BYTES)

    apply = subparsers.add_parser("apply", help="apply an exact reviewed manifest")
    apply.add_argument("manifest")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        if args.command == "inventory":
            payload = build_inventory(
                args.root,
                repo=args.repo,
                owned_parent=args.owned_parent,
                protected_roots=args.protected_root,
                max_entries=args.max_entries,
                max_file_bytes=args.max_file_bytes,
            )
            _write_json(payload, args.output)
            return 0
        manifest = _load_manifest(args.manifest)
        print(json.dumps({"status": apply_manifest(manifest)}, sort_keys=True))
        return 0
    except CleanupError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
