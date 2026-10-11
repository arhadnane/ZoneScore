"""End-to-end ETL pipeline: grid -> feature counts -> scores -> clusters -> Parquet/DuckDB."""

from __future__ import annotations

import duckdb
import pandas as pd

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.etl.features import build_feature_counts
from app.etl.grid import generate_grid, get_city_boundary
from app.models.clustering import cluster_zones
from app.models.scoring import compute_scores

log = get_logger(__name__)


def build_zone_table(
    boundary, resolution: int, settings: Settings, city: str | None = None
) -> pd.DataFrame:
    """Assemble the full zone table (counts + scores + clusters) for one resolution and city."""
    cells = generate_grid(boundary, resolution)
    counts = build_feature_counts(boundary, cells, resolution, settings, city=city)
    scores = compute_scores(counts)
    clusters = cluster_zones(counts)
    df = counts.join(scores).join(clusters)
    df.insert(0, "resolution", resolution)
    if city:
        df.insert(1, "city", city)
    return df


def register_duckdb(settings: Settings) -> None:
    """(Re)create DuckDB views over the processed Parquet artifacts for all Canadian cities."""
    from app.core.cities import list_cities

    settings.processed_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(settings.duckdb_path))
    try:
        # Legacy views
        for res in settings.resolutions:
            parquet = settings.zones_parquet(res)
            if parquet.exists():
                con.execute(
                    f"CREATE OR REPLACE VIEW zones_res{res} AS "
                    f"SELECT * FROM read_parquet('{parquet.as_posix()}')"
                )
        # City-specific views
        for city_cfg in list_cities():
            for res in settings.resolutions:
                city_parquet = settings.city_parquet(city_cfg.id, res)
                if city_parquet.exists():
                    con.execute(
                        f"CREATE OR REPLACE VIEW zones_{city_cfg.id}_res{res} AS "
                        f"SELECT * FROM read_parquet('{city_parquet.as_posix()}')"
                    )
        log.info("DuckDB views registered at %s.", settings.duckdb_path)
    finally:
        con.close()


def run_pipeline(
    settings: Settings | None = None, city_ids: list[str] | None = None
) -> dict[str, dict[int, pd.DataFrame]]:
    """Execute the pipeline for specified cities (or default city) and resolutions."""
    from app.core.cities import get_city

    s = settings or get_settings()
    s.raw_dir.mkdir(parents=True, exist_ok=True)
    s.processed_dir.mkdir(parents=True, exist_ok=True)

    target_cities = [get_city(cid) for cid in city_ids] if city_ids else [get_city()]
    all_results: dict[str, dict[int, pd.DataFrame]] = {}

    for city_cfg in target_cities:
        log.info("Running ETL pipeline for %s (%s)...", city_cfg.name, city_cfg.province)
        boundary = get_city_boundary(city=city_cfg.id, settings=s)
        city_results: dict[int, pd.DataFrame] = {}
        for res in s.resolutions:
            df = build_zone_table(boundary, res, s, city=city_cfg.id)
            out = s.city_parquet(city_cfg.id, res)
            df.reset_index().to_parquet(out, index=False)
            log.info("Wrote %d zones for %s (res %d) -> %s", len(df), city_cfg.id, res, out)
            # Also keep legacy zones_res{res}.parquet updated if city is quebec
            if city_cfg.id == "quebec":
                legacy_out = s.processed_dir / f"zones_res{res}.parquet"
                df.reset_index().to_parquet(legacy_out, index=False)
            city_results[res] = df
        all_results[city_cfg.id] = city_results

    register_duckdb(s)
    return all_results


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="URBIS Canada ETL Pipeline")
    parser.add_argument("--cities", type=str, default="all", help="Comma-separated cities or 'all'")
    parser.add_argument("--offline", action="store_true", help="Run in offline/synthetic mode")
    args = parser.parse_args()

    s = get_settings()
    if args.offline:
        s.offline = True

    if args.cities == "all":
        from app.core.cities import list_cities

        cids = [c.id for c in list_cities()]
    else:
        cids = [c.strip() for c in args.cities.split(",")]

    run_pipeline(s, city_ids=cids)
