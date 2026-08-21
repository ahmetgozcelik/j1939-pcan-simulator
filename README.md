# J1939 PCAN Simulator

Desktop simulator for sending configurable SAE J1939 CAN frames through PEAK PCAN
USB adapters or a software-only virtual CAN backend.

TR: PEAK PCAN USB veya sanal CAN backend uzerinden yapilandirilabilir SAE J1939
mesajlari gonderen masaustu simulator.

## Status

This project is an operator-oriented J1939 test bench. It is useful for ECU, PLC,
HMI, and bench-test workflows where repeatable PGN/SPN data is needed without
manually typing payload bytes in PCAN-View.

The UI and protocol helpers are designed around SAE J1939 concepts:

- 29-bit extended CAN identifiers
- Priority, PGN, source address, destination address/group extension fields
- PDU1/PDU2 PGN parsing rules
- Standard, request, transport, diagnostic, proprietary A/B PGN categories
- 8-byte single-frame J1939 messages
- DM1 and DM2 diagnostic DTC simulation panels
- PEAK PCAN and virtual python-can backends

## SAE J1939 Scope

Supported:

- 29-bit extended CAN ID parsing and formatting
- PGN calculation using the SAE J1939 PDU rule:
  - PDU1: `PF < 240`, `PS` is destination address and is not part of the PGN
  - PDU2: `PF >= 240`, `PS` is group extension and is part of the PGN
- Single-frame 8-byte payload packing
- Little-endian and big-endian signal packing
- Raw/physical value conversion with scale and offset
- DM1 PGN `0x00FECA` / `65226`
- DM2 PGN `0x00FECB` / `65227`
- DM1/DM2 lamp status, flash lamp status, SPN, FMI, occurrence count preview
- External DM lamp/FMI definitions in `configs/dm1_definitions.json`
- Workspace validation for invalid IDs, duplicate IDs, signal overlap, bit
  range errors, raw range errors, and invalid scale values

Not currently supported:

- J1939 Transport Protocol transmit for multi-packet payloads
- Multi-DTC DM1/DM2 messages beyond a single 8-byte frame
- Full SAE J1939 Digital Annex database import
- Automatic SPN database lookup for every standard PGN
- Hardware-in-the-loop verification without a connected PEAK adapter

## PCAN Requirements

For real CAN bus transmission:

- Windows 10/11 64-bit
- PEAK PCAN USB adapter
- PEAK PCAN-Basic driver/runtime installed
- `python-can`
- Default J1939 bitrate: `250 kbps`
- Supported UI bitrate options: `125 kbps`, `250 kbps`, `500 kbps`, `1 Mbps`
- Default PCAN channel: `PCAN_USBBUS1`

Important notes:

- `PCANBasic.dll` is supplied by the PEAK PCAN-Basic installation.
- This repository should not include `PCANBasic.dll` unless its license and
  redistribution terms are explicitly checked.
- If the PEAK driver is not installed, the app should still open and can be used
  in `virtual` backend mode for offline preview and UI testing.

## Installation From Source

```powershell
git clone https://github.com/ahmetgozcelik/j1939-pcan-simulator.git
cd j1939-pcan-simulator
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Optional editable install for development:

```powershell
pip install -e .
j1939-pcan-simulator
```

For development tests:

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests
.venv\Scripts\python.exe -m compileall main.py src tests
```

## Basic Usage

1. Start the app with `python main.py` or the packaged EXE.
2. Select backend:
   - `PCAN` for PEAK hardware
   - `Virtual` for offline software-only testing
3. Select channel and bitrate.
4. Click `Reconnect`.
5. Open or edit a JSON configuration.
6. Select a message row.
7. Edit J1939 fields such as PGN, priority, source address, and destination/group
   extension directly in the message table.
8. For standard single-frame messages, add/edit signals in the signal panel.
9. For DM1/DM2 messages, use the diagnostic DTC panel for lamp status, SPN, FMI,
   occurrence count, and frame preview.
