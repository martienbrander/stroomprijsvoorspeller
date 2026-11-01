import pandas as pd

from stroomprijsvoorspeller.sources import entsoe

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
