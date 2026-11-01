"""Tests voor kwantielmodellen, baselines, kalibratie en de rolling-origin loop."""

from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from stroomprijsvoorspeller.evaluation import metrics
from stroomprijsvoorspeller.evaluation.rolling import run_rolling, trainset
from stroomprijsvoorspeller.model import calibration as cal
from stroomprijsvoorspeller.model.baselines import baseline_voorspelling
from stroomprijsvoorspeller.model.quantile_models import (
    Combinatie,
    LightGBMKwantiel,
    LineairKwantiel,
    kwantiel_naam,
    sorteer_kwantielen,
)
from stroomprijsvoorspeller.processing import features as ft
from tests.conftest import maak_config
from tests.test_features import _prijzen, _weer


def _synthetisch(n=2000, seed=0):
    rng = np.random.default_rng(seed)
    X = pd.DataFrame({
        "x1": rng.normal(size=n), "x2": rng.normal(size=n),
        "uur_lokaal": rng.integers(0, 24, n), "weekdag": rng.integers(0, 7, n),
        "a__wind_speed_100m": rng.normal(size=n),
    })
    y = 50 + 10 * X["x1"] - 5 * X["x2"] + rng.normal(scale=5, size=n)
    return X, pd.Series(y)


def test_kwantiel_naam_en_sortering():
    assert kwantiel_naam(0.1) == "p10" and kwantiel_naam(0.5) == "p50" and kwantiel_naam(0.9) == "p90"
    df = pd.DataFrame({"p10": [5.0, 1.0], "p50": [3.0, 2.0], "p90": [1.0, 3.0]})
    s = sorteer_kwantielen(df)
    assert (s["p10"] <= s["p50"]).all() and (s["p50"] <= s["p90"]).all()


@pytest.mark.parametrize("model", [
    LineairKwantiel(),
    LightGBMKwantiel(params={"n_estimators": 60, "learning_rate": 0.1, "num_leaves": 7, "min_child_samples": 5}),
    Combinatie([LineairKwantiel(), LightGBMKwantiel(params={"n_estimators": 30, "num_leaves": 7})]),
])
def test_modellen_leren_en_geven_geordende_kwantielen(model):
    X, y = _synthetisch()
    model.fit(X.iloc[:1500], y.iloc[:1500])
    pred = model.predict(X.iloc[1500:])
    assert list(pred.columns) == ["p10", "p50", "p90"]
    assert (pred["p10"] <= pred["p50"]).all() and (pred["p50"] <= pred["p90"]).all()
    assert metrics.mae(y.iloc[1500:], pred["p50"]) < 6.0
    d = metrics.dekking(y.iloc[1500:], pred["p10"], pred["p90"])
    assert 0.65 < d < 0.95


def test_lineair_laat_per_punt_kolommen_weg():
    X, y = _synthetisch()
    m = LineairKwantiel().fit(X, y)
    assert "a__wind_speed_100m" not in m.kolommen
    assert "x1" in m.kolommen


def test_conformal_correctie_herstelt_dekking():
    rng = np.random.default_rng(1)
    y = rng.normal(size=5000)
    lo, hi = np.full(5000, -0.5), np.full(5000, 0.5)  # veel te smal: dekt ~38%
    q = cal.conformal_correctie(cal.conformal_score(y, lo, hi), alpha=0.2)
    assert q > 0
    assert abs(cal.dekking(y, lo - q, hi + q) - 0.8) < 0.03


def test_conformal_maakt_te_breed_interval_smaller():
    rng = np.random.default_rng(2)
    y = rng.normal(size=5000)
    q = cal.conformal_correctie(cal.conformal_score(y, np.full(5000, -5.0), np.full(5000, 5.0)))
    assert q < 0


