"""De dagelijkse run (besluit 33, 49, 50).

Soorten runs:
- hoofd:      prijzen en weer ophalen (ook de historische weersverwachtingen), datasets en features bijwerken,
              gemiste dagen inhalen, model hertrainen als het ouder is dan `hertrain_elke_dagen`, voorspellen,
              kalibreren, archiveren en de JSON voor de site schrijven.
- verversing: alleen de actuele weersverwachting (en prijzen) ophalen en opnieuw voorspellen met het bestaande model.
- inhaal:     een gemiste hoofdrun, achteraf uitgerekend met de weersverwachting zoals die toen was (previous runs),
              precies zoals de backtest. Zo blijft de historie voor kalibratie en scores zonder gaten.
- auto:       hoofd als er voor het huidige voorspelmoment nog geen hoofdrun is, anders verversing.

Het voorspelmoment (origin) is de dag waarop de laatst bekende day-ahead dag bekend werd: laatst bekende dag min 1.
Zijn de prijzen van morgen nog niet binnen, dan is origin gisteren en toont de site één dag minder vooruit.
"""

from __future__ import annotations

import logging
import time
from datetime import date, timedelta

import joblib
import numpy as np
import pandas as pd

from stroomprijsvoorspeller.config import Config
from stroomprijsvoorspeller.evaluation import blocks
from stroomprijsvoorspeller.evaluation.compare import FEATURES_BESTAND, laad_basis, laad_features
from stroomprijsvoorspeller.evaluation.rolling import run_rolling
from stroomprijsvoorspeller.model import operational
from stroomprijsvoorspeller.model.calibration import pas_aci_toe, pas_conformal_toe
from stroomprijsvoorspeller.pipeline import archive, site_export
from stroomprijsvoorspeller.processing import dataset
from stroomprijsvoorspeller.processing.features import DOEL, PRIJS, bouw_features, origins_in_bereik
from stroomprijsvoorspeller.sources import energy_charts, open_meteo
from stroomprijsvoorspeller.timeutil import TZ, local_date, local_hour_range, publication_cutoff, utc_now

log = logging.getLogger(__name__)

MIN_UREN_BEKEND = 23      # een lokale dag telt als bekend met minstens 23 uurprijzen (zomertijd)
FEATURES_HERBOUW_DAGEN = 9  # doeluren van D+2..D+7 worden tot 8 dagen na D bekend; 9 voor de zekerheid
LAADBLOK_UREN = 3
WASBLOK_UREN = 2
ACI_GAMMA = 0.02


# ---------- hulpfuncties ----------

def laatste_bekende_dag(prijzen: pd.DataFrame) -> date:
    """Laatste lokale dag waarvoor (vrijwel) alle uurprijzen bekend zijn."""
    p = prijzen.dropna(subset=[PRIJS])
    per_dag = pd.Series(1, index=local_date(pd.DatetimeIndex(p["time_utc"]))).groupby(level=0).sum()
    vol = per_dag[per_dag >= MIN_UREN_BEKEND]
    return vol.index.max()


def bepaal_origin(prijzen: pd.DataFrame, vandaag: date) -> date:
    """Voorspelmoment: de dag waarop de laatst bekende dag bekend werd (laatst bekende dag - 1), nooit later dan vandaag."""
    return min(laatste_bekende_dag(prijzen) - timedelta(days=1), vandaag)


