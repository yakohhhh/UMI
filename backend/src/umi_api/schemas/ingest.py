from umi_api.schemas.base import ApiModel


class FlagCounts(ApiModel):
    accepted: int
    # Bad or missing signature, pressed outside the service area, or over the rider's daily cap.
    rejected: int


class IngestReceipt(ApiModel):
    """What processing an uploaded session produced (protocol/README.md §3)."""

    activity_id: str
    # Distinct street segments the ride went through.
    segments_matched: int
    flags: FlagCounts
    # Ride events stored: the Clip's (hard brakes, potholes) and the derived ones (PM2.5 spikes, noise peaks).
    events: int
