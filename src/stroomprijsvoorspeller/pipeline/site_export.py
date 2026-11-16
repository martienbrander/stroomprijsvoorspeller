"""Schrijft de JSON voor de site (contract: site/ontwerpen/README.md) en de leverancierslijst.

Bestanden: site/data/forecast.json, site/data/leveranciers.json en dezelfde forecast als site/api/v1/voorspelling.json
(besluit 37; documentatie van de API volgt in fase 5).
"""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import yaml

from stroomprijsvoorspeller.config import Config
from stroomprijsvoorspeller.evaluation import reliability
from stroomprijsvoorspeller.evaluation.metrics import dekking, mae
from stroomprijsvoorspeller.pipeline import archive
from stroomprijsvoorspeller.processing import dataset
from stroomprijsvoorspeller.processing.dagsoort import Dagsoorten, dag_effecten
from stroomprijsvoorspeller.processing.features import DOEL, PRIJS
from stroomprijsvoorspeller.timeutil import TZ, local_date

log = logging.getLogger(__name__)

SCORE_DAGEN = 30
LEVERANCIER_VELDEN = ["naam", "inkoopvergoeding_ct_kwh_excl_btw", "vaste_kosten_maand_eur_incl_btw", "status", "peildatum", "bron_url"]


def site_dir(cfg: Config) -> Path:
    return cfg.root / "site"


def _num(x, decimalen: int = 2):
    if x is None or (isinstance(x, float) and np.isnan(x)) or pd.isna(x):
        return None
    return round(float(x), decimalen)


def _iso_lokaal(ts) -> str:
    return pd.Timestamp(ts).tz_convert(TZ).isoformat()


def _iso_utc(ts) -> str | None:
    if ts is None or pd.isna(ts):
        return None
    return pd.Timestamp(ts).tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")


def scores_per_horizon(cfg: Config, prijzen: pd.DataFrame, origin: date) -> dict:
    """MAE, dekking en rMAE per horizon over de laatste SCORE_DAGEN voorspelmomenten met bekende uitkomsten."""
    methode = cfg.operationele_methode
    hist = archive.historie(cfg, methode, prijzen, dagen=SCORE_DAGEN + 10, tot=origin)
    uit = {"periode_dagen": SCORE_DAGEN, "mae": {}, "dekking": {}, "rmae": {}, "n_dagen": {}}
    if hist.empty:
        return uit
    tot = pd.Timestamp(origin)
    h = hist[(hist["origin"] < tot) & (hist["origin"] >= tot - pd.Timedelta(days=SCORE_DAGEN))].dropna(subset=[DOEL])
    uit["rmae"] = reliability.rmae_per_horizon(hist, methode, tot=tot, dagen=SCORE_DAGEN)
    for k, g in h[h["methode"] == methode].groupby("horizon_dag"):
        uit["mae"][int(k)] = mae(g[DOEL], g["p50"])
        uit["dekking"][int(k)] = dekking(g[DOEL], g["p10_kal"], g["p90_kal"])
        uit["n_dagen"][int(k)] = int(g["origin"].nunique())
    return uit


def dagen_lijst(alles: pd.DataFrame, origin: date, scores: dict, ds: Dagsoorten | None = None) -> list[dict]:
    uit = []
    dag = local_date(pd.DatetimeIndex(alles["time_utc"]))
    for d in sorted(pd.unique(dag)):
        g = alles[dag == d]
        k = (d - origin).days
        extra = {"dagsoort": ds.soort(d), "feestdag": ds.feestdag(d)} if ds else {}
        if g["bekend"].astype(bool).all():
            uit.append({"datum": str(d), "horizon_dag": k, "betrouwbaarheid": "bekend", "verwachte_afwijking_ct": 0.0, **extra})
            continue
        band = float((g["p90_kal"] - g["p10_kal"]).mean())
        niveau = float(g["p50"].abs().mean())
        code = reliability.betrouwbaarheid(scores["rmae"].get(k), band, niveau)
        m = scores["mae"].get(k)
        uit.append({"datum": str(d), "horizon_dag": k, "betrouwbaarheid": code,
                    "verwachte_afwijking_ct": _num(m / 10, 2) if m is not None else None, **extra})
    return uit


def feestdag_effect(cfg: Config, prijzen: pd.DataFrame, origin: date, dagen: int = 730) -> dict:
    """Prijseffect van feestdagen over de laatste `dagen` dagen, voor de melding op de site."""
    p = prijzen[prijzen["time_utc"] >= pd.Timestamp(origin - timedelta(days=dagen), tz="UTC")]
    if p.empty:
        return {"pct_tov_werkdag": None, "aantal_feestdagen": 0, "vanaf": None, "tot": None}
    e = dag_effecten(p, cfg.root, PRIJS)
    return {"pct_tov_werkdag": e["feestdag"]["pct_tov_werkdag"], "aantal_feestdagen": e["feestdag"]["aantal_dagen"],
            "vanaf": e["vanaf"], "tot": e["tot"]}


