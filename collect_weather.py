"""
Collect current weather for the Orlando theme park area.
Saves to data/weather.csv — open it in Excel to view.

Usage:
    pip install requests pandas
    python collect_weather.py
"""

import os
from datetime import datetime, timezone, timedelta

import requests
import pandas as pd

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

WEATHER_URL = "https://api.open-meteo.com/v1/forecast"
LAT = 28.3852   # Central Orlando
LON = -81.5639

HOURLY_VARS = [
    "temperature_2m", "apparent_temperature", "relative_humidity_2m",
    "precipitation", "precipitation_probability", "weather_code",
    "wind_speed_10m", "wind_gusts_10m", "uv_index",
]

WMO_CODES = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
    95: "Thunderstorm", 96: "Thunderstorm w/ slight hail", 99: "Thunderstorm w/ heavy hail",
}

CSV_PATH = os.path.join("data", "weather.csv")


def collect():
    """Fetch current weather. Returns a DataFrame."""
    ET = timezone(timedelta(hours=-5))
    now_utc = datetime.now(timezone.utc)
    now_et = now_utc.astimezone(ET)
    current_hour = now_et.hour

    params = {
        "latitude": LAT, "longitude": LON,
        "hourly": ",".join(HOURLY_VARS),
        "daily": "temperature_2m_max,temperature_2m_min",
        "temperature_unit": "fahrenheit",
        "wind_speed_unit": "mph",
        "precipitation_unit": "inch",
        "timezone": "America/New_York",
        "forecast_days": 1,
    }

    resp = requests.get(WEATHER_URL, params=params, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    hourly = data.get("hourly", {})
    daily = data.get("daily", {})
    times = hourly.get("time", [])

    if not times:
        print("No weather data returned.")
        return None

    # Find current hour
    idx = min(current_hour, len(times) - 1)

    def get(key):
        vals = hourly.get(key, [])
        return vals[idx] if idx < len(vals) else None

    temp = get("temperature_2m")
    feels = get("apparent_temperature")
    wcode = get("weather_code")

    row = {
        "timestamp": now_utc.strftime("%Y-%m-%d %H:%M:%S"),
        "date": now_et.strftime("%Y-%m-%d"),
        "hour": current_hour,
        "temp_f": temp,
        "feels_like_f": feels,
        "humidity_pct": get("relative_humidity_2m"),
        "precipitation_in": get("precipitation"),
        "precip_probability_pct": get("precipitation_probability"),
        "weather_code": int(wcode) if wcode is not None else None,
        "weather_description": WMO_CODES.get(int(wcode), "Unknown") if wcode is not None else "Unknown",
        "wind_speed_mph": get("wind_speed_10m"),
        "wind_gust_mph": get("wind_gusts_10m"),
        "uv_index": get("uv_index"),
        "temp_high_f": daily.get("temperature_2m_max", [None])[0],
        "temp_low_f": daily.get("temperature_2m_min", [None])[0],
        "is_thunderstorm": wcode is not None and int(wcode) in (95, 96, 99),
    }

    return pd.DataFrame([row])


def save(df):
    """Append to CSV."""
    os.makedirs("data", exist_ok=True)

    if os.path.exists(CSV_PATH):
        existing = pd.read_csv(CSV_PATH)
        combined = pd.concat([existing, df], ignore_index=True)
        combined = combined.drop_duplicates(subset=["timestamp"], keep="last")
    else:
        combined = df

    combined.to_csv(CSV_PATH, index=False)
    return len(df)


def main():
    print("Collecting weather data...\n")
    df = collect()
    if df is not None:
        save(df)
        row = df.iloc[0]
        print(f"  Temperature:  {row['temp_f']}°F (feels like {row['feels_like_f']}°F)")
        print(f"  Conditions:   {row['weather_description']}")
        print(f"  Humidity:     {row['humidity_pct']}%")
        print(f"  Wind:         {row['wind_speed_mph']} mph")
        print(f"  UV Index:     {row['uv_index']}")
        print(f"  High/Low:     {row['temp_high_f']}°F / {row['temp_low_f']}°F")
        print(f"\nSaved to {CSV_PATH}")


if __name__ == "__main__":
    main()
