"""Commandoregel: `epv <commando>` of `python -m stroomprijsvoorspeller <commando>`.

Fase 1: fetch, build, status. Fase 2/3: features, compare, backtest, train, predict.
Fase 4: daily, refresh, site, serve, evalueer-verversingen.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

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


def _datum(s: str | None):
    return pd.Timestamp(s).date() if s else None


def cmd_features(args) -> int:
    from stroomprijsvoorspeller.evaluation import compare

    cfg = load_config(args.config)
    f = compare.bouw_en_bewaar_features(cfg, _datum(args.start), _datum(args.einde))
    print(f"features: {len(f)} rijen, {f.shape[1]} kolommen, {f['origin'].min().date()} .. {f['origin'].max().date()}")
    return 0


def cmd_compare(args) -> int:
    from stroomprijsvoorspeller.evaluation import compare

    cfg = load_config(args.config)
    methoden = args.methoden.split(",") if args.methoden else None
    extra = {}
    if args.uit:
        extra = {"uitvoer_bestand": args.uit, "rapport": cfg.root / "reports" / f"{Path(args.uit).stem}.md"}
    tabel = compare.vergelijk(cfg, methoden, _datum(args.start), _datum(args.einde), args.hertrain, **extra)
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print(tabel.round(3).to_string(index=False))
    return 0


def cmd_backtest(args) -> int:
    from stroomprijsvoorspeller.evaluation import report

    cfg = load_config(args.config)
    pad = report.maak_rapport(cfg, gamma_aci=args.gamma)
    print(f"rapport: {pad}")
    return 0


def cmd_train(args) -> int:
    from stroomprijsvoorspeller.model import operational

    cfg = load_config(args.config)
    pad = operational.train_en_bewaar(cfg, args.methode, _datum(args.origin))
    print(f"model opgeslagen: {pad}")
    return 0


def cmd_predict(args) -> int:
    from stroomprijsvoorspeller.model import operational

    cfg = load_config(args.config)
    v = operational.voorspel(cfg, args.methode, _datum(args.origin))
    uit = args.uit or (cfg.processed_dir / "voorspelling_actueel.parquet")
    v.to_parquet(uit, index=False)
    kort = v[["time_utc", "horizon_dag", "p10_kal", "p50", "p90_kal"]].copy()
    kort["tijd_lokaal"] = pd.DatetimeIndex(kort.pop("time_utc")).tz_convert(cfg.tijdzone).strftime("%a %d-%m %H:%M")
    with pd.option_context("display.max_rows", 200, "display.width", 120):
        print(kort.round(1).to_string(index=False))
    print(f"-> {uit}")
    return 0


def cmd_daily(args) -> int:
    from stroomprijsvoorspeller.pipeline import daily

    cfg = load_config(args.config)
    uit = daily.run(cfg, run_type=args.type, fetch=not args.geen_fetch)
    print(f"run {uit['run_type']} klaar in {uit['duur_s']:.0f} s; voorspelmoment {uit['origin']}, "
          f"model getraind op {uit['model_getraind']}, {len(uit['ingehaald'])} dagen ingehaald")
    print(f"archief: {uit['archief']}")
    print(f"site:    {uit['json']}")
    return 0


def cmd_refresh(args) -> int:
    args.type = "verversing"
    return cmd_daily(args)


def cmd_site(args) -> int:
    """Schrijft de JSON voor de site opnieuw uit de laatste gearchiveerde run (zonder te voorspellen)."""
    from stroomprijsvoorspeller.pipeline import archive, daily, site_export

    cfg = load_config(args.config)
    runs = archive.lees_runs(cfg)
    if runs.empty:
        print("geen runs in het archief; draai eerst `epv daily`", file=sys.stderr)
        return 2
    laatste = runs[runs["run_utc"] == runs["run_utc"].max()]
    prijzen = pd.read_parquet(cfg.processed_dir / "prijzen_nl_uur.parquet")
    prijzen["time_utc"] = pd.to_datetime(prijzen["time_utc"], utc=True)
    origin = laatste["origin"].iloc[0].date()
    pad = site_export.schrijf_site(cfg, laatste, prijzen, origin, laatste["run_utc"].iloc[0], laatste["run_type"].iloc[0],
                                   daily.laad_model(cfg))
    print(f"site: {pad}")
    return 0


def cmd_historie_export(args) -> int:
    from stroomprijsvoorspeller.pipeline import archive

    cfg = load_config(args.config)
    print(f"historie: {archive.exporteer_historie(cfg, cfg.operationele_methode, args.dagen)}")
    return 0


def cmd_serve(args) -> int:
    from stroomprijsvoorspeller.pipeline import serve

    cfg = load_config(args.config)
    serve.serve(cfg, poort=args.poort, open_browser=args.open)
    return 0


def cmd_evalueer_verversingen(args) -> int:
    from stroomprijsvoorspeller.evaluation import refresh

    cfg = load_config(args.config)
    print(f"rapport: {refresh.evalueer(cfg)}")
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

    fe = sub.add_parser("features", help="bouw de featurematrix (data/processed/features.parquet)")
    fe.add_argument("--start", help="eerste voorspelmoment, YYYY-MM-DD (standaard: weer_start)")
    fe.add_argument("--einde", help="laatste voorspelmoment (standaard: laatste dag met weerdata)")
    fe.set_defaults(func=cmd_features)

    c = sub.add_parser("compare", help="rolling-origin vergelijking van baselines en modellen")
    c.add_argument("--methoden", help="kommagescheiden, bijv. laatste_dag,profiel_4w,lightgbm")
    c.add_argument("--start", help="eerste voorspelmoment in de test, YYYY-MM-DD")
    c.add_argument("--einde", help="laatste voorspelmoment in de test, YYYY-MM-DD")
    c.add_argument("--hertrain", type=int, help="hertrainen elke N dagen (standaard uit config)")
    c.add_argument("--uit", help="naam van het uitvoerbestand in data/processed (standaard voorspellingen_rolling.parquet)")
    c.set_defaults(func=cmd_compare)

    bt = sub.add_parser("backtest", help="schrijf reports/backtest.md met tabellen en grafieken uit de rolling voorspellingen")
    bt.add_argument("--gamma", type=float, default=0.02, help="leersnelheid van de online kalibratie (ACI)")
    bt.set_defaults(func=cmd_backtest)

    t = sub.add_parser("train", help="train het operationele model op het rolling venster t/m vandaag")
    t.add_argument("--methode", help="bijv. lightgbm, lightgbm_d2, lightgbm_w365_hg, lineair (standaard uit config)")
    t.add_argument("--origin", help="voorspelmoment YYYY-MM-DD (standaard vandaag)")
    t.set_defaults(func=cmd_train)

    pr = sub.add_parser("predict", help="voorspel de komende dagen met het getrainde model")
    pr.add_argument("--methode", help="zelfde naam als bij train (standaard uit config)")
    pr.add_argument("--origin", help="voorspelmoment YYYY-MM-DD (standaard vandaag)")
    pr.add_argument("--uit", help="uitvoerbestand (parquet)")
    pr.set_defaults(func=cmd_predict)

    d = sub.add_parser("daily", help="dagelijkse run: ophalen, inhalen, (her)trainen, voorspellen, archiveren, JSON voor de site")
    d.add_argument("--type", choices=["auto", "hoofd", "verversing"], default="auto",
                   help="auto = hoofdrun als die er vandaag nog niet is, anders verversing")
    d.add_argument("--geen-fetch", action="store_true", help="niets ophalen, alleen met de data die er is")
    d.set_defaults(func=cmd_daily)

    r = sub.add_parser("refresh", help="lichte verversing: nieuw weer, opnieuw voorspellen met het bestaande model")
    r.add_argument("--geen-fetch", action="store_true")
    r.set_defaults(func=cmd_refresh)

    si = sub.add_parser("site", help="schrijf site/data/forecast.json opnieuw uit de laatste run")
    si.set_defaults(func=cmd_site)

    sv = sub.add_parser("serve", help="lokale server voor de site, met ververs-knop")
    sv.add_argument("--poort", type=int, default=8766)
    sv.add_argument("--open", action="store_true", help="open de site in de browser")
    sv.set_defaults(func=cmd_serve)

    he = sub.add_parser("historie-export", help="compacte backtest-historie voor online gebruik -> data/processed/voorspellingen_historie.parquet")
    he.add_argument("--dagen", type=int, default=150)
    he.set_defaults(func=cmd_historie_export)

    ev = sub.add_parser("evalueer-verversingen", help="rapport over de waarde van de verversingsruns -> reports/verversingen.md")
    ev.set_defaults(func=cmd_evalueer_verversingen)

    args = p.parse_args(argv)
    _logging(args.verbose)
    return args.func(args)
