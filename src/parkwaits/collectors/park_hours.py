"""Park hours collector using ThemeParks.wiki schedule API."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Optional

import pandas as pd

from parkwaits.config import ET, PARK_ENTITIES, PARK_SLUGS, THEMEPARKS_API_BASE
from parkwaits.collectors.base import BaseCollector

logger = logging.getLogger(__name__)

# Schedule types that indicate early/extra magic hours
_EARLY_ENTRY_TYPES = {"EARLY_ENTRY", "EXTRA_HOURS", "EARLY_MAGIC"}
_AFTER_HOURS_TYPES = {"AFTER_HOURS", "SPECIAL_EVENT", "TICKETED_EVENT"}


def _iso_to_local_hhmm(iso_str: str) -> Optional[str]:
    """Convert ISO 8601 timestamp to HH:MM in Eastern Time."""
    try:
        dt = datetime.fromisoformat(iso_str)
        local = dt.astimezone(ET)
        return local.strftime("%H:%M")
    except (ValueError, TypeError):
        return None


class ParkHoursCollector(BaseCollector):
    """Collect park operating hours from ThemeParks.wiki schedule endpoint."""

    dataset = "park_hours"

    def collect(self) -> Optional[pd.DataFrame]:
        now_utc = datetime.now(timezone.utc)
        now_local = now_utc.astimezone(ET)
        today_str = now_local.strftime("%Y-%m-%d")
        collected_at_utc = now_utc.isoformat()

        all_rows: list[dict] = []

        for slug in PARK_SLUGS:
            park = PARK_ENTITIES[slug]
            entity_id = park["entity_id"]
            if not entity_id:
                continue

            try:
                row = self._collect_park_schedule(
                    slug, entity_id, today_str, collected_at_utc,
                )
                all_rows.append(row)
            except Exception:
                logger.exception("Failed to get schedule for %s", slug)

        if not all_rows:
            return None

        df = pd.DataFrame(all_rows)
        df["park_slug"] = df["park_slug"].astype("category")
        return df

    def _collect_park_schedule(
        self,
        park_slug: str,
        entity_id: str,
        today_str: str,
        collected_at_utc: str,
    ) -> dict:
        url = f"{THEMEPARKS_API_BASE}/entity/{entity_id}/schedule"
        data = self.fetch_json(url)

        schedule_items = data.get("schedule", [])

        open_time = None
        close_time = None
        emh_open = None
        emh_park = False
        extended_hours = False
        after_hours_event = None
        after_hours_start = None

        for item in schedule_items:
            item_date = item.get("date", "")
            if item_date != today_str:
                continue

            stype = item.get("type", "")
            opening = item.get("openingTime")
            closing = item.get("closingTime")

            if stype == "OPERATING":
                open_time = _iso_to_local_hhmm(opening) if opening else None
                close_time = _iso_to_local_hhmm(closing) if closing else None

            elif stype in _EARLY_ENTRY_TYPES:
                emh_open = _iso_to_local_hhmm(opening) if opening else None
                emh_park = True
                extended_hours = True

            elif stype in _AFTER_HOURS_TYPES:
                after_hours_event = stype
                after_hours_start = _iso_to_local_hhmm(opening) if opening else None
                extended_hours = True

        return {
            "date": today_str,
            "park_slug": park_slug,
            "open_time_local": open_time,
            "close_time_local": close_time,
            "emh_open_time": emh_open,
            "emh_park": emh_park,
            "extended_hours": extended_hours,
            "after_hours_event": after_hours_event,
            "after_hours_start": after_hours_start,
            "collected_at_utc": collected_at_utc,
            "is_hours_update": True,
        }
