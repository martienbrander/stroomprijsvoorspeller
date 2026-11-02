# stroomprijsvoorspeller

Open, gratis voorspeller van de Nederlandse day-ahead stroomprijs (EPEX, biedzone NL), tot 7 dagen vooruit, met een
onzekerheidsmarge en per dag een betrouwbaarheidslabel. Voor huishoudens met een dynamisch contract die willen weten
wanneer de auto laden of de was draaien goedkoop is.

De dag van de voorspelling en de dag erna staan vast (die prijzen komen van de beurs). De dagen daarna zijn een verwachting op basis van
de weersverwachting (wind op zee en land, zon, temperatuur) en de prijzen van de afgelopen dagen. Bij elke verwachting
hoort een onder- en bovengrens; hoe verder vooruit, hoe breder die band en hoe minder detail de site laat zien.

Status: fase 1 tot en met 5 klaar (data, modellen, backtest, dagelijkse run met site, publicatie). De site draait
lokaal; online zetten kan met de meegeleverde workflows. Zie [PLAN.md](PLAN.md) voor de fasen en
[DECISIONS.md](DECISIONS.md) voor alle 52 keuzes en aannames.

## Hoe goed is het?

Getest als in de econometrie: elke dag om 13:00 opnieuw voorspellen met alleen wat toen bekend was, 786 dagen lang
(augustus 2024 tot en met oktober 2026), en vergelijken met drie naïeve regels. Gemiddelde afwijking per uur, in
EUR/MWh (delen door 10 geeft ct/kWh):

| | dag 2 (overmorgen) | dag 4 | dag 7 |
|---|---|---|---|
| dit model (LightGBM, venster 365 dagen, apart model voor dag 2) | 17,0 | 21,6 | 25,9 |
| naïef: gemiddeld uurprofiel van de laatste 4 weken | 28,4 | 29,1 | 30,2 |

Het verschil is op elke horizon statistisch hard (Diebold-Mariano, p < 0,0001). Het 80%-interval dekt na kalibratie
79% van de werkelijke prijzen. Eerlijke kanttekening: voor het kiezen van het goedkoopste blok van drie uur is het
model maar iets beter dan de naïeve regel (89% tegen 88% binnen 10% van het beste blok op dag 2). De winst zit in
hoeveel het kost en hoe zeker dat is, niet zozeer in wanneer. Volledige backtest met tabellen, grafieken en de
experimenten die tot de modelkeuze leidden: [reports/backtest.md](reports/backtest.md).

## Beperkingen

- Een plotselinge sprong in het prijsniveau (zoals in oktober 2026) zit niet in de weersverwachting; het model loopt
  dan een paar weken achter en de band is te smal. De scores op de site ("afgelopen 30 dagen") laten dat zien.
- De middaguren zijn structureel het moeilijkst: daar bepalen zon en de mate van afschakelen de prijs.
- Dag 6 en 7 geven alleen een richting; de site toont ze als dagdelen en noemt ze "onzeker".
- De betrouwbaarheid per dag is relatief ten opzichte van de naïeve regel, niet absoluut.
- Alleen biedzone Nederland, alleen de kale beursprijs. Belasting, btw en inkoopvergoeding rekent de site er zelf bij
  (drie prijsstanden: Marktprijs, Marktprijs+ en All-in); de leverancier bepaalt wat u echt betaalt.
- De weersverwachting komt van één model (Open-Meteo `best_match`); er is geen ensemble van weermodellen.

## Bronnen en licenties

- Prijzen: [Energy-Charts](https://energy-charts.info) van Fraunhofer ISE (data: Bundesnetzagentur | SMARD.de,
  CC BY 4.0). Optionele fallback: ENTSO-E Transparency Platform (gratis token nodig, `ENTSOE_TOKEN` in `.env`).
