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
from stroomprijsvoorspeller.evaluation.blocks import LAADBLOK_UREN, goedkoopste_blok
from stroomprijsvoorspeller.evaluation.markdown import md_tabel
from stroomprijsvoorspeller.evaluation.metrics import dekking, pinball
from stroomprijsvoorspeller.pipeline import archive
from stroomprijsvoorspeller.processing import dataset
from stroomprijsvoorspeller.processing.features import DOEL
from stroomprijsvoorspeller.timeutil import MIN_UREN_PER_DAG, TZ, local_date

log = logging.getLogger(__name__)

SLOTS = (19, 1, 7)          # verversingsmomenten (lokaal uur) uit besluit 33
MIN_PAREN_BESLUIT = 40      # dagen met volledige paren voordat de beslisregel geldt
MIN_DAGEN_TOETS = 10        # Diebold-Mariano pas vanaf zoveel dagen
# de beslisregel uit PLAN.md: een slot blijft als de fout genoeg daalt of het advies vaak genoeg beter wordt
MAE_WINST_PCT = 3           # MAE minstens zoveel procent lager ...
MAE_P_GRENS = 0.10          # ... met een p-waarde onder deze grens
BLOK_WINST_AANDEEL = 0.10   # of het advies verschuift op minstens dit deel van de dagen naar een goedkoper blok


def slot_van(run_utc: pd.Timestamp) -> int:
    """Dichtstbijzijnde verversingsslot (lokaal uur) van een runtijd."""
    lokaal = pd.Timestamp(run_utc).tz_convert(TZ)
    uur = lokaal.hour + lokaal.minute / 60
    return min(SLOTS, key=lambda s: min(abs(uur - s), 24 - abs(uur - s)))


def _slotnaam(slot: int) -> str:
    return f"{slot:02d}:00"


def paren(runs: pd.DataFrame) -> pd.DataFrame:
    """Per doeluur: fout van de hoofdrun naast die van elke verversing van hetzelfde voorspelmoment.

    Kolommen van de hoofdrun eindigen op `_h`, die van de verversing op `_v`.
    """
    voorspeld = runs[~runs["bekend"].astype(bool)].dropna(subset=[DOEL])
    hoofd = (voorspeld[voorspeld["run_type"] == "hoofd"].sort_values("run_utc")
             .drop_duplicates(["origin", "time_utc"], keep="last"))
    verv = voorspeld[voorspeld["run_type"] == "verversing"].copy()
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


def _pinball_interval(doel: pd.Series, p10: pd.Series, p90: pd.Series) -> float:
    """Gemiddelde van het pinball-verlies op de onder- en de bovengrens."""
    return (pinball(doel, p10, 0.1) + pinball(doel, p90, 0.9)) / 2


def tabel_per_slot(p: pd.DataFrame) -> pd.DataFrame:
    """Per verversingsslot en horizon: fout, pinball en dekking van hoofdrun en verversing, met Diebold-Mariano."""
    rijen = []
    for (slot, horizon), g in p.groupby(["slot", "horizon_dag"]):
        per_dag_h = g.groupby("origin")["fout_h"].mean()
        per_dag_v = g.groupby("origin")["fout_v"].mean()
        dm, p_waarde = np.nan, np.nan
        if len(per_dag_h) >= MIN_DAGEN_TOETS and not np.allclose(per_dag_v, per_dag_h):
            dm, p_waarde = stats.diebold_mariano(per_dag_v.to_numpy(), per_dag_h.to_numpy())
        mae_h, mae_v = g["fout_h"].mean(), g["fout_v"].mean()
        rijen.append({
            "slot": _slotnaam(slot), "horizon_dag": int(horizon), "n_dagen": int(g["origin"].nunique()), "n_uren": len(g),
            "mae_hoofd": mae_h, "mae_verversing": mae_v,
            "verschil": mae_v - mae_h,
            "verschil_pct": (mae_v / mae_h - 1) * 100 if mae_h else np.nan,
            "pinball_hoofd": _pinball_interval(g[DOEL], g["p10_kal_h"], g["p90_kal_h"]),
            "pinball_verversing": _pinball_interval(g[DOEL], g["p10_kal_v"], g["p90_kal_v"]),
            "dekking_hoofd": dekking(g[DOEL], g["p10_kal_h"], g["p90_kal_h"]),
            "dekking_verversing": dekking(g[DOEL], g["p10_kal_v"], g["p90_kal_v"]),
            "dm": dm, "p": p_waarde,
        })
    return pd.DataFrame(rijen)


