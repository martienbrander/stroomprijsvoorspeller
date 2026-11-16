"""Evaluatie van de verversingsruns (PLAN.md, sectie "Evaluatie van de verversingsruns"; besluit 33).

Vergelijkt per doeluur de hoofdrun van een voorspelmoment met elke latere verversing van hetzelfde voorspelmoment,
zodra de echte prijs bekend is. Schrijft reports/verversingen.md.
"""

from __future__ import annotations

import logging
from pathlib import Path

import numpy as np
import pandas as pd

from stroomprijsvoorspeller.config import Config
from stroomprijsvoorspeller.evaluation import stats
from stroomprijsvoorspeller.evaluation.blocks import goedkoopste_blok
from stroomprijsvoorspeller.evaluation.metrics import dekking, pinball
from stroomprijsvoorspeller.pipeline import archive
from stroomprijsvoorspeller.processing.features import DOEL
from stroomprijsvoorspeller.timeutil import TZ, local_date

log = logging.getLogger(__name__)

SLOTS = (19, 1, 7)          # verversingsmomenten (lokaal uur) uit besluit 33
MIN_PAREN_BESLUIT = 40      # dagen met volledige paren voordat de beslisregel geldt
LAADBLOK_UREN = 3


def slot_van(run_utc: pd.Timestamp) -> int:
    """Dichtstbijzijnde verversingsslot (lokaal uur) van een runtijd."""
    uur = pd.Timestamp(run_utc).tz_convert(TZ).hour + pd.Timestamp(run_utc).tz_convert(TZ).minute / 60
    return min(SLOTS, key=lambda s: min(abs(uur - s), 24 - abs(uur - s)))


def paren(runs: pd.DataFrame) -> pd.DataFrame:
    """Per doeluur: fout van de hoofdrun naast die van elke verversing van hetzelfde voorspelmoment."""
    r = runs[~runs["bekend"].astype(bool)].dropna(subset=[DOEL])
    hoofd = r[r["run_type"] == "hoofd"].sort_values("run_utc").drop_duplicates(["origin", "time_utc"], keep="last")
    verv = r[r["run_type"] == "verversing"].copy()
    if hoofd.empty or verv.empty:
        return pd.DataFrame()
    verv["slot"] = verv["run_utc"].map(slot_van)
    verv = verv.sort_values("run_utc").drop_duplicates(["origin", "time_utc", "slot"], keep="last")
    kol = ["origin", "time_utc", "horizon_dag", "p10_kal", "p50", "p90_kal", "laadblok_start", "run_utc"]
    p = verv[[*kol, "slot", DOEL]].merge(hoofd[kol], on=["origin", "time_utc", "horizon_dag"], suffixes=("_v", "_h"))
    p["doeldag"] = local_date(pd.DatetimeIndex(p["time_utc"]))
    p["fout_h"] = (p[DOEL] - p["p50_h"]).abs()
    p["fout_v"] = (p[DOEL] - p["p50_v"]).abs()
    return p


def tabel_per_slot(p: pd.DataFrame) -> pd.DataFrame:
    rijen = []
    for (slot, k), g in p.groupby(["slot", "horizon_dag"]):
        dag_h = g.groupby("origin")["fout_h"].mean()
        dag_v = g.groupby("origin")["fout_v"].mean()
        dm, pw = (np.nan, np.nan)
        if len(dag_h) >= 10 and not np.allclose(dag_v, dag_h):
            dm, pw = stats.diebold_mariano(dag_v.to_numpy(), dag_h.to_numpy())
        rijen.append({
            "slot": f"{slot:02d}:00", "horizon_dag": int(k), "n_dagen": int(g["origin"].nunique()), "n_uren": len(g),
            "mae_hoofd": g["fout_h"].mean(), "mae_verversing": g["fout_v"].mean(),
            "verschil": g["fout_v"].mean() - g["fout_h"].mean(),
            "verschil_pct": (g["fout_v"].mean() / g["fout_h"].mean() - 1) * 100 if g["fout_h"].mean() else np.nan,
            "pinball_hoofd": (pinball(g[DOEL], g["p10_kal_h"], 0.1) + pinball(g[DOEL], g["p90_kal_h"], 0.9)) / 2,
            "pinball_verversing": (pinball(g[DOEL], g["p10_kal_v"], 0.1) + pinball(g[DOEL], g["p90_kal_v"], 0.9)) / 2,
            "dekking_hoofd": dekking(g[DOEL], g["p10_kal_h"], g["p90_kal_h"]),
            "dekking_verversing": dekking(g[DOEL], g["p10_kal_v"], g["p90_kal_v"]),
            "dm": dm, "p": pw,
        })
    return pd.DataFrame(rijen)


