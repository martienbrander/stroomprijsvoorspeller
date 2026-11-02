from datetime import date, timedelta

import numpy as np
import pandas as pd

from stroomprijsvoorspeller.processing import dagsoort
from stroomprijsvoorspeller.timeutil import local_hour_range

VAKANTIES = """
peildatum: 2026-11-02
vakanties:
  - {schooljaar: 2025-2026, naam: meivakantie, advies: false, noord: [2026-04-25, 2026-05-03], midden: [2026-04-25, 2026-05-03], zuid: [2026-04-25, 2026-05-03]}
  - {schooljaar: 2025-2026, naam: zomervakantie, advies: false, noord: [2026-07-04, 2026-08-16], midden: [2026-07-18, 2026-08-30], zuid: [2026-07-11, 2026-08-23]}
"""


def _root(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "schoolvakanties.yaml").write_text(VAKANTIES, encoding="utf-8")
    return tmp_path


def test_dagsoorten(tmp_path):
    ds = dagsoort.Dagsoorten(_root(tmp_path))
    assert ds.soort(date(2026, 5, 14)) == "feestdag"          # Hemelvaartsdag
    assert ds.feestdag(date(2026, 5, 14)) == "Hemelvaartsdag"
    assert ds.soort(date(2026, 5, 15)) == "brugdag"           # vrijdag na Hemelvaart
    assert ds.soort(date(2026, 5, 16)) == "weekend"
    assert ds.soort(date(2026, 4, 28)) == "schoolvakantie"    # dinsdag in de meivakantie
    assert ds.soort(date(2026, 4, 27)) == "feestdag"          # Koningsdag gaat voor
    assert ds.soort(date(2026, 7, 7)) == "schoolvakantie"     # alleen noord is al vrij: telt mee
    assert ds.soort(date(2026, 5, 12)) == "werkdag"
    assert ds.feestdag(date(2026, 5, 12)) is None
    # maandag voor een feestdag op dinsdag is ook een brugdag; maandag 2 januari 2023 niet (1 januari was zondag)
    assert ds.soort(date(2023, 1, 2)) == "werkdag"


def test_zonder_bestand_alleen_feestdag_en_weekend(tmp_path):
    ds = dagsoort.Dagsoorten(tmp_path)
    assert ds.vakanties == []
    assert ds.soort(date(2026, 4, 28)) == "werkdag"


def test_dag_effecten(tmp_path):
    root = _root(tmp_path)
    # drie maanden uurprijzen: werkdag 100, feestdag en brugdag 80, schoolvakantie 90, weekend 70
    ds = dagsoort.Dagsoorten(root)
    delen = []
    d = date(2026, 4, 1)
    while d <= date(2026, 6, 30):
        niveau = {"werkdag": 100.0, "feestdag": 80.0, "brugdag": 80.0, "schoolvakantie": 90.0, "weekend": 70.0}[ds.soort(d)]
        uren = local_hour_range(d)
        delen.append(pd.DataFrame({"time_utc": uren, "prijs_eur_mwh": np.full(len(uren), niveau)}))
        d += timedelta(days=1)
    e = dagsoort.dag_effecten(pd.concat(delen, ignore_index=True), root)
    assert e["vanaf"] == "2026-04-01" and e["tot"] == "2026-06-30"
    assert e["feestdag"]["aantal_dagen"] >= 5 and abs(e["feestdag"]["pct_tov_werkdag"] + 20) < 0.01
    assert abs(e["brugdag"]["pct_tov_werkdag"] + 20) < 0.01
    assert abs(e["schoolvakantie"]["pct_tov_werkdag"] + 10) < 0.01
    assert e["feestdag"]["aandeel_goedkoper"] == 1.0
