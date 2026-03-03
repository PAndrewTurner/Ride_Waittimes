"""Abstract base class for all data collectors."""

from __future__ import annotations

import abc
import logging
from datetime import datetime, timezone
from typing import Optional

import httpx
import pandas as pd
from tenacity import (
    retry,
    stop_after_attempt,
    wait_exponential,
    retry_if_exception_type,
)

from parkwaits.config import HTTP_TIMEOUT_SECONDS, HTTP_USER_AGENT, HTTP_MAX_RETRIES
from parkwaits.storage import append_to_monthly, log_collection_run

logger = logging.getLogger(__name__)

_RETRY_EXCEPTIONS = (
    httpx.HTTPStatusError,
    httpx.ConnectError,
    httpx.ReadTimeout,
)


class BaseCollector(abc.ABC):
    """Abstract base for HTTP data collectors with retry and logging."""

    dataset: str = ""  # Subclass must set

    def __init__(self) -> None:
        self._client = httpx.Client(
            timeout=HTTP_TIMEOUT_SECONDS,
            headers={"User-Agent": HTTP_USER_AGENT},
            follow_redirects=True,
        )

    def __enter__(self) -> BaseCollector:
        return self

    def __exit__(self, *args: object) -> None:
        self._client.close()

    @retry(
        stop=stop_after_attempt(HTTP_MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(_RETRY_EXCEPTIONS),
        reraise=True,
    )
    def fetch_json(self, url: str, **kwargs: object) -> dict:
        """Fetch JSON with retry/backoff."""
        resp = self._client.get(url, **kwargs)  # type: ignore[arg-type]
        resp.raise_for_status()
        return resp.json()

    @retry(
        stop=stop_after_attempt(HTTP_MAX_RETRIES),
        wait=wait_exponential(multiplier=1, min=2, max=30),
        retry=retry_if_exception_type(_RETRY_EXCEPTIONS),
        reraise=True,
    )
    def fetch_text(self, url: str, **kwargs: object) -> str:
        """Fetch text with retry/backoff."""
        resp = self._client.get(url, **kwargs)  # type: ignore[arg-type]
        resp.raise_for_status()
        return resp.text

    @abc.abstractmethod
    def collect(self) -> Optional[pd.DataFrame]:
        """Collect data and return a DataFrame. Subclasses must implement."""
        ...

    def run(self) -> int:
        """Execute collection, store results, and log the run. Returns row count."""
        started = datetime.now(timezone.utc)
        try:
            df = self.collect()
            row_count = len(df) if df is not None else 0
            if df is not None and not df.empty:
                append_to_monthly(df, self.dataset)
            log_collection_run(
                collector_name=self.__class__.__name__,
                status="success",
                records=row_count,
                started=started,
            )
            logger.info("%s collected %d rows", self.__class__.__name__, row_count)
            return row_count
        except Exception as exc:
            logger.exception("%s failed", self.__class__.__name__)
            log_collection_run(
                collector_name=self.__class__.__name__,
                status="error",
                records=0,
                started=started,
                error=str(exc),
            )
            raise
