# stroomprijsvoorspeller

Open, gratis voorspeller van de Nederlandse day-ahead stroomprijs (EPEX, biedzone NL), tot 7 dagen vooruit, met een
onzekerheidsmarge. Voor huishoudens met een dynamisch contract die willen weten wanneer laden of wassen goedkoop is.

Status: in opbouw. Fase 1 (data), 2 (modellen) en 3 (backtest) zijn klaar. Zie [PLAN.md](PLAN.md) voor de fasen en
[DECISIONS.md](DECISIONS.md) voor alle keuzes.

Eerste resultaat (rolling-origin backtest, 786 dagen, aug 2024 t/m okt 2026): het LightGBM-kwantielmodel zit op dag 2
gemiddeld 20,7 EUR/MWh (2,1 ct/kWh) naast de werkelijke uurprijs, op dag 7 27,0. Het naïeve 4-weeks uurprofiel zit op
28 tot 30. Het 80%-interval dekt na kalibratie 79% van de werkelijke prijzen. Volledige backtest met tabellen, grafieken en eerlijke kanttekeningen in
[reports/backtest.md](reports/backtest.md); de methodenvergelijking in [reports/methodenvergelijking.md](reports/methodenvergelijking.md).

## Bronnen

- Prijzen: [Energy-Charts](https://energy-charts.info) van Fraunhofer ISE (data: Bundesnetzagentur | SMARD.de, CC BY 4.0).
  Optionele fallback: ENTSO-E Transparency Platform (gratis token nodig).
- Weer: [Open-Meteo](https://open-meteo.com) (CC BY 4.0). Forecast API voor de komende dagen, Previous Runs API voor
  historische verwachtingen zoals die destijds waren.
- Kalender: Nederlandse feestdagen via het Python-package `holidays`.

## Zelf draaien

```bash
python -m venv .venv
.venv\Scripts\pip install -e ".[dev]"
epv fetch      # haalt prijzen (vanaf nov 2022) en weer (vanaf maart 2024) op, incrementeel
epv build      # bouwt data/processed
epv status     # toont wat er aan data is
epv features   # bouwt de featurematrix per voorspelmoment en doeluur
epv compare    # rolling-origin vergelijking van baselines en modellen -> reports/methodenvergelijking.md (duurt ~2 uur)
epv backtest   # volledig rapport met grafieken -> reports/backtest.md
epv train      # traint het operationele model op de laatste 180 dagen
epv predict    # voorspelt dag 2 t/m 7 met de actuele weersverwachting
pytest
```

Alle instellingen staan in `config.yaml`: weerpunten, horizon, kwantielen, rolling venster, LightGBM-parameters.

Verdere rapporten: [dataverkenning](reports/verkenning/data-verkenning.md), [literatuurmemo over
schattingsmethoden](reports/literatuur-schattingsmethoden.md), [inventarisatie van leveranciers met een dynamisch
contract](reports/leveranciers-inventarisatie.md). Ontwerpvarianten van de site: `site/ontwerpen/`.

## Licentie

MIT. Zie [LICENSE](LICENSE).
