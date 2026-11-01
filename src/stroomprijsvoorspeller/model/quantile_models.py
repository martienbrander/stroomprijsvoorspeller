"""Kwantielmodellen met één interface: fit(X, y) en predict(X) -> DataFrame met kolommen p10, p50, p90.

- LightGBMKwantiel  gradient boosting met pinball-verlies, één model per kwantiel
- LineairKwantiel   lineaire kwantielregressie (statsmodels QuantReg) op een compacte featureset
- Combinatie        gemiddelde van meerdere modellen per kwantiel
"""

from __future__ import annotations

import logging
import re
import warnings

import numpy as np
import pandas as pd

log = logging.getLogger(__name__)

PER_PUNT = re.compile(r"^\w+__\w+$")  # kolommen per weerpunt, bijv. flevoland__wind_speed_100m
DUMMIES = ("uur_lokaal", "weekdag")


def kwantiel_naam(q: float) -> str:
    return f"p{round(q * 100):02d}"


def transformeer(y, naam: str | None):
    """Variantiestabilisatie van het doel. asinh werkt ook bij negatieve prijzen (anders dan log)."""
    y = np.asarray(y, dtype=float)
    return np.arcsinh(y) if naam == "asinh" else y


def terug(z, naam: str | None):
    z = np.asarray(z, dtype=float)
    return np.sinh(z) if naam == "asinh" else z


def sorteer_kwantielen(pred: pd.DataFrame) -> pd.DataFrame:
    """Zorgt dat p10 <= p50 <= p90 per rij (kwantielen kunnen anders kruisen)."""
    waarden = np.sort(pred.to_numpy(dtype=float), axis=1)
    return pd.DataFrame(waarden, index=pred.index, columns=pred.columns)


class LightGBMKwantiel:
    def __init__(self, kwantielen=(0.1, 0.5, 0.9), params: dict | None = None, transformatie: str | None = None):
        self.kwantielen = tuple(kwantielen)
        self.transformatie = transformatie
        self.params = {"n_estimators": 400, "learning_rate": 0.05, "num_leaves": 31, "min_child_samples": 30,
                       "subsample": 0.8, "subsample_freq": 1, "colsample_bytree": 0.8}
        self.params.update(params or {})
        self.modellen = {}
        self.kolommen: list[str] = []

    def fit(self, X: pd.DataFrame, y: pd.Series):
        import lightgbm as lgb

        self.kolommen = list(X.columns)
        yt = transformeer(y, self.transformatie)
        for q in self.kwantielen:
            m = lgb.LGBMRegressor(objective="quantile", alpha=q, verbose=-1, **self.params)
            m.fit(X, yt)
            self.modellen[q] = m
        return self

    def predict(self, X: pd.DataFrame) -> pd.DataFrame:
        uit = pd.DataFrame({kwantiel_naam(q): terug(self.modellen[q].predict(X[self.kolommen]), self.transformatie)
                            for q in self.kwantielen}, index=X.index)
        return sorteer_kwantielen(uit)

    def belang(self) -> pd.Series:
        """Feature-belang (gain) van het P50-model."""
        m = self.modellen.get(0.5) or next(iter(self.modellen.values()))
        return pd.Series(m.booster_.feature_importance("gain"), index=self.kolommen).sort_values(ascending=False)


