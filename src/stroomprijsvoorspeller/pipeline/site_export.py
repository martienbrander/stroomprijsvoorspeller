"""Schrijft de JSON voor de site en de API, en de leverancierslijst.

Bestanden:
- site/data/forecast.json           de voorspelling; dit leest de pagina zelf
- site/api/v1/voorspelling.json     dezelfde inhoud onder een vast API-pad (besluit 37)
- site/data/leveranciers.json       leveranciers met een dynamisch contract, uit data/leveranciers.yaml

De velden staan beschreven in API.md. Binnen v1 komen er alleen velden bij; bestaande veranderen niet (besluit 52).
"""

from __future__ import annotations

import json
import logging
from datetime import date, timedelta
from pathlib import Path

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

SCORE_DAGEN = 30           # de scores op de site gaan over zoveel voorspelmomenten terug
SCORE_HISTORIE_MARGE = 10  # extra dagen historie, zodat het venster ook met ontbrekende dagen gevuld is
FEESTDAG_EFFECT_DAGEN = 730
BRONNEN = ("Prijzen: ENTSO-E Transparency Platform. Oudere prijzen en dagen die daar ontbreken: Energy-Charts "
           "(Fraunhofer ISE), data Bundesnetzagentur | SMARD.de, CC BY 4.0, of EnergyZero. "
           "Weer: Open-Meteo, CC BY 4.0.")
LEVERANCIER_VELDEN = ["naam", "inkoopvergoeding_ct_kwh_excl_btw", "vaste_kosten_maand_eur_incl_btw", "status",
                      "peildatum", "bron_url"]


def site_dir(cfg: Config) -> Path:
    return cfg.root / "site"


# ---------- opmaak ----------

def _num(x, decimalen: int = 2) -> float | None:
    """Afgerond getal voor de JSON; None als de waarde ontbreekt."""
    return None if pd.isna(x) else round(float(x), decimalen)


def _iso_lokaal(ts) -> str:
    return pd.Timestamp(ts).tz_convert(TZ).isoformat()


def _iso_utc(ts) -> str | None:
    if ts is None or pd.isna(ts):
        return None
    return pd.Timestamp(ts).tz_convert("UTC").strftime("%Y-%m-%dT%H:%M:%SZ")


# ---------- onderdelen van de voorspelling ----------

def scores_per_horizon(cfg: Config, prijzen: pd.DataFrame, origin: date) -> dict:
    """MAE, dekking en rMAE per horizon over de laatste SCORE_DAGEN voorspelmomenten met bekende uitkomsten.

    Resultaat: {"periode_dagen": 30, "mae": {horizon: ...}, "dekking": {...}, "rmae": {...}, "n_dagen": {...}}.
    """
    methode = cfg.operationele_methode
    hist = archive.historie(cfg, methode, prijzen, dagen=SCORE_DAGEN + SCORE_HISTORIE_MARGE, tot=origin)
    uit = {"periode_dagen": SCORE_DAGEN, "mae": {}, "dekking": {}, "rmae": {}, "n_dagen": {}}
    if hist.empty:
        return uit
    tot = pd.Timestamp(origin)
    in_venster = (hist["origin"] < tot) & (hist["origin"] >= tot - pd.Timedelta(days=SCORE_DAGEN))
    model = hist[in_venster & (hist["methode"] == methode)].dropna(subset=[DOEL])
    uit["rmae"] = reliability.rmae_per_horizon(hist, methode, tot=tot, dagen=SCORE_DAGEN)
    for horizon, g in model.groupby("horizon_dag"):
        uit["mae"][int(horizon)] = mae(g[DOEL], g["p50"])
        uit["dekking"][int(horizon)] = dekking(g[DOEL], g["p10_kal"], g["p90_kal"])
        uit["n_dagen"][int(horizon)] = int(g["origin"].nunique())
    return uit


def dagen_lijst(alles: pd.DataFrame, origin: date, scores: dict, ds: Dagsoorten | None = None) -> list[dict]:
    """Per lokale dag: horizon, betrouwbaarheid (besluit 34) en de recente afwijking; met `ds` ook dagsoort en feestdag."""
    uit = []
    dag_per_rij = local_date(pd.DatetimeIndex(alles["time_utc"]))
    for dag in sorted(pd.unique(dag_per_rij)):
        uren = alles[dag_per_rij == dag]
        horizon = (dag - origin).days
        if uren["bekend"].astype(bool).all():
            betrouwbaarheid, afwijking_ct = "bekend", 0.0
        else:
            band = float((uren["p90_kal"] - uren["p10_kal"]).mean())
            niveau = float(uren["p50"].abs().mean())
            betrouwbaarheid = reliability.betrouwbaarheid(scores["rmae"].get(horizon), band, niveau)
            mae_horizon = scores["mae"].get(horizon)
            afwijking_ct = _num(mae_horizon / 10, 2) if mae_horizon is not None else None   # EUR/MWh -> ct/kWh
        info = {"datum": str(dag), "horizon_dag": horizon, "betrouwbaarheid": betrouwbaarheid,
                "verwachte_afwijking_ct": afwijking_ct}
        if ds:
            info |= {"dagsoort": ds.soort(dag), "feestdag": ds.feestdag(dag)}
        uit.append(info)
    return uit


def uren_lijst(alles: pd.DataFrame) -> list[dict]:
    """Per uur: lokale tijd, P50 en de gekalibreerde grenzen. Bij bekende uren zijn alle drie de echte prijs."""
    return [{"tijd": _iso_lokaal(r.time_utc), "p10": _num(r.p10_kal), "p50": _num(r.p50), "p90": _num(r.p90_kal),
             "bekend": bool(r.bekend)} for r in alles.sort_values("time_utc").itertuples()]