def werk_features_bij(cfg: Config, tot: date) -> pd.DataFrame:
    """Herbouwt de featurematrix vanaf (laatste origin - 9 dagen) tot en met `tot` en plakt die aan het bestand.

    Zo krijgen recente rijen hun inmiddels bekende doelprijs, en worden gemiste dagen alsnog gebouwd.
    """
    prijzen, weer = laad_basis(cfg)
    pad = cfg.processed_dir / FEATURES_BESTAND
    if pad.exists():
        f = laad_features(cfg)
        start = f["origin"].max().date() - timedelta(days=FEATURES_HERBOUW_DAGEN)
        oud = f[f["origin"] < pd.Timestamp(start)]
    else:
        start = pd.Timestamp(cfg.weer_start).date()
        oud = None
    laatste_weer = weer.index.max().tz_convert(cfg.tijdzone).date()
    einde = min(tot, laatste_weer)
    if einde < start:
        log.info("features: niets bij te werken (weer t/m %s)", laatste_weer)
        return laad_features(cfg)
    origins = origins_in_bereik(start, einde)
    nieuw = bouw_features(prijzen, weer, cfg, origins, horizon_dagen=cfg.backtest_horizon_dagen)
    f = pd.concat([oud, nieuw], ignore_index=True) if oud is not None else nieuw
    f.to_parquet(pad, index=False)
    log.info("features bijgewerkt: %d voorspelmomenten herbouwd (%s .. %s), %d rijen totaal", len(origins), start, einde, len(f))
    return laad_features(cfg)


def model_is_oud(cfg: Config, bundel: dict | None, vandaag: date) -> bool:
    if bundel is None or bundel.get("methode") != cfg.operationele_methode:
        return True
    return (vandaag - bundel["origin"]).days >= cfg.hertrain_elke_dagen


def laad_model(cfg: Config) -> dict | None:
    pad = cfg.root / "models" / operational.MODEL_BESTAND.format(methode=cfg.operationele_methode)
    return joblib.load(pad) if pad.exists() else None


# ---------- voorspellen en kalibreren ----------

def voorspel_ruw(cfg: Config, bundel: dict, prijzen: pd.DataFrame, origin: date, weer_actueel: pd.DataFrame) -> pd.DataFrame:
    """Ruwe kwantielen plus de profiel-baseline voor alle horizonten vanaf `origin`, met de actuele weersverwachting."""
    f = bouw_features(prijzen, None, cfg, [origin], horizon_dagen=cfg.horizon_dagen, weer_actueel=weer_actueel)
    X = f.reindex(columns=list(dict.fromkeys([*f.columns, *bundel["kolommen"]])))
    pred = bundel["model"].predict(X, bundel["kolommen"])
    uit = f[["origin", "time_utc", "horizon_dag", "horizon_uren"]].copy()
    for k in ("p10", "p50", "p90"):
        uit[k] = pred[k].to_numpy()
    uit["profiel_p50"] = f["prijs_profiel_uur_gem"].to_numpy()
    uit[DOEL] = np.nan
    return uit


def kalibreer(cfg: Config, ruw: pd.DataFrame, prijzen: pd.DataFrame, origin: date) -> pd.DataFrame:
    """Conformal-correctie plus ACI (besluit 40, 41) op de historie tot `origin`, toegepast op de nieuwe voorspelling."""
    methode = cfg.operationele_methode
    hist = archive.historie(cfg, methode, prijzen, dagen=120, tot=origin)
    hist = hist[hist["methode"] == methode]
    nieuw = ruw.assign(methode=methode)[["methode", "origin", "time_utc", "horizon_dag", "p10", "p50", "p90", DOEL]]
    samen = pd.concat([hist[nieuw.columns], nieuw], ignore_index=True)
    kal = pas_conformal_toe(samen, cfg.kalibratie_venster_dagen)
    aci = pas_aci_toe(kal, cfg.kalibratie_venster_dagen, gamma=ACI_GAMMA)
    eigen = aci[aci["origin"] == pd.Timestamp(origin)].set_index("time_utc")
    uit = ruw.copy()
    idx = pd.DatetimeIndex(uit["time_utc"])
    uit["conformal_q"] = eigen["conformal_q"].reindex(idx).to_numpy()
    uit["alpha_aci"] = eigen["alpha_aci"].reindex(idx).to_numpy()
    uit["p10_kal"] = eigen["p10_aci"].reindex(idx).to_numpy()
    uit["p90_kal"] = eigen["p90_aci"].reindex(idx).to_numpy()
    return uit


