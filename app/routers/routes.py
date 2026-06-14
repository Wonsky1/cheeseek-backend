from uuid import UUID

from fastapi import APIRouter, Query

from app.schemas import RouteResponse
from app.store import store

router = APIRouter(tags=["routes"])


@router.get("/routes", response_model=list[RouteResponse])
def get_routes(user_id: UUID = Query(alias="userId")) -> list[RouteResponse]:
    return store.routes_for_user(user_id)
