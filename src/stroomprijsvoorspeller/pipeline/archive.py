"""Runarchief: elke run (hoofd, verversing of inhaal) schrijft één parquet in data/runs/.

Bestandsnaam: run_<YYYYMMDD_HHMM>_<type>.parquet (tijd in UTC). Kolommen volgens PLAN.md, sectie "Evaluatie van de
verversingsruns": run_utc, run_type, origin, model_getraind_utc, weer_uitgegeven_utc, time_utc, horizon_dag,
horizon_uren_run, p10, p50, p90, p10_kal, p90_kal, conformal_q, alpha_aci, bekend, profiel_p50, laadblok_start,
wasblok_start, doel (bij de run meestal NaN; wordt bij het lezen gevuld met de inmiddels bekende prijs).

De historie voor kalibratie en scores bestaat uit:
1. de backtest-voorspellingen van de operationele methode (onder haar canonieke naam), en
2. per voorspelmoment één run uit het archief: de hoofdrun, anders de inhaalrun.
Zo heeft de 30-dagenhistorie nooit gaten, ook niet als er dagen niet gedraaid is (besluit 50).
"""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path

import pandas as pd

from stroomprijsvoorspeller.config import Config
from stroomprijsvoorspeller.evaluation.rolling import parse_spec
from stroomprijsvoorspeller.processing.features import DOEL, PRIJS
from stroomprijsvoorspeller.timeutil import TZ

log = logging.getLogger(__name__)

RUN_TYPES = ("hoofd", "verversing", "inhaal")
LOGBESTAND = "runs.csv"
KOLOMMEN = ["run_utc", "run_type", "origin", "model_getraind_utc", "weer_uitgegeven_utc", "time_utc", "horizon_dag",
            "horizon_uren_run", "p10", "p50", "p90", "p10_kal", "p90_kal", "conformal_q", "alpha_aci", "bekend",
            "profiel_p50", "laadblok_start", "wasblok_start", DOEL]


def runs_dir(cfg: Config) -> Path:
    return cfg.root / "data" / "runs"


def run_bestand(cfg: Config, run_utc: pd.Timestamp, run_type: str) -> Path:
    return runs_dir(cfg) / f"run_{pd.Timestamp(run_utc).tz_convert('UTC').strftime('%Y%m%d_%H%M')}_{run_type}.parquet"


def schrijf_run(cfg: Config, rijen: pd.DataFrame, run_utc: pd.Timestamp, run_type: str) -> Path:
    if run_type not in RUN_TYPES:
        raise ValueError(run_type)
    runs_dir(cfg).mkdir(parents=True, exist_ok=True)
    pad = run_bestand(cfg, run_utc, run_type)
    uit = rijen.reindex(columns=KOLOMMEN)
    uit.to_parquet(pad, index=False)
    return pad


def lees_runs(cfg: Config, types: tuple[str, ...] = RUN_TYPES) -> pd.DataFrame:
    """Alle archiefbestanden van de gegeven typen, in één frame (leeg frame als er niets is)."""
    delen = []
    for pad in sorted(runs_dir(cfg).glob("run_*.parquet")) if runs_dir(cfg).exists() else []:
        t = pad.stem.split("_")[-1]
        if t in types:
            d = pd.read_parquet(pad)
            d["bestand"] = pad.name
            delen.append(d)
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
    r = runs[runs["run_type"].isin(("hoofd", "inhaal"))].copy()
    if r.empty:
        return r
    r["_rang"] = r["run_type"].map({"hoofd": 0, "inhaal": 1})
    keuze = (r.sort_values(["origin", "_rang", "run_utc"], ascending=[True, True, False])
             .drop_duplicates("origin")[["origin", "bestand"]])
    return r.merge(keuze, on=["origin", "bestand"]).drop(columns="_rang")