def voeg_blokken_toe(df: pd.DataFrame) -> pd.DataFrame:
    """Per lokale doeldag het goedkoopste laad- en wasblok (beginuur) op basis van P50, met de standaardinstellingen."""
    uit = df.copy()
    dag = local_date(pd.DatetimeIndex(uit["time_utc"]))
    uur = pd.DatetimeIndex(uit["time_utc"]).tz_convert(TZ).hour
    uit["laadblok_start"] = np.nan
    uit["wasblok_start"] = np.nan
    for d in pd.unique(dag):
        m = (dag == d)
        p50 = uit.loc[m, "p50"].to_numpy()
        uren = uur[m]
        if len(p50) < WASBLOK_UREN or np.isnan(p50).all():
            continue
        i_l, _ = blocks.goedkoopste_blok(p50, LAADBLOK_UREN)
        i_w, _ = blocks.goedkoopste_blok(p50, WASBLOK_UREN)
        uit.loc[m, "laadblok_start"] = int(uren[i_l])
        uit.loc[m, "wasblok_start"] = int(uren[i_w])
    return uit


def bekende_uren(prijzen: pd.DataFrame, origin: date, vandaag: date) -> pd.DataFrame:
    """Rijen voor vandaag t/m de laatst bekende dag: p10 = p50 = p90 = de echte prijs, bekend = True."""
    serie = prijzen.set_index("time_utc")[PRIJS]
    laatste = origin + timedelta(days=1)
    rijen = []
    for d in origins_in_bereik(min(vandaag, laatste), laatste):
        uren = local_hour_range(d)
        p = serie.reindex(uren).to_numpy()
        rijen.append(pd.DataFrame({"origin": pd.Timestamp(origin), "time_utc": uren, "horizon_dag": (d - origin).days,
                                   "horizon_uren": np.nan, "p10": p, "p50": p, "p90": p, "p10_kal": p, "p90_kal": p,
                                   "conformal_q": 0.0, "alpha_aci": np.nan, "profiel_p50": np.nan, DOEL: p, "bekend": True}))
    return pd.concat(rijen, ignore_index=True) if rijen else pd.DataFrame()


# ---------- runs ----------

def inhaalruns(cfg: Config, features: pd.DataFrame, prijzen: pd.DataFrame, tot: date) -> list[date]:
    """Rekent gemiste hoofdruns alsnog uit met de weersverwachting van toen (previous runs) en archiveert ze als `inhaal`."""
    methode = cfg.operationele_methode
    origins = [d for d in archive.ontbrekende_origins(cfg, methode, tot) if pd.Timestamp(d) in set(features["origin"])]
    if not origins:
        return []
    log.info("inhaalruns voor %d gemiste voorspelmomenten (%s .. %s)", len(origins), origins[0], origins[-1])
    v = run_rolling(features, cfg, [methode, "profiel_4w"], origins, kalibreren=False)
    if v.empty:
        log.warning("inhaalruns: geen voorspellingen (te weinig trainingsdata?)")
        return []
    model = v[v["methode"] == methode].drop(columns="methode")
    profiel = v[v["methode"] == "profiel_4w"].set_index(["origin", "time_utc"])["p50"]
    gedaan = []
    for D in origins:
        ruw = model[model["origin"] == pd.Timestamp(D)].copy()
        if ruw.empty:
            continue
        ruw["profiel_p50"] = profiel.reindex(pd.MultiIndex.from_frame(ruw[["origin", "time_utc"]])).to_numpy()
        ruw["horizon_uren"] = (pd.DatetimeIndex(ruw["time_utc"]) - publication_cutoff(D, cfg.publicatie_uur_lokaal)) / pd.Timedelta(hours=1)
        ruw[DOEL] = np.nan   # bij het archiveren onbekend; de lezer vult de prijs in
        kal = voeg_blokken_toe(kalibreer(cfg, ruw, prijzen, D))
        kal["bekend"] = False
        run_utc = publication_cutoff(D, cfg.publicatie_uur_lokaal) + pd.Timedelta(minutes=15)
        rijen = kal.assign(run_utc=run_utc, run_type="inhaal", model_getraind_utc=pd.NaT, weer_uitgegeven_utc=pd.NaT,
                           horizon_uren_run=kal["horizon_uren"])
        archive.schrijf_run(cfg, rijen, run_utc, "inhaal")
        archive.log_run(cfg, run_utc, "inhaal", D, 0.0, "ok", "achteraf ingehaald")
        gedaan.append(D)
    return gedaan


