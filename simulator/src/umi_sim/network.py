"""The street graph built from the scored segments, and routing on it.

``streets.json`` holds segments, not a graph: the Cerdà grid streets are cut every
few blocks, so a cross street usually meets a segment in its middle rather than
at an end. Building the graph therefore splits every segment where another one
crosses or touches it (within ``SNAP_M``) and merges points closer than that into
one junction. The largest connected component is kept; :class:`Connectivity`
says how much of the network that is (the Ciutat Vella avenues are islands in
the mock data).

Routing is Dijkstra over the junctions, with two costs: *fastest* (length over
a nominal riding speed per street kind) and *calmest* (the same time, inflated
on streets with a low overall score at that hour).
"""

from __future__ import annotations

import heapq
import math
from bisect import bisect_right
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from functools import cached_property
from itertools import pairwise

from .geo import XY, Polyline, bearing_deg, turn_deg
from .world import Street, StreetKind

#: Segment ends and crossings closer than this are one junction (metres).
SNAP_M = 5.0
# Two pieces whose directions differ by less than ~3° are treated as parallel.
_PARALLEL_SIN = 0.05

#: Nominal cycling speed per street kind (m/s), with and without a bike lane: the
#: "fastest" cost. Promenades and superblocks are shared with pedestrians.
_RIDING_SPEED_MS: dict[StreetKind, tuple[float, float]] = {
    "arterial": (5.6, 4.6),
    "boulevard": (5.6, 4.8),
    "street": (5.0, 4.4),
    "green": (4.6, 4.4),
    "promenade": (3.4, 3.2),
    "seafront": (5.0, 4.6),
}
# How much a poor street costs the calmest route: a street scoring 35 costs about
# 2.3 times the time of one scoring 70 (Gràcia → 22@ at 8:00: +4 min, overall 47 → 64).
_CALM_WEIGHT = 6.0
_LIT_KINDS: frozenset[StreetKind] = frozenset({"arterial", "boulevard", "street"})


class RouteGoal(StrEnum):
    FASTEST = "fastest"
    CALMEST = "calmest"


class RouteError(ValueError):
    """No route between the two points (they snap to the same junction)."""


def riding_speed_ms(street: Street) -> float:
    with_lane, without = _RIDING_SPEED_MS[street.kind]
    return with_lane if street.bike_lane else without


@dataclass(frozen=True, slots=True, eq=False)
class Edge:
    """A stretch of one street between two junctions; ``line`` runs from ``a`` to ``b``."""

    id: int
    a: int
    b: int
    street: Street
    line: Polyline

    @property
    def length(self) -> float:
        return self.line.length


@dataclass(frozen=True, slots=True)
class Connectivity:
    """How much of the mock street network the routable graph keeps."""

    segments: int
    segments_kept: int
    length_m: float
    length_kept_m: float
    components: int
    nodes: int
    edges: int

    @property
    def share(self) -> float:
        return self.length_kept_m / self.length_m

    def __str__(self) -> str:
        return (
            f"{self.segments_kept} of {self.segments} segments ({self.share:.1%} of {self.length_m / 1000:.1f} km) "
            f"in the largest of {self.components} components: {self.nodes} junctions, {self.edges} edges"
        )


@dataclass(frozen=True, slots=True)
class RouteStep:
    """One edge travelled in one direction, starting ``start_s`` metres into the route."""

    edge: Edge
    forward: bool
    start_s: float

    @property
    def points(self) -> tuple[XY, ...]:
        return self.edge.line.points if self.forward else self.edge.line.points[::-1]

    @property
    def end_node(self) -> int:
        return self.edge.b if self.forward else self.edge.a


@dataclass(frozen=True, slots=True)
class Junction:
    """A node the route goes through where at least three street stretches meet."""

    s: float
    node: int
    degree: int
    turn_deg: float
    has_lights: bool


@dataclass(frozen=True)
class Route:
    steps: tuple[RouteStep, ...]
    line: Polyline
    junctions: tuple[Junction, ...]

    @property
    def length(self) -> float:
        return self.line.length

    @cached_property
    def _bounds(self) -> tuple[float, float, float, float]:
        return _bbox(self.line.points, 0.0)

    def locate(self, point: XY, reach_m: float) -> float | None:
        """Distance along the route where it passes within ``reach_m`` of ``point``, if it does."""
        x0, y0, x1, y1 = self._bounds
        if not (x0 - reach_m <= point[0] <= x1 + reach_m and y0 - reach_m <= point[1] <= y1 + reach_m):
            return None
        s, off = self.line.project(point)
        return s if off <= reach_m else None

    def street_at(self, s: float) -> Street:
        starts = [step.start_s for step in self.steps]
        return self.steps[max(bisect_right(starts, s) - 1, 0)].edge.street

    @property
    def via(self) -> tuple[str, ...]:
        """Street names in travel order, each once per stretch."""
        names: list[str] = []
        for step in self.steps:
            if not names or names[-1] != step.edge.street.name:
                names.append(step.edge.street.name)
        return tuple(names)

    def mean_overall(self, hour: int) -> float:
        """Length-weighted overall score of the streets at ``hour``."""
        total = sum(step.edge.length * step.edge.street.scores_at(hour).overall for step in self.steps)
        return total / self.length


