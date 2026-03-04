"""
Collect today's park operating hours for WDW + Universal Orlando.
Saves to data/park_hours.csv — open it in Excel to view.

Usage:
    pip install requests pandas
    python collect_park_hours.py
"""

import os
import time
from datetime import datetime, timezone, timedelta

import requests
import pandas as pd

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

API_BASE = "https://api.themeparks.wiki/v1"

PARKS = {
    "mk":    {"name": "Magic Kingdom",            "entity_id": "75ea578a-adc8-4116-a54d-dccb60765ef9"},
    "epcot": {"name": "EPCOT",                    "entity_id": "47f90d2c-e191-4239-a466-5892ef439e13"},
    "hs":    {"name": "Hollywood Studios",         "entity_id": "288747d1-8b4f-4a64-867e-ea7c9b27f1c3"},
    "ak":    {"name": "Animal Kingdom",            "entity_id": "1c84a229-8862-4648-9c71-f15c6e5c9774"},
    "usf":   {"name": "Universal Studios Florida", "entity_id": "eb3f4560-2383-4a36-9152-6b3e5ed6bc57"},
    "ioa":   {"name": "Islands of Adventure",      "entity_id": "267615cc-8943-4c2a-ae2c-5da728ca591f"},
    "vb":    {"name": "Volcano Bay",               "entity_id": "fe78a026-b91b-470c-b906-9d2266b692da"},
    "eu":    {"name": "Epic Universe",             "entity_id": ""},  # Update after discover
}

EARLY_ENTRY_TYPES = {"EARLY_ENTRY", "EXTRA_HOURS", "EARLY_MAGIC"}
AFTER_HOURS_TYPES = {"AFTER_HOURS", "SPECIAL_EVENT", "TICKETED_EVENT"}

CSV_PATH = os.path.join("data", "park_hours.csv")


def to_local_time(iso_str):
    """Convert ISO timestamp to HH:MM Eastern."""
    try:
        ET = timezone(timedelta(hours=-5))
        dt = datetime.fromisoformat(iso_str).astimezone(ET)
        return dt.strftime("%H:%M")
    except (ValueError, TypeError):
        return None


def collect():
    """Fetch today's park hours. Returns a DataFrame."""
    ET = timezone(timedelta(hours=-5))
    now_utc = datetime.now(timezone.utc)
    now_et = now_utc.astimezone(ET)
    today = now_et.strftime("%Y-%m-%d")

    rows = []

    for slug, info in PARKS.items():
        entity_id = info["entity_id"]
        if not entity_id:
            print(f"  {info['name']}: skipped (no entity_id)")
            continue

        try:
            url = f"{API_BASE}/entity/{entity_id}/schedule"
            resp = requests.get(url, timeout=30)
            resp.raise_for_status()
            data = resp.json()

            open_time = close_time = early_entry = None
            has_early_entry = False

            for item in data.get("schedule", []):
                if item.get("date") != today:
                    continue

                stype = item.get("type", "")
                if stype == "OPERATING":
                    open_time = to_local_time(item.get("openingTime", ""))
                    close_time = to_local_time(item.get("closingTime", ""))
                elif stype in EARLY_ENTRY_TYPES:
                    early_entry = to_local_time(item.get("openingTime", ""))
                    has_early_entry = True

            rows.append({
                "park": slug,
                "park_name": info["name"],
                "date": today,
                "open_time": open_time,
                "close_time": close_time,
                "early_entry_time": early_entry,
                "has_early_entry": has_early_entry,
            })
            hours_str = f"{open_time or '?'} - {close_time or '?'}"
            ee_str = f" (Early Entry: {early_entry})" if has_early_entry else ""
            print(f"  {info['name']}: {hours_str}{ee_str}")

        except Exception as e:
            print(f"  {info['name']}: FAILED - {e}")

        time.sleep(0.3)

    if not rows:
        return None

    df = pd.DataFrame(rows)
    df.insert(0, "timestamp", now_utc.strftime("%Y-%m-%d %H:%M:%S"))
    return df


def save(df):
    """Append to CSV."""
    os.makedirs("data", exist_ok=True)

    if os.path.exists(CSV_PATH):
        existing = pd.read_csv(CSV_PATH)
        combined = pd.concat([existing, df], ignore_index=True)
        combined = combined.drop_duplicates(subset=["timestamp", "park"], keep="last")
    else:
        combined = df

    combined.to_csv(CSV_PATH, index=False)
    return len(df)


def main():
    print("Collecting park hours...\n")
    df = collect()
    if df is not None:
        save(df)
        print(f"\nSaved to {CSV_PATH}")


if __name__ == "__main__":
    main()
