"""Tests for data collectors with mocked API responses."""

from unittest.mock import patch, MagicMock

import pandas as pd
import pytest

from parkwaits.collectors.wait_times import WaitTimeCollector, _slugify
from parkwaits.collectors.weather import WeatherCollector
from parkwaits.collectors.park_hours import ParkHoursCollector


# ---------------------------------------------------------------------------
# Mock API responses
# ---------------------------------------------------------------------------

MOCK_THEMEPARKS_LIVE = {
    "liveData": [
        {
            "name": "Space Mountain",
            "entityType": "ATTRACTION",
            "status": "OPERATING",
            "queue": {
                "STANDBY": {"waitTime": 45},
            },
        },
        {
            "name": "Rock 'n' Roller Coaster",
            "entityType": "ATTRACTION",
            "status": "DOWN",
            "queue": {},
        },
        {
            "name": "Cosmic Rewind",
            "entityType": "ATTRACTION",
            "status": "OPERATING",
            "queue": {
                "STANDBY": {"waitTime": 90},
                "PAID_RETURN_TIME": {"returnStart": "2025-06-15T16:30:00"},
            },
        },
        {
            "name": "Be Our Guest Restaurant",
            "entityType": "RESTAURANT",
            "status": "OPERATING",
            "queue": {},
        },
    ]
}

MOCK_QUEUETIMES = {
    "lands": [
        {
            "name": "Adventureland",
            "rides": [
                {"name": "Jungle Cruise", "is_open": True, "wait_time": 35},
                {"name": "Pirates of the Caribbean", "is_open": False, "wait_time": 0},
            ],
        }
    ]
}

MOCK_WEATHER = {
    "hourly": {
        "time": ["2025-06-15T14:00"],
        "temperature_2m": [92.0],
        "apparent_temperature": [105.0],
        "relative_humidity_2m": [65.0],
        "precipitation": [0.0],
        "precipitation_probability": [20.0],
        "weather_code": [95],
        "wind_speed_10m": [8.0],
        "wind_gusts_10m": [15.0],
        "uv_index": [9.0],
    },
    "daily": {
        "temperature_2m_max": [95.0],
        "temperature_2m_min": [75.0],
    },
}

MOCK_SCHEDULE = {
    "schedule": [
        {
            "date": "2025-06-15",
            "type": "OPERATING",
            "openingTime": "2025-06-15T13:00:00+00:00",
            "closingTime": "2025-06-16T01:00:00+00:00",
        },
        {
            "date": "2025-06-15",
            "type": "EARLY_ENTRY",
            "openingTime": "2025-06-15T12:30:00+00:00",
            "closingTime": "2025-06-15T13:00:00+00:00",
        },
    ]
}


# ---------------------------------------------------------------------------
# Slugify tests
# ---------------------------------------------------------------------------

def test_slugify_basic():
    assert _slugify("Space Mountain") == "space-mountain"


def test_slugify_apostrophe():
    assert _slugify("Rock 'n' Roller Coaster") == "rock-n-roller-coaster"


def test_slugify_curly_apostrophe():
    assert _slugify("it\u2019s a small world") == "its-a-small-world"


# ---------------------------------------------------------------------------
# WaitTimeCollector tests
# ---------------------------------------------------------------------------

def test_wait_time_filters_restaurants():
    """Should filter out RESTAURANT entities."""
    collector = WaitTimeCollector()
    collector.fetch_json = MagicMock(return_value=MOCK_THEMEPARKS_LIVE)

    rows = collector._collect_themeparks_wiki(
        "mk", "fake-id", "2025-06-15T10:00:00", "2025-06-15T10:00:00",
        "2025-06-15", 10,
    )
    names = [r["ride_name"] for r in rows]
    assert "Be Our Guest Restaurant" not in names
    assert "Space Mountain" in names


def test_wait_time_maps_status():
    collector = WaitTimeCollector()
    collector.fetch_json = MagicMock(return_value=MOCK_THEMEPARKS_LIVE)

    rows = collector._collect_themeparks_wiki(
        "mk", "fake-id", "2025-06-15T10:00:00", "2025-06-15T10:00:00",
        "2025-06-15", 10,
    )
    status_map = {r["ride_name"]: r["ride_status"] for r in rows}
    assert status_map["Space Mountain"] == "operating"
    assert status_map["Rock 'n' Roller Coaster"] == "down"


