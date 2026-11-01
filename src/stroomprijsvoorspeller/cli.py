"""Commandoregel: `epv <commando>` of `python -m stroomprijsvoorspeller <commando>`.

Fase 1: fetch, build, status. Latere fases voegen train, backtest, predict en daily toe.
"""

from __future__ import annotations

import argparse
import logging
import sys

import pandas as pd

from stroomprijsvoorspeller.config import load_config
from stroomprijsvoorspeller.processing import dataset
from stroomprijsvoorspeller.sources import energy_charts, entsoe, open_meteo


def _logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )


def cmd_fetch(args) -> int:
    cfg = load_config(args.config)
    if args.alleen in (None, "prijzen"):
        if cfg.prijsbron == "entsoe":
            if not entsoe.beschikbaar():
                print("prijsbron entsoe gekozen maar ENTSOE_TOKEN ontbreekt", file=sys.stderr)
                return 2
            start = pd.Timestamp(cfg.data_start, tz="UTC")
            df = entsoe.fetch_prices(start, pd.Timestamp.now(tz="UTC") + pd.Timedelta(days=2), bzn=cfg.biedzone)
            cfg.raw_dir.mkdir(parents=True, exist_ok=True)
            df.to_parquet(cfg.raw_dir / energy_charts.RUW_BESTAND, index=False)
        else:
            energy_charts.update_prices(cfg.raw_dir, cfg.data_start, bzn=cfg.biedzone)
    if args.alleen in (None, "weer"):
        open_meteo.update_previous_runs(cfg)
        if not args.geen_forecast:
            open_meteo.store_forecasts(cfg)
    return 0


def cmd_build(args) -> int:
    cfg = load_config(args.config)
    paden = dataset.bouw_alles(cfg)
    for naam, pad in paden.items():
        print(f"{naam:10s} {pad}")
    return 0


def cmd_status(args) -> int:
    cfg = load_config(args.config)
    ruw = energy_charts.lees_ruw(cfg.raw_dir)
    print(f"config:      {cfg.root / 'config.yaml'}")
    print(f"prijsbron:   {cfg.prijsbron}  (ENTSO-E token aanwezig: {entsoe.beschikbaar()})")
    if ruw.empty:
        print("prijzen:     geen data")
    else:
        print(f"prijzen:     {len(ruw)} rijen, {ruw['time_utc'].min()} .. {ruw['time_utc'].max()}")
    for punt in cfg.weerpunten:
        pad = open_meteo.prev_runs_bestand(cfg.raw_dir, punt.naam)
        if pad.exists():
            df = pd.read_parquet(pad, columns=["time_utc"])
            print(f"weer {punt.naam:22s} {len(df):6d} uren t/m {pd.to_datetime(df['time_utc'].max(), utc=True)}")
        else:
            print(f"weer {punt.naam:22s} geen data")
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="epv", description="stroomprijsvoorspeller")
    p.add_argument("--config", help="pad naar config.yaml (standaard: zoekt omhoog vanaf de werkmap)")
    p.add_argument("-v", "--verbose", action="store_true")
    sub = p.add_subparsers(dest="cmd", required=True)

    f = sub.add_parser("fetch", help="haal prijzen en weer op (incrementeel)")
    f.add_argument("--alleen", choices=["prijzen", "weer"], help="alleen deze bron")
    f.add_argument("--geen-forecast", action="store_true", help="sla de actuele weersverwachting over")
    f.set_defaults(func=cmd_fetch)

    b = sub.add_parser("build", help="bouw de verwerkte datasets in data/processed")
    b.set_defaults(func=cmd_build)

    s = sub.add_parser("status", help="toon wat er aan data is")
    s.set_defaults(func=cmd_status)

    args = p.parse_args(argv)
    _logging(args.verbose)
    return args.func(args)
