import numpy as np
import pandas as pd

from stroomprijsvoorspeller.processing import prices
from stroomprijsvoorspeller.sources import energy_charts


def _kwartier(start: str, waarden: list[float]) -> pd.DataFrame:
    t = pd.date_range(start, periods=len(waarden), freq="15min", tz="UTC")
    return pd.DataFrame({"time_utc": t, "prijs_eur_mwh": waarden})


def _uur(start: str, waarden: list[float]) -> pd.DataFrame:
    t = pd.date_range(start, periods=len(waarden), freq="h", tz="UTC")
    return pd.DataFrame({"time_utc": t, "prijs_eur_mwh": waarden})


def test_parse_response_zet_none_om_naar_nan_en_sorteert():
    payload = {"unix_seconds": [1760922000, 1760918400], "price": [None, 57.66], "unit": "EUR / MWh"}
    df = energy_charts.parse_response(payload)
    assert list(df["time_utc"]) == [pd.Timestamp("2025-10-20T00:00Z"), pd.Timestamp("2025-10-20T01:00Z")]
    assert df["prijs_eur_mwh"].iloc[0] == 57.66
    assert np.isnan(df["prijs_eur_mwh"].iloc[1])


def test_kwartier_naar_uurgemiddelde():
    df = _kwartier("2025-10-20T00:00Z", [10, 20, 30, 40, 50, 50, 50, 50])
    uur = prices.naar_uur(df)
    assert len(uur) == 2
    assert uur["prijs_eur_mwh"].tolist() == [25.0, 50.0]
    assert uur["n_waarden"].tolist() == [4, 4]


def test_uurdata_blijft_uurdata():
    df = _uur("2025-01-01T00:00Z", [1.0, 2.0, 3.0])
    uur = prices.naar_uur(df)
    assert uur["prijs_eur_mwh"].tolist() == [1.0, 2.0, 3.0]
    assert uur["n_waarden"].tolist() == [1, 1, 1]


def test_alleen_kwartier_scheidt_resoluties():
    uurdeel = _uur("2025-09-30T20:00Z", [1, 2, 3, 4])
    kwartierdeel = _kwartier("2025-10-01T00:00Z", [5, 6, 7, 8, 9, 10, 11, 12])
    ruw = pd.concat([uurdeel, kwartierdeel], ignore_index=True)
    kw = prices.alleen_kwartier(ruw)
    assert len(kw) == 8
    assert kw["time_utc"].min() == pd.Timestamp("2025-10-01T00:00Z")


def test_kleine_gaten_worden_gevuld_grote_niet():
    t = pd.date_range("2025-01-01T00:00Z", periods=12, freq="h")
    df = pd.DataFrame({"time_utc": t, "prijs_eur_mwh": range(12)}).astype({"prijs_eur_mwh": "float64"})
    # gat van 2 uur (uur 3,4) en gat van 5 uur (uur 7..11 weg)
    df = df.drop(index=[3, 4]).drop(index=[7, 8, 9, 10]).reset_index(drop=True)
    uur = prices.naar_uur(df)
    assert len(prices.ontbrekende_uren(uur)) == 6
    gevuld = prices.vul_kleine_gaten(uur, max_uren=3)
    assert len(gevuld) == 12
    s = gevuld.set_index("time_utc")["prijs_eur_mwh"]
    assert s.iloc[3] == 3.0 and s.iloc[4] == 4.0           # lineair gevuld
    assert s.iloc[7:11].isna().all()                        # te groot gat blijft leeg
    assert gevuld["geinterpoleerd"].sum() == 2


def test_update_prices_is_incrementeel(tmp_path, monkeypatch):
    aanroepen = []

    def nep_fetch(start, end, *, bzn="NL", session=None):
        aanroepen.append((start, end))
        t = pd.date_range(start.floor("h"), end, freq="h", inclusive="left")
        return pd.DataFrame({"time_utc": t, "prijs_eur_mwh": np.arange(len(t), dtype="float64")})

    monkeypatch.setattr(energy_charts, "fetch_prices", nep_fetch)
    monkeypatch.setattr(energy_charts, "utc_now", lambda: pd.Timestamp("2025-01-10T12:00Z"))

    df1 = energy_charts.update_prices(tmp_path, "2025-01-01")
    assert aanroepen[0][0] == pd.Timestamp("2025-01-01", tz="UTC")
    assert df1["time_utc"].max() == pd.Timestamp("2025-01-11T23:00Z")

    # tweede run: begint bij laatste tijdstip minus overlap, resultaat zonder dubbelen
    monkeypatch.setattr(energy_charts, "utc_now", lambda: pd.Timestamp("2025-01-12T12:00Z"))
    df2 = energy_charts.update_prices(tmp_path, "2025-01-01", overlap_dagen=3)
    assert aanroepen[1][0] == pd.Timestamp("2025-01-08T23:00Z")
    assert df2["time_utc"].is_unique
    assert df2["time_utc"].is_monotonic_increasing
    assert df2["time_utc"].max() == pd.Timestamp("2025-01-13T23:00Z")
