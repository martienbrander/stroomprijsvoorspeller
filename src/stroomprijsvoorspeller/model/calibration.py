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


def pas_aci_toe(voorsp: pd.DataFrame, venster_dagen: int, gamma: float = 0.02, alpha: float = 0.2,
                min_scores: int = MIN_SCORES, alpha_min: float = 0.01, alpha_max: float = 0.5) -> pd.DataFrame:
    """Adaptive Conformal Inference (Gibbs en Candès 2021) bovenop de rolling conformal-correctie.

    Het foutniveau alpha_t wordt per (methode, horizon) online bijgestuurd: alpha_{t+1} = alpha_t + gamma (alpha - err_t),
    waarbij err_t het aandeel uren buiten het interval is van het meest recente voorspelmoment waarvan de uitkomsten
    bekend zijn. Bij structurele onderdekking (err > alpha) daalt alpha_t en wordt het interval breder.
    Voegt p10_aci, p90_aci en alpha_aci toe.
    """
    uit = voorsp.copy()
    uit["alpha_aci"] = alpha
    uit["p10_aci"] = uit["p10"]
    uit["p90_aci"] = uit["p90"]
    score = conformal_score(uit["doel"], uit["p10"], uit["p90"])
    venster = pd.Timedelta(days=venster_dagen)

    for idx in uit.groupby(["methode", "horizon_dag"]).groups.values():
        g = uit.loc[idx]
        origins = pd.to_datetime(g["origin"]).to_numpy()
        tijden = pd.DatetimeIndex(g["time_utc"]).tz_convert("UTC").tz_localize(None).to_numpy()
        sc = score[uit.index.get_indexer(idx)]
        pos = {D: np.flatnonzero(origins == D) for D in np.unique(origins)}
        q_per_origin: dict = {}
        a_t = alpha
        verwerkt: set = set()
        for D in sorted(pos):
            D_ts = pd.Timestamp(D)
            grens = bekend_tot(D_ts.date()).tz_convert("UTC").tz_localize(None).to_datetime64()
            # update alpha met alle eerdere voorspelmomenten waarvan nu alle uren bekend zijn
            for D2 in sorted(pos):
                if D2 >= D or D2 in verwerkt or D2 not in q_per_origin:
                    continue
                rows = pos[D2]
                if not (tijden[rows] < grens).all():
                    continue
                err = float(np.nanmean(sc[rows] > q_per_origin[D2]))
                a_t = float(np.clip(a_t + gamma * (alpha - err), alpha_min, alpha_max))
                verwerkt.add(D2)
            mask = (origins >= (D_ts - venster).to_datetime64()) & (origins < D_ts.to_datetime64()) \
                & (tijden < grens) & ~np.isnan(sc)
            if mask.sum() < min_scores:
                q = 0.0
            else:
                q = conformal_correctie(sc[mask], a_t)
            q_per_origin[D] = q
            rows = idx[pos[D]]
            uit.loc[rows, "alpha_aci"] = a_t
            uit.loc[rows, "p10_aci"] = uit.loc[rows, "p10"] - q
            uit.loc[rows, "p90_aci"] = uit.loc[rows, "p90"] + q
    uit["p10_aci"] = np.minimum(uit["p10_aci"], uit["p50"])
    uit["p90_aci"] = np.maximum(uit["p90_aci"], uit["p50"])
    return uit
