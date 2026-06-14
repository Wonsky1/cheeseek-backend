from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.schemas import (
    TrackPointsUploadRequest,
    TrackPointsUploadResponse,
    WalkSessionCreate,
    WalkSessionResponse,
)
from app.store import store

router = APIRouter(prefix="/walk-sessions", tags=["walk sessions"])


@router.post("", response_model=WalkSessionResponse)
def create_or_update_walk_session(payload: WalkSessionCreate, response: Response) -> WalkSessionResponse:
    session, created = store.save_walk_session(payload)
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return session


@router.post("/{session_id}/points", response_model=TrackPointsUploadResponse)
def upload_track_points(session_id: UUID, payload: TrackPointsUploadRequest) -> TrackPointsUploadResponse:
    owner = store.session_owner(session_id)
    if owner is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Walk session not found")
    if owner != payload.user_id:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User does not own this session")
    return store.upload_points(session_id, payload.points)


@router.get("", response_model=list[WalkSessionResponse])
def get_walk_sessions(user_id: UUID = Query(alias="userId")) -> list[WalkSessionResponse]:
    return store.sessions_for_user(user_id)