def kwartieren_lijst(cfg: Config, bekende_dagen: list[date]) -> list[dict]:
    """De kwartierprijzen van de beurs voor de bekende dagen (de verwachting zelf is per uur)."""
    pad = cfg.processed_dir / dataset.KWARTIER_BESTAND
    if not pad.exists() or not bekende_dagen:
        return []
    k = pd.read_parquet(pad)
    k["time_utc"] = pd.to_datetime(k["time_utc"], utc=True)
    k = k[local_date(pd.DatetimeIndex(k["time_utc"])).isin(bekende_dagen)]
    return [{"tijd": _iso_lokaal(t), "prijs": _num(p)} for t, p in zip(k["time_utc"], k[PRIJS], strict=True)]


def feestdag_effect(cfg: Config, prijzen: pd.DataFrame, origin: date, dagen: int = FEESTDAG_EFFECT_DAGEN) -> dict:
    """Prijseffect van feestdagen over de laatste `dagen` dagen (besluit 53)."""
    recent = prijzen[prijzen["time_utc"] >= pd.Timestamp(origin - timedelta(days=dagen), tz="UTC")]
    if recent.empty:
        return {"pct_tov_werkdag": None, "aantal_feestdagen": 0, "vanaf": None, "tot": None}
    effecten = dag_effecten(recent, cfg.root, PRIJS)
    return {"pct_tov_werkdag": effecten["feestdag"]["pct_tov_werkdag"],
            "aantal_feestdagen": effecten["feestdag"]["aantal_dagen"],
            "vanaf": effecten["vanaf"], "tot": effecten["tot"]}


def _scores_plat(scores: dict) -> dict:
    """De scores zoals ze in de JSON staan: mae_dagK, dekking80_dagK en n_dagen_dagK per horizon K."""
    plat = {"periode_dagen": scores["periode_dagen"]}
    for k in sorted(scores["mae"]):
        plat[f"mae_dag{k}"] = _num(scores["mae"][k])
        plat[f"dekking80_dag{k}"] = _num(scores["dekking"].get(k), 3)
        plat[f"n_dagen_dag{k}"] = scores["n_dagen"].get(k)
    return plat


# ---------- de bestanden ----------

def maak_forecast_json(cfg: Config, alles: pd.DataFrame, prijzen: pd.DataFrame, origin: date, nu: pd.Timestamp,
                       run_type: str, bundel: dict | None) -> dict:
    """De voorspelling als JSON-klaar woordenboek. `alles` zijn de rijen van de run (bekende en voorspelde uren)."""
    scores = scores_per_horizon(cfg, prijzen, origin)
    dagen = dagen_lijst(alles, origin, scores, Dagsoorten(cfg.root))
    bekende_dagen = [date.fromisoformat(d["datum"]) for d in dagen if d["betrouwbaarheid"] == "bekend"]
    weer_uitgegeven = alles["weer_uitgegeven_utc"].dropna().max() if "weer_uitgegeven_utc" in alles else None
    return {
        "gegenereerd_utc": _iso_utc(nu),
        "run_type": run_type,
        "voorspelmoment": str(origin),
        "prijzen_bekend_tot": str(max(bekende_dagen)) if bekende_dagen else None,
        "model": {"methode": cfg.operationele_methode, "getraind_tot": str(bundel["origin"]) if bundel else None,
                  "venster_dagen": cfg.rolling_venster_dagen},
        "weer_uitgegeven_utc": _iso_utc(weer_uitgegeven),
        "biedzone": cfg.biedzone,
        "eenheid": "EUR/MWh",
        "uren": uren_lijst(alles),
        "kwartieren": kwartieren_lijst(cfg, bekende_dagen),
        "dagen": dagen,
        "feestdag_effect": feestdag_effect(cfg, prijzen, origin),
        "scores": _scores_plat(scores),
        "bronnen": BRONNEN,
    }


def maak_leveranciers_json(cfg: Config) -> dict:
    """De leveranciers met een dynamisch contract uit data/leveranciers.yaml, op naam gesorteerd (besluit 36)."""
    data = yaml.safe_load((cfg.root / "data" / "leveranciers.yaml").read_text(encoding="utf-8"))
    items = [{veld: lev.get(veld) for veld in LEVERANCIER_VELDEN}
             for lev in data["leveranciers"] if lev.get("dynamisch_aanbod") is True]
    items.sort(key=lambda x: x["naam"].casefold())
    return {"peildatum_lijst": data.get("peildatum_lijst"), "bron_register": data.get("bron_register"),
            "leveranciers": items}


def _schrijf(pad: Path, obj: dict) -> None:
    pad.parent.mkdir(parents=True, exist_ok=True)
    pad.write_text(json.dumps(obj, ensure_ascii=False, separators=(",", ":"), default=str) + "\n", encoding="utf-8")


def schrijf_site(cfg: Config, alles: pd.DataFrame, prijzen: pd.DataFrame, origin: date, nu: pd.Timestamp,
                 run_type: str, bundel: dict | None) -> Path:
    """Schrijft de drie JSON-bestanden en geeft het pad van forecast.json terug."""
    forecast = maak_forecast_json(cfg, alles, prijzen, origin, nu, run_type, bundel)
    pad = site_dir(cfg) / "data" / "forecast.json"
    _schrijf(pad, forecast)
    _schrijf(site_dir(cfg) / "api" / "v1" / "voorspelling.json", forecast)
    _schrijf(site_dir(cfg) / "data" / "leveranciers.json", maak_leveranciers_json(cfg))
    log.info("site: %d uren, %d dagen -> %s", len(forecast["uren"]), len(forecast["dagen"]), pad)
    return pad
