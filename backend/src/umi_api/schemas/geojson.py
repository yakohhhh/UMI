"""GeoJSON passed through as stored (RFC 7946): geometries are not re-validated."""

from typing import Any, Literal

from pydantic import BaseModel


class Feature(BaseModel):
    type: Literal["Feature"] = "Feature"
    properties: dict[str, Any]
    geometry: dict[str, Any]


class FeatureCollection(BaseModel):
    type: Literal["FeatureCollection"] = "FeatureCollection"
    features: list[Feature]
