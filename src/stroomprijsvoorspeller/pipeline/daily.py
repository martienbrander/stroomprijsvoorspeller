"""De dagelijkse run (besluit 33, 49, 50, 54).

Soorten runs:
- hoofd:      prijzen en weer ophalen (ook de historische weersverwachtingen), datasets en features bijwerken,
              gemiste dagen inhalen, model hertrainen als het ouder is dan `hertrain_elke_dagen`, voorspellen,
              kalibreren, archiveren en de JSON voor de site schrijven.
- verversing: alleen de actuele weersverwachting (en prijzen) ophalen en opnieuw voorspellen met het bestaande model.
- inhaal:     een gemiste hoofdrun, achteraf uitgerekend met de weersverwachting zoals die toen was (previous runs),
              precies zoals de backtest. Zo blijft de historie voor kalibratie en scores zonder gaten.
- auto:       hoofd als er voor het huidige voorspelmoment nog geen hoofdrun is, anders verversing.
- middag:     hoofd in de eerste poging waarin de prijzen voor morgen binnen zijn, anders niets doen (rooster online).

Het voorspelmoment (origin) is de dag waarop de laatst bekende day-ahead dag bekend werd: laatst bekende dag min 1.
Zijn de prijzen van morgen nog niet binnen, dan is origin gisteren en toont de site één dag minder vooruit.

De functie `run` onderaan is het hele verhaal in volgorde; de functies erboven zijn de stappen.
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
from stroomprijsvoorspeller.evaluation.compare import FEATURES_BESTAND, laad_features
from stroomprijsvoorspeller.evaluation.rolling import run_rolling
from stroomprijsvoorspeller.model import operational
from stroomprijsvoorspeller.model.calibration import pas_aci_toe, pas_conformal_toe
from stroomprijsvoorspeller.pipeline import archive, site_export
from stroomprijsvoorspeller.processing import dataset
from stroomprijsvoorspeller.processing.features import DOEL, PRIJS, bouw_features, origins_in_bereik
from stroomprijsvoorspeller.sources import energy_charts, open_meteo
from stroomprijsvoorspeller.sources.http import BronNietBereikbaar
from stroomprijsvoorspeller.timeutil import (
    MIN_UREN_PER_DAG,
    TZ,
    local_date,
    local_hour_range,
    publication_cutoff,
    utc_now,
)

log = logging.getLogger(__name__)

FEATURES_HERBOUW_DAGEN = 9   # doeluren van D+2..D+7 worden tot 8 dagen na D bekend; 9 voor de zekerheid
KALIBRATIE_HISTORIE_DAGEN = 120   # zoveel voorspelmomenten terug wordt de kalibratie elke run doorgerekend (besluit 51)
INHAAL_MINUTEN_NA_PUBLICATIE = 15   # een inhaalrun krijgt als tijdstip: publicatiemoment van die dag plus een kwartier


# ---------- voorspelmoment en soort run ----------

def laatste_bekende_dag(prijzen: pd.DataFrame) -> date:
    """Laatste lokale dag waarvoor (vrijwel) alle uurprijzen bekend zijn."""
    if prijzen.empty:
        raise RuntimeError("geen prijsdata in data/raw; draai eerst `epv fetch`")
    bekend = prijzen.dropna(subset=[PRIJS])
    uren_per_dag = pd.Series(1, index=local_date(pd.DatetimeIndex(bekend["time_utc"]))).groupby(level=0).sum()
    volledig = uren_per_dag[uren_per_dag >= MIN_UREN_PER_DAG]
    if volledig.empty:
        raise RuntimeError("geen enkele dag met (vrijwel) alle uurprijzen in data/raw")
    return volledig.index.max()


def bepaal_origin(prijzen: pd.DataFrame, vandaag: date) -> date:
    """Voorspelmoment: de dag waarop de laatst bekende dag bekend werd (laatst bekende dag - 1), nooit later dan vandaag."""
    return min(laatste_bekende_dag(prijzen) - timedelta(days=1), vandaag)


def kies_bron(cfg: Config, origin: date) -> str:
    """Welke prijsbron de run gebruikt: de fallback alleen voor NL en alleen als die prijzen voor morgen heeft."""
    if cfg.biedzone == "NL":
        for kandidaat in (entsoe, energyzero):
            if kandidaat.beschikbaar() and not kandidaat.fetch_prices(
                    pd.Timestamp(origin, tz="UTC") + pd.Timedelta(days=1),
                    pd.Timestamp(origin, tz="UTC") + pd.Timedelta(days=2), bzn="NL").empty:
                return "entsoe" if kandidaat is entsoe else "energyzero"
    return "energy_charts"


def kies_type(cfg: Config, origin: date) -> str:
    """`auto`: hoofdrun als er voor dit voorspelmoment nog geen is, anders een verversing."""
    hoofdruns = archive.lees_runs(cfg, ("hoofd",))
    if hoofdruns.empty or pd.Timestamp(origin) not in set(hoofdruns["origin"]):
        return "hoofd"
    return "verversing"


def middag_beslissing(cfg: Config, origin: date, vandaag: date) -> str:
    """Rooster rond de day-ahead publicatie (besluit 54): de hoofdrun draait alleen in de eerste poging waarin de prijzen
    voor morgen binnen zijn (voorspelmoment = vandaag) en er voor dat moment nog geen hoofdrun is. Anders: overgeslagen."""
    if origin < vandaag:
        return "overgeslagen"
    return "hoofd" if kies_type(cfg, origin) == "hoofd" else "overgeslagen"


# ---------- features en model ----------

def werk_features_bij(cfg: Config, tot: date, prijzen: pd.DataFrame, weer: pd.DataFrame) -> pd.DataFrame:
    """Herbouwt de featurematrix vanaf (laatste origin - 9 dagen) tot en met `tot` en plakt die aan het bestand.

    Zo krijgen recente rijen hun inmiddels bekende doelprijs, en worden gemiste dagen alsnog gebouwd.
    `prijzen` en `weer` zijn de zojuist gebouwde datasets (uurprijzen en previous-runs weer).
    """
    pad = cfg.processed_dir / FEATURES_BESTAND
    if pad.exists():
        bestaand = laad_features(cfg)
        start = bestaand["origin"].max().date() - timedelta(days=FEATURES_HERBOUW_DAGEN)
    else:
        bestaand = None
        start = pd.Timestamp(cfg.weer_start).date()
    laatste_weer = weer.index.max().tz_convert(cfg.tijdzone).date()
    einde = min(tot, laatste_weer)
    if einde < start:
        if bestaand is None:
            raise RuntimeError(f"geen weerdata vanaf {start} om features mee te bouwen; draai eerst `epv fetch`")
        log.info("features: niets bij te werken (weer t/m %s)", laatste_weer)
        return bestaand
    origins = origins_in_bereik(start, einde)
    nieuw = bouw_features(prijzen, weer, cfg, origins, horizon_dagen=cfg.backtest_horizon_dagen)
    if bestaand is None:
        nieuw.to_parquet(pad, index=False)
        log.info("features gebouwd: %d voorspelmomenten (%s .. %s), %d rijen", len(origins), start, einde, len(nieuw))
        return laad_features(cfg)   # teruglezen, zodat de kolomtypen gelijk zijn aan die van elke latere run
    features = pd.concat([bestaand[bestaand["origin"] < pd.Timestamp(start)], nieuw], ignore_index=True)
    features.to_parquet(pad, index=False)
    log.info("features bijgewerkt: %d voorspelmomenten herbouwd (%s .. %s), %d rijen totaal",
             len(origins), start, einde, len(features))
    return features


def laad_model(cfg: Config) -> dict | None:
    """Het bewaarde operationele model (zie `operational.train_en_bewaar`), of None als er nog geen is."""
    pad = operational.model_pad(cfg, cfg.operationele_methode)
    return joblib.load(pad) if pad.exists() else None


def model_is_oud(cfg: Config, bundel: dict | None, vandaag: date) -> bool:
    """Hertrainen is nodig als er geen model is, de methode in de config veranderd is, of het model te oud is."""
    if bundel is None or bundel.get("methode") != cfg.operationele_methode:
        return True
    return (vandaag - bundel["origin"]).days >= cfg.hertrain_elke_dagen


# ---------- voorspellen en kalibreren ----------

def voorspel_ruw(cfg: Config, bundel: dict, prijzen: pd.DataFrame, origin: date, weer_actueel: pd.DataFrame) -> pd.DataFrame:
    """Ruwe kwantielen plus de profiel-baseline voor alle horizonten vanaf `origin`, met de actuele weersverwachting."""
    f = bouw_features(prijzen, None, cfg, [origin], horizon_dagen=cfg.horizon_dagen, weer_actueel=weer_actueel)
    uit = operational.voorspel_kwantielen(bundel, f)
    uit["profiel_p50"] = f["prijs_profiel_uur_gem"].to_numpy()
    uit[DOEL] = np.nan
    return uit


def kalibreer(cfg: Config, ruw: pd.DataFrame, prijzen: pd.DataFrame, origin: date) -> pd.DataFrame:
    """Conformal-correctie plus ACI (besluit 40, 41) op de historie tot `origin`, toegepast op de nieuwe voorspelling.

    De hele historie wordt elke keer opnieuw doorgerekend, zodat er geen toestand tussen runs bewaard hoeft te worden
    (besluit 51). Uit de uitkomst gaan alleen de rijen van `origin` zelf mee.
    """
    methode = cfg.operationele_methode
    kolommen = ["methode", "origin", "time_utc", "horizon_dag", "p10", "p50", "p90", DOEL]
    hist = archive.historie(cfg, methode, prijzen, dagen=KALIBRATIE_HISTORIE_DAGEN, tot=origin)
    hist = hist[hist["methode"] == methode]
    samen = pd.concat([hist[kolommen], ruw.assign(methode=methode)[kolommen]], ignore_index=True)
    conformal = pas_conformal_toe(samen, cfg.kalibratie_venster_dagen)
    aci = pas_aci_toe(conformal, cfg.kalibratie_venster_dagen)
    eigen = aci[aci["origin"] == pd.Timestamp(origin)].set_index("time_utc").reindex(pd.DatetimeIndex(ruw["time_utc"]))
    uit = ruw.copy()
    uit["conformal_q"] = eigen["conformal_q"].to_numpy()
    uit["alpha_aci"] = eigen["alpha_aci"].to_numpy()
    uit["p10_kal"] = eigen["p10_aci"].to_numpy()
    uit["p90_kal"] = eigen["p90_aci"].to_numpy()
    return uit


def voeg_blokken_toe(df: pd.DataFrame) -> pd.DataFrame:
    """Per lokale doeldag het goedkoopste laad- en wasblok (beginuur) op basis van P50, met de standaardinstellingen."""
    uit = df.copy()
    tijden = pd.DatetimeIndex(uit["time_utc"])
    dag = local_date(tijden)
    uur = tijden.tz_convert(TZ).hour
    uit["laadblok_start"] = np.nan
    uit["wasblok_start"] = np.nan
    for d in pd.unique(dag):
        van_dag = (dag == d)
        p50 = uit.loc[van_dag, "p50"].to_numpy()
        if len(p50) < blocks.WASBLOK_UREN or np.isnan(p50).all():
            continue
        laad_start, _ = blocks.goedkoopste_blok(p50, blocks.LAADBLOK_UREN)
        was_start, _ = blocks.goedkoopste_blok(p50, blocks.WASBLOK_UREN)
        uit.loc[van_dag, "laadblok_start"] = int(uur[van_dag][laad_start])
        uit.loc[van_dag, "wasblok_start"] = int(uur[van_dag][was_start])
    return uit


def bekende_uren(prijzen: pd.DataFrame, origin: date, vandaag: date) -> pd.DataFrame:
    """Rijen voor vandaag t/m de laatst bekende dag: p10 = p50 = p90 = de echte prijs, bekend = True."""
    serie = prijzen.set_index("time_utc")[PRIJS]
    laatste = origin + timedelta(days=1)
    rijen = []
    for dag in origins_in_bereik(min(vandaag, laatste), laatste):
        uren = local_hour_range(dag)
        p = serie.reindex(uren).to_numpy()
        rijen.append(pd.DataFrame({
            "origin": pd.Timestamp(origin), "time_utc": uren, "horizon_dag": (dag - origin).days, "horizon_uren": np.nan,
            "p10": p, "p50": p, "p90": p, "p10_kal": p, "p90_kal": p, "conformal_q": 0.0, "alpha_aci": np.nan,
            "profiel_p50": np.nan, DOEL: p, "bekend": True,
        }))
    return pd.concat(rijen, ignore_index=True) if rijen else pd.DataFrame()


# ---------- inhaalruns ----------

def inhaalruns(cfg: Config, features: pd.DataFrame, prijzen: pd.DataFrame, tot: date) -> list[date]:
    """Rekent gemiste hoofdruns alsnog uit met de weersverwachting van toen (previous runs) en archiveert ze als `inhaal`."""
    methode = cfg.operationele_methode
    met_features = set(features["origin"])
    origins = [d for d in archive.ontbrekende_origins(cfg, methode, tot) if pd.Timestamp(d) in met_features]
    if not origins:
        return []
    log.info("inhaalruns voor %d gemiste voorspelmomenten (%s .. %s)", len(origins), origins[0], origins[-1])
    v = run_rolling(features, cfg, [methode, archive.PROFIEL], origins, kalibreren=False)
    if v.empty:
        log.warning("inhaalruns: geen voorspellingen (te weinig trainingsdata?)")
        return []
    model = v[v["methode"] == methode].drop(columns="methode")
    profiel = v[v["methode"] == archive.PROFIEL].set_index(["origin", "time_utc"])["p50"]
    gedaan = []
    for origin in origins:
        ruw = model[model["origin"] == pd.Timestamp(origin)].copy()
        if ruw.empty:
            continue
        publicatie = publication_cutoff(origin, cfg.publicatie_uur_lokaal)
        ruw["profiel_p50"] = profiel.reindex(pd.MultiIndex.from_frame(ruw[["origin", "time_utc"]])).to_numpy()
        ruw["horizon_uren"] = (pd.DatetimeIndex(ruw["time_utc"]) - publicatie) / pd.Timedelta(hours=1)
        ruw[DOEL] = np.nan   # bij het archiveren onbekend; de lezer vult de prijs in
        kal = voeg_blokken_toe(kalibreer(cfg, ruw, prijzen, origin))
        run_utc = publicatie + pd.Timedelta(minutes=INHAAL_MINUTEN_NA_PUBLICATIE)
        rijen = kal.assign(bekend=False, run_utc=run_utc, run_type="inhaal", model_getraind_utc=pd.NaT,
                           weer_uitgegeven_utc=pd.NaT, horizon_uren_run=kal["horizon_uren"])
        archive.schrijf_run(cfg, rijen, run_utc, "inhaal")
        archive.log_run(cfg, run_utc, "inhaal", origin, 0.0, "ok", "achteraf ingehaald")
        gedaan.append(origin)
    return gedaan


# ---------- de run zelf ----------

def _bereid_hoofdrun_voor(cfg: Config, prijzen: pd.DataFrame, origin: date, fetch: bool) -> tuple[dict, list[date]]:
    """Alles wat alleen de hoofdrun doet: historisch weer ophalen, datasets en features bijwerken, gemiste dagen
    inhalen en het model hertrainen als dat nodig is. Geeft het model en de ingehaalde voorspelmomenten terug."""
    if fetch:
        open_meteo.update_previous_runs(cfg)
    dataset.bouw_basis(cfg, prijzen)
    weer = dataset.bouw_weer(cfg)
    if weer is None:
        raise RuntimeError("geen historische weersverwachtingen in data/raw; draai eerst `epv fetch`")
    features = werk_features_bij(cfg, origin, prijzen, weer)
    ingehaald = inhaalruns(cfg, features, prijzen, origin)
    bundel = laad_model(cfg)
    if model_is_oud(cfg, bundel, origin):
        operational.train_en_bewaar(cfg, cfg.operationele_methode, origin)
        bundel = laad_model(cfg)
    return bundel, ingehaald


def _stel_run_samen(cfg: Config, bundel: dict, prijzen: pd.DataFrame, origin: date, nu: pd.Timestamp,
                    run_type: str) -> pd.DataFrame:
    """Voorspelt en kalibreert de onbekende dagen, zet de bekende uren ervoor en voegt de gegevens over de run toe.
    Het resultaat is wat in het archief komt en waar de site-JSON uit gemaakt wordt."""
    weer_actueel, weer_uitgegeven = operational.laad_actuele_verwachting(cfg)
    ruw = voorspel_ruw(cfg, bundel, prijzen, origin, weer_actueel)
    voorspeld = voeg_blokken_toe(kalibreer(cfg, ruw, prijzen, origin)).assign(bekend=False)
    bekend = bekende_uren(prijzen, origin, nu.tz_convert(TZ).date())
    alles = pd.concat([bekend, voorspeld], ignore_index=True).sort_values("time_utc").reset_index(drop=True)
    getraind_tot = bundel.get("train_tot")
    alles["run_utc"] = nu
    alles["run_type"] = run_type
    alles["model_getraind_utc"] = pd.Timestamp(getraind_tot).tz_convert("UTC") if getraind_tot is not None else pd.NaT
    alles["weer_uitgegeven_utc"] = weer_uitgegeven
    alles["horizon_uren_run"] = (pd.DatetimeIndex(alles["time_utc"]) - nu) / pd.Timedelta(hours=1)
    return alles


def haal_weer_op(cfg: Config, rondes: int = 1, wacht_minuten: float = 20.0, slaap=time.sleep) -> bool:
    """Haalt de actuele weersverwachting op. Elke ronde doet een paar snelle pogingen (zie open_meteo); mislukt een
    ronde omdat de bron niet antwoordt, dan wachten we `wacht_minuten` en proberen het opnieuw, hoogstens `rondes`
    keer (besluit 78). Geeft False terug als het na alle rondes niet gelukt is."""
    for ronde in range(1, rondes + 1):
        try:
            open_meteo.store_forecasts(cfg)
            return True
        except BronNietBereikbaar as fout:
            if ronde == rondes:
                log.warning("weerbron niet bereikbaar na %d ronde(n): %s", rondes, fout)
                return False
            log.warning("weerbron niet bereikbaar (ronde %d van %d): %s; over %.0f minuten opnieuw",
                        ronde, rondes, fout, wacht_minuten)
            slaap(wacht_minuten * 60)
    return False


def run(cfg: Config, run_type: str = "auto", nu: pd.Timestamp | None = None, fetch: bool = True,
        weer_rondes: int = 1, weer_wacht_minuten: float = 20.0) -> dict:
    """Voert een run uit en geeft een korte samenvatting terug. De uitkomst kan `overgeslagen` zijn: bij type `middag`
    als er niets nieuws is, en bij een verversing als de weerbron na `weer_rondes` rondes niet antwoordt. Dan is er
    niets gearchiveerd en niets voor de site geschreven."""
    t0 = time.time()
    nu = nu or utc_now()
    vandaag = nu.tz_convert(TZ).date()
    if fetch:
        energy_charts.update_prices(cfg.raw_dir, cfg.data_start, bzn=cfg.biedzone)
    prijzen = dataset.bouw_prijzen(cfg)
    log.info("prijzen bekend t/m %s", prijzen.dropna(subset=[PRIJS])["time_utc"].max().tz_convert(TZ))
    origin = bepaal_origin(prijzen, vandaag)

    if run_type == "auto":
        run_type = kies_type(cfg, origin)
    elif run_type == "middag":
        run_type = middag_beslissing(cfg, origin, vandaag)
        if run_type == "overgeslagen":
            reden = "prijzen voor morgen nog niet binnen" if origin < vandaag else "hoofdrun voor vandaag bestaat al"
            log.info("middagrun overgeslagen: %s (voorspelmoment %s)", reden, origin)
            archive.log_run(cfg, nu, "overgeslagen", origin, time.time() - t0, "overgeslagen", reden)
            return {"run_type": "overgeslagen", "origin": origin, "archief": None, "json": None, "ingehaald": [],
                    "duur_s": time.time() - t0, "model_getraind": None, "reden": reden}
    log.info("run %s, voorspelmoment %s (vandaag %s)", run_type, origin, vandaag)

    if run_type == "hoofd":
        bundel, ingehaald = _bereid_hoofdrun_voor(cfg, prijzen, origin, fetch)
    else:
        bundel, ingehaald = laad_model(cfg), []
        if bundel is None:
            raise RuntimeError("geen getraind model; draai eerst een hoofdrun (`epv daily --type hoofd`)")
    # Ook de hoofdrun wacht in rondes: anders gaat bij een haperende weerbron het werk van de hele run verloren
    # (features, trainen) en moet de volgende geplande poging alles opnieuw doen (besluit 78).
    if fetch and not haal_weer_op(cfg, weer_rondes, weer_wacht_minuten):
        reden = "weerbron niet bereikbaar"
        if run_type != "verversing":
            # een hoofdrun zonder weer is een fout: dan mist de site de prijzen voor morgen
            raise BronNietBereikbaar(f"{reden}: de hoofdrun kan niet zonder de actuele weersverwachting")
        # een verversing zonder nieuw weer voegt niets toe: overslaan zonder fout, wel in het logboek
        archive.log_run(cfg, nu, run_type, origin, time.time() - t0, "geen_weer", reden)
        return {"run_type": "overgeslagen", "origin": origin, "archief": None, "json": None, "ingehaald": [],
                "duur_s": time.time() - t0, "model_getraind": None, "reden": reden}

    alles = _stel_run_samen(cfg, bundel, prijzen, origin, nu, run_type)
    archief_pad = archive.schrijf_run(cfg, alles, nu, run_type)
    json_pad = site_export.schrijf_site(cfg, alles, prijzen, origin, nu, run_type, bundel)
    duur = time.time() - t0
    archive.log_run(cfg, nu, run_type, origin, duur, "ok", f"{len(ingehaald)} ingehaald" if ingehaald else "")
    log.info("run klaar in %.0f s: %s, %s", duur, archief_pad.name, json_pad)
    return {"run_type": run_type, "origin": origin, "archief": archief_pad, "json": json_pad, "ingehaald": ingehaald,
            "duur_s": duur, "model_getraind": bundel.get("origin")}
