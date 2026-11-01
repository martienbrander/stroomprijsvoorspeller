"""Prijsverwerking: ruwe resolutie (uur of kwartier) -> uurgemiddelden, plus losse kwartierreeks en controles."""

from __future__ import annotations

import pandas as pd


def resolutie_minuten(df: pd.DataFrame) -> pd.Series:
    """Per rij: minuten tot het volgende tijdstip (laatste rij krijgt de waarde van de rij ervoor)."""
    t = df["time_utc"]
    d = t.diff().shift(-1)
    d.iloc[-1] = d.iloc[-2] if len(d) > 1 else pd.Timedelta(hours=1)
    return (d / pd.Timedelta(minutes=1)).round().astype("int64")


def naar_uur(df: pd.DataFrame) -> pd.DataFrame:
    """Uurgemiddelde per volledig UTC-uur. Kolommen: time_utc, prijs_eur_mwh, n_waarden.

    Een uur met uurresolutie heeft n_waarden = 1, met kwartierresolutie 4. Uren zonder waarde ontbreken.
    """
    if df.empty:
        return pd.DataFrame(columns=["time_utc", "prijs_eur_mwh", "n_waarden"])
    s = df.dropna(subset=["prijs_eur_mwh"]).set_index("time_utc")["prijs_eur_mwh"].sort_index()
    g = s.groupby(s.index.floor("h"))
    uit = pd.DataFrame({"prijs_eur_mwh": g.mean(), "n_waarden": g.size().astype("int64")})
    uit.index.name = "time_utc"
    return uit.reset_index()


def alleen_kwartier(df: pd.DataFrame) -> pd.DataFrame:
    """Alleen de rijen met kwartierresolutie (de ruwe EPEX 15-minuten prijzen vanaf oktober 2025)."""
    if len(df) < 2:
        return df.iloc[0:0]
    res = resolutie_minuten(df)
    return df.loc[res.to_numpy() == 15].reset_index(drop=True)


def ontbrekende_uren(uur: pd.DataFrame) -> pd.DatetimeIndex:
    """Uren tussen het eerste en laatste tijdstip die ontbreken."""
    if uur.empty:
        return pd.DatetimeIndex([], tz="UTC")
    volledig = pd.date_range(uur["time_utc"].min(), uur["time_utc"].max(), freq="h")
    return volledig.difference(pd.DatetimeIndex(uur["time_utc"]))


def vul_kleine_gaten(uur: pd.DataFrame, max_uren: int = 3) -> pd.DataFrame:
    """Interpoleert gaten van hoogstens `max_uren` uur lineair; grotere gaten blijven leeg (NaN) maar krijgen wel een rij."""
    if uur.empty:
        return uur
    s = uur.set_index("time_utc")["prijs_eur_mwh"].asfreq("h")
    # alleen gaten vullen waarvan de totale lengte <= max_uren is (pandas' limit= vult ook het begin van grote gaten)
    leeg = s.isna()
    groep = (leeg != leeg.shift()).cumsum()
    gatlengte = leeg.groupby(groep).transform("sum")
    mag_vullen = leeg & (gatlengte <= max_uren)
    gevuld = s.interpolate(limit_area="inside").where(mag_vullen | ~leeg)
    n = uur.set_index("time_utc")["n_waarden"].reindex(s.index).fillna(0).astype("int64")
    uit = pd.DataFrame({"prijs_eur_mwh": gevuld, "n_waarden": n})
    uit["geinterpoleerd"] = s.isna() & gevuld.notna()
    uit.index.name = "time_utc"
    return uit.reset_index()
