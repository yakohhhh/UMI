"""Sensor frames as the Clip's UARTs receive them: NMEA 0183 sentences and Plantower PM frames.

These are what ``firmware/lib/umi_drivers`` parses (``nmea.c``, ``pms.c``), so a
scenario exercises the real parsers, checksums included.
"""

from __future__ import annotations

import struct
from datetime import datetime
from functools import reduce

from .sensors import GnssEpoch, PmFrame

_KNOT_MS = 1852 / 3600
# Barcelona's geoid separation (EGM96), carried in GGA for completeness.
_GEOID_SEPARATION_M = 49.5

_PMS_START = b"\x42\x4d"
_PMS_BODY_LEN = 28
# Particles per 0.1 L above 0.3, 0.5, 1, 2.5, 5 and 10 µm, per µg/m³ of PM2.5 (or PM10
# for the coarse bins): a typical urban size distribution.
_COUNTS_PER_PM25 = (60.0, 18.0, 3.0, 0.4)
_COUNTS_PER_PM10 = (0.1, 0.02)


def nmea_checksum(body: str) -> str:
    """XOR of every character between ``$`` and ``*``, as two uppercase hex digits."""
    return f"{reduce(lambda acc, c: acc ^ ord(c), body, 0):02X}"


def nmea_sentence(body: str) -> str:
    return f"${body}*{nmea_checksum(body)}"


def _coordinate(value: float, degree_digits: int, positive: str, negative: str) -> tuple[str, str]:
    """``(d)ddmm.mmmmm`` and its hemisphere letter."""
    magnitude = abs(value)
    degrees = int(magnitude)
    minutes = round((magnitude - degrees) * 60, 5)
    if minutes >= 60:
        degrees, minutes = degrees + 1, minutes - 60
    return f"{degrees:0{degree_digits}d}{minutes:08.5f}", positive if value >= 0 else negative


def _utc_time(at: datetime) -> str:
    return f"{at:%H%M%S}.{at.microsecond // 10000:02d}"


def gnrmc(epoch: GnssEpoch, at: datetime) -> str:
    """Recommended minimum data: time, status, position, speed over ground (knots), course, date."""
    if not epoch.fixed:
        return nmea_sentence(f"GNRMC,{_utc_time(at)},V,,,,,,,{at:%d%m%y},,,N")
    lat, ns = _coordinate(epoch.lat, 2, "N", "S")
    lon, ew = _coordinate(epoch.lon, 3, "E", "W")
    knots = epoch.speed / _KNOT_MS
    return nmea_sentence(
        f"GNRMC,{_utc_time(at)},A,{lat},{ns},{lon},{ew},{knots:.3f},{epoch.course:.2f},{at:%d%m%y},,,A"
    )


def gngga(epoch: GnssEpoch, at: datetime) -> str:
    """Fix data: time, position, quality, satellites, HDOP, altitude."""
    if not epoch.fixed:
        return nmea_sentence(f"GNGGA,{_utc_time(at)},,,,,0,{epoch.sats:02d},,,M,,M,,")
    lat, ns = _coordinate(epoch.lat, 2, "N", "S")
    lon, ew = _coordinate(epoch.lon, 3, "E", "W")
    hdop = "" if epoch.hdop is None else f"{epoch.hdop:.1f}"
    return nmea_sentence(
        f"GNGGA,{_utc_time(at)},{lat},{ns},{lon},{ew},1,{epoch.sats:02d},{hdop},"
        f"{epoch.altitude:.1f},M,{_GEOID_SEPARATION_M:.1f},M,,"
    )


def pms_frame(frame: PmFrame) -> bytes:
    """A 32-byte Plantower frame: start bytes, length 28, 13 big-endian words, then their byte sum.

    The "CF=1" and "atmospheric" values are equal, as they are at urban levels.
    """
    fine = [round(frame.pm25 * k) for k in _COUNTS_PER_PM25]
    coarse = [round(frame.pm10 * k) for k in _COUNTS_PER_PM10]
    words = [frame.pm1, frame.pm25, frame.pm10] * 2 + fine + coarse + [0]
    body = _PMS_START + struct.pack(">H13H", _PMS_BODY_LEN, *(min(w, 0xFFFF) for w in words))
    return body + struct.pack(">H", sum(body) & 0xFFFF)
