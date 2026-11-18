"""Tests voor de operationele pipeline (fase 4): voorspelmoment, bekende uren, blokken, runarchief, JSON, verversingen."""

import json
from datetime import date, timedelta

import numpy as np
import pandas as pd
import pytest

from stroomprijsvoorspeller.evaluation import refresh
from stroomprijsvoorspeller.pipeline import archive, daily, site_export
from stroomprijsvoorspeller.processing.features import DOEL, PRIJS
from stroomprijsvoorspeller.timeutil import local_hour_range, publication_cutoff
from tests.conftest import maak_config


def _prijzen(tot_en_met: date, vanaf: date = date(2026, 10, 1)) -> pd.DataFrame:
    uren = pd.concat([pd.Series(local_hour_range(vanaf + timedelta(days=i))) for i in range((tot_en_met - vanaf).days + 1)])
    idx = pd.DatetimeIndex(uren)
    prijs = 100.0 + 10 * np.sin(np.arange(len(idx)) * 2 * np.pi / 24)
    return pd.DataFrame({"time_utc": idx, PRIJS: prijs})


def test_bepaal_origin_volgt_laatst_bekende_dag():
    vandaag = date(2026, 11, 3)
    assert daily.bepaal_origin(_prijzen(vandaag + timedelta(days=1)), vandaag) == vandaag       # morgen bekend
    assert daily.bepaal_origin(_prijzen(vandaag), vandaag) == vandaag - timedelta(days=1)     # morgen nog niet
    # een dag met maar 3 uur telt niet als bekend
    p = _prijzen(vandaag + timedelta(days=1))
    p = p[p["time_utc"] < local_hour_range(vandaag + timedelta(days=1))[3]]
    assert daily.bepaal_origin(p, vandaag) == vandaag - timedelta(days=1)


def test_bekende_uren_zijn_de_echte_prijs_en_veranderen_niet():
    vandaag = date(2026, 11, 3)
    p = _prijzen(vandaag + timedelta(days=1))
    b1 = daily.bekende_uren(p, vandaag, vandaag)
    b2 = daily.bekende_uren(p, vandaag, vandaag)      # een verversing later op de dag: zelfde uitkomst
    assert len(b1) == 48 and b1["bekend"].all()
    assert (b1["p10"] == b1["p50"]).all() and (b1["p90"] == b1["p50"]).all() and (b1[DOEL] == b1["p50"]).all()
    pd.testing.assert_frame_equal(b1, b2)
    assert set(b1["horizon_dag"]) == {0, 1}
    # origin gisteren (morgen onbekend): alleen vandaag
    assert set(daily.bekende_uren(_prijzen(vandaag), vandaag - timedelta(days=1), vandaag)["horizon_dag"]) == {1}


def test_voeg_blokken_toe_kiest_goedkoopste_blok_per_dag():
    dag = date(2026, 11, 5)
    uren = local_hour_range(dag)
    p50 = np.full(24, 100.0); p50[3:6] = 10.0; p50[14:16] = 5.0
    df = pd.DataFrame({"time_utc": uren, "p50": p50})
    uit = daily.voeg_blokken_toe(df)
    assert (uit["laadblok_start"] == 3).all()      # 3-uursblok: 3-6
    assert (uit["wasblok_start"] == 14).all()      # 2-uursblok: 14-16 is goedkoper


def _run_rijen(origin: date, run_type: str, run_utc, p50_offset: float, blok: int) -> pd.DataFrame:
    uren = local_hour_range(origin + timedelta(days=2))
    p50 = 100.0 + p50_offset + np.zeros(len(uren))
    return pd.DataFrame({"run_utc": pd.Timestamp(run_utc), "run_type": run_type, "origin": pd.Timestamp(origin),
                         "model_getraind_utc": pd.NaT, "weer_uitgegeven_utc": pd.NaT, "time_utc": uren, "horizon_dag": 2,
                         "horizon_uren_run": 30.0, "p10": p50 - 10, "p50": p50, "p90": p50 + 10, "p10_kal": p50 - 12,
                         "p90_kal": p50 + 12, "conformal_q": 2.0, "alpha_aci": 0.2, "bekend": False, "profiel_p50": 105.0,
                         "laadblok_start": float(blok), "wasblok_start": float(blok), DOEL: np.nan})