class LineairKwantiel:
    """Lineaire kwantielregressie. Gebruikt standaard alleen de geaggregeerde weerfeatures (niet per punt), plus
    prijsfeatures, horizon en dummies voor uur en weekdag. Features worden gestandaardiseerd; NaN -> mediaan."""

    def __init__(self, kwantielen=(0.1, 0.5, 0.9), kolommen: list[str] | None = None, max_iter: int = 2000,
                 transformatie: str | None = "asinh"):
        self.kwantielen = tuple(kwantielen)
        self.kolommen_opgegeven = kolommen
        self.max_iter = max_iter
        self.transformatie = transformatie
        self.kolommen: list[str] = []
        self.mediaan = None
        self.gem = None
        self.std = None
        self.ontwerp_kolommen: list[str] = []
        self.coef: dict[float, np.ndarray] = {}

    def _selecteer(self, X: pd.DataFrame) -> list[str]:
        if self.kolommen_opgegeven is not None:
            return [c for c in self.kolommen_opgegeven if c in X.columns]
        return [c for c in X.columns if not PER_PUNT.match(c) or c.startswith("wind_")]

    def _ontwerp(self, X: pd.DataFrame, fit: bool) -> np.ndarray:
        num = X[self.kolommen].astype(float)
        if fit:
            self.mediaan = num.median()
            num = num.fillna(self.mediaan)
            self.gem = num.mean()
            self.std = num.std().replace(0, 1.0).fillna(1.0)
        else:
            num = num.fillna(self.mediaan)
        num = (num - self.gem) / self.std
        delen = [num]
        for d in DUMMIES:
            if d in X.columns:
                cat = pd.Categorical(X[d].astype(int), categories=range(24 if d == "uur_lokaal" else 7))
                dum = pd.get_dummies(cat, prefix=d, drop_first=True, dtype=float)
                dum.index = X.index
                delen.append(dum)
        M = pd.concat(delen, axis=1)
        if fit:
            # constante kolommen weg, anders is de matrix singulier
            variatie = M.std()
            self.ontwerp_kolommen = list(variatie[variatie > 1e-12].index)
        M = M.reindex(columns=self.ontwerp_kolommen, fill_value=0.0)
        return np.column_stack([np.ones(len(M)), M.to_numpy(dtype=float)])

    def fit(self, X: pd.DataFrame, y: pd.Series):
        from statsmodels.regression.quantile_regression import QuantReg

        self.kolommen = [c for c in self._selecteer(X) if c not in DUMMIES]
        A = self._ontwerp(X, fit=True)
        yv = transformeer(y, self.transformatie)
        for q in self.kwantielen:
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                res = QuantReg(yv, A).fit(q=q, max_iter=self.max_iter, p_tol=1e-5)
            self.coef[q] = np.asarray(res.params, dtype=float)
        return self

    def predict(self, X: pd.DataFrame) -> pd.DataFrame:
        A = self._ontwerp(X, fit=False)
        uit = pd.DataFrame({kwantiel_naam(q): terug(A @ self.coef[q], self.transformatie) for q in self.kwantielen},
                           index=X.index)
        return sorteer_kwantielen(uit)


class Combinatie:
    def __init__(self, leden: list):
        self.leden = leden

    def fit(self, X: pd.DataFrame, y: pd.Series):
        for m in self.leden:
            m.fit(X, y)
        return self

    def predict(self, X: pd.DataFrame) -> pd.DataFrame:
        preds = [m.predict(X) for m in self.leden]
        gem = sum(p.to_numpy(dtype=float) for p in preds) / len(preds)
        return sorteer_kwantielen(pd.DataFrame(gem, index=X.index, columns=preds[0].columns))


MODELNAMEN = ("lineair", "lightgbm", "lightgbm_asinh", "combinatie")


def maak_model(naam: str, kwantielen=(0.1, 0.5, 0.9), lightgbm_params: dict | None = None):
    if naam == "lightgbm":
        return LightGBMKwantiel(kwantielen, lightgbm_params)
    if naam == "lightgbm_asinh":
        return LightGBMKwantiel(kwantielen, lightgbm_params, transformatie="asinh")
    if naam == "lineair":
        return LineairKwantiel(kwantielen)
    if naam == "lineair_ruw":
        return LineairKwantiel(kwantielen, transformatie=None)
    if naam == "combinatie":
        return Combinatie([LineairKwantiel(kwantielen), LightGBMKwantiel(kwantielen, lightgbm_params)])
    raise KeyError(f"onbekend model: {naam}")
