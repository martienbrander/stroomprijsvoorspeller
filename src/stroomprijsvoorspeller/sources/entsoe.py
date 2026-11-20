"""ENTSO-E Transparency Platform, day-ahead prijzen (documentType A44). De hoofdbron voor de prijzen (besluit 83).

Alleen actief als ENTSOE_TOKEN in .env of de omgeving staat. Gratis token na registratie op
https://transparency.entsoe.eu. Antwoord is XML; we parsen Period/Point met resolutie PT60M of PT15M.
"""

from __future__ import annotations

import logging
import os
import time
import xml.etree.ElementTree as ET

import pandas as pd
import requests
from dotenv import load_dotenv

from stroomprijsvoorspeller.sources.http import USER_AGENT, BronNietBereikbaar

log = logging.getLogger(__name__)

BASE_URL = "https://web-api.tp.entsoe.eu/api"
EIC = {"NL": "10YNL----------L"}
RESOLUTIE = {"PT60M": pd.Timedelta(hours=1), "PT15M": pd.Timedelta(minutes=15), "PT30M": pd.Timedelta(minutes=30)}
POGINGEN = 3          # bij een storing (geen antwoord, 429 of 5xx) zo vaak proberen
PAUZE_SECONDEN = 5.0
DAY_AHEAD = "A01"   # contract_MarketAgreement.type; A07 is de intraday-veiling en hoort hier niet bij


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
    """Zet een A44-document om naar time_utc / prijs_eur_mwh. Ontbrekende posities (curve type A03) worden doorgetrokken.

    Alleen day-ahead reeksen tellen mee: reeksen van de intraday-veiling (contract A07) slaan we over. Staat een uur
    er in meer dan één resolutie in, dan wint de fijnste (kwartier boven uur), zodat een uurprijs nooit de plaats van
    een kwartierprijs inneemt.
    """
    root = ET.fromstring(tekst)
    rijen: list[tuple[pd.Timestamp, float, pd.Timedelta]] = []
    for ts in root.iter():
        if _strip_ns(ts.tag) != "TimeSeries":
            continue
        contract = ts.find("./{*}contract_MarketAgreement.type")
        if contract is not None and contract.text != DAY_AHEAD:
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
                    rijen.append((start + (pos - 1) * stap, laatste, stap))
    df = pd.DataFrame(rijen, columns=["time_utc", "prijs_eur_mwh", "stap"])
    if not df.empty:
        uur = df["time_utc"].dt.floor("h")
        df = df[df["stap"] == df.groupby(uur)["stap"].transform("min")]
    df = df.drop(columns="stap")
    return df.sort_values("time_utc").drop_duplicates("time_utc", keep="last").reset_index(drop=True)


def _vraag(s: requests.Session, params: dict) -> str:
    """Eén verzoek aan de API, met een paar pogingen bij een storing. Geeft de XML terug.

    De foutmeldingen van requests bevatten de URL, en daarin staat het token. Daarom eigen meldingen zonder URL.
    """
    melding = ""
    for poging in range(1, POGINGEN + 1):
        try:
            r = s.get(BASE_URL, params=params, timeout=120, headers={"User-Agent": USER_AGENT})
        except requests.RequestException as fout:
            melding = f"ENTSO-E niet bereikbaar ({type(fout).__name__})"
        else:
            if r.status_code == 200:
                return r.text
            melding = f"ENTSO-E gaf HTTP {r.status_code}"
            if r.status_code != 429 and r.status_code < 500:   # een afwijzing (401, 400) wordt van wachten niet beter
                break
        if poging < POGINGEN:
            log.warning("%s; poging %d van %d", melding, poging, POGINGEN)
            time.sleep(PAUZE_SECONDEN)
    raise BronNietBereikbaar(melding)


def fetch_prices(start: pd.Timestamp, end: pd.Timestamp, *, bzn: str = "NL",
                 session: requests.Session | None = None, blok_dagen: int = 300) -> pd.DataFrame:
    tok = token()
    if not tok:
        raise RuntimeError("ENTSOE_TOKEN ontbreekt")
    s = session or requests.Session()
    delen = []
    t, end = start.floor("h"), end.ceil("h")   # hele uren, zoals in de voorbeelden van ENTSO-E
    while t < end:
        t_eind = min(t + pd.Timedelta(days=blok_dagen), end)
        params = {
            "securityToken": tok, "documentType": "A44",
            "in_Domain": EIC[bzn], "out_Domain": EIC[bzn],
            "periodStart": t.strftime("%Y%m%d%H%M"), "periodEnd": t_eind.strftime("%Y%m%d%H%M"),
        }
        log.info("ENTSO-E %s: %s .. %s", bzn, t.date(), t_eind.date())
        delen.append(parse_xml(_vraag(s, params)))
        t = t_eind
    if not delen:
        return pd.DataFrame(columns=["time_utc", "prijs_eur_mwh"])
    return pd.concat(delen, ignore_index=True).drop_duplicates("time_utc", keep="last").reset_index(drop=True)