def test_archief_schrijven_lezen_en_keuze_per_origin(tmp_path):
    cfg = maak_config(tmp_path)
    D = date(2026, 11, 1)
    archive.schrijf_run(cfg, _run_rijen(D, "inhaal", "2026-11-01T12:15:00Z", 5, 3), pd.Timestamp("2026-11-01T12:15:00Z"), "inhaal")
    archive.schrijf_run(cfg, _run_rijen(D, "hoofd", "2026-11-01T12:20:00Z", 0, 3), pd.Timestamp("2026-11-01T12:20:00Z"), "hoofd")
    archive.schrijf_run(cfg, _run_rijen(D, "verversing", "2026-11-01T18:00:00Z", -3, 4), pd.Timestamp("2026-11-01T18:00:00Z"), "verversing")
    archive.schrijf_run(cfg, _run_rijen(D + timedelta(days=1), "inhaal", "2026-11-02T12:15:00Z", 2, 5), pd.Timestamp("2026-11-02T12:15:00Z"), "inhaal")
    runs = archive.lees_runs(cfg)
    assert len(runs) == 4 * 24 and set(runs["run_type"]) == {"inhaal", "hoofd", "verversing"}
    keuze = archive.laatste_run_per_origin(runs)
    per_origin = keuze.groupby("origin")["run_type"].first()
    assert per_origin[pd.Timestamp(D)] == "hoofd" and per_origin[pd.Timestamp(D + timedelta(days=1))] == "inhaal"
    assert (keuze[keuze["origin"] == pd.Timestamp(D)]["p50"] == 100.0).all()   # de hoofdrun, niet de verversing
    # gemiste dagen: 3 en 4 november ontbreken vóór 5 november; zonder backtest begint het bij de eerste run
    assert archive.ontbrekende_origins(cfg, "lightgbm", date(2026, 11, 5)) == [date(2026, 11, 3), date(2026, 11, 4)]
    # doel invullen met inmiddels bekende prijzen
    gevuld = archive.vul_doel(runs, _prijzen(date(2026, 11, 10)))
    assert gevuld[DOEL].notna().all()
    assert set(archive.lees_runs(cfg, ("hoofd",))["run_type"]) == {"hoofd"}
    archive.log_run(cfg, pd.Timestamp("2026-11-01T12:20:00Z"), "hoofd", D, 12.3, "ok")
    assert (archive.runs_dir(cfg) / archive.LOGBESTAND).exists()


def test_historie_combineert_runs_en_vult_doel(tmp_path):
    cfg = maak_config(tmp_path)
    for i in range(3):
        D = date(2026, 11, 1) + timedelta(days=i)
        archive.schrijf_run(cfg, _run_rijen(D, "hoofd", f"2026-11-0{i+1}T12:20:00Z", 0, 3), pd.Timestamp(f"2026-11-0{i+1}T12:20:00Z"), "hoofd")
    h = archive.historie(cfg, "lightgbm", _prijzen(date(2026, 11, 10)))
    assert set(h["methode"]) == {"lightgbm", "profiel_4w"}
    assert h[DOEL].notna().all()
    assert (h[h["methode"] == "profiel_4w"]["p50"] == 105.0).all()
    assert archive.historie(cfg, "lightgbm", _prijzen(date(2026, 11, 10)), tot=date(2026, 11, 2))["origin"].max() == pd.Timestamp("2026-11-01")


