"""Test configuration: fully offline, isolated temp data directory, res 8 only."""

from __future__ import annotations

import os
import tempfile

# Must be set before any app import so the cached Settings picks them up.
os.environ["URBIS_OFFLINE"] = "1"
os.environ["URBIS_DATA_DIR"] = tempfile.mkdtemp(prefix="urbis_test_")
os.environ["URBIS_RESOLUTIONS"] = "[8]"

import pytest
from app.core.config import get_settings
from fastapi.testclient import TestClient


@pytest.fixture(scope="session")
def settings():
    return get_settings()


@pytest.fixture(scope="session")
def pipeline_result(settings):
    from app.etl.pipeline import run_pipeline

    return run_pipeline(settings, city_ids=["ottawa", "quebec", "montreal"])


@pytest.fixture(scope="session")
def client(pipeline_result):
    from app.main import app

    with TestClient(app) as test_client:
        yield test_client