def test_pas_conformal_toe_gebruikt_alleen_bekende_uitkomsten():
    """Voor voorspelmoment D mogen alleen uitkomsten meetellen van uren vóór bekend_tot(D)."""
    origins = [date(2025, 2, 1) + timedelta(days=i) for i in range(40)]
    rijen = []
    for D in origins:
        for k in (2,):
            uren = pd.date_range(ft.bekend_tot(D) + pd.Timedelta(days=k - 2), periods=24, freq="h")
            for t in uren:
                rijen.append({"origin": pd.Timestamp(D), "time_utc": t, "horizon_dag": k, "methode": "m",
                              "p10": 0.0, "p50": 0.0, "p90": 0.0, "doel": 1.0})
    v = pd.DataFrame(rijen)
    # vergiftig het doel van alles wat op het laatste voorspelmoment nog niet bekend was
    laatste = origins[-1]
    v2 = v.copy()
    v2.loc[v2["time_utc"] >= ft.bekend_tot(laatste), "doel"] = 1e6
    k1 = cal.pas_conformal_toe(v, venster_dagen=30)
    k2 = cal.pas_conformal_toe(v2, venster_dagen=30)
    r1 = k1[k1["origin"] == pd.Timestamp(laatste)]
    r2 = k2[k2["origin"] == pd.Timestamp(laatste)]
    assert np.allclose(r1["conformal_q"], r2["conformal_q"])
    assert (r1["conformal_q"] > 0).all()           # er is wel gecorrigeerd
    assert (r1["p10_kal"] <= r1["p50"]).all() and (r1["p90_kal"] >= r1["p50"]).all()
    # de eerste voorspelmomenten hebben nog geen bekende uitkomsten: geen correctie
    eerste = k1[k1["origin"] == pd.Timestamp(origins[0])]
    assert (eerste["conformal_q"] == 0).all()


def test_metrics_basis():
    y = np.array([1.0, 2.0, 3.0, np.nan])
    p = np.array([1.0, 3.0, 1.0, 5.0])
    assert metrics.mae(y, p) == 1.0
    assert np.isclose(metrics.rmse(y, p), np.sqrt(5 / 3))
    assert np.isclose(metrics.pinball(y, p, 0.5), 0.5)
    assert metrics.dekking(y, p - 1, p + 1) == 2 / 3
    assert metrics.breedte(p - 1, p + 1) == 2.0


def _features_voor_rolling(cfg, origins):
    return ft.bouw_features(_prijzen(), _weer(cfg), cfg, origins, horizon_dagen=(2, 3))


def test_trainset_bevat_geen_toekomst():
    cfg = maak_config()
    origins = [date(2025, 1, 10) + timedelta(days=i) for i in range(40)]
    f = _features_voor_rolling(cfg, origins)
    D = date(2025, 2, 10)
    tr = trainset(f, D, venster_dagen=30)
    assert (tr["time_utc"] < ft.bekend_tot(D)).all()
    assert (tr["origin"] < pd.Timestamp(D)).all()
    assert (tr["origin"] >= pd.Timestamp(D) - pd.Timedelta(days=30)).all()
    assert tr[ft.DOEL].notna().all()
    assert len(tr) > 24 * 20


def test_run_rolling_levert_alle_methoden_en_baselines_zijn_exact():
    cfg = maak_config()
    origins = [date(2025, 1, 10) + timedelta(days=i) for i in range(45)]
    f = _features_voor_rolling(cfg, origins)
    test_origins = origins[-5:]
    v = run_rolling(f, cfg, ["laatste_dag", "profiel_4w", "lightgbm", "lineair_ruw"], test_origins,
                    hertrain_elke_dagen=3, venster_dagen=30)
    assert set(v["methode"]) == {"laatste_dag", "profiel_4w", "lightgbm", "lineair_ruw"}
    assert set(v["horizon_dag"]) == {2, 3}
    assert {"p10_kal", "p90_kal", "conformal_q"} <= set(v.columns)
    # baseline laatste_dag: prijs van D+1 zelfde uur; met prijs = 100*dagidx + uur is de fout exact 100*(k-1)
    b = v[v["methode"] == "laatste_dag"]
    assert np.allclose(b["doel"] - b["p50"], 100 * (b["horizon_dag"] - 1))
    # de synthetische prijs is exact lineair in de features (laatste dag + 100 per horizon-dag):
    # het lineaire model moet de baseline ruim verslaan; bomen kunnen een trend niet extrapoleren
    lin = v[v["methode"] == "lineair_ruw"]
    assert metrics.mae(lin["doel"], lin["p50"]) < 0.25 * metrics.mae(b["doel"], b["p50"])
    assert v["p50"].notna().all()


def test_baseline_voorspelling_kopieert_feature():
    cfg = maak_config()
    f = _features_voor_rolling(cfg, [date(2025, 2, 10)])
    p = baseline_voorspelling(f, "vorige_week")
    assert (p["p10"] == f["prijs_vorige_week_uur"]).all() and (p["p90"] == p["p50"]).all()
