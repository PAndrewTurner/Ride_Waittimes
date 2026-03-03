"""Single source of truth for all parkwaits configuration."""

from __future__ import annotations

from pathlib import Path
from zoneinfo import ZoneInfo

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DATA_DIR = PROJECT_ROOT / "data"

# ---------------------------------------------------------------------------
# Timezones
# ---------------------------------------------------------------------------
ET = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")

# ---------------------------------------------------------------------------
# ThemeParks.wiki API
# ---------------------------------------------------------------------------
THEMEPARKS_API_BASE = "https://api.themeparks.wiki/v1"

PARK_ENTITIES: dict[str, dict] = {
    # Walt Disney World
    "mk": {
        "name": "Magic Kingdom",
        "resort": "wdw",
        "entity_id": "75ea578a-adc8-4116-a54d-dccb60765ef9",
        "lat": 28.4177,
        "lon": -81.5812,
        "is_water_park": False,
    },
    "epcot": {
        "name": "EPCOT",
        "resort": "wdw",
        "entity_id": "47f90d2c-e191-4239-a466-5892ef439e13",
        "lat": 28.3747,
        "lon": -81.5494,
        "is_water_park": False,
    },
    "hs": {
        "name": "Hollywood Studios",
        "resort": "wdw",
        "entity_id": "288747d1-8b4f-4a64-867e-ea7c9b27f1c3",
        "lat": 28.3575,
        "lon": -81.5583,
        "is_water_park": False,
    },
    "ak": {
        "name": "Animal Kingdom",
        "resort": "wdw",
        "entity_id": "1c84a229-8862-4648-9c71-f15c6e5c9774",
        "lat": 28.3553,
        "lon": -81.5901,
        "is_water_park": False,
    },
    # Universal Orlando
    "usf": {
        "name": "Universal Studios Florida",
        "resort": "uni",
        "entity_id": "eb3f4560-2383-4a36-9152-6b3e5ed6bc57",
        "lat": 28.4754,
        "lon": -81.4685,
        "is_water_park": False,
    },
    "ioa": {
        "name": "Islands of Adventure",
        "resort": "uni",
        "entity_id": "267615cc-8943-4c2a-ae2c-5da728ca591f",
        "lat": 28.4712,
        "lon": -81.4710,
        "is_water_park": False,
    },
    "vb": {
        "name": "Volcano Bay",
        "resort": "uni",
        "entity_id": "fe78a026-b91b-470c-b906-9d2266b692da",
        "lat": 28.4621,
        "lon": -81.4707,
        "is_water_park": True,
    },
    "eu": {
        "name": "Epic Universe",
        "resort": "uni",
        "entity_id": "",  # Discover at deploy time via `parkwaits discover`
        "lat": 28.4300,
        "lon": -81.5100,
        "is_water_park": False,
    },
}

# ---------------------------------------------------------------------------
# Convenience lookups
# ---------------------------------------------------------------------------
PARK_SLUGS: list[str] = list(PARK_ENTITIES.keys())
WDW_PARKS: set[str] = {k for k, v in PARK_ENTITIES.items() if v["resort"] == "wdw"}
UNI_PARKS: set[str] = {k for k, v in PARK_ENTITIES.items() if v["resort"] == "uni"}

# ---------------------------------------------------------------------------
# Queue-Times.com (fallback)
# ---------------------------------------------------------------------------
QUEUETIMES_API_BASE = "https://queue-times.com"
QUEUETIMES_PARK_IDS: dict[str, int] = {
    "mk": 6, "epcot": 5, "hs": 7, "ak": 8,
    "usf": 64, "ioa": 65, "vb": 69, "eu": 0,
}

# ---------------------------------------------------------------------------
# Open-Meteo Weather API
# ---------------------------------------------------------------------------
OPENMETEO_CURRENT_URL = "https://api.open-meteo.com/v1/forecast"
OPENMETEO_ARCHIVE_URL = "https://archive-api.open-meteo.com/v1/archive"
WEATHER_LAT = 28.3852
WEATHER_LON = -81.5639
WEATHER_HOURLY_VARS = [
    "temperature_2m",
    "apparent_temperature",
    "relative_humidity_2m",
    "precipitation",
    "precipitation_probability",
    "weather_code",
    "wind_speed_10m",
    "wind_gusts_10m",
    "uv_index",
]

# ---------------------------------------------------------------------------
# WMO Weather Codes
# ---------------------------------------------------------------------------
WMO_WEATHER_CODES: dict[int, str] = {
    0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
    45: "Fog", 48: "Depositing rime fog",
    51: "Light drizzle", 53: "Moderate drizzle", 55: "Dense drizzle",
    56: "Light freezing drizzle", 57: "Dense freezing drizzle",
    61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
    66: "Light freezing rain", 67: "Heavy freezing rain",
    71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow", 77: "Snow grains",
    80: "Slight rain showers", 81: "Moderate rain showers", 82: "Violent rain showers",
    85: "Slight snow showers", 86: "Heavy snow showers",
    95: "Thunderstorm", 96: "Thunderstorm w/ slight hail", 99: "Thunderstorm w/ heavy hail",
}

# ---------------------------------------------------------------------------
# Collection settings
# ---------------------------------------------------------------------------
COLLECTION_HOUR_START = 7   # 7 AM ET
COLLECTION_HOUR_END = 24    # midnight ET
HTTP_TIMEOUT_SECONDS = 30.0
HTTP_USER_AGENT = "parkwaits-collector/0.1.0 (github.com/PAndrewTurner/Ride_Waittimes)"
HTTP_MAX_RETRIES = 3
HISTORICAL_START_DATE = "2015-01-01"

# ---------------------------------------------------------------------------
# Deduplication keys per dataset
# ---------------------------------------------------------------------------
DEDUP_KEYS: dict[str, list[str]] = {
    "wait_times": ["collected_at_utc", "park_slug", "ride_slug"],
    "weather": ["date", "hour_of_day_local"],
    "park_hours": ["date", "park_slug", "collected_at_utc"],
    "demand_signals": ["date"],
    "events": ["event_name", "start_date"],
    "collection_log": [],  # Never deduplicate logs
}
