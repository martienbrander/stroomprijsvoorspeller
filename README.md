# stroomprijsvoorspeller

Open, gratis voorspeller van de Nederlandse day-ahead stroomprijs (EPEX, biedzone NL), tot 7 dagen vooruit, met een
onzekerheidsmarge en per dag een betrouwbaarheidslabel. Voor huishoudens met een dynamisch contract die willen weten
wanneer de auto laden of de was draaien goedkoop is.

De dag van de voorspelling en de dag erna staan vast (die prijzen komen van de beurs). De dagen daarna zijn een verwachting op basis van
de weersverwachting (wind op zee en land, zon, temperatuur) en de prijzen van de afgelopen dagen. Bij elke verwachting
hoort een onder- en bovengrens; hoe verder vooruit, hoe breder die band en hoe minder detail de site laat zien.

Status: testversie 0.1.0. Fase 1 tot en met 5 zijn klaar (data, modellen, backtest, dagelijkse run met site,
publicatie); de site staat online ter beproeving, de voorspellingen worden nog gecontroleerd en de opmaak kan
veranderen. Zie [PLAN.md](PLAN.md) voor de fasen en
[DECISIONS.md](DECISIONS.md) voor alle keuzes en aannames.

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
- Feestdagen en weekenden kent het model; schoolvakanties en brugdagen niet. De backtest splitst de fout uit per dagsoort en laat zien dat het model in schoolvakanties niet slechter is dan op werkdagen, dus daar is geen aparte vlag nodig. Feestdagen waren de afgelopen twee jaar gemiddeld ruim 20% goedkoper dan de werkdagen eromheen; de site noemt de feestdag bij de dag.

**Geen advies, geen garantie.** Deze voorspelling is een inschatting op basis van openbare gegevens en een statistisch
model. Het is geen advies en geen garantie; de werkelijke prijzen kunnen afwijken. Gebruik is op eigen risico. De maker
is niet aansprakelijk voor beslissingen die op deze cijfers worden gebaseerd. De code valt onder de MIT-licentie, die
hetzelfde zegt over de software.

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
  als `ververs.bat` en laadt de pagina daarna opnieuw. Het servervenster toont ook een adres als
  `http://192.168.x.x:8766/` voor je telefoon op hetzelfde wifinetwerk (`epv serve --netwerk`; zonder die optie is de
  site alleen op de pc zelf te zien). Windows Firewall vraagt de eerste keer om toestemming voor Python.

De prijzen voor de volgende dag komen tussen 13:00 en 14:00 binnen; eerder verversen geeft één dag minder vooruit. De pagina noemt dagen altijd bij weekdag en datum en laat een voorbije dag na middernacht vanzelf vallen, ook als ze open blijft staan. Elke run komt in
`data/runs/` terecht (hoofdrun, verversing of inhaalrun). Een paar dagen niet draaien is geen probleem: de volgende
run rekent de gemiste dagen alsnog uit, zodat de kalibratie en de scores doorlopen (besluit 50).

## API

De cijfers staan als JSON naast de site: `/api/v1/voorspelling.json` en `/data/leveranciers.json`. Velden, eenheden en
voorwaarden in [API.md](API.md).

## Online

De site staat op [martienbrander.github.io/stroomprijsvoorspeller](https://martienbrander.github.io/stroomprijsvoorspeller/)
en verhuist naar [stroomprijsvoorspeller.nl](https://stroomprijsvoorspeller.nl) zodra de DNS-records bij dds.nl staan.
De broncode staat op [github.com/martienbrander/stroomprijsvoorspeller](https://github.com/martienbrander/stroomprijsvoorspeller).

**Wat er draait** (besluit 47, 54, 62). De workflow "dagelijkse run" in `.github/workflows/daily.yml` doet online
hetzelfde als `ververs.bat` lokaal: vijf pogingen tussen 12:20 en 15:20 (alleen de eerste poging waarin de prijzen voor
morgen binnen zijn doet echt iets; GitHub rekent in UTC, vandaar de ruime marge voor zomer- en wintertijd) en drie
verversingen per dag (19:05, 01:05, 07:05). Elke run haalt de werkdata van de branch `data`, draait `epv daily`, zet de
nieuwe werkdata terug op die branch (één commit, geen geschiedenis) en publiceert `site/` via GitHub Pages. Een pagina die openstaat kijkt elke vijf minuten of er een nieuwere
voorspelling staat en werkt zichzelf dan bij; de knop Herladen doet dat meteen. De
workflow "wekelijkse evaluatie" schrijft op maandag `reports/verversingen.md` bij.

**Waar staat wat, en wat kost het.** Code, dagelijkse run en hosting: GitHub (publieke repository, gratis). Domein en
DNS: dds.nl (ongeveer 36 euro per jaar). Mail: geen; het domein verstuurt geen mail en de DNS zegt dat ook.

**Als een run mislukt.** Kijk onder "Actions" naar de rode run en open de stap "Run"; daar staat de foutmelding van
`epv daily`. Een gemiste dag is geen ramp: de volgende run haalt de gemiste dagen in (besluit 50) en de site toont hoe
oud de laatste voorspelling is. Zelf een run starten: Actions, "dagelijkse run", "Run workflow" met type `auto` (of
`gh workflow run "dagelijkse run" -f type=auto`). Is de branch `data` onbruikbaar geraakt, verwijder hem dan; de
volgende run haalt alles opnieuw op (dat duurt dan een kwartier in plaats van twee minuten) en bouwt de kalibratie
opnieuw op uit het runarchief dat verloren is, dus doe dat alleen als het echt moet.

**Lokaal blijft werken.** `ververs.bat` en `epv serve` doen het nog steeds op deze pc. De lokale werkdata en de
werkdata online zijn gescheiden en worden niet gesynchroniseerd; de online run is de bron voor de site.

## Onderhoud en kosten

Hosting op GitHub Pages is gratis, de domeinnaam kost ongeveer 36 euro per jaar bij dds.nl; het werk zit in het bijhouden van
de leverancierstabel, het controleren van de scores en het meegroeien met de bronnen. Er komen geen advertenties en
geen affiliate-links, omdat die de onafhankelijkheid van de leverancierstabel zouden aantasten. Hoe het onderhoud op
termijn betaald wordt (donaties, een subsidie voor uitbreidingen) is nog open; zie besluit 38.

## Hoe dit gemaakt is

Dit project is gebouwd door Martien Brander samen met Claude (Claude Code van Anthropic). De keuzes staan in
[DECISIONS.md](DECISIONS.md); de opdrachtgever nam elk besluit, Claude schreef de code, de analyses en de documentatie.
Elke commit vermeldt dat met een regel `Co-Authored-By`. Fouten zijn van ons samen, meld ze gerust via een issue.

## Bijdragen

Fouten melden, een leverancier aanvullen (`data/leveranciers.yaml`, met bron en peildatum) of een idee aandragen kan
via een issue of pull request op [github.com/martienbrander/stroomprijsvoorspeller](https://github.com/martienbrander/stroomprijsvoorspeller). Voor codewijzigingen: `ruff check src tests` en `pytest` moeten slagen, en elke aanname
krijgt een regel in `DECISIONS.md`.

Verdere rapporten: [dataverkenning](reports/verkenning/data-verkenning.md), [literatuurmemo over
schattingsmethoden](reports/literatuur-schattingsmethoden.md). Ontwerpvarianten van de site: `site/ontwerpen/`.
