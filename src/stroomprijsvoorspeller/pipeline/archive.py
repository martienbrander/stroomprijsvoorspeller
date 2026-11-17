"""Runarchief: elke run (hoofd, verversing of inhaal) schrijft één parquet in data/runs/.

Bestandsnaam: run_<YYYYMMDD_HHMM>_<type>.parquet (tijd in UTC). Kolommen volgens PLAN.md, sectie "Evaluatie van de
verversingsruns": run_utc, run_type, origin, model_getraind_utc, weer_uitgegeven_utc, time_utc, horizon_dag,
horizon_uren_run, p10, p50, p90, p10_kal, p90_kal, conformal_q, alpha_aci, bekend, profiel_p50, laadblok_start,
wasblok_start, doel (bij de run meestal NaN; wordt bij het lezen gevuld met de inmiddels bekende prijs).

De historie voor kalibratie en scores bestaat uit:
1. de backtest-voorspellingen van de operationele methode (onder haar canonieke naam), en
2. per voorspelmoment één run uit het archief: de hoofdrun, anders de inhaalrun.
Zo heeft de 30-dagenhistorie nooit gaten, ook niet als er dagen niet gedraaid is (besluit 50).

Eén run vraagt de historie meerdere keren op (kalibratie, per inhaalrun, scores voor de site). Daarom wordt elk
bestand per proces maar één keer gelezen, tenzij het intussen veranderd is (zie `_lees_eenmalig`).
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import date
from pathlib import Path

import pandas as pd

from stroomprijsvoorspeller.config import Config
from stroomprijsvoorspeller.evaluation.rolling import parse_spec
from stroomprijsvoorspeller.processing.features import DOEL, PRIJS

log = logging.getLogger(__name__)

RUN_TYPES = ("hoofd", "verversing", "inhaal")
HISTORIE_TYPES = ("hoofd", "inhaal")   # verversingen tellen niet mee voor kalibratie en scores
PROFIEL = "profiel_4w"                 # de baseline waartegen de betrouwbaarheid wordt afgezet
LOGBESTAND = "runs.csv"
HISTORIE_BESTAND = "voorspellingen_historie.parquet"
KOLOMMEN = ["run_utc", "run_type", "origin", "model_getraind_utc", "weer_uitgegeven_utc", "time_utc", "horizon_dag",
            "horizon_uren_run", "p10", "p50", "p90", "p10_kal", "p90_kal", "conformal_q", "alpha_aci", "bekend",
            "profiel_p50", "laadblok_start", "wasblok_start", DOEL]
HISTORIE_KOLOMMEN = ["methode", "origin", "time_utc", "horizon_dag", "p10", "p50", "p90", "p10_kal", "p90_kal", DOEL]

# (soort, pad) -> ((wijzigingstijd, grootte), inhoud); zie _lees_eenmalig
_GELEZEN: dict[tuple[str, str], tuple[tuple[int, int], pd.DataFrame]] = {}


def _lees_eenmalig(pad: Path, lees: Callable[[Path], pd.DataFrame], soort: str) -> pd.DataFrame:
    """Leest `pad` met `lees`, maar hoogstens één keer per proces zolang het bestand niet verandert.

    Het teruggegeven frame wordt gedeeld tussen aanroepers: niet ter plekke wijzigen.
    """
    stat = pad.stat()
    versie = (stat.st_mtime_ns, stat.st_size)
    bewaard = _GELEZEN.get((soort, str(pad)))
    if bewaard is None or bewaard[0] != versie:
        bewaard = (versie, lees(pad))
        _GELEZEN[(soort, str(pad))] = bewaard
    return bewaard[1]


# ---------- runs schrijven en lezen ----------

def runs_dir(cfg: Config) -> Path:
    return cfg.root / "data" / "runs"


def run_bestand(cfg: Config, run_utc: pd.Timestamp, run_type: str) -> Path:
    tijd = pd.Timestamp(run_utc).tz_convert("UTC").strftime("%Y%m%d_%H%M")
    return runs_dir(cfg) / f"run_{tijd}_{run_type}.parquet"


def schrijf_run(cfg: Config, rijen: pd.DataFrame, run_utc: pd.Timestamp, run_type: str) -> Path:
    if run_type not in RUN_TYPES:
        raise ValueError(run_type)
    runs_dir(cfg).mkdir(parents=True, exist_ok=True)
    pad = run_bestand(cfg, run_utc, run_type)
    rijen.reindex(columns=KOLOMMEN).to_parquet(pad, index=False)
    return pad


def lees_runs(cfg: Config, types: tuple[str, ...] = RUN_TYPES) -> pd.DataFrame:
    """Alle archiefbestanden van de gegeven typen, in één frame (leeg frame als er niets is).

    Het type staat in de bestandsnaam, dus bestanden van andere typen worden niet eens geopend.
    """
    delen = []
    for pad in sorted(runs_dir(cfg).glob("run_*.parquet")):
        if pad.stem.split("_")[-1] in types:
            delen.append(_lees_eenmalig(pad, pd.read_parquet, "run").assign(bestand=pad.name))
    if not delen:
        return pd.DataFrame(columns=[*KOLOMMEN, "bestand"])
    uit = pd.concat(delen, ignore_index=True)
    for k in ("run_utc", "model_getraind_utc", "weer_uitgegeven_utc", "time_utc"):
        uit[k] = pd.to_datetime(uit[k], utc=True)
    uit["origin"] = pd.to_datetime(uit["origin"])
    return uit


def vul_doel(runs: pd.DataFrame, prijzen: pd.DataFrame) -> pd.DataFrame:
    """Vult `doel` met de inmiddels bekende uurprijs."""
    serie = prijzen.set_index("time_utc")[PRIJS]
    uit = runs.copy()
    uit[DOEL] = serie.reindex(pd.DatetimeIndex(uit["time_utc"])).to_numpy()
    return uit


def laatste_run_per_origin(runs: pd.DataFrame) -> pd.DataFrame:
    """Per voorspelmoment één run: de laatste hoofdrun, anders de laatste inhaalrun. Verversingen tellen niet mee."""
    if runs.empty:
        return runs
    r = runs[runs["run_type"].isin(HISTORIE_TYPES)].copy()
    if r.empty:
        return r
    r["_rang"] = r["run_type"].map({"hoofd": 0, "inhaal": 1})
    keuze = (r.sort_values(["origin", "_rang", "run_utc"], ascending=[True, True, False])
             .drop_duplicates("origin")[["origin", "bestand"]])
    return r.merge(keuze, on=["origin", "bestand"]).drop(columns="_rang")


def log_run(cfg: Config, run_utc: pd.Timestamp, run_type: str, origin: date, duur_s: float, status: str,
            melding: str = "") -> None:
    """Voegt één regel toe aan data/runs/runs.csv (ook voor overgeslagen middagpogingen)."""
    runs_dir(cfg).mkdir(parents=True, exist_ok=True)
    pad = runs_dir(cfg) / LOGBESTAND
    rij = pd.DataFrame([{"run_utc": pd.Timestamp(run_utc).tz_convert("UTC").isoformat(), "run_type": run_type,
                         "origin": str(origin), "duur_s": round(duur_s, 1), "status": status, "melding": melding}])
    rij.to_csv(pad, mode="a", header=not pad.exists(), index=False)


# ---------- historie voor kalibratie en scores ----------

def _canonieke_naam(cfg: Config, methode: str) -> str:
    return parse_spec(methode).canoniek(cfg.rolling_venster_dagen)


def backtest_historie(cfg: Config, methode: str) -> pd.DataFrame:
    """Backtest-voorspellingen van de methode (ook onder haar canonieke naam) plus de profiel-baseline, als lang frame."""
    namen = {methode, _canonieke_naam(cfg, methode), PROFIEL}

    def lees(pad: Path) -> pd.DataFrame:
        d = pd.read_parquet(pad)
        return d[d["methode"].isin(namen)]

    soort = "backtest:" + ",".join(sorted(namen))
    delen = [_lees_eenmalig(pad, lees, soort) for pad in sorted(cfg.processed_dir.glob("voorspellingen_*.parquet"))]
    delen = [d for d in delen if not d.empty]
    if not delen:
        return pd.DataFrame()
    v = pd.concat(delen, ignore_index=True)
    v["methode"] = v["methode"].where(v["methode"] == PROFIEL, methode)
    v["time_utc"] = pd.to_datetime(v["time_utc"], utc=True)
    v["origin"] = pd.to_datetime(v["origin"])
    v = v.drop_duplicates(["methode", "origin", "time_utc"])
    # bestanden zonder kalibratie: het ruwe interval, correctie nul
    for kolom, standaard in (("p10_kal", v["p10"]), ("p90_kal", v["p90"]), ("conformal_q", 0.0)):
        if kolom not in v.columns:
            v[kolom] = standaard
    return v[HISTORIE_KOLOMMEN]


def exporteer_historie(cfg: Config, methode: str, dagen: int = 150) -> Path:
    """Schrijft een compacte versie van de backtest-historie (alleen de operationele methode en het profiel, laatste
    `dagen` voorspelmomenten) voor gebruik online, waar de grote backtest-bestanden niet mee hoeven (besluit 47)."""
    bt = backtest_historie(cfg, methode)
    if bt.empty:
        raise RuntimeError("geen backtest-voorspellingen gevonden")
    bt = bt[bt["origin"] >= bt["origin"].max() - pd.Timedelta(days=dagen)].copy()
    bt["methode"] = bt["methode"].where(bt["methode"] == PROFIEL, _canonieke_naam(cfg, methode))
    pad = cfg.processed_dir / HISTORIE_BESTAND
    bt.to_parquet(pad, index=False)
    log.info("historie: %d rijen, %s .. %s -> %s", len(bt), bt["origin"].min().date(), bt["origin"].max().date(), pad)
    return pad


def _runs_als_historie(runs: pd.DataFrame, methode: str) -> list[pd.DataFrame]:
    """De voorspelde uren van archiefruns in de vorm van de historie: één deel voor het model, één voor het profiel
    (dat per run is meegearchiveerd als `profiel_p50` en geen eigen interval heeft)."""
    model = runs.assign(methode=methode)[HISTORIE_KOLOMMEN]
    p = runs["profiel_p50"]
    profiel = runs.assign(methode=PROFIEL, p10=p, p50=p, p90=p, p10_kal=p, p90_kal=p)[HISTORIE_KOLOMMEN]
    return [model, profiel]


def historie(cfg: Config, methode: str, prijzen: pd.DataFrame, dagen: int = 120, tot: date | None = None) -> pd.DataFrame:
    """Lang frame (zie HISTORIE_KOLOMMEN) van de laatste `dagen` voorspelmomenten vóór `tot`: archiefruns waar die er
    zijn, anders de backtest. Alleen voorspelde uren (niet `bekend`)."""
    runs = laatste_run_per_origin(lees_runs(cfg, HISTORIE_TYPES))
    delen = []
    if not runs.empty:
        runs = vul_doel(runs[~runs["bekend"].astype(bool)], prijzen)
        delen += _runs_als_historie(runs, methode)
    bt = backtest_historie(cfg, methode)
    if not bt.empty:
        if not runs.empty:
            bt = bt[~bt["origin"].isin(set(runs["origin"]))]
        delen.append(bt)
    if not delen:
        return pd.DataFrame(columns=HISTORIE_KOLOMMEN)
    h = pd.concat(delen, ignore_index=True)
    if tot is not None:
        h = h[h["origin"] < pd.Timestamp(tot)]
    grens = h["origin"].max() - pd.Timedelta(days=dagen)
    return h[h["origin"] >= grens].sort_values(["methode", "origin", "time_utc"]).reset_index(drop=True)


KOUDE_START_DAGEN = 60   # eerste run zonder enige historie: zoveel dagen achteraf narekenen (besluit 76)


def ontbrekende_origins(cfg: Config, methode: str, tot: date, max_dagen: int = 120) -> list[date]:
    """Voorspelmomenten vóór `tot` zonder hoofd- of inhaalrun: vanaf de dag na het einde van de backtest, of anders
    vanaf de eerste archiefrun; hoogstens `max_dagen` terug (besluit 50). Is er nog helemaal niets (een nieuwe
    installatie), dan de laatste KOUDE_START_DAGEN dagen: zonder die historie is de onzekerheidsmarge niet
    gekalibreerd en zijn er geen scores (besluit 76)."""
    runs = lees_runs(cfg, HISTORIE_TYPES)
    bt = backtest_historie(cfg, methode)
    if not bt.empty:
        start = bt["origin"].max() + pd.Timedelta(days=1)
    elif not runs.empty:
        start = runs["origin"].min()
    else:
        start = pd.Timestamp(tot) - pd.Timedelta(days=KOUDE_START_DAGEN)
    einde = pd.Timestamp(tot) - pd.Timedelta(days=1)
    start = max(start, pd.Timestamp(tot) - pd.Timedelta(days=max_dagen))
    gedaan = {d.date() for d in pd.DatetimeIndex(runs["origin"]).unique()}
    return [d for d in pd.date_range(start, einde, freq="D").date if d not in gedaan]
