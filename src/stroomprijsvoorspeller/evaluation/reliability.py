"""Betrouwbaarheidsindicator per dag (besluit 34).

Twee ingrediënten:
1. Vaardigheid op de horizon: rMAE van het model t.o.v. het 4-weeks profiel over de laatste `dagen` bekende dagen.
   hoog  als rMAE < DREMPEL_HOOG, redelijk als rMAE < DREMPEL_REDELIJK, anders laag.
2. Scherpte van de dag: gekalibreerde intervalbreedte gedeeld door het absolute P50-niveau van die dag.
   Is die verhouding groter dan BAND_VAAG, dan één niveau omlaag.

De drempels zijn geijkt op de backtest (zie reports/backtest.md, sectie betrouwbaarheid).
"""

from __future__ import annotations

import pandas as pd

from stroomprijsvoorspeller.evaluation.metrics import mae

NIVEAUS = ("hoog", "redelijk", "laag")
DREMPEL_HOOG = 0.80
DREMPEL_REDELIJK = 0.88
BAND_VAAG = 1.0
MIN_DAGEN = 10


def rmae_per_horizon(voorsp: pd.DataFrame, methode: str, referentie: str = "profiel_4w",
                     tot: pd.Timestamp | None = None, dagen: int = 30) -> dict[int, float]:
    """rMAE per horizon over de voorspelmomenten in de `dagen` dagen voor `tot`, alleen bekende uitkomsten."""
    v = voorsp.dropna(subset=["doel"])
    if tot is not None:
        v = v[(v["origin"] < pd.Timestamp(tot)) & (v["origin"] >= pd.Timestamp(tot) - pd.Timedelta(days=dagen))]
    uit = {}
    for k, g in v.groupby("horizon_dag"):
        m = g[g["methode"] == methode]
        r = g[g["methode"] == referentie]
        if m["origin"].nunique() < MIN_DAGEN or r.empty:
            continue
        uit[int(k)] = mae(m["doel"], m["p50"]) / mae(r["doel"], r["p50"])
    return uit


def niveau_uit_rmae(rmae: float | None) -> str:
    if rmae is None or pd.isna(rmae):
        return "laag"
    if rmae < DREMPEL_HOOG:
        return "hoog"
    if rmae < DREMPEL_REDELIJK:
        return "redelijk"
    return "laag"


def verlaag(niveau: str) -> str:
    i = NIVEAUS.index(niveau)
    return NIVEAUS[min(i + 1, len(NIVEAUS) - 1)]


def betrouwbaarheid(rmae: float | None, band_breedte: float, p50_niveau: float) -> str:
    """Niveau voor één dag: vaardigheid op de horizon, één stap omlaag bij een vage band."""
    niveau = niveau_uit_rmae(rmae)
    if p50_niveau and abs(p50_niveau) > 1e-9 and band_breedte / abs(p50_niveau) > BAND_VAAG:
        niveau = verlaag(niveau)
    return niveau


def verdeling_niveaus(voorsp: pd.DataFrame, methode: str, referentie: str = "profiel_4w", dagen: int = 30) -> pd.DataFrame:
    """Voor het ijken: per voorspelmoment en horizon het rMAE van de 30 dagen ervoor en het niveau. Maandelijkse steekproef."""
    rijen = []
    origins = sorted(voorsp["origin"].unique())
    for D in origins[::7]:
        r = rmae_per_horizon(voorsp, methode, referentie, tot=pd.Timestamp(D), dagen=dagen)
        for k, waarde in r.items():
            rijen.append({"origin": pd.Timestamp(D), "horizon_dag": k, "rmae_30d": waarde, "niveau": niveau_uit_rmae(waarde)})
    return pd.DataFrame(rijen)
