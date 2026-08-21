"""External DM1 definitions for J1939 diagnostics UI and simulation."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List

from j1939_pcan_simulator.app.paths import config_path

CONFIG_PATH = config_path("dm1_definitions.json")


DEFAULT_FMI_DESCRIPTIONS = {
    0: "Above normal / most severe",
    1: "Below normal / most severe",
    2: "Erratic, intermittent or incorrect",
    3: "Voltage above normal",
    4: "Voltage below normal",
    5: "Current below normal / open circuit",
    6: "Current above normal / grounded",
    7: "Mechanical system not responding",
    8: "Abnormal frequency / pulse width",
    9: "Abnormal update rate",
    10: "Abnormal rate of change",
    11: "Root cause unknown",
    12: "Bad intelligent device or component",
    13: "Out of calibration",
    14: "Special instructions",
    15: "Above normal / least severe",
    16: "Above normal / moderately severe",
    17: "Below normal / least severe",
    18: "Below normal / moderately severe",
    19: "Network error",
    20: "Data drifted high",
    21: "Data drifted low",
    31: "Condition exists",
}


@dataclass(frozen=True)
class LampDefinition:
    key: str
    label: str
    bit: int


@dataclass(frozen=True)
class DM1Definitions:
    lamps: List[LampDefinition]
    fmi_descriptions: Dict[int, str]

    @property
    def lamp_keys(self) -> List[str]:
        return [lamp.key for lamp in self.lamps]


DEFAULT_LAMPS = [
    LampDefinition("red", "Red Stop Lamp", 4),
    LampDefinition("amber", "Amber Warning Lamp", 2),
    LampDefinition("protect", "Protect Lamp", 0),
    LampDefinition("mil", "MIL (Malfunction Indicator Lamp)", 6),
]


DEFAULT_DEFINITIONS = DM1Definitions(
    lamps=DEFAULT_LAMPS,
    fmi_descriptions=DEFAULT_FMI_DESCRIPTIONS,
)


def load_dm1_definitions(path: Path | str = CONFIG_PATH) -> DM1Definitions:
    """Load DM1 display definitions from JSON, falling back to SAE-safe defaults."""
    path = Path(path)
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
        return _parse_definitions(payload)
    except (OSError, ValueError, TypeError, json.JSONDecodeError):
        return DEFAULT_DEFINITIONS


def _parse_definitions(payload: dict) -> DM1Definitions:
    if not isinstance(payload, dict):
        raise ValueError("DM1 definitions must be a JSON object")

    lamps = _parse_lamps(payload.get("lamp_statuses", []))
    if not lamps:
        lamps = DEFAULT_LAMPS

    fmi_payload = payload.get("fmi_descriptions", {})
    fmi_descriptions = dict(DEFAULT_FMI_DESCRIPTIONS)
    if isinstance(fmi_payload, dict):
        for key, value in fmi_payload.items():
            fmi = int(key)
            if 0 <= fmi <= 31:
                fmi_descriptions[fmi] = str(value)

    return DM1Definitions(lamps=lamps, fmi_descriptions=fmi_descriptions)


def _parse_lamps(entries: Iterable[dict]) -> List[LampDefinition]:
    lamps: List[LampDefinition] = []
    seen_keys = set()
    seen_bits = set()
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        key = str(entry.get("key", "")).strip().lower()
        label = str(entry.get("label", "")).strip()
        bit = int(entry.get("bit"))
        if not key or not label:
            continue
        if bit not in (0, 2, 4, 6):
            raise ValueError("DM1 lamp bit must be one of 0, 2, 4, 6")
        if key in seen_keys or bit in seen_bits:
            raise ValueError("DM1 lamp keys and bits must be unique")
        seen_keys.add(key)
        seen_bits.add(bit)
        lamps.append(LampDefinition(key=key, label=label, bit=bit))
    return lamps


def set_lamp(byte_val: int, key: str, on: bool, definitions: DM1Definitions) -> int:
    lamp = _lamp_by_key(key, definitions)
    mask = 0b11 << lamp.bit
    byte_val &= ~mask & 0xFF
    if on:
        byte_val |= (0b01 << lamp.bit) & 0xFF
    return byte_val


def get_lamp(byte_val: int, key: str, definitions: DM1Definitions) -> bool:
    lamp = _lamp_by_key(key, definitions)
    return ((byte_val >> lamp.bit) & 0b11) == 0b01


def auto_lamp_steps(definitions: DM1Definitions) -> List[List[str]]:
    """Return the configured auto cycle, preserving standard DM1 lamp semantics."""
    available = set(definitions.lamp_keys)
    preferred = [["red"], ["amber"], ["protect"], ["red", "amber", "protect"]]
    steps = [[key for key in step if key in available] for step in preferred]
    steps = [step for step in steps if step]
    if steps:
        return steps
    return [[lamp.key] for lamp in definitions.lamps]


def lamp_sequence_label(definitions: DM1Definitions) -> str:
    labels = {lamp.key: lamp.label for lamp in definitions.lamps}
    steps = []
    for step in auto_lamp_steps(definitions):
        steps.append(" + ".join(labels.get(key, key) for key in step))
    return "Cycle: " + " -> ".join(steps)


def build_lamp_status(keys: Iterable[str], definitions: DM1Definitions) -> int:
    byte_val = 0x00
    for key in keys:
        byte_val = set_lamp(byte_val, key, True, definitions)
    return byte_val


def _lamp_by_key(key: str, definitions: DM1Definitions) -> LampDefinition:
    for lamp in definitions.lamps:
        if lamp.key == key:
            return lamp
    raise KeyError(f"Unknown DM1 lamp key: {key}")

