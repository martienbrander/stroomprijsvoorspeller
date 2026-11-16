"""Tests voor de backtest-logica van fase 3: goedkoopste blok, Diebold-Mariano, ACI, betrouwbaarheid."""

from datetime import date, timedelta

import numpy as np
import pandas as pd

from stroomprijsvoorspeller.evaluation import blocks, metrics, reliability, stats
from stroomprijsvoorspeller.model import calibration as cal
from stroomprijsvoorspeller.processing import features as ft


def test_goedkoopste_blok():
    p = np.array([50, 40, 30, 20, 10, 20, 30, 40], float)
    i, gem = blocks.goedkoopste_blok(p, 3)
    assert i == 3 and gem == 50 / 3
    i, gem = blocks.goedkoopste_blok(np.array([np.nan] * 5), 3)
    assert np.isnan(gem)
    assert blocks.dagdeel(5) == "nacht" and blocks.dagdeel(6) == "ochtend" and blocks.dagdeel(23) == "avond"


def _dag(origin: date, k: int, methode: str, doel, p50):
    uren = ft.local_hour_range(origin + timedelta(days=k))
    return pd.DataFrame({"origin": pd.Timestamp(origin), "time_utc": uren, "horizon_dag": k, "methode": methode,
                         "p10": p50, "p50": p50, "p90": p50, "doel": doel})


def test_blok_scores_exact_en_tolerantie():
    origin = date(2025, 6, 1)
    doel = np.array([100.0] * 24)
    doel[3:6] = 10.0        # echt goedkoopste blok: 3-6 uur lokaal
    doel[14:17] = 15.0      # tweede blok, 5 EUR/MWh duurder = binnen 10% van daggemiddelde (~88)
    goed = doel.copy()
    fout = doel.copy(); fout[14:17] = 0.0   # model denkt dat de middag het goedkoopst is
    echt_fout = doel.copy(); echt_fout[20:23] = 50.0; echt_fout_pred = np.array([100.0] * 24); echt_fout_pred[20:23] = 0
    v = pd.concat([
        _dag(origin, 2, "goed", doel, goed),
        _dag(origin, 2, "bijna", doel, fout),
        _dag(origin, 2, "mis", doel, echt_fout_pred),
    ])
    s = blocks.blok_scores(v, lengte=3).set_index("methode")
    assert s.loc["goed", "exact"] and s.loc["goed", "meerkosten"] == 0
    assert not s.loc["bijna", "exact"] and s.loc["bijna", "binnen_tol"] and np.isclose(s.loc["bijna", "meerkosten"], 5.0)
    assert not s.loc["bijna", "dagdeel_juist"]
    assert not s.loc["mis", "binnen_tol"] and s.loc["mis", "meerkosten"] == 90.0
    sam = blocks.blok_samenvatting(s.reset_index())
    assert set(sam["methode"]) == {"goed", "bijna", "mis"}


def test_diebold_mariano_herkent_beter_model():
    rng = np.random.default_rng(0)
    n = 400
    b = np.abs(rng.normal(10, 3, n))
    a = b - 1.0 + rng.normal(0, 0.5, n)   # a is structureel 1 beter
    stat, p = stats.diebold_mariano(a, b)
    assert stat < -5 and p < 1e-6
    stat2, p2 = stats.diebold_mariano(b, a)
    assert stat2 > 5 and p2 > 0.999
    # gelijk goede modellen: geen significantie
    c = b + rng.normal(0, 0.5, n)
    _, p3 = stats.diebold_mariano(c, b)
    assert 0.05 < p3 < 0.95


def test_newey_west_groter_bij_autocorrelatie():
    rng = np.random.default_rng(1)
    e = rng.normal(size=2000)
    ar = np.zeros(2000)
    for t in range(1, 2000):
        ar[t] = 0.8 * ar[t - 1] + e[t]
    assert stats.newey_west_variantie(ar, lags=10) > 3 * stats.newey_west_variantie(e, lags=10)


