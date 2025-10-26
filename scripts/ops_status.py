"""Operations status inspection utility for telemetry health endpoints."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib import error, request

DEFAULT_BASE_URL = "http://127.0.0.1:9464"


@dataclass(frozen=True)
class StatusSnapshot:
    """Normalized view of the telemetry health payload."""

    status: str
    url: str
    probe: str
    timestamp: str
    payload: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "url": self.url,
            "probe": self.probe,
            "timestamp": self.timestamp,
            "payload": self.payload,
        }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--url",
        default=DEFAULT_BASE_URL,
        help="Base URL for the telemetry server (host and port).",
    )
    parser.add_argument(
        "--probe",
        choices=("healthz", "ready", "live"),
        default="healthz",
        help="Health endpoint to query.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=2.0,
        help="Timeout in seconds for the HTTP request.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path to write the JSON summary.",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    probe_url = _build_probe_url(args.url, args.probe)
    try:
        payload = _fetch_json(probe_url, timeout=args.timeout)
    except error.HTTPError as exc:
        payload = _decode_http_error(exc)
        status = str(payload.get("status", "error")).lower()
        ok = status in {"ok", "pass", "ready", "live"}
        snapshot = StatusSnapshot(
            status=status,
            url=probe_url,
            probe=args.probe,
            timestamp=datetime.now(timezone.utc).isoformat(),
            payload=payload,
        )
        _emit_snapshot(snapshot, args.output)
        sys.exit(0 if ok else 1)
    except error.URLError as exc:
        snapshot = StatusSnapshot(
            status="error",
            url=probe_url,
            probe=args.probe,
            timestamp=datetime.now(timezone.utc).isoformat(),
            payload={"error": str(exc)},
        )
        _emit_snapshot(snapshot, args.output)
        sys.exit(2)
    else:
        status = str(payload.get("status", "unknown")).lower()
        ok = status in {"ok", "pass", "ready", "live"}
        snapshot = StatusSnapshot(
            status=status,
            url=probe_url,
            probe=args.probe,
            timestamp=datetime.now(timezone.utc).isoformat(),
            payload=payload,
        )
        _emit_snapshot(snapshot, args.output)
        sys.exit(0 if ok else 1)


def _emit_snapshot(snapshot: StatusSnapshot, output: Path | None) -> None:
    body = json.dumps(snapshot.to_dict(), indent=2)
    print(body)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(body, encoding="utf-8")


def _fetch_json(url: str, *, timeout: float) -> dict[str, Any]:
    with request.urlopen(url, timeout=timeout) as response:
        charset = response.headers.get_content_charset("utf-8")
        data = response.read().decode(charset)
        payload = json.loads(data)
        if not isinstance(payload, dict):
            raise ValueError("Health endpoint returned a non-object payload")
        return payload


def _decode_http_error(exc: error.HTTPError) -> dict[str, Any]:
    charset = exc.headers.get_content_charset("utf-8") if exc.headers else "utf-8"
    try:
        data = exc.read().decode(charset)
    except Exception:
        data = ""
    if data:
        try:
            payload = json.loads(data)
        except json.JSONDecodeError:
            payload = {}
        if isinstance(payload, dict):
            payload.setdefault("status", "error")
            payload.setdefault("http_status", exc.code)
            return payload
        return {
            "status": "error",
            "http_status": exc.code,
            "reason": exc.reason,
            "body": data,
        }
    return {"status": "error", "http_status": exc.code, "reason": exc.reason}


def _build_probe_url(base_url: str, probe: str) -> str:
    normalized = base_url.rstrip("/")
    suffix_map = {
        "healthz": "/healthz",
        "ready": "/healthz/ready",
        "live": "/healthz/live",
    }
    if normalized.endswith(tuple(suffix_map.values())):
        return normalized
    return normalized + suffix_map[probe]


if __name__ == "__main__":
    main()