def kwartieren_lijst(cfg: Config, bekende_dagen: list[date]) -> list[dict]:
    pad = cfg.processed_dir / dataset.KWARTIER_BESTAND
    if not pad.exists() or not bekende_dagen:
        return []
    k = pd.read_parquet(pad)
    k["time_utc"] = pd.to_datetime(k["time_utc"], utc=True)
    dag = local_date(pd.DatetimeIndex(k["time_utc"]))
    k = k[pd.Index(dag).isin(bekende_dagen)]
    return [{"tijd": _iso_lokaal(t), "prijs": _num(p)} for t, p in zip(k["time_utc"], k[PRIJS])]


def maak_forecast_json(cfg: Config, alles: pd.DataFrame, prijzen: pd.DataFrame, origin: date, nu: pd.Timestamp,
                       run_type: str, bundel: dict | None) -> dict:
    scores = scores_per_horizon(cfg, prijzen, origin)
    dagen = dagen_lijst(alles, origin, scores, Dagsoorten(cfg.root))
    bekende_dagen = [date.fromisoformat(d["datum"]) for d in dagen if d["betrouwbaarheid"] == "bekend"]
    uren = [{"tijd": _iso_lokaal(r.time_utc), "p10": _num(r.p10_kal), "p50": _num(r.p50), "p90": _num(r.p90_kal),
             "bekend": bool(r.bekend)} for r in alles.sort_values("time_utc").itertuples()]
    sc = {"periode_dagen": scores["periode_dagen"]}
    for k in sorted(scores["mae"]):
        sc[f"mae_dag{k}"] = _num(scores["mae"][k])
        sc[f"dekking80_dag{k}"] = _num(scores["dekking"].get(k), 3)
        sc[f"n_dagen_dag{k}"] = scores["n_dagen"].get(k)
    return {
        "gegenereerd_utc": _iso_utc(nu),
        "run_type": run_type,
        "voorspelmoment": str(origin),
        "prijzen_bekend_tot": str(origin + timedelta(days=1)) if bekende_dagen and max(bekende_dagen) > origin else str(max(bekende_dagen)) if bekende_dagen else None,
        "model": {"methode": cfg.operationele_methode, "getraind_tot": str(bundel["origin"]) if bundel else None,
                  "venster_dagen": cfg.rolling_venster_dagen},
        "weer_uitgegeven_utc": _iso_utc(alles["weer_uitgegeven_utc"].dropna().max()) if "weer_uitgegeven_utc" in alles else None,
        "biedzone": cfg.biedzone,
        "eenheid": "EUR/MWh",
        "uren": uren,
        "kwartieren": kwartieren_lijst(cfg, bekende_dagen),
        "dagen": dagen,
        "feestdag_effect": feestdag_effect(cfg, prijzen, origin),
        "scores": sc,
        "bronnen": "Prijzen: Energy-Charts (Fraunhofer ISE), data Bundesnetzagentur | SMARD.de, CC BY 4.0. Weer: Open-Meteo, CC BY 4.0.",
    }


def maak_leveranciers_json(cfg: Config) -> dict:
    data = yaml.safe_load((cfg.root / "data" / "leveranciers.yaml").read_text(encoding="utf-8"))
    items = [{veld: lev.get(veld) for veld in LEVERANCIER_VELDEN} for lev in data["leveranciers"] if lev.get("dynamisch_aanbod") is True]
    items.sort(key=lambda x: x["naam"].casefold())
    return {"peildatum_lijst": data.get("peildatum_lijst"), "bron_register": data.get("bron_register"), "leveranciers": items}


def _schrijf(pad: Path, obj: dict) -> None:
    pad.parent.mkdir(parents=True, exist_ok=True)
    pad.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":"), default=str) + "\n", encoding="utf-8")


def schrijf_site(cfg: Config, alles: pd.DataFrame, prijzen: pd.DataFrame, origin: date, nu: pd.Timestamp,
                 run_type: str, bundel: dict | None) -> Path:
    forecast = maak_forecast_json(cfg, alles, prijzen, origin, nu, run_type, bundel)
    pad = site_dir(cfg) / "data" / "forecast.json"
    _schrijf(pad, forecast)
    _schrijf(site_dir(cfg) / "api" / "v1" / "voorspelling.json", forecast)
    _schrijf(site_dir(cfg) / "data" / "leveranciers.json", maak_leveranciers_json(cfg))
    log.info("site: %d uren, %d dagen -> %s", len(forecast["uren"]), len(forecast["dagen"]), pad)
    return pad
