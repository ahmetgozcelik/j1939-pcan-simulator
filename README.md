# J1939 PCAN Simulator

A PyQt5 desktop application that simulates J1939 CAN messages on a PEAK PCAN-USB
adapter. The user defines messages and signals externally (no hardcoded PGNs),
configures simulation parameters per signal, and persists everything to JSON.

## Features

- Define CAN messages (extended ID) and SPN-style signals from the GUI.
- Per-signal byte/bit packing, scale/offset, min/max, units.
- Four simulation modes per signal: Fixed, Random, Sine, Ramp.
- Special DM1 panel (lamps + SPN/FMI/OC) for diagnostic messages.
- Live preview of the 8-byte CAN frame as you edit.
- Frame log of the last 100 transmissions.
- Save/Load workspace as JSON, plus auto-save on exit and recent-files menu.
- Dark theme.
- Works offline (PCAN disconnected) so frame building can be validated without
hardware.

## Hardware / Driver

- Tested with a PEAK PCAN-USB adapter and DSE M640 PLC.
- Bitrate: 250 kbit/s (J1939 standard).
- Channel: `PCAN_USBBUS1`.
- Requires the PEAK PCAN-Basic driver to be installed on Windows
(it provides `PCANBasic.dll`, used by `python-can`).

## Install

```
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```
python main.py
```

On first launch the app loads `configs/default.json` (a starter workspace with
the typical J1939 PGNs: EFL/P1, HOURS, DM1, VD, EEC1, VEP1). Subsequent
launches reload the last opened config.

## File layout

```
j1939_simulator/
├── main.py
├── can_interface.py
├── frame_builder.py
├── simulator_engine.py
├── config_manager.py
├── gui/
│   ├── main_window.py
│   ├── message_panel.py
│   ├── signal_panel.py
│   ├── signal_detail.py
│   ├── dm1_panel.py
│   └── log_panel.py
├── configs/
│   └── default.json
└── requirements.txt
```

## JSON format

```json
{
  "version": "1.0",
  "messages": [
    {
      "can_id": "18FEF100",
      "name": "ET1 - Engine Temperature",
      "cycle_ms": 1000,
      "active": true,
      "signals": [
        {
          "name": "Engine Coolant Temp",
          "byte_pos": 0,
          "bit_pos": 0,
          "bit_length": 8,
          "byte_order": "little_endian",
          "scale": 1.0,
          "offset": -40.0,
          "raw_min": 0,
          "raw_max": 250,
          "raw_value": 100,
          "sim_mode": "fixed",
          "unit": "°C"
        }
      ]
    }
  ]
}
```

## Notes

- All values entered by the user can be expressed as physical or raw — the app
converts internally.
- DM1 messages are detected by name containing "DM1" or by the CAN ID ending in
`CA00` and use a dedicated panel.

