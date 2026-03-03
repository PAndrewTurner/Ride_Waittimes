"""Build ML feature store by joining wait_times + weather + calendar + park_hours."""

from __future__ import annotations

import logging
from pathlib import Path

import duckdb

from parkwaits.config import DATA_DIR

logger = logging.getLogger(__name__)

FEATURE_STORE_PATH = DATA_DIR / "ml" / "feature_store.parquet"

FEATURE_QUERY = """
SELECT
    -- Identifiers
    wt.park_slug,
    wt.ride_slug,
    wt.ride_name,

    -- Target
    wt.wait_minutes,

    -- Temporal features
    wt.date,
    wt.hour_of_day_local,
    cal.day_of_week,
    cal.day_of_week_name,
    cal.week_of_year,
    cal.month,
    cal.month_name,
    cal.quarter,
    cal.year,
    cal.is_weekend,
    cal.is_us_federal_holiday,
    cal.holiday_name,
    cal.is_school_break_fl,
    cal.is_school_break_northeast,
    cal.is_hurricane_season,
    cal.season,

    -- Weather features
    wx.temp_f,
    wx.feels_like_f,
    wx.humidity_pct,
    wx.precipitation_in,
    wx.precip_probability_pct,
    wx.weather_code,
    wx.wind_speed_mph,
    wx.uv_index,
    wx.is_heat_advisory,
    wx.is_thunderstorm,

    -- Park hours features
    ph.open_time_local,
    ph.close_time_local,
    ph.emh_park,
    ph.extended_hours,

    -- Ride metadata
    wt.is_virtual_queue,
    wt.ll_available,
    wt.data_source,
    wt.collected_at_utc

FROM read_parquet('{wait_times_glob}', union_by_name=true) wt
LEFT JOIN read_parquet('{calendar_path}') cal
    ON wt.date = cal.date
LEFT JOIN read_parquet('{weather_glob}', union_by_name=true) wx
    ON wt.date = wx.date AND wt.hour_of_day_local = wx.hour_of_day_local
LEFT JOIN read_parquet('{park_hours_glob}', union_by_name=true) ph
    ON wt.park_slug = ph.park_slug AND wt.date = ph.date
WHERE wt.ride_status = 'operating'
  AND wt.wait_minutes IS NOT NULL
ORDER BY wt.date, wt.hour_of_day_local, wt.park_slug, wt.ride_slug
"""


def build_feature_store() -> Path:
    """Build the ML feature store and write to Parquet."""
    wait_times_glob = str(DATA_DIR / "wait_times" / "*" / "*.parquet")
    weather_glob = str(DATA_DIR / "weather" / "*" / "*.parquet")
    park_hours_glob = str(DATA_DIR / "park_hours" / "*" / "*.parquet")
    calendar_path = str(DATA_DIR / "dimensions" / "calendar.parquet")

    query = FEATURE_QUERY.format(
        wait_times_glob=wait_times_glob,
        weather_glob=weather_glob,
        park_hours_glob=park_hours_glob,
        calendar_path=calendar_path,
    )

    FEATURE_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)

    result = duckdb.sql(query).fetchdf()
    result.to_parquet(str(FEATURE_STORE_PATH), engine="pyarrow", index=False)
    logger.info("Feature store built: %d rows -> %s", len(result), FEATURE_STORE_PATH)
    return FEATURE_STORE_PATH


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    build_feature_store()
