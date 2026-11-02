"""Laadt config.yaml naar een onveranderlijke Config."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class Weerpunt:
    naam: str
    lat: float
    lon: float
    type: str


@dataclass(frozen=True)
class Config:
    root: Path
    tijdzone: str
    biedzone: str
    data_start: str
    weer_start: str
    raw_dir: Path
    processed_dir: Path
    prijsbron: str
    kwartier_vanaf: str
    weer_model: str
    weer_variabelen: tuple[str, ...]
    forecast_dagen: int
    lead_dagen: tuple[int, ...]
    weerpunten: tuple[Weerpunt, ...]
    publicatie_uur_lokaal: int
    horizon_dagen: tuple[int, ...]
    backtest_horizon_dagen: tuple[int, ...]
    kwantielen: tuple[float, ...]
    operationele_methode: str
    rolling_venster_dagen: int
    recente_prijs_dagen: int
    profiel_dagen: int
    hertrain_elke_dagen: int
    kalibratie_venster_dagen: int
    lightgbm_params: dict

    def weerpunt(self, naam: str) -> Weerpunt:
        for p in self.weerpunten:
            if p.naam == naam:
                return p
        raise KeyError(naam)


def find_config_path(start: Path | None = None) -> Path:
    """Zoekt config.yaml: eerst env EPV_CONFIG, dan omhoog vanaf de werkmap, dan de projectroot van dit package."""
    env = os.environ.get("EPV_CONFIG")
    if env:
        return Path(env)
    here = (start or Path.cwd()).resolve()
    for d in [here, *here.parents]:
        kandidaat = d / "config.yaml"
        if kandidaat.exists():
            return kandidaat
    pakket_root = Path(__file__).resolve().parents[2] / "config.yaml"
    if pakket_root.exists():
        return pakket_root
    raise FileNotFoundError("config.yaml niet gevonden")


def load_config(path: Path | str | None = None) -> Config:
    cfg_path = Path(path) if path else find_config_path()
    with open(cfg_path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    root = cfg_path.parent
    data = raw["data"]
    weer = raw["weer"]
    prijzen = raw.get("prijzen", {})
    voorspelling = raw["voorspelling"]
    model = raw["model"]
    punten = tuple(Weerpunt(p["naam"], float(p["lat"]), float(p["lon"]), p.get("type", "land")) for p in weer["punten"])
    namen = [p.naam for p in punten]
    if len(set(namen)) != len(namen):
        raise ValueError("weerpunt-namen moeten uniek zijn")
    return Config(
        root=root,
        tijdzone=raw.get("tijdzone", "Europe/Amsterdam"),
        biedzone=raw.get("biedzone", "NL"),
        data_start=str(data["start"]),
        weer_start=str(data["weer_start"]),
        raw_dir=root / data.get("raw_dir", "data/raw"),
        processed_dir=root / data.get("processed_dir", "data/processed"),
        prijsbron=prijzen.get("bron", "energy_charts"),
        kwartier_vanaf=str(prijzen.get("kwartier_vanaf", "2025-10-01")),
        weer_model=weer.get("model", "best_match"),
        weer_variabelen=tuple(weer["variabelen"]),
        forecast_dagen=int(weer.get("forecast_dagen", 7)),
        lead_dagen=tuple(int(x) for x in weer["lead_dagen"]),
        weerpunten=punten,
        publicatie_uur_lokaal=int(voorspelling.get("publicatie_uur_lokaal", 13)),
        horizon_dagen=tuple(int(x) for x in voorspelling["horizon_dagen"]),
        backtest_horizon_dagen=tuple(int(x) for x in voorspelling.get("backtest_horizon_dagen",
                                                                       voorspelling["horizon_dagen"])),
        kwantielen=tuple(float(q) for q in model["kwantielen"]),
        operationele_methode=str(model.get("methode", "lightgbm")),
        rolling_venster_dagen=int(model.get("rolling_venster_dagen", 365)),
        recente_prijs_dagen=int(model.get("recente_prijs_dagen", 7)),
        profiel_dagen=int(model.get("profiel_dagen", 28)),
        hertrain_elke_dagen=int(model.get("hertrain_elke_dagen", 7)),
        kalibratie_venster_dagen=int(model.get("kalibratie_venster_dagen", 30)),
        lightgbm_params=dict(model.get("lightgbm", {})),
    )
