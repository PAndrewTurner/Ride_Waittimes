"""
Collect current ride wait times from Walt Disney World + Universal Orlando.
Saves to data/wait_times.csv — open it in Excel to view.

Usage:
    pip install requests pandas
    python collect_wait_times.py
"""

import os
import re
import time
from datetime import datetime, timezone, timedelta

import requests
import pandas as pd

# ---------------------------------------------------------------------------
# Configuration — all parks and API URLs
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
    "eu":    {"name": "Epic Universe",             "entity_id": ""},  # Update after running discover
}

# Queue-Times.com fallback
QUEUETIMES_BASE = "https://queue-times.com"
QUEUETIMES_IDS = {"mk": 6, "epcot": 5, "hs": 7, "ak": 8, "usf": 64, "ioa": 65, "vb": 69, "eu": 0}

STATUS_MAP = {
    "OPERATING": "operating",
    "CLOSED": "closed",
    "DOWN": "down",
    "REFURBISHMENT": "refurbishment",
}

CSV_PATH = os.path.join("data", "wait_times.csv")


def slugify(name):
    """Convert ride name to a clean slug."""
    s = name.replace("'", "").replace("\u2019", "").replace("\u2018", "")
    s = s.lower()
    s = re.sub(r"[^a-z0-9]+", "-", s).strip("-")
    return s


def fetch_themeparks_wiki(park_slug, entity_id):
    """Fetch live wait times from ThemeParks.wiki."""
    url = f"{API_BASE}/entity/{entity_id}/live"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    rows = []
    for item in data.get("liveData", []):
        if item.get("entityType") not in ("ATTRACTION", "RIDE"):
            continue

        name = item.get("name", "Unknown")
        status = STATUS_MAP.get(item.get("status", "CLOSED"), "closed")
        queue = item.get("queue", {})
        wait = queue.get("STANDBY", {}).get("waitTime") if status == "operating" else None

        rows.append({
            "park": park_slug,
            "ride": name,
            "ride_slug": slugify(name),
            "wait_minutes": wait,
            "status": status,
            "has_lightning_lane": "PAID_RETURN_TIME" in queue,
            "source": "themeparks_wiki",
        })
    return rows


def fetch_queue_times(park_slug, park_id):
    """Fallback: fetch from Queue-Times.com."""
    url = f"{QUEUETIMES_BASE}/parks/{park_id}/queue_times.json"
    resp = requests.get(url, timeout=30)
    resp.raise_for_status()
    data = resp.json()

    rows = []
    for land in data.get("lands", []):
        for ride in land.get("rides", []):
            name = ride.get("name", "Unknown")
            is_open = ride.get("is_open", False)
            rows.append({
                "park": park_slug,
                "ride": name,
                "ride_slug": slugify(name),
                "wait_minutes": ride.get("wait_time") if is_open else None,
                "status": "operating" if is_open else "closed",
                "has_lightning_lane": False,
                "source": "queue_times",
            })
    return rows


def collect():
    """Collect wait times for all parks. Returns a DataFrame."""
    ET = timezone(timedelta(hours=-5))  # Approximate Eastern
    now_utc = datetime.now(timezone.utc)
    now_et = now_utc.astimezone(ET)

    all_rows = []

    for slug, info in PARKS.items():
        entity_id = info["entity_id"]
        park_name = info["name"]

        # Try primary source
        if entity_id:
            try:
                rows = fetch_themeparks_wiki(slug, entity_id)
                all_rows.extend(rows)
                print(f"  {park_name}: {len(rows)} rides")
                continue
            except Exception as e:
                print(f"  {park_name}: ThemeParks.wiki failed ({e}), trying fallback...")

        # Fallback
        qt_id = QUEUETIMES_IDS.get(slug, 0)
        if qt_id:
            try:
                rows = fetch_queue_times(slug, qt_id)
                all_rows.extend(rows)
                print(f"  {park_name}: {len(rows)} rides (via Queue-Times)")
            except Exception as e:
                print(f"  {park_name}: FAILED - {e}")
        else:
            print(f"  {park_name}: skipped (no entity_id)")

        time.sleep(0.3)  # Be nice to APIs

    if not all_rows:
        print("\nNo data collected.")
        return None

    df = pd.DataFrame(all_rows)
    df.insert(0, "timestamp", now_utc.strftime("%Y-%m-%d %H:%M:%S"))
    df.insert(1, "date", now_et.strftime("%Y-%m-%d"))
    df.insert(2, "hour", now_et.hour)
    return df


def save(df):
    """Append to CSV, avoiding exact duplicate rows."""
    os.makedirs("data", exist_ok=True)

    if os.path.exists(CSV_PATH):
        existing = pd.read_csv(CSV_PATH)
        combined = pd.concat([existing, df], ignore_index=True)
        combined = combined.drop_duplicates(subset=["timestamp", "park", "ride_slug"], keep="last")
    else:
        combined = df

    combined.to_csv(CSV_PATH, index=False)
    return len(df)


def main():
    print("Collecting ride wait times...\n")
    df = collect()
    if df is not None:
        count = save(df)
        print(f"\nSaved {count} rows to {CSV_PATH}")

        # Print summary
        operating = df[df["status"] == "operating"]
        if not operating.empty:
            print(f"\nTop wait times right now:")
            top = operating.nlargest(10, "wait_minutes")[["park", "ride", "wait_minutes", "status"]]
            print(top.to_string(index=False))
        else:
            print("\nAll rides currently closed (parks may not be open).")


if __name__ == "__main__":
    main()