def test_verversingen_gepaard_en_beoordeeld(tmp_path):
    cfg = maak_config(tmp_path)
    rng = np.random.default_rng(3)
    prijzen = _prijzen(date(2026, 12, 31))
    serie = prijzen.set_index("time_utc")[PRIJS]
    for i in range(15):
        D = date(2026, 11, 1) + timedelta(days=i)
        hoofd = _run_rijen(D, "hoofd", publication_cutoff(D) + pd.Timedelta(minutes=15), 0, 3)
        echt = serie.reindex(pd.DatetimeIndex(hoofd["time_utc"])).to_numpy()
        hoofd["p50"] = echt + rng.normal(0, 8, len(echt))          # hoofdrun: fout ~8
        verv = hoofd.copy()
        verv["run_type"] = "verversing"
        verv["run_utc"] = publication_cutoff(D) + pd.Timedelta(hours=6)   # 19:00 lokaal
        verv["p50"] = echt + rng.normal(0, 3, len(echt))           # verversing: fout ~3
        verv["laadblok_start"] = 4.0
        archive.schrijf_run(cfg, hoofd, hoofd["run_utc"].iloc[0], "hoofd")
        archive.schrijf_run(cfg, verv, verv["run_utc"].iloc[0], "verversing")
    assert refresh.slot_van(pd.Timestamp("2026-11-01T18:05:00Z")) == 19
    assert refresh.slot_van(pd.Timestamp("2026-11-02T00:10:00Z")) == 1
    assert refresh.slot_van(pd.Timestamp("2026-11-02T06:20:00Z")) == 7
    runs = archive.vul_doel(archive.lees_runs(cfg), prijzen)
    p = refresh.paren(runs)
    assert len(p) == 15 * 24 and not p.empty
    t = refresh.tabel_per_slot(p)
    r = t.iloc[0]
    assert r["slot"] == "19:00" and r["n_dagen"] == 15
    assert r["mae_verversing"] < r["mae_hoofd"] and r["p"] < 0.05
    b = refresh.blokverschuiving(p)
    assert b["verschoven"].iloc[0] == 1.0
    oordeel = refresh.oordeel(t, b)
    assert "nog" in oordeel[0] and "25 dagen te gaan" in oordeel[0]
    cfg.processed_dir.mkdir(parents=True, exist_ok=True)
    prijzen.to_parquet(cfg.processed_dir / "prijzen_nl_uur.parquet", index=False)
    pad = refresh.evalueer(cfg)
    assert pad.exists() and "19:00" in pad.read_text(encoding="utf-8")


