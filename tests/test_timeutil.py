from datetime import date

import pandas as pd

from stroomprijsvoorspeller import timeutil as tu


def test_zomertijd_dagen_hebben_23_en_25_uur():
    assert tu.hours_in_local_day(date(2025, 3, 30)) == 23   # klok vooruit
    assert tu.hours_in_local_day(date(2025, 10, 26)) == 25  # klok terug
    assert tu.hours_in_local_day(date(2025, 7, 1)) == 24


def test_dag_grenzen_in_utc():
    start, einde = tu.local_day_bounds(date(2025, 7, 1))
    assert start == pd.Timestamp("2025-06-30T22:00Z")
    assert einde == pd.Timestamp("2025-07-01T22:00Z")
    start, einde = tu.local_day_bounds(date(2025, 1, 15))
    assert start == pd.Timestamp("2025-01-14T23:00Z")


def test_publicatiemoment_13_uur_lokaal():
    assert tu.publication_cutoff(date(2025, 7, 1), 13) == pd.Timestamp("2025-07-01T11:00Z")
    assert tu.publication_cutoff(date(2025, 1, 15), 13) == pd.Timestamp("2025-01-15T12:00Z")


def test_local_hour_range_telt_alle_uren():
    assert len(tu.local_hour_range(date(2025, 10, 26))) == 25
    assert len(tu.local_hour_range(date(2025, 3, 30))) == 23


def test_ensure_utc_leest_naief_als_utc():
    idx = pd.DatetimeIndex(["2025-01-01T00:00"])
    assert tu.ensure_utc(idx)[0] == pd.Timestamp("2025-01-01T00:00Z")
