cat > /Users/deepakverma/Documents/monocarton-backend/README.md << 'EOF'
# Mono Backend

FastAPI backend for Mono — the Monocarton Imposition Planner.

## What it does
Receives carton and sheet dimensions via REST API, runs layout algorithms, and returns precise carton positions as JSON for the frontend to render.

## Tech Stack
- Python 3.12
- FastAPI
- Uvicorn
- Hosted on Railway

## Local Setup

### Prerequisites
- Python 3.12+
- pip

### Install dependencies
```bash
pip install fastapi uvicorn pydantic
```

### Run locally
```bash
uvicorn main:app --reload
```

API will be available at `http://127.0.0.1:8000`
Auto docs available at `http://127.0.0.1:8000/docs`

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | / | Health check |
| POST | /layout/straight | Straight layout calculation |
| POST | /layout/tumble | Tumble layout calculation |
| POST | /layout/first-fit | First Fit algorithm |
| POST | /layout/first-fit-decreasing | First Fit Decreasing algorithm |
| POST | /layout/nfdh | Next Fit Decreasing Height algorithm |
| POST | /layout/best-fit | Best Fit algorithm |
| POST | /layout/compare | Run all algorithms and return ranked comparison |

## Request Format
All layout endpoints accept the same request body:
```json
{
  "carton_w": 6,
  "carton_h": 9,
  "sheet_w": 23,
  "sheet_h": 36,
  "margin": 1,
  "nesting_pct": 10
}
```

## Response Format
```json
{
  "layout_type": "straight",
  "cartons": [
    { "x": 1, "y": 1, "w": 6, "h": 9, "flipped": false, "row": 0, "col": 0 }
  ],
  "total_cartons": 9,
  "cartons_per_row": 3,
  "num_rows": 3,
  "utilization": 68.07,
  "usable_w": 21,
  "usable_h": 34,
  "sheet_w": 23,
  "sheet_h": 36,
  "margin": 1,
  "nesting_saving": 0,
  "pair_height": 0,
  "algorithm_notes": ""
}
```

## Deployment
Hosted on Railway. Auto deploys on every push to main branch.

Live URL: `https://web-production-e59f.up.railway.app`

## Algorithms Implemented
- Straight Layout — simple row by row placement
- Tumble Layout — alternate rows flipped 180° with nesting saving
- First Fit — place in first available position
- First Fit Decreasing — sort by size then First Fit
- NFDH — shelf based packing sorted by height
- Best Fit — place in shelf with least remaining space

## Changelog
- v1.1 — Added Tier 2 algorithms: FF, FFD, NFDH, Best Fit, Compare endpoint
- v1.0 — Initial release with Straight and Tumble layout
EOF