def test_forecast_json_contract(tmp_path):
    cfg = maak_config(tmp_path)
    vandaag = date(2026, 11, 3)
    prijzen = _prijzen(vandaag + timedelta(days=1))
    bekend = daily.bekende_uren(prijzen, vandaag, vandaag)
    delen = [bekend]
    for k in (2, 3):
        uren = local_hour_range(vandaag + timedelta(days=k))
        p50 = np.full(len(uren), 90.0)
        delen.append(pd.DataFrame({"origin": pd.Timestamp(vandaag), "time_utc": uren, "horizon_dag": k, "horizon_uren": 40.0,
                                   "p10": p50 - 10, "p50": p50, "p90": p50 + 10, "p10_kal": p50 - 15, "p90_kal": p50 + 15,
                                   "conformal_q": 5.0, "alpha_aci": 0.2, "profiel_p50": 95.0, DOEL: np.nan, "bekend": False}))
    alles = pd.concat(delen, ignore_index=True)
    alles["weer_uitgegeven_utc"] = pd.Timestamp("2026-11-03T06:00:00Z")
    nu = pd.Timestamp("2026-11-03T12:20:00Z")
    f = site_export.maak_forecast_json(cfg, alles, prijzen, vandaag, nu, "hoofd", {"origin": vandaag})
    assert f["gegenereerd_utc"] == "2026-11-03T12:20:00Z" and f["run_type"] == "hoofd" and f["eenheid"] == "EUR/MWh"
    assert len(f["uren"]) == 4 * 24 and f["uren"][0]["tijd"].startswith("2026-11-03T00:00:00+01:00")
    assert f["uren"][0]["bekend"] is True and f["uren"][0]["p10"] == f["uren"][0]["p90"]
    assert f["uren"][-1]["bekend"] is False and f["uren"][-1]["p10"] == 75.0 and f["uren"][-1]["p90"] == 105.0
    assert [d["betrouwbaarheid"] for d in f["dagen"]][:2] == ["bekend", "bekend"]
    assert f["dagen"][2]["horizon_dag"] == 2 and f["dagen"][2]["betrouwbaarheid"] in ("hoog", "redelijk", "laag")
    assert f["prijzen_bekend_tot"] == "2026-11-04"
    assert f["scores"]["periode_dagen"] == 30     # zonder historie geen mae-velden, de site vangt dat op
    assert f["kwartieren"] == []
    (cfg.root / "data").mkdir(exist_ok=True)
    (cfg.root / "data" / "leveranciers.yaml").write_text(
        "peildatum_lijst: 2026-11-01\nleveranciers:\n"
        "  - {naam: Zeta, dynamisch_aanbod: true, inkoopvergoeding_ct_kwh_excl_btw: 1.5, status: bevestigd_tariefpagina}\n"
        "  - {naam: Alfa, dynamisch_aanbod: true, status: niet_gepubliceerd}\n"
        "  - {naam: Vast, dynamisch_aanbod: false}\n", encoding="utf-8")
    pad = site_export.schrijf_site(cfg, alles, prijzen, vandaag, nu, "hoofd", {"origin": vandaag})
    assert pad.exists() and (cfg.root / "site" / "api" / "v1" / "voorspelling.json").exists()
    lev = site_export.maak_leveranciers_json(cfg)
    assert [x["naam"] for x in lev["leveranciers"]] == ["Alfa", "Zeta"]


def test_model_is_oud(tmp_path):
    cfg = maak_config(tmp_path)
    assert daily.model_is_oud(cfg, None, date(2026, 11, 3))
    assert daily.model_is_oud(cfg, {"methode": "anders", "origin": date(2026, 11, 3)}, date(2026, 11, 3))
    assert not daily.model_is_oud(cfg, {"methode": "lightgbm", "origin": date(2026, 11, 1)}, date(2026, 11, 3))
    assert daily.model_is_oud(cfg, {"methode": "lightgbm", "origin": date(2026, 10, 20)}, date(2026, 11, 3))


@pytest.mark.parametrize("run_type", ["hoofd", "verversing"])
def test_kies_type(tmp_path, run_type):
    cfg = maak_config(tmp_path)
    D = date(2026, 11, 1)
    if run_type == "verversing":
        archive.schrijf_run(cfg, _run_rijen(D, "hoofd", "2026-11-01T12:20:00Z", 0, 3), pd.Timestamp("2026-11-01T12:20:00Z"), "hoofd")
    assert daily.kies_type(cfg, D) == run_type


def test_historie_export_is_compact_en_wordt_gevonden(tmp_path):
    cfg = maak_config(tmp_path, rolling_venster_dagen=365, operationele_methode="lightgbm_d2")
    cfg.processed_dir.mkdir(parents=True)
    rijen = []
    for i in range(200):
        D = pd.Timestamp("2026-01-01") + pd.Timedelta(days=i)
        uren = local_hour_range(D.date() + timedelta(days=2))[:3]
        for m in ("lightgbm_w365_d2", "profiel_4w", "lightgbm_w90"):
            rijen.append(pd.DataFrame({"origin": D, "time_utc": uren, "horizon_dag": 2, "methode": m, "p10": 1.0, "p50": 2.0,
                                       "p90": 3.0, DOEL: 2.5, "p10_kal": 0.5, "p90_kal": 3.5, "conformal_q": 0.5}))
    pd.concat(rijen).to_parquet(cfg.processed_dir / "voorspellingen_experimenten.parquet", index=False)
    pad = archive.exporteer_historie(cfg, "lightgbm_d2", dagen=150)
    h = pd.read_parquet(pad)
    assert set(h["methode"]) == {"lightgbm_w365_d2", "profiel_4w"}
    assert h["origin"].nunique() == 151
    # het exportbestand telt zelf mee als historie, zonder dubbele rijen
    bt = archive.backtest_historie(cfg, "lightgbm_d2")
    assert bt.groupby(["methode", "origin", "time_utc"]).size().max() == 1
    assert set(bt["methode"]) == {"lightgbm_d2", "profiel_4w"}


