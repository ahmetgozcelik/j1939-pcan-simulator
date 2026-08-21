"""Workspace validation for J1939 simulator configs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable, Optional

from j1939_pcan_simulator.config.workspace import Message, Signal, Workspace
from j1939_pcan_simulator.config.workspace import VALID_BYTE_ORDERS, VALID_SIM_MODES
from j1939_pcan_simulator.protocol.identifier import format_can_id, parse_can_id


FRAME_BITS = 64


@dataclass(frozen=True)
class ValidationIssue:
    severity: str
    code: str
    message: str
    message_index: Optional[int] = None
    signal_index: Optional[int] = None
    field: str = ""


def validate_workspace(workspace: Workspace) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    seen_ids: dict[str, int] = {}

    for msg_index, msg in enumerate(workspace.messages):
        can_id_hex = _normalized_can_id(msg)
        if can_id_hex is None:
            issues.append(_issue(
                "error",
                "invalid_can_id",
                f"Message CAN ID is not a valid 29-bit J1939 ID: {msg.can_id!r}",
                msg_index,
                field="can_id",
            ))
        elif can_id_hex in seen_ids:
            first = seen_ids[can_id_hex]
            issues.append(_issue(
                "error",
                "duplicate_can_id",
                f"CAN ID {can_id_hex} is duplicated by messages {first + 1} and {msg_index + 1}",
                msg_index,
                field="can_id",
            ))
        else:
            seen_ids[can_id_hex] = msg_index

        if msg.cycle_ms < 1:
            issues.append(_issue(
                "error",
                "invalid_cycle_ms",
                "Cycle time must be at least 1 ms",
                msg_index,
                field="cycle_ms",
            ))

        issues.extend(validate_message(msg, msg_index))

    return issues


def validate_message(
    message: Message,
    message_index: Optional[int] = None,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []
    used_bits: dict[int, int] = {}

    for sig_index, sig in enumerate(message.signals):
        sig_issues = validate_signal(sig, message_index, sig_index)
        issues.extend(sig_issues)
        if any(i.code in {"invalid_bit_layout", "signal_out_of_frame"} for i in sig_issues):
            continue

        bits = list(signal_bit_positions(sig))
        for bit in bits:
            prev_sig_index = used_bits.get(bit)
            if prev_sig_index is not None:
                issues.append(_issue(
                    "error",
                    "signal_overlap",
                    (
                        f"Signal {sig_index + 1} overlaps signal {prev_sig_index + 1} "
                        f"at frame bit {bit}"
                    ),
                    message_index,
                    sig_index,
                    field="bit_layout",
                ))
                break
            used_bits[bit] = sig_index

    return issues


def validate_signal(
    signal: Signal,
    message_index: Optional[int] = None,
    signal_index: Optional[int] = None,
) -> list[ValidationIssue]:
    issues: list[ValidationIssue] = []

    if signal.byte_order not in VALID_BYTE_ORDERS:
        issues.append(_issue(
            "error",
            "invalid_byte_order",
            f"Byte order must be one of {', '.join(VALID_BYTE_ORDERS)}",
            message_index,
            signal_index,
            field="byte_order",
        ))

    if signal.sim_mode not in VALID_SIM_MODES:
        issues.append(_issue(
            "error",
            "invalid_sim_mode",
            f"Simulation mode must be one of {', '.join(VALID_SIM_MODES)}",
            message_index,
            signal_index,
            field="sim_mode",
        ))

    if signal.scale == 0:
        issues.append(_issue(
            "error",
            "zero_scale",
            "Scale must not be zero",
            message_index,
            signal_index,
            field="scale",
        ))

    if not (0 <= signal.byte_pos <= 7 and 0 <= signal.bit_pos <= 7 and 1 <= signal.bit_length <= 64):
        issues.append(_issue(
            "error",
            "invalid_bit_layout",
            "Byte position, bit position, and bit length must describe a valid J1939 signal layout",
            message_index,
            signal_index,
            field="bit_layout",
        ))
    else:
        bits = list(signal_bit_positions(signal))
        if not bits or min(bits) < 0 or max(bits) >= FRAME_BITS:
            issues.append(_issue(
                "error",
                "signal_out_of_frame",
                "Signal bit layout extends outside the 8-byte J1939 frame",
                message_index,
                signal_index,
                field="bit_layout",
            ))

    max_raw_for_length = (1 << signal.bit_length) - 1 if 1 <= signal.bit_length <= 64 else None
    lo = min(signal.raw_min, signal.raw_max)
    hi = max(signal.raw_min, signal.raw_max)

    if signal.raw_min < 0 or signal.raw_max < 0 or signal.raw_value < 0:
        issues.append(_issue(
            "error",
            "negative_raw_value",
            "Raw min, max, and current value must be unsigned",
            message_index,
            signal_index,
            field="raw",
        ))

    if max_raw_for_length is not None and hi > max_raw_for_length:
        issues.append(_issue(
            "error",
            "raw_range_exceeds_bit_length",
            f"Raw range exceeds {signal.bit_length}-bit maximum {max_raw_for_length}",
            message_index,
            signal_index,
            field="raw_max",
        ))

    if not (lo <= signal.raw_value <= hi):
        issues.append(_issue(
            "error",
            "raw_value_out_of_range",
            "Current raw value must be between raw min and raw max",
            message_index,
            signal_index,
            field="raw_value",
        ))

    return issues


def signal_bit_positions(signal: Signal) -> Iterable[int]:
    if signal.byte_order == "little_endian":
        start = signal.byte_pos * 8 + signal.bit_pos
        for offset in range(signal.bit_length):
            yield start + offset
        return

    if signal.byte_order == "big_endian":
        cur_byte = signal.byte_pos
        cur_bit = signal.bit_pos
        for _ in range(signal.bit_length):
            yield cur_byte * 8 + cur_bit
            if cur_bit == 0:
                cur_byte += 1
                cur_bit = 7
            else:
                cur_bit -= 1


def has_errors(issues: Iterable[ValidationIssue]) -> bool:
    return any(issue.severity == "error" for issue in issues)


def _normalized_can_id(message: Message) -> Optional[str]:
    try:
        parsed = parse_can_id(message.can_id)
        return format_can_id(parsed.can_id)
    except (TypeError, ValueError):
        return None


def _issue(
    severity: str,
    code: str,
    message: str,
    message_index: Optional[int],
    signal_index: Optional[int] = None,
    field: str = "",
) -> ValidationIssue:
    return ValidationIssue(
        severity=severity,
        code=code,
        message=message,
        message_index=message_index,
        signal_index=signal_index,
        field=field,
    )

