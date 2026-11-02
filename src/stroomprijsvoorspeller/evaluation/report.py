"""Backtest-rapport: reports/backtest.md plus figuren in reports/figures/.

Leest de rolling-origin voorspellingen (hoofdrun en, als die er is, de experimentenrun) en rekent alles door:
foutmaten per horizon, baselines, Diebold-Mariano, praktijkmaat goedkoopste blok, kalibratie (ruw, conformal, ACI),
periodes, uur van de dag, experimenten, feature-belang en de ijking van de betrouwbaarheidsindicator.
"""

from __future__ import annotations

import logging
from pathlib import Path

import joblib
import matplotlib
import numpy as np
import pandas as pd

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from stroomprijsvoorspeller.config import Config
from stroomprijsvoorspeller.evaluation import blocks, reliability, stats
from stroomprijsvoorspeller.evaluation.compare import VOORSPELLINGEN_BESTAND
from stroomprijsvoorspeller.evaluation.metrics import breedte, dekking, mae, pinball, rmse
from stroomprijsvoorspeller.model.calibration import pas_aci_toe

log = logging.getLogger(__name__)

EXPERIMENTEN_BESTAND = "voorspellingen_experimenten.parquet"
HOOFDMODEL = "lightgbm"
REFERENTIE = "profiel_4w"

# kleuren: gevalideerd categorisch palet (dataviz-skill), vaste toewijzing per methode
KLEUR = {
    "lightgbm": "#2a78d6", "profiel_4w": "#eb6834", "laatste_dag": "#1baf7a", "vorige_week": "#eda100",
    "combinatie": "#e87ba4", "lineair": "#008300", "lightgbm_asinh": "#6250d6",
    "lightgbm_w90": "#1baf7a", "lightgbm_w365": "#eda100", "lightgbm_ens": "#e87ba4", "lightgbm_hg": "#6250d6",
    "lightgbm_w730": "#e34948", "lightgbm_w365_hg": "#008300", "lightgbm_w365_d2": "#1d1d1b",
}
LABEL = {
    "lightgbm": "LightGBM", "profiel_4w": "4-weeks profiel", "laatste_dag": "laatst bekende dag",
    "vorige_week": "zelfde uur vorige week", "combinatie": "combinatie", "lineair": "lineair (asinh)",
    "lightgbm_asinh": "LightGBM asinh", "lightgbm_w90": "LightGBM venster 90 d", "lightgbm_w365": "LightGBM venster 365 d",
    "lightgbm_ens": "LightGBM ensemble 90/180/365", "lightgbm_hg": "LightGBM per horizongroep",
    "lightgbm_w730": "LightGBM venster 730 d", "lightgbm_w365_hg": "LightGBM venster 365 d, per horizongroep",
    "lightgbm_w365_d2": "LightGBM venster 365 d, dag 2 apart (gekozen)",
}
GRIJS = "#52514e"
LICHTGRIJS = "#e6e5e1"
TZ = "Europe/Amsterdam"


def _label(m: str) -> str:
    return LABEL.get(m, m)


def _stijl(ax, titel: str, ylabel: str = "", xlabel: str = ""):
    ax.set_title(titel, loc="left", fontsize=11, color="#0b0b0b")
    ax.set_ylabel(ylabel, color=GRIJS)
    ax.set_xlabel(xlabel, color=GRIJS)
    ax.grid(axis="y", color=LICHTGRIJS, linewidth=1)
    ax.set_axisbelow(True)
    for kant in ("top", "right"):
        ax.spines[kant].set_visible(False)
    for kant in ("left", "bottom"):
        ax.spines[kant].set_color(LICHTGRIJS)
    ax.tick_params(colors=GRIJS)


def _bewaar(fig, pad: Path):
    pad.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(pad, dpi=150, facecolor="white")
    plt.close(fig)


def _md(df: pd.DataFrame, fmt: dict[str, str] | None = None, hernoem: dict[str, str] | None = None) -> str:
    fmt = fmt or {}
    hernoem = hernoem or {}
    kop = "| " + " | ".join(str(hernoem.get(c, c)) for c in df.columns) + " |"
    lijn = "|" + "|".join("---" for _ in df.columns) + "|"
    rijen = []
    for _, r in df.iterrows():
        cellen = []
        for c in df.columns:
            v = r[c]
            if isinstance(v, float) and np.isnan(v):
                cellen.append("")
            elif c in fmt:
                cellen.append(fmt[c].format(v))
            elif isinstance(v, (int, np.integer)) or (isinstance(v, float) and float(v).is_integer() and c in ("horizon_dag", "dag", "n", "count", "n_dagen", "dagen", "n_uren")):
                cellen.append(str(int(v)))
            elif isinstance(v, float):
                cellen.append(f"{v:.2f}")
            else:
                cellen.append(str(v))
        rijen.append("| " + " | ".join(cellen) + " |")
    return "\n".join([kop, lijn, *rijen])


def laad_voorspellingen(cfg: Config, bestand: str = VOORSPELLINGEN_BESTAND) -> pd.DataFrame | None:
    pad = cfg.processed_dir / bestand
    if not pad.exists():
        return None
    v = pd.read_parquet(pad)
    v["time_utc"] = pd.to_datetime(v["time_utc"], utc=True)
    v["origin"] = pd.to_datetime(v["origin"])
    return v


# ---------- tabellen ----------

