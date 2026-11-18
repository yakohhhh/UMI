"""The two checksums of the session log.

CRC-16/CCITT-FALSE protects each record (cheap enough to run per record on the
Clip); CRC-32/ISO-HDLC, the zlib one, protects the header and the whole file.
Both functions take the running value so a writer can checksum as it streams.
"""

from __future__ import annotations

import binascii
import zlib
from collections.abc import Buffer

CRC16_INIT = 0xFFFF


def crc16_ccitt_false(data: Buffer, crc: int = CRC16_INIT) -> int:
    """CRC-16/CCITT-FALSE: poly 0x1021, init 0xFFFF, no reflection, no final xor."""
    # crc_hqx is the same non-reflected 0x1021 CRC with a caller-chosen init, in C.
    return binascii.crc_hqx(data, crc)


def crc32_iso_hdlc(data: Buffer, crc: int = 0) -> int:
    """CRC-32/ISO-HDLC, identical to ``zlib.crc32``; pass the previous value to continue."""
    return zlib.crc32(data, crc)
