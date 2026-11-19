"""Fallback: EnergyZero API, day-ahead prijzen NL (leveranciersprijzen via EnergyZero).

Alleen een vangnet: wordt in `epv daily`/`epv fetch` gebruikt als ENTSO-E geen (nieuwere) prijzen
levert, zodat de site de prijzen voor morgen toch kan tonen. Geen sleutel nodig.

Endpoint: https://api.energyzero.nl/v1/energyprices?fromDate=...&tillDate=...&interval=4&usageType=1&inclBtw=false
Antwoord: {"Prices": [{"readingDate": "...Z", "price": <EUR/kWh>}, ...]}.
We vragen prijzen exclusief btw (kale beursprijs, zelfde grootheid als ENTSO-E na omrekening /1000)
en geven EUR/MWh terug, zodat de rest van de pipeline (btw, inkoopvergoeding, kalibratie) er niets
van merkt.
"""

from __future__ import annotations

import logging
from datetime import timedelta

import pandas as pd
import requests

from stroomprijsvoorspeller.sources.http import get_json

log = logging.getLogger(__name__)

BASE_URL = "https://api.energyzero.nl/v1/energyprices"
KOLOMMEN = ["time_utc", "prijs_eur_mwh"]

# interval-codes van de API: 4 = per uur, 5 = per kwartier
_INTERVAL = {"PT60M": 4, "PT15M": 5}


def _iso_ms(ts: pd.Timestamp) -> str:
    """UTC ISO-tijd met milliseconden, zoals de API verwacht: 2026-11-19T23:00:00.000Z."""
    return ts.tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%S.000Z")


def parse_response(payload: dict) -> pd.DataFrame:
    """Zet het API-antwoord om naar een DataFrame met time_utc (tz=UTC) en prijs_eur_mwh (float, NaN bij ontbrekend).

    `price` is in EUR/kWh exclusief btw; x1000 geeft EUR/MWh. Zelfde vorm als `energy_charts.parse_response`,
    zodat de pipeline beide bronnen door elkaar kan gebruiken.
    """
    prijzen = payload.get("Prices") or []
    if not prijzen:
        return pd.DataFrame(columns=KOLOMMEN)
    df = pd.DataFrame({
        "time_utc": pd.to_datetime(pd.Series([p.get("readingDate") for p in prijzen], dtype="object"), utc=True),
        "prijs_eur_mwh": pd.to_numeric(pd.Series([p.get("price") for p in prijzen], dtype="object"),
                                       errors="coerce").astype("float64") * 1000.0,
    })
    return df.sort_values("time_utc").drop_duplicates("time_utc", keep="last").reset_index(drop=True)


def fetch_prices(start: pd.Timestamp, end: pd.Timestamp, *, bzn: str = "NL", resolutie: str = "PT60M",
                 session: requests.Session | None = None, blok_dagen: int = 30) -> pd.DataFrame:
    """Haalt prijzen op in [start, end], in blokken zodat één mislukte call niet alles kost."""
    if bzn != "NL":
        raise ValueError("EnergyZero levert alleen prijzen voor NL")
    if resolutie not in _INTERVAL:
        raise ValueError(f"onbekende resolutie voor EnergyZero: {resolutie}")
    delen = []
    t = start
    while t < end:
        t_eind = min(t + pd.Timedelta(days=blok_dagen), end)
        log.info("EnergyZero %s (%s): %s .. %s", bzn, resolutie, t.date(), t_eind.date())
        params = {
            "fromDate": _iso_ms(t), "tillDate": _iso_ms(t_eind - pd.Timedelta(milliseconds=1)),
            "interval": _INTERVAL[resolutie], "usageType": 1, "inclBtw": "false",
        }
        payload = get_json(BASE_URL, params, session=session)
        delen.append(parse_response(payload))
        t = t_eind
    if not delen:
        return pd.DataFrame(columns=KOLOMMEN)
    df = pd.concat(delen, ignore_index=True)
    return df.sort_values("time_utc").drop_duplicates("time_utc", keep="last").reset_index(drop=True)
