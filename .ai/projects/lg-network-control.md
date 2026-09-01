# LG BH6730T Network Control

## Goal

Make the LG BH6730T a frictionless network-controlled music system using
existing hardware, preferably an ESP32 physical controller.

## Available hardware

- LG BH6730T home theater
- ESP32-WROOM-32 DevKit
- ST7789V TFT display, rotary encoder, WS2812B LED ring, and INMP441 microphone
- Linux PC and the existing home network

The display may present playback and system status; the encoder may provide
volume and navigation; the LED ring may provide state feedback. The microphone
is reserved for future audio-reactive or input experiments.

## HomeBoy plan

- [x] Connect BH6730T to LAN
- [x] Identify it on network → `192.168.1.104`
- [x] Update firmware → `BD3.412.50203.C`
- [x] Enable **Network Play**
- [x] Confirm from LG UI that **DMR is explicitly supported**
- [x] Rerun SSDP discovery with Network Play enabled
- [x] Find its `MediaRenderer` advertisement + `LOCATION` XML
- [x] Inspect advertised `AVTransport`, `RenderingControl`, and `ConnectionManager`
- [ ] From Linux, send a simple **Play this MP3** command to the LG
- [ ] Test play/pause/stop/volume
- [ ] Test serving/streaming music from Linux → LG
- [ ] Figure out what sources we can realistically feed it: local files, PC audio, phone, Spotify/etc.
- [ ] Reproduce the working UPnP control flow on the **ESP32**
- [ ] Add rotary encoder → volume/playback
- [ ] Add ST7789 TFT → track/status/device UI
- [ ] Add WS2812 ring → playback/status visualization
- [ ] Make discovery automatic so ESP32 finds the LG without hardcoded IP
- [ ] Investigate power/input control separately — UPnP if possible, otherwise LG protocol/IR
- [ ] Eventually make the whole thing feel like one appliance: **turn it on → choose music → it plays**

## Confirmed device evidence

- IP address: `192.168.1.104`
- MAC address: `98:93:cc:07:4f:1f` (LG Electronics OUI)
- Software: `BD3.412.50203.C`; Driver/Loader: `H12SON0420`
- The device software was updated before further network-control testing.
- Ethernet, DLNA, HDMI output, legacy LG network/remote functionality, and DMR
  are available. Network Play is enabled.
- The device setting states that DMR permits media streamed from home-networked
  devices. This confirms media-renderer capability only—not network transport,
  volume, or general remote control.

## Prior discovery results

Before Network Play was confirmed and enabled, TCP HTTP services were observed
on ports `46211` and `57626`; both returned `404 Not Found` for `/`. No SSDP
response or advertisement for `MediaRenderer`, `AVTransport`,
`RenderingControl`, or `ConnectionManager` was found. Repeat this discovery
with Network Play active before treating those negatives as current.

## Discovery record: 2026-09-01

- With the BH6730T powered on and Network Play enabled, active SSDP discovery
  succeeded at `2026-09-01T21:55:59+03:30`.
- Repeat with: `python3 scripts/discover_ssdp.py --all --timeout 5`
- The device responded from `192.168.1.104:2870` and advertised
  `MediaRenderer:1`, `AVTransport:1`, `RenderingControl:1`, and
  `ConnectionManager:1`.
- Device description: `http://192.168.1.104:2870/dmr.xml`
- Server header: `LG-BDP Linux/2.6.35 UPnP/1.0 DLNADOC/1.50 LGE_DLNA_SDK/1.5.0`

## Service inspection record: 2026-09-01

- Retrieved `dmr.xml` and all three service-description documents at
  `2026-09-01T22:01:31+03:30`. These are advertised capabilities; their SOAP
  behavior has not yet been tested.
- `AVTransport`:
  - SCPD: `http://192.168.1.104:2870/dmr_avts.xml`
  - Control: `http://192.168.1.104:2870/control/AVTransport`
  - Advertised actions include `SetAVTransportURI`, `Play`, `Pause`, `Stop`,
    `Seek`, `Next`, `Previous`, and transport/media status queries.
- `RenderingControl`:
  - SCPD: `http://192.168.1.104:2870/dmr_rcs.xml`
  - Control: `http://192.168.1.104:2870/control/RenderingControl`
  - Advertised actions include `GetVolume`, `SetVolume`, `GetMute`, and
    `SetMute`; volume is declared as `0`–`100` and the `Master` channel is
    allowed.
- `ConnectionManager`:
  - SCPD: `http://192.168.1.104:2870/dmr_cms.xml`
  - Control: `http://192.168.1.104:2870/control/ConnectionManager`
  - Advertised actions include `GetProtocolInfo`, `GetCurrentConnectionIDs`,
    and `GetCurrentConnectionInfo`.

## Next experiment

1. Call the read-only SOAP actions `GetProtocolInfo`, `GetTransportInfo`, and
   `GetVolume` to establish request format and current state.
2. Independently test compatible-media playback, transport controls, and volume
   control.
3. Record ports, service URLs, request/response details, pairing prompts, and
   behavior changes.

## Follow-on research

- Reverse-engineer the legacy LG Remote app protocol and capture its pairing and
  control traffic.
- Investigate the BD-J/Java environment as an independent track.
- Explore Linux monitor input switching through DDC/CI.
