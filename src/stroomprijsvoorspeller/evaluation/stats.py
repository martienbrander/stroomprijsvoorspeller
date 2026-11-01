"""Statistische toetsen: Diebold-Mariano op dagelijkse verliezen, met HAC-correctie (Newey-West)."""

from __future__ import annotations

import numpy as np
import pandas as pd
from scipy import stats as sps


def newey_west_variantie(d: np.ndarray, lags: int | None = None) -> float:
    """HAC-variantie van het gemiddelde van d (Bartlett-gewichten)."""
    d = np.asarray(d, dtype=float)
    n = len(d)
    if lags is None:
        lags = int(np.floor(4 * (n / 100) ** (2 / 9)))
    dc = d - d.mean()
    s = np.dot(dc, dc) / n
    for lag in range(1, min(lags, n - 1) + 1):
        w = 1 - lag / (lags + 1)
        s += 2 * w * np.dot(dc[lag:], dc[:-lag]) / n
    return float(s / n)


def diebold_mariano(verlies_a, verlies_b, lags: int | None = None) -> tuple[float, float]:
    """DM-toets op d = verlies_a - verlies_b (per dag). Retourneert (statistiek, eenzijdige p-waarde voor 'a beter dan b').

    Negatieve statistiek = a heeft lager verlies. Kleine p = a is significant beter.
    """
    a, b = np.asarray(verlies_a, float), np.asarray(verlies_b, float)
    ok = ~(np.isnan(a) | np.isnan(b))
    d = a[ok] - b[ok]
    if len(d) < 10:
        return float("nan"), float("nan")
    var = newey_west_variantie(d, lags)
    if var <= 0:
        return float("nan"), float("nan")
    stat = d.mean() / np.sqrt(var)
    p = float(sps.norm.cdf(stat))
    return float(stat), p


def dagelijks_verlies(voorsp: pd.DataFrame, kolom: str = "p50") -> pd.DataFrame:
    """Gemiddelde absolute fout per (methode, horizon_dag, origin)."""
    v = voorsp.dropna(subset=["doel"]).copy()
    v["fout"] = (v["doel"] - v[kolom]).abs()
    return v.groupby(["methode", "horizon_dag", "origin"])["fout"].mean().reset_index()


def dm_tabel(voorsp: pd.DataFrame, referentie: str = "profiel_4w") -> pd.DataFrame:
    """Per methode en horizon: DM-statistiek en p-waarde dat de methode beter is dan de referentie (op MAE per dag)."""
    dv = dagelijks_verlies(voorsp)
    rijen = []
    for k, g in dv.groupby("horizon_dag"):
        ref = g[g["methode"] == referentie].set_index("origin")["fout"]
        for methode, gm in g.groupby("methode"):
            if methode == referentie:
                continue
            m = gm.set_index("origin")["fout"]
            samen = pd.concat([m, ref], axis=1, join="inner", keys=["m", "ref"])
            stat, p = diebold_mariano(samen["m"], samen["ref"])
            rijen.append({"methode": methode, "horizon_dag": int(k), "n_dagen": len(samen),
                          "mae_methode": samen["m"].mean(), "mae_referentie": samen["ref"].mean(),
                          "dm_stat": stat, "p_beter": p})
    return pd.DataFrame(rijen).sort_values(["horizon_dag", "dm_stat"]).reset_index(drop=True)
