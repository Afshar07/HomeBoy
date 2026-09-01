#!/usr/bin/env python3
"""Send one explicit UPnP SOAP action to the LG receiver and save its response.

No network traffic is sent until an action is selected. Every request/response
is retained under artifacts/upnp-tests/ for manual inspection.
"""

from __future__ import annotations

import argparse
import html
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_DEVICE = "http://192.168.1.104:2870"
SERVICES = {
    "protocol-info": "ConnectionManager",
    "transport-info": "AVTransport",
    "transport-actions": "AVTransport",
    "volume": "RenderingControl",
    "set-volume": "RenderingControl",
    "mute": "RenderingControl",
    "set-mute": "RenderingControl",
    "set-uri": "AVTransport",
    "play": "AVTransport",
    "pause": "AVTransport",
    "stop": "AVTransport",
}
ACTION_NAMES = {
    "protocol-info": "GetProtocolInfo",
    "transport-info": "GetTransportInfo",
    "transport-actions": "GetCurrentTransportActions",
    "volume": "GetVolume",
    "set-volume": "SetVolume",
    "mute": "GetMute",
    "set-mute": "SetMute",
    "set-uri": "SetAVTransportURI",
    "play": "Play",
    "pause": "Pause",
    "stop": "Stop",
}


def didl_metadata(uri: str) -> str:
    title = Path(uri.split("?", 1)[0]).name or "HomeBoy test media"
    return (
        '<DIDL-Lite xmlns="urn:schemas-upnp-org:metadata-1-0/DIDL-Lite/" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/" '
        'xmlns:upnp="urn:schemas-upnp-org:metadata-1-0/upnp/">'
        '<item id="homeboy-test" parentID="0" restricted="1">'
        f"<dc:title>{html.escape(title)}</dc:title>"
        "<upnp:class>object.item.audioItem.musicTrack</upnp:class>"
        f'<res protocolInfo="http-get:*:audio/mpeg:DLNA.ORG_PN=MP3">{html.escape(uri)}</res>'
        "</item></DIDL-Lite>"
    )


def action_body(
    action: str, uri: str | None, metadata: str, volume: int | None, mute: bool | None
) -> tuple[str, str]:
    if action == "protocol-info":
        return "ConnectionManager", ""
    if action == "transport-info":
        return "AVTransport", "<InstanceID>0</InstanceID>"
    if action == "transport-actions":
        return "AVTransport", "<InstanceID>0</InstanceID>"
    if action == "volume":
        return "RenderingControl", "<InstanceID>0</InstanceID><Channel>Master</Channel>"
    if action == "set-volume":
        if volume is None:
            raise ValueError("--volume is required for set-volume")
        return (
            "RenderingControl",
            f"<InstanceID>0</InstanceID><Channel>Master</Channel><DesiredVolume>{volume}</DesiredVolume>",
        )
    if action == "mute":
        return "RenderingControl", "<InstanceID>0</InstanceID><Channel>Master</Channel>"
    if action == "set-mute":
        if mute is None:
            raise ValueError("--mute is required for set-mute")
        return (
            "RenderingControl",
            f"<InstanceID>0</InstanceID><Channel>Master</Channel><DesiredMute>{int(mute)}</DesiredMute>",
        )
    if action == "set-uri":
        if not uri:
            raise ValueError("--uri is required for set-uri")
        current_metadata = "" if metadata == "empty" else didl_metadata(uri)
        return (
            "AVTransport",
            "<InstanceID>0</InstanceID>"
            f"<CurrentURI>{html.escape(uri)}</CurrentURI>"
            f"<CurrentURIMetaData>{html.escape(current_metadata)}</CurrentURIMetaData>",
        )
    if action == "play":
        return "AVTransport", "<InstanceID>0</InstanceID><Speed>1</Speed>"
    return "AVTransport", "<InstanceID>0</InstanceID>"


def soap_envelope(service: str, action: str, body: str) -> str:
    service_urn = f"urn:schemas-upnp-org:service:{service}:1"
    return f'''<?xml version="1.0" encoding="utf-8"?>
<s:Envelope xmlns:s="http://schemas.xmlsoap.org/soap/envelope/" s:encodingStyle="http://schemas.xmlsoap.org/soap/encoding/">
  <s:Body>
    <u:{action} xmlns:u="{service_urn}">{body}</u:{action}>
  </s:Body>
</s:Envelope>
'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--action", choices=SERVICES, required=True)
    parser.add_argument("--uri", help="HTTP URL the receiver can reach; required by set-uri")
    parser.add_argument("--metadata", choices=("didl", "empty"), default="didl")
    parser.add_argument("--volume", type=int, help="volume from 0 to 100; required by set-volume")
    parser.add_argument("--mute", choices=("true", "false"), help="required by set-mute")
    parser.add_argument("--device", default=DEFAULT_DEVICE, help=f"receiver base URL (default: {DEFAULT_DEVICE})")
    parser.add_argument("--output-dir", type=Path, default=Path("artifacts/upnp-tests"))
    args = parser.parse_args()

    try:
        if args.volume is not None and not 0 <= args.volume <= 100:
            raise ValueError("--volume must be between 0 and 100")
        mute = None if args.mute is None else args.mute == "true"
        service, body = action_body(args.action, args.uri, args.metadata, args.volume, mute)
    except ValueError as error:
        parser.error(str(error))

    action_name = ACTION_NAMES[args.action]
    payload = soap_envelope(service, action_name, body)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stem = args.output_dir / f"{timestamp}-{args.action}"
    request_path = stem.with_suffix(".request.xml")
    response_path = stem.with_suffix(".response.xml")
    request_path.write_text(payload, encoding="utf-8")

    url = f"{args.device.rstrip('/')}/control/{service}"
    service_urn = f"urn:schemas-upnp-org:service:{service}:1"
    request = Request(
        url,
        data=payload.encode("utf-8"),
        headers={
            "Content-Type": 'text/xml; charset="utf-8"',
            "SOAPACTION": f'"{service_urn}#{action_name}"',
        },
        method="POST",
    )
    try:
        with urlopen(request, timeout=10) as response:
            response_path.write_bytes(response.read())
            status = response.status
    except HTTPError as error:
        response_path.write_bytes(error.read())
        status = error.code
    except URLError as error:
        response_path = stem.with_suffix(".error.txt")
        response_path.write_text(str(error), encoding="utf-8")
        print(f"Request could not reach the receiver; details: {response_path}", file=sys.stderr)
        return 2

    print(f"HTTP {status}; request: {request_path}; response: {response_path}")
    return 0 if 200 <= status < 300 else 1


if __name__ == "__main__":
    raise SystemExit(main())
