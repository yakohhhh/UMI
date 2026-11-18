"""Conventions every response model follows to mirror src/lib/types.ts."""

from datetime import datetime
from typing import Annotated, Any

from pydantic import BaseModel, ConfigDict, Field, PlainSerializer

from umi_api.domain.calendar import iso_utc


def camel(name: str) -> str:
    """snake_case -> camelCase, leaving digits alone (`riders30d`, `eu2030Pm25`).

    pydantic's to_camel upper-cases a letter after a digit (`riders30D`).
    """
    head, *rest = name.rstrip("_").split("_")
    return head + "".join(part[:1].upper() + part[1:] for part in rest)


class ApiModel(BaseModel):
    model_config = ConfigDict(alias_generator=camel, populate_by_name=True, from_attributes=True)


def optional(**kwargs: Any) -> Any:
    """An optional property (`name?: T` in TypeScript): left out of the JSON when None."""
    return Field(default=None, exclude_if=lambda value: value is None, **kwargs)


# [longitude, latitude], GeoJSON order.
LngLat = tuple[float, float]

# Instants as JavaScript's Date.toISOString() writes them: UTC, milliseconds, "Z".
IsoDateTime = Annotated[datetime, PlainSerializer(iso_utc, return_type=str)]
