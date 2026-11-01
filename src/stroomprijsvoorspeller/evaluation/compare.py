"""Methodenvergelijking op de rolling-origin backtest: schrijft een compacte tabel naar reports/.

Fase 3 bouwt hierop voort met de volledige backtest-rapportage (praktijkmaat, grafieken).
"""

from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path

import pandas as pd

from stroomprijsvoorspeller.config import Config
from stroomprijsvoorspeller.evaluation.metrics import samenvatting
from stroomprijsvoorspeller.evaluation.rolling import run_rolling
from stroomprijsvoorspeller.model.baselines import BASELINES
from stroomprijsvoorspeller.model.quantile_models import MODELNAMEN
from stroomprijsvoorspeller.processing import dataset
from stroomprijsvoorspeller.processing.features import DOEL, bouw_features, origins_in_bereik

log = logging.getLogger(__name__)

FEATURES_BESTAND = "features.parquet"
VOORSPELLINGEN_BESTAND = "voorspellingen_rolling.parquet"
ALLE_METHODEN = (*BASELINES, *MODELNAMEN)


def laad_basis(cfg: Config) -> tuple[pd.DataFrame, pd.DataFrame]:
    prijzen = pd.read_parquet(cfg.processed_dir / dataset.UUR_BESTAND)
    prijzen["time_utc"] = pd.to_datetime(prijzen["time_utc"], utc=True)
    weer = pd.read_parquet(cfg.processed_dir / dataset.WEER_BESTAND)
    weer.index = pd.to_datetime(weer.index, utc=True)
    return prijzen, weer


def bouw_en_bewaar_features(cfg: Config, start: date | None = None, einde: date | None = None,
                            horizon: tuple[int, ...] | None = None) -> pd.DataFrame:
    prijzen, weer = laad_basis(cfg)
    start = start or pd.Timestamp(cfg.weer_start).date()
    einde = einde or weer.index.max().tz_convert(cfg.tijdzone).date()
    origins = origins_in_bereik(start, einde)
    log.info("features bouwen voor %d voorspelmomenten (%s .. %s)", len(origins), start, einde)
    f = bouw_features(prijzen, weer, cfg, origins, horizon_dagen=horizon or cfg.backtest_horizon_dagen)
    cfg.processed_dir.mkdir(parents=True, exist_ok=True)
    f.to_parquet(cfg.processed_dir / FEATURES_BESTAND, index=False)
    log.info("features: %d rijen x %d kolommen -> %s", *f.shape, cfg.processed_dir / FEATURES_BESTAND)
    return f


def laad_features(cfg: Config) -> pd.DataFrame:
    f = pd.read_parquet(cfg.processed_dir / FEATURES_BESTAND)
    f["time_utc"] = pd.to_datetime(f["time_utc"], utc=True)
    f["origin"] = pd.to_datetime(f["origin"])
    return f


def test_origins(features: pd.DataFrame, cfg: Config, start: date | None, einde: date | None) -> list[date]:
    """Voorspelmomenten met volledig trainingsvenster ervoor en bekende uitkomsten voor alle horizonten erna."""
    eerste = features["origin"].min().date() + timedelta(days=cfg.rolling_venster_dagen + 1)
    bekend = features.dropna(subset=[DOEL])
    laatste = bekend.groupby("origin")[DOEL].count()
    volledig = laatste[laatste == laatste.max()].index.max().date()
    start = max(start or eerste, eerste)
    einde = min(einde or volledig, volledig)
    return origins_in_bereik(start, einde)


