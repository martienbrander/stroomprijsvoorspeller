"""Featurematrix per (voorspelmoment, doeluur).

Het voorspelmoment ("origin") is een lokale dag D om `publicatie_uur_lokaal` (13:00). Op dat moment zijn de
day-ahead prijzen bekend tot en met het einde van de lokale dag D+1. We voorspellen alle uren van D+k voor
k in de horizon (2..5, in de backtest tot 7).

Lekkage-regels (getest in tests/test_features.py):
- prijsfeatures gebruiken uitsluitend prijzen met time_utc < bekend_tot(D)
- weerfeatures voor dag D+k komen uit de kolommen `<punt>__<var>_lead{k}`: de verwachting zoals die k dagen
  voor het doeluur bestond, dus op dag D
- kalenderfeatures zijn deterministisch

Rijen: één per (origin, time_utc). Kolommen: META, kalender, weer (naam zonder lead-suffix), prijs, DOEL.
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

import numpy as np
import pandas as pd

from stroomprijsvoorspeller.config import Config
from stroomprijsvoorspeller.sources.calendar import kalender_features
from stroomprijsvoorspeller.timeutil import local_day_bounds, local_hour_range, publication_cutoff

log = logging.getLogger(__name__)

PRIJS = "prijs_eur_mwh"
DOEL = "doel"
META = ["origin", "time_utc", "horizon_dag", "horizon_uren", "datum_lokaal"]
KALENDER = ["uur_lokaal", "weekdag", "maand", "dag_van_jaar", "is_weekend", "is_feestdag", "is_vrije_dag", "seizoen"]
PRIJSFEATURES = [
    "prijs_laatste_dag_uur", "prijs_laatste_dag_gem", "prijs_laatste_dag_std",
    "prijs_laatste_dag_min", "prijs_laatste_dag_max",
    "prijs_dag_min1_uur", "prijs_dag_min2_uur",
    "prijs_recent_gem", "prijs_recent_std", "prijs_recent_uur_gem",
    "prijs_profiel_uur_gem", "prijs_vorige_week_uur",
]
BASELINE_KOLOMMEN = {
    "laatste_dag": "prijs_laatste_dag_uur",
    "vorige_week": "prijs_vorige_week_uur",
    "profiel_4w": "prijs_profiel_uur_gem",
}
WIND_PLAFOND_MS = 12.0  # boven deze windsnelheid levert een turbine ongeveer vol vermogen


def bekend_tot(origin: date) -> pd.Timestamp:
    """Prijzen zijn op het voorspelmoment bekend voor alle uren vóór dit tijdstip: einde van lokale dag D+1."""
    return local_day_bounds(origin + timedelta(days=1))[1]


def weer_kolommen_voor_lead(kolommen, lead: int) -> dict[str, str]:
    """Mapping `<punt>__<var>_lead{lead}` -> `<punt>__<var>` voor alle kolommen met deze lead."""
    suffix = f"_lead{lead}"
    return {c: c[: -len(suffix)] for c in kolommen if c.endswith(suffix)}


def prijs_pivot(prijzen: pd.DataFrame) -> pd.DataFrame:
    """Prijs per (lokale datum, lokaal uur). Dubbel uur bij wintertijd wordt gemiddeld; ontbrekend uur blijft NaN."""
    kal = kalender_features(pd.DatetimeIndex(prijzen["time_utc"]))
    df = pd.DataFrame({
        "datum_lokaal": kal["datum_lokaal"].to_numpy(),
        "uur_lokaal": kal["uur_lokaal"].to_numpy(),
        PRIJS: prijzen[PRIJS].to_numpy(),
    })
    pivot = df.pivot_table(index="datum_lokaal", columns="uur_lokaal", values=PRIJS, aggfunc="mean")
    pivot.index = pd.Index(pivot.index, name="datum_lokaal")
    return pivot.reindex(columns=range(24))


def weer_aggregaten(weer: pd.DataFrame, cfg: Config) -> pd.DataFrame:
    """Gemiddelden over groepen weerpunten. Verwacht kolommen `<punt>__<var>` (zonder lead-suffix)."""
    uit = pd.DataFrame(index=weer.index)
    groepen = {
        "zee": [p.naam for p in cfg.weerpunten if p.type == "zee"],
        "land": [p.naam for p in cfg.weerpunten if p.type == "land"],
        "buitenland": [p.naam for p in cfg.weerpunten if "buitenland" in p.type],
        "alle": [p.naam for p in cfg.weerpunten],
    }

    def kolommen(punten, var):
        return [f"{p}__{var}" for p in punten if f"{p}__{var}" in weer.columns]

    for groep in ("zee", "land", "buitenland"):
        k = kolommen(groepen[groep], "wind_speed_100m")
        if k:
            w = weer[k]
            uit[f"wind_{groep}_gem"] = w.mean(axis=1)
            uit[f"wind_{groep}_vermogen"] = (w.clip(upper=WIND_PLAFOND_MS) / WIND_PLAFOND_MS).pow(3).mean(axis=1)
    for var, naam in (("shortwave_radiation", "straling"), ("cloud_cover", "bewolking"), ("temperature_2m", "temp")):
        k = kolommen(groepen["alle"], var)
        if k:
            uit[f"{naam}_gem"] = weer[k].mean(axis=1)
    return uit


def _prijsfeatures_voor_origin(pivot_bekend: pd.DataFrame, origin: date, doeldata: pd.Index,
                               uren: pd.Index, cfg: Config) -> pd.DataFrame:
    """Prijsfeatures voor alle doelrijen van één origin. `pivot_bekend` bevat alleen dagen <= D+1."""
    laatste = origin + timedelta(days=1)
    recent_start = laatste - timedelta(days=cfg.recente_prijs_dagen - 1)
    profiel_start = laatste - timedelta(days=cfg.profiel_dagen - 1)
    uit = pd.DataFrame(index=range(len(uren)))
    uren_arr = np.asarray(uren, dtype=int)

    if laatste in pivot_bekend.index:
        rij = pivot_bekend.loc[laatste]
        uit["prijs_laatste_dag_uur"] = rij.to_numpy()[uren_arr]
        uit["prijs_laatste_dag_gem"] = rij.mean()
        uit["prijs_laatste_dag_std"] = rij.std()
        uit["prijs_laatste_dag_min"] = rij.min()
        uit["prijs_laatste_dag_max"] = rij.max()
    else:
        for k in ("prijs_laatste_dag_uur", "prijs_laatste_dag_gem", "prijs_laatste_dag_std",
                  "prijs_laatste_dag_min", "prijs_laatste_dag_max"):
            uit[k] = np.nan

    # extra lags zoals in LEAR: zelfde uur op D en D-1 (de twee dagen voor de laatst bekende dag)
    for n in (1, 2):
        dag = laatste - timedelta(days=n)
        if dag in pivot_bekend.index:
            uit[f"prijs_dag_min{n}_uur"] = pivot_bekend.loc[dag].to_numpy()[uren_arr]
        else:
            uit[f"prijs_dag_min{n}_uur"] = np.nan

    recent = pivot_bekend.loc[(pivot_bekend.index >= recent_start) & (pivot_bekend.index <= laatste)]
    uit["prijs_recent_gem"] = recent.to_numpy().ravel().mean() if recent.size else np.nan
    uit["prijs_recent_std"] = np.nanstd(recent.to_numpy().ravel()) if recent.size else np.nan
    uit["prijs_recent_uur_gem"] = recent.mean(axis=0).to_numpy()[uren_arr] if len(recent) else np.nan

    profiel = pivot_bekend.loc[(pivot_bekend.index >= profiel_start) & (pivot_bekend.index <= laatste)]
    uit["prijs_profiel_uur_gem"] = profiel.mean(axis=0).to_numpy()[uren_arr] if len(profiel) else np.nan

    vorige_week = np.full(len(uren), np.nan)
    for i, (d, u) in enumerate(zip(doeldata, uren_arr)):
        dag = d - timedelta(days=7)
        if dag <= laatste and dag in pivot_bekend.index:
            vorige_week[i] = pivot_bekend.at[dag, u]
    uit["prijs_vorige_week_uur"] = vorige_week
    return uit


def bouw_features(prijzen: pd.DataFrame, weer: pd.DataFrame | None, cfg: Config, origins: list[date],
                  horizon_dagen: tuple[int, ...] | None = None,
                  weer_actueel: pd.DataFrame | None = None) -> pd.DataFrame:
    """Bouwt de featurematrix.

    prijzen: kolommen time_utc, prijs_eur_mwh (uurgemiddelden, alles wat we hebben; de functie filtert zelf op bekend_tot)
    weer: index time_utc, kolommen `<punt>__<var>_lead{N}` (previous runs). Mag None zijn.
    weer_actueel: index time_utc, kolommen `<punt>__<var>` (de actuele verwachting), gebruikt voor doeluren
        die niet in `weer` staan (de operationele run).
    """
    horizon = tuple(horizon_dagen or cfg.horizon_dagen)
    prijzen = prijzen.dropna(subset=[PRIJS]).sort_values("time_utc")
    prijs_serie = prijzen.set_index("time_utc")[PRIJS]
    pivot = prijs_pivot(prijzen)
    lead_maps = {k: weer_kolommen_voor_lead(weer.columns, k) for k in horizon} if weer is not None else {}

    delen = []
    for origin in origins:
        grens = bekend_tot(origin)
        cutoff = publication_cutoff(origin, cfg.publicatie_uur_lokaal)
        pivot_bekend = pivot.loc[pivot.index <= origin + timedelta(days=1)]
        for k in horizon:
            doeldag = origin + timedelta(days=k)
            uren_utc = local_hour_range(doeldag)
            kal = kalender_features(uren_utc)
            rijen = pd.DataFrame({
                "origin": pd.Timestamp(origin),
                "time_utc": uren_utc,
                "horizon_dag": k,
                "horizon_uren": ((uren_utc - cutoff) / pd.Timedelta(hours=1)).astype(float),
                "datum_lokaal": kal["datum_lokaal"].to_numpy(),
            })
            for kol in KALENDER:
                rijen[kol] = kal[kol].to_numpy()

            # weer: lead k uit previous runs; anders de actuele verwachting
            w = None
            if weer is not None and lead_maps.get(k):
                w = weer.reindex(uren_utc)[list(lead_maps[k])].rename(columns=lead_maps[k])
            if weer_actueel is not None:
                wa = weer_actueel.reindex(uren_utc)
                w = wa if w is None else w.fillna(wa)
            if w is not None:
                w = w.reset_index(drop=True)
                rijen = pd.concat([rijen, w, weer_aggregaten(w, cfg)], axis=1)

            pf = _prijsfeatures_voor_origin(pivot_bekend, origin, pd.Index(kal["datum_lokaal"]),
                                            pd.Index(kal["uur_lokaal"]), cfg)
            rijen = pd.concat([rijen, pf], axis=1)
            assert (rijen["time_utc"] >= grens).all(), "doeluren moeten na het bekende venster liggen"
            rijen[DOEL] = prijs_serie.reindex(uren_utc).to_numpy()
            delen.append(rijen)
    if not delen:
        return pd.DataFrame()
    df = pd.concat(delen, ignore_index=True)
    # daggemiddelden van het weer op de doeldag (zelfde origin + horizon)
    for kol in ("wind_zee_gem", "wind_land_gem", "wind_buitenland_gem", "straling_gem", "temp_gem"):
        if kol in df.columns:
            df[f"{kol}_dag"] = df.groupby(["origin", "horizon_dag"])[kol].transform("mean")
    # interacties die de dataverkenning als sterkste samenspel aanwijst (vooral voor het lineaire model)
    if "straling_gem" in df.columns:
        middag = df["uur_lokaal"].between(10, 16).astype(float)
        df["zon_middag"] = df["straling_gem"] * middag
        df["zon_vrije_dag"] = df["straling_gem"] * df["is_vrije_dag"].astype(float)
    if "wind_zee_vermogen" in df.columns:
        df["wind_vrije_dag"] = df["wind_zee_vermogen"] * df["is_vrije_dag"].astype(float)
    return df


def feature_kolommen(df: pd.DataFrame) -> list[str]:
    """Kolommen die een model mag gebruiken: alles behalve meta, doel en niet-numerieke kolommen."""
    verboden = set(META) | {DOEL}
    return [c for c in df.columns if c not in verboden and pd.api.types.is_numeric_dtype(df[c])]


def origins_in_bereik(start: date, einde: date) -> list[date]:
    n = (einde - start).days
    return [start + timedelta(days=i) for i in range(n + 1)]
