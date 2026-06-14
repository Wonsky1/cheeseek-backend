from uuid import UUID

from fastapi import APIRouter, Query

from app.schemas import CoverageResponse, CoverageUpsertRequest
from app.store import store


router = APIRouter(prefix="/coverage", tags=["coverage"])


@router.get("", response_model=CoverageResponse)
def get_coverage(user_id: UUID = Query(alias="userId"), area_id: str = Query(alias="areaId")) -> CoverageResponse:
    return store.coverage_for_user_area(user_id, area_id)


@router.put("", response_model=CoverageResponse)
def upsert_coverage(payload: CoverageUpsertRequest) -> CoverageResponse:
    return store.upsert_coverage(payload)
