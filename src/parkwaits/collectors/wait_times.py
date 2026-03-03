"""Wait time collector: ThemeParks.wiki (primary) + Queue-Times.com (fallback)."""

from __future__ import annotations

import logging
import re
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

from parkwaits.config import (
    ET,
    PARK_ENTITIES,
    PARK_SLUGS,
    QUEUETIMES_API_BASE,
    QUEUETIMES_PARK_IDS,
    THEMEPARKS_API_BASE,
)
from parkwaits.collectors.base import BaseCollector

logger = logging.getLogger(__name__)

# Status mapping from ThemeParks.wiki
_STATUS_MAP = {
    "OPERATING": "operating",
    "CLOSED": "closed",
    "DOWN": "down",
    "REFURBISHMENT": "refurbishment",
}


def _slugify(name: str) -> str:
    """Convert ride name to URL-safe slug.

    Strips apostrophes (all variants) before replacing non-alphanumeric chars.
    """
    # Strip apostrophes first
    slug = name.replace("'", "").replace("\u2019", "").replace("\u2018", "")
    slug = slug.lower()
    slug = re.sub(r"[^a-z0-9]+", "-", slug)
    slug = slug.strip("-")
    return slug


class WaitTimeCollector(BaseCollector):
    """Collect ride wait times from ThemeParks.wiki with Queue-Times.com fallback."""

    dataset = "wait_times"

    def collect(self) -> Optional[pd.DataFrame]:
        now_utc = datetime.now(timezone.utc)
        now_local = now_utc.astimezone(ET)
        collected_at_utc = now_utc.isoformat()
        collected_at_local = now_local.strftime("%Y-%m-%dT%H:%M:%S")
        date_str = now_local.strftime("%Y-%m-%d")
        hour_local = now_local.hour

        all_rows: list[dict] = []

        for slug in PARK_SLUGS:
            park = PARK_ENTITIES[slug]
            entity_id = park["entity_id"]

            # Try primary source
            if entity_id:
                try:
                    rows = self._collect_themeparks_wiki(
                        slug, entity_id, collected_at_utc, collected_at_local,
                        date_str, hour_local,
                    )
                    all_rows.extend(rows)
                    continue
                except Exception:
                    logger.warning(
                        "ThemeParks.wiki failed for %s, trying Queue-Times fallback",
                        slug,
                    )

            # Fallback to Queue-Times
            qt_id = QUEUETIMES_PARK_IDS.get(slug, 0)
            if qt_id:
                try:
                    rows = self._collect_queue_times(
                        slug, qt_id, collected_at_utc, collected_at_local,
                        date_str, hour_local,
                    )
                    all_rows.extend(rows)
                except Exception:
                    logger.exception("Queue-Times also failed for %s", slug)

        if not all_rows:
            return None

        df = pd.DataFrame(all_rows)
        # Apply proper dtypes
        df["park_slug"] = df["park_slug"].astype("category")
        df["ride_status"] = df["ride_status"].astype("category")
        df["wait_minutes"] = df["wait_minutes"].astype("Int16")
        df["hour_of_day_local"] = df["hour_of_day_local"].astype("int8")
        return df

    def _collect_themeparks_wiki(
        self,
        park_slug: str,
        entity_id: str,
        collected_at_utc: str,
        collected_at_local: str,
        date_str: str,
        hour_local: int,
    ) -> list[dict]:
        url = f"{THEMEPARKS_API_BASE}/entity/{entity_id}/live"
        data = self.fetch_json(url)
        rows: list[dict] = []

        for item in data.get("liveData", []):
            entity_type = item.get("entityType", "")
            if entity_type not in ("ATTRACTION", "RIDE"):
                continue

            name = item.get("name", "Unknown")
            status_raw = item.get("status", "CLOSED")
            status = _STATUS_MAP.get(status_raw, "closed")

            queue = item.get("queue", {})

            # Standby wait
            standby = queue.get("STANDBY", {})
            wait_minutes = standby.get("waitTime") if status == "operating" else None

            # Virtual queue (boarding groups)
            is_virtual_queue = "BOARDING_GROUP" in queue

            # Lightning Lane
            paid_return = queue.get("PAID_RETURN_TIME", {})
            ll_return_time = paid_return.get("returnStart")
            ll_available = "PAID_RETURN_TIME" in queue

            rows.append({
                "collected_at_utc": collected_at_utc,
                "collected_at_local": collected_at_local,
                "date": date_str,
                "hour_of_day_local": hour_local,
                "park_slug": park_slug,
                "ride_slug": _slugify(name),
                "ride_name": name,
                "wait_minutes": wait_minutes,
                "ride_status": status,
                "is_virtual_queue": is_virtual_queue,
                "ll_return_time": ll_return_time,
                "ll_available": ll_available,
                "data_source": "themeparks_wiki",
            })

        return rows

    def _collect_queue_times(
        self,
        park_slug: str,
        park_id: int,
        collected_at_utc: str,
        collected_at_local: str,
        date_str: str,
        hour_local: int,
    ) -> list[dict]:
        url = f"{QUEUETIMES_API_BASE}/parks/{park_id}/queue_times.json"
        data = self.fetch_json(url)
        rows: list[dict] = []

        for land in data.get("lands", []):
            for ride in land.get("rides", []):
                name = ride.get("name", "Unknown")
                is_open = ride.get("is_open", False)
                wait = ride.get("wait_time", 0)

                rows.append({
                    "collected_at_utc": collected_at_utc,
                    "collected_at_local": collected_at_local,
                    "date": date_str,
                    "hour_of_day_local": hour_local,
                    "park_slug": park_slug,
                    "ride_slug": _slugify(name),
                    "ride_name": name,
                    "wait_minutes": wait if is_open else None,
                    "ride_status": "operating" if is_open else "closed",
                    "is_virtual_queue": False,
                    "ll_return_time": None,
                    "ll_available": False,
                    "data_source": "queue_times",
                })

        return rows
