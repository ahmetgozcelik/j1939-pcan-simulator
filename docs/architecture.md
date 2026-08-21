# Architecture Plan

This private source repository keeps the full application code. Public
distribution should happen through a separate repository that contains only
documentation, screenshots, issue templates, and release assets.

## Repository Model

```text
j1939-pcan-simulator         private source repository
j1939-pcan-simulator-public  public distribution and issue repository
```

The public repository must not contain Python source, private configs, build
intermediates, virtual environments, local task files, or PCAN runtime DLLs.

## Target Source Layout

The current project is intentionally kept stable while release packaging is
being prepared. Future refactors should move code toward this package layout:

```text
src/j1939_pcan_simulator/
  app/          application startup and window orchestration
  config/       workspace models, JSON IO, recovery, settings
  protocol/     SAE J1939 identifier parsing and frame packing
  transport/    PCAN, virtual CAN, future SocketCAN adapters
  simulation/   timers, value generation, transmit engine
  validation/   workspace and signal validators
  gui/          PyQt widgets, theme, delegates, icons
tests/
configs/
docs/
tools/
```

## Refactor Rules

- Keep behavior unchanged during package migration.
- Move one ownership boundary at a time.
- Add compatibility imports when needed so tests can move gradually.
- Keep protocol logic independent from PyQt and hardware.
- Keep transport logic independent from UI widgets.
- Keep config serialization independent from PCAN.
- Run tests after every move.

## Suggested Migration Order

1. Move protocol modules:
   - `j1939_id.py` -> `src/j1939_pcan_simulator/protocol/identifier.py`
   - `frame_builder.py` -> `src/j1939_pcan_simulator/protocol/frame_builder.py`
   - `dm1_definitions.py` -> `src/j1939_pcan_simulator/protocol/dm_definitions.py`
2. Move config and validation:
   - `config_manager.py` -> `src/j1939_pcan_simulator/config/workspace.py`
   - `validators.py` -> `src/j1939_pcan_simulator/validation/workspace.py`
3. Move transport and simulation:
   - `can_interface.py` -> `src/j1939_pcan_simulator/transport/can_bus.py`
   - `simulator_engine.py` -> `src/j1939_pcan_simulator/simulation/engine.py`
4. Move UI:
   - `gui/` -> `src/j1939_pcan_simulator/gui/`
5. Convert `main.py` into a thin entry point that imports from the package.
6. Update PyInstaller spec, tests, and README paths.

## Public Repository Export

The public repository is generated from allowlisted assets only:

- `README.md`
- `RELEASE_NOTES.md`
- `.github/ISSUE_TEMPLATE/*.yml`
- `docs/images/*`
- optional `dist/J1939_Simulator.exe`

Use:

```powershell
.venv\Scripts\python.exe tools\prepare_public_repo.py --include-exe
```

The output is written to `public_release/`, which is ignored by Git.
