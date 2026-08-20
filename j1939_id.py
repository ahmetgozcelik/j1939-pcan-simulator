"""SAE J1939 29-bit CAN identifier helpers.

This module is intentionally UI- and hardware-free. It centralizes J1939 ID
parsing so config, simulator, and future UI validation use the same rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional


MAX_CAN_ID_29 = 0x1FFFFFFF
MAX_PGN = 0x3FFFF

PDU2_PF_MIN = 0xF0

PGN_REQUEST = 0x00EA00
PGN_TP_DT = 0x00EB00
PGN_TP_CM = 0x00EC00
PGN_PROPRIETARY_A = 0x00EF00
PGN_DM1 = 0x00FECA
PGN_PROPRIETARY_B_MIN = 0x00FF00
PGN_PROPRIETARY_B_MAX = 0x00FFFF


class PgnCategory(str, Enum):
    STANDARD = "standard"
    REQUEST = "request"
    TRANSPORT = "transport"
    DIAGNOSTIC = "diagnostic"
    PROPRIETARY_A = "proprietary_a"
    PROPRIETARY_B = "proprietary_b"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class J1939Id:
    can_id: int
    priority: int
    edp: int
    dp: int
    pf: int
    ps: int
    source_address: int
    pgn: int

    @property
    def is_pdu1(self) -> bool:
        return self.pf < PDU2_PF_MIN

    @property
    def is_pdu2(self) -> bool:
        return not self.is_pdu1

    @property
    def destination_address(self) -> Optional[int]:
        return self.ps if self.is_pdu1 else None

    @property
    def group_extension(self) -> Optional[int]:
        return self.ps if self.is_pdu2 else None

    @property
    def category(self) -> PgnCategory:
        return classify_pgn(self.pgn)

    def to_hex(self) -> str:
        return format_can_id(self.can_id)


def parse_can_id(value: int | str) -> J1939Id:
    can_id = _parse_can_id_value(value)
    priority = (can_id >> 26) & 0x07
    edp = (can_id >> 25) & 0x01
    dp = (can_id >> 24) & 0x01
    pf = (can_id >> 16) & 0xFF
    ps = (can_id >> 8) & 0xFF
    source_address = can_id & 0xFF
    pgn = pgn_from_fields(edp=edp, dp=dp, pf=pf, ps=ps)
    return J1939Id(
        can_id=can_id,
        priority=priority,
        edp=edp,
        dp=dp,
        pf=pf,
        ps=ps,
        source_address=source_address,
        pgn=pgn,
    )


def pgn_from_fields(*, edp: int, dp: int, pf: int, ps: int) -> int:
    _require_bit("edp", edp)
    _require_bit("dp", dp)
    _require_byte("pf", pf)
    _require_byte("ps", ps)
    pdu_specific = ps if pf >= PDU2_PF_MIN else 0
    return (edp << 17) | (dp << 16) | (pf << 8) | pdu_specific


def build_can_id(
    *,
    priority: int,
    pgn: int,
    source_address: int,
    destination_address: Optional[int] = None,
    group_extension: Optional[int] = None,
) -> int:
    _require_range("priority", priority, 0, 7)
    _require_range("pgn", pgn, 0, MAX_PGN)
    _require_byte("source_address", source_address)

    edp = (pgn >> 17) & 0x01
    dp = (pgn >> 16) & 0x01
    pf = (pgn >> 8) & 0xFF

    if pf < PDU2_PF_MIN:
        if pgn & 0xFF:
            raise ValueError("PDU1 PGNs must not include a destination byte")
        ps = 0xFF if destination_address is None else destination_address
        _require_byte("destination_address", ps)
    else:
        ps = pgn & 0xFF if group_extension is None else group_extension
        _require_byte("group_extension", ps)

    return (
        (priority << 26)
        | (edp << 25)
        | (dp << 24)
        | (pf << 16)
        | (ps << 8)
        | source_address
    )


def format_can_id(value: int | str) -> str:
    return f"{_parse_can_id_value(value):08X}"


def classify_pgn(pgn: int) -> PgnCategory:
    if not isinstance(pgn, int) or pgn < 0 or pgn > MAX_PGN:
        return PgnCategory.UNKNOWN
    if pgn == PGN_REQUEST:
        return PgnCategory.REQUEST
    if pgn in (PGN_TP_CM, PGN_TP_DT):
        return PgnCategory.TRANSPORT
    if pgn == PGN_DM1:
        return PgnCategory.DIAGNOSTIC
    if pgn == PGN_PROPRIETARY_A:
        return PgnCategory.PROPRIETARY_A
    if PGN_PROPRIETARY_B_MIN <= pgn <= PGN_PROPRIETARY_B_MAX:
        return PgnCategory.PROPRIETARY_B
    return PgnCategory.STANDARD


def is_dm1_can_id(value: int | str) -> bool:
    try:
        return parse_can_id(value).pgn == PGN_DM1
    except ValueError:
        return False


def _parse_can_id_value(value: int | str) -> int:
    if isinstance(value, int):
        can_id = value
    elif isinstance(value, str):
        cleaned = value.strip().upper().replace("0X", "").replace(" ", "")
        if not cleaned:
            raise ValueError("CAN ID cannot be empty")
        can_id = int(cleaned, 16)
    else:
        raise TypeError(f"CAN ID must be int or hex str, got {type(value).__name__}")
    _require_range("can_id", can_id, 0, MAX_CAN_ID_29)
    return can_id


def _require_bit(name: str, value: int) -> None:
    _require_range(name, value, 0, 1)


def _require_byte(name: str, value: int) -> None:
    _require_range(name, value, 0, 0xFF)


def _require_range(name: str, value: int, low: int, high: int) -> None:
    if not isinstance(value, int) or value < low or value > high:
        raise ValueError(f"{name} must be in {low}..{high}, got {value!r}")
