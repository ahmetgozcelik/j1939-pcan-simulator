"""8-byte CAN çerçevesi (frame) oluşturma ve fiziksel <-> ham dönüşümler.

Bu modül saf fonksiyonlardan oluşur ve hiçbir UI / donanım bağımlılığı içermez,
böylece kolayca test edilebilir.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from config_manager import Message, Signal


FRAME_LEN = 8


# ---------------------------------------------------------------------------
# Ham <-> Fiziksel dönüşümler
# ---------------------------------------------------------------------------


def physical_to_raw(phys: float, scale: float, offset: float) -> int:
    """Fiziksel değeri ham'a çevirir (yuvarlanır)."""
    if scale == 0:
        return 0
    return int(round((phys - offset) / scale))


def raw_to_physical(raw: int, scale: float, offset: float) -> float:
    return raw * scale + offset


# ---------------------------------------------------------------------------
# Bit paketleme
# ---------------------------------------------------------------------------


def _set_bit(frame: bytearray, byte_idx: int, bit_idx: int, value: int) -> None:
    if byte_idx < 0 or byte_idx >= len(frame):
        raise ValueError(
            f"Bit pozisyonu çerçeve sınırlarının dışında: byte={byte_idx}"
        )
    if value:
        frame[byte_idx] = (frame[byte_idx] | (1 << bit_idx)) & 0xFF
    else:
        frame[byte_idx] = frame[byte_idx] & (~(1 << bit_idx) & 0xFF)


def pack_signal(
    frame: bytearray,
    raw: int,
    byte_pos: int,
    bit_pos: int,
    bit_length: int,
    byte_order: str,
) -> None:
    """Bir tamsayı ham değeri 8 byte'lık ``frame``'in içine yerleştirir.

    little_endian (Intel): ``(byte_pos, bit_pos)`` LSB konumudur, bitler yukarı
    doğru ilerler ve byte taşınca bir sonraki byte'ın bit 0'ına geçer.

    big_endian (Motorola): ``(byte_pos, bit_pos)`` MSB konumudur, bitler aşağı
    doğru iner ve byte taşınca bir sonraki byte'ın bit 7'sine geçer.
    """
    if bit_length <= 0 or bit_length > 64:
        raise ValueError(f"bit_length aralık dışı: {bit_length}")
    if not 0 <= bit_pos <= 7:
        raise ValueError(f"bit_pos 0-7 olmalı: {bit_pos}")

    # 0 .. (2**bit_length - 1) aralığına maskele.
    mask = (1 << bit_length) - 1
    raw_u = raw & mask

    if byte_order == "little_endian":
        for i in range(bit_length):
            bit_val = (raw_u >> i) & 1
            abs_bit = byte_pos * 8 + bit_pos + i
            tb = abs_bit // 8
            tbit = abs_bit % 8
            _set_bit(frame, tb, tbit, bit_val)
    elif byte_order == "big_endian":
        cur_byte = byte_pos
        cur_bit = bit_pos
        # MSB'den LSB'ye doğru yazıyoruz: en yüksek anlamlı bit önce.
        for i in range(bit_length - 1, -1, -1):
            bit_val = (raw_u >> i) & 1
            _set_bit(frame, cur_byte, cur_bit, bit_val)
            if cur_bit == 0:
                cur_byte += 1
                cur_bit = 7
            else:
                cur_bit -= 1
    else:
        raise ValueError(f"Bilinmeyen byte_order: {byte_order}")


def clamp_raw(value: float, signal: Signal) -> int:
    """Sinyal min/max + bit_length sınırlarına göre ``value``'yu kırpar."""
    lo = min(signal.raw_min, signal.raw_max)
    hi = max(signal.raw_min, signal.raw_max)
    v = int(round(value))
    if v < lo:
        v = lo
    elif v > hi:
        v = hi
    upper = (1 << signal.bit_length) - 1
    if v < 0:
        v = 0
    if v > upper:
        v = upper
    return v