def blokverschuiving(p: pd.DataFrame) -> pd.DataFrame:
    """Per (slot, doeldag): hoe vaak verschoof het laadblok door de verversing, en was het nieuwe blok achteraf goedkoper?"""
    rijen = []
    for (slot, k, origin, doeldag), g in p.groupby(["slot", "horizon_dag", "origin", "doeldag"]):
        g = g.sort_values("time_utc")
        if len(g) < 23:
            continue
        echt = g[DOEL].to_numpy()
        uren = pd.DatetimeIndex(g["time_utc"]).tz_convert(TZ).hour.to_numpy()
        s_h, s_v = g["laadblok_start_h"].iloc[0], g["laadblok_start_v"].iloc[0]
        if pd.isna(s_h) or pd.isna(s_v):
            continue
        i_h = int(np.flatnonzero(uren == int(s_h))[0]) if (uren == int(s_h)).any() else None
        i_v = int(np.flatnonzero(uren == int(s_v))[0]) if (uren == int(s_v)).any() else None
        if i_h is None or i_v is None:
            continue
        kost_h = float(np.mean(echt[i_h:i_h + LAADBLOK_UREN]))
        kost_v = float(np.mean(echt[i_v:i_v + LAADBLOK_UREN]))
        _, beste = goedkoopste_blok(echt, LAADBLOK_UREN)
        rijen.append({"slot": f"{slot:02d}:00", "horizon_dag": int(k), "origin": origin, "verschoven": s_h != s_v,
                      "winst": kost_h - kost_v, "meerkosten_hoofd": kost_h - beste, "meerkosten_verversing": kost_v - beste})
    if not rijen:
        return pd.DataFrame()
    d = pd.DataFrame(rijen)
    g = d.groupby(["slot", "horizon_dag"])
    uit = pd.DataFrame({
        "n_dagen": g.size(),
        "verschoven": g["verschoven"].mean(),
        "verschoven_en_goedkoper": g.apply(lambda x: (x["verschoven"] & (x["winst"] > 0)).mean()),
        "winst_gem": g["winst"].mean(),
        "meerkosten_hoofd": g["meerkosten_hoofd"].mean(),
        "meerkosten_verversing": g["meerkosten_verversing"].mean(),
    }).reset_index()
    return uit


def betrouwbaarheid_runs(cfg: Config) -> pd.DataFrame:
    pad = archive.runs_dir(cfg) / archive.LOGBESTAND
    if not pad.exists():
        return pd.DataFrame()
    lg = pd.read_csv(pad)
    lg["run_utc"] = pd.to_datetime(lg["run_utc"], utc=True)
    lg["slot"] = np.where(lg["run_type"] == "verversing", lg["run_utc"].map(lambda t: f"{slot_van(t):02d}:00"), lg["run_type"])
    # middagpogingen zonder nieuwe prijzen (status overgeslagen) zijn geen mislukte runs
    echt = lg[lg["status"] != "overgeslagen"]
    g = echt.groupby("slot")
    uit = pd.DataFrame({"runs": g.size(), "gelukt": g["status"].apply(lambda s: (s == "ok").sum()),
                        "duur_gem_s": g["duur_s"].mean()}).reset_index()
    n_over = int((lg["status"] == "overgeslagen").sum())
    if n_over:
        uit = pd.concat([uit, pd.DataFrame([{"slot": "middag overgeslagen", "runs": n_over, "gelukt": n_over, "duur_gem_s": lg[lg["status"] == "overgeslagen"]["duur_s"].mean()}])],
                        ignore_index=True)
    return uit


def _md(df: pd.DataFrame, fmt: dict[str, str] | None = None) -> str:
    if df.empty:
        return "_geen gegevens_"
    fmt = fmt or {}
    kop = "| " + " | ".join(df.columns) + " |"
    lijn = "|" + "|".join("---" for _ in df.columns) + "|"
    rijen = []
    for _, r in df.iterrows():
        cellen = []
        for c in df.columns:
            v = r[c]
            if pd.isna(v) if not isinstance(v, str) else False:
                cellen.append("")
            elif c in fmt:
                cellen.append(fmt[c].format(v))
            elif isinstance(v, (float, np.floating)):
                cellen.append(f"{v:.2f}")
            else:
                cellen.append(str(v))
        rijen.append("| " + " | ".join(cellen) + " |")
    return "\n".join([kop, lijn, *rijen])


