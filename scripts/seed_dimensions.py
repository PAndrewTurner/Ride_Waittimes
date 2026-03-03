#!/usr/bin/env python3
"""Seed dimension tables: parks, rides, calendar."""

from __future__ import annotations

import logging
import sys
import time
from datetime import date, timedelta

import httpx
import pandas as pd
from astral import LocationInfo
from astral.sun import sun
from zoneinfo import ZoneInfo

# Add src to path
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent / "src"))

from parkwaits.config import (
    ET,
    HTTP_TIMEOUT_SECONDS,
    HTTP_USER_AGENT,
    PARK_ENTITIES,
    THEMEPARKS_API_BASE,
)
from parkwaits.storage import save_dimension

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def seed_parks() -> pd.DataFrame:
    """Build parks dimension from config."""
    rows = []
    for slug, info in PARK_ENTITIES.items():
        rows.append({
            "park_slug": slug,
            "park_name": info["name"],
            "resort": info["resort"],
            "entity_id": info["entity_id"],
            "lat": info["lat"],
            "lon": info["lon"],
            "is_water_park": info["is_water_park"],
        })
    df = pd.DataFrame(rows)
    save_dimension(df, "parks")
    logger.info("Parks dimension: %d rows", len(df))
    return df


def seed_rides() -> pd.DataFrame:
    """Fetch ride data from ThemeParks.wiki children endpoint."""
    client = httpx.Client(
        timeout=HTTP_TIMEOUT_SECONDS,
        headers={"User-Agent": HTTP_USER_AGENT},
    )

    all_rides: list[dict] = []
    ride_id = 1

    try:
        for slug, info in PARK_ENTITIES.items():
            entity_id = info["entity_id"]
            if not entity_id:
                logger.warning("Skipping %s — no entity_id", slug)
                continue

            url = f"{THEMEPARKS_API_BASE}/entity/{entity_id}/children"
            try:
                resp = client.get(url)
                resp.raise_for_status()
                data = resp.json()
            except Exception:
                logger.exception("Failed to fetch children for %s", slug)
                continue

            children = data.get("children", [])
            for child in children:
                etype = child.get("entityType", "")
                if etype not in ("ATTRACTION", "RIDE"):
                    continue

                name = child.get("name", "Unknown")
                # Slugify
                ride_slug = name.replace("'", "").replace("\u2019", "").replace("\u2018", "")
                ride_slug = ride_slug.lower()
                import re
                ride_slug = re.sub(r"[^a-z0-9]+", "-", ride_slug).strip("-")

                all_rides.append({
                    "ride_id": ride_id,
                    "park_slug": slug,
                    "ride_name": name,
                    "ride_slug": ride_slug,
                    "external_id": child.get("id", ""),
                    "entity_type": etype,
                    "ride_type": None,
                    "is_indoor": None,
                    "height_requirement_in": None,
                    "has_single_rider": None,
                    "theoretical_hourly_capacity": None,
                    "ride_duration_seconds": None,
                    "ip_franchise": None,
                    "themed_land": None,
                    "year_opened": None,
                    "last_refurb_year": None,
                    "is_active": True,
                    "ll_tier": None,
                    "express_available": None,
                })
                ride_id += 1

            logger.info("%s: found %d attractions", slug, sum(1 for r in all_rides if r["park_slug"] == slug))
            time.sleep(0.5)
    finally:
        client.close()

    df = pd.DataFrame(all_rides)
    save_dimension(df, "rides")
    logger.info("Rides dimension: %d rows", len(df))
    return df


def seed_calendar() -> pd.DataFrame:
    """Generate calendar dimension from 2015-01-01 to 2030-12-31."""
    import holidays as hol

    us_holidays = hol.UnitedStates(years=range(2015, 2031))

    orlando = LocationInfo("Orlando", "USA", "America/New_York", 28.3852, -81.5639)
    tz = ZoneInfo("America/New_York")

    start = date(2015, 1, 1)
    end = date(2030, 12, 31)
    current = start

    rows: list[dict] = []
    while current <= end:
        dow = current.weekday()  # 0=Monday
        month = current.month

        # Season
        if month in (3, 4, 5):
            season = "spring"
        elif month in (6, 7, 8):
            season = "summer"
        elif month in (9, 10, 11):
            season = "fall"
        else:
            season = "winter"

        # Holiday
        is_holiday = current in us_holidays
        holiday_name = us_holidays.get(current)

        # School breaks (Florida approximation)
        md = (month, current.day)
        is_school_break_fl = (
            (month == 12 and current.day >= 20)
            or (month == 1 and current.day <= 3)
            or (month == 3 and 10 <= current.day <= 20)
            or (month in (6, 7))
            or (month == 8 and current.day <= 10)
            or (month == 11 and current.day >= 22)
        )

        # Northeast school breaks
        is_school_break_ne = (
            (month == 12 and current.day >= 23)
            or (month == 1 and current.day <= 2)
            or (month == 2 and 15 <= current.day <= 23)
            or (month == 4 and 5 <= current.day <= 20)
            or (month in (7, 8))
            or (month == 6 and current.day >= 20)
            or (month == 11 and current.day >= 22)
        )

        # Sunrise/sunset
        try:
            s = sun(orlando.observer, date=current, tzinfo=tz)
            sunrise = s["sunrise"].strftime("%H:%M")
            sunset = s["sunset"].strftime("%H:%M")
        except Exception:
            sunrise = None
            sunset = None

        rows.append({
            "date": current.isoformat(),
            "day_of_week": dow,
            "day_of_week_name": current.strftime("%A"),
            "day_of_month": current.day,
            "week_of_year": current.isocalendar()[1],
            "month": month,
            "month_name": current.strftime("%B"),
            "quarter": (month - 1) // 3 + 1,
            "year": current.year,
            "is_weekend": dow >= 5,
            "is_us_federal_holiday": is_holiday,
            "holiday_name": holiday_name,
            "is_school_break_fl": is_school_break_fl,
            "is_school_break_northeast": is_school_break_ne,
            "is_hurricane_season": month in (6, 7, 8, 9, 10, 11),
            "season": season,
            "sunrise_time_et": sunrise,
            "sunset_time_et": sunset,
        })

        current += timedelta(days=1)

    df = pd.DataFrame(rows)
    df["day_of_week"] = df["day_of_week"].astype("int8")
    df["month"] = df["month"].astype("int8")
    df["year"] = df["year"].astype("int16")
    save_dimension(df, "calendar")
    logger.info("Calendar dimension: %d rows", len(df))
    return df


if __name__ == "__main__":
    logger.info("Seeding parks dimension...")
    seed_parks()

    logger.info("Seeding rides dimension...")
    seed_rides()

    logger.info("Seeding calendar dimension...")
    seed_calendar()

    logger.info("Done!")
