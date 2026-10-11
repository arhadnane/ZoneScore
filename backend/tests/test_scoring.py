"""Scoring model tests."""

from __future__ import annotations

import numpy as np
import pandas as pd
from app.core.constants import FEATURES
from app.models.scoring import compute_scores, robust_scale


def _base_frame(n: int = 24) -> pd.DataFrame:
    rng = np.random.RandomState(7)
    data = {f: rng.poisson(4, n) for f in FEATURES}
    return pd.DataFrame(data, index=[f"cell_{i}" for i in range(n)])


def test_scores_bounded_0_100():
    scores = compute_scores(_base_frame())
    assert scores["safety_score"].between(0, 100).all()
    assert scores["calmness_score"].between(0, 100).all()


def test_robust_scale_finite_with_constant_column():
    df = _base_frame()
    df["police_fire"] = 2  # constant -> IQR of 0
    scaled = robust_scale(df)
    assert np.isfinite(scaled.to_numpy()).all()
    assert scaled.to_numpy().max() <= 3.0
    assert scaled.to_numpy().min() >= -3.0


def test_nightlife_degrades_safety():
    df = _base_frame()
    df["bar_nightlife"] = 1
    df.loc["cell_0", "bar_nightlife"] = 60  # extreme nightlife hotspot
    scores = compute_scores(df)
    assert scores.loc["cell_0", "safety_score"] == scores["safety_score"].min()


def test_parks_improve_calmness():
    df = _base_frame()
    df["park_green"] = 1
    baseline = compute_scores(df).loc["cell_1", "calmness_score"]
    df.loc["cell_1", "park_green"] = 60
    boosted = compute_scores(df).loc["cell_1", "calmness_score"]
    assert boosted > baseline


def test_weight_override_changes_scores():
    df = _base_frame()
    base = compute_scores(df)
    inverted = compute_scores(df, safety_weights={"bar_nightlife": 0.5, "streetlight": -0.5})
    assert not base["safety_score"].equals(inverted["safety_score"])
    # Calmness untouched by a safety-only override.
    assert base["calmness_score"].equals(inverted["calmness_score"])


def test_compute_scores_from_scaled_matches_compute_scores():
    from app.models.scoring import compute_scores_from_scaled

    df = _base_frame()
    scaled = robust_scale(df)
    scores_direct = compute_scores(df)
    scores_from_scaled = compute_scores_from_scaled(scaled)
    assert scores_direct.equals(scores_from_scaled)


def test_family_score_bounded_and_schools_improve():
    df = _base_frame()
    scores = compute_scores(df)
    assert "family_score" in scores.columns
    assert scores["family_score"].between(0, 100).all()

    df["school"] = 1
    df["park_green"] = 1
    base_fam = compute_scores(df).loc["cell_2", "family_score"]
    df.loc["cell_2", "school"] = 50
    df.loc["cell_2", "park_green"] = 50
    boosted_fam = compute_scores(df).loc["cell_2", "family_score"]
    assert boosted_fam > base_fam
