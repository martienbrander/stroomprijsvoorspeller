"""Rolling-origin evaluatie (pseudo-out-of-sample, zoals in de econometrie).

Voor elk voorspelmoment D (13:00 lokaal) wordt elk model geschat op een rolling venster van voorspelmomenten
vóór D, uitsluitend met doeluren die op D al bekend waren, en voorspelt het alle horizonten voor D.
Hertrainen gebeurt elke `hertrain_elke_dagen` dagen (de featurematrix beweegt wel elke dag mee).

Methodenamen:
- baselines: laatste_dag, vorige_week, profiel_4w
- modellen: lineair, lineair_ruw, lightgbm, lightgbm_asinh
- varianten: `<model>_w<N>` traint op een venster van N dagen (bijv. lightgbm_w90, lightgbm_w365);
             `<model>_hg` traint aparte modellen per horizongroep (dag 2 apart, dag 3+ samen)
- afgeleid:  combinatie = gemiddelde van lineair en lightgbm; lightgbm_ens = gemiddelde van lightgbm_w90,
             lightgbm en lightgbm_w365 (middelen over trainingsvensters, zoals Hubicka e.a. aanbevelen)
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
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
HORIZONGROEPEN = ((2,), (3, 4, 5, 6, 7))
AFGELEID = {
    "combinatie": ("lineair", "lightgbm"),
    "lightgbm_ens": ("lightgbm_w90", "lightgbm", "lightgbm_w365"),
}
_SPEC = re.compile(r"^(lineair_ruw|lineair|lightgbm_asinh|lightgbm)(?:_w(\d+))?(_hg)?$")


@dataclass(frozen=True)
class Spec:
    naam: str
    basis: str
    venster: int | None          # None = venster uit config
    horizongroepen: bool = False


def parse_spec(naam: str) -> Spec:
    m = _SPEC.match(naam)
    if not m:
        raise KeyError(f"onbekende methode: {naam}")
    return Spec(naam, m.group(1), int(m.group(2)) if m.group(2) else None, bool(m.group(3)))


def trainset(features: pd.DataFrame, origin: date, venster_dagen: int) -> pd.DataFrame:
    """Rijen van voorspelmomenten in [D - venster, D-1] waarvan het doeluur op D bekend is."""
    D = pd.Timestamp(origin)
    start = D - pd.Timedelta(days=venster_dagen)
    grens = bekend_tot(D.date())
    mask = (features["origin"] >= start) & (features["origin"] < D) & (features["time_utc"] < grens) \
        & features[DOEL].notna()
    return features.loc[mask]


def _te_schatten(methoden: list[str]) -> list[Spec]:
    namen: list[str] = []
    for m in methoden:
        if is_baseline(m):
            continue
        for n in AFGELEID.get(m, (m,)):
            if n not in namen:
                namen.append(n)
    return [parse_spec(n) for n in namen]


class _Geschat:
    """Een geschat model: één model, of één per horizongroep."""

    def __init__(self, spec: Spec, cfg: Config, train: pd.DataFrame, kolommen: list[str]):
        self.spec = spec
        self.delen = {}
        groepen = HORIZONGROEPEN if spec.horizongroepen else (None,)
        for groep in groepen:
            deel = train if groep is None else train[train["horizon_dag"].isin(groep)]
            self.delen[groep] = maak_model(spec.basis, cfg.kwantielen, cfg.lightgbm_params).fit(deel[kolommen], deel[DOEL])

    def predict(self, test: pd.DataFrame, kolommen: list[str]) -> pd.DataFrame:
        if None in self.delen:
            return self.delen[None].predict(test[kolommen])
        delen = []
        for groep, model in self.delen.items():
            rijen = test[test["horizon_dag"].isin(groep)]
            if len(rijen):
                delen.append(model.predict(rijen[kolommen]))
        return pd.concat(delen).reindex(test.index)


def run_rolling(features: pd.DataFrame, cfg: Config, methoden: list[str], origins: list[date],
                hertrain_elke_dagen: int | None = None, venster_dagen: int | None = None,
                kalibreren: bool = True) -> pd.DataFrame:
    hertrain = hertrain_elke_dagen or cfg.hertrain_elke_dagen
    standaard_venster = venster_dagen or cfg.rolling_venster_dagen
    kolommen = feature_kolommen(features)
    specs = _te_schatten(methoden)
    modellen: dict[str, _Geschat | None] = {s.naam: None for s in specs}
    laatste_fit: pd.Timestamp | None = None
    uit = []
    t0 = time.time()

    for origin in origins:
        D = pd.Timestamp(origin)
        test = features[features["origin"] == D]
        if test.empty:
            continue
        if specs and (laatste_fit is None or (D - laatste_fit).days >= hertrain):
            trainsets = {}
            genoeg = True
            for spec in specs:
                v = spec.venster or standaard_venster
                if v not in trainsets:
                    trainsets[v] = trainset(features, origin, v)
                if len(trainsets[v]) < MIN_TRAINRIJEN:
                    genoeg = False
            if not genoeg:
                log.info("%s: te weinig trainingsdata, overgeslagen", origin)
                continue
            for spec in specs:
                modellen[spec.naam] = _Geschat(spec, cfg, trainsets[spec.venster or standaard_venster], kolommen)
            laatste_fit = D
            log.info("%s: hertraind (%s), %.0fs verstreken", origin,
                     ", ".join(f"{v}d: {len(t)} rijen" for v, t in sorted(trainsets.items())), time.time() - t0)
        if specs and laatste_fit is None:
            continue
        preds = {naam: model.predict(test, kolommen) for naam, model in modellen.items()}
        for naam in methoden:
            if is_baseline(naam):
                pred = baseline_voorspelling(test, naam)
            elif naam in AFGELEID:
                leden = [preds[n] for n in AFGELEID[naam]]
                pred = sorteer_kwantielen(sum(leden) / len(leden))
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
