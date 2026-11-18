"""Weer van Open-Meteo (geen sleutel; data CC BY 4.0).

Twee API's:
- Forecast API: de huidige verwachting voor de komende dagen. Gebruikt in de dagelijkse run.
- Previous Runs API: per uur de verwachting zoals die N dagen eerder was (`<var>_previous_dayN`).
  Gebruikt voor trainen en backtesten zonder lekkage. Data beschikbaar vanaf ca. 2024-03-01.

Kolomnaam-conventie in onze data: `<variabele>_lead<N>` (previous runs) en `<variabele>` (forecast).
Windsnelheid vragen we op in m/s.
"""

from __future__ import annotations

import logging
import time
from pathlib import Path

import pandas as pd
import requests

from stroomprijsvoorspeller.config import Config, Weerpunt
from stroomprijsvoorspeller.sources.http import get_json
from stroomprijsvoorspeller.timeutil import utc_now

log = logging.getLogger(__name__)

FORECAST_URL = "https://api.open-meteo.com/v1/forecast"
PREVIOUS_RUNS_URL = "https://previous-runs-api.open-meteo.com/v1/forecast"
PAUZE_SECONDEN = 0.6  # netjes blijven binnen de gratis limieten (600 calls per minuut)
# De actuele verwachting: drie snelle pogingen met 30 seconden wachten op antwoord (besluit 78). Een gezond antwoord
# komt binnen een seconde; een storing lossen meer snelle pogingen niet op, daarvoor zijn de rondes in pipeline/daily.
FORECAST_POGINGEN = 3
FORECAST_TIMEOUT_SECONDEN = 30


def prev_run_var(variabele: str, lead: int) -> str:
    return f"{variabele}_previous_day{lead}"


def lead_kolom(variabele: str, lead: int) -> str:
    return f"{variabele}_lead{lead}"


def parse_hourly(payload: dict, hernoem: dict[str, str] | None = None) -> pd.DataFrame:
    """Zet payload["hourly"] om naar een DataFrame met time_utc (tz=UTC) en een kolom per variabele."""
    hourly = payload.get("hourly") or {}
    if "time" not in hourly:
        raise ValueError("geen hourly.time in antwoord")
    df = pd.DataFrame({k: v for k, v in hourly.items() if k != "time"})
    df.insert(0, "time_utc", pd.to_datetime(hourly["time"], utc=True))
    for k in df.columns[1:]:
        df[k] = pd.to_numeric(df[k], errors="coerce").astype("float64")
    if hernoem:
        df = df.rename(columns=hernoem)
    return df


def fetch_forecast(punt: Weerpunt, variabelen: tuple[str, ...], dagen: int, model: str,
                   session: requests.Session | None = None) -> pd.DataFrame:
    """Huidige verwachting voor `dagen` dagen vooruit (vandaag inbegrepen)."""
    params = {
        "latitude": punt.lat, "longitude": punt.lon,
        "hourly": ",".join(variabelen),
        "forecast_days": dagen, "timezone": "UTC", "wind_speed_unit": "ms",
        "models": model,
    }
    payload = get_json(FORECAST_URL, params, session=session, retries=FORECAST_POGINGEN,
                       timeout=FORECAST_TIMEOUT_SECONDEN)
    df = parse_hourly(payload)
    df.insert(1, "punt", punt.naam)
    df.insert(2, "uitgegeven_utc", utc_now())
    return df


def fetch_previous_runs(punt: Weerpunt, variabelen: tuple[str, ...], leads: tuple[int, ...],
                        start: pd.Timestamp, einde: pd.Timestamp, model: str,
                        session: requests.Session | None = None, blok_dagen: int = 120) -> pd.DataFrame:
    """Verwachtingen zoals die `lead` dagen eerder waren, voor alle uren in [start, einde]."""
    gevraagd = [prev_run_var(v, n) for v in variabelen for n in leads]
    hernoem = {prev_run_var(v, n): lead_kolom(v, n) for v in variabelen for n in leads}
    delen = []
    t = start.normalize()
    while t <= einde:
        t_eind = min(t + pd.Timedelta(days=blok_dagen - 1), einde)
        params = {
            "latitude": punt.lat, "longitude": punt.lon,
            "hourly": ",".join(gevraagd),
            "start_date": t.strftime("%Y-%m-%d"), "end_date": t_eind.strftime("%Y-%m-%d"),
            "timezone": "UTC", "wind_speed_unit": "ms", "models": model,
        }
        log.info("Open-Meteo previous runs %s: %s .. %s", punt.naam, params["start_date"], params["end_date"])
        payload = get_json(PREVIOUS_RUNS_URL, params, session=session)
        delen.append(parse_hourly(payload, hernoem))
        t = t_eind + pd.Timedelta(days=1)
        time.sleep(PAUZE_SECONDEN)
    if delen:
        df = pd.concat(delen, ignore_index=True)
    else:
        df = pd.DataFrame(columns=["time_utc", *hernoem.values()])
    df.insert(1, "punt", punt.naam)
    return df.sort_values("time_utc").drop_duplicates("time_utc", keep="last").reset_index(drop=True)


