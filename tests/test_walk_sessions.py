from fastapi.testclient import TestClient


def create_profile(client: TestClient) -> str:
    response = client.post(
        "/profiles",
        json={"nickname": "vlad", "deviceId": "00000000-0000-0000-0000-000000000001"},
    )
    return response.json()["id"]


def test_create_session_and_upload_points_idempotently(client: TestClient) -> None:
    user_id = create_profile(client)
    session_id = "11111111-1111-1111-1111-111111111111"

    session_response = client.post(
        "/walk-sessions",
        json={
            "id": session_id,
            "userId": user_id,
            "startedAt": "2026-06-08T12:00:00Z",
            "endedAt": "2026-06-08T12:10:00Z",
            "distanceMeters": 700,
            "durationSeconds": 600,
            "syncStatus": "readyToSync",
        },
    )
    assert session_response.status_code == 201
    assert session_response.json()["syncStatus"] == "synced"

    point_payload = {
        "userId": user_id,
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
    }
    first_upload = client.post(f"/walk-sessions/{session_id}/points", json=point_payload)
    second_upload = client.post(f"/walk-sessions/{session_id}/points", json=point_payload)

    assert first_upload.json() == {"saved": 1, "skippedDuplicates": 0}
    assert second_upload.json() == {"saved": 0, "skippedDuplicates": 1}

    sessions = client.get(f"/walk-sessions?userId={user_id}")
    assert sessions.status_code == 200
    assert len(sessions.json()[0]["points"]) == 1


def test_wrong_point_owner_returns_403(client: TestClient) -> None:
    owner_id = create_profile(client)
    other_id = client.post(
        "/profiles",
        json={"nickname": "partner", "deviceId": "00000000-0000-0000-0000-000000000002"},
    ).json()["id"]
    session_id = "11111111-1111-1111-1111-111111111111"
    client.post(
        "/walk-sessions",
        json={
            "id": session_id,
            "userId": owner_id,
            "startedAt": "2026-06-08T12:00:00Z",
            "distanceMeters": 0,
            "durationSeconds": 0,
            "syncStatus": "readyToSync",
        },
    )

    response = client.post(f"/walk-sessions/{session_id}/points", json={"userId": other_id, "points": []})

    assert response.status_code == 403
