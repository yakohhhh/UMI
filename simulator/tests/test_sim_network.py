from __future__ import annotations

import math
from itertools import pairwise

import pytest
from umi_sim.geo import to_xy
from umi_sim.network import Route, RouteError, RouteGoal, riding_speed_ms
from umi_sim.places import PLACES, Place, UnknownPlaceError, find_place, resolve
from umi_sim.simulation import City


def test_graph_keeps_most_of_the_network(city: City) -> None:
    connectivity = city.network.connectivity
    assert connectivity.segments == len(city.world.streets) == 335
    assert connectivity.segments_kept >= 320
    assert connectivity.share > 0.95
    assert connectivity.nodes == len(city.network.nodes)
    assert "largest of" in str(connectivity)


def test_every_junction_is_reachable(city: City) -> None:
    network = city.network
    neighbours: dict[int, set[int]] = {}
    for edge in network.edges:
        neighbours.setdefault(edge.a, set()).add(edge.b)
        neighbours.setdefault(edge.b, set()).add(edge.a)
    seen, frontier = {0}, [0]
    while frontier:
        for other in neighbours[frontier.pop()] - seen:
            seen.add(other)
            frontier.append(other)
    assert len(seen) == len(network.nodes)


@pytest.mark.parametrize("place", PLACES, ids=lambda p: p.name)
def test_every_place_is_a_junction(city: City, place: Place) -> None:
    position = place.position
    assert math.dist(city.network.nodes[city.network.nearest_node(position)], position) < 5.0


def test_route_is_continuous_from_origin_to_destination(city: City) -> None:
    origin, destination = find_place("Gràcia").position, find_place("22@").position
    route = city.network.route([origin, destination])
    for before, after in pairwise(route.steps):
        assert before.end_node == (after.edge.a if after.forward else after.edge.b)
        assert after.start_s == pytest.approx(before.start_s + before.edge.length)
    assert math.dist(route.line.points[0], origin) < 5.0
    assert math.dist(route.line.points[-1], destination) < 5.0
    assert math.dist(origin, destination) < route.length < 1.6 * math.dist(origin, destination)
    assert route.via[-1] == "Carrer de la Llacuna"
    assert all(j.degree >= 3 for j in route.junctions)


def test_calmest_route_trades_minutes_for_calm(city: City) -> None:
    waypoints = [find_place("Gràcia").position, find_place("22@").position]
    fastest = city.network.route(waypoints, goal=RouteGoal.FASTEST, hour=8)
    calmest = city.network.route(waypoints, goal=RouteGoal.CALMEST, hour=8)

    def minutes(route: Route) -> float:
        return sum(step.edge.length / riding_speed_ms(step.edge.street) for step in route.steps) / 60

    assert calmest.mean_overall(8) > fastest.mean_overall(8) + 5
    assert minutes(fastest) < minutes(calmest) < minutes(fastest) + 10


def test_a_loop_goes_out_and_back(city: City) -> None:
    home, turn = find_place("Poblenou").position, find_place("Bogatell").position
    route = city.network.route([home, turn, home])
    assert math.dist(route.line.points[0], route.line.points[-1]) < 1.0
    assert route.length == pytest.approx(2 * city.network.route([home, turn]).length)
    assert any(abs(j.turn_deg) > 150 for j in route.junctions)  # the turnaround


def test_points_snapping_to_one_junction_cannot_be_routed(city: City) -> None:
    here = find_place("Verdaguer").position
    with pytest.raises(RouteError):
        city.network.route([here, (here[0] + 1.0, here[1])])


def test_places_ignore_accents_case_and_punctuation() -> None:
    assert find_place("gracia") is find_place("Gràcia")
    assert find_place("PLACA DE CATALUNYA").name == "Plaça de Catalunya"
    with pytest.raises(UnknownPlaceError, match="Did you mean"):
        find_place("Gracai")


def test_coordinates_are_accepted_as_places() -> None:
    label, position = resolve("41.40158, 2.19381")
    assert label == "41.40158,2.19381"
    assert position == pytest.approx(to_xy(2.19381, 41.40158))
