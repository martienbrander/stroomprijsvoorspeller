"""Dagsoorten voor de evaluatie en de site: werkdag, schoolvakantie, brugdag, weekend, feestdag (besluit 53).

Het model kent alleen feestdag en weekend (sources/calendar.py). Deze module voegt daar voor de evaluatie twee soorten
aan toe die geen feature zijn: schoolvakantie (werkdag in een schoolvakantie van minstens één regio, uit
data/schoolvakanties.yaml) en brugdag (werkdag ingeklemd tussen een feestdag en een weekend). Zo wordt zichtbaar of
die dagen systematisch slechter voorspeld worden, voordat ze eventueel een feature worden.
"""

from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yaml

from stroomprijsvoorspeller.sources.calendar import nl_feestdagen
from stroomprijsvoorspeller.timeutil import local_date

DAGSOORTEN = ("werkdag", "schoolvakantie", "brugdag", "weekend", "feestdag")
VAKANTIE_BESTAND = "schoolvakanties.yaml"
REGIOS = ("noord", "midden", "zuid")


def laad_schoolvakanties(pad: Path) -> list[dict]:
    """Lijst van {naam, schooljaar, advies, regio, start, einde}; leeg als het bestand ontbreekt."""
    if not pad.exists():
        return []
    data = yaml.safe_load(pad.read_text(encoding="utf-8")) or {}
    uit = []
    for v in data.get("vakanties", []):
        for regio in REGIOS:
            if regio in v:
                start, einde = (pd.Timestamp(x).date() for x in v[regio])
                uit.append({"naam": v["naam"], "schooljaar": str(v["schooljaar"]), "advies": bool(v.get("advies", False)),
                            "regio": regio, "start": start, "einde": einde})
    return uit


def vakantiedagen(vakanties: list[dict]) -> set[date]:
    """Alle dagen die in minstens één regio schoolvakantie zijn."""
    dagen: set[date] = set()
    for v in vakanties:
        d = v["start"]
        while d <= v["einde"]:
            dagen.add(d)
            d += timedelta(days=1)
    return dagen


class Dagsoorten:
    """Bepaalt per datum de dagsoort en de naam van de feestdag."""

    def __init__(self, root: Path, jaren: range | None = None):
        jaren = jaren or range(2022, 2031)
        self.feest = nl_feestdagen(jaren)
        self.vakanties = laad_schoolvakanties(root / "data" / VAKANTIE_BESTAND)
        self._vakantie = vakantiedagen(self.vakanties)

    def feestdag(self, d: date) -> str | None:
        return self.feest.get(d)

    def is_vrij(self, d: date) -> bool:
        return d.weekday() >= 5 or d in self.feest

    def soort(self, d: date) -> str:
        if d in self.feest:
            return "feestdag"
        if d.weekday() >= 5:
            return "weekend"
        vorige, volgende = d - timedelta(days=1), d + timedelta(days=1)
        if (vorige in self.feest and volgende.weekday() >= 5) or (vorige.weekday() >= 5 and volgende in self.feest):
            return "brugdag"
        if d in self._vakantie:
            return "schoolvakantie"
        return "werkdag"

    def serie(self, datums) -> pd.Series:
        return pd.Series([self.soort(pd.Timestamp(d).date()) for d in datums], index=getattr(datums, "index", None))


def _effect(prijs_dag: pd.Series, soorten: pd.Series, doel: str, venster_dagen: int) -> dict:
    """Gemiddeld prijsverschil (in procent) van dagen van soort `doel` t.o.v. de werkdagen in de `venster_dagen`
    ervoor en erna. Per dag één vergelijking, zodat seizoen en prijsniveau zo goed mogelijk gelijk blijven."""
    prijs_dag = prijs_dag.dropna()
    werk = prijs_dag[soorten.reindex(prijs_dag.index) == "werkdag"]
    verschillen = []
    for d, p in prijs_dag[soorten.reindex(prijs_dag.index) == doel].items():
        ref = werk[(werk.index >= d - timedelta(days=venster_dagen)) & (werk.index <= d + timedelta(days=venster_dagen))]
        if len(ref) >= 5 and abs(ref.mean()) > 1e-9:
            verschillen.append((p - ref.mean()) / ref.mean() * 100)
    if not verschillen:
        return {"pct_tov_werkdag": None, "aantal_dagen": 0}
    s = pd.Series(verschillen)
    return {"pct_tov_werkdag": round(float(s.mean()), 1), "mediaan_pct": round(float(s.median()), 1),
            "aantal_dagen": len(s), "aandeel_goedkoper": round(float((s < 0).mean()), 2)}


def dag_effecten(prijzen: pd.DataFrame, root: Path, prijs_kolom: str = "prijs_eur_mwh") -> dict:
    """Prijseffect van feestdagen, brugdagen en schoolvakantiedagen t.o.v. gewone werkdagen in de buurt, uit de
    daggemiddelde beursprijs. Geeft ook de periode waarover gerekend is."""
    p = prijzen.dropna(subset=[prijs_kolom])
    dag = pd.Index(local_date(pd.DatetimeIndex(p["time_utc"])))
    prijs_dag = p[prijs_kolom].groupby(dag).mean()
    prijs_dag.index = pd.Index([pd.Timestamp(d).date() for d in prijs_dag.index])
    ds = Dagsoorten(root)
    soorten = pd.Series([ds.soort(d) for d in prijs_dag.index], index=prijs_dag.index)
    return {
        "vanaf": str(prijs_dag.index.min()), "tot": str(prijs_dag.index.max()),
        "feestdag": _effect(prijs_dag, soorten, "feestdag", 10),
        "brugdag": _effect(prijs_dag, soorten, "brugdag", 10),
        "schoolvakantie": _effect(prijs_dag, soorten, "schoolvakantie", 21),
    }
