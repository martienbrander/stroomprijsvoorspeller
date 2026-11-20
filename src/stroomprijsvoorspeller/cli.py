"""Commandoregel: `epv <commando>` of `python -m stroomprijsvoorspeller <commando>`.

Dagelijks gebruik: daily (alles in één keer), refresh, serve. De rest zijn de losse stappen en de evaluatie:
fetch, build, status, features, compare, backtest, train, predict, site, historie-export, evalueer-verversingen,
leveranciers-status.
Elk commando is een functie `cmd_<naam>(args)` die een exitcode teruggeeft; `main` onderaan koppelt ze aan argparse.

Zware modules (LightGBM, matplotlib) worden pas geladen in het commando dat ze nodig heeft, zodat `epv status` en
`epv fetch` snel starten.
"""

from __future__ import annotations

import argparse
import logging
import sys
from datetime import date
from pathlib import Path

import pandas as pd

from stroomprijsvoorspeller.config import load_config
from stroomprijsvoorspeller.model.calibration import ACI_GAMMA
from stroomprijsvoorspeller.processing import dataset
from stroomprijsvoorspeller.sources import energy_charts, entsoe, open_meteo


def _logging(verbose: bool) -> None:
    logging.basicConfig(
        level=logging.DEBUG if verbose else logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
        stream=sys.stdout,
    )


def cmd_fetch(args: argparse.Namespace) -> int:
    """Prijzen (ENTSO-E, met terugval naar Energy-Charts en EnergyZero) en weer (Open-Meteo) ophalen."""
    cfg = load_config(args.config)
    if args.alleen in (None, "prijzen"):
        from stroomprijsvoorspeller.pipeline import daily
        bron = daily.werk_prijzen_bij(cfg)
        print(f"prijzen bijgewerkt; de nieuwste komen van {bron}")
    if args.alleen in (None, "weer"):
        open_meteo.update_previous_runs(cfg)
        if not args.geen_forecast:
            open_meteo.store_forecasts(cfg)
    return 0


def cmd_build(args: argparse.Namespace) -> int:
    cfg = load_config(args.config)
    paden = dataset.bouw_alles(cfg)
    for naam, pad in paden.items():
        print(f"{naam:10s} {pad}")
    return 0


def _datum(tekst: str | None) -> date | None:
    """YYYY-MM-DD van de commandoregel naar een datum; None als de optie niet is meegegeven."""
    return pd.Timestamp(tekst).date() if tekst else None


def cmd_features(args: argparse.Namespace) -> int:
    from stroomprijsvoorspeller.evaluation import compare

    cfg = load_config(args.config)
    f = compare.bouw_en_bewaar_features(cfg, _datum(args.start), _datum(args.einde))
    print(f"features: {len(f)} rijen, {f.shape[1]} kolommen, {f['origin'].min().date()} .. {f['origin'].max().date()}")
    return 0


def cmd_compare(args: argparse.Namespace) -> int:
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


def cmd_backtest(args: argparse.Namespace) -> int:
    from stroomprijsvoorspeller.evaluation import report

    cfg = load_config(args.config)
    pad = report.maak_rapport(cfg, gamma_aci=args.gamma)
    print(f"rapport: {pad}")
    return 0


def cmd_train(args: argparse.Namespace) -> int:
    from stroomprijsvoorspeller.model import operational

    cfg = load_config(args.config)
    pad = operational.train_en_bewaar(cfg, args.methode, _datum(args.origin))
    print(f"model opgeslagen: {pad}")
    return 0


def cmd_predict(args: argparse.Namespace) -> int:
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


def cmd_daily(args: argparse.Namespace) -> int:
    from stroomprijsvoorspeller.pipeline import daily

    cfg = load_config(args.config)
    uit = daily.run(cfg, run_type=args.type, fetch=not args.geen_fetch,
                    weer_rondes=args.weer_rondes, weer_wacht_minuten=args.weer_wacht)
    if uit["run_type"] == "overgeslagen":
        print(f"run overgeslagen: {uit['reden']} (voorspelmoment {uit['origin']})")
        return 0
    print(f"run {uit['run_type']} klaar in {uit['duur_s']:.0f} s; voorspelmoment {uit['origin']}, "
          f"model getraind op {uit['model_getraind']}, {len(uit['ingehaald'])} dagen ingehaald")
    print(f"archief: {uit['archief']}")
    print(f"site:    {uit['json']}")
    return 0


def cmd_refresh(args: argparse.Namespace) -> int:
    """`epv refresh` is `epv daily --type verversing`."""
    args.type = "verversing"
    return cmd_daily(args)


