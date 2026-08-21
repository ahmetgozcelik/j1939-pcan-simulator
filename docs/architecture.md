# Architecture

This repository is intended to be public and CV-friendly: source code,
documentation, tests, and release notes live together in one clean Python
project. Local task notes, virtual environments, build outputs, runtime state,
and PCAN runtime DLLs remain ignored.

## Source Layout

```text
src/j1939_pcan_simulator/
  app/          application startup, runtime paths, error reporting
  config/       workspace dataclasses, JSON IO, recovery, adapter settings
  protocol/     SAE J1939 identifiers, frame packing, DM definitions
  transport/    PCAN and virtual python-can backends
  simulation/   timers, value generation, transmit engine
  validation/   workspace and signal validators
  gui/          PyQt widgets, delegates, icons, theme, waveform preview
tests/
configs/
docs/
```

## Ownership Rules

- `protocol` has no PyQt or hardware dependency.
- `config` owns JSON serialization and local app state paths.
- `validation` works on config models and protocol helpers only.
- `transport` owns `python-can`, PCAN, and virtual bus details.
- `simulation` coordinates timers, generated values, and transmit calls.
- `gui` owns PyQt widgets and emits model-level changes instead of encoding
  protocol rules directly.
- `app` wires startup concerns such as resource paths, global error reporting,
  and the top-level application entry point.

## J1939 Boundaries

- All CAN identifiers are treated as 29-bit extended SAE J1939 IDs.
- PGN parsing follows the PDU rule:
  - PDU1 (`PF < 240`): `PS` is destination address and is excluded from PGN.
  - PDU2 (`PF >= 240`): `PS` is group extension and is included in PGN.
- Single-frame messages are packed into 8-byte payloads initialized with
  `0xFF` for not-available fields.
- DM diagnostic payloads use data-driven lamp/FMI definitions from
  `configs/dm1_definitions.json`.

## Packaging

`main.py` is intentionally a thin launcher. It adds `src/` to `sys.path` for
source-checkout execution, then calls `j1939_pcan_simulator.app.main`.

`J1939_Simulator.spec` bundles:

- `configs/`
- `src/j1939_pcan_simulator/gui/theme.qss`
- optional `PCANBasic.dll` when it exists next to the spec file

## Development Checks

```powershell
.venv\Scripts\python.exe -m unittest discover -s tests
.venv\Scripts\python.exe -m compileall main.py src tests
```
