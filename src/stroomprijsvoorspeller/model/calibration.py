"""Kalibratie van het 80%-interval met conformal prediction (conformalized quantile regression, CQR).

Score per bekende uitkomst: s = max(p10 - y, y - p90). Positief als y buiten het interval valt.
Correctie q = het (1 - alpha)(1 + 1/n)-kwantiel van de scores in het kalibratievenster.
Nieuw interval: [p10 - q, p90 + q]. q kan negatief zijn: dan was het interval te breed en wordt het smaller.

Voor baselines (p10 = p50 = p90) wordt dit een symmetrisch interval van residu-kwantielen rond de puntvoorspelling.

Lekkage-regel: voor voorspelmoment D tellen alleen uitkomsten mee van doeluren die op D al bekend waren
(time_utc < bekend_tot(D)), uit voorspelmomenten in de `venster_dagen` dagen voor D.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

from stroomprijsvoorspeller.processing.features import bekend_tot

MIN_SCORES = 48  # minstens twee dagen aan bekende uitkomsten voordat we corrigeren


def conformal_score(y, lo, hi) -> np.ndarray:
    y, lo, hi = (np.asarray(a, dtype=float) for a in (y, lo, hi))
    return np.maximum(lo - y, y - hi)


def conformal_correctie(scores, alpha: float = 0.2) -> float:
    s = np.asarray(scores, dtype=float)
    s = s[~np.isnan(s)]
    n = len(s)
    if n == 0:
        return 0.0
    niveau = min(1.0, np.ceil((n + 1) * (1 - alpha)) / n)
    return float(np.quantile(s, niveau, method="higher"))


def dekking(y, lo, hi) -> float:
    y, lo, hi = (np.asarray(a, dtype=float) for a in (y, lo, hi))
    ok = ~np.isnan(y)
    if ok.sum() == 0:
        return float("nan")
    return float(((y[ok] >= lo[ok]) & (y[ok] <= hi[ok])).mean())


def pas_conformal_toe(voorsp: pd.DataFrame, venster_dagen: int, alpha: float = 0.2,
                      min_scores: int = MIN_SCORES) -> pd.DataFrame:
    """Voegt p10_kal, p90_kal en conformal_q toe. Per (methode, horizon_dag) en per voorspelmoment, in tijdvolgorde.

    voorsp: kolommen origin (Timestamp), time_utc, horizon_dag, methode, p10, p50, p90, doel.
    """
    uit = voorsp.copy()
    uit["conformal_q"] = 0.0
    uit["p10_kal"] = uit["p10"]
    uit["p90_kal"] = uit["p90"]
    score = conformal_score(uit["doel"], uit["p10"], uit["p90"])
    venster = pd.Timedelta(days=venster_dagen)

    for idx in uit.groupby(["methode", "horizon_dag"]).groups.values():
        g = uit.loc[idx]
        origins = pd.to_datetime(g["origin"]).to_numpy()
        tijden = pd.DatetimeIndex(g["time_utc"]).tz_convert("UTC").tz_localize(None).to_numpy()
        sc = score[uit.index.get_indexer(idx)]
        for D in np.unique(origins):
            D_ts = pd.Timestamp(D)
            grens = bekend_tot(D_ts.date()).tz_convert("UTC").tz_localize(None).to_datetime64()
            mask = (origins >= (D_ts - venster).to_datetime64()) & (origins < D_ts.to_datetime64()) \
                & (tijden < grens) & ~np.isnan(sc)
            if mask.sum() < min_scores:
                continue
            q = conformal_correctie(sc[mask], alpha)
            doel_idx = idx[origins == D]
            uit.loc[doel_idx, "conformal_q"] = q
            uit.loc[doel_idx, "p10_kal"] = uit.loc[doel_idx, "p10"] - q
            uit.loc[doel_idx, "p90_kal"] = uit.loc[doel_idx, "p90"] + q
    # interval mag niet kruisen met de mediaan
    uit["p10_kal"] = np.minimum(uit["p10_kal"], uit["p50"])
    uit["p90_kal"] = np.maximum(uit["p90_kal"], uit["p50"])
    return uit
