from fastapi.testclient import TestClient


def test_shared_progress_and_routes(client: TestClient) -> None:
    profile = client.post(
        "/profiles",
        json={"nickname": "vlad", "deviceId": "00000000-0000-0000-0000-000000000001"},
    ).json()
    session_id = "11111111-1111-1111-1111-111111111111"
    client.post(
        "/walk-sessions",
        json={
            "id": session_id,
            "userId": profile["id"],
            "startedAt": "2026-06-08T12:00:00Z",
            "endedAt": "2026-06-08T12:10:00Z",
            "distanceMeters": 700,
            "durationSeconds": 600,
            "syncStatus": "readyToSync",
        },
    )
    client.post(
        f"/walk-sessions/{session_id}/points",
        json={
            "userId": profile["id"],
            "points": [
                {
                    "id": "22222222-2222-2222-2222-222222222222",
                    "latitude": 52.2297,
                    "longitude": 21.0122,
                    "altitude": None,
                    "horizontalAccuracy": 8.5,
                    "timestamp": "2026-06-08T12:01:00Z",
                }
            ],
        },
    )

    progress = client.get("/shared-progress").json()
    routes = client.get(f"/routes?userId={profile['id']}").json()

    assert progress["totalDistanceMeters"] == 700
    assert progress["totalWalks"] == 1
    assert routes[0]["coordinates"] == [{"latitude": 52.2297, "longitude": 21.0122}]
