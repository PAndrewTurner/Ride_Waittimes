"""CLI interface: collect, status, discover commands."""

from __future__ import annotations

import argparse
import logging
import sys

from parkwaits import __version__

logger = logging.getLogger("parkwaits")


def _setup_logging() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


def cmd_collect(args: argparse.Namespace) -> int:
    """Run collectors based on target."""
    from parkwaits.collectors.wait_times import WaitTimeCollector
    from parkwaits.collectors.weather import WeatherCollector
    from parkwaits.collectors.park_hours import ParkHoursCollector

    target = args.target
    failed = False

    collectors: list[tuple[str, type]] = []

    if target in ("hourly", "waits", "all"):
        collectors.append(("WaitTimes", WaitTimeCollector))
    if target in ("hourly", "weather", "all"):
        collectors.append(("Weather", WeatherCollector))
    if target in ("daily", "hours", "all"):
        collectors.append(("ParkHours", ParkHoursCollector))

    for name, cls in collectors:
        try:
            with cls() as collector:
                count = collector.run()
                print(f"  {name}: {count} rows collected")
        except Exception as exc:
            print(f"  {name}: FAILED - {exc}")
            failed = True

    return 1 if failed else 0


def cmd_status(_args: argparse.Namespace) -> int:
    """Show dataset status and recent collection logs."""
    from parkwaits.storage import read_dataset, read_latest

    datasets = ["wait_times", "weather", "park_hours", "events", "collection_log"]

    print(f"\nparkwaits v{__version__} — Data Status\n")
    print(f"{'Dataset':<20} {'Rows':>8}  {'Date Range'}")
    print("-" * 60)

    for ds in datasets:
        df = read_dataset(ds)
        if df.empty:
            print(f"{ds:<20} {'0':>8}  (no data)")
            continue

        row_count = len(df)
        if "date" in df.columns:
            date_min = df["date"].min()
            date_max = df["date"].max()
            print(f"{ds:<20} {row_count:>8}  {date_min} to {date_max}")
        else:
            print(f"{ds:<20} {row_count:>8}")

    # Recent collection logs
    log_df = read_latest("collection_log")
    if not log_df.empty:
        print(f"\nRecent Collection Runs:")
        print("-" * 60)
        tail = log_df.tail(10)
        for _, row in tail.iterrows():
            icon = "\u2713" if row.get("status") == "success" else "\u2717"
            collector = row.get("collector", "?")
            records = row.get("records", 0)
            duration = row.get("duration_seconds", 0)
            ts = row.get("finished_at_utc", "")
            print(f"  {icon} {collector:<25} {records:>4} rows  {duration:>6.1f}s  {ts}")

    return 0


def cmd_discover(_args: argparse.Namespace) -> int:
    """Discover park entity IDs from ThemeParks.wiki."""
    import httpx
    from parkwaits.config import THEMEPARKS_API_BASE, HTTP_USER_AGENT, HTTP_TIMEOUT_SECONDS

    print("Fetching destinations from ThemeParks.wiki...\n")

    client = httpx.Client(
        timeout=HTTP_TIMEOUT_SECONDS,
        headers={"User-Agent": HTTP_USER_AGENT},
    )

    try:
        resp = client.get(f"{THEMEPARKS_API_BASE}/destinations")
        resp.raise_for_status()
        data = resp.json()
    finally:
        client.close()

    destinations = data.get("destinations", [])

    keywords = ["walt disney world", "universal orlando", "universal studios"]

    for dest in destinations:
        dest_name = dest.get("name", "").lower()
        if not any(kw in dest_name for kw in keywords):
            continue

        print(f"=== {dest.get('name', 'Unknown')} ===")
        parks = dest.get("parks", [])
        for park in parks:
            print(f"  {park.get('name', '?'):<40} {park.get('id', '?')}")
        print()

    print("Update config.py with any missing entity_id values.")
    return 0


def main() -> None:
    _setup_logging()

    parser = argparse.ArgumentParser(
        prog="parkwaits",
        description="Theme park wait time data collector",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparsers = parser.add_subparsers(dest="command")

    # collect
    collect_parser = subparsers.add_parser("collect", help="Collect data")
    collect_parser.add_argument(
        "target",
        choices=["hourly", "daily", "waits", "weather", "hours", "all"],
        help="What to collect",
    )
    collect_parser.set_defaults(func=cmd_collect)

    # status
    status_parser = subparsers.add_parser("status", help="Show data status")
    status_parser.set_defaults(func=cmd_status)

    # discover
    discover_parser = subparsers.add_parser("discover", help="Discover park entity IDs")
    discover_parser.set_defaults(func=cmd_discover)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(0)

    exit_code = args.func(args)
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