def vergelijk(cfg: Config, methoden: list[str] | None = None, start: date | None = None, einde: date | None = None,
              hertrain: int | None = None, rapport: Path | None = None,
              uitvoer_bestand: str = VOORSPELLINGEN_BESTAND) -> pd.DataFrame:
    f = laad_features(cfg)
    methoden = list(methoden or ALLE_METHODEN)
    origins = test_origins(f, cfg, start, einde)
    log.info("vergelijking: %d methoden, %d voorspelmomenten (%s .. %s)", len(methoden), len(origins),
             origins[0], origins[-1])
    voorsp = run_rolling(f, cfg, methoden, origins, hertrain_elke_dagen=hertrain)
    voorsp.to_parquet(cfg.processed_dir / uitvoer_bestand, index=False)
    ruw = samenvatting(voorsp, "p10", "p90")
    kal = samenvatting(voorsp, "p10_kal", "p90_kal")
    tabel = ruw.merge(kal[["methode", "horizon_dag", "dekking80", "breedte80", "pinball_p10", "pinball_p90"]],
                      on=["methode", "horizon_dag"], suffixes=("", "_kal"))
    pad = rapport or (cfg.root / "reports" / "methodenvergelijking.md")
    pad.parent.mkdir(parents=True, exist_ok=True)
    pad.write_text(schrijf_rapport(tabel, origins, cfg), encoding="utf-8")
    log.info("rapport -> %s", pad)
    return tabel


def _md_tabel(df: pd.DataFrame, kolommen: dict[str, str], fmt: dict[str, str]) -> str:
    kop = "| " + " | ".join(kolommen.values()) + " |"
    lijn = "|" + "|".join("---" for _ in kolommen) + "|"
    rijen = []
    for _, r in df.iterrows():
        cellen = []
        for k in kolommen:
            v = r[k]
            cellen.append(fmt.get(k, "{}").format(v) if pd.notna(v) else "")
        rijen.append("| " + " | ".join(cellen) + " |")
    return "\n".join([kop, lijn, *rijen])


def schrijf_rapport(tabel: pd.DataFrame, origins: list[date], cfg: Config) -> str:
    delen = [
        "# Methodenvergelijking (rolling-origin backtest)\n",
        (f"Voorspelmomenten: {origins[0]} t/m {origins[-1]} ({len(origins)} dagen), elke dag om "
        f"{cfg.publicatie_uur_lokaal}:00 lokaal. Trainingsvenster {cfg.rolling_venster_dagen} dagen, hertrainen elke "
        f"{cfg.hertrain_elke_dagen} dagen, conformal-kalibratie op {cfg.kalibratie_venster_dagen} dagen.\n"),
        ("Fouten in EUR/MWh. `dekking80` = aandeel werkelijke prijzen binnen P10-P90 (doel 0,80). "
        "Kolommen met `_kal` zijn na conformal-correctie.\n"),
    ]
    kolommen = {"methode": "methode", "n": "n", "mae": "MAE", "rmse": "RMSE", "pinball_p50": "pinball P50",
                "pinball_p10": "pinball P10", "pinball_p90": "pinball P90", "dekking80": "dekking80",
                "breedte80": "breedte80", "dekking80_kal": "dekking80 kal", "breedte80_kal": "breedte80 kal"}
    fmt = {"n": "{:.0f}", "mae": "{:.2f}", "rmse": "{:.2f}", "pinball_p50": "{:.2f}", "pinball_p10": "{:.2f}",
           "pinball_p90": "{:.2f}", "dekking80": "{:.3f}", "breedte80": "{:.1f}", "dekking80_kal": "{:.3f}",
           "breedte80_kal": "{:.1f}"}
    for k, g in tabel.groupby("horizon_dag"):
        delen.append(f"\n## Dag {k} vooruit\n")
        delen.append(_md_tabel(g.sort_values("mae"), kolommen, fmt))
        delen.append("")
    beste = tabel.loc[tabel.groupby("horizon_dag")["mae"].idxmin(), ["horizon_dag", "methode", "mae"]]
    delen.append("\n## Beste methode per horizon (op MAE)\n")
    delen.append(_md_tabel(beste, {"horizon_dag": "dag", "methode": "methode", "mae": "MAE"},
                           {"horizon_dag": "{:.0f}", "mae": "{:.2f}"}))
    return "\n".join(delen) + "\n"