10. Use `Start Active` to transmit active messages.
11. Use `Stop All` to stop all running message timers.
12. Check the frame log and validation status strip.
13. Save the configuration as JSON.

Panel recovery:

- Use `View > Panels > Frame Log` to reopen the frame log if it is closed.
- Use `View > Panels > Validation Issues` or click the validation status in the
  status bar to inspect validation errors.
- Use `View > Panels > Reset Layout` to return dock panels to the default
  bottom layout.

## Configuration Files

The app loads JSON workspaces from the `configs` directory or any user-selected
path.

Bundled examples:

- `configs/default.json`: compact starter workspace
- `configs/global_j1939_comprehensive.json`: broader J1939-oriented example
- `configs/dm1_definitions.json`: editable lamp/FMI definitions for DM1/DM2 UI

User state is stored outside the repository:

- Recent files and adapter settings: `%USERPROFILE%\.j1939_simulator`
- Recovery backups: `%USERPROFILE%\.j1939_simulator\recovery`

## Project Structure

```text
src/j1939_pcan_simulator/
  app/          application startup, resource paths, error reporting
  config/       workspace models, JSON IO, recovery, adapter settings
  protocol/     SAE J1939 identifiers, frame packing, DM definitions
  transport/    PCAN and virtual CAN backend integration
  simulation/   timers, signal value generation, transmit engine
  validation/   workspace and signal validation rules
  gui/          PyQt widgets, delegates, icons, HMI theme
tests/          protocol, config, UI, and packaging smoke tests
configs/        editable example workspaces and DM definitions
docs/           architecture and release documentation
```

## Workspace JSON Schema

Top-level shape:

```json
{
  "version": "1.0",
  "messages": []
}
```

Message shape:

```json
{
  "can_id": "18F00480",
  "name": "EEC1 - Electronic Engine Controller 1",
  "cycle_ms": 100,
  "active": true,
  "signals": [],
  "dm1_config": null
}
```

Signal shape:

```json
{
  "name": "Engine Speed",
  "byte_pos": 3,
  "bit_pos": 0,
  "bit_length": 16,
  "byte_order": "little_endian",
  "scale": 0.125,
  "offset": 0.0,
  "raw_min": 0,
  "raw_max": 64255,
  "raw_value": 12000,
  "sim_mode": "ramp",
  "unit": "rpm",
  "sine_period_s": 10.0,
  "ramp_step": null,
  "ramp_period_s": 10.0
}
```

DM1/DM2 diagnostic config shape:

```json
{
  "lamp_status": 0,
  "flash_lamp_status": 255,
  "lamp_mode": "fixed",
  "auto_lamp_interval_s": 2.0,
  "fmi": 3,
  "occurrence": 0,
  "spn": 104,
  "spn_mode": "fixed",
  "spn_list": [100, 110, 190, 168],
  "spn_list_interval_s": 2.0,
  "spn_range_min": 0,
  "spn_range_max": 524287,
  "spn_range_interval_s": 2.0
}
```

Supported signal simulation modes:

- `fixed`
- `random`
- `sine`
- `sawtooth`
- `ramp`

Supported diagnostic SPN modes:

- `fixed`
- `list`
- `random_range`

## Build EXE

Install PyInstaller in the virtual environment:

```powershell
.venv\Scripts\activate
pip install pyinstaller
pyinstaller --clean --noconfirm J1939_Simulator.spec
```

Expected output:

```text
dist\J1939_Simulator.exe
```

Packaging notes:

- `configs` must be bundled with the executable.
- `can.interfaces.pcan` and `can.interfaces.virtual` must be available.
- The PEAK driver/runtime should be installed on the target Windows machine.
- `J1939_Simulator.spec` includes `PCANBasic.dll` only when that file exists next
  to the spec file.
- If `PCANBasic.dll` is not bundled, install the PEAK PCAN-Basic runtime on the
  target machine.
- Do not publish `PCANBasic.dll` in this repository unless PEAK's redistribution
  terms have been explicitly checked.

## Release Checklist

Before publishing a GitHub Release:

1. Run tests:

   ```powershell
   .venv\Scripts\python.exe -m unittest discover -s tests
   .venv\Scripts\python.exe -m compileall main.py src tests
   ```

2. Build the EXE:

   ```powershell
   pyinstaller --clean --noconfirm J1939_Simulator.spec
   ```

3. Smoke test without PCAN hardware:
   - Start `dist\J1939_Simulator.exe`.
   - Confirm the app opens even if PCAN is disconnected.
   - Select `Virtual` backend.
   - Click `Reconnect`.
   - Open `configs\default.json`.
   - Start and stop an active message.
   - Confirm the frame log updates and validation status is visible.

4. Smoke test with PCAN hardware:
   - Install the PEAK PCAN-Basic runtime.
   - Connect the PEAK PCAN USB adapter.
   - Select `PCAN`, `PCAN_USBBUS1`, and the correct bitrate.
   - Click `Reconnect`.
   - Send one known test frame and confirm it on the target bus or PCAN-View.

5. Publish the release:

   ```powershell
   git tag v1.0.1
   git push origin main
   git push origin v1.0.1
   gh release create v1.0.1 dist\J1939_Simulator.exe --title "J1939 PCAN Simulator v1.0.1" --notes-file RELEASE_NOTES.md
   ```

Use a different tag if the release version has changed.

## Troubleshooting

### App opens but PCAN shows disconnected

Check:

- PEAK PCAN-Basic driver is installed
- PCAN USB adapter is connected
- Correct channel is selected, usually `PCAN_USBBUS1`
- Bitrate matches the target bus, usually `250 kbps` for J1939
- Another application is not holding the adapter exclusively

Use `Virtual` backend to verify the UI and frame preview without hardware.

### Driver is not loaded

Install or repair the PEAK PCAN-Basic package, then reconnect the adapter and
restart the app.

### Frames are shown in preview but not received by the target ECU

Check:

- Bus bitrate
- 120 ohm termination
- CAN-H/CAN-L wiring
- 29-bit extended identifier support on the receiver
- PGN, source address, destination address/group extension
- Active state and cycle period

### Validation shows signal overlap

Two signals are mapped to the same payload bits. Adjust byte position, bit
position, or bit length until the validation status returns to `OK`.

### DM1/DM2 panel does not show expected lamp/FMI labels

Edit `configs/dm1_definitions.json`, then click `Reload` in the diagnostic DTC
panel.

### New configuration replaced current work

Recovery backups are written before destructive open/new actions when the
current workspace has messages. Check:

```text
%USERPROFILE%\.j1939_simulator\recovery
```

## Known Limitations

- Transport Protocol is planned but not implemented.
- DM1/DM2 currently focus on one DTC payload in a single 8-byte frame.
- Standard PGN/SPN definitions are examples, not a complete licensed SAE
  database.
- PCAN hardware behavior must be verified on the target Windows machine.
- The virtual backend is for software smoke testing; it does not prove physical
  bus wiring, bitrate, or adapter driver health.

## Turkish Summary

- Gercek PCAN gonderimi icin PEAK driver kurulu olmalidir.
- PCAN yoksa `Virtual` backend ile arayuz ve frame preview test edilebilir.
- J1939 mesajlari 29-bit extended CAN ID olarak modellenir.
- DM1 `0x00FECA`, DM2 `0x00FECB` PGN'leri diagnostik DTC panelini acar.
- TP/multi-packet mesajlar henuz desteklenmez.

Kaynak koddan calistirma:

```powershell
git clone https://github.com/ahmetgozcelik/j1939-pcan-simulator.git
cd j1939-pcan-simulator
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
python main.py
```

Temel kullanim akisi:

1. Backend sec: `PCAN` veya `Virtual`.
2. Channel ve bitrate sec.
3. `Reconnect` ile baglan.
4. JSON config ac veya duzenle.
5. Mesaj/sinyal veya DM1/DM2 diagnostik alanlarini duzenle.
6. `Start Active` ile aktif mesajlari baslat.
7. Log ve validation satirini kontrol et.
8. Config dosyasini kaydet.

## License

MIT License.