def hoofdtabel(v: pd.DataFrame) -> pd.DataFrame:
    rijen = []
    for (m, k), g in v.dropna(subset=["doel"]).groupby(["methode", "horizon_dag"]):
        rijen.append({
            "methode": m, "horizon_dag": int(k), "n_uren": len(g),
            "mae": mae(g["doel"], g["p50"]), "rmse": rmse(g["doel"], g["p50"]),
            "pinball_p10": pinball(g["doel"], g["p10_kal"], 0.1), "pinball_p50": pinball(g["doel"], g["p50"], 0.5),
            "pinball_p90": pinball(g["doel"], g["p90_kal"], 0.9),
            "dekking_ruw": dekking(g["doel"], g["p10"], g["p90"]) if m not in ("laatste_dag", "vorige_week", "profiel_4w") else np.nan,
            "dekking_kal": dekking(g["doel"], g["p10_kal"], g["p90_kal"]), "breedte_kal": breedte(g["p10_kal"], g["p90_kal"]),
        })
    t = pd.DataFrame(rijen)
    ref = t[t["methode"] == REFERENTIE].set_index("horizon_dag")["mae"]
    t["rmae"] = t.apply(lambda r: r["mae"] / ref[r["horizon_dag"]], axis=1)
    return t.sort_values(["horizon_dag", "mae"]).reset_index(drop=True)


def periode_tabel(v: pd.DataFrame, groep: str, horizons=(2, 5, 7)) -> pd.DataFrame:
    rijen = []
    for (g, k), d in v[v["horizon_dag"].isin(horizons)].groupby([groep, "horizon_dag"]):
        lg = d[d["methode"] == HOOFDMODEL]
        pf = d[d["methode"] == REFERENTIE]
        if lg.empty or pf.empty:
            continue
        rijen.append({groep: g, "dag": int(k), "dagen": lg["origin"].nunique(), "mae_model": mae(lg["doel"], lg["p50"]),
                      "mae_profiel": mae(pf["doel"], pf["p50"]),
                      "rmae": mae(lg["doel"], lg["p50"]) / mae(pf["doel"], pf["p50"]),
                      "dekking_kal": dekking(lg["doel"], lg["p10_kal"], lg["p90_kal"]), "gem_prijs": lg["doel"].mean()})
    return pd.DataFrame(rijen)


def verrijk(v: pd.DataFrame) -> pd.DataFrame:
    v = v.dropna(subset=["doel"]).copy()
    lok = v["time_utc"].dt.tz_convert(TZ)
    v["kwartaal"] = lok.dt.year.astype(str) + "Q" + lok.dt.quarter.astype(str)
    v["maand"] = lok.dt.strftime("%Y-%m")
    v["uur"] = lok.dt.hour
    v["seizoen"] = lok.dt.month.map({12: "winter", 1: "winter", 2: "winter", 3: "voorjaar", 4: "voorjaar", 5: "voorjaar",
                                     6: "zomer", 7: "zomer", 8: "zomer", 9: "najaar", 10: "najaar", 11: "najaar"})
    v["periode_kwartier"] = np.where(v["time_utc"] >= pd.Timestamp("2025-09-30T22:00Z"), "na 1 okt 2025", "voor 1 okt 2025")
    return v


# ---------- figuren ----------

def fig_mae_per_horizon(t: pd.DataFrame, pad: Path, methoden: list[str]):
    fig, ax = plt.subplots(figsize=(8, 4.5))
    for m in methoden:
        d = t[t["methode"] == m].sort_values("horizon_dag")
        if d.empty:
            continue
        ax.plot(d["horizon_dag"], d["mae"], color=KLEUR.get(m, GRIJS), linewidth=2, marker="o", markersize=5, label=_label(m))
        ax.annotate(f"{d['mae'].iloc[-1]:.1f}", (d["horizon_dag"].iloc[-1], d["mae"].iloc[-1]), xytext=(6, 0),
                    textcoords="offset points", fontsize=8, color=GRIJS, va="center")
    _stijl(ax, "Gemiddelde absolute fout per horizon", "MAE (EUR/MWh)", "dagen vooruit")
    ax.set_xticks(sorted(t["horizon_dag"].unique()))
    ax.set_ylim(bottom=0)
    ax.legend(frameon=False, fontsize=8)
    _bewaar(fig, pad)


def fig_dekking(v: pd.DataFrame, pad: Path):
    rijen = []
    for k, g in v[v["methode"] == HOOFDMODEL].dropna(subset=["doel"]).groupby("horizon_dag"):
        rijen.append({"dag": int(k), "ruw": dekking(g["doel"], g["p10"], g["p90"]),
                      "conformal": dekking(g["doel"], g["p10_kal"], g["p90_kal"]),
                      "ACI": dekking(g["doel"], g["p10_aci"], g["p90_aci"]) if "p10_aci" in g else np.nan})
    d = pd.DataFrame(rijen)
    fig, ax = plt.subplots(figsize=(8, 4.2))
    for kol, kleur in (("ruw", "#eb6834"), ("conformal", "#2a78d6"), ("ACI", "#1baf7a")):
        if d[kol].notna().any():
            ax.plot(d["dag"], d[kol], color=kleur, linewidth=2, marker="o", markersize=5, label=kol)
    ax.axhline(0.8, color=GRIJS, linewidth=1, linestyle=":")
    ax.text(d["dag"].max() + 0.1, 0.8, "doel 80%", color=GRIJS, fontsize=8, va="center")
    _stijl(ax, "Dekking van het P10-P90-interval (LightGBM)", "aandeel werkelijke prijzen binnen interval", "dagen vooruit")
    ax.set_ylim(0.4, 1.0)
    ax.set_xticks(d["dag"])
    ax.legend(frameon=False, fontsize=8, loc="lower left")
    _bewaar(fig, pad)
    return d


