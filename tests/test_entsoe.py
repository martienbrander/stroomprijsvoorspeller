import pandas as pd
import pytest
import requests

from stroomprijsvoorspeller.sources import entsoe
from stroomprijsvoorspeller.sources.http import BronNietBereikbaar

XML = """<?xml version="1.0" encoding="UTF-8"?>
<Publication_MarketDocument xmlns="urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:3">
  <TimeSeries>
    <mRID>1</mRID>
    <curveType>A03</curveType>
    <Period>
      <timeInterval><start>2025-06-01T22:00Z</start><end>2025-06-02T02:00Z</end></timeInterval>
      <resolution>PT60M</resolution>
      <Point><position>1</position><price.amount>80.0</price.amount></Point>
      <Point><position>2</position><price.amount>75.5</price.amount></Point>
      <Point><position>4</position><price.amount>60.0</price.amount></Point>
    </Period>
  </TimeSeries>
</Publication_MarketDocument>
"""


def test_parse_xml_vult_ontbrekende_positie_door():
    df = entsoe.parse_xml(XML)
    assert len(df) == 4
    assert df["time_utc"].iloc[0] == pd.Timestamp("2025-06-01T22:00Z")
    # positie 3 ontbreekt (curve type A03 = zelfde prijs als vorige positie)
    assert df["prijs_eur_mwh"].tolist() == [80.0, 75.5, 75.5, 60.0]


def test_zonder_token_niet_beschikbaar(monkeypatch):
    monkeypatch.delenv("ENTSOE_TOKEN", raising=False)
    monkeypatch.setattr(entsoe, "load_dotenv", lambda: None)
    assert entsoe.beschikbaar() is False


def _reeks(resolutie: str, prijzen: list[float], contract: str = "A01") -> str:
    punten = "".join(f"<Point><position>{i}</position><price.amount>{p}</price.amount></Point>"
                     for i, p in enumerate(prijzen, start=1))
    return f"""<TimeSeries>
    <contract_MarketAgreement.type>{contract}</contract_MarketAgreement.type>
    <Period>
      <timeInterval><start>2026-11-19T22:00Z</start><end>2026-11-19T23:00Z</end></timeInterval>
      <resolution>{resolutie}</resolution>{punten}
    </Period>
  </TimeSeries>"""


def _document(*reeksen: str) -> str:
    return ('<Publication_MarketDocument xmlns="urn:iec62325.351:tc57wg16:451-3:publicationdocument:7:3">'
            + "".join(reeksen) + "</Publication_MarketDocument>")


def test_parse_xml_kiest_day_ahead_en_de_fijnste_resolutie():
    df = entsoe.parse_xml(_document(
        _reeks("PT60M", [50.0]),                                   # hetzelfde uur per uur: verliest van de kwartieren
        _reeks("PT15M", [10.0, 20.0, 30.0, 40.0]),
        _reeks("PT15M", [999.0, 999.0, 999.0, 999.0], contract="A07"),   # intraday-veiling: telt niet mee
    ))
    assert df["time_utc"].tolist() == list(pd.date_range("2026-11-19T22:00Z", periods=4, freq="15min"))
    assert df["prijs_eur_mwh"].tolist() == [10.0, 20.0, 30.0, 40.0]


def test_parse_xml_zonder_reeksen_is_leeg():
    # zo antwoordt ENTSO-E als de prijzen er nog niet zijn
    leeg = ('<Acknowledgement_MarketDocument xmlns="urn:iec62325.351:tc57wg0:451-1:acknowledgementdocument:7:0">'
            "<Reason><code>999</code><text>No matching data found</text></Reason></Acknowledgement_MarketDocument>")
    assert entsoe.parse_xml(leeg).empty


class _Sessie:
    def __init__(self, antwoord):
        self.antwoord = antwoord

    def get(self, *_args, **_kwargs):
        if isinstance(self.antwoord, Exception):
            raise self.antwoord
        return self.antwoord


class _Antwoord:
    def __init__(self, status_code: int, text: str = ""):
        self.status_code, self.text = status_code, text


@pytest.mark.parametrize("antwoord", [
    requests.ConnectionError("Max retries exceeded with url: /api?securityToken=geheim-token&documentType=A44"),
    _Antwoord(401, "Unauthorized geheim-token"),
])
def test_foutmelding_bevat_het_token_niet(monkeypatch, antwoord):
    monkeypatch.setenv("ENTSOE_TOKEN", "geheim-token")
    monkeypatch.setattr(entsoe, "load_dotenv", lambda: None)
    with pytest.raises(BronNietBereikbaar) as fout:
        entsoe.fetch_prices(pd.Timestamp("2026-11-19T23:00Z"), pd.Timestamp("2026-11-20T23:00Z"),
                            session=_Sessie(antwoord))
    assert "geheim-token" not in str(fout.value)
    # ook de oorspronkelijke fout (met de URL erin) hangt er niet meer aan
    assert fout.value.__cause__ is None
    assert fout.value.__context__ is None or fout.value.__suppress_context__
