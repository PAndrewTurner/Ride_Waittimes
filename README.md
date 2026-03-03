# Theme Park Wait Times Collector

Automated data collection agent for Walt Disney World and Universal Orlando ride wait times, weather, and park operating hours.

## Quick Start

```bash
# Install
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
pip install -e ".[dev]"

# Seed dimension tables
python scripts/seed_dimensions.py
python scripts/seed_events.py

# Collect data
python -m parkwaits collect hourly    # wait times + weather
python -m parkwaits collect daily     # park hours
python -m parkwaits status            # view collection status
python -m parkwaits discover          # find park entity IDs
```

## Architecture

- **Data Source**: ThemeParks.wiki API (primary), Queue-Times.com (fallback), Open-Meteo (weather)
- **Storage**: Parquet files organized by `data/{dataset}/{year}/{YYYY-MM}.parquet`
- **Scheduling**: GitHub Actions cron (hourly, daily, weekly)
- **Query Engine**: DuckDB for analytics
- **Cost**: $0/month (free APIs + GitHub Actions free tier)

## Parks Covered

### Walt Disney World
- Magic Kingdom, EPCOT, Hollywood Studios, Animal Kingdom

### Universal Orlando
- Universal Studios Florida, Islands of Adventure, Volcano Bay, Epic Universe

## Data Layout

```
data/
  wait_times/     # Ride wait times (hourly)
  weather/        # Weather observations (hourly)
  park_hours/     # Operating hours (twice daily)
  events/         # Historical events catalog
  dimensions/     # Parks, rides, calendar lookup tables
  ml/             # ML feature store (auto-built)
  collection_log/ # Run history
```

## GitHub Actions

| Workflow | Schedule | What it collects |
|----------|----------|-----------------|
| Hourly | Every hour 7AM-midnight ET | Wait times + weather |
| Daily | 6AM + 6PM ET | Park hours + feature rebuild |
| Weekly | Monday 8AM ET | Ride metadata + events refresh |

## License

MIT
