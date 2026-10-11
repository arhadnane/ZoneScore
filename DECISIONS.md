# Architectural Decision Log — URBIS / GeoSafe Cross-Border

| # | Decision | Rationale |
|---|----------|-----------|
| 1 | Workspace root (`ZoneScore/`) is used directly as the `urbisqc/` project root. | Avoids a redundant nesting level; all spec paths are preserved relative to root. |
| 2 | H3 v4 Python API (`h3>=4.0`) with `geo_to_cells` on shapely geometries. | v4 is the maintained API; `__geo_interface__` integration removes manual coordinate munging. |
| 3 | Geometry is **not persisted**; hex boundaries are derived on demand from H3 cell ids via `cell_to_boundary`. | H3 ids are a lossless spatial encoding — persisting only ids + attributes keeps Parquet small and schema simple. |
| 4 | Embedded storage = Parquet (canonical) + DuckDB file exposing views over the Parquet. | Zero standalone services; DuckDB gives ad-hoc SQL analytics over the same files. |
| 5 | OSM ingestion with multi-tier fallback: Local PBF (DuckDB Spatial) → Overpass API → Deterministic synthetic fallback (`URBIS_OFFLINE=1`). | Guarantees the pipeline always completes; synthetic data uses a seeded hash + downtown-distance gradient so results are reproducible and spatially plausible when network is unavailable. |
| 6 | City boundary: Exact bounding boxes per metropolitan urban agglomeration (`app/core/cities.py`). | Prevents Overpass query timeouts and national-scale memory bloat by focusing directly on urban cores. |
| 7 | Scores = robust-scaled (median/IQR) feature counts → weighted linear blend → percentile rank mapped to 0–100. | RobustScaler resists heavy-tailed POI counts; percentile ranking yields an interpretable, uniformly distributed score. |
| 8 | Clustering = K-Means (k=5) on robust-scaled features, with human-readable profile labels derived from cluster centroids. | K-Means is stable, fast and deterministic (fixed seed); HDBSCAN rejected as it produces noise labels that complicate the UI. |
| 9 | Frontend = single self-contained `index.html` (MapLibre GL via CDN) served by FastAPI at `/`. | No build step, no Node toolchain required at runtime — satisfies bare-metal, zero-friction constraint. |
| 10 | Simulation endpoint recomputes scores server-side from persisted feature counts with user-supplied weight overrides. | Keeps the scoring model authoritative in one place; frontend stays a thin client. |
| 11 | API loads Parquet into an in-process cache at startup; if artifacts are missing the ETL pipeline runs automatically. | Single-command launch (`run.sh` / `make run`) works from a clean clone. |
| 12 | Tests run fully offline (`URBIS_OFFLINE=1`) against a temporary data directory. | Deterministic, network-free CI. |
| 13 | Pre-cached scaled features in `ZoneStore` (`scaled_frame`) for `/api/simulate`. | Eliminates redundant `RobustScaler.fit_transform()` calls on what-if simulations, achieving sub-10ms response times. |
| 14 | Automatic GZip compression on FastAPI (`GZipMiddleware`, `minimum_size=1000`). | Drastically reduces GeoJSON network transfer payload (~70-80% compression). |
| 15 | H3 polygon coverage expansion for large urban spaces (parks, industrial zones). | Replaces single representative points with `h3.geo_to_cells` to avoid concentrating multi-hectare parks in a single cell. |
| 16 | Multi-Metropolitan Cross-Border Architecture (Canada & USA). | Partitions urban coverage across major metropolitan areas (Québec, Montréal, Ottawa, Toronto, Vancouver, Calgary, Edmonton, New York, Los Angeles, Chicago, Seattle, Boston, Houston) with Country › Province/State › City cascading hierarchy. |
| 17 | On-Demand Live OSM Enrichment (`GET /api/zones/{h3}?live=true`). | Complements the pre-computed grid with instant live OpenStreetMap REST API queries on cell click, showing real-time venue names, active POIs, and live indicators without pre-download bottlenecks. |
| 18 | Local PBF Extraction via DuckDB Spatial (`ST_ReadOSM`). | Allows processing entire provincial/state extracts (e.g. `quebec-latest.osm.pbf`) in seconds with 0 external network requests, bypassing Overpass server rate limits. |
