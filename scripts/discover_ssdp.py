#!/usr/bin/env python3
"""Actively discover UPnP/DLNA services with SSDP M-SEARCH.

Default target is the service needed to establish whether the receiver is a
DLNA MediaRenderer. Pass --all to probe its control services as well.
"""

from __future__ import annotations

import argparse
import select
import socket
import sys
import time
from collections.abc import Iterable


SSDP_ADDRESS = ("239.255.255.250", 1900)
MEDIA_RENDERER = "urn:schemas-upnp-org:device:MediaRenderer:1"
CONTROL_SERVICES = (
    "urn:schemas-upnp-org:service:AVTransport:1",
    "urn:schemas-upnp-org:service:RenderingControl:1",
    "urn:schemas-upnp-org:service:ConnectionManager:1",
)


def search_message(search_target: str, mx: int) -> bytes:
    return (
        "M-SEARCH * HTTP/1.1\r\n"
        "HOST: 239.255.255.250:1900\r\n"
        'MAN: "ssdp:discover"\r\n'
        f"MX: {mx}\r\n"
        f"ST: {search_target}\r\n"
        "\r\n"
    ).encode("ascii")


def parse_headers(response: bytes) -> dict[str, str]:
    lines = response.decode("utf-8", errors="replace").split("\r\n")
    headers = {"_status": lines[0] if lines else ""}
    for line in lines[1:]:
        if ":" in line:
            key, value = line.split(":", 1)
            headers[key.strip().lower()] = value.strip()
    return headers


def targets(include_all: bool) -> Iterable[str]:
    yield MEDIA_RENDERER
    if include_all:
        yield from CONTROL_SERVICES


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="also probe UPnP control services")
    parser.add_argument("--timeout", type=float, default=5, help="seconds to wait per search (default: 5)")
    parser.add_argument("--mx", type=int, default=3, help="SSDP MX header, in seconds (default: 3)")
    args = parser.parse_args()

    if args.timeout <= 0 or not 1 <= args.mx <= 120:
        parser.error("--timeout must be positive and --mx must be between 1 and 120")

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM, socket.IPPROTO_UDP)
    sock.setsockopt(socket.IPPROTO_IP, socket.IP_MULTICAST_TTL, 2)
    sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    sock.bind(("", 0))

    results: dict[tuple[str, str], dict[str, str]] = {}
    try:
        for target in targets(args.all):
            print(f"Searching for {target}…", flush=True)
            sock.sendto(search_message(target, args.mx), SSDP_ADDRESS)
            deadline = time.monotonic() + args.timeout
            while (remaining := deadline - time.monotonic()) > 0:
                ready, _, _ = select.select([sock], [], [], remaining)
                if not ready:
                    break
                response, sender = sock.recvfrom(65535)
                headers = parse_headers(response)
                key = (headers.get("usn", ""), headers.get("location") or sender[0])
                results[key] = headers | {"_sender": f"{sender[0]}:{sender[1]}"}
    finally:
        sock.close()

    if not results:
        print("No SSDP responses received.")
        return 1

    print(f"\nReceived {len(results)} unique SSDP response(s):")
    for headers in results.values():
        print("\n---")
        for key in ("_sender", "_status", "st", "usn", "location", "server", "cache-control"):
            if value := headers.get(key):
                print(f"{key.upper()}: {value}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