def test_forecast_json_dagsoort_en_feestdag(tmp_path):
    cfg = maak_config(tmp_path)
    (tmp_path / "data").mkdir(exist_ok=True)
    (tmp_path / "data" / "leveranciers.yaml").write_text("peildatum_lijst: 2026-11-01\nleveranciers: []\n", encoding="utf-8")
    vandaag = date(2026, 5, 12)   # dag 2 = donderdag 14 mei 2026, Hemelvaartsdag; dag 3 = brugdag
    prijzen = _prijzen(vandaag + timedelta(days=1), vanaf=date(2026, 3, 1))
    bekend = daily.bekende_uren(prijzen, vandaag, vandaag)
    delen = [bekend]
    for k in (2, 3):
        uren = local_hour_range(vandaag + timedelta(days=k))
        p50 = np.full(len(uren), 90.0)
        delen.append(pd.DataFrame({"origin": pd.Timestamp(vandaag), "time_utc": uren, "horizon_dag": k, "horizon_uren": 40.0,
                                   "p10": p50 - 10, "p50": p50, "p90": p50 + 10, "p10_kal": p50 - 15, "p90_kal": p50 + 15,
                                   "conformal_q": 5.0, "alpha_aci": 0.2, "profiel_p50": 95.0, DOEL: np.nan, "bekend": False}))
    alles = pd.concat(delen, ignore_index=True)
    f = site_export.maak_forecast_json(cfg, alles, prijzen, vandaag, pd.Timestamp("2026-05-12T12:30Z"), "hoofd", None)
    per_datum = {d["datum"]: d for d in f["dagen"]}
    assert per_datum["2026-05-14"]["dagsoort"] == "feestdag" and per_datum["2026-05-14"]["feestdag"] == "Hemelvaartsdag"
    assert per_datum["2026-05-15"]["dagsoort"] == "brugdag" and per_datum["2026-05-15"]["feestdag"] is None
    assert per_datum["2026-05-12"]["dagsoort"] == "werkdag"
    assert set(f["feestdag_effect"]) == {"pct_tov_werkdag", "aantal_feestdagen", "vanaf", "tot"}
    json.dumps(f, default=str)


def test_middag_beslissing(tmp_path):
    cfg = maak_config(tmp_path)
    vandaag = date(2026, 11, 2)
    # prijzen voor morgen nog niet binnen: voorspelmoment is gisteren -> overslaan
    assert daily.middag_beslissing(cfg, vandaag - timedelta(days=1), vandaag) == "overgeslagen"
    # prijzen binnen en nog geen hoofdrun -> hoofdrun
    assert daily.middag_beslissing(cfg, vandaag, vandaag) == "hoofd"
    archive.schrijf_run(cfg, _run_rijen(vandaag, "hoofd", "2026-11-02T12:25:00Z", 0, 3), pd.Timestamp("2026-11-02T12:25:00Z"), "hoofd")
    # tweede poging dezelfde dag -> overslaan
    assert daily.middag_beslissing(cfg, vandaag, vandaag) == "overgeslagen"


