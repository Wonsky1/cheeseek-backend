from __future__ import annotations

from dataclasses import dataclass, field
from math import cos, hypot, radians
from threading import RLock
from typing import Any

import httpx

from app.schemas import TrackPointCreate


MAP_AREA_ID = "osm-building-sides-v1"


@dataclass(frozen=True)
class Coordinate:
    latitude: float
    longitude: float


@dataclass
class BuildingSide:
    id: str
    building_id: str
    start: Coordinate
    end: Coordinate
    walkable_edge_count: int = 0


@dataclass
class Building:
    id: str
    coordinates: list[Coordinate]
    sides: list[BuildingSide]


@dataclass
class WalkableEdge:
    id: str
    coordinates: list[Coordinate]


@dataclass
class MapVectorStore:
    buildings: dict[str, Building] = field(default_factory=dict)
    walkable_edges: dict[str, WalkableEdge] = field(default_factory=dict)
    loaded_bboxes: list[tuple[float, float, float, float]] = field(default_factory=list)
    lock: RLock = field(default_factory=RLock)

    def reset(self) -> None:
        with self.lock:
            self.buildings.clear()
            self.walkable_edges.clear()
            self.loaded_bboxes.clear()

    def ensure_bbox_loaded(self, south: float, west: float, north: float, east: float) -> None:
        bbox = (south, west, north, east)
        with self.lock:
            if any(_contains_bbox(loaded, bbox) for loaded in self.loaded_bboxes):
                return

        try:
            buildings, edges = _fetch_osm_bbox(south, west, north, east)
        except Exception:
            buildings, edges = [], []

        with self.lock:
            for building in buildings:
                self.buildings[building.id] = building
            for edge in edges:
                self.walkable_edges[edge.id] = edge
            self._rebuild_side_adjacency()
            self.loaded_bboxes.append(bbox)

    def feature_collection(
        self,
        south: float,
        west: float,
        north: float,
        east: float,
        covered_side_ids: set[str],
        active_side_ids: set[str],
    ) -> dict[str, Any]:
        self.ensure_bbox_loaded(south, west, north, east)
        features = []
        with self.lock:
            for building in self.buildings.values():
                if not any(_inside_bbox(coordinate, south, west, north, east) for coordinate in building.coordinates):
                    continue
                reachable_side_ids = {side.id for side in building.sides if side.walkable_edge_count > 0}
                if not reachable_side_ids:
                    reachable_side_ids = {side.id for side in building.sides}
                covered_for_building = covered_side_ids.intersection(reachable_side_ids)
                active_for_building = active_side_ids.intersection(reachable_side_ids)
                if active_for_building:
                    status = "active"
                elif covered_for_building:
                    status = "explored"
                else:
                    status = "available"
                covered_count = len(covered_for_building.union(active_for_building))
                required_count = max(len(reachable_side_ids), 1)
                features.append(
                    {
                        "type": "Feature",
                        "id": building.id,
                        "properties": {
                            "id": building.id,
                            "status": status,
                            "coveredSideCount": covered_count,
                            "requiredSideCount": required_count,
                            "reachableSideIds": sorted(reachable_side_ids),
                            "isFullyCovered": covered_count >= required_count or (required_count == 1 and covered_count > 0),
                        },
                        "geometry": {
                            "type": "Polygon",
                            "coordinates": [[
                                [coordinate.longitude, coordinate.latitude]
                                for coordinate in _closed_ring(building.coordinates)
                            ]],
                        },
                    }
                )
        return {"type": "FeatureCollection", "features": features}

    def covered_side_ids_for_points(self, points: list[TrackPointCreate]) -> set[str]:
        if not points:
            return set()
        south = min(point.latitude for point in points) - 0.004
        north = max(point.latitude for point in points) + 0.004
        west = min(point.longitude for point in points) - 0.004
        east = max(point.longitude for point in points) + 0.004
        self.ensure_bbox_loaded(south, west, north, east)

        covered: set[str] = set()
        path = [Coordinate(latitude=point.latitude, longitude=point.longitude) for point in points]
        with self.lock:
            for start, end in zip(path, path[1:]):
                for building in self.buildings.values():
                    for side in building.sides:
                        if side.walkable_edge_count <= 0:
                            continue
                        distance = _segment_distance_meters(side.start, side.end, start, end)
                        if distance <= 42:
                            covered.add(side.id)
                            reachable_sides = [candidate for candidate in building.sides if candidate.walkable_edge_count > 0]
                            if len(reachable_sides) <= 1:
                                covered.update(candidate.id for candidate in reachable_sides)
        return covered

    def _rebuild_side_adjacency(self) -> None:
        for building in self.buildings.values():
            for side in building.sides:
                side.walkable_edge_count = 0
                for edge in self.walkable_edges.values():
                    for start, end in zip(edge.coordinates, edge.coordinates[1:]):
                        if _segment_distance_meters(side.start, side.end, start, end) <= 38:
                            side.walkable_edge_count += 1
                            break


