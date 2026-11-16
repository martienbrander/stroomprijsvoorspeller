"""Kalibratie van het 80%-interval met conformal prediction (conformalized quantile regression, CQR).

Score per bekende uitkomst: s = max(p10 - y, y - p90). Positief als y buiten het interval valt.
Correctie q = het (1 - alpha)(1 + 1/n)-kwantiel van de scores in het kalibratievenster.
Nieuw interval: [p10 - q, p90 + q]. q kan negatief zijn: dan was het interval te breed en wordt het smaller.

Voor baselines (p10 = p50 = p90) wordt dit een symmetrisch interval van residu-kwantielen rond de puntvoorspelling.

Lekkage-regel: voor voorspelmoment D tellen alleen uitkomsten mee van doeluren die op D al bekend waren
(time_utc < bekend_tot(D)), uit voorspelmomenten in de `venster_dagen` dagen voor D.

Beide `pas_..._toe`-functies rekenen per (methode, horizon_dag) op numpy-arrays en schrijven de uitkomst pas aan het
eind in het frame: toewijzen per voorspelmoment met `.loc` maakte de kalibratie de traagste stap van de dagelijkse run.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np
import pandas as pd

from stroomprijsvoorspeller.processing.features import bekend_tot

MIN_SCORES = 48   # minstens twee dagen aan bekende uitkomsten voordat we corrigeren
ACI_GAMMA = 0.02  # leersnelheid van de online bijsturing (besluit 41)


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


@lru_cache(maxsize=4096)
def _bekend_tot_utc(origin: np.datetime64) -> np.datetime64:
    """`bekend_tot` van een voorspelmoment als tijdzoneloze UTC-tijd, vergelijkbaar met de arrays hieronder."""
    return bekend_tot(pd.Timestamp(origin).date()).tz_convert("UTC").tz_localize(None).to_datetime64()


def _tijdassen(voorsp: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Voorspelmoment en doeluur per rij als numpy-arrays (doeluur in UTC, zonder tijdzone)."""
    origins = pd.to_datetime(voorsp["origin"]).to_numpy()
    tijden = pd.DatetimeIndex(voorsp["time_utc"]).tz_convert("UTC").tz_localize(None).to_numpy()
    return origins, tijden


def _kalibratiescores(origins: np.ndarray, tijden: np.ndarray, scores: np.ndarray, origin: np.datetime64,
                      venster: np.timedelta64) -> np.ndarray:
    """Scores die op voorspelmoment `origin` mogen meetellen: uit voorspelmomenten in het venster ervoor, en alleen
    van doeluren waarvan de prijs op dat moment al bekend was (de lekkage-regel)."""
    telt_mee = (origins >= origin - venster) & (origins < origin) & (tijden < _bekend_tot_utc(origin)) & ~np.isnan(scores)
    return scores[telt_mee]


def pas_conformal_toe(voorsp: pd.DataFrame, venster_dagen: int, alpha: float = 0.2,
                      min_scores: int = MIN_SCORES) -> pd.DataFrame:
    """Voegt p10_kal, p90_kal en conformal_q toe. Per (methode, horizon_dag) en per voorspelmoment, in tijdvolgorde.

    voorsp: kolommen origin (Timestamp), time_utc, horizon_dag, methode, p10, p50, p90, doel.
    """
    uit = voorsp.copy()
    alle_scores = conformal_score(uit["doel"], uit["p10"], uit["p90"])
    alle_origins, alle_tijden = _tijdassen(uit)
    venster = np.timedelta64(venster_dagen, "D")
    q = np.zeros(len(uit))

    for rijen in uit.groupby(["methode", "horizon_dag"]).indices.values():
        origins, tijden, scores = alle_origins[rijen], alle_tijden[rijen], alle_scores[rijen]
        for origin in np.unique(origins):
            bekend = _kalibratiescores(origins, tijden, scores, origin, venster)
            if len(bekend) >= min_scores:
                q[rijen[origins == origin]] = conformal_correctie(bekend, alpha)

    uit["conformal_q"] = q
    # het interval mag de mediaan niet kruisen
    uit["p10_kal"] = np.minimum(uit["p10"] - q, uit["p50"])
    uit["p90_kal"] = np.maximum(uit["p90"] + q, uit["p50"])
    return uit


def pas_aci_toe(voorsp: pd.DataFrame, venster_dagen: int, gamma: float = ACI_GAMMA, alpha: float = 0.2,
                min_scores: int = MIN_SCORES, alpha_min: float = 0.01, alpha_max: float = 0.5) -> pd.DataFrame:
    """Adaptive Conformal Inference (Gibbs en Candès 2021) bovenop de rolling conformal-correctie.

    Het foutniveau alpha_t wordt per (methode, horizon) online bijgestuurd: alpha_{t+1} = alpha_t + gamma (alpha - err_t),
    waarbij err_t het aandeel uren buiten het interval is van het meest recente voorspelmoment waarvan de uitkomsten
    bekend zijn. Bij structurele onderdekking (err > alpha) daalt alpha_t en wordt het interval breder.
    Voegt p10_aci, p90_aci en alpha_aci toe.
    """
    uit = voorsp.copy()
    alle_scores = conformal_score(uit["doel"], uit["p10"], uit["p90"])
    alle_origins, alle_tijden = _tijdassen(uit)
    venster = np.timedelta64(venster_dagen, "D")
    q = np.zeros(len(uit))
    alpha_per_rij = np.full(len(uit), alpha)

    for rijen in uit.groupby(["methode", "horizon_dag"]).indices.values():
        origins, tijden, scores = alle_origins[rijen], alle_tijden[rijen], alle_scores[rijen]
        alpha_t = alpha
        # eerdere voorspelmomenten waarvan de uitkomst nog niet in alpha_t verwerkt is: (positie in de groep, eigen q)
        wachtend: list[tuple[np.ndarray, float]] = []
        for origin in np.unique(origins):
            grens = _bekend_tot_utc(origin)
            # stuur alpha bij met elk eerder voorspelmoment waarvan nu alle uren bekend zijn, oudste eerst
            nog_wachtend = []
            for eerder, q_eerder in wachtend:
                if (tijden[eerder] < grens).all():
                    fout = float(np.nanmean(scores[eerder] > q_eerder))
                    alpha_t = float(np.clip(alpha_t + gamma * (alpha - fout), alpha_min, alpha_max))
                else:
                    nog_wachtend.append((eerder, q_eerder))
            wachtend = nog_wachtend

            bekend = _kalibratiescores(origins, tijden, scores, origin, venster)
            q_origin = conformal_correctie(bekend, alpha_t) if len(bekend) >= min_scores else 0.0
            eigen = np.flatnonzero(origins == origin)
            q[rijen[eigen]] = q_origin
            alpha_per_rij[rijen[eigen]] = alpha_t
            wachtend.append((eigen, q_origin))

    uit["alpha_aci"] = alpha_per_rij
    uit["p10_aci"] = np.minimum(uit["p10"] - q, uit["p50"])
    uit["p90_aci"] = np.maximum(uit["p90"] + q, uit["p50"])
    return uit
