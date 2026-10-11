"""In-process zone data store: loads Parquet artifacts and caches GeoJSON across Canadian cities."""

from __future__ import annotations

from threading import Lock

import pandas as pd

from app.core.cities import DEFAULT_CITY_ID, get_city, list_cities
from app.core.config import Settings, get_settings
from app.core.constants import FEATURES
from app.core.logging import get_logger
from app.etl.grid import cell_centroid, cell_polygon_coords
from app.models.scoring import compute_scores_from_scaled, robust_scale

log = get_logger(__name__)


class ZoneStore:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        # Keyed by (city_id, resolution)
        self._frames: dict[tuple[str, int], pd.DataFrame] = {}
        self._scaled_frames: dict[tuple[str, int], pd.DataFrame] = {}
        self._geojson_cache: dict[tuple[str, int], dict] = {}
        self._lock = Lock()

    @property
    def settings(self) -> Settings:
        return self._settings

    def load_city(self, city_id: str, run_etl_if_missing: bool = False) -> bool:
        """Load resolution tables for a single city. Returns True if data was loaded."""
        c = get_city(city_id)
        cid = c.id
        loaded_any = False
        with self._lock:
            for res in self._settings.resolutions:
                path = self._settings.city_parquet(cid, res)
                if path.exists():
                    df = pd.read_parquet(path).set_index("h3")
                    counts = df[[f for f in FEATURES if f in df.columns]]
                    scaled = robust_scale(counts)
                    self._scaled_frames[(cid, res)] = scaled
                    if "family_score" not in df.columns:
                        dyn_scores = compute_scores_from_scaled(scaled)
                        df["family_score"] = dyn_scores["family_score"]
                    self._frames[(cid, res)] = df
                    self._geojson_cache.pop((cid, res), None)
                    loaded_any = True
                    log.info(
                        "Loaded %d zones for city '%s' at resolution %d.", len(df), cid, res
                    )
        if not loaded_any and run_etl_if_missing:
            log.info("Artifacts missing for city '%s'; running ETL pipeline...", cid)
            from app.etl.pipeline import run_pipeline

            run_pipeline(self._settings, city_ids=[cid])
            return self.load_city(cid, run_etl_if_missing=False)
        return loaded_any

    def load(self, run_etl_if_missing: bool = True) -> None:
        """Load all available city tables, running ETL for default city (quebec) if absent."""
        legacy_res8 = self._settings.processed_dir / "zones_res8.parquet"
        quebec_res8 = self._settings.city_parquet("quebec", 8)
        if not legacy_res8.exists() and not quebec_res8.exists() and run_etl_if_missing:
            log.info("Default artifacts missing; running ETL pipeline for Québec.")
            from app.etl.pipeline import run_pipeline

            run_pipeline(self._settings, city_ids=["quebec"])

        for city_cfg in list_cities():
            self.load_city(city_cfg.id, run_etl_if_missing=False)

    def loaded_cities(self) -> list[str]:
        with self._lock:
            cids = {cid for cid, _ in self._frames}
            return sorted(list(cids)) if cids else [DEFAULT_CITY_ID]

    def resolutions(self, city: str = DEFAULT_CITY_ID) -> list[int]:
        c = get_city(city).id
        with self._lock:
            res_list = [r for (cid, r) in self._frames if cid == c]
            return sorted(res_list) if res_list else sorted(list(self._settings.resolutions))

    def zone_counts(self, city: str = DEFAULT_CITY_ID) -> dict[int, int]:
        c = get_city(city).id
        with self._lock:
            return {res: len(df) for (cid, res), df in self._frames.items() if cid == c}

    def frame(self, resolution: int, city: str = DEFAULT_CITY_ID) -> pd.DataFrame:
        c = get_city(city).id
        key = (c, resolution)
        with self._lock:
            if key not in self._frames:
                self.load_city(c, run_etl_if_missing=False)
            if key not in self._frames:
                raise KeyError(f"No data for city '{c}' at resolution {resolution}.")
            return self._frames[key]

    def scaled_frame(self, resolution: int, city: str = DEFAULT_CITY_ID) -> pd.DataFrame:
        c = get_city(city).id
        key = (c, resolution)
        with self._lock:
            if key not in self._scaled_frames:
                self.frame(resolution, city=c)
            return self._scaled_frames[key]

    def geojson(self, resolution: int, city: str = DEFAULT_CITY_ID) -> dict:
        """GeoJSON FeatureCollection for a resolution and city (built once, cached)."""
        c = get_city(city).id
        key = (c, resolution)
        with self._lock:
            if key in self._geojson_cache:
                return self._geojson_cache[key]
        df = self.frame(resolution, city=c)
        cells = df.index.tolist()
        safety = df["safety_score"].astype(float).tolist()
        calmness = df["calmness_score"].astype(float).tolist()
        family = (
            df["family_score"].astype(float).tolist()
            if "family_score" in df.columns
            else [50.0] * len(cells)
        )
        clusters = df["cluster"].astype(int).tolist()
        profiles = df["profile"].astype(str).tolist()

        features = [
            {
                "type": "Feature",
                "id": cell,
                "geometry": {"type": "Polygon", "coordinates": [cell_polygon_coords(cell)]},
                "properties": {
                    "h3": cell,
                    "city": c,
                    "safety_score": s,
                    "calmness_score": clm,
                    "family_score": fam,
                    "cluster": cl,
                    "profile": pr,
                },
            }
            for cell, s, clm, fam, cl, pr in zip(
                cells, safety, calmness, family, clusters, profiles, strict=False
            )
        ]
        collection = {"type": "FeatureCollection", "features": features}
        with self._lock:
            self._geojson_cache[key] = collection
        return collection

    def zone_detail(self, cell: str, city: str | None = None) -> dict | None:
        """Find details for an H3 cell. If city is specified, search that city first."""
        target_keys: list[tuple[str, int]] = []
        if city:
            c = get_city(city).id
            target_keys = [(c, res) for res in self._settings.resolutions]
        with self._lock:
            all_keys = list(self._frames.keys())
        for k in all_keys:
            if k not in target_keys:
                target_keys.append(k)

        for (cid, res) in target_keys:
            with self._lock:
                df = self._frames.get((cid, res))
            if df is not None and cell in df.index:
                row = df.loc[cell]
                lat, lng = cell_centroid(cell)
                return {
                    "h3": cell,
                    "city": cid,
                    "resolution": res,
                    "safety_score": float(row["safety_score"]),
                    "calmness_score": float(row["calmness_score"]),
                    "family_score": float(row.get("family_score", 50.0)),
                    "cluster": int(row["cluster"]),
                    "profile": str(row["profile"]),
                    "counts": {f: int(row[f]) for f in FEATURES if f in df.columns},
                    "centroid": (lat, lng),
                }
        return None


_store: ZoneStore | None = None


def get_store() -> ZoneStore:
    global _store
    if _store is None:
        _store = ZoneStore()
    return _store


def reset_store() -> None:
    """Test hook: drop the singleton so a fresh Settings instance is picked up."""
    global _store
    _store = None
