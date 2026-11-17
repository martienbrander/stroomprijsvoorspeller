"""Tests voor de bewaking van de leverancierstabel (besluit 77): vaste controledata, leeftijd, melding, exitcode."""

from datetime import date
from pathlib import Path

import pytest

from stroomprijsvoorspeller import cli
from stroomprijsvoorspeller.pipeline import leveranciers
from tests.conftest import maak_config

ROOT = Path(__file__).resolve().parents[1]


def _schrijf(root, peildatum: str | None) -> None:
    (root / "data").mkdir(exist_ok=True)
    regel = f"peildatum_lijst: {peildatum}\n" if peildatum is not None else ""
    (root / "data" / "leveranciers.yaml").write_text(regel + "leveranciers: []\n", encoding="utf-8")


@pytest.mark.parametrize("vandaag, vorige, volgende", [
    (date(2026, 11, 18), date(2026, 10, 1), date(2027, 1, 1)),
    (date(2027, 1, 1), date(2027, 1, 1), date(2027, 4, 1)),      # de controledatum zelf telt als bereikt
    (date(2027, 3, 31), date(2027, 1, 1), date(2027, 4, 1)),
    (date(2027, 12, 31), date(2027, 10, 1), date(2028, 1, 1)),
])
def test_controledata_zijn_de_eerste_dag_van_elk_kwartaal(vandaag, vorige, volgende):
    assert leveranciers.vorige_controledatum(vandaag) == vorige
    assert leveranciers.volgende_controledatum(vandaag) == volgende


@pytest.mark.parametrize("peildatum, vandaag, verouderd", [
    ("2026-11-01", date(2026, 12, 31), False),   # nog voor de volgende controledatum
    ("2026-11-01", date(2027, 1, 1), True),      # controledatum bereikt, lijst niet nagelopen
    ("2027-01-01", date(2027, 1, 4), False),     # op de controledatum nagelopen
    ("2027-01-06", date(2027, 3, 31), False),    # kort na de controledatum nagelopen
    ("2026-12-28", date(2027, 1, 4), True),      # vlak voor 1 januari telt niet: de tarieven wijzigen op die dag
    ('"2026-11-01"', date(2026, 11, 18), False), # datum als tekst tussen aanhalingstekens, zoals in het echte bestand
])
def test_lijst_is_verouderd_als_de_peildatum_voor_de_laatste_controledatum_ligt(tmp_path, peildatum, vandaag, verouderd):
    cfg = maak_config(tmp_path)
    _schrijf(tmp_path, peildatum)
    assert leveranciers.bepaal_stand(cfg, vandaag).verouderd is verouderd


@pytest.mark.parametrize("peildatum", [None, "onbekend"])
def test_zonder_leesbare_peildatum_is_de_lijst_verouderd(tmp_path, peildatum):
    cfg = maak_config(tmp_path)
    _schrijf(tmp_path, peildatum)
    stand = leveranciers.bepaal_stand(cfg, date(2026, 11, 18))
    assert stand.peildatum is None and stand.verouderd
    assert "geen leesbare" in leveranciers.melding(stand, date(2026, 11, 18))


def test_zonder_bestand_is_de_lijst_verouderd(tmp_path):
    assert leveranciers.bepaal_stand(maak_config(tmp_path), date(2026, 11, 18)).verouderd


def test_melding_noemt_peildatum_leeftijd_en_controledatum(tmp_path):
    cfg = maak_config(tmp_path)
    _schrijf(tmp_path, "2026-11-01")
    goed = leveranciers.melding(leveranciers.bepaal_stand(cfg, date(2026, 11, 18)), date(2026, 11, 18))
    assert goed == "Leverancierstabel: peildatum 1 november 2026, 17 dagen oud. Volgende controle: 1 januari 2027."
    oud = leveranciers.melding(leveranciers.bepaal_stand(cfg, date(2027, 1, 4)), date(2027, 1, 4))
    assert "1 november 2026 (64 dagen oud)" in oud and "1 januari 2027" in oud and "energiebelasting" in oud
    april = leveranciers.melding(leveranciers.bepaal_stand(cfg, date(2027, 4, 5)), date(2027, 4, 5))
    assert "1 april 2027" in april and "energiebelasting" not in april


def test_commando_geeft_alleen_met_strikt_exitcode_3(tmp_path, capsys):
    _schrijf(tmp_path, "2026-11-01")
    config = tmp_path / "config.yaml"
    config.write_text((ROOT / "config.yaml").read_text(encoding="utf-8"), encoding="utf-8")   # root = tmp_path
    basis = ["--config", str(config), "leveranciers-status"]
    assert cli.main(basis + ["--datum", "2026-11-18", "--strikt"]) == 0
    assert "17 dagen oud" in capsys.readouterr().out
    assert cli.main(basis + ["--datum", "2027-01-04"]) == 0
    assert cli.main(basis + ["--datum", "2027-01-04", "--strikt"]) == 3
    assert "toe aan controle" in capsys.readouterr().out
