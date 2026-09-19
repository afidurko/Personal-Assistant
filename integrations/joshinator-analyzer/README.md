# Joshinator Analyzer

Real-time sports-card auction analyzer for live streams (OCR + pricing + ROI),
with an **IP-safe procedural 3D embodiment** layer.

## Features

- Screen-region capture + OCR card identification
- Optional Whisper audio fusion
- eBay comps + ROI signal (GREEN / YELLOW / RED / GRAY)
- **3D Embodiment:** detect → resolve original archetype → spawn procedural champion (no franchise character assets)

## Quick start

```bash
# Backend
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
# from backend/ with PYTHONPATH set, or:
cd ..
PYTHONPATH=backend uvicorn app.main:socket_app --app-dir backend --host 0.0.0.0 --port 3001

# Frontend
cd frontend
npm install
npm start
```

## Embodiment (IP-safe)

See [docs/EMBODIMENT.md](docs/EMBODIMENT.md).

```bash
# Unit tests (no GPU / OCR required)
PYTHONPATH=backend python3 -m unittest backend.test_embodiment -v
```

REST:

- `GET /api/embodiment/catalog`
- `POST /api/embodiment/resolve` with `{ "card_info": { "player_name": "...", "sport": "Baseball" } }`

## Docs

- [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- [docs/VISION.md](docs/VISION.md)
- [docs/EMBODIMENT.md](docs/EMBODIMENT.md)
- [docs/STARTUP.md](docs/STARTUP.md)
