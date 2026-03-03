"""Parquet read/write/append/deduplicate utilities."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import duckdb
import pandas as pd

from parkwaits.config import DATA_DIR, DEDUP_KEYS

logger = logging.getLogger(__name__)


def append_to_monthly(
    df: Optional[pd.DataFrame],
    dataset: str,
    date_col: str = "date",
) -> Optional[Path]:
    """Append rows to the appropriate monthly Parquet file, deduplicating by composite key.

    Returns the path written, or None if nothing to write.
    """
    if df is None or df.empty:
        return None

    # Determine year/month from first row
    first_date = df[date_col].iloc[0]
    if isinstance(first_date, str):
        first_date = pd.Timestamp(first_date)
    year = str(first_date.year)
    month_str = f"{first_date.year}-{first_date.month:02d}"

    # Target path
    dataset_dir = DATA_DIR / dataset / year
    dataset_dir.mkdir(parents=True, exist_ok=True)
    path = dataset_dir / f"{month_str}.parquet"

    # Read existing and concat
    if path.exists():
        existing = pd.read_parquet(path, engine="pyarrow")
        combined = pd.concat([existing, df], ignore_index=True)
    else:
        combined = df.copy()

    # Deduplicate
    dedup_keys = DEDUP_KEYS.get(dataset, [])
    if dedup_keys:
        # Ensure all dedup key columns exist in the dataframe
        valid_keys = [k for k in dedup_keys if k in combined.columns]
        if valid_keys:
            combined = combined.drop_duplicates(subset=valid_keys, keep="last")

    combined.to_parquet(path, engine="pyarrow", index=False)
    logger.info("Wrote %d rows to %s", len(combined), path)

    # Also update latest.parquet with today's data only
    latest_dir = DATA_DIR / dataset
    latest_path = latest_dir / "latest.parquet"
    df.to_parquet(latest_path, engine="pyarrow", index=False)

    return path


def read_dataset(
    dataset: str,
    year: str = "*",
    months: str = "*",
) -> pd.DataFrame:
    """Read dataset Parquet files via DuckDB glob with schema evolution support."""
    pattern = str(DATA_DIR / dataset / year / f"{months}.parquet")
    try:
        result = duckdb.sql(
            f"SELECT * FROM read_parquet('{pattern}', union_by_name=true)"
        ).fetchdf()
        return result
    except duckdb.IOException:
        return pd.DataFrame()
    except Exception:
        logger.exception("Error reading dataset %s", dataset)
        return pd.DataFrame()


def read_latest(dataset: str) -> pd.DataFrame:
    """Read the latest.parquet for a dataset."""
    path = DATA_DIR / dataset / "latest.parquet"
    if path.exists():
        return pd.read_parquet(path, engine="pyarrow")
    return pd.DataFrame()


def save_dimension(df: pd.DataFrame, name: str) -> Path:
    """Save a dimension table to data/dimensions/{name}.parquet."""
    dim_dir = DATA_DIR / "dimensions"
    dim_dir.mkdir(parents=True, exist_ok=True)
    path = dim_dir / f"{name}.parquet"
    df.to_parquet(path, engine="pyarrow", index=False)
    logger.info("Saved dimension %s: %d rows", name, len(df))
    return path


def read_dimension(name: str) -> pd.DataFrame:
    """Read a dimension table. Returns empty DataFrame if not found."""
    path = DATA_DIR / "dimensions" / f"{name}.parquet"
    if path.exists():
        return pd.read_parquet(path, engine="pyarrow")
    return pd.DataFrame()


def log_collection_run(
    collector_name: str,
    status: str,
    records: int,
    started: datetime,
    error: Optional[str] = None,
) -> Optional[Path]:
    """Log a collection run to the collection_log dataset."""
    now = datetime.now(timezone.utc)
    duration = (now - started).total_seconds()

    log_df = pd.DataFrame([{
        "collector": collector_name,
        "status": status,
        "records": records,
        "started_at_utc": started.isoformat(),
        "finished_at_utc": now.isoformat(),
        "duration_seconds": round(duration, 2),
        "error": error,
        "date": now.strftime("%Y-%m-%d"),
    }])

    return append_to_monthly(log_df, "collection_log", date_col="date")
