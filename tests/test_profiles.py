from fastapi.testclient import TestClient


def test_create_profile_returns_stable_profile(client: TestClient) -> None:
    response = client.post(
        "/profiles",
        json={"nickname": "vlad", "deviceId": "00000000-0000-0000-0000-000000000001"},
    )

    assert response.status_code == 201
    body = response.json()
    assert body["nickname"] == "vlad"
    assert body["deviceId"] == "00000000-0000-0000-0000-000000000001"


def test_same_nickname_relinks_existing_profile(client: TestClient) -> None:
    first = client.post(
        "/profiles",
        json={"nickname": "vlad", "deviceId": "00000000-0000-0000-0000-000000000001"},
    )
    second = client.post(
        "/profiles",
        json={"nickname": " VLAD ", "deviceId": "00000000-0000-0000-0000-000000000002"},
    )

    assert second.status_code == 200
    assert second.json()["id"] == first.json()["id"]
    assert second.json()["deviceId"] == "00000000-0000-0000-0000-000000000002"


def test_missing_nickname_returns_404(client: TestClient) -> None:
    response = client.get("/profiles/by-nickname/nope")

    assert response.status_code == 404