def test_overgeslagen_runs_tellen_niet_als_mislukt(tmp_path):
    cfg = maak_config(tmp_path)
    archive.log_run(cfg, pd.Timestamp("2026-11-02T11:20:00Z"), "overgeslagen", date(2026, 11, 1), 12.0, "overgeslagen", "prijzen voor morgen nog niet binnen")
    archive.log_run(cfg, pd.Timestamp("2026-11-02T12:20:00Z"), "hoofd", date(2026, 11, 2), 90.0, "ok")
    archive.log_run(cfg, pd.Timestamp("2026-11-02T18:05:00Z"), "verversing", date(2026, 11, 2), 20.0, "fout", "weer niet bereikbaar")
    t = refresh.betrouwbaarheid_runs(cfg).set_index("slot")
    assert t.loc["hoofd", "runs"] == 1 and t.loc["hoofd", "gelukt"] == 1
    assert t.loc["19:00", "gelukt"] == 0
    assert t.loc["middag overgeslagen", "runs"] == 1


def test_nieuwe_installatie_rekent_zestig_dagen_na(tmp_path):
    cfg = maak_config(tmp_path)
    vandaag = date(2026, 11, 17)
    # geen backtest en geen runs: de laatste 60 dagen moeten achteraf worden nagerekend (besluit 76)
    ontbreekt = archive.ontbrekende_origins(cfg, "lightgbm", vandaag)
    assert len(ontbreekt) == archive.KOUDE_START_DAGEN
    assert ontbreekt[0] == vandaag - timedelta(days=60) and ontbreekt[-1] == vandaag - timedelta(days=1)
    # staat er eenmaal een run, dan telt alleen wat sinds de eerste run ontbreekt
    eerste = vandaag - timedelta(days=3)
    archive.schrijf_run(cfg, _run_rijen(eerste, "inhaal", "2026-11-14T12:15:00Z", 0, 3), pd.Timestamp("2026-11-14T12:15:00Z"), "inhaal")
    assert archive.ontbrekende_origins(cfg, "lightgbm", vandaag) == [vandaag - timedelta(days=2), vandaag - timedelta(days=1)]


def test_weer_ophalen_in_rondes(tmp_path, monkeypatch):
    from stroomprijsvoorspeller.sources.http import BronNietBereikbaar

    cfg = maak_config(tmp_path)
    aanroepen, gewacht = [], []

    def hapert_twee_keer(_cfg):
        aanroepen.append(1)
        if len(aanroepen) < 3:
            raise BronNietBereikbaar("opgegeven na 3 pogingen")

    monkeypatch.setattr(daily.open_meteo, "store_forecasts", hapert_twee_keer)
    # derde ronde lukt: twee keer 20 minuten gewacht
    assert daily.haal_weer_op(cfg, rondes=3, wacht_minuten=20, slaap=gewacht.append) is True
    assert len(aanroepen) == 3 and gewacht == [1200, 1200]

    # blijft de bron weg, dan na de laatste ronde False, zonder daarna nog te wachten
    aanroepen.clear(); gewacht.clear()
    monkeypatch.setattr(daily.open_meteo, "store_forecasts", lambda _cfg: (_ for _ in ()).throw(BronNietBereikbaar("weg")))
    assert daily.haal_weer_op(cfg, rondes=3, wacht_minuten=20, slaap=gewacht.append) is False
    assert gewacht == [1200, 1200]
    # lokaal is de standaard een ronde: meteen False, niet wachten
    gewacht.clear()
    assert daily.haal_weer_op(cfg, slaap=gewacht.append) is False and gewacht == []


def test_verversing_zonder_weer_telt_als_niet_gelukt(tmp_path):
    cfg = maak_config(tmp_path)
    archive.log_run(cfg, pd.Timestamp("2026-11-18T07:16:00Z"), "verversing", date(2026, 11, 17), 2700.0, "geen_weer", "weerbron niet bereikbaar")
    archive.log_run(cfg, pd.Timestamp("2026-11-18T01:11:00Z"), "verversing", date(2026, 11, 17), 20.0, "ok")
    t = refresh.betrouwbaarheid_runs(cfg).set_index("slot")
    assert t.loc["07:00", "runs"] == 1 and t.loc["07:00", "gelukt"] == 0
    assert t.loc["01:00", "gelukt"] == 1
