import pandas as pd

from stroomprijsvoorspeller.sources.calendar import kalender_features


def test_feestdagen_en_weekend():
    idx = pd.DatetimeIndex([
        "2025-04-26T10:00Z",  # Koningsdag (zaterdag)
        "2025-12-25T10:00Z",  # Eerste Kerstdag (donderdag)
        "2025-06-10T10:00Z",  # gewone dinsdag
        "2025-06-15T10:00Z",  # gewone zondag (8 juni is Eerste Pinksterdag)
    ])
    k = kalender_features(idx)
    assert k["is_feestdag"].tolist() == [True, True, False, False]
    assert k["is_weekend"].tolist() == [True, False, False, True]
    assert k["is_vrije_dag"].tolist() == [True, True, False, True]
    assert k["weekdag"].tolist() == [5, 3, 1, 6]


def test_lokaal_uur_rond_zomertijd():
    # 26 okt 2025: om 01:00 UTC gaat de klok van 03:00 CEST terug naar 02:00 CET
    idx = pd.DatetimeIndex(["2025-10-26T00:00Z", "2025-10-26T01:00Z", "2025-07-01T11:00Z", "2025-01-15T12:00Z"])
    k = kalender_features(idx)
    assert k["uur_lokaal"].tolist() == [2, 2, 13, 13]
    assert k["datum_lokaal"].iloc[0] == pd.Timestamp("2025-10-26").date()


def test_seizoen_en_maand():
    idx = pd.DatetimeIndex(["2025-01-15T12:00Z", "2025-04-15T12:00Z", "2025-07-15T12:00Z", "2025-10-15T12:00Z"])
    k = kalender_features(idx)
    assert k["seizoen"].tolist() == [0, 1, 2, 3]
    assert k["maand"].tolist() == [1, 4, 7, 10]
    assert k.index.name == "time_utc"
