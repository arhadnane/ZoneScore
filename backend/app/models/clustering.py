"""Zone profiling via K-Means clustering on robust-scaled feature counts."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans

from app.models.scoring import robust_scale

N_CLUSTERS = 5
_RANDOM_STATE = 42

# Ordered heuristics: first matching rule names the cluster profile.
_PROFILE_RULES: tuple[tuple[str, str, str], ...] = (
    ("bar_nightlife", "high", "Vibrant nightlife district"),
    ("industrial", "high", "Industrial / logistics corridor"),
    ("park_green", "high", "Green haven"),
    ("shop_retail", "high", "Commercial & services hub"),
    ("major_road", "high", "High-traffic artery zone"),
)
_DEFAULT_PROFILE = "Tranquil residential"


def _label_centroid(centroid: pd.Series, global_std: pd.Series) -> str:
    """Derive a human-readable profile from a cluster centroid signature."""
    for feature, _, label in _PROFILE_RULES:
        if feature in centroid.index and centroid[feature] > 0.75 * max(global_std.get(feature, 1.0), 1e-9):
            return label
    return _DEFAULT_PROFILE


def cluster_zones(counts: pd.DataFrame, n_clusters: int = N_CLUSTERS) -> pd.DataFrame:
    """Assign each cell a cluster id and profile label.

    Returns a DataFrame with ``cluster`` (int) and ``profile`` (str) columns.
    """
    scaled = robust_scale(counts)
    k = min(n_clusters, max(1, len(scaled)))
    if k == 1 or len(scaled) < 2:
        return pd.DataFrame(
            {"cluster": np.zeros(len(scaled), dtype=int), "profile": _DEFAULT_PROFILE},
            index=scaled.index,
        )
    model = KMeans(n_clusters=k, n_init=10, random_state=_RANDOM_STATE)
    labels = model.fit_predict(scaled.to_numpy())
    centroids = pd.DataFrame(model.cluster_centers_, columns=scaled.columns)
    global_std = scaled.std()
    profiles = {i: _label_centroid(centroids.iloc[i], global_std) for i in range(k)}
    return pd.DataFrame(
        {"cluster": labels, "profile": [profiles[i] for i in labels]},
        index=scaled.index,
    )