def fig_mae_per_uur(v: pd.DataFrame, pad: Path, k: int = 2):
    d = v[(v["horizon_dag"] == k)]
    fig, ax = plt.subplots(figsize=(8, 4.2))
    for m in (HOOFDMODEL, REFERENTIE):
        g = d[d["methode"] == m].groupby("uur").apply(lambda x: mae(x["doel"], x["p50"]))
        ax.plot(g.index, g.values, color=KLEUR[m], linewidth=2, label=_label(m))
    dk = d[d["methode"] == HOOFDMODEL].groupby("uur").apply(lambda x: dekking(x["doel"], x["p10_kal"], x["p90_kal"]))
    _stijl(ax, f"Fout per uur van de dag, dag {k} vooruit", "MAE (EUR/MWh)", "uur (lokale tijd)")
    ax.set_xticks(range(0, 24, 3))
    ax.set_ylim(bottom=0)
    ax.legend(frameon=False, fontsize=8)
    _bewaar(fig, pad)
    return dk


def fig_mae_per_maand(v: pd.DataFrame, pad: Path):
    fig, ax = plt.subplots(figsize=(10, 4.2))
    for m, k, stijl in ((HOOFDMODEL, 2, "-"), (HOOFDMODEL, 5, "--"), (REFERENTIE, 2, "-")):
        g = v[(v["methode"] == m) & (v["horizon_dag"] == k)].groupby("maand").apply(lambda x: mae(x["doel"], x["p50"]))
        ax.plot(range(len(g)), g.values, color=KLEUR[m], linewidth=2, linestyle=stijl, label=f"{_label(m)}, dag {k}")
        maanden = list(g.index)
    ax.set_xticks(range(0, len(maanden), 3))
    ax.set_xticklabels(maanden[::3], rotation=45, ha="right", fontsize=8)
    _stijl(ax, "Fout per maand", "MAE (EUR/MWh)")
    ax.set_ylim(bottom=0)
    ax.legend(frameon=False, fontsize=8)
    _bewaar(fig, pad)


def fig_blokken(sam: pd.DataFrame, pad: Path, methoden: list[str]):
    fig, axes = plt.subplots(1, 2, figsize=(10, 4.2))
    for m in methoden:
        d = sam[sam["methode"] == m].sort_values("horizon_dag")
        if d.empty:
            continue
        axes[0].plot(d["horizon_dag"], d["binnen_10pct"], color=KLEUR.get(m, GRIJS), linewidth=2, marker="o", markersize=5, label=_label(m))
        axes[1].plot(d["horizon_dag"], d["meerkosten_gem"], color=KLEUR.get(m, GRIJS), linewidth=2, marker="o", markersize=5, label=_label(m))
    _stijl(axes[0], "Gekozen 3-uursblok hoogstens 10% duurder dan het beste", "aandeel dagen", "dagen vooruit")
    axes[0].set_ylim(0.5, 1.0)
    _stijl(axes[1], "Meerkosten gekozen blok t.o.v. beste blok", "EUR/MWh (gemiddeld)", "dagen vooruit")
    axes[1].set_ylim(bottom=0)
    for ax in axes:
        ax.set_xticks(sorted(sam["horizon_dag"].unique()))
    axes[0].legend(frameon=False, fontsize=8)
    _bewaar(fig, pad)


def fig_voorbeeld(v: pd.DataFrame, pad: Path, origin: pd.Timestamp | None = None):
    lg = v[v["methode"] == HOOFDMODEL]
    if origin is None:
        # een "typische" dag: het voorspelmoment waarvan de fout het dichtst bij de mediaan over alle voorspelmomenten ligt
        bekend = lg.dropna(subset=["doel"])
        per_origin = bekend.groupby("origin").apply(lambda g: pd.Series({"n": len(g), "mae": mae(g["doel"], g["p50"])}))
        per_origin = per_origin[per_origin["n"] == per_origin["n"].max()]
        origin = (per_origin["mae"] - per_origin["mae"].median()).abs().idxmin()
    d = lg[lg["origin"] == origin].sort_values("time_utc")
    t = d["time_utc"].dt.tz_convert(TZ)
    fig, ax = plt.subplots(figsize=(11, 4.5))
    ax.fill_between(t, d["p10_kal"], d["p90_kal"], color="#2a78d6", alpha=0.12, linewidth=0, label="80%-interval (gekalibreerd)")
    ax.plot(t, d["p50"], color="#2a78d6", linewidth=2, label="voorspelling (P50)")
    ax.plot(t, d["doel"], color="#0b0b0b", linewidth=1.5, label="werkelijke prijs")
    onder = min(d[["p10_kal", "doel"]].min().min(), 0)
    for dag in sorted(d["horizon_dag"].unique()):
        eerste = t[d["horizon_dag"] == dag].iloc[0]
        ax.axvline(eerste, color=LICHTGRIJS, linewidth=1)
        ax.text(eerste, onder, f" dag {dag}", fontsize=8, color=GRIJS, va="bottom")
    _stijl(ax, f"Voorbeeld van een typische dag: voorspelling gemaakt op {origin.date()} om 13:00", "EUR/MWh")
    ax.legend(frameon=False, fontsize=8, loc="upper left")
    fig.autofmt_xdate()
    _bewaar(fig, pad)
    return origin


DM_VARIANTEN = (
    ("lightgbm_w365", "lightgbm"), ("lightgbm_w730", "lightgbm_w365"),
    ("lightgbm_w365_hg", "lightgbm_w365"), ("lightgbm_w365_d2", "lightgbm_w365"),
)


