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
- `GetVolume` returned 15 at `2026-09-01T19:15:50Z`; `SetVolume` to 12 then
  `GetVolume` returned 12 at `19:16:44Z`. Volume control is confirmed without
  raising the level.
- `GetMute` / `SetMute` were tested at `19:38Z`: the user heard a brief mute
  then unmute. The receiver is currently unmuted. The user changed volume with
  the physical remote; a final `GetVolume` at `19:39:08Z` confirmed the current
  volume is 16.
- The physical UI reports a value 10 lower than the UPnP value in two observed
  cases: UPnP 16 displayed as 6, and UPnP 12 displayed as 2. Treat this as a
  provisional `UI volume = UPnP volume - 10` mapping until tested at more
  points.
- `Stop` returned HTTP 200 and changed transport state to `STOPPED` at
  `19:28:44Z`. `Pause` returned UPnP error 701 (`No Such Object`) while the
  receiver still reported `PLAYING`. While playing at `19:36:09Z`,
  `GetCurrentTransportActions` returned only `Play,Stop`; Pause is not a
  currently supported action for this direct-stream flow.

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
- Startup trace with the current Ethernet cable at `2026-09-01T19:57Z`
  (`artifacts/startup-trace-current-cable.jsonl`) showed that the first GET
  began immediately after playback was started (`19:57:11.685Z`). The LG then
  issued many overlapping full-file GETs, all without `Range`, for the same
  8,729,455-byte MP3. Early requests disconnected after 1.6–8.5 MB; later
  requests repeatedly completed the entire file in roughly 0.6–0.8 seconds.
  Audio was heard only after this repeated-fetch period. This rules out a
  delayed *initial* HTTP request, but does not yet distinguish receiver
  buffering/firmware behavior from a network-link contribution. Retest with a
  known-good cable before treating the cable as causal.

## DLNA streaming research: 2026-09-01

- Repeated complete GETs without a `Range` header are valid renderer behavior.
  The server must return the full representation for those requests; it must
  not invent partial responses to suppress repeat downloads.
- `transferMode.dlna.org: Streaming`, `Accept-Ranges: bytes`, and the current
  MP3 `contentFeatures.dlna.org` format are broadly appropriate. Do not change
  transfer mode, DLNA operation flags, or feature flags without a specific
  compatibility hypothesis.
- `TimeSeekRange.dlna.org` is for explicit time-based seeks, not ordinary
  initial playback, and is unlikely to explain full GETs with no `Range`.
- The next protocol check is metadata consistency: the DIDL-Lite resource
  `protocolInfo` must agree exactly with HTTP `Content-Type` (`audio/mpeg`) and
  `contentFeatures.dlna.org` MP3 profile/features. Include the correct resource
  size where available.
- The server now logs start/end time, duration, bytes sent, and client
  disconnects, allowing response completeness to be verified before changing
  compatibility behavior.
- An explicit `Connection: close` response is safe only as a diagnostic
  variant; it may increase reconnections and is not a proposed fix.
- If complete, metadata-consistent responses still repeat, the leading
  explanation is BH6730T renderer buffering/retry behavior rather than a
  missing HTTP/DLNA feature.
- Public references: [UPnP AV Architecture](https://www.upnp.org/specs/av/UPnP-av-AVArchitecture-v2.pdf),
  [RFC 7230 HTTP persistence/framing](https://www.rfc-editor.org/rfc/rfc7230),
  and [RFC 7233 range requests](https://www.rfc-editor.org/rfc/rfc7233).

## Current plan

- [x] Connect, discover, inspect services, and play an MP3 from Linux.
- [x] Test volume and mute. Stop works; direct-stream playback cannot pause.
- [ ] Measure startup delay and streaming behavior with the working flow.
- [ ] Verify DIDL-Lite/HTTP metadata consistency, then run one isolated
  connection-behavior compatibility experiment.
- [ ] Decide practical music sources (local files, PC audio, phone, Spotify).
- [ ] Reproduce the working flow on ESP32, then add controls and UI.
- [ ] Add automatic discovery; investigate power/input control separately.

## Commands

```sh
python3 scripts/discover_ssdp.py --all --timeout 5
python3 scripts/play_to_lg.py assets/gdaal.mp3
python3 scripts/play_to_lg.py --stop
```

`play_to_lg.py` derives the PC's LAN address, starts the media server when it
is not already running, and sends the DIDL-Lite Set URI and Play commands.
Use `--dry-run` to inspect its derived URL without network control.
`--stop` sends Stop to the receiver then stops the exact recorded server PID;
it never uses process-name matching. `--stop-playback` and `--stop-server` are
also available separately. HTTP request logs and the PID file go in
`artifacts/` (intentionally untracked).