def _positie_van_uur(uren: np.ndarray, uur: float) -> int | None:
    """Plaats van het lokale uur `uur` in de reeks uren van een dag, of None als dat uur er niet in zit."""
    treffers = np.flatnonzero(uren == int(uur))
    return int(treffers[0]) if len(treffers) else None


def blokverschuiving(p: pd.DataFrame) -> pd.DataFrame:
    """Per (slot, doeldag): hoe vaak verschoof het laadblok door de verversing, en was het nieuwe blok achteraf goedkoper?"""
    rijen = []
    for (slot, horizon, origin, _doeldag), g in p.groupby(["slot", "horizon_dag", "origin", "doeldag"]):
        g = g.sort_values("time_utc")
        if len(g) < MIN_UREN_PER_DAG:
            continue
        start_h, start_v = g["laadblok_start_h"].iloc[0], g["laadblok_start_v"].iloc[0]
        if pd.isna(start_h) or pd.isna(start_v):
            continue
        uren = pd.DatetimeIndex(g["time_utc"]).tz_convert(TZ).hour.to_numpy()
        i_h, i_v = _positie_van_uur(uren, start_h), _positie_van_uur(uren, start_v)
        if i_h is None or i_v is None:
            continue
        echt = g[DOEL].to_numpy()
        kosten_h = float(np.mean(echt[i_h:i_h + LAADBLOK_UREN]))
        kosten_v = float(np.mean(echt[i_v:i_v + LAADBLOK_UREN]))
        _, kosten_beste = goedkoopste_blok(echt, LAADBLOK_UREN)
        verschoven = start_h != start_v
        winst = kosten_h - kosten_v
        rijen.append({"slot": _slotnaam(slot), "horizon_dag": int(horizon), "origin": origin, "verschoven": verschoven,
                      "verschoven_en_goedkoper": verschoven and winst > 0, "winst": winst,
                      "meerkosten_hoofd": kosten_h - kosten_beste, "meerkosten_verversing": kosten_v - kosten_beste})
    if not rijen:
        return pd.DataFrame()
    g = pd.DataFrame(rijen).groupby(["slot", "horizon_dag"])
    return pd.DataFrame({
        "n_dagen": g.size(),
        "verschoven": g["verschoven"].mean(),
        "verschoven_en_goedkoper": g["verschoven_en_goedkoper"].mean(),
        "winst_gem": g["winst"].mean(),
        "meerkosten_hoofd": g["meerkosten_hoofd"].mean(),
        "meerkosten_verversing": g["meerkosten_verversing"].mean(),
    }).reset_index()


def betrouwbaarheid_runs(cfg: Config) -> pd.DataFrame:
    """Uit runs.csv: per slot het aantal runs, hoeveel er gelukt zijn en de gemiddelde doorlooptijd."""
    pad = archive.runs_dir(cfg) / archive.LOGBESTAND
    if not pad.exists():
        return pd.DataFrame()
    logboek = pd.read_csv(pad)
    logboek["run_utc"] = pd.to_datetime(logboek["run_utc"], utc=True)
    is_verversing = logboek["run_type"] == "verversing"
    logboek["slot"] = np.where(is_verversing, logboek["run_utc"].map(lambda t: _slotnaam(slot_van(t))), logboek["run_type"])
    # middagpogingen zonder nieuwe prijzen (status overgeslagen) zijn geen mislukte runs
    overgeslagen = logboek["status"] == "overgeslagen"
    echt = logboek[~overgeslagen]
    g = echt.groupby("slot")
    uit = pd.DataFrame({"runs": g.size(), "gelukt": (echt["status"] == "ok").groupby(echt["slot"]).sum(),
                        "duur_gem_s": g["duur_s"].mean()}).reset_index()
    n_over = int(overgeslagen.sum())
    if n_over:
        rij = {"slot": "middag overgeslagen", "runs": n_over, "gelukt": n_over,
               "duur_gem_s": logboek.loc[overgeslagen, "duur_s"].mean()}
        uit = pd.concat([uit, pd.DataFrame([rij])], ignore_index=True)
    return uit