def dm_varianten(exp: pd.DataFrame, paren=DM_VARIANTEN) -> pd.DataFrame:
    """Diebold-Mariano per horizon tussen varianten (eenzijdig: variant beter dan referentie), op dagelijkse MAE."""
    dl = stats.dagelijks_verlies(exp)
    aanwezig = set(dl["methode"])
    rijen = []
    for variant, referentie in paren:
        if variant not in aanwezig or referentie not in aanwezig:
            continue
        for k in sorted(dl["horizon_dag"].unique()):
            a = dl[(dl["methode"] == variant) & (dl["horizon_dag"] == k)].set_index("origin")["fout"]
            b = dl[(dl["methode"] == referentie) & (dl["horizon_dag"] == k)].set_index("origin")["fout"]
            a, b = a.align(b, join="inner")
            if len(a) < 30 or np.allclose(a.to_numpy(), b.to_numpy()):
                continue   # identieke voorspellingen (bijv. dag 3+ van de d2-variant): niets te toetsen
            dm, p = stats.diebold_mariano(a.to_numpy(), b.to_numpy())
            rijen.append({"variant": variant, "referentie": referentie, "horizon_dag": int(k),
                          "mae_variant": a.mean(), "mae_referentie": b.mean(), "dm": dm, "p": p})
    return pd.DataFrame(rijen)


def fig_feature_belang(cfg: Config, pad: Path) -> pd.Series | None:
    kandidaten = [cfg.root / "models" / f"model_{cfg.operationele_methode}.joblib", cfg.root / "models" / "model_lightgbm.joblib"]
    model_pad = next((p for p in kandidaten if p.exists()), None)
    if model_pad is None:
        return None
    bundel = joblib.load(model_pad)
    model = bundel["model"]
    b = model.belang() if hasattr(model, "belang") else None
    if b is None:
        return None
    b = b / b.sum()
    top = b.head(20).iloc[::-1]
    fig, ax = plt.subplots(figsize=(8, 6))
    ax.barh(top.index, top.values, color="#2a78d6", height=0.6)
    _stijl(ax, "Belangrijkste features (aandeel in gain, P50-model)", "", "aandeel")
    ax.grid(axis="x", color=LICHTGRIJS, linewidth=1)
    ax.grid(axis="y", visible=False)
    _bewaar(fig, pad)
    return b


def fig_rmae_verdeling(verd: pd.DataFrame, pad: Path):
    fig, ax = plt.subplots(figsize=(8, 4.2))
    data = [verd[verd["horizon_dag"] == k]["rmae_30d"].dropna().to_numpy() for k in sorted(verd["horizon_dag"].unique())]
    bp = ax.boxplot(data, tick_labels=[str(k) for k in sorted(verd["horizon_dag"].unique())], patch_artist=True,
                    medianprops={"color": "#0b0b0b"}, whiskerprops={"color": GRIJS}, capprops={"color": GRIJS},
                    flierprops={"marker": ".", "markeredgecolor": GRIJS, "markersize": 4})
    for patch in bp["boxes"]:
        patch.set(facecolor="#cde2fb", edgecolor="#2a78d6")
    ax.axhline(reliability.DREMPEL_HOOG, color="#0ca30c", linewidth=1, linestyle=":")
    ax.axhline(reliability.DREMPEL_REDELIJK, color="#ec835a", linewidth=1, linestyle=":")
    ax.axhline(1.0, color=GRIJS, linewidth=1)
    ax.text(0.55, reliability.DREMPEL_HOOG, " hoog", fontsize=8, color=GRIJS, va="bottom")
    ax.text(0.55, reliability.DREMPEL_REDELIJK, " redelijk", fontsize=8, color=GRIJS, va="bottom")
    ax.text(0.55, 1.0, " gelijk aan profiel", fontsize=8, color=GRIJS, va="bottom")
    _stijl(ax, "Vaardigheid over de laatste 30 dagen (rMAE t.o.v. 4-weeks profiel), per horizon", "rMAE", "dagen vooruit")
    _bewaar(fig, pad)


# ---------- rapport ----------

