from pathlib import Path

import pytest

from stroomprijsvoorspeller.config import Config, Weerpunt


def maak_config(root: Path | None = None, **over) -> Config:
    """Kleine testconfig met twee weerpunten (zee en land)."""
    root = root or Path(".")
    waarden = {
        "root": root, "tijdzone": "Europe/Amsterdam", "biedzone": "NL",
        "data_start": "2022-11-01", "weer_start": "2024-03-01",
        "raw_dir": root / "raw", "processed_dir": root / "processed",
        "prijsbron": "energy_charts", "kwartier_vanaf": "2025-10-01",
        "weer_model": "best_match",
        "weer_variabelen": ("wind_speed_100m", "shortwave_radiation", "cloud_cover", "temperature_2m"),
        "forecast_dagen": 7, "lead_dagen": (1, 2, 3, 4, 5, 6, 7),
        "weerpunten": (Weerpunt("a", 53.0, 4.0, "zee"), Weerpunt("b", 52.0, 5.0, "land")),
        "publicatie_uur_lokaal": 13, "horizon_dagen": (2, 3, 4, 5), "backtest_horizon_dagen": (2, 3, 4, 5, 6, 7),
        "kwantielen": (0.1, 0.5, 0.9), "operationele_methode": "lightgbm", "rolling_venster_dagen": 30, "recente_prijs_dagen": 7,
        "profiel_dagen": 28, "hertrain_elke_dagen": 7, "kalibratie_venster_dagen": 30,
        "lightgbm_params": {"n_estimators": 30, "learning_rate": 0.1, "num_leaves": 7, "min_child_samples": 5},
    }
    waarden.update(over)
    return Config(**waarden)


@pytest.fixture
def testconfig(tmp_path):
    return maak_config(tmp_path)
