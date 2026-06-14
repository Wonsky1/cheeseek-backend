from uuid import uuid4

import app.map_vectors as map_vectors


def _fake_osm_vectors(monkeypatch):
    building_id = "osm-building-test-1"
    building_coordinates = [
        map_vectors.Coordinate(latitude=52.23010, longitude=21.01100),
        map_vectors.Coordinate(latitude=52.23010, longitude=21.01160),
        map_vectors.Coordinate(latitude=52.23040, longitude=21.01160),
        map_vectors.Coordinate(latitude=52.23040, longitude=21.01100),
    ]
    building = map_vectors.Building(
        id=building_id,
        coordinates=building_coordinates,
        sides=map_vectors._sides(building_id, building_coordinates),
    )
    edge = map_vectors.WalkableEdge(
        id="osm-edge-test-1",
        coordinates=[
            map_vectors.Coordinate(latitude=52.23008, longitude=21.01080),
            map_vectors.Coordinate(latitude=52.23008, longitude=21.01180),
        ],
    )

    def fetch_osm_bbox(*args, **kwargs):
        return [building], [edge]

    monkeypatch.setattr(map_vectors, "_fetch_osm_bbox", fetch_osm_bbox)


def test_map_features_returns_feature_collection(client, monkeypatch):
    _fake_osm_vectors(monkeypatch)
    response = client.get(
        "/map/features",
        params={
            "south": 52.228,
            "west": 21.01,
            "north": 52.232,
            "east": 21.016,
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["type"] == "FeatureCollection"
    assert payload["features"]
    assert payload["features"][0]["geometry"]["type"] == "Polygon"
    assert payload["features"][0]["properties"]["reachableSideIds"]
    assert payload["features"][0]["properties"]["requiredSideCount"] == len(
        payload["features"][0]["properties"]["reachableSideIds"]
    )


def test_coverage_candidates_returns_building_side_ids(client, monkeypatch):
    _fake_osm_vectors(monkeypatch)
    points = [
        {
            "id": str(uuid4()),
            "latitude": 52.23,
            "longitude": 21.01,
            "altitude": 0,
            "horizontalAccuracy": 5,
            "timestamp": "2026-06-08T17:00:00Z",
        },
        {
            "id": str(uuid4()),
            "latitude": 52.23,
            "longitude": 21.016,
            "altitude": 0,
            "horizontalAccuracy": 5,
            "timestamp": "2026-06-08T17:01:00Z",
        },
    ]

    response = client.post("/map/coverage-candidates", json={"points": points})

    assert response.status_code == 200
    payload = response.json()
    assert payload["areaId"] == "osm-building-sides-v1"
    assert payload["coveredFeatureIds"]
