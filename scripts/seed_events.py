#!/usr/bin/env python3
"""Seed historical events catalog 2015-2026."""

from __future__ import annotations

import logging
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from parkwaits.config import DATA_DIR
from parkwaits.storage import append_to_monthly, save_dimension

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def _generate_recurring_events() -> list[dict]:
    """Generate recurring annual events for 2015-2026."""
    events: list[dict] = []
    eid = 1

    for year in range(2015, 2027):
        # --- runDisney ---
        events.append({
            "event_id": eid, "event_name": f"WDW Marathon Weekend {year}",
            "event_category": "rundisney", "resort": "wdw",
            "start_date": f"{year}-01-06", "end_date": f"{year}-01-12",
            "affected_parks": "mk,epcot,ak,hs",
            "estimated_crowd_impact": "medium", "notes": "Marathon weekend",
        })
        eid += 1

        events.append({
            "event_id": eid, "event_name": f"Princess Half Marathon {year}",
            "event_category": "rundisney", "resort": "wdw",
            "start_date": f"{year}-02-19", "end_date": f"{year}-02-23",
            "affected_parks": "mk,epcot",
            "estimated_crowd_impact": "medium", "notes": "Princess Half",
        })
        eid += 1

        events.append({
            "event_id": eid, "event_name": f"Wine & Dine Half Marathon {year}",
            "event_category": "rundisney", "resort": "wdw",
            "start_date": f"{year}-11-01", "end_date": f"{year}-11-05",
            "affected_parks": "epcot",
            "estimated_crowd_impact": "medium", "notes": "Wine & Dine race weekend",
        })
        eid += 1

        # --- EPCOT Festivals ---
        events.append({
            "event_id": eid, "event_name": f"EPCOT Flower & Garden {year}",
            "event_category": "epcot_festival", "resort": "wdw",
            "start_date": f"{year}-03-01", "end_date": f"{year}-07-05",
            "affected_parks": "epcot",
            "estimated_crowd_impact": "medium", "notes": "",
        })
        eid += 1

        # Food & Wine: pre-2022 started late Sep, from 2022 started late Jul
        if year < 2022:
            fw_start = f"{year}-09-20"
        else:
            fw_start = f"{year}-07-27"
        events.append({
            "event_id": eid, "event_name": f"EPCOT Food & Wine {year}",
            "event_category": "epcot_festival", "resort": "wdw",
            "start_date": fw_start, "end_date": f"{year}-11-22",
            "affected_parks": "epcot",
            "estimated_crowd_impact": "high", "notes": "",
        })
        eid += 1

        events.append({
            "event_id": eid, "event_name": f"EPCOT Festival of the Holidays {year}",
            "event_category": "epcot_festival", "resort": "wdw",
            "start_date": f"{year}-11-24", "end_date": f"{year}-12-30",
            "affected_parks": "epcot",
            "estimated_crowd_impact": "high", "notes": "",
        })
        eid += 1

        # Festival of the Arts started 2017
        if year >= 2017:
            events.append({
                "event_id": eid, "event_name": f"EPCOT Festival of the Arts {year}",
                "event_category": "epcot_festival", "resort": "wdw",
                "start_date": f"{year}-01-13", "end_date": f"{year}-02-24",
                "affected_parks": "epcot",
                "estimated_crowd_impact": "medium", "notes": "",
            })
            eid += 1

        # --- Hard Ticket Events ---
        events.append({
            "event_id": eid,
            "event_name": f"Mickey's Not-So-Scary Halloween Party {year}",
            "event_category": "hard_ticket", "resort": "wdw",
            "start_date": f"{year}-08-12", "end_date": f"{year}-10-31",
            "affected_parks": "mk",
            "estimated_crowd_impact": "high", "notes": "Select nights",
        })
        eid += 1

        events.append({
            "event_id": eid,
            "event_name": f"Mickey's Very Merry Christmas Party {year}",
            "event_category": "hard_ticket", "resort": "wdw",
            "start_date": f"{year}-11-08", "end_date": f"{year}-12-22",
            "affected_parks": "mk",
            "estimated_crowd_impact": "high", "notes": "Select nights",
        })
        eid += 1

        # --- Universal Events ---
        events.append({
            "event_id": eid, "event_name": f"Universal Mardi Gras {year}",
            "event_category": "universal_event", "resort": "uni",
            "start_date": f"{year}-02-01", "end_date": f"{year}-04-20",
            "affected_parks": "usf",
            "estimated_crowd_impact": "medium", "notes": "",
        })
        eid += 1

        events.append({
            "event_id": eid, "event_name": f"Halloween Horror Nights {year}",
            "event_category": "universal_event", "resort": "uni",
            "start_date": f"{year}-09-05", "end_date": f"{year}-11-02",
            "affected_parks": "usf",
            "estimated_crowd_impact": "extreme", "notes": "Select nights",
        })
        eid += 1

        events.append({
            "event_id": eid, "event_name": f"Universal Holidays {year}",
            "event_category": "universal_event", "resort": "uni",
            "start_date": f"{year}-11-15", "end_date": f"{year+1}-01-02",
            "affected_parks": "usf,ioa",
            "estimated_crowd_impact": "high", "notes": "",
        })
        eid += 1

        # --- Sports ---
        events.append({
            "event_id": eid, "event_name": f"Pop Warner Super Bowl {year}",
            "event_category": "sports", "resort": "wdw",
            "start_date": f"{year}-12-01", "end_date": f"{year}-12-10",
            "affected_parks": "mk,epcot,hs,ak",
            "estimated_crowd_impact": "medium", "notes": "Pop Warner Cheer & Football",
        })
        eid += 1

    return events