class StreetNetwork:
    """The routable graph: junctions (``nodes``) and street stretches (``edges``)."""

    def __init__(self, nodes: Sequence[XY], edges: Sequence[Edge], connectivity: Connectivity) -> None:
        self.nodes: tuple[XY, ...] = tuple(nodes)
        self.edges: tuple[Edge, ...] = tuple(edges)
        self.connectivity = connectivity
        adjacent: list[list[tuple[Edge, int]]] = [[] for _ in self.nodes]
        for edge in self.edges:
            adjacent[edge.a].append((edge, edge.b))
            adjacent[edge.b].append((edge, edge.a))
        self._adjacent = tuple(tuple(links) for links in adjacent)

    @classmethod
    def build(cls, streets: Sequence[Street], snap_m: float = SNAP_M) -> StreetNetwork:
        pieces = [piece for street in streets for piece in _split(street, _cuts(street, streets, snap_m))]
        node_of, positions = _cluster([p for _, line in pieces for p in (line[0], line[-1])], snap_m)
        raw_edges: list[tuple[int, int, Street, list[XY]]] = []
        for k, (street, line) in enumerate(pieces):
            a, b = node_of[2 * k], node_of[2 * k + 1]
            if a != b:
                raw_edges.append((a, b, street, [positions[a], *line[1:-1], positions[b]]))
        components, keep = _largest_component(len(positions), raw_edges)
        renumber = {old: new for new, old in enumerate(sorted(keep))}
        edges = [
            Edge(i, renumber[a], renumber[b], street, Polyline(line))
            for i, (a, b, street, line) in enumerate(e for e in raw_edges if e[0] in keep)
        ]
        kept = {e.street.id: e.street for e in edges}
        connectivity = Connectivity(
            segments=len(streets),
            segments_kept=len(kept),
            length_m=sum(s.length_m for s in streets),
            length_kept_m=sum(s.length_m for s in kept.values()),
            components=components,
            nodes=len(renumber),
            edges=len(edges),
        )
        return cls([positions[old] for old in sorted(keep)], edges, connectivity)

    def nearest_node(self, point: XY) -> int:
        return min(range(len(self.nodes)), key=lambda n: math.dist(self.nodes[n], point))

    def route(self, waypoints: Sequence[XY], *, goal: RouteGoal = RouteGoal.FASTEST, hour: int = 8) -> Route:
        """The cheapest route through ``waypoints`` (at least two), each snapped to its nearest junction."""
        nodes = [self.nearest_node(p) for p in waypoints]
        if len(nodes) < 2:
            raise RouteError("a route needs an origin and a destination")
        cost = _cost(goal, hour)
        legs: list[tuple[Edge, int]] = []
        for src, dst in pairwise(nodes):
            if src == dst:
                raise RouteError("two consecutive waypoints snap to the same junction")
            legs.extend(self._shortest_path(src, dst, cost))
        return self._assemble(legs, nodes[0])

    def _shortest_path(self, src: int, dst: int, cost: Callable[[Edge], float]) -> list[tuple[Edge, int]]:
        """Dijkstra; returns ``(edge, node it was entered from)`` for each step from ``src`` to ``dst``."""
        best = {src: 0.0}
        came_from: dict[int, tuple[Edge, int]] = {}
        heap = [(0.0, src)]
        while heap:
            d, node = heapq.heappop(heap)
            if node == dst:
                break
            if d > best[node]:
                continue
            for edge, other in self._adjacent[node]:
                nd = d + cost(edge)
                if nd < best.get(other, math.inf):
                    best[other] = nd
                    came_from[other] = (edge, node)
                    heapq.heappush(heap, (nd, other))
        if dst not in came_from:
            raise RouteError(f"junction {dst} is not reachable from {src}")
        path: list[tuple[Edge, int]] = []
        node = dst
        while node != src:
            edge, previous = came_from[node]
            path.append((edge, previous))
            node = previous
        return path[::-1]

    def _assemble(self, legs: Iterable[tuple[Edge, int]], origin: int) -> Route:
        steps: list[RouteStep] = []
        points: list[XY] = [self.nodes[origin]]
        s = 0.0
        for edge, entered_from in legs:
            step = RouteStep(edge, forward=edge.a == entered_from, start_s=s)
            steps.append(step)
            points.extend(step.points[1:])
            s += edge.length
        junctions = []
        for before, after in pairwise(steps):
            node = before.end_node
            links = self._adjacent[node]
            if len(links) < 3:
                continue
            turn = turn_deg(bearing_deg(*before.points[-2:]), bearing_deg(*after.points[:2]))
            lit = any(edge.street.kind in _LIT_KINDS for edge, _ in links)
            junctions.append(Junction(after.start_s, node, len(links), turn, lit))
        return Route(tuple(steps), Polyline(points), tuple(junctions))


