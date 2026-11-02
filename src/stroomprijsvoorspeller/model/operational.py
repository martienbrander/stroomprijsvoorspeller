"""Operationeel trainen en voorspellen: het pad dat de dagelijkse run straks gebruikt.

- train:   schat het gekozen model op het rolling venster tot en met vandaag en bewaart het in models/
- predict: bouwt features voor het voorspelmoment van vandaag (weer uit de actuele verwachting), voorspelt alle
           horizonten en past de conformal-correctie toe met de meest recente bekende uitkomsten uit de backtest
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


def laad_weer_actueel(cfg: Config) -> pd.DataFrame:
    """Laatste uitgegeven verwachting per punt, als frame met index time_utc en kolommen `<punt>__<var>`."""
    delen = []
    for punt in cfg.weerpunten:
        pad = open_meteo.forecast_bestand(cfg.raw_dir, punt.naam)
        if not pad.exists():
            raise FileNotFoundError(f"geen actuele verwachting voor {punt.naam}; draai `epv fetch`")
        df = pd.read_parquet(pad)
        df["time_utc"] = pd.to_datetime(df["time_utc"], utc=True)
        df["uitgegeven_utc"] = pd.to_datetime(df["uitgegeven_utc"], utc=True)
        laatste = df[df["uitgegeven_utc"] == df["uitgegeven_utc"].max()]
        w = laatste.set_index("time_utc")[list(cfg.weer_variabelen)]
        w.columns = [f"{punt.naam}__{c}" for c in w.columns]
        delen.append(w)
    return pd.concat(delen, axis=1).sort_index()


def vandaag_lokaal() -> date:
    return utc_now().tz_convert(TZ).date()


def train_en_bewaar(cfg: Config, methode: str | None = None, origin: date | None = None) -> Path:
    methode = methode or cfg.operationele_methode
    spec = parse_spec(methode)
    origin = origin or vandaag_lokaal()
    f = compare.laad_features(cfg)
    train = trainset(f, origin, spec.venster or cfg.rolling_venster_dagen)
    kolommen = feature_kolommen(f)
    model = Geschat(spec, cfg, train, kolommen)
    (cfg.root / "models").mkdir(exist_ok=True)
    pad = cfg.root / "models" / MODEL_BESTAND.format(methode=methode)
    joblib.dump({"methode": methode, "spec": spec, "model": model, "kolommen": kolommen, "origin": origin,
                 "n_train": len(train), "n_train_per_deel": model.n_train, "train_tot": train["time_utc"].max()}, pad)
    log.info("model %s getraind op %d rijen (t/m %s), delen %s -> %s", methode, len(train), train["time_utc"].max(),
             model.n_train, pad)
    return pad


def conformal_per_horizon(cfg: Config, methode: str, origin: date) -> dict[int, float]:
    """Correctie per horizon uit de meest recente bekende uitkomsten van de rolling backtest.

    Zoekt in alle `voorspellingen_*.parquet` naar de methode, ook onder haar canonieke naam (met venster expliciet).
    Fase 4 vervangt dit door de eigen runhistorie zodra die lang genoeg is.
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
    grens = bekend_tot(origin)
    v = v[(v["time_utc"] < grens) & (v["origin"] >= pd.Timestamp(origin) - pd.Timedelta(days=cfg.kalibratie_venster_dagen))]
    uit = {}
    for k, g in v.dropna(subset=[DOEL]).groupby("horizon_dag"):
        uit[int(k)] = conformal_correctie(conformal_score(g[DOEL], g["p10"], g["p90"]))
    return uit


def voorspel(cfg: Config, methode: str | None = None, origin: date | None = None) -> pd.DataFrame:
    methode = methode or cfg.operationele_methode
    origin = origin or vandaag_lokaal()
    pad = cfg.root / "models" / MODEL_BESTAND.format(methode=methode)
    bundel = joblib.load(pad)
    prijzen, weer = compare.laad_basis(cfg)
    actueel = laad_weer_actueel(cfg)
    f = bouw_features(prijzen, weer, cfg, [origin], horizon_dagen=cfg.horizon_dagen, weer_actueel=actueel)
    X = f.reindex(columns=bundel["kolommen"])
    pred = bundel["model"].predict(f.reindex(columns=list(dict.fromkeys([*f.columns, *bundel["kolommen"]]))), bundel["kolommen"])
    uit = f[["origin", "time_utc", "horizon_dag", "horizon_uren"]].copy()
    for k in ("p10", "p50", "p90"):
        uit[k] = pred[k].to_numpy()
    q = conformal_per_horizon(cfg, methode, origin)
    uit["conformal_q"] = uit["horizon_dag"].map(q).fillna(0.0)
    uit["p10_kal"] = (uit["p10"] - uit["conformal_q"]).clip(upper=uit["p50"])
    uit["p90_kal"] = (uit["p90"] + uit["conformal_q"]).clip(lower=uit["p50"])
    uit["methode"] = methode
    ontbrekend = X.isna().mean().sort_values(ascending=False)
    if ontbrekend.iloc[0] > 0.5:
        log.warning("features met veel ontbrekende waarden: %s", ontbrekend[ontbrekend > 0.5].index.tolist()[:10])
    return uit
