from fastapi.testclient import TestClient


def create_profile(client: TestClient) -> str:
    response = client.post(
        "/profiles",
        json={"nickname": "coverage-user", "deviceId": "11111111-1111-1111-1111-111111111111"},
    )
    assert response.status_code == 201
    return response.json()["id"]


def test_get_empty_coverage_for_known_profile(client: TestClient) -> None:
    user_id = create_profile(client)

    response = client.get(f"/coverage?userId={user_id}&areaId=warsaw-demo-v1")

    assert response.status_code == 200
    assert response.json()["userId"] == user_id
    assert response.json()["areaId"] == "warsaw-demo-v1"
    assert response.json()["coveredFeatureIds"] == []


def test_upsert_coverage_merges_feature_ids(client: TestClient) -> None:
    user_id = create_profile(client)

    first = client.put(
        "/coverage",
        json={
            "userId": user_id,
            "areaId": "warsaw-demo-v1",
            "coveredFeatureIds": ["demo-1-1", "demo-1-2", "demo-1-1"],
        },
    )
    second = client.put(
        "/coverage",
        json={
            "userId": user_id,
            "areaId": "warsaw-demo-v1",
            "coveredFeatureIds": ["demo-1-2", "demo-2-1"],
        },
    )

    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["coveredFeatureIds"] == ["demo-1-1", "demo-1-2", "demo-2-1"]


def test_get_empty_coverage_for_unknown_profile(client: TestClient) -> None:
    response = client.get("/coverage?userId=11111111-1111-1111-1111-111111111111&areaId=warsaw-demo-v1")

    assert response.status_code == 200
    assert response.json()["coveredFeatureIds"] == []
