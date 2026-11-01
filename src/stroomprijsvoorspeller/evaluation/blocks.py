"""Praktijkmaat: kiest het model het goedkoopste aaneengesloten blok van N uur van de dag?

Per (methode, voorspelmoment, doeldag) bepalen we het blok met de laagste voorspelde P50 en vergelijken de
werkelijke kosten van dat blok met het werkelijk goedkoopste blok van die dag.

- exact:      zelfde beginuur
- binnen_tol: werkelijke kosten van het gekozen blok <= beste kosten + tolerantie, met tolerantie = 10% van de
              absolute werkelijke daggemiddelde prijs (niet 10% van het blok zelf, want dat kan rond nul of negatief zijn)
- meerkosten: werkelijke gemiddelde prijs in het gekozen blok minus die in het beste blok, in EUR/MWh (0 = perfect)
- dagdeel_juist: valt het gekozen blok in hetzelfde dagdeel (nacht 0-6, ochtend 6-12, middag 12-18, avond 18-24)
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from stroomprijsvoorspeller.timeutil import to_local

DAGDELEN = ["nacht", "ochtend", "middag", "avond"]


def goedkoopste_blok(prijzen: np.ndarray, lengte: int = 3) -> tuple[int, float]:
    """Startindex en gemiddelde prijs van het goedkoopste aaneengesloten blok. NaN-uren maken een blok ongeldig."""
    p = np.asarray(prijzen, dtype=float)
    if len(p) < lengte:
        return 0, float("nan")
    # glijdend gemiddelde met NaN-propagatie
    gem = np.array([np.mean(p[i:i + lengte]) for i in range(len(p) - lengte + 1)])
    if np.all(np.isnan(gem)):
        return 0, float("nan")
    i = int(np.nanargmin(gem))
    return i, float(gem[i])


def dagdeel(uur_lokaal: int) -> str:
    return DAGDELEN[min(int(uur_lokaal) // 6, 3)]


def blok_scores(voorsp: pd.DataFrame, lengte: int = 3, tolerantie: float = 0.10, prijs_kolom: str = "p50") -> pd.DataFrame:
    """Eén rij per (methode, origin, horizon_dag)."""
    v = voorsp.dropna(subset=["doel"]).sort_values(["methode", "origin", "horizon_dag", "time_utc"])
    rijen = []
    for (methode, origin, k), g in v.groupby(["methode", "origin", "horizon_dag"], sort=False):
        if len(g) < lengte or g["doel"].isna().any():
            continue
        echt = g["doel"].to_numpy()
        voorspeld = g[prijs_kolom].to_numpy()
        uren = to_local(pd.DatetimeIndex(g["time_utc"])).hour
        i_v, _ = goedkoopste_blok(voorspeld, lengte)
        i_e, kosten_beste = goedkoopste_blok(echt, lengte)
        kosten_gekozen = float(np.mean(echt[i_v:i_v + lengte]))
        daggem = float(np.mean(echt))
        rijen.append({
            "methode": methode, "origin": origin, "horizon_dag": int(k),
            "start_voorspeld": int(uren[i_v]), "start_echt": int(uren[i_e]),
            "kosten_gekozen": kosten_gekozen, "kosten_beste": kosten_beste, "daggemiddelde": daggem,
            "meerkosten": kosten_gekozen - kosten_beste,
            "exact": i_v == i_e,
            "binnen_tol": kosten_gekozen <= kosten_beste + tolerantie * abs(daggem),
            "dagdeel_juist": dagdeel(uren[i_v]) == dagdeel(uren[i_e]),
            "besparing_gekozen": daggem - kosten_gekozen,     # t.o.v. gelijk verdeeld verbruik
            "besparing_beste": daggem - kosten_beste,
        })
    return pd.DataFrame(rijen)


def blok_samenvatting(scores: pd.DataFrame) -> pd.DataFrame:
    """Per methode en horizon: aandeel exact, aandeel binnen tolerantie, gemiddelde en mediane meerkosten."""
    if scores.empty:
        return pd.DataFrame()
    g = scores.groupby(["methode", "horizon_dag"])
    uit = pd.DataFrame({
        "n_dagen": g.size(),
        "exact": g["exact"].mean(),
        "binnen_10pct": g["binnen_tol"].mean(),
        "dagdeel_juist": g["dagdeel_juist"].mean(),
        "meerkosten_gem": g["meerkosten"].mean(),
        "meerkosten_mediaan": g["meerkosten"].median(),
        "besparing_gekozen_gem": g["besparing_gekozen"].mean(),
        "besparing_beste_gem": g["besparing_beste"].mean(),
    }).reset_index()
    uit["aandeel_van_besparing"] = uit["besparing_gekozen_gem"] / uit["besparing_beste_gem"]
    return uit.sort_values(["horizon_dag", "meerkosten_gem"]).reset_index(drop=True)
