from fastapi import APIRouter, HTTPException, Response, status

from app.schemas import ProfileCreate, ProfileResponse
from app.store import store

router = APIRouter(prefix="/profiles", tags=["profiles"])


@router.post("", response_model=ProfileResponse)
def create_or_relink_profile(payload: ProfileCreate, response: Response) -> ProfileResponse:
    profile, created = store.create_or_relink_profile(payload)
    response.status_code = status.HTTP_201_CREATED if created else status.HTTP_200_OK
    return profile


@router.get("/by-nickname/{nickname}", response_model=ProfileResponse)
def get_profile_by_nickname(nickname: str) -> ProfileResponse:
    profile = store.profile_by_nickname(nickname)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Profile not found")
    return profile
