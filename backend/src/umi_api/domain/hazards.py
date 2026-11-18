"""Hazard lifecycle: which flags join a hazard, and how distinct riders move it along.

    pending (the rider alone) -> verified (map_min_riders, on everyone's map)
        -> sent_to_city (city_min_riders, City Insights and IRIS) -> fixed | expired

Riders are always counted as distinct riders from the confirmations, never
trusted from a stored figure (ADR 0006). Fixed and expired are set by the
lifecycle job (expiry by kind, repair proof), never by a new flag.
"""

from umi_protocol import constants

from umi_api.domain.enums import HazardKind, HazardStatus

MERGE_RADIUS_M = constants.REPORTS_HAZARD_MERGE_RADIUS_M

# Hazards a new flag or a passing Clip can still confirm.
OPEN_STATUSES = (HazardStatus.PENDING, HazardStatus.VERIFIED, HazardStatus.SENT_TO_CITY)

_ORDER = {status: rank for rank, status in enumerate(OPEN_STATUSES)}


def kinds_compatible(hazard_kind: HazardKind | None, flag_kind: HazardKind | None) -> bool:
    """A flag joins a hazard of the same kind; a hazard or flag that does not say what it is joins any kind."""
    return hazard_kind is None or flag_kind is None or hazard_kind is flag_kind


def status_for(current: HazardStatus, riders: int) -> HazardStatus:
    """Where `riders` distinct riders put a hazard. A hazard never moves back, and a closed one stays closed."""
    if current not in _ORDER:
        return current
    if riders >= constants.PRIVACY_CITY_MIN_RIDERS:
        reached = HazardStatus.SENT_TO_CITY
    elif riders >= constants.PRIVACY_MAP_MIN_RIDERS:
        reached = HazardStatus.VERIFIED
    else:
        reached = HazardStatus.PENDING
    return max(current, reached, key=_ORDER.__getitem__)
