# J1939 PCAN Simulator

A desktop tool for simulating J1939 ECUs over PCAN without hand-calculating hex
frames. Configure signals by physical units, simulate diagnostic messages, and
manage everything through editable JSON configs.

## Download

Download the latest Windows executable from the GitHub Releases page.

```text
J1939_Simulator.exe
```

## What It Does

- Sends configurable SAE J1939 29-bit CAN frames.
- Lets you edit PGN, priority, source address, and destination/group extension.
- Configures signal values with byte/bit layout, scale, offset, raw range, and
  physical units.
- Supports PEAK PCAN USB adapters through the PCAN backend.
- Supports a virtual backend for offline smoke testing.
- Uses editable JSON configuration files.
- Shows frame preview, validation status, and transmit logs.

## Requirements

- Windows 10/11 64-bit
- PEAK PCAN USB adapter for real CAN transmission
- PEAK PCAN-Basic driver/runtime for PCAN backend

No PCAN hardware is required for the virtual backend.

## Basic Usage

1. Start `J1939_Simulator.exe`.
2. Select backend:
   - `PCAN` for PEAK hardware
   - `Virtual` for offline testing
3. Select channel and bitrate.
4. Click `Reconnect`.
5. Open or edit a JSON configuration.
6. Start active messages and watch the frame log.

## Reporting Issues

Use GitHub Issues in this public repository for:

- Bug reports
- Feature requests
- PCAN connection problems
- Packaging or release problems

Please include screenshots, Windows version, PCAN adapter model, driver status,
and the exact steps to reproduce the problem.

## Source Code

The source code is maintained in a private repository. This public repository is
for releases, documentation, screenshots, and issue tracking.

## License

MIT License for public release materials unless stated otherwise.
