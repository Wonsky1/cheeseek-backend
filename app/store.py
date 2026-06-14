from dataclasses import dataclass, field
from datetime import datetime
from threading import RLock
from uuid import UUID, uuid4

from app.map_vectors import MapVectorStore
from app.schemas import (
    CoverageResponse,
    CoverageUpsertRequest,
    ProfileCreate,
    ProfileResponse,
    RouteResponse,
    SharedProgressResponse,
    TrackPointCreate,
    TrackPointResponse,
    TrackPointsUploadResponse,
    WalkSessionCreate,
    WalkSessionResponse,
    utc_now,
)


@dataclass
class ProfileRecord:
    id: UUID
    nickname: str
    device_id: UUID
    created_at: datetime
    updated_at: datetime


@dataclass
class WalkSessionRecord:
    id: UUID
    user_id: UUID
    started_at: datetime
    ended_at: datetime | None
    distance_meters: float
    duration_seconds: float
    sync_status: str
    created_at: datetime
    updated_at: datetime


@dataclass
class CoverageRecord:
    user_id: UUID
    area_id: str
    covered_feature_ids: set[str]
    updated_at: datetime


@dataclass
class InMemoryStore:
    profiles: dict[UUID, ProfileRecord] = field(default_factory=dict)
    profiles_by_nickname: dict[str, UUID] = field(default_factory=dict)
    sessions: dict[UUID, WalkSessionRecord] = field(default_factory=dict)
    points_by_session: dict[UUID, dict[UUID, TrackPointCreate]] = field(default_factory=dict)
    coverage_by_user_area: dict[tuple[UUID, str], CoverageRecord] = field(default_factory=dict)
    map_vector_store: MapVectorStore = field(default_factory=MapVectorStore)
    lock: RLock = field(default_factory=RLock)

    def reset(self) -> None:
        with self.lock:
            self.profiles.clear()
            self.profiles_by_nickname.clear()
            self.sessions.clear()
            self.points_by_session.clear()
            self.coverage_by_user_area.clear()
            self.map_vector_store.reset()

    def create_or_relink_profile(self, payload: ProfileCreate) -> tuple[ProfileResponse, bool]:
        normalized = payload.nickname.casefold()
        now = utc_now()
        with self.lock:
            if normalized in self.profiles_by_nickname:
                profile = self.profiles[self.profiles_by_nickname[normalized]]
                profile.device_id = payload.device_id
                profile.updated_at = now
                return self._profile_response(profile), False

            profile = ProfileRecord(
                id=uuid4(),
                nickname=payload.nickname,
                device_id=payload.device_id,
                created_at=now,
                updated_at=now,
            )
            self.profiles[profile.id] = profile
            self.profiles_by_nickname[normalized] = profile.id
            return self._profile_response(profile), True

    def profile_by_nickname(self, nickname: str) -> ProfileResponse | None:
        with self.lock:
            profile_id = self.profiles_by_nickname.get(nickname.strip().casefold())
            if profile_id is None:
                return None
            return self._profile_response(self.profiles[profile_id])

    def profile_exists(self, profile_id: UUID) -> bool:
        with self.lock:
            return profile_id in self.profiles

    def save_walk_session(self, payload: WalkSessionCreate) -> tuple[WalkSessionResponse, bool]:
        now = utc_now()
        with self.lock:
            created = payload.id not in self.sessions
            existing = self.sessions.get(payload.id)
            self.sessions[payload.id] = WalkSessionRecord(
                id=payload.id,
                user_id=payload.user_id,
                started_at=payload.started_at,
                ended_at=payload.ended_at,
                distance_meters=payload.distance_meters,
                duration_seconds=payload.duration_seconds,
                sync_status="synced",
                created_at=existing.created_at if existing else now,
                updated_at=now,
            )
            self.points_by_session.setdefault(payload.id, {})
            return self._session_response(self.sessions[payload.id]), created

    def session_owner(self, session_id: UUID) -> UUID | None:
        with self.lock:
            session = self.sessions.get(session_id)
            return session.user_id if session else None

    def upload_points(
        self,
        session_id: UUID,
        points: list[TrackPointCreate],
    ) -> TrackPointsUploadResponse:
        with self.lock:
            point_bucket = self.points_by_session.setdefault(session_id, {})
            saved = 0
            skipped = 0
            for point in points:
                if point.id in point_bucket:
                    skipped += 1
                    continue
                point_bucket[point.id] = point
                saved += 1
            return TrackPointsUploadResponse(saved=saved, skippedDuplicates=skipped)

    def sessions_for_user(self, user_id: UUID) -> list[WalkSessionResponse]:
        with self.lock:
            sessions = [
                self._session_response(session)
                for session in self.sessions.values()
                if session.user_id == user_id
            ]
        return sorted(sessions, key=lambda session: session.started_at, reverse=True)

    def shared_progress(self) -> SharedProgressResponse:
        with self.lock:
            total_distance = sum(session.distance_meters for session in self.sessions.values())
            total_walks = len(self.sessions)
        return SharedProgressResponse(
            totalDistanceMeters=total_distance,
            totalWalks=total_walks,
            completedRoutesPlaceholder=0,
            explorationProgressPercentPlaceholder=0.0,
        )

    def coverage_for_user_area(self, user_id: UUID, area_id: str) -> CoverageResponse:
        normalized_area_id = area_id.strip()
        with self.lock:
            record = self.coverage_by_user_area.get((user_id, normalized_area_id))
            if record is None:
                return CoverageResponse(
                    userId=user_id,
                    areaId=normalized_area_id,
                    coveredFeatureIds=[],
                    updatedAt=utc_now(),
                )
            return self._coverage_response(record)

    def upsert_coverage(self, payload: CoverageUpsertRequest) -> CoverageResponse:
        key = (payload.user_id, payload.area_id)
        now = utc_now()
        with self.lock:
            record = self.coverage_by_user_area.get(key)
            if record is None:
                record = CoverageRecord(
                    user_id=payload.user_id,
                    area_id=payload.area_id,
                    covered_feature_ids=set(payload.covered_feature_ids),
                    updated_at=now,
                )
                self.coverage_by_user_area[key] = record
            else:
                record.covered_feature_ids.update(payload.covered_feature_ids)
                record.updated_at = now
            return self._coverage_response(record)

    def routes_for_user(self, user_id: UUID) -> list[RouteResponse]:
        with self.lock:
            routes = []
            for session in self.sessions.values():
                if session.user_id != user_id:
                    continue
                points = self._point_responses(session.id)
                routes.append(
                    RouteResponse(
                        id=session.id,
                        userId=session.user_id,
                        title=f"Walk on {session.started_at.date().isoformat()}",
                        coordinates=[
                            {"latitude": point.latitude, "longitude": point.longitude}
                            for point in points
                        ],
                    )
                )
        return routes

    def _profile_response(self, profile: ProfileRecord) -> ProfileResponse:
        return ProfileResponse(
            id=profile.id,
            nickname=profile.nickname,
            deviceId=profile.device_id,
            createdAt=profile.created_at,
            updatedAt=profile.updated_at,
        )

    def _session_response(self, session: WalkSessionRecord) -> WalkSessionResponse:
        return WalkSessionResponse(
            id=session.id,
            userId=session.user_id,
            startedAt=session.started_at,
            endedAt=session.ended_at,
            distanceMeters=session.distance_meters,
            durationSeconds=session.duration_seconds,
            syncStatus=session.sync_status,
            points=self._point_responses(session.id),
        )

    def _point_responses(self, session_id: UUID) -> list[TrackPointResponse]:
        points = list(self.points_by_session.get(session_id, {}).values())
        points.sort(key=lambda point: point.timestamp)
        return [TrackPointResponse(**point.model_dump(by_alias=True)) for point in points]

    def _coverage_response(self, record: CoverageRecord) -> CoverageResponse:
        return CoverageResponse(
            userId=record.user_id,
            areaId=record.area_id,
            coveredFeatureIds=sorted(record.covered_feature_ids),
            updatedAt=record.updated_at,
        )


store = InMemoryStore()
