from pathlib import Path
from typing import Any, Callable

import pytest

from zscripts.application.io_utils import (
    OutputPathError,
    atomic_write_bytes,
    atomic_write_text,
    atomic_write_text_stream,
    prepare_output_path,
)


def test_prepare_output_path_creates_parents(tmp_path: Path) -> None:
    target = tmp_path / "nested" / "report.txt"
    resolved = prepare_output_path(target)
    assert resolved == target.resolve()
    assert (tmp_path / "nested").is_dir()


def test_prepare_output_path_rejects_directory(tmp_path: Path) -> None:
    directory = tmp_path / "reports"
    directory.mkdir()

    with pytest.raises(OutputPathError) as excinfo:
        prepare_output_path(directory)

    assert "is a directory" in str(excinfo.value)


def test_prepare_output_path_detects_unwritable_parent(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    directory = tmp_path / "protected"
    directory.mkdir()

    monkeypatch.setattr(
        "zscripts.application.io_utils.os.access",
        lambda path, mode: False,
    )

    with pytest.raises(OutputPathError) as excinfo:
        prepare_output_path(directory / "report.txt")

    message = str(excinfo.value)
    assert "not writable" in message
    assert str(directory) in message


def test_prepare_output_path_resolution_fallback(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    target = tmp_path / "reports" / "summary.txt"
    original_resolve = Path.resolve

    def _resolve(self: Path, strict: bool = False) -> Path:  # type: ignore[override]
        if self == target:
            raise OSError("failed to resolve")
        return original_resolve(self, strict=strict)

    monkeypatch.setattr(Path, "resolve", _resolve)

    resolved = prepare_output_path(target)

    assert resolved == target
    assert target.parent.is_dir()


def test_prepare_output_path_reports_parent_creation_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    target = tmp_path / "nested" / "report.txt"
    parent = target.parent
    original_mkdir = Path.mkdir

    def _mkdir(self: Path, *args, **kwargs):  # type: ignore[no-untyped-def]
        if self == parent:
            raise OSError("mkdir blocked")
        return original_mkdir(self, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", _mkdir)

    with pytest.raises(OutputPathError) as excinfo:
        prepare_output_path(target)

    assert "unable to create parent directory" in str(excinfo.value)
    assert excinfo.value.cause is not None


def test_prepare_output_path_parent_not_directory(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    parent = tmp_path / "artifact"
    parent.write_text("file", encoding="utf-8")
    target = parent / "report.txt"
    original_mkdir = Path.mkdir
    original_is_dir = Path.is_dir

    def _mkdir(self: Path, *args, **kwargs):  # type: ignore[no-untyped-def]
        if self == parent:
            return None
        return original_mkdir(self, *args, **kwargs)

    def _is_dir(self: Path) -> bool:  # type: ignore[override]
        if self == parent:
            return False
        return original_is_dir(self)

    monkeypatch.setattr(Path, "mkdir", _mkdir)
    monkeypatch.setattr(Path, "is_dir", _is_dir)

    with pytest.raises(OutputPathError) as excinfo:
        prepare_output_path(target)

    assert "is not a directory" in str(excinfo.value)


Writer = Callable[[Path, Any], None]
Reader = Callable[[Path], Any]


@pytest.mark.parametrize(
    ("writer", "prepare_existing", "reader", "payload"),
    [
        (
            atomic_write_text,
            lambda destination: destination.write_text("old", encoding="utf-8"),
            lambda destination: destination.read_text(encoding="utf-8"),
            "new contents",
        ),
        (
            atomic_write_bytes,
            lambda destination: destination.write_bytes(b"old"),
            lambda destination: destination.read_bytes(),
            b"\x00\x01payload",
        ),
    ],
)
def test_atomic_write_replaces_atomically(
    tmp_path: Path,
    writer: Writer,
    prepare_existing: Callable[[Path], None],
    reader: Reader,
    payload: Any,
) -> None:
    destination = tmp_path / "report.bin"
    prepare_existing(destination)

    writer(destination, payload)

    assert reader(destination) == payload
    entries = list(tmp_path.iterdir())
    assert entries == [destination]


@pytest.mark.parametrize(
    ("writer", "payload"),
    [
        (atomic_write_text, "payload"),
        (atomic_write_bytes, b"payload"),
    ],
)
def test_atomic_write_raises_on_permission_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, writer: Writer, payload: Any
) -> None:
    destination = tmp_path / "report.txt"

    def _raise_permission_error(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise PermissionError("blocked")

    monkeypatch.setattr(
        "zscripts.application.io_utils.tempfile.NamedTemporaryFile",
        _raise_permission_error,
    )

    with pytest.raises(OutputPathError) as excinfo:
        writer(destination, payload)

    assert "unable to write" in str(excinfo.value)


@pytest.mark.parametrize(
    ("writer", "payload"),
    [
        (atomic_write_text, "payload"),
        (atomic_write_bytes, b"payload"),
    ],
)
def test_atomic_write_handles_cleanup_failures(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    writer: Writer,
    payload: Any,
) -> None:
    destination = tmp_path / "report.txt"
    captured: dict[str, Path] = {}

    def _replace(src: str, dst: str) -> None:
        captured["temp"] = Path(src)
        raise OSError("replace failed")

    original_unlink = Path.unlink

    def _unlink(self: Path, *args, **kwargs):  # type: ignore[no-untyped-def]
        temp = captured.get("temp")
        if temp and self == temp:
            raise OSError("cleanup failed")
        return original_unlink(self, *args, **kwargs)

    monkeypatch.setattr("zscripts.application.io_utils.os.replace", _replace)
    monkeypatch.setattr(Path, "unlink", _unlink)

    with pytest.raises(OutputPathError) as excinfo:
        writer(destination, payload)

    assert "unable to write" in str(excinfo.value)
    temp_path = captured["temp"]
    assert temp_path.exists()
    original_unlink(temp_path)


def test_atomic_write_text_stream(tmp_path: Path) -> None:
    destination = tmp_path / "streamed.txt"

    def _writer(handle: Any) -> None:
        handle.write("stream")
        handle.write("ed")

    atomic_write_text_stream(destination, _writer)

    assert destination.read_text(encoding="utf-8") == "streamed"