def build_frame(message: Message, raw_overrides: dict | None = None) -> bytes:
    """Mesajdaki tüm sinyalleri yerleştirip 8 baytlık çerçeveyi döner.

    ``raw_overrides`` verilirse, sinyalin yerine geçici bir ham değer kullanılır.
    Bu özellik canlı önizleme / simülasyon motoru için kullanışlıdır.
    """
    frame = bytearray(b"\xFF" * FRAME_LEN)
    for sig in message.signals:
        raw = (
            raw_overrides[id(sig)]
            if raw_overrides and id(sig) in raw_overrides
            else sig.raw_value
        )
        raw = clamp_raw(raw, sig)
        try:
            pack_signal(
                frame,
                raw,
                sig.byte_pos,
                sig.bit_pos,
                sig.bit_length,
                sig.byte_order,
            )
        except ValueError:
            # Hatalı sinyal varsa onu atla; geri kalanı çerçeveye ekleyebilelim.
            continue
    return bytes(frame)


# ---------------------------------------------------------------------------
# DM1 (J1939-73) çerçeve oluşturucu
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DiagnosticTroubleCode:
    spn: int
    fmi: int
    occurrence_count: int
    conversion_method: int = 0


def build_dm1_frame(
    lamp_status: int,
    spn: int,
    fmi: int,
    oc: int,
    flash_lamp_status: int = 0xFF,
    conversion_method: int = 0,
) -> bytes:
    """Tek bir DTC içeren DM1 çerçevesi.

    J1939-73 tek-frame DM1 düzeni:
        Byte 0: lamp_status
        Byte 1: flash_lamp_status
        Byte 2: SPN[0:7]
        Byte 3: SPN[8:15]
        Byte 4: (SPN[16:18] << 5) | (FMI & 0x1F)
        Byte 5: occurrence count (0..126) + conversion method bit 7
        Byte 6: 0xFF
        Byte 7: 0xFF
    """
    return build_dm1_frame_from_dtcs(
        lamp_status,
        [DiagnosticTroubleCode(spn, fmi, oc, conversion_method)],
        flash_lamp_status=flash_lamp_status,
    )


def build_dm1_frame_from_dtcs(
    lamp_status: int,
    dtcs: Iterable[DiagnosticTroubleCode],
    flash_lamp_status: int = 0xFF,
) -> bytes:
    """Build a single-frame DM1 payload.

    A single 8-byte DM1 frame can carry lamp status, flash lamp status, and at
    most one DTC. More DTCs require J1939 Transport Protocol support.
    """
    dtc_list = list(dtcs)
    if len(dtc_list) > 1:
        raise ValueError("Multiple DM1 DTCs require J1939 Transport Protocol")

    frame = bytearray(b"\xFF" * FRAME_LEN)
    frame[0] = lamp_status & 0xFF
    frame[1] = flash_lamp_status & 0xFF
    if not dtc_list:
        return bytes(frame)

    _pack_dm1_dtc(frame, 2, dtc_list[0])
    return bytes(frame)


def _pack_dm1_dtc(frame: bytearray, start_byte: int, dtc: DiagnosticTroubleCode) -> None:
    spn = dtc.spn
    fmi = dtc.fmi
    oc = dtc.occurrence_count
    conversion_method = dtc.conversion_method

    if not 0 <= spn <= 0x7FFFF:
        raise ValueError(f"SPN must be in 0..524287, got {spn!r}")
    if not 0 <= fmi <= 0x1F:
        raise ValueError(f"FMI must be in 0..31, got {fmi!r}")
    if not 0 <= oc <= 0x7E:
        raise ValueError(f"Occurrence count must be in 0..126, got {oc!r}")
    if conversion_method not in (0, 1):
        raise ValueError(f"Conversion method must be 0 or 1, got {conversion_method!r}")

    spn &= 0x7FFFF
    fmi &= 0x1F
    oc &= 0x7F
    frame[start_byte] = spn & 0xFF
    frame[start_byte + 1] = (spn >> 8) & 0xFF
    frame[start_byte + 2] = (((spn >> 16) & 0x07) << 5) | fmi
    frame[start_byte + 3] = ((conversion_method & 0x01) << 7) | oc


# ---------------------------------------------------------------------------
# Yardımcı: byte dizisini hex string olarak döner
# ---------------------------------------------------------------------------


def format_bytes(data: Iterable[int]) -> str:
    return " ".join(f"{b:02X}" for b in data)