def test_wait_time_extracts_waits():
    collector = WaitTimeCollector()
    collector.fetch_json = MagicMock(return_value=MOCK_THEMEPARKS_LIVE)

    rows = collector._collect_themeparks_wiki(
        "mk", "fake-id", "2025-06-15T10:00:00", "2025-06-15T10:00:00",
        "2025-06-15", 10,
    )
    wait_map = {r["ride_name"]: r["wait_minutes"] for r in rows}
    assert wait_map["Space Mountain"] == 45
    assert wait_map["Rock 'n' Roller Coaster"] is None  # DOWN = null wait


def test_wait_time_detects_lightning_lane():
    collector = WaitTimeCollector()
    collector.fetch_json = MagicMock(return_value=MOCK_THEMEPARKS_LIVE)

    rows = collector._collect_themeparks_wiki(
        "mk", "fake-id", "2025-06-15T10:00:00", "2025-06-15T10:00:00",
        "2025-06-15", 10,
    )
    ll_map = {r["ride_name"]: r["ll_available"] for r in rows}
    assert ll_map["Cosmic Rewind"] is True
    assert ll_map["Space Mountain"] is False


# ---------------------------------------------------------------------------
# Queue-Times fallback tests
# ---------------------------------------------------------------------------

def test_queue_times_shapes_data():
    collector = WaitTimeCollector()
    collector.fetch_json = MagicMock(return_value=MOCK_QUEUETIMES)

    rows = collector._collect_queue_times(
        "mk", 6, "2025-06-15T10:00:00", "2025-06-15T10:00:00",
        "2025-06-15", 10,
    )
    assert len(rows) == 2
    open_ride = [r for r in rows if r["ride_name"] == "Jungle Cruise"][0]
    assert open_ride["wait_minutes"] == 35
    assert open_ride["ride_status"] == "operating"

    closed_ride = [r for r in rows if r["ride_name"] == "Pirates of the Caribbean"][0]
    assert closed_ride["wait_minutes"] is None
    assert closed_ride["ride_status"] == "closed"


# ---------------------------------------------------------------------------
# WeatherCollector tests
# ---------------------------------------------------------------------------

@patch("parkwaits.collectors.weather.datetime")
def test_weather_schema(mock_dt):
    """WeatherCollector produces correct schema."""
    from datetime import datetime, timezone
    from zoneinfo import ZoneInfo

    now = datetime(2025, 6, 15, 18, 0, 0, tzinfo=timezone.utc)
    mock_dt.now.return_value = now
    mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

    collector = WeatherCollector()
    collector.fetch_json = MagicMock(return_value=MOCK_WEATHER)

    df = collector.collect()
    assert df is not None
    assert "temp_f" in df.columns
    assert "is_heat_advisory" in df.columns
    assert "is_thunderstorm" in df.columns
    assert "weather_description" in df.columns


@patch("parkwaits.collectors.weather.datetime")
def test_weather_heat_advisory(mock_dt):
    from datetime import datetime, timezone

    now = datetime(2025, 6, 15, 18, 0, 0, tzinfo=timezone.utc)
    mock_dt.now.return_value = now
    mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

    collector = WeatherCollector()
    collector.fetch_json = MagicMock(return_value=MOCK_WEATHER)

    df = collector.collect()
    # feels_like_f = 105.0, which is >= 103
    assert df.iloc[0]["is_heat_advisory"] == True


@patch("parkwaits.collectors.weather.datetime")
def test_weather_thunderstorm(mock_dt):
    from datetime import datetime, timezone

    now = datetime(2025, 6, 15, 18, 0, 0, tzinfo=timezone.utc)
    mock_dt.now.return_value = now
    mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)

    collector = WeatherCollector()
    collector.fetch_json = MagicMock(return_value=MOCK_WEATHER)

    df = collector.collect()
    # weather_code = 95 = Thunderstorm
    assert df.iloc[0]["is_thunderstorm"] == True


# ---------------------------------------------------------------------------
# ParkHoursCollector tests
# ---------------------------------------------------------------------------

def test_park_hours_parses_schedule():
    collector = ParkHoursCollector()
    collector.fetch_json = MagicMock(return_value=MOCK_SCHEDULE)

    from datetime import datetime, timezone
    with patch("parkwaits.collectors.park_hours.datetime") as mock_dt:
        now = datetime(2025, 6, 15, 18, 0, 0, tzinfo=timezone.utc)
        mock_dt.now.return_value = now
        mock_dt.side_effect = lambda *a, **kw: datetime(*a, **kw)
        mock_dt.fromisoformat = datetime.fromisoformat

        row = collector._collect_park_schedule(
            "mk", "fake-id", "2025-06-15", "2025-06-15T18:00:00+00:00",
        )
    assert row["park_slug"] == "mk"
    assert row["open_time_local"] is not None
    assert row["emh_park"] is True
