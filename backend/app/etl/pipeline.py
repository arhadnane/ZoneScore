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


def build_zone_table(boundary, resolution: int, settings: Settings) -> pd.DataFrame:
    """Assemble the full zone table (counts + scores + clusters) for one resolution."""
    cells = generate_grid(boundary, resolution)
    counts = build_feature_counts(boundary, cells, resolution, settings)
    scores = compute_scores(counts)
    clusters = cluster_zones(counts)
    df = counts.join(scores).join(clusters)
    df.insert(0, "resolution", resolution)
    return df


def register_duckdb(settings: Settings) -> None:
    """(Re)create DuckDB views over the processed Parquet artifacts."""
    settings.processed_dir.mkdir(parents=True, exist_ok=True)
    con = duckdb.connect(str(settings.duckdb_path))
    try:
        for res in settings.resolutions:
            parquet = settings.zones_parquet(res)
            if parquet.exists():
                con.execute(
                    f"CREATE OR REPLACE VIEW zones_res{res} AS "
                    f"SELECT * FROM read_parquet('{parquet.as_posix()}')"
                )
        log.info("DuckDB views registered at %s.", settings.duckdb_path)
    finally:
        con.close()


def run_pipeline(settings: Settings | None = None) -> dict[int, pd.DataFrame]:
    """Execute the full pipeline for every configured resolution."""
    s = settings or get_settings()
    s.raw_dir.mkdir(parents=True, exist_ok=True)
    s.processed_dir.mkdir(parents=True, exist_ok=True)

    boundary = get_city_boundary(s)
    results: dict[int, pd.DataFrame] = {}
    for res in s.resolutions:
        df = build_zone_table(boundary, res, s)
        out = s.zones_parquet(res)
        df.reset_index().to_parquet(out, index=False)
        log.info("Wrote %d zones -> %s", len(df), out)
        results[res] = df
    register_duckdb(s)
    return results


if __name__ == "__main__":
    run_pipeline()
