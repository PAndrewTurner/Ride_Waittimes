#!/usr/bin/env python3
"""Backfill historical hourly weather data from Open-Meteo archive API."""

from __future__ import annotations

import argparse
import logging
import sys
import time
from datetime import date, datetime
from pathlib import Path

import httpx
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from parkwaits.config import (
    DATA_DIR,
    HTTP_TIMEOUT_SECONDS,
    HTTP_USER_AGENT,
    OPENMETEO_ARCHIVE_URL,
    WEATHER_HOURLY_VARS,
    WEATHER_LAT,
    WEATHER_LON,
    WMO_WEATHER_CODES,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def fetch_year(client: httpx.Client, year: int) -> pd.DataFrame:
    """Fetch one year of hourly weather data."""
    start_date = f"{year}-01-01"
    # Don't request future dates
    today = date.today()
    if year == today.year:
        end_date = (today.replace(day=1) if today.day > 1 else today).isoformat()
        # Use yesterday to ensure complete data
        end_date = min(f"{year}-12-31", (today - __import__("datetime").timedelta(days=1)).isoformat())
    elif year > today.year:
        logger.warning("Skipping future year %d", year)
        return pd.DataFrame()
    else:
        end_date = f"{year}-12-31"

    params = {
        "latitude": WEATHER_LAT,
        "longitude": WEATHER_LON,
        "hourly": ",".join(WEATHER_HOURLY_VARS),
        "daily": "temperature_2m_max,temperature_2m_min",
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
        "timezone": "America/New_York",
        "start_date": start_date,
        "end_date": end_date,
    }

    resp = client.get(OPENMETEO_ARCHIVE_URL, params=params)
    resp.raise_for_status()
    data = resp.json()

    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    if not times:
        return pd.DataFrame()

    rows: list[dict] = []
    # Build daily lookup for high/low
    daily = data.get("daily", {})
    daily_dates = daily.get("time", [])
    daily_highs = daily.get("temperature_2m_max", [])
    daily_lows = daily.get("temperature_2m_min", [])
    daily_map: dict[str, tuple] = {}
    for i, d in enumerate(daily_dates):
        h = daily_highs[i] if i < len(daily_highs) else None
        lo = daily_lows[i] if i < len(daily_lows) else None
        daily_map[d] = (h, lo)

    for i, t in enumerate(times):
        # t is like "2015-01-01T00:00"
        dt_str = t[:10]
        hour = int(t[11:13])

        temp = _get(hourly, "temperature_2m", i)
        feels = _get(hourly, "apparent_temperature", i)
        humidity = _get(hourly, "relative_humidity_2m", i)
        precip = _get(hourly, "precipitation", i)
        precip_prob = _get(hourly, "precipitation_probability", i)
        wcode = _get(hourly, "weather_code", i)
        wind = _get(hourly, "wind_speed_10m", i)
        gust = _get(hourly, "wind_gusts_10m", i)
        uv = _get(hourly, "uv_index", i)

        wcode_int = int(wcode) if wcode is not None else None
        desc = WMO_WEATHER_CODES.get(wcode_int, "Unknown") if wcode_int is not None else "Unknown"
        is_heat = feels is not None and feels >= 103.0
        is_storm = wcode_int is not None and wcode_int in (95, 96, 99)

        hi, lo = daily_map.get(dt_str, (None, None))

        rows.append({
            "observed_at_local": t + ":00",
            "date": dt_str,
            "hour_of_day_local": hour,
            "temp_f": temp,
            "feels_like_f": feels,
            "humidity_pct": humidity,
            "precipitation_in": precip,
            "precip_probability_pct": precip_prob,
            "weather_code": wcode_int,
            "wind_speed_mph": wind,
            "wind_gust_mph": gust,
            "uv_index": uv,
            "weather_description": desc,
            "is_heat_advisory": is_heat,
            "is_thunderstorm": is_storm,
            "temp_high_f": hi,
            "temp_low_f": lo,
            "collected_at_utc": datetime.now(__import__("datetime").timezone.utc).isoformat(),
        })

    df = pd.DataFrame(rows)
    df["hour_of_day_local"] = df["hour_of_day_local"].astype("int8")
    return df


def _get(hourly: dict, key: str, idx: int):
    vals = hourly.get(key, [])
    return vals[idx] if idx < len(vals) else None


def save_monthly(df: pd.DataFrame, output_dir: Path) -> None:
    """Split DataFrame into monthly Parquet files."""
    if df.empty:
        return

    df["_month"] = pd.to_datetime(df["date"]).dt.to_period("M")
    for period, group in df.groupby("_month"):
        year = period.year
        month_str = str(period)
        year_dir = output_dir / str(year)
        year_dir.mkdir(parents=True, exist_ok=True)
        path = year_dir / f"{month_str}.parquet"
        group.drop(columns=["_month"]).to_parquet(path, engine="pyarrow", index=False)
        logger.info("  %s: %d rows", path.name, len(group))


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill historical weather data")
    parser.add_argument("--start-year", type=int, default=2015)
    parser.add_argument("--end-year", type=int, default=date.today().year)
    parser.add_argument("--output-dir", type=str, default=str(DATA_DIR / "weather"))
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    all_frames: list[pd.DataFrame] = []

    client = httpx.Client(
        timeout=120.0,  # Historical API can be slow
        headers={"User-Agent": HTTP_USER_AGENT},
    )

    try:
        for year in range(args.start_year, args.end_year + 1):
            logger.info("Fetching %d...", year)
            df = fetch_year(client, year)
            if df.empty:
                logger.warning("No data for %d", year)
                continue

            logger.info("  %d: %d rows", year, len(df))
            save_monthly(df, output_dir)
            all_frames.append(df)

            if year < args.end_year:
                time.sleep(1.5)
    finally:
        client.close()

    # Save combined file
    if all_frames:
        combined = pd.concat(all_frames, ignore_index=True)
        combined_path = output_dir / "all_historical.parquet"
        combined.to_parquet(combined_path, engine="pyarrow", index=False)
        logger.info("Combined: %d rows -> %s", len(combined), combined_path)


if __name__ == "__main__":
    main()
