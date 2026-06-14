from typing import Annotated

from fastapi import APIRouter, Query

from app.map_vectors import MAP_AREA_ID
from app.schemas import MapCoverageCandidatesRequest, MapCoverageCandidatesResponse
from app.store import store


router = APIRouter(prefix="/map", tags=["map"])


@router.get("/features")
def get_map_features(
    south: Annotated[float, Query(ge=-90, le=90)],
    west: Annotated[float, Query(ge=-180, le=180)],
    north: Annotated[float, Query(ge=-90, le=90)],
    east: Annotated[float, Query(ge=-180, le=180)],
    covered_feature_ids: Annotated[str, Query(alias="coveredFeatureIds")] = "",
    active_feature_ids: Annotated[str, Query(alias="activeFeatureIds")] = "",
) -> dict:
    covered_ids = _parse_ids(covered_feature_ids)
    active_ids = _parse_ids(active_feature_ids)
    return store.map_vector_store.feature_collection(
        south=south,
        west=west,
        north=north,
        east=east,
        covered_side_ids=covered_ids,
        active_side_ids=active_ids,
    )


@router.post("/coverage-candidates", response_model=MapCoverageCandidatesResponse)
def coverage_candidates(payload: MapCoverageCandidatesRequest) -> MapCoverageCandidatesResponse:
    covered_ids = store.map_vector_store.covered_side_ids_for_points(payload.points)
    return MapCoverageCandidatesResponse(
        areaId=MAP_AREA_ID,
        coveredFeatureIds=sorted(covered_ids),
    )


def _parse_ids(raw_value: str) -> set[str]:
    if not raw_value:
        return set()
    return {item for item in raw_value.split(",") if item}