def oordeel(tabel: pd.DataFrame, blok: pd.DataFrame) -> list[str]:
    """Beslisregel uit PLAN.md per slot, op de eerstvolgende voorspelde dag (horizon 2)."""
    if tabel.empty:
        return ["Nog geen paren van hoofdrun en verversing met bekende uitkomsten."]
    uit = []
    for slot, g in tabel.groupby("slot"):
        eerste = g[g["horizon_dag"] == g["horizon_dag"].min()].iloc[0]
        dag, n_dagen = int(eerste["horizon_dag"]), int(eerste["n_dagen"])
        if n_dagen < MIN_PAREN_BESLUIT:
            uit.append(f"- {slot}: nog {MIN_PAREN_BESLUIT - n_dagen} dagen te gaan voor de beslisregel "
                       f"({n_dagen} van {MIN_PAREN_BESLUIT}); tussenstand MAE {eerste['verschil_pct']:+.1f}% op dag {dag}.")
            continue
        blok_slot = blok[(blok["slot"] == slot) & (blok["horizon_dag"] == dag)] if not blok.empty else pd.DataFrame()
        aandeel_beter_blok = float(blok_slot["verschoven_en_goedkoper"].iloc[0]) if len(blok_slot) else np.nan
        mae_ok = eerste["verschil_pct"] <= -MAE_WINST_PCT and eerste["p"] < MAE_P_GRENS
        blok_ok = not np.isnan(aandeel_beter_blok) and aandeel_beter_blok >= BLOK_WINST_AANDEEL
        besluit = "blijft" if (mae_ok or blok_ok) else "gaat eruit"
        regel = f"- {slot}: **{besluit}**. MAE {eerste['verschil_pct']:+.1f}% (p = {eerste['p']:.3f})"
        if np.isnan(aandeel_beter_blok):
            uit.append(regel + ".")
        else:
            uit.append(f"{regel}; advies verschoven naar een achteraf goedkoper blok op "
                       f"{aandeel_beter_blok * 100:.0f}% van de dagen.")
    return uit


def evalueer(cfg: Config) -> Path:
    """Schrijft reports/verversingen.md uit het runarchief en geeft het pad terug."""
    runs = archive.lees_runs(cfg)
    p = pd.DataFrame() if runs.empty else paren(archive.vul_doel(runs, dataset.lees_uurprijzen(cfg)))
    tabel = pd.DataFrame() if p.empty else tabel_per_slot(p)
    blok = pd.DataFrame() if p.empty else blokverschuiving(p)
    aantal = {soort: int(runs.loc[runs["run_type"] == soort, "run_utc"].nunique()) for soort in archive.RUN_TYPES}
    nog_geen_paren = "_Nog geen paren._"

    regels = [
        "# Evaluatie van de verversingsruns\n",
        (f"Gemaakt op {pd.Timestamp.now(tz=TZ).strftime('%Y-%m-%d %H:%M')}. Archief: {aantal['hoofd']} hoofdruns, "
         f"{aantal['verversing']} verversingen, {aantal['inhaal']} inhaalruns. Meetplan en beslisregel: PLAN.md, sectie "
         "\"Evaluatie van de verversingsruns\" (besluit 33).\n"),
        "## 1. Fout per verversingsslot en doeldag\n",
        ("Gepaard per doeluur met de hoofdrun van hetzelfde voorspelmoment; alleen uren waarvan de prijs inmiddels "
         "bekend is. `verschil` = MAE verversing min MAE hoofdrun (negatief = verversing beter). Diebold-Mariano "
         "eenzijdig (verversing beter), Newey-West-correctie, vanaf 10 dagen.\n"),
        md_tabel(tabel.rename(columns={"horizon_dag": "dag"}),
                 {"p": "{:.3f}", "verschil_pct": "{:+.1f}", "dekking_hoofd": "{:.3f}", "dekking_verversing": "{:.3f}"},
                 leeg=nog_geen_paren),
        "\n## 2. Verschuift het advies?\n",
        ("Per doeldag: verschoof het goedkoopste laadblok (3 uur, P50) door de verversing, en was het nieuwe blok "
         "achteraf echt goedkoper? `winst_gem` in EUR/MWh (positief = verversing koos beter).\n"),
        md_tabel(blok.rename(columns={"horizon_dag": "dag"}),
                 {"verschoven": "{:.0%}", "verschoven_en_goedkoper": "{:.0%}"}, leeg=nog_geen_paren),
        "\n## 3. Betrouwbaarheid van de runs\n",
        md_tabel(betrouwbaarheid_runs(cfg), {"duur_gem_s": "{:.0f}"}, leeg="_geen gegevens_"),
        "\n## 4. Oordeel volgens de beslisregel\n",
        *oordeel(tabel, blok),
        ("\nNog niet gemeten: de verandering in de weersverwachting tussen de uitgiften (punt 5 van het meetplan). "
         "Dat komt zodra er genoeg verversingen zijn om een verband te kunnen zien.\n"),
    ]
    pad = cfg.root / "reports" / "verversingen.md"
    pad.parent.mkdir(parents=True, exist_ok=True)
    pad.write_text("\n".join(regels), encoding="utf-8")
    log.info("rapport -> %s", pad)
    return pad
