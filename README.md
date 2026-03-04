# Theme Park Wait Times Collector

Collect ride wait times, weather, and park hours for Walt Disney World + Universal Orlando. Data saves to CSV files you can open in Excel.

## Quick Start

1. Install Python dependencies (only 2):
```
pip install requests pandas
```

2. Run the collector:
```
python collect_all.py
```

3. Open the CSV files in Excel:
- `data/wait_times.csv` — ride wait times
- `data/weather.csv` — current weather
- `data/park_hours.csv` — park operating hours

## Individual Scripts

```
python collect_wait_times.py    # Just wait times
python collect_weather.py       # Just weather
python collect_park_hours.py    # Just park hours
python collect_all.py           # Everything at once
```

## Parks Covered

**Walt Disney World:** Magic Kingdom, EPCOT, Hollywood Studios, Animal Kingdom

**Universal Orlando:** Universal Studios Florida, Islands of Adventure, Volcano Bay, Epic Universe

## Data Sources

- [ThemeParks.wiki](https://themeparks.wiki) — ride wait times and park hours (primary)
- [Queue-Times.com](https://queue-times.com) — ride wait times (fallback)
- [Open-Meteo](https://open-meteo.com) — weather data

All APIs are free, no keys needed.

## License

MIT
