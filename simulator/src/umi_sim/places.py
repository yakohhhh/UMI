"""Named places riders start from and go to.

Each place is a junction of the mock street network (so routing needs no
snapping) chosen to stand for a neighbourhood or a landmark. ``roles`` tells the
fleet what a place is good for: where people live, where they work, where they
go running or for a weekend ride.
"""

from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass
from enum import Flag, auto

from .geo import XY, to_xy


class Role(Flag):
    HOME = auto()
    WORK = auto()
    LEISURE = auto()


_ROLE_NAMES = {Role.HOME: "home", Role.WORK: "work", Role.LEISURE: "leisure"}


@dataclass(frozen=True, slots=True)
class Place:
    name: str
    lat: float
    lon: float
    junction: str
    district: str
    roles: Role

    @property
    def position(self) -> XY:
        return to_xy(self.lon, self.lat)

    @property
    def role_names(self) -> tuple[str, ...]:
        return tuple(name for role, name in _ROLE_NAMES.items() if role in self.roles)


PLACES: tuple[Place, ...] = (
    Place("Gràcia", 41.40120, 2.15290, "Gran de Gràcia × Travessera de Gràcia", "Gràcia", Role.HOME),
    Place("Sagrada Família", 41.40435, 2.17431, "Marina × Provença", "Eixample", Role.HOME | Role.WORK),
    Place("Tetuan", 41.39488, 2.17555, "Pg. de Sant Joan × Gran Via", "Eixample", Role.HOME),
    Place("Eixample Esquerra", 41.38391, 2.15846, "Villarroel × Diputació", "Eixample", Role.HOME),
    Place("Sant Antoni", 41.38032, 2.16096, "Comte d'Urgell × Floridablanca", "Eixample", Role.HOME),
    Place("Poblenou", 41.40241, 2.19944, "Rambla del Poblenou × Llull", "Sant Martí", Role.HOME),
    Place("Clot", 41.40681, 2.19141, "Gran Via at Clot", "Sant Martí", Role.HOME),
    Place("Sant Martí", 41.41276, 2.19931, "Gran Via at Sant Martí de Provençals", "Sant Martí", Role.HOME),
    Place("22@", 41.40158, 2.19381, "Llacuna × Pallars", "Sant Martí", Role.WORK),
    Place("Glòries", 41.40339, 2.18698, "Av. Diagonal at Glòries", "Sant Martí", Role.WORK),
    Place("Verdaguer", 41.39912, 2.16995, "Av. Diagonal × Pg. de Sant Joan", "Eixample", Role.WORK),
    Place("Passeig de Gràcia", 41.39218, 2.16494, "Pg. de Gràcia × Aragó", "Eixample", Role.WORK),
    Place("Plaça de Catalunya", 41.38773, 2.17082, "Pg. de Gràcia × Ausiàs Marc", "Eixample", Role.WORK),
    Place("Universitat", 41.38637, 2.16425, "Gran Via × Enric Granados", "Eixample", Role.WORK),
    Place("Hospital Clínic", 41.38991, 2.15283, "Casanova × Rosselló", "Eixample", Role.WORK),
    Place("Francesc Macià", 41.39240, 2.14317, "Av. Diagonal at Francesc Macià", "Eixample", Role.WORK),
    Place("Sant Pau", 41.41119, 2.17435, "Cartagena at Hospital de Sant Pau", "Eixample", Role.WORK),
    Place("Bogatell", 41.39484, 2.20720, "Passeig Marítim × Ciutat de Granada", "Sant Martí", Role.LEISURE),
    Place("Port Olímpic", 41.38719, 2.20263, "Passeig Marítim at Port Olímpic", "Sant Martí", Role.LEISURE),
    Place("Barceloneta", 41.38217, 2.19689, "Passeig Marítim, west end", "Sant Martí", Role.LEISURE),
    Place("Fòrum", 41.41082, 2.21657, "Av. Diagonal, east end", "Sant Martí", Role.LEISURE),
)

_COORDINATES = re.compile(r"^\s*(-?\d+(?:\.\d+)?)\s*,\s*(-?\d+(?:\.\d+)?)\s*$")


class UnknownPlaceError(LookupError):
    def __init__(self, query: str) -> None:
        close = difflib.get_close_matches(_key(query), [_key(p.name) for p in PLACES], n=3, cutoff=0.5)
        names = [p.name for p in PLACES if _key(p.name) in close]
        hint = f" Did you mean {', '.join(names)}?" if names else " See `umi-sim places`."
        super().__init__(f"unknown place {query!r}.{hint}")


def _key(name: str) -> str:
    """Accents, case, spaces and punctuation ignored: ``Placa de Catalunya`` finds ``Plaça de Catalunya``."""
    bare = "".join(c for c in unicodedata.normalize("NFKD", name) if not unicodedata.combining(c))
    return "".join(c for c in bare.casefold() if c.isalnum() or c == "@")


def find_place(query: str) -> Place:
    key = _key(query)
    for place in PLACES:
        if _key(place.name) == key:
            return place
    raise UnknownPlaceError(query)


def resolve(text: str) -> tuple[str, XY]:
    """A place name, or ``lat,lon`` in degrees; returns a label and the position."""
    if match := _COORDINATES.match(text):
        lat, lon = float(match[1]), float(match[2])
        return f"{lat:.5f},{lon:.5f}", to_xy(lon, lat)
    place = find_place(text)
    return place.name, place.position
