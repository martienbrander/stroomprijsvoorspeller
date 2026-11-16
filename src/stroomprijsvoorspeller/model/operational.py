"""Operationeel trainen en voorspellen.

- train_en_bewaar:  schat het gekozen model op het rolling venster tot en met het voorspelmoment en bewaart het in
                    models/. De dagelijkse run gebruikt dit (pipeline/daily.py).
- voorspel:         het losse commando `epv predict`: voorspelt met het bewaarde model en kalibreert met de uitkomsten
                    van de backtest. De dagelijkse run kalibreert zelf, op het runarchief (besluit 51).
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import joblib
import pandas as pd

from stroomprijsvoorspeller.config import Config
from stroomprijsvoorspeller.evaluation import compare
from stroomprijsvoorspeller.evaluation.rolling import Geschat, parse_spec, trainset
from stroomprijsvoorspeller.model.calibration import conformal_correctie, conformal_score
from stroomprijsvoorspeller.processing.features import DOEL, bekend_tot, bouw_features, feature_kolommen
from stroomprijsvoorspeller.sources import open_meteo
from stroomprijsvoorspeller.timeutil import TZ, utc_now

log = logging.getLogger(__name__)

MODEL_BESTAND = "model_{methode}.joblib"
KWANTIELEN = ("p10", "p50", "p90")


def laad_actuele_verwachting(cfg: Config) -> tuple[pd.DataFrame, pd.Timestamp]:
    """Laatste uitgegeven weersverwachting per punt, als frame met index time_utc en kolommen `<punt>__<var>`,
    plus het (laatste) uitgiftemoment over alle punten."""
    delen = []
    uitgegeven = []
    for punt in cfg.weerpunten:
        pad = open_meteo.forecast_bestand(cfg.raw_dir, punt.naam)
        if not pad.exists():
            raise FileNotFoundError(f"geen actuele verwachting voor {punt.naam}; draai `epv fetch`")
        df = pd.read_parquet(pad)
        df["time_utc"] = pd.to_datetime(df["time_utc"], utc=True)
        df["uitgegeven_utc"] = pd.to_datetime(df["uitgegeven_utc"], utc=True)
        laatste_uitgifte = df["uitgegeven_utc"].max()
        w = df[df["uitgegeven_utc"] == laatste_uitgifte].set_index("time_utc")[list(cfg.weer_variabelen)]
        w.columns = [f"{punt.naam}__{c}" for c in w.columns]
        delen.append(w)
        uitgegeven.append(laatste_uitgifte)
    return pd.concat(delen, axis=1).sort_index(), max(uitgegeven)


def laad_weer_actueel(cfg: Config) -> pd.DataFrame:
    """Alleen het weerframe van `laad_actuele_verwachting`."""
    return laad_actuele_verwachting(cfg)[0]


def vandaag_lokaal() -> date:
    return utc_now().tz_convert(TZ).date()


def model_pad(cfg: Config, methode: str) -> Path:
    return cfg.root / "models" / MODEL_BESTAND.format(methode=methode)


def train_en_bewaar(cfg: Config, methode: str | None = None, origin: date | None = None) -> Path:
    """Traint `methode` op het venster vóór `origin` en bewaart een bundel met het model en wat nodig is om ermee te
    voorspellen: {methode, spec, model, kolommen, origin, n_train, n_train_per_deel, train_tot}."""
    methode = methode or cfg.operationele_methode
    spec = parse_spec(methode)
    origin = origin or vandaag_lokaal()
    features = compare.laad_features(cfg)
    train = trainset(features, origin, spec.venster or cfg.rolling_venster_dagen)
    kolommen = feature_kolommen(features)
    model = Geschat(spec, cfg, train, kolommen)
    pad = model_pad(cfg, methode)
    pad.parent.mkdir(exist_ok=True)
    joblib.dump({"methode": methode, "spec": spec, "model": model, "kolommen": kolommen, "origin": origin,
                 "n_train": len(train), "n_train_per_deel": model.n_train, "train_tot": train["time_utc"].max()}, pad)
    log.info("model %s getraind op %d rijen (t/m %s), delen %s -> %s", methode, len(train), train["time_utc"].max(),
             model.n_train, pad)
    return pad


def voorspel_kwantielen(bundel: dict, features: pd.DataFrame) -> pd.DataFrame:
    """P10, P50 en P90 van het bewaarde model voor de rijen in `features`, met origin, time_utc en horizon erbij.

    Het model krijgt alle kolommen van `features` (het heeft `horizon_dag` nodig om het juiste deelmodel te kiezen)
    plus de kolommen waarop het getraind is; ontbreekt daarvan iets, dan is die kolom leeg (NaN).
    """
    X = features.reindex(columns=list(dict.fromkeys([*features.columns, *bundel["kolommen"]])))
    pred = bundel["model"].predict(X, bundel["kolommen"])
    uit = features[["origin", "time_utc", "horizon_dag", "horizon_uren"]].copy()
    for k in KWANTIELEN:
        uit[k] = pred[k].to_numpy()
    return uit


def conformal_per_horizon(cfg: Config, methode: str, origin: date) -> dict[int, float]:
    """Correctie per horizon uit de meest recente bekende uitkomsten van de rolling backtest.

    Zoekt in alle `voorspellingen_*.parquet` naar de methode, ook onder haar canonieke naam (met venster expliciet).
    Alleen voor `epv predict`; de dagelijkse run kalibreert op het runarchief.
    """
    namen = {methode, parse_spec(methode).canoniek(cfg.rolling_venster_dagen)}
    delen = []
    for pad in sorted(cfg.processed_dir.glob("voorspellingen_*.parquet")):
        d = pd.read_parquet(pad, columns=["origin", "time_utc", "horizon_dag", "methode", "p10", "p90", DOEL])
        delen.append(d[d["methode"].isin(namen)])
    v = pd.concat(delen, ignore_index=True).drop_duplicates(["origin", "time_utc", "horizon_dag"]) if delen else pd.DataFrame()
    if v.empty:
        log.warning("geen backtest-voorspellingen voor %s gevonden; interval wordt niet gekalibreerd", methode)
        return {}
    v["time_utc"] = pd.to_datetime(v["time_utc"], utc=True)
    v["origin"] = pd.to_datetime(v["origin"])
    venster_start = pd.Timestamp(origin) - pd.Timedelta(days=cfg.kalibratie_venster_dagen)
    v = v[(v["time_utc"] < bekend_tot(origin)) & (v["origin"] >= venster_start)]
    uit = {}
    for k, g in v.dropna(subset=[DOEL]).groupby("horizon_dag"):
        uit[int(k)] = conformal_correctie(conformal_score(g[DOEL], g["p10"], g["p90"]))
    return uit


def voorspel(cfg: Config, methode: str | None = None, origin: date | None = None) -> pd.DataFrame:
    """Voorspelt alle horizonten vanaf `origin` met het bewaarde model en de actuele weersverwachting (`epv predict`)."""
    methode = methode or cfg.operationele_methode
    origin = origin or vandaag_lokaal()
    bundel = joblib.load(model_pad(cfg, methode))
    prijzen, weer = compare.laad_basis(cfg)
    f = bouw_features(prijzen, weer, cfg, [origin], horizon_dagen=cfg.horizon_dagen, weer_actueel=laad_weer_actueel(cfg))
    uit = voorspel_kwantielen(bundel, f)
    q = conformal_per_horizon(cfg, methode, origin)
    uit["conformal_q"] = uit["horizon_dag"].map(q).fillna(0.0)
    uit["p10_kal"] = (uit["p10"] - uit["conformal_q"]).clip(upper=uit["p50"])
    uit["p90_kal"] = (uit["p90"] + uit["conformal_q"]).clip(lower=uit["p50"])
    uit["methode"] = methode
    aandeel_leeg = f.reindex(columns=bundel["kolommen"]).isna().mean().sort_values(ascending=False)
    if aandeel_leeg.iloc[0] > 0.5:
        log.warning("features met veel ontbrekende waarden: %s", aandeel_leeg[aandeel_leeg > 0.5].index.tolist()[:10])
    return uit
