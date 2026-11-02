# stroomprijsvoorspeller

Open, gratis voorspeller van de Nederlandse day-ahead stroomprijs (EPEX, biedzone NL), tot 7 dagen vooruit, met een
onzekerheidsmarge. Voor huishoudens met een dynamisch contract die willen weten wanneer laden of wassen goedkoop is.

Status: in opbouw. Fase 1 (data), 2 (modellen), 3 (backtest) en 4 (dagelijkse run en site) zijn klaar; de site draait
lokaal. Zie [PLAN.md](PLAN.md) voor de fasen en [DECISIONS.md](DECISIONS.md) voor alle keuzes.

Resultaat (rolling-origin backtest, 786 dagen, aug 2024 t/m okt 2026): het gekozen LightGBM-kwantielmodel (venster 365
dagen, apart model voor dag 2) zit op dag 2 gemiddeld 17,0 EUR/MWh (1,7 ct/kWh) naast de werkelijke uurprijs, op dag 7
25,9. Het naïeve 4-weeks uurprofiel zit op 28 tot 30. Het 80%-interval dekt na kalibratie 79% van de werkelijke prijzen. Volledige backtest met tabellen, grafieken en eerlijke kanttekeningen in
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
epv train      # traint het operationele model (config: lightgbm_d2, venster 365 dagen)
epv predict    # voorspelt dag 2 t/m 7 met de actuele weersverwachting
epv daily      # de dagelijkse run: ophalen, gemiste dagen inhalen, zo nodig hertrainen, voorspellen, archiveren, site-JSON
epv refresh    # lichte verversing: nieuw weer, opnieuw voorspellen met het bestaande model
epv serve      # lokale server voor de site (http://localhost:8766) met een ververs-knop die `epv daily` start
epv evalueer-verversingen   # wekelijks: wat leveren de verversingen op? -> reports/verversingen.md
pytest
```

## Dagelijks gebruik op deze pc

Twee bestanden in de projectmap (geen taakplanner, zie besluit 49):

- `ververs.bat`: maakt een nieuwe voorspelling. Haalt prijzen en weer op, haalt gemiste dagen in, traint het model opnieuw
  als het ouder is dan een week, voorspelt 7 dagen vooruit en schrijft `site/data/forecast.json`. Duurt een paar minuten.
- `site.bat`: opent de site in de browser via een lokaal servertje. De knop **Ververs** rechtsboven doet hetzelfde als
  `ververs.bat` en laadt de pagina daarna opnieuw.

De prijzen voor morgen komen rond 13:00 binnen; daarvoor verversen geeft één dag minder vooruit. Elke run komt in
`data/runs/` terecht (hoofdrun, verversing of inhaalrun), zodat de kalibratie en de scores op de site doorlopen, ook na
een paar dagen niet draaien.

Alle instellingen staan in `config.yaml`: weerpunten, horizon, kwantielen, rolling venster, LightGBM-parameters.

Verdere rapporten: [dataverkenning](reports/verkenning/data-verkenning.md), [literatuurmemo over
schattingsmethoden](reports/literatuur-schattingsmethoden.md), [inventarisatie van leveranciers met een dynamisch
contract](reports/leveranciers-inventarisatie.md). Ontwerpvarianten van de site: `site/ontwerpen/`.

## Licentie

MIT. Zie [LICENSE](LICENSE).
