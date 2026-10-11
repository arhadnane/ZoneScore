"""Application configuration (environment-driven, prefix ``URBIS_``)."""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repository root = two levels above backend/app/
_REPO_ROOT = Path(__file__).resolve().parents[3]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="URBIS_", case_sensitive=False)

    app_name: str = "ZoneScore — GeoSafe Urban Platform"
    version: str = "1.0.0"

    # Spatial scope
    city_query: str = "Québec (ville), Québec, Canada"
    # Fallback bounding box (lon_min, lat_min, lon_max, lat_max) for Québec City core.
    bbox_west: float = -71.415
    bbox_south: float = 46.720
    bbox_east: float = -71.130
    bbox_north: float = 46.905
    downtown_lat: float = 46.8131
    downtown_lng: float = -71.2075

    resolutions: tuple[int, ...] = (8, 9)

    # Storage
    data_dir: Path = _REPO_ROOT / "data"
    offline: bool = False  # force synthetic feature generation (no network)

    # Server
    host: str = "127.0.0.1"
    port: int = 8000

    @property
    def raw_dir(self) -> Path:
        return self.data_dir / "raw"

    @property
    def processed_dir(self) -> Path:
        return self.data_dir / "processed"

    @property
    def duckdb_path(self) -> Path:
        db_file = self.processed_dir / "zonescore.duckdb"
        if not db_file.exists():
            legacy_db = self.processed_dir / "urbisqc.duckdb"
            if legacy_db.exists():
                return legacy_db
        return db_file

    def city_parquet(self, city: str, resolution: int) -> Path:
        """Parquet file path for a specific city and resolution."""
        city_file = self.processed_dir / f"zones_{city.lower()}_res{resolution}.parquet"
        if city.lower() == "quebec" and not city_file.exists():
            legacy_file = self.processed_dir / f"zones_res{resolution}.parquet"
            if legacy_file.exists():
                return legacy_file
        return city_file

    def zones_parquet(self, resolution: int) -> Path:
        """Default access for Québec City zones."""
        return self.city_parquet("quebec", resolution)


@lru_cache
def get_settings() -> Settings:
    return Settings()
