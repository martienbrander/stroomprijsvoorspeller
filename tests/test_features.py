"""Tests op de featurematrix. De belangrijkste: geen informatie uit de toekomst."""

from datetime import date, timedelta

import numpy as np
import pandas as pd

from stroomprijsvoorspeller.processing import features as ft
from stroomprijsvoorspeller.sources.calendar import kalender_features
from tests.conftest import maak_config

BASIS = date(2025, 1, 1)


def _prijzen(start="2024-12-01T00:00Z", einde="2025-04-15T00:00Z") -> pd.DataFrame:
    """Deterministische prijs: 100 * dagindex (lokaal) + lokaal uur. Zo is elke waarde terug te rekenen."""
    t = pd.date_range(start, einde, freq="h", tz="UTC", inclusive="left")
    kal = kalender_features(t)
    dagidx = np.array([(d - BASIS).days for d in kal["datum_lokaal"]])
    return pd.DataFrame({"time_utc": t, "prijs_eur_mwh": (100.0 * dagidx + kal["uur_lokaal"].to_numpy()).astype(float)})


def _weer(cfg, start="2024-12-01T00:00Z", einde="2025-04-15T00:00Z") -> pd.DataFrame:
    """Weerwaarde = 1000 * lead + UTC-uur, zodat we kunnen zien welke lead gebruikt is."""
    t = pd.date_range(start, einde, freq="h", tz="UTC", inclusive="left")
    df = pd.DataFrame(index=t)
    for p in cfg.weerpunten:
        for var in cfg.weer_variabelen:
            for n in cfg.lead_dagen:
                df[f"{p.naam}__{var}_lead{n}"] = 1000.0 * n + t.hour
    df.index.name = "time_utc"
    return df


def _prijs(dag: date, uur: int) -> float:
    return 100.0 * (dag - BASIS).days + uur


def test_geen_informatie_uit_de_toekomst_in_features():
    cfg = maak_config()
    origin = date(2025, 2, 10)
    prijzen = _prijzen()
    weer = _weer(cfg)
    f_echt = ft.bouw_features(prijzen, weer, cfg, [origin], horizon_dagen=(2, 3, 4, 5, 6, 7))

    # vergiftig alles wat op het voorspelmoment nog niet bekend is
    vergiftigd = prijzen.copy()
    vergiftigd.loc[vergiftigd["time_utc"] >= ft.bekend_tot(origin), "prijs_eur_mwh"] = 1e6
    f_gif = ft.bouw_features(vergiftigd, weer, cfg, [origin], horizon_dagen=(2, 3, 4, 5, 6, 7))

    kolommen = [c for c in f_echt.columns if c != ft.DOEL]
    pd.testing.assert_frame_equal(f_echt[kolommen], f_gif[kolommen])
    # het doel zelf is wel veranderd (dat is de toekomst)
    assert (f_gif[ft.DOEL] == 1e6).all()
    assert not f_echt[ft.DOEL].isna().any()


def test_bekend_tot_is_einde_van_morgen_lokaal():
    assert ft.bekend_tot(date(2025, 7, 1)) == pd.Timestamp("2025-07-02T22:00Z")
    assert ft.bekend_tot(date(2025, 1, 15)) == pd.Timestamp("2025-01-16T23:00Z")


def test_doelrijen_liggen_op_de_juiste_dag_en_horizon():
    cfg = maak_config()
    origin = date(2025, 2, 10)
    f = ft.bouw_features(_prijzen(), _weer(cfg), cfg, [origin], horizon_dagen=(2, 5))
    for k in (2, 5):
        rijen = f[f["horizon_dag"] == k]
        assert len(rijen) == 24
        assert (rijen["datum_lokaal"] == origin + timedelta(days=k)).all()
        # 13:00 lokaal op D tot 00:00 lokaal op D+k = 24k - 13 uur
        assert rijen["horizon_uren"].min() == 24 * k - 13
        assert (rijen["time_utc"] >= ft.bekend_tot(origin)).all()


