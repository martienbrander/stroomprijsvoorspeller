import pandas as pd

from stroomprijsvoorspeller.config import Config, Weerpunt
from stroomprijsvoorspeller.sources import open_meteo


def _payload(tijden, **kolommen):
    return {"hourly": {"time": tijden, **kolommen}}


def test_parse_hourly_hernoemt_en_maakt_float():
    p = _payload(["2025-06-01T00:00", "2025-06-01T01:00"],
                 wind_speed_100m_previous_day3=[5, None], temperature_2m_previous_day3=[10.5, 11.0])
    hernoem = {"wind_speed_100m_previous_day3": "wind_speed_100m_lead3",
               "temperature_2m_previous_day3": "temperature_2m_lead3"}
    df = open_meteo.parse_hourly(p, hernoem)
    assert list(df.columns) == ["time_utc", "wind_speed_100m_lead3", "temperature_2m_lead3"]
    assert df["time_utc"].iloc[0] == pd.Timestamp("2025-06-01T00:00Z")
    assert df["wind_speed_100m_lead3"].isna().iloc[1]
    assert df["temperature_2m_lead3"].dtype == "float64"


def test_kolomnamen():
    assert open_meteo.prev_run_var("wind_speed_100m", 4) == "wind_speed_100m_previous_day4"
    assert open_meteo.lead_kolom("wind_speed_100m", 4) == "wind_speed_100m_lead4"


def _cfg(tmp_path) -> Config:
    return Config(
        root=tmp_path, tijdzone="Europe/Amsterdam", biedzone="NL",
        data_start="2022-11-01", weer_start="2025-01-01",
        raw_dir=tmp_path / "raw", processed_dir=tmp_path / "processed",
        prijsbron="energy_charts", kwartier_vanaf="2025-10-01",
        weer_model="best_match", weer_variabelen=("wind_speed_100m",),
        forecast_dagen=7, lead_dagen=(2, 3),
        weerpunten=(Weerpunt("test", 52.0, 5.0, "land"),),
        publicatie_uur_lokaal=13, horizon_dagen=(2, 3, 4, 5), backtest_horizon_dagen=(2, 3, 4, 5),
        kwantielen=(0.1, 0.5, 0.9), rolling_venster_dagen=180, recente_prijs_dagen=7,
        profiel_dagen=28, hertrain_elke_dagen=7, kalibratie_venster_dagen=30, lightgbm_params={},
    )


def test_update_previous_runs_is_incrementeel(tmp_path, monkeypatch):
    cfg = _cfg(tmp_path)
    aanroepen = []

    def nep_fetch(punt, variabelen, leads, start, einde, model, session=None, blok_dagen=120):
        aanroepen.append((start, einde))
        t = pd.date_range(start, einde + pd.Timedelta(hours=23), freq="h")
        df = pd.DataFrame({"time_utc": t, "punt": punt.naam})
        for n in leads:
            df[f"wind_speed_100m_lead{n}"] = float(n)
        # laatste dag nog niet beschikbaar: alles leeg
        df.loc[df["time_utc"] >= einde, [f"wind_speed_100m_lead{n}" for n in leads]] = None
        return df

    monkeypatch.setattr(open_meteo, "fetch_previous_runs", nep_fetch)
    monkeypatch.setattr(open_meteo, "utc_now", lambda: pd.Timestamp("2025-01-10T12:00Z"))
    uit = open_meteo.update_previous_runs(cfg)
    df1 = uit["test"]
    assert aanroepen[0][0] == pd.Timestamp("2025-01-01", tz="UTC")
    assert df1["time_utc"].max() == pd.Timestamp("2025-01-09T23:00Z")  # lege dag niet bewaard
    assert set(df1.columns) == {"time_utc", "punt", "wind_speed_100m_lead2", "wind_speed_100m_lead3"}

    monkeypatch.setattr(open_meteo, "utc_now", lambda: pd.Timestamp("2025-01-12T12:00Z"))
    df2 = open_meteo.update_previous_runs(cfg, overlap_dagen=2)["test"]
    assert aanroepen[1][0] == pd.Timestamp("2025-01-07", tz="UTC")
    assert df2["time_utc"].is_unique
    assert df2["time_utc"].max() == pd.Timestamp("2025-01-11T23:00Z")
    assert (cfg.raw_dir / "weer_prev_runs_test.parquet").exists()
