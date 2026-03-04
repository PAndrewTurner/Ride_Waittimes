"""
Collect everything: ride wait times + weather + park hours.
Saves CSV files to the data/ folder — open them in Excel.

Usage:
    pip install requests pandas
    python collect_all.py
"""

from collect_wait_times import main as collect_waits
from collect_weather import main as collect_weather
from collect_park_hours import main as collect_hours


def main():
    print("=" * 50)
    print("  Theme Park Wait Times Collector")
    print("=" * 50)

    print("\n--- Wait Times ---")
    try:
        collect_waits()
    except Exception as e:
        print(f"  Wait times failed: {e}")

    print("\n--- Weather ---")
    try:
        collect_weather()
    except Exception as e:
        print(f"  Weather failed: {e}")

    print("\n--- Park Hours ---")
    try:
        collect_hours()
    except Exception as e:
        print(f"  Park hours failed: {e}")

    print("\n" + "=" * 50)
    print("  Done! Check the data/ folder for CSV files.")
    print("  Open them in Excel to view the data.")
    print("=" * 50)


if __name__ == "__main__":
    main()