def cmd_site(args: argparse.Namespace) -> int:
    """Schrijft de JSON voor de site opnieuw uit de laatste gearchiveerde run (zonder te voorspellen)."""
    from stroomprijsvoorspeller.pipeline import archive, daily, site_export

    cfg = load_config(args.config)
    runs = archive.lees_runs(cfg)
    if runs.empty:
        print("geen runs in het archief; draai eerst `epv daily`", file=sys.stderr)
        return 2
    laatste = runs[runs["run_utc"] == runs["run_utc"].max()]
    eerste_rij = laatste.iloc[0]
    pad = site_export.schrijf_site(cfg, laatste, dataset.lees_uurprijzen(cfg), eerste_rij["origin"].date(),
                                   eerste_rij["run_utc"], eerste_rij["run_type"], daily.laad_model(cfg))
    print(f"site: {pad}")
    return 0


def cmd_historie_export(args: argparse.Namespace) -> int:
    from stroomprijsvoorspeller.pipeline import archive

    cfg = load_config(args.config)
    print(f"historie: {archive.exporteer_historie(cfg, cfg.operationele_methode, args.dagen)}")
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    from stroomprijsvoorspeller.pipeline import serve

    cfg = load_config(args.config)
    serve.serve(cfg, poort=args.poort, open_browser=args.open, netwerk=args.netwerk)
    return 0


def cmd_evalueer_verversingen(args: argparse.Namespace) -> int:
    from stroomprijsvoorspeller.evaluation import refresh

    cfg = load_config(args.config)
    print(f"rapport: {refresh.evalueer(cfg)}")
    return 0


def cmd_leveranciers_status(args: argparse.Namespace) -> int:
    """Leeftijd van de leverancierstabel. Met --strikt is de exitcode 3 als de lijst toe is aan controle."""
    from stroomprijsvoorspeller.pipeline import leveranciers

    cfg = load_config(args.config)
    vandaag = _datum(args.datum) or date.today()
    stand = leveranciers.bepaal_stand(cfg, vandaag)
    print(leveranciers.melding(stand, vandaag))
    return 3 if (stand.verouderd and args.strikt) else 0


def cmd_status(args: argparse.Namespace) -> int:
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
    """Leest de commandoregel en voert het gekozen commando uit."""
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
    bt.add_argument("--gamma", type=float, default=ACI_GAMMA, help="leersnelheid van de online kalibratie (ACI)")
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
    d.add_argument("--type", choices=["auto", "hoofd", "verversing", "middag"], default="auto",
                   help="auto = hoofdrun als die er vandaag nog niet is, anders verversing; middag = hoofdrun zodra de prijzen "
                        "voor morgen binnen zijn, anders niets doen (rooster online)")
    d.add_argument("--geen-fetch", action="store_true", help="niets ophalen, alleen met de data die er is")
    d.add_argument("--weer-rondes", type=int, default=1,
                   help="hoe vaak een verversing de weerbron opnieuw probeert als die niet antwoordt (standaard 1: niet wachten)")
    d.add_argument("--weer-wacht", type=float, default=20.0, help="minuten wachten tussen twee rondes (standaard 20)")
    d.set_defaults(func=cmd_daily)

    r = sub.add_parser("refresh", help="lichte verversing: nieuw weer, opnieuw voorspellen met het bestaande model")
    r.add_argument("--geen-fetch", action="store_true")
    r.set_defaults(func=cmd_refresh)

    si = sub.add_parser("site", help="schrijf site/data/forecast.json opnieuw uit de laatste run")
    si.set_defaults(func=cmd_site)

    sv = sub.add_parser("serve", help="lokale server voor de site, met ververs-knop")
    sv.add_argument("--poort", type=int, default=8766)
    sv.add_argument("--open", action="store_true", help="open de site in de browser")
    sv.add_argument("--netwerk", action="store_true", help="ook bereikbaar voor telefoon of andere pc op hetzelfde wifinetwerk")
    sv.set_defaults(func=cmd_serve)

    he = sub.add_parser("historie-export", help="compacte backtest-historie voor online gebruik -> data/processed/voorspellingen_historie.parquet")
    he.add_argument("--dagen", type=int, default=150)
    he.set_defaults(func=cmd_historie_export)

    ev = sub.add_parser("evalueer-verversingen", help="rapport over de waarde van de verversingsruns -> reports/verversingen.md")
    ev.set_defaults(func=cmd_evalueer_verversingen)

    ls = sub.add_parser("leveranciers-status", help="leeftijd van data/leveranciers.yaml: is de lijst toe aan controle?")
    ls.add_argument("--strikt", action="store_true", help="exitcode 3 als de lijst toe is aan controle (voor de workflow)")
    ls.add_argument("--datum", help="reken met deze dag als vandaag, YYYY-MM-DD (om te testen)")
    ls.set_defaults(func=cmd_leveranciers_status)

    args = p.parse_args(argv)
    _logging(args.verbose)
    return args.func(args)
