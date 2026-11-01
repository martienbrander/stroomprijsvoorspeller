"""Fallback: ENTSO-E Transparency Platform, day-ahead prijzen (documentType A44).

Alleen actief als ENTSOE_TOKEN in .env of de omgeving staat. Gratis token na registratie op
https://transparency.entsoe.eu. Antwoord is XML; we parsen Period/Point met resolutie PT60M of PT15M.
"""

from __future__ import annotations

import logging
import os
import xml.etree.ElementTree as ET

import pandas as pd
import requests
from dotenv import load_dotenv

from stroomprijsvoorspeller.sources.http import USER_AGENT

log = logging.getLogger(__name__)

BASE_URL = "https://web-api.tp.entsoe.eu/api"
EIC = {"NL": "10YNL----------L"}
RESOLUTIE = {"PT60M": pd.Timedelta(hours=1), "PT15M": pd.Timedelta(minutes=15), "PT30M": pd.Timedelta(minutes=30)}


def token() -> str | None:
    load_dotenv()
    t = os.environ.get("ENTSOE_TOKEN", "").strip()
    return t or None


def beschikbaar() -> bool:
    return token() is not None


def _strip_ns(tag: str) -> str:
    return tag.split("}", 1)[-1]


def _utc(tekst: str) -> pd.Timestamp:
    ts = pd.Timestamp(tekst)
    return ts.tz_convert("UTC") if ts.tzinfo else ts.tz_localize("UTC")


def parse_xml(tekst: str) -> pd.DataFrame:
    """Zet een A44-document om naar time_utc / prijs_eur_mwh. Ontbrekende posities (curve type A03) worden doorgetrokken."""
    root = ET.fromstring(tekst)
    rijen: list[tuple[pd.Timestamp, float]] = []
    for ts in root.iter():
        if _strip_ns(ts.tag) != "TimeSeries":
            continue
        for periode in ts.iter():
            if _strip_ns(periode.tag) != "Period":
                continue
            kinderen = {_strip_ns(k.tag): k for k in periode}
            start = _utc(kinderen["timeInterval"].find("./{*}start").text)
            einde = _utc(kinderen["timeInterval"].find("./{*}end").text)
            stap = RESOLUTIE[kinderen["resolution"].text]
            punten = {}
            for p in periode:
                if _strip_ns(p.tag) != "Point":
                    continue
                pos = int(p.find("./{*}position").text)
                prijs = float(p.find("./{*}price.amount").text)
                punten[pos] = prijs
            n = int((einde - start) / stap)
            laatste = None
            for pos in range(1, n + 1):
                if pos in punten:
                    laatste = punten[pos]
                if laatste is not None:
                    rijen.append((start + (pos - 1) * stap, laatste))
    df = pd.DataFrame(rijen, columns=["time_utc", "prijs_eur_mwh"])
    return df.sort_values("time_utc").drop_duplicates("time_utc", keep="last").reset_index(drop=True)


def fetch_prices(start: pd.Timestamp, end: pd.Timestamp, *, bzn: str = "NL",
                 session: requests.Session | None = None, blok_dagen: int = 300) -> pd.DataFrame:
    tok = token()
    if not tok:
        raise RuntimeError("ENTSOE_TOKEN ontbreekt; ENTSO-E is alleen een optionele fallback")
    s = session or requests.Session()
    delen = []
    t = start
    while t < end:
        t_eind = min(t + pd.Timedelta(days=blok_dagen), end)
        params = {
            "securityToken": tok, "documentType": "A44",
            "in_Domain": EIC[bzn], "out_Domain": EIC[bzn],
            "periodStart": t.strftime("%Y%m%d%H%M"), "periodEnd": t_eind.strftime("%Y%m%d%H%M"),
        }
        log.info("ENTSO-E %s: %s .. %s", bzn, t.date(), t_eind.date())
        r = s.get(BASE_URL, params=params, timeout=120, headers={"User-Agent": USER_AGENT})
        r.raise_for_status()
        delen.append(parse_xml(r.text))
        t = t_eind
    if not delen:
        return pd.DataFrame(columns=["time_utc", "prijs_eur_mwh"])
    return pd.concat(delen, ignore_index=True).drop_duplicates("time_utc", keep="last").reset_index(drop=True)
