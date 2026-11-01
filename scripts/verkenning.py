"""Verkennend datarapport: figuren en kerncijfers voor reports/verkenning/data-verkenning.md.

Leest alleen uit data/processed/ en config.yaml. Schrijft png's naar reports/verkenning/figuren/
en kerncijfers naar reports/verkenning/kerncijfers.json (gebruikt bij het schrijven van de tekst).

Draaien vanuit de projectmap:  .venv\\Scripts\\python scripts\\verkenning.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import yaml

matplotlib.use("Agg")

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
UIT = ROOT / "reports" / "verkenning"
FIG = UIT / "figuren"
FIG.mkdir(parents=True, exist_ok=True)

CFG = yaml.safe_load((ROOT / "config.yaml").read_text(encoding="utf-8"))
TZ = CFG["tijdzone"]

# Rustige kleuren (gevalideerde standaardpalet van de dataviz-richtlijn, vaste volgorde).
BLAUW, ORANJE, AQUA, GEEL = "#2a78d6", "#eb6834", "#1baf7a", "#eda100"
GRIJS, TEKST, TEKST2, GRID = "#9a9994", "#0b0b0b", "#52514e", "#e6e5e1"
# Sequentieel blauw voor jaren (licht = vroeg, donker = laat).
JAARKLEUR = {2022: "#b7d3f6", 2023: "#86b6ef", 2024: "#5598e7", 2025: "#256abf", 2026: "#0d366b"}
SEIZOEN_NAAM = {0: "winter (dec-feb)", 1: "voorjaar (mrt-mei)", 2: "zomer (jun-aug)", 3: "najaar (sep-nov)"}
SEIZOEN_KLEUR = {0: BLAUW, 1: AQUA, 2: ORANJE, 3: GEEL}
DAGDEEL_NAAM = ["nacht (0-6)", "ochtend (6-12)", "middag (12-18)", "avond (18-24)"]
DAGDEEL_KLEUR = ["#0d366b", "#5598e7", ORANJE, "#9a9994"]

plt.rcParams.update(
    {
        "figure.dpi": 150,
        "savefig.dpi": 150,
        "font.size": 9.5,
        "axes.titlesize": 10.5,
        "axes.titleweight": "bold",
        "axes.labelsize": 9.5,
        "axes.edgecolor": GRID,
        "axes.labelcolor": TEKST2,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "grid.color": GRID,
        "grid.linewidth": 0.8,
        "xtick.color": TEKST2,
        "ytick.color": TEKST2,
        "legend.frameon": False,
        "legend.fontsize": 9,
        "text.color": TEKST,
        "figure.facecolor": "white",
        "axes.facecolor": "white",
    }
)

KERN: dict = {}  # kerncijfers voor de tekst


def jaar_as(ax: plt.Axes) -> None:
    """Jaartallen op de x-as, maanden als kleine streepjes."""
    import matplotlib.dates as mdates

    ax.xaxis.set_major_locator(mdates.YearLocator())
    ax.xaxis.set_major_formatter(mdates.DateFormatter("%Y"))
    ax.xaxis.set_minor_locator(mdates.MonthLocator(bymonth=[4, 7, 10]))


def bewaar(fig: plt.Figure, naam: str) -> None:
    fig.tight_layout()
    fig.savefig(FIG / naam, bbox_inches="tight")
    plt.close(fig)
    print("  figuur:", naam)


# ---------------------------------------------------------------- data laden
def laad_basis() -> pd.DataFrame:
    b = pd.read_parquet(PROC / "basis_uur.parquet").copy()
    b["t_lok"] = b.index.tz_convert(TZ)
    b["datum"] = pd.to_datetime(b["datum_lokaal"])
    b["jaar"] = b["t_lok"].dt.year
    b["jaarmaand"] = b["datum"].dt.to_period("M")
    return b


# ---------------------------------------------------------------- 1 maandniveau
def fig1_maandniveau(b: pd.DataFrame) -> None:
    g = b.groupby("jaarmaand")["prijs_eur_mwh"]
    m = pd.DataFrame({"gem": g.mean(), "p10": g.quantile(0.10), "p90": g.quantile(0.90), "n": g.size()})
    m = m[m["n"] >= 24 * 25]  # alleen (bijna) volledige maanden
    x = m.index.to_timestamp()
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.fill_between(x, m["p10"], m["p90"], color=BLAUW, alpha=0.18, linewidth=0, label="P10 - P90 van de uurprijzen")
    ax.plot(x, m["gem"], color=BLAUW, linewidth=2, label="maandgemiddelde")
    ax.axhline(0, color=GRIJS, linewidth=0.8)
    ax.set_ylabel("prijs (EUR/MWh)")
    ax.set_title("Day-ahead stroomprijs Nederland per maand")
    ax.legend(loc="upper right")
    jaar_as(ax)
    bewaar(fig, "01_maandniveau.png")
    per_jaar = b.groupby("jaar")["prijs_eur_mwh"].agg(["mean", "std"]).round(1)
    KERN["maand"] = {
        "eerste_maand": str(m.index[0]),
        "laatste_maand": str(m.index[-1]),
        "hoogste_maand": {"maand": str(m["gem"].idxmax()), "gem": round(m["gem"].max(), 1)},
        "laagste_maand": {"maand": str(m["gem"].idxmin()), "gem": round(m["gem"].min(), 1)},
        "per_jaar": per_jaar.to_dict("index"),
        "p10_p90_laatste12": {
            "p10": round(m["p10"].iloc[-12:].mean(), 1),
            "p90": round(m["p90"].iloc[-12:].mean(), 1),
            "gem": round(m["gem"].iloc[-12:].mean(), 1),
        },
    }


# ---------------------------------------------------------------- 2 dagprofiel
def fig2_dagprofiel(b: pd.DataFrame) -> None:
    fig, axes = plt.subplots(2, 2, figsize=(9, 6), sharex=True, sharey=True)
    for s, ax in zip(range(4), axes.ravel()):
        d = b[b["seizoen"] == s]
        for vrij, kleur, naam in [(False, BLAUW, "werkdag"), (True, ORANJE, "weekend of feestdag")]:
            prof = d[d["is_vrije_dag"] == vrij].groupby("uur_lokaal")["prijs_eur_mwh"].mean()
            ax.plot(prof.index, prof.values, color=kleur, linewidth=2, label=naam)
        ax.set_title(SEIZOEN_NAAM[s].capitalize())
        ax.set_xticks(range(0, 24, 3))
    for ax in axes[1]:
        ax.set_xlabel("uur van de dag (lokale tijd)")
    for ax in axes[:, 0]:
        ax.set_ylabel("gemiddelde prijs (EUR/MWh)")
    axes[0, 0].legend(loc="upper left")
    fig.suptitle("Gemiddeld dagprofiel per seizoen, nov 2022 t/m nu", fontweight="bold")
    bewaar(fig, "02a_dagprofiel_seizoen.png")

    # Zonnedip per jaar: zomerhalfjaar (apr-sep), alle dagen.
    z = b[b["maand"].between(4, 9) & (b["jaar"] >= 2023)]
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(9, 3.8), gridspec_kw={"width_ratios": [2, 1]})
    dip = {}
    for jaar, d in z.groupby("jaar"):
        prof = d.groupby("uur_lokaal")["prijs_eur_mwh"].mean()
        ax1.plot(prof.index, prof.values, color=JAARKLEUR[jaar], linewidth=2, label=str(jaar))
        daggem = d["prijs_eur_mwh"].mean()
        middag = d[d["uur_lokaal"].between(12, 14)]["prijs_eur_mwh"].mean()
        dip[jaar] = {"daggem": round(daggem, 1), "middag_12_15": round(middag, 1),
                     "dip_eur": round(daggem - middag, 1), "dip_pct": round(100 * (daggem - middag) / daggem, 0)}
    ax1.set_title("Dagprofiel april t/m september, per jaar")
    ax1.set_xlabel("uur van de dag (lokale tijd)")
    ax1.set_ylabel("gemiddelde prijs (EUR/MWh)")
    ax1.set_xticks(range(0, 24, 3))
    ax1.axhline(0, color=GRIJS, linewidth=0.8)
    ax1.legend(title="jaar", loc="lower left")
    jaren = list(dip)
    ax2.bar([str(j) for j in jaren], [dip[j]["dip_pct"] for j in jaren], color=[JAARKLEUR[j] for j in jaren], width=0.6)
    for i, j in enumerate(jaren):
        ax2.text(i, dip[j]["dip_pct"] + 1, f"{dip[j]['dip_pct']:.0f}%", ha="center", color=TEKST2)
    ax2.set_title("Zonnedip: hoeveel goedkoper is 12-15 uur\ndan het daggemiddelde")
    ax2.set_ylabel("% onder daggemiddelde")
    ax2.grid(axis="x", visible=False)
    bewaar(fig, "02b_zonnedip_per_jaar.png")
    KERN["zonnedip"] = dip
    # piekuur avond en dalu per seizoen, werkdag
    prof = b[~b["is_vrije_dag"]].groupby(["seizoen", "uur_lokaal"])["prijs_eur_mwh"].mean().unstack()
    KERN["profiel_werkdag"] = {
        SEIZOEN_NAAM[s]: {"duurste_uur": int(prof.loc[s].idxmax()), "duur": round(prof.loc[s].max(), 0),
                          "goedkoopste_uur": int(prof.loc[s].idxmin()), "goedkoop": round(prof.loc[s].min(), 0)}
        for s in range(4)
    }


# ---------------------------------------------------------------- 3 negatieve prijzen
def fig3_negatief(b: pd.DataFrame) -> None:
    b = b.copy()
    b["neg"] = b["prijs_eur_mwh"] < 0
    b["laag"] = b["prijs_eur_mwh"] < 10
    fig, axes = plt.subplots(1, 3, figsize=(11, 3.8), gridspec_kw={"width_ratios": [1, 2, 1.4]})

    pj = b.groupby("jaar")[["neg", "laag"]].mean() * 100
    uren_jaar = b.groupby("jaar")[["neg", "laag"]].sum()
    labels = [f"{j}\n(nov-dec)" if j == 2022 else (f"{j}\n(t/m okt)" if j == 2026 else str(j)) for j in pj.index]
    xi = np.arange(len(pj))
    axes[0].bar(xi - 0.2, pj["laag"], width=0.4, color="#9ec5f4", label="onder 10 EUR/MWh")
    axes[0].bar(xi + 0.2, pj["neg"], width=0.4, color=BLAUW, label="onder 0 EUR/MWh")
    axes[0].set_xticks(xi, labels, fontsize=8)
    axes[0].set_ylabel("aandeel van de uren (%)")
    axes[0].set_title("Per jaar")
    axes[0].set_ylim(0, 15)
    axes[0].legend(loc="upper left", fontsize=8)
    axes[0].grid(axis="x", visible=False)

    pm = b.groupby("jaarmaand")[["neg", "laag"]].mean() * 100
    x = pm.index.to_timestamp()
    axes[1].fill_between(x, 0, pm["laag"], color="#9ec5f4", step="mid", label="onder 10 EUR/MWh")
    axes[1].fill_between(x, 0, pm["neg"], color=BLAUW, step="mid", label="onder 0 EUR/MWh")
    axes[1].set_title("Per maand")
    axes[1].set_ylabel("aandeel van de uren (%)")
    jaar_as(axes[1])

    pu = b.groupby("uur_lokaal")[["neg", "laag"]].mean() * 100
    axes[2].bar(pu.index, pu["laag"], color="#9ec5f4", width=0.8, label="onder 10 EUR/MWh")
    axes[2].bar(pu.index, pu["neg"], color=BLAUW, width=0.8, label="onder 0 EUR/MWh")
    axes[2].set_xticks(range(0, 24, 3))
    axes[2].set_xlabel("uur van de dag (lokale tijd)")
    axes[2].set_title("Per uur van de dag")
    axes[2].grid(axis="x", visible=False)
    fig.suptitle("Hoe vaak is de prijs negatief of lager dan 10 EUR/MWh?", fontweight="bold")
    bewaar(fig, "03_negatieve_prijzen.png")

    neg_maand = b[b["neg"]].groupby("maand").size()
    neg_dagtype = b[b["neg"]].groupby("is_vrije_dag").size()
    dagen_met_neg = b[b["neg"]].groupby("jaar")["datum"].nunique()
    KERN["negatief"] = {
        "pct_per_jaar": pj.round(1).to_dict("index"),
        "uren_per_jaar": uren_jaar.to_dict("index"),
        "dagen_met_negatief_per_jaar": dagen_met_neg.to_dict(),
        "neg_top3_maanden": neg_maand.sort_values(ascending=False).head(3).to_dict(),
        "neg_aandeel_vrije_dag_pct": round(100 * neg_dagtype.get(True, 0) / neg_dagtype.sum(), 0),
        "neg_pct_per_uur": pu["neg"].round(1).to_dict(),
        "neg_uren_11_16_aandeel_pct": round(100 * b[b["neg"] & b["uur_lokaal"].between(11, 16)].shape[0] / b["neg"].sum(), 0),
        "laagste_prijs": {"prijs": b["prijs_eur_mwh"].min(), "tijd": str(b.loc[b["prijs_eur_mwh"].idxmin(), "t_lok"])},
        "hoogste_prijs": {"prijs": b["prijs_eur_mwh"].max(), "tijd": str(b.loc[b["prijs_eur_mwh"].idxmax(), "t_lok"])},
    }


# ---------------------------------------------------------------- 4 + 5 spreiding en goedkoopste blok
def dagtabel(b: pd.DataFrame) -> pd.DataFrame:
    """Per lokale dag: gemiddelde, max-min, goedkoopste aaneengesloten 3-uursblok (op basis van de volgorde in de tijd)."""
    rijen = []
    for datum, d in b.groupby("datum", sort=True):
        p = d.sort_index()["prijs_eur_mwh"].to_numpy()
        uren = d.sort_index()["uur_lokaal"].to_numpy()
        if len(p) < 20:
            continue
        blok = np.convolve(p, np.ones(3) / 3, mode="valid")
        i = int(blok.argmin())
        rijen.append(
            {
                "datum": datum,
                "gem": p.mean(),
                "min": p.min(),
                "max": p.max(),
                "spreiding": p.max() - p.min(),
                "blok_gem": blok[i],
                "blok_start_uur": int(uren[i]),
                "blok_midden_uur": int(uren[min(i + 1, len(uren) - 1)]),
                "seizoen": int(d["seizoen"].iloc[0]),
                "jaar": int(d["jaar"].iloc[0]),
                "is_vrije_dag": bool(d["is_vrije_dag"].iloc[0]),
            }
        )
    t = pd.DataFrame(rijen)
    t["winst"] = t["gem"] - t["blok_gem"]  # EUR/MWh voordeel t.o.v. daggemiddelde
    t["winst_pct"] = 100 * t["winst"] / t["gem"].where(t["gem"] > 1)
    t["dagdeel"] = pd.cut(t["blok_midden_uur"], [-1, 5, 11, 17, 24], labels=DAGDEEL_NAAM)
    t["jaarmaand"] = pd.to_datetime(t["datum"]).dt.to_period("M")
    return t


def fig4_spreiding(t: pd.DataFrame) -> None:
    g = t.groupby("jaarmaand")
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 3.8))
    x = g["spreiding"].median().index.to_timestamp()
    ax1.fill_between(x, g["spreiding"].quantile(0.25), g["spreiding"].quantile(0.75), color=BLAUW, alpha=0.18, linewidth=0, label="25% - 75% van de dagen")
    ax1.plot(x, g["spreiding"].median(), color=BLAUW, linewidth=2, label="mediaan per maand")
    ax1.set_title("Spreiding binnen een dag (duurste min goedkoopste uur)")
    ax1.set_ylabel("EUR/MWh")
    ax1.legend(loc="upper right")
    ax2.fill_between(x, g["winst"].quantile(0.25), g["winst"].quantile(0.75), color=ORANJE, alpha=0.18, linewidth=0, label="25% - 75% van de dagen")
    ax2.plot(x, g["winst"].median(), color=ORANJE, linewidth=2, label="mediaan per maand")
    ax2.set_title("Voordeel goedkoopste 3-uursblok t.o.v. daggemiddelde")
    ax2.set_ylabel("EUR/MWh")
    ax2.legend(loc="upper right")
    jaar_as(ax1)
    jaar_as(ax2)
    bewaar(fig, "04_spreiding_binnen_dag.png")
    pj = t.groupby("jaar").agg(spreiding_mediaan=("spreiding", "median"), spreiding_gem=("spreiding", "mean"),
                               winst_mediaan=("winst", "median"), winst_gem=("winst", "mean"),
                               winst_pct_mediaan=("winst_pct", "median"), daggem=("gem", "mean")).round(1)
    ps = t.groupby("seizoen").agg(spreiding_mediaan=("spreiding", "median"), winst_mediaan=("winst", "median"),
                                  winst_pct_mediaan=("winst_pct", "median")).round(1)
    ps.index = [SEIZOEN_NAAM[s] for s in ps.index]
    KERN["spreiding"] = {
        "per_jaar": pj.to_dict("index"),
        "per_seizoen": ps.to_dict("index"),
        "totaal": {"spreiding_mediaan": round(t["spreiding"].median(), 1), "winst_mediaan": round(t["winst"].median(), 1),
                   "winst_pct_mediaan": round(t["winst_pct"].median(), 0),
                   "aandeel_dagen_winst_boven_30": round(100 * (t["winst"] > 30).mean(), 0),
                   "aandeel_dagen_spreiding_boven_100": round(100 * (t["spreiding"] > 100).mean(), 0)},
    }


def fig5_dagdeel(t: pd.DataFrame) -> None:
    fig, axes = plt.subplots(1, 4, figsize=(11, 3.8), sharey=True)
    tabel = {}
    for s, ax in zip(range(4), axes):
        d = t[(t["seizoen"] == s) & (t["jaar"] >= 2023)]
        aandeel = d.groupby("jaar")["dagdeel"].value_counts(normalize=True).unstack().reindex(columns=DAGDEEL_NAAM).fillna(0) * 100
        onder = np.zeros(len(aandeel))
        for dagdeel, kleur in zip(DAGDEEL_NAAM, DAGDEEL_KLEUR):
            vals = aandeel[dagdeel].to_numpy()
            ax.bar([str(j) for j in aandeel.index], vals, bottom=onder, color=kleur, width=0.65, label=dagdeel, edgecolor="white", linewidth=1.5)
            for i, v in enumerate(vals):
                if v >= 9:
                    ax.text(i, onder[i] + v / 2, f"{v:.0f}", ha="center", va="center", color="white", fontsize=8)
            onder += vals
        ax.set_title(SEIZOEN_NAAM[s].capitalize())
        ax.grid(axis="x", visible=False)
        tabel[SEIZOEN_NAAM[s]] = (t[t["seizoen"] == s]["dagdeel"].value_counts(normalize=True) * 100).round(0).to_dict()
    axes[0].set_ylabel("aandeel van de dagen (%)")
    axes[0].set_ylim(0, 100)
    axes[-1].legend(loc="upper left", bbox_to_anchor=(1.02, 1), title="dagdeel goedkoopste 3-uursblok")
    fig.suptitle("Wanneer valt het goedkoopste 3-uursblok? Per seizoen en jaar", fontweight="bold")
    bewaar(fig, "05_goedkoopste_blok_dagdeel.png")
    recent = t[t["datum"] >= pd.Timestamp("2025-11-01")]
    KERN["dagdeel"] = {
        "per_seizoen_alle_jaren": tabel,
        "laatste_12_maanden": (recent["dagdeel"].value_counts(normalize=True) * 100).round(0).to_dict(),
        "laatste_12_maanden_zomer": (recent[recent["seizoen"] == 2]["dagdeel"].value_counts(normalize=True) * 100).round(0).to_dict(),
        "laatste_12_maanden_winter": (recent[recent["seizoen"] == 0]["dagdeel"].value_counts(normalize=True) * 100).round(0).to_dict(),
    }


# ---------------------------------------------------------------- 6 weer
def fig6_weer(b: pd.DataFrame) -> None:
    w = pd.read_parquet(PROC / "weer_prev_runs.parquet")
    punten = CFG["weer"]["punten"]
    zee = [p["naam"] for p in punten if p["type"].startswith("zee")]
    land = [p["naam"] for p in punten if p["type"] in ("land", "land_buitenland")]
    alle = [p["naam"] for p in punten]
    f = pd.DataFrame(index=w.index)
    f["wind_zee"] = w[[f"{p}__wind_speed_100m_lead1" for p in zee]].mean(axis=1)
    f["wind_land"] = w[[f"{p}__wind_speed_100m_lead1" for p in land]].mean(axis=1)
    f["straling"] = w[[f"{p}__shortwave_radiation_lead1" for p in alle]].mean(axis=1)
    d = b.join(f, how="inner").dropna(subset=["wind_zee", "wind_land", "straling"])
    KERN["weer_periode"] = {"van": str(d["datum"].min().date()), "tot": str(d["datum"].max().date()), "n_uren": int(len(d))}

    fig, axes = plt.subplots(1, 3, figsize=(11, 3.8), sharey=True)
    specs = [("wind_zee", "Windsnelheid op zee, 100 m (m/s)", np.arange(0, 26, 2)),
             ("wind_land", "Windsnelheid op land, 100 m (m/s)", np.arange(0, 22, 2)),
             ("straling", "Zonnestraling (W/m²)", np.arange(0, 901, 75))]
    for ax, (kol, label, bins) in zip(axes, specs):
        for s in range(4):
            ds = d[d["seizoen"] == s]
            cat = pd.cut(ds[kol], bins)
            g = ds.groupby(cat, observed=True)["prijs_eur_mwh"].agg(["mean", "size"])
            g = g[g["size"] >= 40]
            mid = np.array([iv.mid for iv in g.index])
            ax.plot(mid, g["mean"], color=SEIZOEN_KLEUR[s], linewidth=2, marker="o", markersize=3.5, label=SEIZOEN_NAAM[s])
        ax.axhline(0, color=GRIJS, linewidth=0.8)
        ax.set_xlabel(label)
    axes[0].set_ylabel("gemiddelde uurprijs (EUR/MWh)")
    axes[0].legend(loc="upper right", fontsize=8)
    fig.suptitle("Prijs tegen weersverwachting van één dag eerder, gemiddeld per klasse, mrt 2024 t/m nu", fontweight="bold")
    bewaar(fig, "06_weer_en_prijs.png")

    corr = {}
    for s in range(4):
        ds = d[d["seizoen"] == s]
        dag = ds[ds["uur_lokaal"].between(9, 17)]
        corr[SEIZOEN_NAAM[s]] = {
            "wind_zee": round(ds["prijs_eur_mwh"].corr(ds["wind_zee"]), 2),
            "wind_land": round(ds["prijs_eur_mwh"].corr(ds["wind_land"]), 2),
            "straling_alle_uren": round(ds["prijs_eur_mwh"].corr(ds["straling"]), 2),
            "straling_9_17": round(dag["prijs_eur_mwh"].corr(dag["straling"]), 2),
        }
    corr["alle seizoenen"] = {
        "wind_zee": round(d["prijs_eur_mwh"].corr(d["wind_zee"]), 2),
        "wind_land": round(d["prijs_eur_mwh"].corr(d["wind_land"]), 2),
        "straling_alle_uren": round(d["prijs_eur_mwh"].corr(d["straling"]), 2),
        "straling_9_17": round(d[d["uur_lokaal"].between(9, 17)]["prijs_eur_mwh"].corr(d[d["uur_lokaal"].between(9, 17)]["straling"]), 2),
    }
    KERN["weer_correlatie"] = corr
    # prijs bij weinig/veel wind
    KERN["weer_klassen"] = {
        "wind_zee_onder_5": round(d[d["wind_zee"] < 5]["prijs_eur_mwh"].mean(), 0),
        "wind_zee_boven_15": round(d[d["wind_zee"] > 15]["prijs_eur_mwh"].mean(), 0),
        "straling_boven_500": round(d[d["straling"] > 500]["prijs_eur_mwh"].mean(), 0),
        "straling_0_dag_9_17": round(d[(d["straling"] < 50) & d["uur_lokaal"].between(9, 17)]["prijs_eur_mwh"].mean(), 0),
        "wind_zee_boven_15_pct_negatief": round(100 * (d[d["wind_zee"] > 15]["prijs_eur_mwh"] < 0).mean(), 0),
    }


# ---------------------------------------------------------------- 7 kwartieren
def fig7_kwartier() -> None:
    k = pd.read_parquet(PROC / "prijzen_nl_kwartier.parquet").copy()
    k["uur_utc"] = k["time_utc"].dt.floor("h")
    k["kw"] = (k["time_utc"].dt.minute // 15) + 1
    piv = k.pivot_table(index="uur_utc", columns="kw", values="prijs_eur_mwh")
    piv = piv.dropna()
    piv.columns = [f"kw{c}" for c in piv.columns]
    uurgem = piv.mean(axis=1)
    afw = piv.sub(uurgem, axis=0)
    bereik = piv.max(axis=1) - piv.min(axis=1)
    uur_lok = piv.index.tz_convert(TZ).hour
    afw_uur = afw.groupby(uur_lok).mean()
    bereik_uur = bereik.groupby(uur_lok).median()

    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 3.8))
    kwkleur = ["#0d366b", "#3987e5", "#9ec5f4", ORANJE]
    xi = np.arange(24)
    for i, (kol, kleur) in enumerate(zip(afw.columns, kwkleur)):
        ax1.bar(xi + (i - 1.5) * 0.2, afw_uur[kol], width=0.2, color=kleur, label=f"kwartier {i + 1}")
    ax1.axhline(0, color=GRIJS, linewidth=0.8)
    ax1.set_xticks(range(0, 24, 3))
    ax1.set_xlabel("uur van de dag (lokale tijd)")
    ax1.set_ylabel("afwijking van het uurgemiddelde (EUR/MWh)")
    ax1.set_title("Gemiddelde afwijking per kwartier binnen het uur")
    ax1.legend(fontsize=8, ncol=4, loc="upper center", bbox_to_anchor=(0.5, -0.22))
    ax1.grid(axis="x", visible=False)
    ax2.bar(xi, bereik_uur, color=BLAUW, width=0.8)
    ax2.set_xticks(range(0, 24, 3))
    ax2.set_xlabel("uur van de dag (lokale tijd)")
    ax2.set_ylabel("EUR/MWh")
    ax2.set_title("Verschil duurste min goedkoopste kwartier (mediaan)")
    ax2.grid(axis="x", visible=False)
    fig.suptitle(f"Kwartierprijzen, {piv.index.min().tz_convert(TZ):%d-%m-%Y} t/m {piv.index.max().tz_convert(TZ):%d-%m-%Y}", fontweight="bold")
    bewaar(fig, "07_kwartierprijzen.png")

    KERN["kwartier"] = {
        "n_uren": int(len(piv)),
        "gem_abs_afwijking": round(afw.abs().stack().mean(), 1),
        "bereik_mediaan": round(bereik.median(), 1),
        "bereik_gem": round(bereik.mean(), 1),
        "bereik_p90": round(bereik.quantile(0.9), 1),
        "aandeel_uren_bereik_boven_20": round(100 * (bereik > 20).mean(), 0),
        "aandeel_uren_bereik_boven_50": round(100 * (bereik > 50).mean(), 0),
        "gem_afwijking_per_kwartier": afw.mean().round(1).to_dict(),
        "kw1_duurder_dan_kw4_pct_uren": round(100 * (piv["kw1"] > piv["kw4"]).mean(), 0),
        "bereik_mediaan_per_uur_top3": bereik_uur.sort_values(ascending=False).head(3).round(0).to_dict(),
        "bereik_mediaan_per_uur_laagste3": bereik_uur.sort_values().head(3).round(0).to_dict(),
        "afw_kw1_uur_ochtend_6_8": afw_uur.loc[6:8, "kw1"].round(1).to_dict(),
        "afw_kw4_uur_ochtend_6_8": afw_uur.loc[6:8, "kw4"].round(1).to_dict(),
        "afw_kw1_uur_avond_17_20": afw_uur.loc[17:20, "kw1"].round(1).to_dict(),
        "afw_kw4_uur_avond_17_20": afw_uur.loc[17:20, "kw4"].round(1).to_dict(),
    }


# ---------------------------------------------------------------- 8 naïeve regels
def fig8_naief(b: pd.DataFrame) -> None:
    # matrix dag x lokaal uur (uur 2 op 25-uursdagen = gemiddelde; op 23-uursdagen leeg)
    mat = b.pivot_table(index="datum", columns="uur_lokaal", values="prijs_eur_mwh", aggfunc="mean")
    mat = mat.reindex(pd.date_range(mat.index.min(), mat.index.max(), freq="D"))
    profiel28 = mat.rolling(28, min_periods=20).mean()  # gemiddelde per uur over de laatste 28 dagen t/m de rij zelf
    horizons = CFG["voorspelling"]["backtest_horizon_dagen"]
    periodes = {"sep 2024 t/m nu": ("2024-09-01", None), "2023 t/m nu": ("2023-01-01", None)}
    res = {}
    for pnaam, (van, tot) in periodes.items():
        res[pnaam] = {}
        for h in horizons:
            # voorspelling op dag D om 13:00 voor dag D+h; laatst bekende dag = D+1, dus shift h-1
            pred_laatste = mat.shift(h - 1)
            pred_week = mat.shift(7)
            pred_prof = profiel28.shift(h - 1)
            doel = mat.loc[van:tot]
            res[pnaam][h] = {
                "laatst bekende dag": float((doel - pred_laatste.loc[van:tot]).abs().stack().mean()),
                "zelfde uur vorige week": float((doel - pred_week.loc[van:tot]).abs().stack().mean()),
                "4-weeks uurprofiel": float((doel - pred_prof.loc[van:tot]).abs().stack().mean()),
            }
    # horizon 1 (morgen = bekend) ter referentie: laatst bekende dag = vandaag
    fig, ax = plt.subplots(figsize=(7, 4))
    kleuren = {"laatst bekende dag": BLAUW, "zelfde uur vorige week": ORANJE, "4-weeks uurprofiel": AQUA}
    r = res["sep 2024 t/m nu"]
    for regel, kleur in kleuren.items():
        y = [r[h][regel] for h in horizons]
        ax.plot(horizons, y, color=kleur, linewidth=2, marker="o", markersize=5, label=regel)
        ax.text(horizons[-1] + 0.1, y[-1], f"{y[-1]:.0f}", color=kleur, va="center")
    ax.set_xlabel("horizon (dagen vooruit vanaf het voorspelmoment, 13:00)")
    ax.set_ylabel("gemiddelde absolute fout, MAE (EUR/MWh)")
    ax.set_title("Hoe goed zijn naïeve regels? Periode sep 2024 t/m nu")
    ax.set_xticks(horizons)
    ax.set_ylim(bottom=0)
    ax.legend(loc="lower right")
    bewaar(fig, "08_naieve_regels_mae.png")
    KERN["naief"] = {p: {str(h): {k: round(v, 1) for k, v in d.items()} for h, d in r.items()} for p, r in res.items()}
    # referentie: typische prijs en spreiding in die periode
    doel = mat.loc["2024-09-01":]
    KERN["naief_referentie"] = {"gem_prijs": round(doel.stack().mean(), 1), "std_prijs": round(doel.stack().std(), 1),
                               "mae_als_je_het_daggemiddelde_van_de_dag_zelf_wist": round((doel.sub(doel.mean(axis=1), axis=0)).abs().stack().mean(), 1)}


# ---------------------------------------------------------------- hoofd
def main() -> None:
    print("data laden")
    b = laad_basis()
    KERN["periode"] = {"van": str(b["datum"].min().date()), "tot": str(b["datum"].max().date()), "n_uren": int(len(b)),
                       "dagen_23u": int((b.groupby("datum").size() == 23).sum()), "dagen_25u": int((b.groupby("datum").size() == 25).sum())}
    print("1 maandniveau"); fig1_maandniveau(b)
    print("2 dagprofiel"); fig2_dagprofiel(b)
    print("3 negatief"); fig3_negatief(b)
    print("4/5 dagtabel"); t = dagtabel(b)
    fig4_spreiding(t)
    fig5_dagdeel(t)
    print("6 weer"); fig6_weer(b)
    print("7 kwartier"); fig7_kwartier()
    print("8 naief"); fig8_naief(b)
    (UIT / "kerncijfers.json").write_text(json.dumps(KERN, indent=1, ensure_ascii=False, default=str), encoding="utf-8")
    print("kerncijfers:", UIT / "kerncijfers.json")


if __name__ == "__main__":
    main()
