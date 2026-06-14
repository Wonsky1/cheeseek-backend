from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.schemas import RouteResponse
from app.store import store

router = APIRouter(tags=["routes"])


@router.get("/routes", response_model=list[RouteResponse])
def get_routes(user_id: UUID = Query(alias="userId")) -> list[RouteResponse]:
    if not store.profile_exists(user_id):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return store.routes_for_user(user_id)
