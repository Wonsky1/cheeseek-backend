from fastapi import APIRouter

from app.schemas import SharedProgressResponse
from app.store import store

router = APIRouter(tags=["shared progress"])


@router.get("/shared-progress", response_model=SharedProgressResponse)
def get_shared_progress() -> SharedProgressResponse:
    return store.shared_progress()
