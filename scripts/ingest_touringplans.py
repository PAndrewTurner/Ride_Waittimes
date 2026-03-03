#!/usr/bin/env python3
"""Ingest TouringPlans historical WDW CSVs into project wait_times schema."""

from __future__ import annotations

import logging
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from parkwaits.config import DATA_DIR
from parkwaits.storage import append_to_monthly

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

# Ride catalog: filename patterns -> (ride_name, park_slug)
RIDE_CATALOG: dict[str, tuple[str, str]] = {
    "7_dwarfs_train": ("Seven Dwarfs Mine Train", "mk"),
    "pirates_of_caribbean": ("Pirates of the Caribbean", "mk"),
    "splash_mountain": ("Splash Mountain", "mk"),
    "flight_of_passage": ("Avatar Flight of Passage", "ak"),
    "navi_river_journey": ("Na'vi River Journey", "ak"),
    "expedition_everest": ("Expedition Everest", "ak"),
    "kilimanjaro_safaris": ("Kilimanjaro Safaris", "ak"),
    "dinosaur": ("DINOSAUR", "ak"),
    "rock_n_roller_coaster": ("Rock 'n' Roller Coaster", "hs"),
    "slinky_dog": ("Slinky Dog Dash", "hs"),
    "toy_story_mania": ("Toy Story Mania!", "hs"),
    "alien_swirling_saucers": ("Alien Swirling Saucers", "hs"),
    "soarin": ("Soarin' Around the World", "epcot"),
    "spaceship_earth": ("Spaceship Earth", "epcot"),
}


def _slugify(name: str) -> str:
    slug = name.replace("'", "").replace("\u2019", "").replace("\u2018", "")
    slug = slug.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug).strip("-")
    return slug


def _match_ride(filename: str) -> tuple[str, str] | None:
    """Match a filename to a ride catalog entry (fuzzy)."""
    fname = filename.lower().replace(" ", "_").replace("-", "_")
    fname = re.sub(r"\.csv$", "", fname)

    for key, (ride_name, park_slug) in RIDE_CATALOG.items():
        if key in fname:
            return ride_name, park_slug

    return None


def ingest_file(csv_path: Path) -> int:
    """Ingest a single CSV file. Returns row count."""
    match = _match_ride(csv_path.name)
    if not match:
        logger.warning("Could not match file: %s", csv_path.name)
        return 0

    ride_name, park_slug = match
    ride_slug = _slugify(ride_name)
    logger.info("Processing %s -> %s (%s)", csv_path.name, ride_name, park_slug)

    try:
        df = pd.read_csv(csv_path)
    except Exception:
        logger.exception("Failed to read %s", csv_path)
        return 0

    # Find timestamp column
    ts_col = None
    for col in ["datetime", "date", "timestamp", "DATETIME", "Date", "Timestamp"]:
        if col in df.columns:
            ts_col = col
            break

    if ts_col is None:
        logger.warning("No timestamp column found in %s: %s", csv_path.name, list(df.columns))
        return 0

    # Find wait time column
    wait_col = None
    for col in ["SPOSTMIN", "SACTMIN", "spostmin", "sactmin", "posted_wait", "actual_wait"]:
        if col in df.columns:
            wait_col = col
            break

    if wait_col is None:
        logger.warning("No wait time column found in %s: %s", csv_path.name, list(df.columns))
        return 0

    # Parse timestamps
    df["_ts"] = pd.to_datetime(df[ts_col], errors="coerce")
    df = df.dropna(subset=["_ts"])

    # Filter dates
    df = df[df["_ts"] >= "2015-01-01"]

    # Clean wait times
    df["_wait"] = pd.to_numeric(df[wait_col], errors="coerce")
    df = df.dropna(subset=["_wait"])
    df = df[(df["_wait"] >= 0) & (df["_wait"] <= 600)]

    if df.empty:
        return 0

    # Build output
    collected_at_utc = datetime.now(timezone.utc).isoformat()
    rows: list[dict] = []
    for _, row in df.iterrows():
        ts = row["_ts"]
        rows.append({
            "collected_at_utc": ts.isoformat() if pd.notna(ts) else collected_at_utc,
            "collected_at_local": ts.strftime("%Y-%m-%dT%H:%M:%S") if pd.notna(ts) else "",
            "date": ts.strftime("%Y-%m-%d"),
            "hour_of_day_local": ts.hour,
            "park_slug": park_slug,
            "ride_slug": ride_slug,
            "ride_name": ride_name,
            "wait_minutes": int(row["_wait"]),
            "ride_status": "operating",
            "is_virtual_queue": False,
            "ll_return_time": None,
            "ll_available": False,
            "data_source": "touringplans_csv",
        })

    out_df = pd.DataFrame(rows)
    out_df["park_slug"] = out_df["park_slug"].astype("category")
    out_df["ride_status"] = out_df["ride_status"].astype("category")
    out_df["wait_minutes"] = out_df["wait_minutes"].astype("Int16")
    out_df["hour_of_day_local"] = out_df["hour_of_day_local"].astype("int8")

    # Save monthly
    for date_str, group in out_df.groupby("date"):
        append_to_monthly(group.copy(), "wait_times")

    return len(out_df)


def main() -> None:
    raw_dir = DATA_DIR / "raw" / "touringplans"
    if not raw_dir.exists():
        logger.error("Directory not found: %s", raw_dir)
        logger.info("Place TouringPlans CSV files in %s", raw_dir)
        sys.exit(1)

    csv_files = sorted(raw_dir.glob("*.csv"))
    if not csv_files:
        logger.error("No CSV files found in %s", raw_dir)
        sys.exit(1)

    total = 0
    for csv_path in csv_files:
        count = ingest_file(csv_path)
        total += count

    logger.info("Total ingested: %d rows from %d files", total, len(csv_files))


if __name__ == "__main__":
    main()
