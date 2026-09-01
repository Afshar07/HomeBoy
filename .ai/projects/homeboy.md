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

- No software toolchain or automated verification command is established yet.
- Record repeatable discovery commands, request payloads, responses, pairing
  prompts, and observed device behavior with the relevant experiment.
