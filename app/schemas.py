from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


Nickname = Annotated[str, Field(min_length=1, max_length=32)]


def utc_now() -> datetime:
    return datetime.now(UTC)


def ensure_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class APIModel(BaseModel):
    model_config = ConfigDict(populate_by_name=True)


class ProfileCreate(APIModel):
    nickname: Nickname
    device_id: UUID = Field(alias="deviceId")

    @field_validator("nickname")
    @classmethod
    def validate_nickname(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("nickname cannot be empty")
        allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 _-")
        if any(character not in allowed for character in cleaned):
            raise ValueError("nickname may contain letters, numbers, spaces, _ and -")
        return cleaned


class ProfileResponse(APIModel):
    id: UUID
    nickname: str
    device_id: UUID = Field(alias="deviceId")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")


class TrackPointCreate(APIModel):
    id: UUID
    latitude: float = Field(ge=-90, le=90)
    longitude: float = Field(ge=-180, le=180)
    altitude: float | None = None
    horizontal_accuracy: float = Field(alias="horizontalAccuracy", ge=0)
    timestamp: datetime

    @field_validator("timestamp")
    @classmethod
    def normalize_timestamp(cls, value: datetime) -> datetime:
        return ensure_utc(value)


class WalkSessionCreate(APIModel):
    id: UUID
    user_id: UUID = Field(alias="userId")
    started_at: datetime = Field(alias="startedAt")
    ended_at: datetime | None = Field(default=None, alias="endedAt")
    distance_meters: float = Field(default=0, alias="distanceMeters", ge=0)
    duration_seconds: float = Field(default=0, alias="durationSeconds", ge=0)
    sync_status: str = Field(default="readyToSync", alias="syncStatus")

    @field_validator("started_at", "ended_at")
    @classmethod
    def normalize_datetime(cls, value: datetime | None) -> datetime | None:
        return ensure_utc(value) if value is not None else None

    @model_validator(mode="after")
    def validate_ended_after_started(self) -> "WalkSessionCreate":
        if self.ended_at is not None and self.ended_at < self.started_at:
            raise ValueError("endedAt must be greater than or equal to startedAt")
        return self


class TrackPointResponse(TrackPointCreate):
    pass


class WalkSessionResponse(APIModel):
    id: UUID
    user_id: UUID = Field(alias="userId")
    started_at: datetime = Field(alias="startedAt")
    ended_at: datetime | None = Field(alias="endedAt")
    distance_meters: float = Field(alias="distanceMeters")
    duration_seconds: float = Field(alias="durationSeconds")
    sync_status: str = Field(alias="syncStatus")
    points: list[TrackPointResponse] = []


class TrackPointsUploadRequest(APIModel):
    user_id: UUID = Field(alias="userId")
    points: list[TrackPointCreate]


class TrackPointsUploadResponse(APIModel):
    saved: int
    skipped_duplicates: int = Field(alias="skippedDuplicates")


class SharedProgressResponse(APIModel):
    total_distance_meters: float = Field(alias="totalDistanceMeters")
    total_walks: int = Field(alias="totalWalks")
    completed_routes_placeholder: int = Field(default=0, alias="completedRoutesPlaceholder")
    exploration_progress_percent_placeholder: float = Field(default=0.0, alias="explorationProgressPercentPlaceholder")


class CoverageUpsertRequest(APIModel):
    user_id: UUID = Field(alias="userId")
    area_id: str = Field(alias="areaId", min_length=1, max_length=80)
    covered_feature_ids: list[str] = Field(default_factory=list, alias="coveredFeatureIds")

    @field_validator("area_id")
    @classmethod
    def validate_area_id(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("areaId cannot be empty")
        return cleaned

    @field_validator("covered_feature_ids")
    @classmethod
    def validate_feature_ids(cls, value: list[str]) -> list[str]:
        cleaned = []
        seen = set()
        for feature_id in value:
            normalized = feature_id.strip()
            if not normalized or normalized in seen:
                continue
            cleaned.append(normalized)
            seen.add(normalized)
        return cleaned


class CoverageResponse(APIModel):
    user_id: UUID = Field(alias="userId")
    area_id: str = Field(alias="areaId")
    covered_feature_ids: list[str] = Field(alias="coveredFeatureIds")
    updated_at: datetime = Field(alias="updatedAt")


class MapCoverageCandidatesRequest(APIModel):
    points: list[TrackPointCreate]


class MapCoverageCandidatesResponse(APIModel):
    area_id: str = Field(alias="areaId")
    covered_feature_ids: list[str] = Field(alias="coveredFeatureIds")


class CoordinateResponse(APIModel):
    latitude: float
    longitude: float


class RouteResponse(APIModel):
    id: UUID
    user_id: UUID = Field(alias="userId")
    title: str
    coordinates: list[CoordinateResponse]
