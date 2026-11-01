"""Rolling-origin evaluatie (pseudo-out-of-sample, zoals in de econometrie).

Voor elk voorspelmoment D (13:00 lokaal) wordt elk model geschat op een rolling venster van voorspelmomenten
vóór D, uitsluitend met doeluren die op D al bekend waren, en voorspelt het alle horizonten voor D.
Hertrainen gebeurt elke `hertrain_elke_dagen` dagen (de featurematrix beweegt wel elke dag mee).
"""

from __future__ import annotations

import logging
import time
from datetime import date

import pandas as pd

from stroomprijsvoorspeller.config import Config
from stroomprijsvoorspeller.model.baselines import baseline_voorspelling, is_baseline
from stroomprijsvoorspeller.model.calibration import pas_conformal_toe
from stroomprijsvoorspeller.model.quantile_models import maak_model, sorteer_kwantielen
from stroomprijsvoorspeller.processing.features import DOEL, bekend_tot, feature_kolommen

log = logging.getLogger(__name__)

UITVOER_KOLOMMEN = ["origin", "time_utc", "horizon_dag", "methode", "p10", "p50", "p90", DOEL]
MIN_TRAINRIJEN = 24 * 14


def trainset(features: pd.DataFrame, origin: date, venster_dagen: int) -> pd.DataFrame:
    """Rijen van voorspelmomenten in [D - venster, D-1] waarvan het doeluur op D bekend is."""
    D = pd.Timestamp(origin)
    start = D - pd.Timedelta(days=venster_dagen)
    grens = bekend_tot(D.date())
    mask = (features["origin"] >= start) & (features["origin"] < D) & (features["time_utc"] < grens) \
        & features[DOEL].notna()
    return features.loc[mask]


def run_rolling(features: pd.DataFrame, cfg: Config, methoden: list[str], origins: list[date],
                hertrain_elke_dagen: int | None = None, venster_dagen: int | None = None,
                kalibreren: bool = True) -> pd.DataFrame:
    hertrain = hertrain_elke_dagen or cfg.hertrain_elke_dagen
    venster = venster_dagen or cfg.rolling_venster_dagen
    kolommen = feature_kolommen(features)
    # de combinatie middelt lineair en lightgbm; die twee worden dan altijd (ook) geschat, zonder dubbel werk
    te_schatten = [m for m in methoden if not is_baseline(m) and m != "combinatie"]
    if "combinatie" in methoden:
        te_schatten += [m for m in ("lineair", "lightgbm") if m not in te_schatten]
    modellen = {m: None for m in te_schatten}
    laatste_fit: pd.Timestamp | None = None
    uit = []
    t0 = time.time()

    for i, origin in enumerate(origins):
        D = pd.Timestamp(origin)
        test = features[features["origin"] == D]
        if test.empty:
            continue
        if modellen and (laatste_fit is None or (D - laatste_fit).days >= hertrain):
            train = trainset(features, origin, venster)
            if len(train) < MIN_TRAINRIJEN:
                log.info("%s: te weinig trainingsdata (%d rijen), overgeslagen", origin, len(train))
                continue
            X, y = train[kolommen], train[DOEL]
            for naam in modellen:
                modellen[naam] = maak_model(naam, cfg.kwantielen, cfg.lightgbm_params).fit(X, y)
            laatste_fit = D
            log.info("%s: hertraind op %d rijen (%d kolommen), %.0fs verstreken", origin, len(train),
                     len(kolommen), time.time() - t0)
        if modellen and laatste_fit is None:
            continue
        preds = {m: modellen[m].predict(test[kolommen]) for m in modellen}
        for naam in methoden:
            if is_baseline(naam):
                pred = baseline_voorspelling(test, naam)
            elif naam == "combinatie":
                pred = sorteer_kwantielen((preds["lineair"] + preds["lightgbm"]) / 2)
            else:
                pred = preds[naam]
            rijen = test[["origin", "time_utc", "horizon_dag", DOEL]].copy()
            rijen["methode"] = naam
            for k in ("p10", "p50", "p90"):
                rijen[k] = pred[k].to_numpy()
            uit.append(rijen[UITVOER_KOLOMMEN])
    if not uit:
        return pd.DataFrame(columns=UITVOER_KOLOMMEN)
    voorsp = pd.concat(uit, ignore_index=True)
    if kalibreren:
        voorsp = pas_conformal_toe(voorsp, cfg.kalibratie_venster_dagen)
    return voorsp
