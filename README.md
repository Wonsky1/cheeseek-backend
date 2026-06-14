# Myshachki Backend

Small FastAPI POC backend for the private Myshachki walking app.

This version intentionally uses **in-memory storage**. Data resets whenever the server restarts. Nickname is also only a convenience identity for the POC, not real authentication.

## Run

```bash
uv run uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Or:

```bash
uv run python main.py
```

## Useful Endpoints

- `GET /health`
- `POST /profiles`
- `GET /profiles/by-nickname/{nickname}`
- `POST /walk-sessions`
- `POST /walk-sessions/{sessionId}/points`
- `GET /walk-sessions?userId={uuid}`
- `GET /coverage?userId={uuid}&areaId={areaId}`
- `PUT /coverage`
- `GET /map/features?south={lat}&west={lon}&north={lat}&east={lon}`
- `POST /map/coverage-candidates`
- `GET /shared-progress`
- `GET /routes?userId={uuid}`

## Map Data POC

The map endpoints keep vector geometry in memory for now. On first request for a viewport, the backend tries to load OpenStreetMap buildings and walkable roads from Overpass. If that fails, it returns generated demo geometry so the app still has a visible map overlay while developing.

Coverage IDs use `osm-building-sides-v1`; later this in-memory vector store can be replaced with PostGIS, Qdrant, or another spatial/vector database without changing the app contract.

## iPhone Notes

The iOS Simulator can call `http://127.0.0.1:8000`.

A real iPhone cannot use `127.0.0.1` for your Mac. Use your Mac/server LAN IP or a deployed server URL in the app configuration.
