# stroomprijsvoorspeller

Open, gratis voorspeller van de Nederlandse day-ahead stroomprijs (EPEX, biedzone NL), tot 5 dagen vooruit, met een
onzekerheidsmarge. Voor huishoudens met een dynamisch contract die willen weten wanneer laden of wassen goedkoop is.

Status: in opbouw. Fase 1 (data) is klaar. Zie [PLAN.md](PLAN.md) voor de fasen en [DECISIONS.md](DECISIONS.md) voor alle keuzes.

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
pytest
```

Alle instellingen staan in `config.yaml`: weerpunten, horizon, kwantielen, rolling venster.

## Licentie

MIT. Zie [LICENSE](LICENSE).
