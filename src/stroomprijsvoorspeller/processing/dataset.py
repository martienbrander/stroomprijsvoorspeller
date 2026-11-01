"""Bouwt de verwerkte datasets in data/processed uit de ruwe data.

- prijzen_nl_uur.parquet      uurgemiddelde prijs, volledige reeks, kleine gaten geinterpoleerd
- prijzen_nl_kwartier.parquet ruwe kwartierprijzen (vanaf oktober 2025)
- basis_uur.parquet           uurprijs + kalenderkenmerken (basis voor features in fase 2)
- weer_prev_runs.parquet      alle weerpunten naast elkaar: kolom <punt>__<variabele>_lead<N>
"""

from __future__ import annotations

import logging
from pathlib import Path

import pandas as pd

from stroomprijsvoorspeller.config import Config
from stroomprijsvoorspeller.processing.prices import (
    alleen_kwartier,
    naar_uur,
    ontbrekende_uren,
    vul_kleine_gaten,
)
from stroomprijsvoorspeller.sources import energy_charts, open_meteo
from stroomprijsvoorspeller.sources.calendar import kalender_features

log = logging.getLogger(__name__)

UUR_BESTAND = "prijzen_nl_uur.parquet"
KWARTIER_BESTAND = "prijzen_nl_kwartier.parquet"
BASIS_BESTAND = "basis_uur.parquet"
WEER_BESTAND = "weer_prev_runs.parquet"


def bouw_prijzen(cfg: Config) -> pd.DataFrame:
    ruw = energy_charts.lees_ruw(cfg.raw_dir)
    if ruw.empty:
        raise RuntimeError("geen ruwe prijzen; draai eerst `epv fetch`")
    cfg.processed_dir.mkdir(parents=True, exist_ok=True)
    uur = naar_uur(ruw)
    gaten = ontbrekende_uren(uur)
    if len(gaten):
        log.warning("%d ontbrekende uren in prijsreeks (eerste: %s)", len(gaten), gaten[0])
    uur = vul_kleine_gaten(uur)
    uur.to_parquet(cfg.processed_dir / UUR_BESTAND, index=False)
    kwartier = alleen_kwartier(ruw)
    kwartier.to_parquet(cfg.processed_dir / KWARTIER_BESTAND, index=False)
    log.info("uurprijzen: %d rijen, kwartierprijzen: %d rijen", len(uur), len(kwartier))
    return uur


def bouw_basis(cfg: Config, uur: pd.DataFrame) -> pd.DataFrame:
    idx = pd.DatetimeIndex(uur["time_utc"])
    kal = kalender_features(idx)
    basis = uur.set_index("time_utc").join(kal)
    basis.to_parquet(cfg.processed_dir / BASIS_BESTAND)
    return basis


def bouw_weer(cfg: Config) -> pd.DataFrame | None:
    delen = []
    for punt in cfg.weerpunten:
        pad = open_meteo.prev_runs_bestand(cfg.raw_dir, punt.naam)
        if not pad.exists():
            log.warning("geen weerdata voor %s", punt.naam)
            continue
        df = pd.read_parquet(pad)
        df["time_utc"] = pd.to_datetime(df["time_utc"], utc=True)
        df = df.drop(columns=["punt"]).set_index("time_utc")
        df.columns = [f"{punt.naam}__{c}" for c in df.columns]
        delen.append(df)
    if not delen:
        return None
    weer = pd.concat(delen, axis=1).sort_index()
    weer.to_parquet(cfg.processed_dir / WEER_BESTAND)
    log.info("weer: %d uren x %d kolommen", *weer.shape)
    return weer


def bouw_alles(cfg: Config) -> dict[str, Path]:
    uur = bouw_prijzen(cfg)
    bouw_basis(cfg, uur)
    bouw_weer(cfg)
    return {
        "uur": cfg.processed_dir / UUR_BESTAND,
        "kwartier": cfg.processed_dir / KWARTIER_BESTAND,
        "basis": cfg.processed_dir / BASIS_BESTAND,
        "weer": cfg.processed_dir / WEER_BESTAND,
    }