def backtest_historie(cfg: Config, methode: str) -> pd.DataFrame:
    """Backtest-voorspellingen van de methode (ook onder haar canonieke naam) plus de profiel-baseline, als lang frame."""
    namen = {methode, parse_spec(methode).canoniek(cfg.rolling_venster_dagen)}
    delen = []
    for pad in sorted(cfg.processed_dir.glob("voorspellingen_*.parquet")):
        d = pd.read_parquet(pad)
        d = d[d["methode"].isin(namen | {"profiel_4w"})]
        if not d.empty:
            delen.append(d)
    if not delen:
        return pd.DataFrame()
    v = pd.concat(delen, ignore_index=True)
    v["methode"] = v["methode"].where(v["methode"] == "profiel_4w", methode)
    v["time_utc"] = pd.to_datetime(v["time_utc"], utc=True)
    v["origin"] = pd.to_datetime(v["origin"])
    v = v.drop_duplicates(["methode", "origin", "time_utc"])
    for k in ("p10_kal", "p90_kal", "conformal_q"):
        if k not in v.columns:
            v[k] = v["p10"] if k == "p10_kal" else v["p90"] if k == "p90_kal" else 0.0
    return v[["methode", "origin", "time_utc", "horizon_dag", "p10", "p50", "p90", "p10_kal", "p90_kal", DOEL]]


def historie(cfg: Config, methode: str, prijzen: pd.DataFrame, dagen: int = 120, tot: date | None = None) -> pd.DataFrame:
    """Lang frame (methode, origin, time_utc, horizon_dag, p10, p50, p90, p10_kal, p90_kal, doel) van de laatste `dagen`
    voorspelmomenten vóór `tot`: archiefruns waar die er zijn, anders de backtest. Alleen voorspelde uren (niet `bekend`)."""
    runs = laatste_run_per_origin(lees_runs(cfg))
    delen = []
    if not runs.empty:
        runs = vul_doel(runs[~runs["bekend"].astype(bool)], prijzen)
        model = runs.assign(methode=methode)[["methode", "origin", "time_utc", "horizon_dag", "p10", "p50", "p90",
                                              "p10_kal", "p90_kal", DOEL]]
        profiel = runs.assign(methode="profiel_4w", p10=runs["profiel_p50"], p50=runs["profiel_p50"], p90=runs["profiel_p50"],
                              p10_kal=runs["profiel_p50"], p90_kal=runs["profiel_p50"])[model.columns]
        delen += [model, profiel]
    bt = backtest_historie(cfg, methode)
    if not bt.empty:
        if not runs.empty:
            bt = bt[~bt["origin"].isin(set(runs["origin"]))]
        delen.append(bt)
    if not delen:
        return pd.DataFrame(columns=["methode", "origin", "time_utc", "horizon_dag", "p10", "p50", "p90", "p10_kal", "p90_kal", DOEL])
    h = pd.concat(delen, ignore_index=True)
    if tot is not None:
        h = h[h["origin"] < pd.Timestamp(tot)]
    grens = h["origin"].max() - pd.Timedelta(days=dagen)
    return h[h["origin"] >= grens].sort_values(["methode", "origin", "time_utc"]).reset_index(drop=True)


def ontbrekende_origins(cfg: Config, methode: str, tot: date, max_dagen: int = 120) -> list[date]:
    """Voorspelmomenten vóór `tot` zonder hoofd- of inhaalrun: vanaf de dag na het einde van de backtest, of anders
    vanaf de eerste archiefrun; hoogstens `max_dagen` terug (besluit 50)."""
    runs = lees_runs(cfg, ("hoofd", "inhaal"))
    bt = backtest_historie(cfg, methode)
    gedaan = {d.date() for d in pd.DatetimeIndex(runs["origin"]).unique()} if not runs.empty else set()
    if not bt.empty:
        start = bt["origin"].max().date() + pd.Timedelta(days=1)
    elif not runs.empty:
        start = runs["origin"].min().date()
    else:
        return []
    start = max(pd.Timestamp(start), pd.Timestamp(tot) - pd.Timedelta(days=max_dagen))
    kandidaten = pd.date_range(start, pd.Timestamp(tot) - pd.Timedelta(days=1), freq="D").date
    return [d for d in kandidaten if d not in gedaan]


def log_run(cfg: Config, run_utc: pd.Timestamp, run_type: str, origin: date, duur_s: float, status: str, melding: str = "") -> None:
    runs_dir(cfg).mkdir(parents=True, exist_ok=True)
    pad = runs_dir(cfg) / LOGBESTAND
    rij = pd.DataFrame([{"run_utc": pd.Timestamp(run_utc).tz_convert("UTC").isoformat(), "run_type": run_type,
                         "origin": str(origin), "duur_s": round(duur_s, 1), "status": status, "melding": melding}])
    rij.to_csv(pad, mode="a", header=not pad.exists(), index=False)


def lokale_tijd(ts: pd.Timestamp) -> pd.Timestamp:
    return pd.Timestamp(ts).tz_convert(TZ)
