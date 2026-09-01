#!/usr/bin/env python3
"""Start the local DLNA test server and play one MP3 on the LG receiver."""

from __future__ import annotations

import argparse
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import Request, urlopen

try:
    from .upnp_manual_test import DEFAULT_DEVICE, ACTION_NAMES, action_body, soap_envelope
except ImportError:  # Direct execution: `python3 scripts/play_to_lg.py`.
    from upnp_manual_test import DEFAULT_DEVICE, ACTION_NAMES, action_body, soap_envelope


def local_address_for(device: str) -> str:
    hostname = urlsplit(device).hostname
    if not hostname:
        raise ValueError(f"device URL has no hostname: {device}")
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
        sock.connect((hostname, 2870))
        return sock.getsockname()[0]


def server_is_listening(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=0.2):
            return True
    except OSError:
        return False


def pid_is_media_server(pid: int) -> bool:
    try:
        command = Path(f"/proc/{pid}/cmdline").read_bytes().decode("utf-8", errors="replace")
    except OSError:
        return False
    return "serve_test_media.py" in command


def write_pid(pid_path: Path, pid: int) -> None:
    pid_path.parent.mkdir(parents=True, exist_ok=True)
    temporary_path = pid_path.with_suffix(".tmp")
    temporary_path.write_text(f"{pid}\n", encoding="ascii")
    temporary_path.replace(pid_path)


def stop_server(pid_path: Path) -> bool:
    try:
        pid = int(pid_path.read_text(encoding="ascii").strip())
    except (OSError, ValueError):
        return False
    if not pid_is_media_server(pid):
        pid_path.unlink(missing_ok=True)
        return False
    os.kill(pid, signal.SIGTERM)
    for _ in range(20):
        if not pid_is_media_server(pid):
            pid_path.unlink(missing_ok=True)
            return True
        time.sleep(0.1)
    raise RuntimeError(f"media server PID {pid} did not stop after SIGTERM")


def start_server(directory: Path, port: int, log: Path, pid_path: Path) -> int | None:
    if server_is_listening(port):
        return None
    server_script = Path(__file__).with_name("serve_test_media.py")
    log.parent.mkdir(parents=True, exist_ok=True)
    process = subprocess.Popen(
        [
            sys.executable,
            str(server_script),
            "--directory",
            str(directory),
            "--port",
            str(port),
            "--log",
            str(log),
        ],
        start_new_session=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    for _ in range(20):
        if server_is_listening(port):
            write_pid(pid_path, process.pid)
            return process.pid
        if process.poll() is not None:
            raise RuntimeError(f"media server exited with status {process.returncode}")
        time.sleep(0.1)
    raise RuntimeError(f"media server did not start on port {port}")


def send_action(device: str, action: str, uri: str | None = None) -> int:
    service, body = action_body(action, uri, "didl", None, None)
    action_name = ACTION_NAMES[action]
    service_urn = f"urn:schemas-upnp-org:service:{service}:1"
    request = Request(
        f"{device.rstrip('/')}/control/{service}",
        data=soap_envelope(service, action_name, body).encode("utf-8"),
        headers={
            "Content-Type": 'text/xml; charset="utf-8"',
            "SOAPACTION": f'"{service_urn}#{action_name}"',
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:
            response.read()
            return response.status
    except HTTPError as error:
        error.read()
        return error.code
    except URLError as error:
        raise RuntimeError(f"could not reach receiver: {error.reason}") from error


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("media", type=Path, nargs="?", help="local MP3 to serve and play")
    parser.add_argument("--device", default=DEFAULT_DEVICE, help=f"receiver URL (default: {DEFAULT_DEVICE})")
    parser.add_argument("--port", type=int, default=8000, help="local media-server port (default: 8000)")
    parser.add_argument("--log", type=Path, default=Path("artifacts/media-requests.jsonl"), help="HTTP request log path")
    parser.add_argument("--pid-file", type=Path, default=Path("artifacts/media-server.pid"), help="managed server PID path")
    parser.add_argument("--stop-server", action="store_true", help="stop the server previously started by this script")
    parser.add_argument("--stop-playback", action="store_true", help="send Stop to the LG receiver")
    parser.add_argument("--stop", action="store_true", help="stop LG playback and the managed media server")
    parser.add_argument("--dry-run", action="store_true", help="print the derived playback URL without starting or controlling anything")
    args = parser.parse_args()
    if args.stop:
        args.stop_server = True
        args.stop_playback = True
    if args.stop_server or args.stop_playback:
        if args.media:
            parser.error("media cannot be used with a stop option")
        exit_code = 0
        if args.stop_playback:
            try:
                stop_status = send_action(args.device, "stop")
            except RuntimeError as error:
                print(error, file=sys.stderr)
                exit_code = 2
            else:
                if 200 <= stop_status < 300:
                    print("Stopped LG playback.")
                else:
                    print(f"LG Stop: HTTP {stop_status}", file=sys.stderr)
                    exit_code = 1
        if args.stop_server:
            try:
                stopped = stop_server(args.pid_file)
            except RuntimeError as error:
                print(error, file=sys.stderr)
                return 2
            print("Stopped managed media server." if stopped else "No managed media server is running.")
        return exit_code
    if args.media is None:
        parser.error("media is required unless --stop-server is used")
    if not 1 <= args.port <= 65535:
        parser.error("--port must be between 1 and 65535")
    media = args.media.resolve()
    if not media.is_file():
        parser.error(f"media file does not exist: {media}")
    if media.suffix.lower() != ".mp3":
        parser.error("only MP3 files are supported by this launcher")

    host = local_address_for(args.device)
    uri = f"http://{host}:{args.port}/{quote(media.name)}"
    if args.dry_run:
        print(f"Would serve {media} and play {uri} on {args.device}")
        return 0

    try:
        server_pid = start_server(media.parent, args.port, args.log, args.pid_file)
        set_uri_status = send_action(args.device, "set-uri", uri)
        play_status = send_action(args.device, "play")
    except (RuntimeError, ValueError) as error:
        print(error, file=sys.stderr)
        return 2
    if not 200 <= set_uri_status < 300 or not 200 <= play_status < 300:
        print(f"Set URI: HTTP {set_uri_status}; Play: HTTP {play_status}", file=sys.stderr)
        return 1
    server_message = f"started media server (PID {server_pid})" if server_pid else "using media server already on port"
    print(f"Set URI and started playback; {server_message} {args.port}: {uri}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