def _generate_one_time_events(start_id: int) -> list[dict]:
    """Generate one-time / notable events."""
    eid = start_id
    events = []

    one_time = [
        ("COVID-19 WDW Closure", "closure", "wdw", "2020-03-16", "2020-07-11",
         "mk,epcot,hs,ak", "extreme", "MK/AK reopened Jul 11, EPCOT/HS Jul 15"),
        ("COVID-19 Universal Closure", "closure", "uni", "2020-03-16", "2020-06-05",
         "usf,ioa,vb", "extreme", ""),
        ("Star Wars Galaxy's Edge Opening", "ride_opening", "wdw", "2019-08-29", "2019-08-29",
         "hs", "extreme", "Hollywood Studios"),
        ("Rise of the Resistance Opening", "ride_opening", "wdw", "2019-12-05", "2019-12-05",
         "hs", "extreme", "Hollywood Studios"),
        ("Remy's Ratatouille Adventure Opening", "ride_opening", "wdw", "2021-10-01", "2021-10-01",
         "epcot", "high", "EPCOT"),
        ("Guardians Cosmic Rewind Opening", "ride_opening", "wdw", "2022-05-27", "2022-05-27",
         "epcot", "extreme", "EPCOT"),
        ("TRON Lightcycle Run Opening", "ride_opening", "wdw", "2023-04-04", "2023-04-04",
         "mk", "extreme", "Magic Kingdom"),
        ("Tiana's Bayou Adventure Opening", "ride_opening", "wdw", "2024-06-28", "2024-06-28",
         "mk", "extreme", "Magic Kingdom"),
        ("Hagrid's Magical Creatures Opening", "ride_opening", "uni", "2019-06-13", "2019-06-13",
         "ioa", "extreme", "Islands of Adventure"),
        ("VelociCoaster Opening", "ride_opening", "uni", "2021-06-10", "2021-06-10",
         "ioa", "extreme", "Islands of Adventure"),
        ("Epic Universe Grand Opening", "park_opening", "uni", "2025-05-22", "2025-05-22",
         "eu", "extreme", "New theme park"),
        ("FastPass+ Discontinued", "policy_change", "wdw", "2021-10-01", "2021-10-01",
         "mk,epcot,hs,ak", "high", "Replaced by Genie+"),
        ("Genie+ Launch", "policy_change", "wdw", "2021-10-19", "2021-10-19",
         "mk,epcot,hs,ak", "high", "Paid Lightning Lane system"),
        ("WDW 50th Anniversary", "celebration", "wdw", "2021-10-01", "2023-03-31",
         "mk,epcot,hs,ak", "high", "18-month celebration"),
        ("DAS Program Overhaul", "policy_change", "wdw", "2024-06-18", "2024-06-18",
         "mk,epcot,hs,ak", "medium", "Disability Access Service changes"),
        ("Hurricane Irma", "hurricane", "both", "2017-09-10", "2017-09-12",
         "mk,epcot,hs,ak,usf,ioa,vb", "extreme", "Both resorts closed"),
        ("Hurricane Ian", "hurricane", "both", "2022-09-28", "2022-09-29",
         "mk,epcot,hs,ak,usf,ioa,vb", "extreme", "Both resorts closed"),
        ("Hurricane Milton", "hurricane", "both", "2024-10-09", "2024-10-10",
         "mk,epcot,hs,ak,usf,ioa,vb", "extreme", "Both resorts closed"),
    ]

    for name, cat, resort, start, end, parks, impact, notes in one_time:
        events.append({
            "event_id": eid,
            "event_name": name,
            "event_category": cat,
            "resort": resort,
            "start_date": start,
            "end_date": end,
            "affected_parks": parks,
            "estimated_crowd_impact": impact,
            "notes": notes,
        })
        eid += 1

    return events


def main() -> None:
    recurring = _generate_recurring_events()
    one_time = _generate_one_time_events(start_id=len(recurring) + 1)
    all_events = recurring + one_time

    df = pd.DataFrame(all_events)
    logger.info("Generated %d events", len(df))

    # Save as dimension
    save_dimension(df, "events")

    # Also save to data/events/ as monthly parquet files
    events_dir = DATA_DIR / "events"
    events_dir.mkdir(parents=True, exist_ok=True)
    df.to_parquet(events_dir / "events.parquet", engine="pyarrow", index=False)
    logger.info("Saved events to %s", events_dir / "events.parquet")


if __name__ == "__main__":
    main()
