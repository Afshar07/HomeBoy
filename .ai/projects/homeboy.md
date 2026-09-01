# HomeBoy

## Scope

Research and implementation for controlling an LG BH6730T home theater system
over the local network and, if feasible, through an ESP32 physical controller.

## Local context

For LG device discovery, control-protocol work, DLNA/UPnP testing, or ESP32
controller work, read `.ai/projects/lg-network-control.md`. Do not load local
documents that are unrelated to the requested boundary.

## Ownership boundaries

- This project owns LG device evidence, protocol experiments, controller code,
  and hardware integration details.
- Network control is preferred over adding a Bluetooth receiver. Investigate in
  order: LG proprietary control, DLNA/UPnP, then infrared fallback.
- Keep DLNA media-rendering support distinct from proof of transport, volume,
  or general remote-control support.

## Verification

- No general software toolchain is established yet. For repeatable UPnP/DLNA
  discovery, run `python3 scripts/discover_ssdp.py --all --timeout 5`.
- For one explicit SOAP action, run `python3 scripts/upnp_manual_test.py` with
  an `--action`. It saves the request and response (or connection error) in
  `artifacts/upnp-tests/`, which is intentionally untracked.
- Record discovery commands, SOAP request payloads and responses, pairing
  prompts, and observed device behavior with the relevant experiment.
