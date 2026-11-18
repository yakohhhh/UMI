"""Hard-brake hotspots with why riders brake there, published only from 5+ riders."""

from umi_api.db.models import BrakeHotspot
from umi_api.domain.privacy import cause_mix
from umi_api.repositories.streets import CauseTally
from umi_api.schemas.street_map import BrakeHotspot as BrakeHotspotView
from umi_api.schemas.street_map import CauseShare


def hotspot_view(
    hotspot: BrakeHotspot, tally: CauseTally | None, *, hard_brakes30d: int, hard_brakes_week: int
) -> BrakeHotspotView:
    """Brake counts are passed in because City Insights rescales them to its filters."""
    tally = tally or CauseTally()
    mix = cause_mix(tally.answers, tally.riders)
    return BrakeHotspotView(
        id=hotspot.id,
        label=hotspot.label,
        coordinates=(hotspot.lon, hotspot.lat),
        hard_brakes_week=hard_brakes_week,
        hard_brakes30d=hard_brakes30d,
        peak_hour=hotspot.peak_hour,
        trend=hotspot.trend,
        avg_decel=hotspot.avg_decel,
        causes=None if mix is None else [CauseShare(cause=c.cause, share=c.share) for c in mix],
        answered_by=tally.riders,
    )
