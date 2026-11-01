"""Foutmaten. Alles in EUR/MWh tenzij anders vermeld."""

from __future__ import annotations

import numpy as np
import pandas as pd


def mae(y, p) -> float:
    y, p = np.asarray(y, float), np.asarray(p, float)
    ok = ~(np.isnan(y) | np.isnan(p))
    return float(np.mean(np.abs(y[ok] - p[ok]))) if ok.any() else float("nan")


def rmse(y, p) -> float:
    y, p = np.asarray(y, float), np.asarray(p, float)
    ok = ~(np.isnan(y) | np.isnan(p))
    return float(np.sqrt(np.mean((y[ok] - p[ok]) ** 2))) if ok.any() else float("nan")


def pinball(y, p, q: float) -> float:
    """Pinball-verlies voor kwantiel q. Voor q = 0.5 is dit MAE / 2."""
    y, p = np.asarray(y, float), np.asarray(p, float)
    ok = ~(np.isnan(y) | np.isnan(p))
    d = y[ok] - p[ok]
    return float(np.mean(np.maximum(q * d, (q - 1) * d))) if ok.any() else float("nan")


def dekking(y, lo, hi) -> float:
    y, lo, hi = (np.asarray(a, float) for a in (y, lo, hi))
    ok = ~(np.isnan(y) | np.isnan(lo) | np.isnan(hi))
    return float(np.mean((y[ok] >= lo[ok]) & (y[ok] <= hi[ok]))) if ok.any() else float("nan")


def breedte(lo, hi) -> float:
    lo, hi = np.asarray(lo, float), np.asarray(hi, float)
    ok = ~(np.isnan(lo) | np.isnan(hi))
    return float(np.mean(hi[ok] - lo[ok])) if ok.any() else float("nan")


def samenvatting(voorsp: pd.DataFrame, lo: str = "p10", hi: str = "p90") -> pd.DataFrame:
    """Per methode en horizon: n, MAE, RMSE, pinball P10/P50/P90, dekking en breedte van het 80%-interval."""
    rijen = []
    for (methode, k), g in voorsp.groupby(["methode", "horizon_dag"]):
        g = g.dropna(subset=["doel"])
        rijen.append({
            "methode": methode, "horizon_dag": int(k), "n": len(g),
            "mae": mae(g["doel"], g["p50"]), "rmse": rmse(g["doel"], g["p50"]),
            "pinball_p10": pinball(g["doel"], g[lo], 0.1),
            "pinball_p50": pinball(g["doel"], g["p50"], 0.5),
            "pinball_p90": pinball(g["doel"], g[hi], 0.9),
            "dekking80": dekking(g["doel"], g[lo], g[hi]),
            "breedte80": breedte(g[lo], g[hi]),
        })
    return pd.DataFrame(rijen).sort_values(["horizon_dag", "mae"]).reset_index(drop=True)
