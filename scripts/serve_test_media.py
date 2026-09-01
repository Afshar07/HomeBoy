#!/usr/bin/env python3
"""Serve one test-media directory with byte ranges and request-header logging.

Use this while testing the LG receiver's DLNA playback flow. Request records are
written as JSON Lines so the receiver's method, headers, response status, and
served byte range can be correlated with its UI and AVTransport state.
"""

from __future__ import annotations

import argparse
import json
import mimetypes
import time
from datetime import datetime, timezone
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import TextIO
from urllib.parse import unquote, urlsplit


DLNA_MP3_CONTENT_FEATURES = "DLNA.ORG_PN=MP3;DLNA.ORG_OP=01;DLNA.ORG_CI=0;DLNA.ORG_FLAGS=01500000000000000000000000000000"


def parse_byte_range(value: str | None, size: int) -> tuple[int, int] | None:
    """Return an inclusive byte range, or raise ValueError for an invalid one."""
    if value is None:
        return None
    if not value.startswith("bytes=") or "," in value:
        raise ValueError("only one bytes range is supported")
    start_text, separator, end_text = value[6:].partition("-")
    if not separator or not start_text:
        raise ValueError("range must start with a byte offset")
    try:
        start = int(start_text)
        end = size - 1 if not end_text else int(end_text)
    except ValueError as error:
        raise ValueError("range offsets must be integers") from error
    if start < 0 or end < start or start >= size:
        raise ValueError("range is outside the file")
    return start, min(end, size - 1)


def request_handler(root: Path, log: TextIO) -> type[BaseHTTPRequestHandler]:
    class TestMediaHandler(BaseHTTPRequestHandler):
        server_version = "HomeBoyTestMedia/1.0"
        protocol_version = "HTTP/1.1"

        def do_GET(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
            self.serve_media(include_body=True)

        def do_HEAD(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
            self.serve_media(include_body=False)

        def serve_media(self, *, include_body: bool) -> None:
            started_at = datetime.now(timezone.utc)
            started_monotonic = time.monotonic()
            status = HTTPStatus.OK
            served_range: tuple[int, int] | None = None
            size = 0
            body_bytes_sent = 0
            transfer_error: str | None = None
            try:
                requested_path = Path(unquote(urlsplit(self.path).path).lstrip("/"))
                file_path = (root / requested_path).resolve()
                if root not in file_path.parents or not file_path.is_file():
                    self.send_error(HTTPStatus.NOT_FOUND)
                    status = HTTPStatus.NOT_FOUND
                    return

                size = file_path.stat().st_size
                served_range = parse_byte_range(self.headers.get("Range"), size)
                if served_range is None:
                    start, end = 0, size - 1
                else:
                    start, end = served_range
                    status = HTTPStatus.PARTIAL_CONTENT
                content_length = end - start + 1
                self.send_response(status)
                self.send_header("Accept-Ranges", "bytes")
                self.send_header("Content-Type", mimetypes.guess_type(file_path.name)[0] or "application/octet-stream")
                if file_path.suffix.lower() == ".mp3":
                    self.send_header("contentFeatures.dlna.org", DLNA_MP3_CONTENT_FEATURES)
                if transfer_mode := self.headers.get("transferMode.dlna.org"):
                    self.send_header("transferMode.dlna.org", transfer_mode)
                self.send_header("Content-Length", str(content_length))
                if served_range is not None:
                    self.send_header("Content-Range", f"bytes {start}-{end}/{size}")
                self.end_headers()
                if include_body:
                    with file_path.open("rb") as media:
                        media.seek(start)
                        remaining = content_length
                        while remaining:
                            chunk = media.read(min(64 * 1024, remaining))
                            if not chunk:
                                break
                            self.wfile.write(chunk)
                            body_bytes_sent += len(chunk)
                            remaining -= len(chunk)
            except ValueError:
                status = HTTPStatus.REQUESTED_RANGE_NOT_SATISFIABLE
                self.send_response(status)
                self.send_header("Content-Range", f"bytes */{size}")
                self.end_headers()
            except (BrokenPipeError, ConnectionResetError):
                # The receiver may close a test transfer; retain the request record.
                transfer_error = "client_disconnected"
            finally:
                record = {
                    "timestamp": started_at.isoformat(),
                    "completed_at": datetime.now(timezone.utc).isoformat(),
                    "duration_ms": round((time.monotonic() - started_monotonic) * 1000),
                    "client": self.client_address[0],
                    "method": self.command,
                    "path": self.path,
                    "request_headers": dict(self.headers.items()),
                    "response_status": status.value,
                    "served_range": list(served_range) if served_range else None,
                    "body_bytes_sent": body_bytes_sent,
                    "transfer_error": transfer_error,
                }
                log.write(json.dumps(record) + "\n")
                log.flush()

        def log_message(self, format: str, *args: object) -> None:
            return

    return TestMediaHandler


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=Path("assets"), help="media directory (default: assets)")
    parser.add_argument("--host", default="0.0.0.0", help="address to bind (default: all interfaces)")
    parser.add_argument("--port", type=int, default=8000, help="port to bind (default: 8000)")
    parser.add_argument("--log", type=Path, default=Path("artifacts/media-requests.jsonl"), help="request log path")
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    root = args.directory.resolve()
    if not root.is_dir():
        parser.error(f"media directory does not exist: {root}")
    args.log.parent.mkdir(parents=True, exist_ok=True)

    with args.log.open("a", encoding="utf-8") as log:
        server = ThreadingHTTPServer((args.host, args.port), request_handler(root, log))
        print(f"Serving {root} on http://{args.host}:{args.port}; logging requests to {args.log}")
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
