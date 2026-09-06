# URBISQC — GeoSafe Québec

Spatial data-science platform scoring **Safety** (perceived-safety proxies) and **Calmness**
(tranquility vs. urban vibrancy) across Québec City on an **Uber H3** hexagonal grid
(resolutions 8 & 9). Bare-metal stack — no Docker, no standalone database.

## Stack

| Layer | Technology |
|---|---|
| Spatial indexing | H3 v4 (`h3-py`) |
| Data engine | Python 3.11, pandas, shapely, geopandas, osmnx, DuckDB (embedded), Parquet |
| ML / analytics | scikit-learn — RobustScaler + K-Means zone profiling |
| Backend API | FastAPI (async, Pydantic v2, CORS) |
| Frontend | Single-file MapLibre GL SPA served by FastAPI at `/` |

## Quick start

```bash
./run.sh                 # venv + deps + ETL (auto) + server on :8000
./run.sh --offline       # force deterministic synthetic data (no network)
make install test run    # equivalent Make workflow
```

Windows (PowerShell) equivalent:

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r backend\requirements.txt
cd backend
..\.venv\Scripts\python -m pytest
..\.venv\Scripts\python -m uvicorn app.main:app --port 8000
```

Open **http://127.0.0.1:8000** — choose the metric (Sécurité / Quiétude), switch H3
resolution, click a hex for details, and open the *Simulation* panel to re-weight the
scoring model live.

## Data flow

1. **Boundary** — OSM geocoding of Québec City (bbox fallback when offline).
2. **Grid** — H3 cells at resolutions 8 and 9 covering the boundary.
3. **Features** — 10 urban feature categories counted per cell (OSM via `osmnx`; a
   deterministic synthetic generator with a downtown-distance gradient is used when
   offline or on network failure).
4. **Scores** — RobustScaler → weighted blend → percentile rank (0–100).
5. **Profiles** — K-Means (k=5) with human-readable cluster labels.
6. **Storage** — Parquet per resolution in `data/processed/` + DuckDB views
   (`zones_res8`, `zones_res9`) in `data/processed/urbisqc.duckdb`.

## API

| Endpoint | Description |
|---|---|
| `GET /api/health` | Service status & loaded zone counts |
| `GET /api/zones?resolution=8` | GeoJSON FeatureCollection with scores/profiles |
| `GET /api/zones/{h3}` | Full detail (counts, centroid, cluster) for one cell |
| `GET /api/stats?resolution=8` | Distribution statistics & profile histogram |
| `GET /api/weights` | Default model weights |
| `POST /api/simulate` | Re-score with user weight overrides (what-if) |

Interactive docs: `http://127.0.0.1:8000/docs`.

## Configuration (env, prefix `URBIS_`)

`URBIS_OFFLINE=1` (synthetic data), `URBIS_DATA_DIR`, `URBIS_RESOLUTIONS='[8,9]'`,
`URBIS_PORT`, `URBIS_CITY_QUERY`.

## Tests

```bash
cd backend && ../.venv/bin/python -m pytest    # or make test
```

Fully offline & deterministic — pipeline, scoring, clustering, and end-to-end API suites.

## Ad-hoc analytics (DuckDB)

```sql
-- .venv python: import duckdb; duckdb.connect('data/processed/urbisqc.duckdb')
SELECT profile, count(*), avg(safety_score) FROM zones_res8 GROUP BY profile;
```

See [DECISIONS.md](DECISIONS.md) for the architectural decision log.