def kies_type(cfg: Config, origin: date) -> str:
    runs = archive.lees_runs(cfg, ("hoofd",))
    if runs.empty or pd.Timestamp(origin) not in set(runs["origin"]):
        return "hoofd"
    return "verversing"


def run(cfg: Config, run_type: str = "auto", nu: pd.Timestamp | None = None, fetch: bool = True) -> dict:
    """Voert een run uit en geeft een korte samenvatting terug."""
    t0 = time.time()
    nu = nu or utc_now()
    vandaag = nu.tz_convert(TZ).date()
    if fetch:
        energy_charts.update_prices(cfg.raw_dir, cfg.data_start, bzn=cfg.biedzone)
    prijzen_ruw_tot = energy_charts.lees_ruw(cfg.raw_dir)["time_utc"].max()
    log.info("prijzen bekend t/m %s", pd.Timestamp(prijzen_ruw_tot).tz_convert(TZ))
    uur = dataset.bouw_prijzen(cfg)
    uur["time_utc"] = pd.to_datetime(uur["time_utc"], utc=True)
    origin = bepaal_origin(uur, vandaag)
    if run_type == "auto":
        run_type = kies_type(cfg, origin)
    log.info("run %s, voorspelmoment %s (vandaag %s)", run_type, origin, vandaag)

    bundel = laad_model(cfg)
    if run_type == "hoofd":
        if fetch:
            open_meteo.update_previous_runs(cfg)
        dataset.bouw_basis(cfg, uur)
        dataset.bouw_weer(cfg)
        features = werk_features_bij(cfg, origin)
        ingehaald = inhaalruns(cfg, features, uur, origin)
        if model_is_oud(cfg, bundel, origin):
            operational.train_en_bewaar(cfg, cfg.operationele_methode, origin)
            bundel = laad_model(cfg)
    else:
        ingehaald = []
        if bundel is None:
            raise RuntimeError("geen getraind model; draai eerst een hoofdrun (`epv daily --type hoofd`)")
    if fetch:
        open_meteo.store_forecasts(cfg)
    weer_actueel = operational.laad_weer_actueel(cfg)
    weer_uitgegeven = max(pd.read_parquet(open_meteo.forecast_bestand(cfg.raw_dir, p.naam), columns=["uitgegeven_utc"])["uitgegeven_utc"].max()
                          for p in cfg.weerpunten)

    ruw = voorspel_ruw(cfg, bundel, uur, origin, weer_actueel)
    kal = voeg_blokken_toe(kalibreer(cfg, ruw, uur, origin))
    kal["bekend"] = False
    bekend = bekende_uren(uur, origin, vandaag)
    alles = pd.concat([bekend, kal], ignore_index=True).sort_values("time_utc").reset_index(drop=True)
    alles["run_utc"] = nu
    alles["run_type"] = run_type
    alles["model_getraind_utc"] = pd.Timestamp(bundel["train_tot"]).tz_convert("UTC") if bundel.get("train_tot") is not None else pd.NaT
    alles["weer_uitgegeven_utc"] = pd.to_datetime(weer_uitgegeven, utc=True)
    alles["horizon_uren_run"] = (pd.DatetimeIndex(alles["time_utc"]) - nu) / pd.Timedelta(hours=1)
    pad = archive.schrijf_run(cfg, alles, nu, run_type)

    json_pad = site_export.schrijf_site(cfg, alles, uur, origin, nu, run_type, bundel)
    duur = time.time() - t0
    archive.log_run(cfg, nu, run_type, origin, duur, "ok", f"{len(ingehaald)} ingehaald" if ingehaald else "")
    log.info("run klaar in %.0f s: %s, %s", duur, pad.name, json_pad)
    return {"run_type": run_type, "origin": origin, "archief": pad, "json": json_pad, "ingehaald": ingehaald,
            "duur_s": duur, "model_getraind": bundel.get("origin")}