def test_aci_herstelt_dekking_na_regimewissel():
    """Voor een vaste correctie faalt de dekking na een niveausprong; ACI stuurt alpha bij en herstelt sneller."""
    rng = np.random.default_rng(2)
    origins = [date(2025, 1, 1) + timedelta(days=i) for i in range(160)]
    rijen = []
    for i, D in enumerate(origins):
        uren = ft.local_hour_range(D + timedelta(days=2))
        schaal = 10.0 if i < 80 else 40.0      # na dag 80 vier keer zo volatiel
        y = rng.normal(0, schaal, len(uren))
        rijen.append(pd.DataFrame({"origin": pd.Timestamp(D), "time_utc": uren, "horizon_dag": 2, "methode": "m",
                                   "p10": -5.0, "p50": 0.0, "p90": 5.0, "doel": y}))
    v = pd.concat(rijen, ignore_index=True)
    kal = cal.pas_conformal_toe(v, venster_dagen=30)
    aci = cal.pas_aci_toe(kal, venster_dagen=30, gamma=0.05)
    na = aci[aci["origin"] >= pd.Timestamp(origins[85])]
    na = na[na["origin"] < pd.Timestamp(origins[110])]
    d_kal = metrics.dekking(na["doel"], na["p10_kal"], na["p90_kal"])
    d_aci = metrics.dekking(na["doel"], na["p10_aci"], na["p90_aci"])
    assert d_aci > d_kal
    assert (aci["alpha_aci"] <= 0.5).all() and (aci["alpha_aci"] >= 0.01).all()
    # geen lekkage: alpha en q voor origin D mogen niet afhangen van uitkomsten na bekend_tot(D)
    v2 = v.copy()
    laatste = origins[-1]
    v2.loc[v2["time_utc"] >= ft.bekend_tot(laatste), "doel"] = 1e6
    aci2 = cal.pas_aci_toe(cal.pas_conformal_toe(v2, 30), venster_dagen=30, gamma=0.05)
    r1 = aci[aci["origin"] == pd.Timestamp(laatste)]
    r2 = aci2[aci2["origin"] == pd.Timestamp(laatste)]
    assert np.allclose(r1["p10_aci"], r2["p10_aci"]) and np.allclose(r1["alpha_aci"], r2["alpha_aci"])


def test_betrouwbaarheid_niveaus():
    assert reliability.niveau_uit_rmae(0.7) == "hoog"
    assert reliability.niveau_uit_rmae(0.85) == "redelijk"
    assert reliability.niveau_uit_rmae(0.95) == "laag"
    assert reliability.niveau_uit_rmae(None) == "laag"
    assert reliability.betrouwbaarheid(0.7, band_breedte=50, p50_niveau=100) == "hoog"
    assert reliability.betrouwbaarheid(0.7, band_breedte=150, p50_niveau=100) == "redelijk"   # vage band: stap omlaag
    assert reliability.betrouwbaarheid(0.95, band_breedte=150, p50_niveau=100) == "laag"


def test_rmae_per_horizon_gebruikt_alleen_venster():
    origins = [date(2025, 3, 1) + timedelta(days=i) for i in range(60)]
    rijen = []
    for i, D in enumerate(origins):
        uren = ft.local_hour_range(D + timedelta(days=2))
        doel = np.full(len(uren), 100.0)
        fout_model = 10.0 if i < 30 else 2.0    # model wordt na dag 30 veel beter
        rijen.append(pd.DataFrame({"origin": pd.Timestamp(D), "time_utc": uren, "horizon_dag": 2, "methode": "lightgbm",
                                   "p10": 0.0, "p50": doel + fout_model, "p90": 0.0, "doel": doel}))
        rijen.append(pd.DataFrame({"origin": pd.Timestamp(D), "time_utc": uren, "horizon_dag": 2, "methode": "profiel_4w",
                                   "p10": 0.0, "p50": doel + 10.0, "p90": 0.0, "doel": doel}))
    v = pd.concat(rijen, ignore_index=True)
    r = reliability.rmae_per_horizon(v, "lightgbm", tot=pd.Timestamp(origins[-1]) + pd.Timedelta(days=1), dagen=30)
    assert np.isclose(r[2], 0.2)
    r_vroeg = reliability.rmae_per_horizon(v, "lightgbm", tot=pd.Timestamp(origins[30]), dagen=30)
    assert np.isclose(r_vroeg[2], 1.0)
