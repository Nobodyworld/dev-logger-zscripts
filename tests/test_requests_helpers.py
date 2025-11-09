"""Smoke tests for helpers.requests utilities."""

from __future__ import annotations

from unittest.mock import Mock

import requests

from zscripts.helpers.requests import create_retrying_session, fetch_json


def test_create_retrying_session_mounts_retry_adapter() -> None:
    session = create_retrying_session(total=2, backoff_factor=0.1, status_forcelist=(500,))

    adapter = session.get_adapter("https://")
    retries = adapter.max_retries

    assert retries.total == 2
    assert retries.backoff_factor == 0.1
    assert 500 in retries.status_forcelist


def test_fetch_json_uses_injected_session() -> None:
    mock_session = Mock(spec=requests.Session)
    mock_response = Mock()
    mock_response.raise_for_status.return_value = None
    mock_response.json.return_value = {"status": "ok"}
    mock_session.get.return_value = mock_response

    data = fetch_json(
        "https://example.com/api",
        session=mock_session,
        timeout=5,
        headers={"X-Test": "1"},
    )

    mock_session.get.assert_called_once()
    assert data == {"status": "ok"}


def main() -> None:
    test_create_retrying_session_mounts_retry_adapter()
    test_fetch_json_uses_injected_session()


if __name__ == "__main__":
    main()