def _fetch_osm_bbox(south: float, west: float, north: float, east: float) -> tuple[list[Building], list[WalkableEdge]]:
    query = f"""
    [out:json][timeout:25];
    (
      way["building"]({south},{west},{north},{east});
      way["highway"]({south},{west},{north},{east});
    );
    out tags geom;
    """
    response = httpx.post(
        "https://overpass-api.de/api/interpreter",
        data={"data": query},
        timeout=30,
    )
    response.raise_for_status()
    elements = response.json().get("elements", [])
    buildings: list[Building] = []
    edges: list[WalkableEdge] = []
    for element in elements:
        geometry = [
            Coordinate(latitude=item["lat"], longitude=item["lon"])
            for item in element.get("geometry", [])
            if "lat" in item and "lon" in item
        ]
        tags = element.get("tags", {})
        if tags.get("building") and len(geometry) >= 4 and _is_closed(geometry):
            coordinates = geometry[:-1]
            building_id = f"osm-building-{element['id']}"
            buildings.append(Building(id=building_id, coordinates=coordinates, sides=_sides(building_id, coordinates)))
        elif tags.get("highway") in _walkable_highways() and len(geometry) >= 2:
            edges.append(WalkableEdge(id=f"osm-edge-{element['id']}", coordinates=geometry))
    return buildings, edges


def _sides(building_id: str, coordinates: list[Coordinate]) -> list[BuildingSide]:
    return [
        BuildingSide(
            id=f"{building_id}:side:{index}",
            building_id=building_id,
            start=start,
            end=end,
        )
        for index, (start, end) in enumerate(zip(coordinates, coordinates[1:] + coordinates[:1]))
    ]


def _walkable_highways() -> set[str]:
    return {
        "footway",
        "path",
        "pedestrian",
        "residential",
        "living_street",
        "service",
        "tertiary",
        "secondary",
        "primary",
        "unclassified",
    }


def _contains_bbox(outer: tuple[float, float, float, float], inner: tuple[float, float, float, float]) -> bool:
    return outer[0] <= inner[0] and outer[1] <= inner[1] and outer[2] >= inner[2] and outer[3] >= inner[3]


def _inside_bbox(coordinate: Coordinate, south: float, west: float, north: float, east: float) -> bool:
    return south <= coordinate.latitude <= north and west <= coordinate.longitude <= east


def _is_closed(coordinates: list[Coordinate]) -> bool:
    return coordinates[0].latitude == coordinates[-1].latitude and coordinates[0].longitude == coordinates[-1].longitude


def _closed_ring(coordinates: list[Coordinate]) -> list[Coordinate]:
    if not coordinates:
        return []
    if _is_closed(coordinates):
        return coordinates
    return coordinates + [coordinates[0]]


def _segment_distance_meters(a: Coordinate, b: Coordinate, c: Coordinate, d: Coordinate) -> float:
    return min(
        _point_segment_distance_meters(a, c, d),
        _point_segment_distance_meters(b, c, d),
        _point_segment_distance_meters(c, a, b),
        _point_segment_distance_meters(d, a, b),
    )


def _point_segment_distance_meters(point: Coordinate, start: Coordinate, end: Coordinate) -> float:
    origin = point
    px, py = 0.0, 0.0
    sx, sy = _meters_vector(origin, start)
    ex, ey = _meters_vector(origin, end)
    vx, vy = ex - sx, ey - sy
    length_squared = vx * vx + vy * vy
    if length_squared == 0:
        return hypot(px - sx, py - sy)
    t = max(0, min(1, ((px - sx) * vx + (py - sy) * vy) / length_squared))
    projection_x = sx + t * vx
    projection_y = sy + t * vy
    return hypot(px - projection_x, py - projection_y)


def _meters_vector(origin: Coordinate, target: Coordinate) -> tuple[float, float]:
    meters_per_latitude_degree = 111_320.0
    meters_per_longitude_degree = meters_per_latitude_degree * cos(radians(origin.latitude))
    return (
        (target.longitude - origin.longitude) * meters_per_longitude_degree,
        (target.latitude - origin.latitude) * meters_per_latitude_degree,
    )
