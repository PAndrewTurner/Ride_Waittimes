"""Tests for parkwaits storage layer."""

from datetime import datetime, timezone
from unittest.mock import patch

import pandas as pd
import pytest

from parkwaits.storage import (
    append_to_monthly,
    log_collection_run,
    read_dimension,
    save_dimension,
)


@pytest.fixture
def mock_data_dir(tmp_path):
    """Patch DATA_DIR to use a temp directory."""
    with patch("parkwaits.storage.DATA_DIR", tmp_path):
        yield tmp_path


def test_append_creates_file(mock_data_dir):
    df = pd.DataFrame({
        "date": ["2025-06-15"],
        "park_slug": ["mk"],
        "ride_slug": ["space-mountain"],
        "wait_minutes": pd.array([45], dtype="Int16"),
    })
    path = append_to_monthly(df, "wait_times")
    assert path is not None
    assert path.exists()
    result = pd.read_parquet(path)
    assert len(result) == 1


def test_append_deduplicates(mock_data_dir):
    # Write 2 rows
    df1 = pd.DataFrame({
        "collected_at_utc": ["2025-06-15T10:00:00", "2025-06-15T10:00:00"],
        "date": ["2025-06-15", "2025-06-15"],
        "park_slug": ["mk", "mk"],
        "ride_slug": ["space-mountain", "pirates-of-the-caribbean"],
        "wait_minutes": pd.array([45, 30], dtype="Int16"),
    })
    append_to_monthly(df1, "wait_times")

    # Write 1 row with same key but updated value
    df2 = pd.DataFrame({
        "collected_at_utc": ["2025-06-15T10:00:00"],
        "date": ["2025-06-15"],
        "park_slug": ["mk"],
        "ride_slug": ["space-mountain"],
        "wait_minutes": pd.array([60], dtype="Int16"),
    })
    path = append_to_monthly(df2, "wait_times")

    result = pd.read_parquet(path)
    assert len(result) == 2  # Still 2 rows after dedup
    # The updated value should be kept (keep="last")
    space = result[result["ride_slug"] == "space-mountain"]
    assert space.iloc[0]["wait_minutes"] == 60


def test_append_empty_returns_none(mock_data_dir):
    df = pd.DataFrame()
    result = append_to_monthly(df, "wait_times")
    assert result is None


def test_append_none_returns_none(mock_data_dir):
    result = append_to_monthly(None, "wait_times")
    assert result is None


def test_dimension_round_trip(mock_data_dir):
    df = pd.DataFrame({
        "park_slug": ["mk", "epcot"],
        "park_name": ["Magic Kingdom", "EPCOT"],
    })
    save_dimension(df, "parks")
    result = read_dimension("parks")
    assert len(result) == 2
    assert "park_name" in result.columns


def test_missing_dimension_returns_empty(mock_data_dir):
    result = read_dimension("nonexistent")
    assert isinstance(result, pd.DataFrame)
    assert result.empty


def test_log_collection_run(mock_data_dir):
    started = datetime.now(timezone.utc)
    path = log_collection_run(
        collector_name="TestCollector",
        status="success",
        records=42,
        started=started,
    )
    assert path is not None
    result = pd.read_parquet(path)
    assert len(result) == 1
    assert result.iloc[0]["collector"] == "TestCollector"
    assert result.iloc[0]["status"] == "success"
    assert result.iloc[0]["records"] == 42
