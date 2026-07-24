from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from zscripts import cli as cli_module
from zscripts.application.repository_review import RepositoryReviewService
from zscripts.interfaces.workspace_api import create_workspace_app, validate_workspace_host

FIXTURES = Path(__file__).parents[1] / "fixtures" / "repository_review"
TERMINAL_STATES = {"completed", "cancelled", "failed"}


def _wait_for_analysis(client: TestClient, analysis_id: str) -> dict[str, object]:
    for _ in range(300):
        response = client.get(f"/api/analyses/{analysis_id}")
        assert response.status_code == 200
        payload = response.json()
        if payload["state"] in TERMINAL_STATES:
            return payload
        time.sleep(0.01)
    raise AssertionError("Analysis did not reach a terminal state.")


def test_workspace_api_end_to_end_and_security_headers(tmp_path: Path) -> None:
    repository = tmp_path / "ordinary"
    shutil.copytree(FIXTURES / "ordinary", repository)
    service = RepositoryReviewService(data_directory=tmp_path / "data")
    app = create_workspace_app(service=service)

    with TestClient(app) as client:
        health = client.get("/api/health")
        assert health.status_code == 200
        assert health.headers["content-security-policy"].startswith("default-src 'self'")
        assert health.headers["x-frame-options"] == "DENY"
        notices = client.get("/THIRD_PARTY_NOTICES.md")
        assert notices.status_code == 200
        assert "Meta Platforms" in notices.text
        response = client.post(
            "/api/repositories/analyze",
            json={"repository_path": str(repository)},
        )
        assert response.status_code == 202
        job = _wait_for_analysis(client, response.json()["analysis_id"])
        assert job["state"] == "completed"
        snapshot_id = str(job["snapshot_id"])
        repository_id = str(job["repository_id"])

        repositories = client.get("/api/repositories").json()["repositories"]
        assert repositories[0]["repository_id"] == repository_id
        assert str(tmp_path) not in json.dumps(repositories)
        snapshots = client.get(f"/api/repositories/{repository_id}/snapshots").json()["snapshots"]
        assert snapshots[0]["snapshot_id"] == snapshot_id
        overview = client.get(f"/api/snapshots/{snapshot_id}/overview")
        assert overview.status_code == 200
        assert overview.json()["counts"]["modules"] == 2
        symbols = client.get(
            f"/api/snapshots/{snapshot_id}/symbols",
            params={"search": "method", "kind": "method", "sort": "line", "direction": "desc"},
        )
        assert symbols.status_code == 200
        assert symbols.json()["items"][0]["qualified_name"] == "pkg.module.Example.method"
        source = client.get(
            f"/api/snapshots/{snapshot_id}/source",
            params={"path": "pkg/module.py", "start_line": 1, "end_line": 10},
        )
        assert source.status_code == 200
        assert source.json()["relative_path"] == "pkg/module.py"
        traversal = client.get(
            f"/api/snapshots/{snapshot_id}/source",
            params={"path": "../outside.py"},
        )
        assert traversal.status_code == 400
        assert client.get("/api/route-that-does-not-exist").status_code == 404


def test_validation_is_generic_and_does_not_reflect_input(tmp_path: Path) -> None:
    secret_path = str(tmp_path / "private-secret-repository")
    app = create_workspace_app(data_directory=tmp_path / "data")

    with TestClient(app) as client:
        response = client.post(
            "/api/repositories/analyze",
            json={"repository_path": secret_path, "repository_id": "also-present"},
        )

    assert response.status_code == 422
    assert response.json() == {"detail": "Request validation failed."}
    assert secret_path not in response.text


def test_cli_and_api_share_canonical_snapshot_contract(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    repository = tmp_path / "ordinary"
    shutil.copytree(FIXTURES / "ordinary", repository)
    data_directory = tmp_path / "data"

    exit_code = cli_module.main(
        [
            "experimental",
            "analyze",
            str(repository),
            "--app-data-dir",
            str(data_directory),
            "--json",
        ]
    )
    captured = capsys.readouterr()
    cli_payload = json.loads(captured.out)
    service = RepositoryReviewService(data_directory=data_directory)
    snapshot = service.get_snapshot(cli_payload["snapshot"]["snapshot_id"])

    assert exit_code == 0
    assert snapshot.snapshot_id == cli_payload["snapshot"]["snapshot_id"]
    assert service.overview(snapshot.snapshot_id)["snapshot"]["snapshot_id"] == snapshot.snapshot_id
    assert str(tmp_path) not in captured.out


def test_workspace_binding_is_localhost_only() -> None:
    assert validate_workspace_host("127.0.0.1") == "127.0.0.1"
    try:
        validate_workspace_host("0.0.0.0")
    except ValueError as exc:
        assert "only supports host 127.0.0.1" in str(exc)
    else:
        raise AssertionError("Non-loopback binding was accepted.")
