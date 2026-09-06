"""Safety & Calmness scoring model.

Pipeline: robust scaling (median/IQR) of per-cell feature counts ->
weighted linear blend -> percentile rank mapped to [0, 100].
"""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.preprocessing import RobustScaler

from app.core.constants import FEATURES

# Positive weight => feature improves the score; negative => degrades it.
SAFETY_WEIGHTS: dict[str, float] = {
    "streetlight": 0.25,
    "police_fire": 0.15,
    "transit_stop": 0.10,
    "school": 0.10,
    "park_green": 0.05,
    "shop_retail": 0.05,
    "restaurant_cafe": 0.05,
    "bar_nightlife": -0.30,
    "industrial": -0.10,
    "major_road": -0.05,
}

CALMNESS_WEIGHTS: dict[str, float] = {
    "park_green": 0.35,
    "school": 0.10,
    "streetlight": 0.05,
    "bar_nightlife": -0.30,
    "restaurant_cafe": -0.15,
    "shop_retail": -0.10,
    "major_road": -0.25,
    "industrial": -0.20,
    "transit_stop": -0.10,
    "police_fire": 0.05,
}


def robust_scale(counts: pd.DataFrame) -> pd.DataFrame:
    """Robust-scale feature counts, clipped to [-3, 3] to bound outlier leverage."""
    cols = [f for f in FEATURES if f in counts.columns]
    scaler = RobustScaler(quantile_range=(25.0, 75.0))
    scaled = scaler.fit_transform(counts[cols].astype(float))
    # Constant columns yield IQR=0 -> RobustScaler leaves them centred; ensure finite values.
    scaled = np.nan_to_num(scaled, nan=0.0, posinf=3.0, neginf=-3.0)
    return pd.DataFrame(np.clip(scaled, -3.0, 3.0), index=counts.index, columns=cols)


def weighted_blend(scaled: pd.DataFrame, weights: dict[str, float]) -> pd.Series:
    """Weighted sum of scaled features (missing features contribute zero)."""
    blend = pd.Series(0.0, index=scaled.index)
    for feature, weight in weights.items():
        if feature in scaled.columns:
            blend = blend + weight * scaled[feature]
    return blend


def to_score(blend: pd.Series) -> pd.Series:
    """Map a raw blend to a 0-100 percentile-rank score."""
    if len(blend) == 1:
        return pd.Series(50.0, index=blend.index)
    return (blend.rank(pct=True, method="average") * 100.0).round(1)


def compute_scores(
    counts: pd.DataFrame,
    safety_weights: dict[str, float] | None = None,
    calmness_weights: dict[str, float] | None = None,
) -> pd.DataFrame:
    """Return a DataFrame with ``safety_score`` and ``calmness_score`` columns."""
    scaled = robust_scale(counts)
    sw = {**SAFETY_WEIGHTS, **(safety_weights or {})}
    cw = {**CALMNESS_WEIGHTS, **(calmness_weights or {})}
    return pd.DataFrame(
        {
            "safety_score": to_score(weighted_blend(scaled, sw)),
            "calmness_score": to_score(weighted_blend(scaled, cw)),
        },
        index=counts.index,
    )