# ---------- opslag ----------

def prev_runs_bestand(raw_dir: Path, punt: str) -> Path:
    return raw_dir / f"weer_prev_runs_{punt}.parquet"


def forecast_bestand(raw_dir: Path, punt: str) -> Path:
    return raw_dir / f"weer_forecast_{punt}.parquet"


def _lees(pad: Path) -> pd.DataFrame | None:
    if not pad.exists():
        return None
    df = pd.read_parquet(pad)
    df["time_utc"] = pd.to_datetime(df["time_utc"], utc=True)
    return df


def update_previous_runs(cfg: Config, session: requests.Session | None = None,
                         overlap_dagen: int = 2) -> dict[str, pd.DataFrame]:
    """Per weerpunt: haalt ontbrekende dagen op (tot en met vandaag) en voegt samen met wat er al is."""
    cfg.raw_dir.mkdir(parents=True, exist_ok=True)
    vandaag = utc_now().normalize()
    uit: dict[str, pd.DataFrame] = {}
    for punt in cfg.weerpunten:
        pad = prev_runs_bestand(cfg.raw_dir, punt.naam)
        bestaand = _lees(pad)
        nodig = {lead_kolom(v, n) for v in cfg.weer_variabelen for n in cfg.lead_dagen}
        if bestaand is not None and not nodig.issubset(bestaand.columns):
            log.info("weer prev-runs %s: nieuwe variabelen of leads in config, haal alles opnieuw op", punt.naam)
            bestaand = None
        if bestaand is None or bestaand.empty:
            start = pd.Timestamp(cfg.weer_start, tz="UTC")
        else:
            start = bestaand["time_utc"].max().normalize() - pd.Timedelta(days=overlap_dagen)
        if start > vandaag:
            uit[punt.naam] = bestaand
            continue
        nieuw = fetch_previous_runs(punt, cfg.weer_variabelen, cfg.lead_dagen, start, vandaag,
                                    cfg.weer_model, session)
        # rijen zonder enige waarde (toekomst of ontbrekend) niet bewaren
        waarde_kolommen = [c for c in nieuw.columns if c not in ("time_utc", "punt")]
        nieuw = nieuw.dropna(subset=waarde_kolommen, how="all")
        samen = pd.concat([bestaand, nieuw], ignore_index=True) if bestaand is not None else nieuw
        samen = samen.sort_values("time_utc").drop_duplicates("time_utc", keep="last").reset_index(drop=True)
        samen.to_parquet(pad, index=False)
        log.info("weer prev-runs %s: %d rijen t/m %s", punt.naam, len(samen), samen["time_utc"].max())
        uit[punt.naam] = samen
    return uit


def store_forecasts(cfg: Config, session: requests.Session | None = None) -> dict[str, pd.DataFrame]:
    """Haalt per punt de huidige verwachting op en bewaart die, met uitgiftemoment, naast eerdere uitgiften.

    Zo bouwen we een archief op van wat de dagelijkse run echt te zien kreeg.
    """
    cfg.raw_dir.mkdir(parents=True, exist_ok=True)
    uit: dict[str, pd.DataFrame] = {}
    for punt in cfg.weerpunten:
        nieuw = fetch_forecast(punt, cfg.weer_variabelen, cfg.forecast_dagen, cfg.weer_model, session)
        nieuw["uitgiftedag_utc"] = nieuw["uitgegeven_utc"].dt.normalize()
        pad = forecast_bestand(cfg.raw_dir, punt.naam)
        bestaand = _lees(pad)
        if bestaand is not None:
            bestaand["uitgegeven_utc"] = pd.to_datetime(bestaand["uitgegeven_utc"], utc=True)
            bestaand["uitgiftedag_utc"] = pd.to_datetime(bestaand["uitgiftedag_utc"], utc=True)
            samen = pd.concat([bestaand, nieuw], ignore_index=True)
        else:
            samen = nieuw
        # per uitgiftedag maar een verwachting per uur bewaren (de laatste van die dag)
        samen = (samen.sort_values(["uitgiftedag_utc", "time_utc", "uitgegeven_utc"])
                 .drop_duplicates(["uitgiftedag_utc", "time_utc"], keep="last").reset_index(drop=True))
        samen.to_parquet(pad, index=False)
        uit[punt.naam] = samen
        time.sleep(PAUZE_SECONDEN)
    log.info("weer forecast opgeslagen voor %d punten", len(uit))
    return uit