- Weer: [Open-Meteo](https://open-meteo.com) (CC BY 4.0). Forecast API voor de komende dagen, Previous Runs API voor
  historische verwachtingen zoals die destijds waren, zodat de backtest geen kennis van later gebruikt.
- Kalender: Nederlandse feestdagen via het Python-package `holidays`.
- Leveranciers: met de hand bijgehouden lijst in `data/leveranciers.yaml`, nagelopen tegen het ACM-register;
  zie [reports/leveranciers-inventarisatie.md](reports/leveranciers-inventarisatie.md).

Code: MIT, zie [LICENSE](LICENSE). De gepubliceerde cijfers (JSON) zijn afgeleid van CC BY 4.0-bronnen en worden
onder dezelfde licentie doorgegeven met bronvermelding. Geen cookies, geen tracking, geen persoonsgegevens.

## Zelf draaien

Python 3.11 of hoger. Alles wordt bestuurd door één configbestand, `config.yaml` (weerpunten, horizon, kwantielen,
trainingsvenster, LightGBM-parameters).

```bash
python -m venv .venv
.venv\Scripts\pip install -e ".[model,dev]"
epv daily      # alles in één keer: ophalen, gemiste dagen inhalen, trainen, voorspellen, archiveren, site-JSON
epv serve      # lokale server voor de site (http://localhost:8766) met een ververs-knop
pytest
```

De eerste `epv daily` haalt drie jaar prijzen en de weerhistorie vanaf maart 2024 op (enkele minuten), bouwt de
featurematrix en traint het model. Daarna is een run één tot twee minuten, een verversing een halve minuut.

De losse stappen, voor wie wil kijken of meten:

```bash
epv fetch      # prijzen en weer ophalen, incrementeel
epv build      # data/processed opbouwen
epv status     # wat er aan data is
epv features   # featurematrix per voorspelmoment en doeluur
epv compare    # rolling-origin vergelijking van baselines en modellen -> reports/methodenvergelijking.md (ca. 2 uur)
epv backtest   # volledig rapport met grafieken -> reports/backtest.md
epv train      # operationeel model trainen (config: lightgbm_d2, venster 365 dagen)
epv predict    # voorspellen met de actuele weersverwachting
epv refresh    # lichte verversing: nieuw weer, opnieuw voorspellen met het bestaande model
epv evalueer-verversingen   # wat leveren de verversingen op? -> reports/verversingen.md
epv historie-export         # compacte backtest-historie voor online gebruik
```

## Dagelijks gebruik op deze pc

Twee bestanden in de projectmap (geen taakplanner, besluit 49):

- `ververs.bat`: maakt een nieuwe voorspelling. Haalt prijzen en weer op, haalt gemiste dagen in, traint het model
  opnieuw als het ouder is dan een week, voorspelt 7 dagen vooruit en schrijft `site/data/forecast.json`.
- `site.bat`: opent de site in de browser via een lokaal servertje. De knop **Ververs** rechtsboven doet hetzelfde
  als `ververs.bat` en laadt de pagina daarna opnieuw.

De prijzen voor de volgende dag komen rond 13:00 binnen; eerder verversen geeft één dag minder vooruit. Elke run komt in
`data/runs/` terecht (hoofdrun, verversing of inhaalrun). Een paar dagen niet draaien is geen probleem: de volgende
run rekent de gemiste dagen alsnog uit, zodat de kalibratie en de scores doorlopen (besluit 50).

## API

De cijfers staan als JSON naast de site: `/api/v1/voorspelling.json` en `/data/leveranciers.json`. Velden, eenheden en
voorwaarden in [API.md](API.md).

## Online zetten

De workflows in `.github/workflows/` doen online hetzelfde als `ververs.bat` lokaal (besluit 47):

1. Maak een GitHub-repository en push `main`.
2. Zet in de instellingen van de repository GitHub Pages op "GitHub Actions".
3. Start de workflow "dagelijkse run" één keer met de hand; die haalt alles op en zet de site live. Daarna draait hij
   op het rooster: drie pogingen rond de day-ahead publicatie en drie verversingen per dag.
4. De werkdata (`data/`, `models/`) staan na elke run op de branch `data`, in één commit zonder geschiedenis. Wil je de
   lokale historie meenemen, draai dan eerst `epv historie-export` en push `data/`, `models/` en dat exportbestand
   naar die branch.

De wekelijkse workflow schrijft `reports/verversingen.md` bij.

## Onderhoud en kosten

Hosting op GitHub Pages is gratis, een domeinnaam kost ongeveer tien euro per jaar; het werk zit in het bijhouden van
de leverancierstabel, het controleren van de scores en het meegroeien met de bronnen. Er komen geen advertenties en
geen affiliate-links, omdat die de onafhankelijkheid van de leverancierstabel zouden aantasten. Hoe het onderhoud op
termijn betaald wordt (donaties, een subsidie voor uitbreidingen) is nog open; zie besluit 38.

## Bijdragen

Fouten melden, een leverancier aanvullen (`data/leveranciers.yaml`, met bron en peildatum) of een idee aandragen kan
via een issue of pull request. Voor codewijzigingen: `ruff check src tests` en `pytest` moeten slagen, en elke aanname
krijgt een regel in `DECISIONS.md`.

Verdere rapporten: [dataverkenning](reports/verkenning/data-verkenning.md), [literatuurmemo over
schattingsmethoden](reports/literatuur-schattingsmethoden.md). Ontwerpvarianten van de site: `site/ontwerpen/`.
