"""The simulated city: the web app's mock datasets as typed values.

Virtual riders move through the same Barcelona the web app shows: the 335 scored
street segments (``streets.json``), confirmed potholes, hard-brake hotspots and
the hazards riders flagged (``flags.json``). Reading the files the web app reads,
instead of a copy, keeps a simulated ride consistent with the street map.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from functools import cache
from pathlib import Path
from typing import Any, Literal, cast

from umi_protocol import HazardKind

from .geo import XY, Polyline, to_xy
from .scores import Scores

type StreetKind = Literal["arterial", "boulevard", "street", "green", "promenade", "seafront"]
type Severity = Literal["low", "medium", "high"]

DATA_DIR_ENV = "UMI_SIM_DATA_DIR"
# simulator/src/umi_sim/world.py → the repository root, where the web app keeps its mocks.
_REPO_DATA_DIR = Path(__file__).resolve().parents[3] / "src" / "lib" / "mock" / "data"

HOURS = 24


@dataclass(frozen=True, slots=True)
class Street:
    """One scored street segment (``StreetSegment`` in ``src/lib/types.ts``)."""

    id: str
    name: str
    from_name: str | None
    to_name: str | None
    district: str
    kind: StreetKind
    bike_lane: bool
    coordinates: tuple[XY, ...]
    length_m: float
    hourly: tuple[Scores, ...]
    vib_rms: float

    def scores_at(self, hour: int) -> Scores:
        return self.hourly[hour % HOURS]


@dataclass(frozen=True, slots=True)
class Pothole:
    id: str
    segment_id: str
    position: XY
    severity: Severity


@dataclass(frozen=True, slots=True)
class Hotspot:
    """A junction where riders brake hard; ``hard_brakes_week`` sets how likely it is."""

    id: str
    label: str
    position: XY
    hard_brakes_week: int
    peak_hour: int
    avg_decel_mps2: float


@dataclass(frozen=True, slots=True)
class Hazard:
    """A hazard riders keep flagging (``cityHazards`` in ``flags.json``), still on the street."""

    id: str
    kind: HazardKind
    label: str
    position: XY


class DataError(RuntimeError):
    """The mock datasets are missing or not shaped as expected."""


@dataclass(frozen=True)
class World:
    streets: tuple[Street, ...]
    potholes: tuple[Pothole, ...]
    hotspots: tuple[Hotspot, ...]
    hazards: tuple[Hazard, ...]


def default_data_dir() -> Path:
    """``$UMI_SIM_DATA_DIR``, else the web app's ``src/lib/mock/data`` in this repository."""
    configured = os.environ.get(DATA_DIR_ENV)
    return Path(configured) if configured else _REPO_DATA_DIR


@cache
def load_world(data_dir: Path | None = None) -> World:
    """Read the datasets once per directory; the result is immutable and shared."""
    root = data_dir or default_data_dir()
    try:
        return World(
            streets=tuple(_street(raw) for raw in _read(root, "streets.json")),
            potholes=tuple(_pothole(raw) for raw in _read(root, "potholes.json")),
            hotspots=tuple(_hotspot(raw) for raw in _read(root, "hotspots.json")),
            hazards=tuple(_hazard(raw) for raw in _read(root, "flags.json")["cityHazards"] if raw["status"] != "fixed"),
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise DataError(f"unexpected mock data in {root}: {exc!r}") from exc


def _read(root: Path, name: str) -> Any:
    path = root / name
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise DataError(
            f"{path} not found: run from the repository, or point {DATA_DIR_ENV} (or --data) at src/lib/mock/data"
        ) from None


def _xy(coordinates: list[float]) -> XY:
    lon, lat = coordinates
    return to_xy(lon, lat)


def _street(raw: dict[str, Any]) -> Street:
    hourly = raw["hourly"]
    coordinates = tuple(_xy(c) for c in raw["coordinates"])
    return Street(
        id=raw["id"],
        name=raw["name"],
        from_name=raw["from"],
        to_name=raw["to"],
        district=raw["district"],
        kind=cast(StreetKind, raw["kind"]),
        bike_lane=bool(raw["bikeLane"]),
        coordinates=coordinates,
        length_m=Polyline(coordinates).length,
        hourly=tuple(
            Scores(hourly["comfort"][h], hourly["safety"][h], hourly["air"][h], hourly["noise"][h])
            for h in range(HOURS)
        ),
        vib_rms=float(raw["surface"]["vibRms"]),
    )


def _pothole(raw: dict[str, Any]) -> Pothole:
    return Pothole(raw["id"], raw["segmentId"], _xy(raw["coordinates"]), cast(Severity, raw["severity"]))


def _hotspot(raw: dict[str, Any]) -> Hotspot:
    return Hotspot(
        id=raw["id"],
        label=raw["label"],
        position=_xy(raw["coordinates"]),
        hard_brakes_week=int(raw["hardBrakesWeek"]),
        peak_hour=int(raw["peakHour"]),
        avg_decel_mps2=float(raw["avgDecel"]),
    )


def _hazard(raw: dict[str, Any]) -> Hazard:
    return Hazard(raw["id"], HazardKind[raw["kind"].upper()], raw["street"], _xy(raw["coordinates"]))
