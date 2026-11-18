"""A rider's impact: credit follows what happened to their flags and answers, never the press itself."""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from umi_api.domain.enums import HazardStatus

_NOT_VERIFIED = {HazardStatus.PENDING, HazardStatus.EXPIRED}


class FlagOutcome(Protocol):
    @property
    def status(self) -> HazardStatus: ...
    @property
    def riders_warned(self) -> int: ...


@dataclass(frozen=True)
class Impact:
    riders_warned: int
    verified: int
    fixed: int
    causes_given: int


def impact(earlier: Impact, flags: Iterable[FlagOutcome], causes_given: int) -> Impact:
    """`earlier` carries the outcomes of flags and answers older than the stored rides.

    Every answer counts the same, "just me" included, so nobody has a reason to exaggerate.
    """
    flags = list(flags)
    return Impact(
        riders_warned=earlier.riders_warned + sum(f.riders_warned for f in flags),
        verified=earlier.verified + sum(1 for f in flags if f.status not in _NOT_VERIFIED),
        fixed=earlier.fixed + sum(1 for f in flags if f.status is HazardStatus.FIXED),
        causes_given=earlier.causes_given + causes_given,
    )
