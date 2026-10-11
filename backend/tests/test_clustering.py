"""Clustering model tests."""

from __future__ import annotations

import numpy as np
import pandas as pd
from app.core.constants import FEATURES
from app.models.clustering import N_CLUSTERS, cluster_zones


def _frame(n: int = 60) -> pd.DataFrame:
    rng = np.random.RandomState(11)
    return pd.DataFrame({f: rng.poisson(3, n) for f in FEATURES}, index=[f"c{i}" for i in range(n)])


def test_cluster_assignment_shape():
    df = _frame()
    result = cluster_zones(df)
    assert len(result) == len(df)
    assert set(result.columns) == {"cluster", "profile"}
    assert result["cluster"].between(0, N_CLUSTERS - 1).all()
    assert (result["profile"].str.len() > 0).all()


def test_cluster_deterministic():
    df = _frame()
    a = cluster_zones(df)
    b = cluster_zones(df)
    assert a["cluster"].equals(b["cluster"])


def test_tiny_input_single_cluster():
    df = _frame(1)
    result = cluster_zones(df)
    assert len(result) == 1
    assert result["cluster"].iloc[0] == 0
