from __future__ import annotations

import hashlib
import os
import shutil
import socket
import subprocess
import sys
import urllib.request
from collections.abc import Sequence
from pathlib import Path
from typing import NoReturn

import pytest

from zscripts.application.repository_review import RepositoryReviewService
from zscripts.domain.repository_review import AnalysisState
from zscripts.infrastructure.python_analyzer import PythonAnalysisResult, PythonAnalyzer
from zscripts.infrastructure.repository_discovery import AnalysisCancelled, DiscoveredFile
from zscripts.infrastructure.snapshot_store import SnapshotStore

FIXTURES = Path(__file__).parents[1] / "fixtures" / "repository_review"


def _raise_execution(*_args: object, **_kwargs: object) -> NoReturn:
    raise AssertionError("Repository code attempted to execute during static analysis.")


def test_malicious_import_time_code_is_never_executed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    repository = tmp_path / "malicious"
    shutil.copytree(FIXTURES / "malicious", repository)
    literal_secret = "literal-default-must-not-appear"  # pragma: allowlist secret
    (repository / "literal_default.py").write_text(
        f'def configured(token: str = "{literal_secret}") -> str:\n    return token\n',
        encoding="utf-8",
    )
    before = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in repository.glob("*.py")}
    marker = repository / "ZSCRIPT_ANALYZER_MUST_NOT_CREATE"
    secret = "must-not-appear-in-evidence"  # pragma: allowlist secret
    monkeypatch.chdir(repository)
    monkeypatch.setenv("ZSCRIPT_ANALYZER_SECRET", secret)
    monkeypatch.setattr(os, "system", _raise_execution)
    monkeypatch.setattr(subprocess, "run", _raise_execution)
    monkeypatch.setattr(socket, "create_connection", _raise_execution)
    monkeypatch.setattr(urllib.request, "urlopen", _raise_execution)
    sys.modules.pop("django", None)

    evidence = RepositoryReviewService(data_directory=tmp_path / "data").analyze(repository)

    after = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in repository.glob("*.py")}
    assert marker.exists() is False
    assert before == after
    assert secret.encode() not in evidence.canonical_bytes()
    assert literal_secret.encode() not in evidence.canonical_bytes()
    assert any("<string>" in item.signature for item in evidence.symbols)
    assert "django" not in sys.modules
    assert any(item.qualified_name == "effects.public_function" for item in evidence.symbols)
    assert evidence.snapshot.parse_gap_count == 1


class _CancellingAnalyzer(PythonAnalyzer):
    def analyze(
        self,
        files: Sequence[DiscoveredFile],
        *,
        cancelled: object = None,
        progress: object = None,
    ) -> PythonAnalysisResult:
        del files, cancelled, progress
        raise AnalysisCancelled("cancelled during parsing")


def test_cancelled_analysis_never_promotes_partial_snapshot(tmp_path: Path) -> None:
    repository = tmp_path / "ordinary"
    shutil.copytree(FIXTURES / "ordinary", repository)
    store = SnapshotStore(tmp_path / "data")
    analysis_id = store.allocate_analysis_id()
    service = RepositoryReviewService(store=store, analyzer=_CancellingAnalyzer())

    with pytest.raises(AnalysisCancelled):
        service.analyze(repository, analysis_id=analysis_id)

    status = store.get_analysis(analysis_id)
    assert status is not None
    assert status.state is AnalysisState.CANCELLED
    assert status.snapshot_id is None
    assert store.list_snapshots(status.repository_id) == ()