def test_zomertijd_dag_heeft_23_rijen():
    cfg = maak_config()
    origin = date(2025, 3, 28)  # D+2 = 30 maart, klok vooruit
    f = ft.bouw_features(_prijzen(), _weer(cfg), cfg, [origin], horizon_dagen=(2,))
    assert len(f) == 23
    assert 2 not in f["uur_lokaal"].tolist()


def test_weer_gebruikt_lead_gelijk_aan_horizon():
    cfg = maak_config()
    origin = date(2025, 2, 10)
    f = ft.bouw_features(_prijzen(), _weer(cfg), cfg, [origin], horizon_dagen=(2, 3, 4, 5, 6, 7))
    uur_utc = pd.DatetimeIndex(f["time_utc"]).hour
    verwacht = 1000.0 * f["horizon_dag"] + uur_utc
    assert np.allclose(f["a__wind_speed_100m"], verwacht)
    assert np.allclose(f["b__temperature_2m"], verwacht)
    assert "a__wind_speed_100m_lead2" not in f.columns
    assert {"wind_zee_gem", "wind_land_gem", "straling_gem", "temp_gem", "wind_zee_gem_dag"} <= set(f.columns)


def test_prijsfeatures_kloppen_exact():
    cfg = maak_config()
    origin = date(2025, 2, 10)
    f = ft.bouw_features(_prijzen(), _weer(cfg), cfg, [origin], horizon_dagen=(3,))
    laatste = origin + timedelta(days=1)
    for _, r in f.iterrows():
        u = int(r["uur_lokaal"])
        assert r["prijs_laatste_dag_uur"] == _prijs(laatste, u)
        assert r["prijs_vorige_week_uur"] == _prijs(origin + timedelta(days=3 - 7), u)
        # profiel: gemiddelde over 28 dagen t/m D+1 van 100*dagidx + u
        dagen = [laatste - timedelta(days=i) for i in range(28)]
        assert np.isclose(r["prijs_profiel_uur_gem"], np.mean([_prijs(d, u) for d in dagen]))
        recent = [laatste - timedelta(days=i) for i in range(7)]
        assert np.isclose(r["prijs_recent_uur_gem"], np.mean([_prijs(d, u) for d in recent]))
    assert np.isclose(f["prijs_laatste_dag_gem"].iloc[0], np.mean([_prijs(laatste, u) for u in range(24)]))


def test_doel_ontbreekt_voor_onbekende_toekomst():
    cfg = maak_config()
    origin = date(2025, 4, 13)  # D+2 = 15 april, prijzen lopen tot 15 april 00:00 UTC
    f = ft.bouw_features(_prijzen(), _weer(cfg), cfg, [origin], horizon_dagen=(2,))
    assert f[ft.DOEL].isna().sum() >= 22


def test_feature_kolommen_sluiten_meta_en_doel_uit():
    cfg = maak_config()
    f = ft.bouw_features(_prijzen(), _weer(cfg), cfg, [date(2025, 2, 10)], horizon_dagen=(2,))
    kol = ft.feature_kolommen(f)
    assert ft.DOEL not in kol
    assert not set(ft.META) & set(kol)
    assert "uur_lokaal" in kol and "prijs_recent_gem" in kol


def test_actueel_weer_vult_aan_waar_previous_runs_ontbreken():
    cfg = maak_config()
    origin = date(2025, 2, 10)
    weer = _weer(cfg, einde="2025-02-11T00:00Z")  # stopt voor de doeldag (12 feb lokaal begint 11 feb 23:00 UTC)
    actueel = _weer(cfg)
    actueel = actueel[[c for c in actueel.columns if c.endswith("_lead1")]]
    actueel.columns = [c[: -len("_lead1")] for c in actueel.columns]
    actueel[:] = -1.0
    f = ft.bouw_features(_prijzen(), weer, cfg, [origin], horizon_dagen=(2,), weer_actueel=actueel)
    assert (f["a__wind_speed_100m"] == -1.0).all()
