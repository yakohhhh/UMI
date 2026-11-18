"""The ingest pipeline: a trimmed session log in, a ride and its street data out.

Plain functions over plain values, no FastAPI and no database: the caller
(services.ingest) loads what a stage needs and stores what comes out, so the
pipeline can move to a worker unchanged (ADR 0004).

    body ─read_upload─▶ Upload ─build_track─▶ Track ─map_match─▶ MatchedTrack ─process─▶ ProcessedRide
          decode, trimmed,      plausibility:        nearest segment       readings, flags, events,
          complete,             clock, service area, within reach, along   hazards, summary, segments,
          simulated,            speed, GNSS jumps    the course; runs      passes, exposure, device
          TIME_SYNC                                                                ▲
                                                                                   │
                                              RideContext (services.ingest): published hourly scores,
                                              hotspots, open hazards around the track, the Clip's key,
                                              the rider's flags per day
"""

from umi_api.pipeline.context import HotspotRef, OpenHazard, RideContext
from umi_api.pipeline.exposure import add_exposure
from umi_api.pipeline.matching import MatchedTrack, StreetIndex, StreetRef, Typical, map_match
from umi_api.pipeline.process import ProcessedRide, process
from umi_api.pipeline.ride import activity_id
from umi_api.pipeline.track import Track, build_track
from umi_api.pipeline.upload import SessionRejected, Upload, read_upload

__all__ = [
    "HotspotRef",
    "MatchedTrack",
    "OpenHazard",
    "ProcessedRide",
    "RideContext",
    "SessionRejected",
    "StreetIndex",
    "StreetRef",
    "Track",
    "Typical",
    "Upload",
    "activity_id",
    "add_exposure",
    "build_track",
    "map_match",
    "process",
    "read_upload",
]