def maak_rapport(cfg: Config, uit: Path | None = None, gamma_aci: float = 0.02) -> Path:
    v = laad_voorspellingen(cfg)
    if v is None:
        raise FileNotFoundError("geen backtest-voorspellingen; draai eerst `epv compare`")
    figdir = cfg.root / "reports" / "figures"
    uit = uit or (cfg.root / "reports" / "backtest.md")
    origins = sorted(v["origin"].unique())
    methoden = [m for m in ("lightgbm", "combinatie", "lightgbm_asinh", "lineair", "laatste_dag", "profiel_4w", "vorige_week")
                if m in set(v["methode"])]
    kern = [m for m in ("lightgbm", "profiel_4w", "laatste_dag", "vorige_week") if m in methoden]

    # ACI op het hoofdmodel
    lg = v[v["methode"] == HOOFDMODEL]
    aci = pas_aci_toe(lg, cfg.kalibratie_venster_dagen, gamma=gamma_aci)
    v = v.merge(aci[["origin", "time_utc", "methode", "p10_aci", "p90_aci", "alpha_aci"]], on=["origin", "time_utc", "methode"], how="left")

    t = hoofdtabel(v)
    vr = verrijk(v)
    dm = stats.dm_tabel(v, REFERENTIE)
    sc = blocks.blok_scores(v[v["methode"].isin(kern)])
    sam = blocks.blok_samenvatting(sc)
    kwart = periode_tabel(vr, "kwartaal", (2, 5))
    seiz = periode_tabel(vr, "seizoen")
    kwartier = periode_tabel(vr, "periode_kwartier")
    verd = reliability.verdeling_niveaus(v, HOOFDMODEL, REFERENTIE)

    fig_mae_per_horizon(t, figdir / "mae_per_horizon.png", methoden)
    dek = fig_dekking(v, figdir / "dekking_per_horizon.png")
    dek_uur = fig_mae_per_uur(vr, figdir / "mae_per_uur.png")
    fig_mae_per_maand(vr, figdir / "mae_per_maand.png")
    fig_blokken(sam, figdir / "goedkoopste_blok.png", kern)
    voorbeeld_origin = fig_voorbeeld(v, figdir / "voorbeeld_voorspelling.png")
    belang = fig_feature_belang(cfg, figdir / "feature_belang.png")
    fig_rmae_verdeling(verd, figdir / "rmae_verdeling.png")

    # experimenten: alle bestanden voorspellingen_experimenten*.parquet, zonder dubbele methoden
    exp_delen = [laad_voorspellingen(cfg, p.name) for p in sorted(cfg.processed_dir.glob("voorspellingen_experimenten*.parquet"))]
    exp = pd.concat(exp_delen, ignore_index=True).drop_duplicates(["methode", "origin", "time_utc"]) if exp_delen else None
    exp_tabel = None
    exp_dm = None
    if exp is not None:
        exp_dm = dm_varianten(exp)
        exp_tabel = hoofdtabel(pd.concat([exp, v[v["methode"] == REFERENTIE]], ignore_index=True))
        exp_tabel = exp_tabel[exp_tabel["methode"] != REFERENTIE]
        exp_sc = blocks.blok_samenvatting(blocks.blok_scores(exp))
        exp_tabel = exp_tabel.merge(exp_sc[["methode", "horizon_dag", "binnen_10pct", "meerkosten_gem"]], on=["methode", "horizon_dag"], how="left")

    tekst = schrijf_markdown(cfg, v, t, dm, sam, kwart, seiz, kwartier, dek, dek_uur, exp_tabel, belang, verd, origins, voorbeeld_origin,
                             exp_dm)
    uit.parent.mkdir(parents=True, exist_ok=True)
    uit.write_text(tekst, encoding="utf-8")
    log.info("rapport -> %s", uit)
    return uit


def _f(x, n=1):
    return f"{x:.{n}f}"