def oordeel(tabel: pd.DataFrame, blok: pd.DataFrame) -> list[str]:
    """Beslisregel uit PLAN.md per slot, op de eerstvolgende voorspelde dag (horizon 2)."""
    uit = []
    if tabel.empty:
        return ["Nog geen paren van hoofdrun en verversing met bekende uitkomsten."]
    for slot, g in tabel.groupby("slot"):
        e = g[g["horizon_dag"] == g["horizon_dag"].min()].iloc[0]
        b = blok[(blok["slot"] == slot) & (blok["horizon_dag"] == e["horizon_dag"])] if not blok.empty else pd.DataFrame()
        verschuift = float(b["verschoven_en_goedkoper"].iloc[0]) if len(b) else np.nan
        if e["n_dagen"] < MIN_PAREN_BESLUIT:
            uit.append(f"- {slot}: nog {int(MIN_PAREN_BESLUIT - e['n_dagen'])} dagen te gaan voor de beslisregel "
                       f"({int(e['n_dagen'])} van {MIN_PAREN_BESLUIT}); tussenstand MAE {e['verschil_pct']:+.1f}% op dag {int(e['horizon_dag'])}.")
            continue
        mae_ok = e["verschil_pct"] <= -3 and e["p"] < 0.10
        blok_ok = not np.isnan(verschuift) and verschuift >= 0.10
        besluit = "blijft" if (mae_ok or blok_ok) else "gaat eruit"
        uit.append(f"- {slot}: **{besluit}**. MAE {e['verschil_pct']:+.1f}% (p = {e['p']:.3f}); advies verschoven naar een "
                   f"achteraf goedkoper blok op {verschuift * 100:.0f}% van de dagen." if not np.isnan(verschuift) else
                   f"- {slot}: **{besluit}**. MAE {e['verschil_pct']:+.1f}% (p = {e['p']:.3f}).")
    return uit


def evalueer(cfg: Config) -> Path:
    runs = archive.lees_runs(cfg)
    prijzen = pd.read_parquet(cfg.processed_dir / "prijzen_nl_uur.parquet")
    prijzen["time_utc"] = pd.to_datetime(prijzen["time_utc"], utc=True)
    runs = archive.vul_doel(runs, prijzen) if not runs.empty else runs
    p = paren(runs) if not runs.empty else pd.DataFrame()
    tabel = tabel_per_slot(p) if not p.empty else pd.DataFrame()
    blok = blokverschuiving(p) if not p.empty else pd.DataFrame()
    betr = betrouwbaarheid_runs(cfg)
    n_hoofd = int((runs["run_type"] == "hoofd").sum() and runs[runs["run_type"] == "hoofd"]["run_utc"].nunique()) if not runs.empty else 0
    n_verv = int(runs[runs["run_type"] == "verversing"]["run_utc"].nunique()) if not runs.empty else 0
    n_inhaal = int(runs[runs["run_type"] == "inhaal"]["run_utc"].nunique()) if not runs.empty else 0

    L = ["# Evaluatie van de verversingsruns\n",
         (f"Gemaakt op {pd.Timestamp.now(tz=TZ).strftime('%Y-%m-%d %H:%M')}. Archief: {n_hoofd} hoofdruns, {n_verv} verversingen, "
         f"{n_inhaal} inhaalruns. Meetplan en beslisregel: PLAN.md, sectie \"Evaluatie van de verversingsruns\" (besluit 33).\n"),
         "## 1. Fout per verversingsslot en doeldag\n",
         ("Gepaard per doeluur met de hoofdrun van hetzelfde voorspelmoment; alleen uren waarvan de prijs inmiddels bekend is. "
         "`verschil` = MAE verversing min MAE hoofdrun (negatief = verversing beter). Diebold-Mariano eenzijdig (verversing beter), "
         "Newey-West-correctie, vanaf 10 dagen.\n"),
         _md(tabel.rename(columns={"horizon_dag": "dag"}), {"p": "{:.3f}", "verschil_pct": "{:+.1f}", "dekking_hoofd": "{:.3f}",
                                                             "dekking_verversing": "{:.3f}"}) if not tabel.empty else "_Nog geen paren._",
         "\n## 2. Verschuift het advies?\n",
         ("Per doeldag: verschoof het goedkoopste laadblok (3 uur, P50) door de verversing, en was het nieuwe blok achteraf echt "
         "goedkoper? `winst_gem` in EUR/MWh (positief = verversing koos beter).\n"),
         _md(blok.rename(columns={"horizon_dag": "dag"}), {"verschoven": "{:.0%}", "verschoven_en_goedkoper": "{:.0%}"}) if not blok.empty else "_Nog geen paren._",
         "\n## 3. Betrouwbaarheid van de runs\n",
         _md(betr, {"duur_gem_s": "{:.0f}"}),
         "\n## 4. Oordeel volgens de beslisregel\n",
         *oordeel(tabel, blok),
         ("\nNog niet gemeten: de verandering in de weersverwachting tussen de uitgiften (punt 5 van het meetplan). Dat komt "
         "zodra er genoeg verversingen zijn om een verband te kunnen zien.\n")]
    pad = cfg.root / "reports" / "verversingen.md"
    pad.parent.mkdir(parents=True, exist_ok=True)
    pad.write_text("\n".join(L), encoding="utf-8")
    log.info("rapport -> %s", pad)
    return pad
