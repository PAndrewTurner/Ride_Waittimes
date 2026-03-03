"""Weather collector using Open-Meteo forecast API."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

from parkwaits.config import (
    ET,
    OPENMETEO_CURRENT_URL,
    WEATHER_HOURLY_VARS,
    WEATHER_LAT,
    WEATHER_LON,
    WMO_WEATHER_CODES,
)
from parkwaits.collectors.base import BaseCollector

logger = logging.getLogger(__name__)


class WeatherCollector(BaseCollector):
    """Collect current weather conditions from Open-Meteo."""

    dataset = "weather"

    def collect(self) -> Optional[pd.DataFrame]:
        now_utc = datetime.now(timezone.utc)
        now_local = now_utc.astimezone(ET)
        current_hour = now_local.hour

        params = {
            "latitude": WEATHER_LAT,
            "longitude": WEATHER_LON,
            "hourly": ",".join(WEATHER_HOURLY_VARS),
            "daily": "temperature_2m_max,temperature_2m_min",
            "temperature_unit": "fahrenheit",
            "wind_speed_unit": "mph",
            "precipitation_unit": "inch",
            "timezone": "America/New_York",
            "forecast_days": 1,
        }

        data = self.fetch_json(OPENMETEO_CURRENT_URL, params=params)

        hourly = data.get("hourly", {})
        daily = data.get("daily", {})

        times = hourly.get("time", [])
        if not times:
            logger.warning("No hourly weather data returned")
            return None

        # Find the current hour's index, or take the last available
        hour_idx = None
        for i, t in enumerate(times):
            # Format: "2025-06-15T14:00"
            if len(t) >= 13:
                h = int(t[11:13])
                if h == current_hour:
                    hour_idx = i
                    break

        if hour_idx is None:
            hour_idx = len(times) - 1

        # Extract values at the target hour
        temp_f = _safe_get(hourly, "temperature_2m", hour_idx)
        feels_like_f = _safe_get(hourly, "apparent_temperature", hour_idx)
        humidity = _safe_get(hourly, "relative_humidity_2m", hour_idx)
        precip = _safe_get(hourly, "precipitation", hour_idx)
        precip_prob = _safe_get(hourly, "precipitation_probability", hour_idx)
        weather_code = _safe_get(hourly, "weather_code", hour_idx)
        wind_speed = _safe_get(hourly, "wind_speed_10m", hour_idx)
        wind_gust = _safe_get(hourly, "wind_gusts_10m", hour_idx)
        uv = _safe_get(hourly, "uv_index", hour_idx)

        # Daily high/low
        temp_high = daily.get("temperature_2m_max", [None])[0]
        temp_low = daily.get("temperature_2m_min", [None])[0]

        # Derived fields
        weather_desc = WMO_WEATHER_CODES.get(
            int(weather_code) if weather_code is not None else -1,
            "Unknown",
        )
        is_heat = feels_like_f is not None and feels_like_f >= 103.0
        is_storm = weather_code is not None and int(weather_code) in (95, 96, 99)

        row = {
            "observed_at_local": now_local.strftime("%Y-%m-%dT%H:%M:%S"),
            "date": now_local.strftime("%Y-%m-%d"),
            "hour_of_day_local": current_hour,
            "temp_f": temp_f,
            "feels_like_f": feels_like_f,
            "humidity_pct": humidity,
            "precipitation_in": precip,
            "precip_probability_pct": precip_prob,
            "weather_code": int(weather_code) if weather_code is not None else None,
            "wind_speed_mph": wind_speed,
            "wind_gust_mph": wind_gust,
            "uv_index": uv,
            "weather_description": weather_desc,
            "is_heat_advisory": is_heat,
            "is_thunderstorm": is_storm,
            "temp_high_f": temp_high,
            "temp_low_f": temp_low,
            "collected_at_utc": now_utc.isoformat(),
        }

        df = pd.DataFrame([row])
        df["hour_of_day_local"] = df["hour_of_day_local"].astype("int8")
        return df


def _safe_get(hourly: dict, key: str, idx: int) -> Optional[float]:
    """Safely get a value from hourly data arrays."""
    values = hourly.get(key, [])
    if idx < len(values):
        return values[idx]
    return None
