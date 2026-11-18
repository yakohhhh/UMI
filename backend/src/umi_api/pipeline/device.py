"""Stage 9: what the session says about the Clip itself."""

from dataclasses import dataclass

from umi_protocol import Session, Status


@dataclass(frozen=True)
class DeviceStatus:
    firmware: str
    hw_rev: int
    # From the last STATUS record; None when the session has none.
    battery_pct: int | None


def device_status(session: Session) -> DeviceStatus:
    header = session.header
    battery = [s.battery_pct for s in session.of_type(Status) if s.battery_pct <= 100]
    return DeviceStatus(
        firmware=".".join(str(part) for part in header.fw_version),
        hw_rev=header.hw_rev,
        battery_pct=battery[-1] if battery else None,
    )
