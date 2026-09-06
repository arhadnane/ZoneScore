"""In-process zone data store: loads Parquet artifacts and caches GeoJSON."""
from __future__ import annotations

from threading import Lock

import pandas as pd

from app.core.config import Settings, get_settings
from app.core.constants import FEATURES
from app.core.logging import get_logger
from app.etl.grid import cell_centroid, cell_polygon_coords

log = get_logger(__name__)


class ZoneStore:
    def __init__(self, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()
        self._frames: dict[int, pd.DataFrame] = {}
        self._geojson_cache: dict[int, dict] = {}
        self._lock = Lock()

    @property
    def settings(self) -> Settings:
        return self._settings

    def load(self, run_etl_if_missing: bool = True) -> None:
        """Load all resolution tables, running the ETL pipeline if artifacts are absent."""
        missing = [r for r in self._settings.resolutions if not self._settings.zones_parquet(r).exists()]
        if missing and run_etl_if_missing:
            log.info("Artifacts missing for resolutions %s; running ETL pipeline.", missing)
            from app.etl.pipeline import run_pipeline

            run_pipeline(self._settings)
        with self._lock:
            self._frames.clear()
            self._geojson_cache.clear()
            for res in self._settings.resolutions:
                path = self._settings.zones_parquet(res)
                if path.exists():
                    self._frames[res] = pd.read_parquet(path).set_index("h3")
                    log.info("Loaded %d zones for resolution %d.", len(self._frames[res]), res)

    def resolutions(self) -> list[int]:
        return sorted(self._frames)

    def zone_counts(self) -> dict[int, int]:
        return {res: len(df) for res, df in self._frames.items()}

    def frame(self, resolution: int) -> pd.DataFrame:
        if resolution not in self._frames:
            raise KeyError(resolution)
        return self._frames[resolution]

    def geojson(self, resolution: int) -> dict:
        """GeoJSON FeatureCollection for a resolution (built once, then cached)."""
        with self._lock:
            if resolution in self._geojson_cache:
                return self._geojson_cache[resolution]
        df = self.frame(resolution)
        features = []
        for cell, row in df.iterrows():
            features.append(
                {
                    "type": "Feature",
                    "id": cell,
                    "geometry": {"type": "Polygon", "coordinates": [cell_polygon_coords(cell)]},
                    "properties": {
                        "h3": cell,
                        "safety_score": float(row["safety_score"]),
                        "calmness_score": float(row["calmness_score"]),
                        "cluster": int(row["cluster"]),
                        "profile": str(row["profile"]),
                    },
                }
            )
        collection = {"type": "FeatureCollection", "features": features}
        with self._lock:
            self._geojson_cache[resolution] = collection
        return collection

    def zone_detail(self, cell: str) -> dict | None:
        for res, df in self._frames.items():
            if cell in df.index:
                row = df.loc[cell]
                lat, lng = cell_centroid(cell)
                return {
                    "h3": cell,
                    "resolution": res,
                    "safety_score": float(row["safety_score"]),
                    "calmness_score": float(row["calmness_score"]),
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
