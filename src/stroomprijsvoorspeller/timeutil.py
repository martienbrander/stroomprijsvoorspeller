"""Tijdhulpmiddelen. Intern rekenen we in UTC; dagen, uren en weergave zijn lokaal (Europe/Amsterdam)."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

import pandas as pd

TZ_NAAM = "Europe/Amsterdam"
TZ = ZoneInfo(TZ_NAAM)
MIN_UREN_PER_DAG = 23   # een lokale dag heeft minstens 23 uur (de dag waarop de zomertijd ingaat)


def utc_now() -> pd.Timestamp:
    return pd.Timestamp.now(tz="UTC").floor("s")


def ensure_utc(index: pd.DatetimeIndex | pd.Series) -> pd.DatetimeIndex:
    """Maakt een DatetimeIndex tz-aware in UTC. Naïeve tijden worden als UTC gelezen."""
    idx = pd.DatetimeIndex(index)
    if idx.tz is None:
        return idx.tz_localize("UTC")
    return idx.tz_convert("UTC")


def to_local(index: pd.DatetimeIndex) -> pd.DatetimeIndex:
    return ensure_utc(index).tz_convert(TZ)


def local_date(index: pd.DatetimeIndex) -> pd.Index:
    """Lokale kalenderdag per tijdstip (python date)."""
    return pd.Index(to_local(index).date)


def local_day_bounds(dag: date) -> tuple[pd.Timestamp, pd.Timestamp]:
    """[start, einde) van een lokale dag, in UTC. Zomertijd-dagen hebben 23 of 25 uur."""
    start = pd.Timestamp(datetime.combine(dag, time(0), tzinfo=TZ)).tz_convert("UTC")
    einde = pd.Timestamp(datetime.combine(dag + timedelta(days=1), time(0), tzinfo=TZ)).tz_convert("UTC")
    return start, einde


def hours_in_local_day(dag: date) -> int:
    start, einde = local_day_bounds(dag)
    return int((einde - start) / pd.Timedelta(hours=1))


def publication_cutoff(dag: date, uur_lokaal: int = 13) -> pd.Timestamp:
    """Tijdstip (UTC) waarop op dag `dag` de day-ahead prijzen voor morgen bekend zijn."""
    return pd.Timestamp(datetime.combine(dag, time(uur_lokaal), tzinfo=TZ)).tz_convert("UTC")


def local_hour_range(dag: date) -> pd.DatetimeIndex:
    """Alle uurtijdstippen (UTC) van een lokale dag."""
    start, einde = local_day_bounds(dag)
    return pd.date_range(start, einde, freq="h", inclusive="left")
