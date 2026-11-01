"""Day-ahead prijzen van Energy-Charts (Fraunhofer ISE). Geen sleutel nodig. Licentie data: CC BY 4.0.

Endpoint: https://api.energy-charts.info/price?bzn=NL&start=...&end=...
Antwoord: {"unix_seconds": [...], "price": [...], "unit": "EUR / MWh", ...}
Resolutie: uur tot en met september 2025, kwartier daarna. We bewaren de ruwe resolutie.
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd
import requests

from stroomprijsvoorspeller.sources.http import get_json
from stroomprijsvoorspeller.timeutil import utc_now

log = logging.getLogger(__name__)

BASE_URL = "https://api.energy-charts.info/price"
RUW_BESTAND = "prijzen_nl_ruw.parquet"
KOLOMMEN = ["time_utc", "prijs_eur_mwh"]


def parse_response(payload: dict) -> pd.DataFrame:
    """Zet het API-antwoord om naar een DataFrame met time_utc (tz=UTC) en prijs_eur_mwh (float, NaN bij ontbrekend)."""
    secs = payload.get("unix_seconds") or []
    prijzen = payload.get("price") or []
    if len(secs) != len(prijzen):
        raise ValueError("unix_seconds en price hebben verschillende lengte")
    df = pd.DataFrame({
        "time_utc": pd.to_datetime(pd.Series(secs, dtype="int64"), unit="s", utc=True),
        "prijs_eur_mwh": pd.to_numeric(pd.Series(prijzen, dtype="object"), errors="coerce").astype("float64"),
    })
    return df.sort_values("time_utc").drop_duplicates("time_utc", keep="last").reset_index(drop=True)


def _iso(ts: pd.Timestamp) -> str:
    return ts.tz_convert("UTC").strftime("%Y-%m-%dT%H:%MZ")


def fetch_prices(start: pd.Timestamp, end: pd.Timestamp, *, bzn: str = "NL",
                 session: requests.Session | None = None, blok_dagen: int = 400) -> pd.DataFrame:
    """Haalt prijzen op in [start, end], in blokken zodat één mislukte call niet alles kost."""
    delen = []
    t = start
    while t < end:
        t_eind = min(t + pd.Timedelta(days=blok_dagen), end)
        log.info("Energy-Charts %s: %s .. %s", bzn, t.date(), t_eind.date())
        payload = get_json(BASE_URL, {"bzn": bzn, "start": _iso(t), "end": _iso(t_eind)}, session=session)
        delen.append(parse_response(payload))
        t = t_eind
    if not delen:
        return pd.DataFrame(columns=KOLOMMEN)
    df = pd.concat(delen, ignore_index=True)
    return df.sort_values("time_utc").drop_duplicates("time_utc", keep="last").reset_index(drop=True)


def lees_ruw(raw_dir: Path) -> pd.DataFrame:
    pad = raw_dir / RUW_BESTAND
    if not pad.exists():
        return pd.DataFrame(columns=KOLOMMEN).astype({"prijs_eur_mwh": "float64"})
    df = pd.read_parquet(pad)
    df["time_utc"] = pd.to_datetime(df["time_utc"], utc=True)
    return df


def update_prices(raw_dir: Path, data_start: str, *, bzn: str = "NL", overlap_dagen: int = 3,
                  session: requests.Session | None = None) -> pd.DataFrame:
    """Incrementeel: haalt alles op vanaf (laatste bekende tijdstip - overlap) tot overmorgen en voegt samen.

    De overlap zorgt dat late correcties en de nog niet gepubliceerde uren van gisteren alsnog goed komen.
    """
    raw_dir.mkdir(parents=True, exist_ok=True)
    bestaand = lees_ruw(raw_dir)
    if bestaand.empty:
        start = pd.Timestamp(data_start, tz="UTC")
    else:
        start = bestaand["time_utc"].max() - pd.Timedelta(days=overlap_dagen)
    einde = (utc_now() + pd.Timedelta(days=2)).normalize()
    nieuw = fetch_prices(start, einde, bzn=bzn, session=session)
    nieuw = nieuw.dropna(subset=["prijs_eur_mwh"])
    samen = pd.concat([bestaand, nieuw], ignore_index=True)
    samen = samen.sort_values("time_utc").drop_duplicates("time_utc", keep="last").reset_index(drop=True)
    samen.to_parquet(raw_dir / RUW_BESTAND, index=False)
    log.info("prijzen: %d rijen, %s .. %s (+%d nieuw/bijgewerkt)", len(samen),
             samen["time_utc"].min(), samen["time_utc"].max(), len(nieuw))
    return samen
