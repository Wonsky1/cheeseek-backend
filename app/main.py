from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.routers import coverage, health, map_data, profiles, routes, shared_progress, walk_sessions

app = FastAPI(
    title="Cheeseek Backend",
    description="Small in-memory POC backend for the private walking app.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health.router)
app.include_router(profiles.router)
app.include_router(walk_sessions.router)
app.include_router(shared_progress.router)
app.include_router(routes.router)
app.include_router(coverage.router)
app.include_router(map_data.router)