def _cost(goal: RouteGoal, hour: int) -> Callable[[Edge], float]:
    def fastest(edge: Edge) -> float:
        return edge.length / riding_speed_ms(edge.street)

    def calmest(edge: Edge) -> float:
        poor = (100 - edge.street.scores_at(hour).overall) / 100
        return fastest(edge) * (1 + _CALM_WEIGHT * poor * poor)

    return fastest if goal is RouteGoal.FASTEST else calmest


# ---------------------------------------------------------------- graph construction


def _bbox(points: Sequence[XY], margin: float) -> tuple[float, float, float, float]:
    xs, ys = [p[0] for p in points], [p[1] for p in points]
    return min(xs) - margin, min(ys) - margin, max(xs) + margin, max(ys) + margin


def _overlap(a: tuple[float, float, float, float], b: tuple[float, float, float, float]) -> bool:
    return a[0] <= b[2] and b[0] <= a[2] and a[1] <= b[3] and b[1] <= a[3]


def _cross(u: XY, v: XY) -> float:
    return u[0] * v[1] - u[1] * v[0]


def _cuts(street: Street, streets: Sequence[Street], snap_m: float) -> list[float]:
    """Distances along ``street`` where another street crosses it or ends on it.

    Pieces are extended by ``snap_m`` at both ends, so a street that stops just
    short of another (a T-junction drawn a metre off) still meets it.
    """
    line = Polyline(street.coordinates)
    box = _bbox(line.points, snap_m)
    cuts: list[float] = []
    for other in streets:
        if other is street or not _overlap(box, _bbox(other.coordinates, snap_m)):
            continue
        for i, (p, q) in enumerate(pairwise(line.points)):
            d1 = (q[0] - p[0], q[1] - p[1])
            len1 = math.hypot(*d1)
            for r, s in pairwise(other.coordinates):
                d2 = (s[0] - r[0], s[1] - r[1])
                len2 = math.hypot(*d2)
                den = _cross(d1, d2)
                if abs(den) < _PARALLEL_SIN * len1 * len2:
                    continue
                rp = (r[0] - p[0], r[1] - p[1])
                t, u = _cross(rp, d2) / den, _cross(rp, d1) / den
                e1, e2 = snap_m / len1, snap_m / len2
                if -e1 <= t <= 1 + e1 and -e2 <= u <= 1 + e2:
                    cuts.append(line.cumulative[i] + min(max(t, 0.0), 1.0) * len1)
    return cuts


def _split(street: Street, cuts: Iterable[float]) -> list[tuple[Street, list[XY]]]:
    """The street cut into pieces at ``cuts`` (distances along it); ends are always cuts."""
    line = Polyline(street.coordinates)
    marks = sorted({0.0, line.length, *cuts})
    pieces = []
    for lo, hi in pairwise(marks):
        inner = [p for p, s in zip(line.points, line.cumulative, strict=True) if lo < s < hi]
        pieces.append((street, [line.point_at(lo), *inner, line.point_at(hi)]))
    return pieces


def _cluster(points: Sequence[XY], snap_m: float) -> tuple[list[int], list[XY]]:
    """Merge points closer than ``snap_m`` (transitively); returns each point's node and node positions."""
    parent = list(range(len(points)))

    def root(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    buckets: dict[tuple[int, int], list[int]] = {}
    for i, (x, y) in enumerate(points):
        cell = (math.floor(x / snap_m), math.floor(y / snap_m))
        for dx in (-1, 0, 1):
            for dy in (-1, 0, 1):
                for j in buckets.get((cell[0] + dx, cell[1] + dy), ()):
                    if math.dist(points[i], points[j]) <= snap_m:
                        parent[root(i)] = root(j)
        buckets.setdefault(cell, []).append(i)

    members: dict[int, list[int]] = {}
    for i in range(len(points)):
        members.setdefault(root(i), []).append(i)
    node_of = [0] * len(points)
    positions: list[XY] = []
    for node, indices in enumerate(members.values()):
        for i in indices:
            node_of[i] = node
        positions.append(
            (sum(points[i][0] for i in indices) / len(indices), sum(points[i][1] for i in indices) / len(indices))
        )
    return node_of, positions


def _largest_component(n: int, edges: Sequence[tuple[int, int, Street, list[XY]]]) -> tuple[int, set[int]]:
    """How many components the edges form, and the nodes of the one with the most street length."""
    parent = list(range(n))

    def root(i: int) -> int:
        while parent[i] != i:
            parent[i] = parent[parent[i]]
            i = parent[i]
        return i

    for a, b, _, _ in edges:
        parent[root(a)] = root(b)
    length: dict[int, float] = {}
    for a, _, _, line in edges:
        length[root(a)] = length.get(root(a), 0.0) + Polyline(line).length
    biggest = max(length, key=lambda c: length[c])
    return len(length), {i for i in range(n) if root(i) == biggest}