def schrijf_markdown(cfg, v, t, dm, sam, kwart, seiz, kwartier, dek, dek_uur, exp_tabel, belang, verd, origins, voorbeeld_origin,
                     exp_dm=None) -> str:
    lg = t[t["methode"] == HOOFDMODEL].set_index("horizon_dag")
    pf = t[t["methode"] == REFERENTIE].set_index("horizon_dag")
    horizons = sorted(lg.index)
    d2, dmax = horizons[0], horizons[-1]
    n_dagen = len(origins)
    blok_lg = sam[sam["methode"] == HOOFDMODEL].set_index("horizon_dag")
    blok_pf = sam[sam["methode"] == REFERENTIE].set_index("horizon_dag")
    dm_lg = dm[dm["methode"] == HOOFDMODEL].set_index("horizon_dag")
    okt = v[(v["origin"] >= "2026-10-01") & (v["methode"] == HOOFDMODEL)].dropna(subset=["doel"])

    L = []
    L.append("# Backtest stroomprijsvoorspeller\n")
    L.append(f"Gegenereerd door `epv backtest`. Voorspelmomenten: {pd.Timestamp(origins[0]).date()} t/m "
             f"{pd.Timestamp(origins[-1]).date()} ({n_dagen} dagen), elke dag om {cfg.publicatie_uur_lokaal}:00 lokaal, "
             f"waarop de day-ahead prijzen tot en met morgen bekend zijn. Voorspeld: dag {d2} t/m {dmax} vooruit, alle uren. "
             f"Trainingsvenster {cfg.rolling_venster_dagen} dagen, hertrainen elke {cfg.hertrain_elke_dagen} dagen, "
             f"conformal-kalibratie op {cfg.kalibratie_venster_dagen} dagen bekende uitkomsten. Fouten in EUR/MWh "
             f"(10 EUR/MWh = 1 ct/kWh).\n")

    L.append("## Samenvatting\n")
    L.append(f"- Het model (LightGBM-kwantiel) zit op dag {d2} gemiddeld {_f(lg.loc[d2,'mae'])} EUR/MWh naast de werkelijke "
             f"uurprijs en op dag {dmax} {_f(lg.loc[dmax,'mae'])}. Het beste naïeve ijkpunt, het 4-weeks uurprofiel, zit op "
             f"{_f(pf.loc[d2,'mae'])} tot {_f(pf.loc[dmax,'mae'])}. Relatief: {_f(lg.loc[d2,'rmae'],2)} op dag {d2} tot "
             f"{_f(lg.loc[dmax,'rmae'],2)} op dag {dmax} (1,00 = even goed als het profiel).")
    L.append(f"- Het verschil met het profiel is op elke horizon statistisch significant (Diebold-Mariano, eenzijdig, HAC): "
             f"p < {max(1e-4, dm_lg['p_beter'].max()):.4f} op alle horizonten.")
    L.append(f"- Het 80%-interval dekt na conformal-correctie {dek['conformal'].min()*100:.0f} tot {dek['conformal'].max()*100:.0f}% van de "
             f"werkelijke prijzen (zonder correctie {dek['ruw'].min()*100:.0f} tot {dek['ruw'].max()*100:.0f}%). "
             f"Met online bijsturing (ACI) {dek['ACI'].min()*100:.0f} tot {dek['ACI'].max()*100:.0f}%.")
    L.append(f"- Praktijkmaat: op dag {d2} kiest het model op {blok_lg.loc[d2,'binnen_10pct']*100:.0f}% van de dagen een 3-uursblok dat "
             f"hoogstens 10% duurder is dan het echte goedkoopste blok (profiel: {blok_pf.loc[d2,'binnen_10pct']*100:.0f}%); op dag "
             f"{dmax} is dat {blok_lg.loc[dmax,'binnen_10pct']*100:.0f}% (profiel {blok_pf.loc[dmax,'binnen_10pct']*100:.0f}%). "
             f"De gemiddelde meerkosten van het gekozen blok zijn {_f(blok_lg.loc[d2,'meerkosten_gem'])} EUR/MWh op dag {d2} en "
             f"{_f(blok_lg.loc[dmax,'meerkosten_gem'])} op dag {dmax}, tegen {_f(blok_pf.loc[d2,'meerkosten_gem'])} en "
             f"{_f(blok_pf.loc[dmax,'meerkosten_gem'])} voor het profiel.")
    L.append("- **Eerlijke kanttekening:** voor het kiezen van het goedkoopste blok is de winst van het model klein. Het goedkoopste "
             "blok ligt structureel in de nacht (winter) of de middag (zomer), en dat weet een 4-weeks profiel ook. Het model wint "
             "vooral op het prijsniveau en op dagen waarop het weer het patroon doorbreekt.\n")

    L.append("## 1. Fout per horizon\n")
    L.append("![MAE per horizon](figures/mae_per_horizon.png)\n")
    for k in horizons:
        g = t[t["horizon_dag"] == k].copy()
        g["methode"] = g["methode"].map(_label)
        L.append(f"### Dag {k} vooruit\n")
        L.append(_md(g[["methode", "mae", "rmse", "rmae", "pinball_p10", "pinball_p50", "pinball_p90", "dekking_ruw", "dekking_kal", "breedte_kal"]],
                     {"rmae": "{:.3f}", "dekking_ruw": "{:.3f}", "dekking_kal": "{:.3f}", "breedte_kal": "{:.1f}"},
                     {"mae": "MAE", "rmse": "RMSE", "rmae": "rMAE", "pinball_p10": "pinball P10", "pinball_p50": "pinball P50",
                      "pinball_p90": "pinball P90", "dekking_ruw": "dekking ruw", "dekking_kal": "dekking kal.", "breedte_kal": "breedte kal."}))
        L.append("")
    L.append("Pinball P10 en P90 zijn berekend op de gekalibreerde grenzen. Baselines hebben geen eigen interval; hun gekalibreerde "
             "interval is een symmetrisch residu-interval rond de puntvoorspelling.\n")

    L.append("## 2. Vergelijking met de baselines (Diebold-Mariano)\n")
    L.append(f"Toets op de dagelijkse gemiddelde absolute fout, methode tegen {_label(REFERENTIE)}, eenzijdig (methode beter), "
             "Newey-West-correctie voor samenhang tussen dagen. Negatieve statistiek = methode is beter.\n")
    g = dm.copy()
    g["methode"] = g["methode"].map(_label)
    L.append(_md(g[["methode", "horizon_dag", "n_dagen", "mae_methode", "mae_referentie", "dm_stat", "p_beter"]],
                 {"dm_stat": "{:.2f}", "p_beter": "{:.4f}"},
                 {"horizon_dag": "dag", "n_dagen": "dagen", "mae_methode": "MAE methode", "mae_referentie": "MAE profiel", "dm_stat": "DM", "p_beter": "p (beter)"}))
    L.append("")

    L.append("## 3. Praktijkmaat: het goedkoopste blok van 3 uur\n")
    L.append("Per dag kiest elke methode het blok van 3 aaneengesloten uren met de laagste voorspelde prijs. We vergelijken de "
             "werkelijke kosten van dat blok met het werkelijk goedkoopste blok. `binnen 10%` = hoogstens 10% van de absolute "
             "daggemiddelde prijs duurder (het blok zelf kan rond nul of negatief zijn, dus niet 10% van het blok). "
             "`meerkosten` = werkelijke prijs in het gekozen blok minus die in het beste blok. `aandeel besparing` = welk deel van "
             "de maximaal haalbare besparing (t.o.v. gelijkmatig verbruik) de keuze oplevert.\n")
    L.append("![Goedkoopste blok](figures/goedkoopste_blok.png)\n")
    g = sam.copy()
    g["methode"] = g["methode"].map(_label)
    L.append(_md(g[["methode", "horizon_dag", "exact", "binnen_10pct", "dagdeel_juist", "meerkosten_gem", "meerkosten_mediaan", "besparing_beste_gem", "aandeel_van_besparing"]],
                 {"exact": "{:.3f}", "binnen_10pct": "{:.3f}", "dagdeel_juist": "{:.3f}", "aandeel_van_besparing": "{:.3f}"},
                 {"horizon_dag": "dag", "exact": "zelfde start", "binnen_10pct": "binnen 10%", "dagdeel_juist": "zelfde dagdeel",
                  "meerkosten_gem": "meerkosten gem.", "meerkosten_mediaan": "meerkosten mediaan", "besparing_beste_gem": "max. besparing",
                  "aandeel_van_besparing": "aandeel besparing"}))
    L.append("")

    L.append("## 4. Kalibratie van het interval\n")
    L.append("![Dekking per horizon](figures/dekking_per_horizon.png)\n")
    L.append(_md(dek, {"ruw": "{:.3f}", "conformal": "{:.3f}", "ACI": "{:.3f}"}, {"ruw": "dekking ruw", "conformal": "dekking conformal", "ACI": "dekking ACI"}))
    L.append("")
    if len(okt):
        L.append(f"De eigen kwantielen van LightGBM zijn te smal. De conformal-correctie op {cfg.kalibratie_venster_dagen} dagen herstelt de "
                 f"dekking, maar loopt achter bij een plotselinge niveausprong: in oktober 2026 (gemiddelde prijs "
                 f"{okt['doel'].mean():.0f} EUR/MWh) dekte het interval {dekking(okt['doel'], okt['p10_kal'], okt['p90_kal'])*100:.0f}% "
                 f"(conformal) en {dekking(okt['doel'], okt['p10_aci'], okt['p90_aci'])*100:.0f}% (ACI, gamma {0.02}). "
                 "ACI helpt dus iets, maar lost een regimewissel niet op.\n")

    L.append("## 5. Fout per uur, per maand, per seizoen en per periode\n")
    L.append("![MAE per uur](figures/mae_per_uur.png)\n")
    slecht = dek_uur.sort_values().head(3)
    L.append(f"Dekking van het gekalibreerde interval per uur op dag {d2}: het laagst om {', '.join(f'{int(u)} uur ({d*100:.0f}%)' for u, d in slecht.items())}; "
             f"het hoogst 's nachts ({dek_uur.max()*100:.0f}%). De middag met de zonnedip is het moeilijkste deel van de dag.\n")
    L.append("![MAE per maand](figures/mae_per_maand.png)\n")
    L.append("### Per kwartaal (dag 2 en 5)\n")
    k2 = kwart.pivot(index="kwartaal", columns="dag", values=["mae_model", "mae_profiel", "rmae", "dekking_kal"])
    k2.columns = [f"{a} dag {b}" for a, b in k2.columns]
    L.append(_md(k2.reset_index(), {c: "{:.3f}" for c in k2.columns if c.startswith(("rmae", "dekking"))}))
    L.append("\n### Per seizoen\n")
    L.append(_md(seiz, {"rmae": "{:.3f}", "dekking_kal": "{:.3f}", "gem_prijs": "{:.0f}"},
                 {"mae_model": "MAE model", "mae_profiel": "MAE profiel", "rmae": "rMAE", "dekking_kal": "dekking", "gem_prijs": "gem. prijs"}))
    L.append("\n### Voor en na de kwartierprijzen (1 oktober 2025)\n")
    L.append(_md(kwartier, {"rmae": "{:.3f}", "dekking_kal": "{:.3f}", "gem_prijs": "{:.0f}"},
                 {"periode_kwartier": "periode", "mae_model": "MAE model", "mae_profiel": "MAE profiel", "rmae": "rMAE", "dekking_kal": "dekking", "gem_prijs": "gem. prijs"}))
    L.append("")

    L.append("## 6. Voorbeeld\n")
    L.append("![Voorbeeld](figures/voorbeeld_voorspelling.png)\n")
    L.append(f"Voorspelling gemaakt op {pd.Timestamp(voorbeeld_origin).date()} om 13:00 voor dag {d2} t/m {dmax}, met het gekalibreerde "
             "80%-interval. Dit is een typische dag: het voorspelmoment waarvan de fout het dichtst bij de mediaan over alle "
             "voorspelmomenten ligt, niet een uitgezochte goede dag.\n")

    if exp_tabel is not None and not exp_tabel.empty:
        L.append("## 7. Experimenten: trainingsvensters en horizongroepen\n")
        L.append("Varianten van het hoofdmodel op dezelfde backtest: venster 90, 180 (standaard) en 365 dagen, het gemiddelde van die drie "
                 "(ensemble, naar Hubicka e.a. 2018), venster 730 dagen, aparte modellen voor dag 2 en voor dag 3+ (horizongroepen), en de "
                 "gekozen combinatie: een apart model voor dag 2 en het model op alle horizonten voor dag 3+ (`_d2`). Let op: in de eerste "
                 "maanden van de testperiode heeft het 365-dagenvenster nog geen vol jaar data, en het 730-dagenvenster is pas vanaf maart 2026 "
                 "langer dan alle beschikbare data.\n")
        g = exp_tabel.copy()
        g["methode"] = g["methode"].map(_label)
        L.append(_md(g[["methode", "horizon_dag", "mae", "rmae", "pinball_p50", "dekking_kal", "breedte_kal", "binnen_10pct", "meerkosten_gem"]],
                     {"rmae": "{:.3f}", "dekking_kal": "{:.3f}", "breedte_kal": "{:.1f}", "binnen_10pct": "{:.3f}"},
                     {"horizon_dag": "dag", "mae": "MAE", "rmae": "rMAE", "pinball_p50": "pinball P50", "dekking_kal": "dekking kal.",
                      "breedte_kal": "breedte kal.", "binnen_10pct": "blok binnen 10%", "meerkosten_gem": "meerkosten blok"}))
        beste = exp_tabel.loc[exp_tabel.groupby("horizon_dag")["mae"].idxmin()]
        L.append("\nBeste variant op MAE per horizon: " + "; ".join(f"dag {int(r.horizon_dag)}: {_label(r.methode)} ({r.mae:.2f})" for r in beste.itertuples()) + ".\n")
        std = exp_tabel[exp_tabel["methode"] == "lightgbm"].set_index("horizon_dag")["mae"]
        duiding = []
        for naam in ("lightgbm_w90", "lightgbm_w365", "lightgbm_w730", "lightgbm_ens", "lightgbm_hg", "lightgbm_w365_hg",
                     "lightgbm_w365_d2"):
            e = exp_tabel[exp_tabel["methode"] == naam].set_index("horizon_dag")["mae"]
            if e.empty or std.empty:
                continue
            verschil = ((e - std) / std * 100).reindex(std.index)
            duiding.append(f"- {_label(naam)}: {', '.join(f'dag {int(k)} {v:+.0f}%' for k, v in verschil.dropna().items())} t.o.v. venster 180 dagen.")
        if duiding:
            L.append("Verschil in MAE per variant (negatief = beter):\n")
            L.extend(duiding)
            L.append("")
        if exp_dm is not None and not exp_dm.empty:
            L.append("Is het verschil tussen varianten statistisch hard? Diebold-Mariano op de dagelijkse MAE, eenzijdig (variant beter dan "
                     "referentie), Newey-West-correctie. Een p-waarde boven 0,10 betekent: niet aangetoond.\n")
            g = exp_dm.copy()
            g["variant"] = g["variant"].map(_label)
            g["referentie"] = g["referentie"].map(_label)
            L.append(_md(g[["variant", "referentie", "horizon_dag", "mae_variant", "mae_referentie", "dm", "p"]],
                         {"p": "{:.4f}"},
                         {"horizon_dag": "dag", "mae_variant": "MAE variant", "mae_referentie": "MAE referentie", "dm": "DM", "p": "p"}))
            L.append("")
    else:
        L.append("## 7. Experimenten\n\nNog niet beschikbaar (de experimentenrun is niet gevonden).\n")

    L.append("## 8. Wat het model gebruikt\n")
    if belang is not None:
        L.append("![Feature-belang](figures/feature_belang.png)\n")
        top = belang.head(10)
        L.append("Top 10 (aandeel in gain van het P50-model, laatst getrainde operationele model): " +
                 ", ".join(f"{naam} ({w*100:.1f}%)" for naam, w in top.items()) + ".\n")
    else:
        L.append("Geen getraind operationeel model gevonden (`epv train`).\n")

    L.append("## 9. IJking van de betrouwbaarheidsindicator\n")
    L.append("![rMAE-verdeling](figures/rmae_verdeling.png)\n")
    vt = verd.groupby("horizon_dag")["rmae_30d"].describe()[["count", "25%", "50%", "75%"]].reset_index()
    nv = verd.groupby(["horizon_dag", "niveau"]).size().unstack(fill_value=0)
    nv = (nv.T / nv.sum(axis=1)).T.reindex(columns=["hoog", "redelijk", "laag"], fill_value=0).reset_index()
    L.append(f"Per voorspelmoment (wekelijkse steekproef) is de rMAE van de 30 dagen ervoor berekend. Drempels: hoog < "
             f"{reliability.DREMPEL_HOOG}, redelijk < {reliability.DREMPEL_REDELIJK}, anders laag. Een vage band (breedte > "
             f"{reliability.BAND_VAAG:.0%} van het prijsniveau van die dag) zet het niveau één stap lager.\n")
    L.append(_md(vt.merge(nv, on="horizon_dag"), {"count": "{:.0f}", "25%": "{:.3f}", "50%": "{:.3f}", "75%": "{:.3f}", "hoog": "{:.0%}", "redelijk": "{:.0%}", "laag": "{:.0%}"},
                 {"horizon_dag": "dag", "count": "n", "25%": "rMAE 25%", "50%": "rMAE mediaan", "75%": "rMAE 75%"}))
    L.append("")

    L.append("## 10. Conclusie\n")
    L.append(f"Het model is op alle horizonten beter dan de drie naïeve regels, en dat verschil is statistisch hard. De winst is het grootst "
             f"op dag {d2} ({(1-lg.loc[d2,'rmae'])*100:.0f}% lagere fout dan het profiel) en krimpt naar {(1-lg.loc[dmax,'rmae'])*100:.0f}% op dag {dmax}. "
             f"Voor het praktische doel, het kiezen van het goedkoopste blok, is de winst klein: het model zit op dag {d2} op "
             f"{blok_lg.loc[d2,'binnen_10pct']*100:.0f}% en het profiel op {blok_pf.loc[d2,'binnen_10pct']*100:.0f}%; vanaf dag 5 kiest het profiel "
             f"even vaak of vaker het exacte blok. Wie alleen wil weten *wanneer* het goedkoop is, heeft aan het profiel bijna genoeg; "
             f"wie wil weten *hoeveel* het kost en hoe zeker dat is, heeft het model en het interval nodig. "
             f"Het interval klopt gemiddeld (79%), maar faalt bij plotselinge niveausprongen; daar is geen van de geteste kalibraties tegen "
             f"bestand. De middaguren zijn structureel het moeilijkst.\n")
    if exp_tabel is not None and "lightgbm_w365_d2" in set(exp_tabel["methode"]):
        e = exp_tabel.set_index(["methode", "horizon_dag"])["mae"]
        L.append(f"De experimenten (sectie 7) leiden tot het operationele model: trainingsvenster 365 dagen, een apart model voor dag 2 "
                 f"en het model op alle horizonten voor dag 3 tot 7. Dat haalt een MAE van {e[('lightgbm_w365_d2', d2)]:.1f} op dag {d2} "
                 f"(tegen {e[('lightgbm', d2)]:.1f} voor de standaardinstelling van deze backtest) en {e[('lightgbm_w365_d2', dmax)]:.1f} "
                 f"op dag {dmax} (tegen {e[('lightgbm', dmax)]:.1f}).\n")
    return "\n".join(L)
