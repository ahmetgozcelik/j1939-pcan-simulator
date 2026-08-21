# J1939 PCAN Simulator v1.0.0

Initial public release candidate for the SAE J1939 PCAN simulator.

## Highlights

- Configure and transmit 29-bit SAE J1939 CAN frames.
- Edit PGN, priority, source address, and destination/group extension fields.
- Configure SPN-like signals by byte/bit layout, raw range, scale, offset, and
  physical units.
- Simulate values with fixed, random, sine, sawtooth, and ramp modes.
- Use PCAN hardware through `python-can` or the software-only virtual backend.
- Preview 8-byte payloads before transmission.
- Simulate diagnostic DTC payloads for DM messages using editable JSON
  definitions.
- Validate workspaces for duplicate IDs, invalid bit ranges, signal overlap, raw
  range errors, and invalid scales.
- Use recovery backups before destructive new/open actions.
- Work in a defense/industrial-style operator UI with logs and validation status.

## Requirements

- Windows 10/11 64-bit
- PEAK PCAN USB adapter for real CAN transmission
- PEAK PCAN-Basic driver/runtime for PCAN backend
- No hardware required for virtual backend smoke testing

## Known Limitations

- J1939 Transport Protocol transmit is not implemented yet.
- Multi-packet payloads are not supported.
- The included PGN/SPN examples are starter definitions, not a complete SAE
  Digital Annex database.
- PCAN hardware transmission must be verified on the target Windows machine.
- `PCANBasic.dll` is not redistributed in the public repository unless its
  license/redistribution terms are explicitly checked.

## Smoke Test

Before publishing the release asset:

1. Run the app without PCAN hardware and confirm it opens.
2. Select `Virtual` backend and reconnect.
3. Open `configs/default.json`.
4. Start and stop an active message.
5. Confirm the frame log updates.
6. If hardware is available, reconnect with `PCAN`, `PCAN_USBBUS1`, and the
   target bus bitrate, then confirm a known frame on the bus.
