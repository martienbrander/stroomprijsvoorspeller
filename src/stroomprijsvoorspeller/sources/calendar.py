"""Kalenderkenmerken: lokaal uur, weekdag, maand, Nederlandse feestdagen, seizoen."""

from __future__ import annotations

import holidays
import pandas as pd

from stroomprijsvoorspeller.timeutil import to_local

SEIZOEN = {12: 0, 1: 0, 2: 0, 3: 1, 4: 1, 5: 1, 6: 2, 7: 2, 8: 2, 9: 3, 10: 3, 11: 3}  # 0 winter .. 3 herfst


def nl_feestdagen(jaren) -> holidays.HolidayBase:
    return holidays.country_holidays("NL", years=jaren)


def kalender_features(index_utc: pd.DatetimeIndex) -> pd.DataFrame:
    """Kenmerken per tijdstip, berekend in lokale tijd. Index = time_utc."""
    lokaal = to_local(index_utc)
    if len(lokaal):
        jaren = range(int(lokaal.year.min()), int(lokaal.year.max()) + 1)
    else:
        jaren = range(2024, 2025)
    feest = nl_feestdagen(jaren)
    datums = pd.Index(lokaal.date)
    is_feestdag = [d in feest for d in datums]
    df = pd.DataFrame({
        "datum_lokaal": datums,
        "uur_lokaal": lokaal.hour,
        "weekdag": lokaal.day_of_week,      # 0 = maandag
        "maand": lokaal.month,
        "dag_van_jaar": lokaal.day_of_year,
        "is_weekend": lokaal.day_of_week >= 5,
        "is_feestdag": pd.Series(is_feestdag, dtype="bool").to_numpy(),
    }, index=pd.DatetimeIndex(index_utc, name="time_utc"))
    df["is_vrije_dag"] = df["is_weekend"] | df["is_feestdag"]
    df["seizoen"] = df["maand"].map(SEIZOEN).astype("int8")
    return df
