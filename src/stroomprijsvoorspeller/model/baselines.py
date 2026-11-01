"""Baselines: puntvoorspellingen die geen model nodig hebben. Ze komen uit de featurematrix.

a. laatste_dag  zelfde uur op de laatst bekende dag (D+1). "Gisteren" bestaat niet voor dag 2+: de laatst bekende
                dag is het dichtstbijzijnde equivalent.
b. vorige_week  zelfde uur, zeven dagen voor het doeluur (voor horizon <= 5 altijd bekend)
c. profiel_4w   gemiddeld uurprofiel van de laatste 28 bekende dagen
"""

from __future__ import annotations

import pandas as pd

from stroomprijsvoorspeller.processing.features import BASELINE_KOLOMMEN

BASELINES = tuple(BASELINE_KOLOMMEN)


def is_baseline(naam: str) -> bool:
    return naam in BASELINE_KOLOMMEN


def baseline_voorspelling(features: pd.DataFrame, naam: str, kwantiel_namen=("p10", "p50", "p90")) -> pd.DataFrame:
    """Puntvoorspelling als alle kwantielen tegelijk; de conformal-stap maakt er later een interval van."""
    kolom = BASELINE_KOLOMMEN[naam]
    waarde = features[kolom].to_numpy(dtype=float)
    return pd.DataFrame({k: waarde for k in kwantiel_namen}, index=features.index)
