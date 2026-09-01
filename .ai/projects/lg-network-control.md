# LG BH6730T Network Control

## Goal

Make the LG BH6730T a frictionless network-controlled music system, ultimately
with an ESP32 physical controller.

## Hardware

- LG BH6730T; ESP32-WROOM-32 DevKit
- ST7789V display, rotary encoder, WS2812B LED ring, INMP441 microphone
- Linux PC on the same LAN

## Confirmed receiver and service evidence

- IP: `192.168.1.104`; MAC: `98:93:cc:07:4f:1f`
- Firmware: `BD3.412.50203.C`; Network Play is enabled.
- The receiver is a DLNA `MediaRenderer:1` at
  `http://192.168.1.104:2870/dmr.xml`, advertising `AVTransport:1`,
  `RenderingControl:1`, and `ConnectionManager:1`.
- Control URLs:
  - AVTransport: `http://192.168.1.104:2870/control/AVTransport`
  - RenderingControl: `http://192.168.1.104:2870/control/RenderingControl`
  - ConnectionManager: `http://192.168.1.104:2870/control/ConnectionManager`
- `GetProtocolInfo` confirms HTTP GET MP3 support with `DLNA.ORG_PN=MP3`.
- AVTransport supports URI selection and `Play`, `Pause`, `Stop`, `Seek`,
  `Next`, `Previous`, and state queries. RenderingControl advertises `Master`
  volume (0–100) and mute actions.

## Confirmed Linux-to-LG MP3 playback: 2026-09-01

- `assets/gdaal.mp3` is MPEG Layer III, 320 kbps, 44.1 kHz. It played audibly
  after a roughly two-minute delay when served from
  `http://192.168.1.103:8000/gdaal.mp3`.
- Successful control flow: `SetAVTransportURI` with DIDL-Lite metadata, then
  `Play`, both using `InstanceID` `0`. The bare-URI flow does not work.
- `scripts/serve_test_media.py` is the required test server: it responds with
  HTTP/1.1, MP3 DLNA content features, byte-range support, and request logging.
- During playback the receiver repeatedly made full-file `GET` requests with
  `transferMode.dlna.org: Streaming`, without `Range`. At
  `2026-09-01T19:11:18Z`, `GetTransportInfo` returned `PLAYING` / `OK`.
- The exact cause of the long startup delay is unknown; the request log does
  not record transferred-byte counts, so it does not establish full download
  versus buffering/retries.

## Current plan

- [x] Connect, discover, inspect services, and play an MP3 from Linux.
- [ ] Test `GetVolume`, `SetVolume`, mute, and playback transport controls.
- [ ] Measure startup delay and streaming behavior with the working flow.
- [ ] Decide practical music sources (local files, PC audio, phone, Spotify).
- [ ] Reproduce the working flow on ESP32, then add controls and UI.
- [ ] Add automatic discovery; investigate power/input control separately.

## Commands

```sh
python3 scripts/discover_ssdp.py --all --timeout 5
python3 scripts/serve_test_media.py
python3 scripts/upnp_manual_test.py --action set-uri --uri http://192.168.1.103:8000/gdaal.mp3
python3 scripts/upnp_manual_test.py --action play
```

SOAP artifacts go in `artifacts/upnp-tests/`; HTTP request logs go in
`artifacts/media-requests.jsonl` (both intentionally untracked).
