# PLAN — stroomprijsvoorspeller: open stroomprijsvoorspeller voor Nederland

Naam: **stroomprijsvoorspeller** (map `C:\ClaudeCode\stroomprijsvoorspeller`, package `stroomprijsvoorspeller`).

## Wat het wordt

Een Python-pipeline die dagelijks de NL day-ahead prijs (EPEX, biedzone NL) voor dag 2 t/m 5 voorspelt met een
80%-interval, en een statische site die dat toont. Alles draait op gratis bronnen (Energy-Charts, Open-Meteo) en
gratis hosting (GitHub Actions + GitHub Pages).

## Fasen

| Fase | Inhoud | Resultaat |
|---|---|---|
| 1 | Data ophalen en verwerken | `data/raw/*.parquet`, `data/processed/*.parquet`, `python -m stroomprijsvoorspeller fetch` werkt incrementeel, tests |
| 2 | Features, baselines, kwantielmodellen (lineair asinh, LightGBM), conformal-kalibratie, methodenvergelijking op rolling-origin | `epv features`, `epv compare` -> `reports/methodenvergelijking.md`, `epv train`, `epv predict` |
| 3 | Backtest met dagelijkse 13:00-simulatie | `reports/backtest.md` + png's, tests op lekkage |
| 4 | Dagelijkse run (hoofd, verversing, inhaal), runarchief, JSON, site op variant C, lokale server met ververs-knop | `epv daily`, `epv serve`, `ververs.bat`, `site/` leest `site/data/forecast.json` |
| 5 | README, API-documentatie, GitHub Actions + Pages | online sinds 16 november 2026 op martienbrander.github.io/stroomprijsvoorspeller; eigen domein stroomprijsvoorspeller.nl zodra de DNS staat |

Na elke fase: korte samenvatting, commit, wachten op akkoord.

## Mappenstructuur (src-layout, toekomstvast: nieuwe bron = één bestand in sources/, nieuw model = één bestand in model/)

```
stroomprijsvoorspeller/
├── PLAN.md                    dit plan
├── DECISIONS.md               alle aannames en keuzes, doorlopend genummerd
├── README.md                  Nederlands: doel, bronnen, werking, beperkingen, zelf draaien, bijdragen
├── LICENSE                    MIT
├── pyproject.toml             package, dependencies, `epv`-commando, pytest- en ruff-config
├── config.yaml                één configbestand: weerpunten, horizon, kwantielen, rolling venster, paden
├── .env.example               ENTSOE_TOKEN= (optioneel)
├── .gitignore                 data/, models/, .env, site/data/*.json (gegenereerd)
│
├── src/stroomprijsvoorspeller/   Python-package
│   ├── cli.py                 `epv fetch | build | status` (later: train, backtest, predict, daily)
│   ├── config.py              laadt config.yaml naar een onveranderlijke Config
│   ├── timeutil.py            UTC <-> Europe/Amsterdam, dag-grenzen, zomertijd, publicatiemoment 13:00
│   ├── sources/               databronnen; pure parse-functies (testbaar zonder netwerk) + fetch/update
│   │   ├── http.py            retries, backoff, User-Agent
│   │   ├── energy_charts.py   day-ahead prijzen NL, incrementeel, ruwe resolutie bewaard
│   │   ├── entsoe.py          fallback, alleen actief met token in .env
│   │   ├── open_meteo.py      forecast (komende 7 dagen) + previous runs (lead 1-5 dagen), per weerpunt
│   │   └── calendar.py        feestdagen (holidays), weekdag, uur, maand, seizoen
│   ├── processing/
│   │   ├── prices.py          kwartier -> uurgemiddelde, kwartierreeks apart, gaten
│   │   ├── dataset.py         bouwt data/processed uit data/raw
│   │   ├── features.py        featurematrix per (voorspelmoment, doeluur); prijzen alleen < bekend_tot(D)
│   │   └── dagsoort.py        dagsoorten voor de evaluatie en de site (besluit 53)
│   ├── model/
│   │   ├── baselines.py       laatste bekende dag, vorige week, 4-weeks profiel
│   │   ├── quantile_models.py LineairKwantiel (asinh), LightGBMKwantiel, Combinatie; één interface fit/predict
│   │   ├── calibration.py     conformal (CQR) per methode en horizon, rolling venster, lekkage-vrij
│   │   └── operational.py     train op venster t/m vandaag, voorspel met actuele weersverwachting
│   ├── evaluation/
│   │   ├── rolling.py         rolling-origin loop: trainset zonder toekomst, hertrainen elke N dagen
│   │   ├── metrics.py         MAE, RMSE, pinball, dekking, breedte (fase 3: 3-uursblok, DM-toets)
│   │   └── compare.py         features bouwen/bewaren, methodenvergelijking, rapport
│   └── pipeline/              fase 4: daily.py (hoofd/verversing/inhaal), archive.py (data/runs), site_export.py (JSON), serve.py
│
├── ververs.bat, site.bat      fase 4: handmatig starten van de run en van de lokale site (besluit 49)
├── tests/                     pytest: tijd, prijzen, kalender, bronnen (zonder netwerk), config
│
├── data/                      niet in git
│   ├── raw/                   prijzen_nl_ruw.parquet, weer_prev_runs_<punt>.parquet, weer_forecast_<punt>.parquet
│   └── processed/             prijzen_nl_uur.parquet, prijzen_nl_kwartier.parquet, basis_uur.parquet, weer_prev_runs.parquet
├── models/                    laatst getrainde modellen (niet in git)
├── reports/                   backtest.md + figures/*.png (wel in git)
├── site/                      fase 4: statische site, plain HTML + JS; site/data/ bevat de gegenereerde JSON
└── .github/workflows/         fase 5 (online sinds 2026-11-16)
```

## Datastroom (fase 1)

1. `energy_charts.py` haalt `GET api.energy-charts.info/price?bzn=NL&start=..&end=..` op in blokken per kwartaal,
   vanaf 2022-11-01 (3 jaar). Resolutie wisselt op 1 oktober 2025 van uur naar kwartier. Beide bewaard:
   `prices_nl_quarter.parquet` (ruw, alleen vanaf oktober 2025) en `prices_nl_hour.parquet` (uurgemiddelde, volledige reeks).
   Incrementeel: alleen ophalen vanaf laatste bekende tijdstip minus 2 dagen (overschrijft die overlap).
2. `open_meteo.py` haalt per weerpunt op:
   - **Forecast API** (`api.open-meteo.com`): komende 7 dagen, voor de dagelijkse run.
   - **Previous Runs API** (`previous-runs-api.open-meteo.com`): variabelen `<var>_previous_dayN` voor N = 1..5.
     Dit is de verwachting zoals die N dagen eerder was. Data beschikbaar vanaf ca. maart 2024 (gecontroleerd).
     Dit is de bron voor trainen en backtesten zonder lekkage.
   - Variabelen: `wind_speed_100m`, `shortwave_radiation`, `cloud_cover`, `temperature_2m`.
3. `calendar.py`: NL-feestdagen via `holidays`, weekdag, uur, maand, seizoen.
4. Alles intern in UTC. Dag-grenzen en weergave in Europe/Amsterdam.

## Weerpunten (gekozen op basis van waar de windstroom vandaan komt)

Opgesteld vermogen wind op land eind 2024 (CBS 70960ned, MW): Flevoland 2161, Groningen 916, Zuid-Holland 750,
Noord-Holland 713, Fryslân 617, Zeeland 610, Noord-Brabant 424, Drenthe 271, rest < 250. Totaal 6955 MW.
Wind op zee ca. 4,7 GW: Borssele 1,5 GW, Hollandse Kust Zuid 1,6 GW, Hollandse Kust Noord ca. 1,0 GW, Gemini 0,6 GW.
Hollandse Kust West (1,5 GW) komt in 2026-2027 bij. Duitse wind (offshore ca. 9 GW, onshore ca. 60 GW) beweegt de NL-prijs
sterk mee via de koppeling met DE-LU. Zon (ca. 25 GW) ligt verspreid over het hele land.

| Naam | Lat | Lon | Dekt | Type |
|---|---|---|---|---|
| borssele | 51.70 | 3.05 | Borssele I-V, 1,5 GW | zee |
| hollandse_kust_zuid | 52.35 | 4.05 | HKZ + Luchterduinen, 1,6 GW | zee |
| hollandse_kust_noord | 52.70 | 4.00 | HKN, Egmond, Amalia, straks HKW | zee |
| gemini | 54.05 | 5.95 | Gemini, 0,6 GW; straks Ten noorden van de Wadden | zee |
| duitse_bocht | 54.20 | 7.20 | Duitse offshore wind | zee, buitenland |
| flevoland | 52.50 | 5.55 | Windplan Groen/Blauw, Noordoostpolder, 2,2 GW | land |
| groningen | 53.40 | 6.85 | Eemshaven, Delfzijl, N33, Drentse Monden, 1,2 GW | land |
| fryslan | 53.00 | 5.35 | Windpark Fryslân (IJsselmeer), Afsluitdijk, 0,6 GW | land |
| wieringermeer | 52.85 | 5.00 | Windpark Wieringermeer, Noord-Holland, 0,7 GW | land |
| maasvlakte | 51.95 | 4.05 | Rotterdamse haven, Zuid-Holland, 0,75 GW | land |
| zeeland | 51.55 | 3.90 | Krammer, Kreekrak, Zeeuwse kust, 0,6 GW | land |
| de_bilt | 52.10 | 5.18 | midden NL: zon, temperatuur, vraag | land, zon |
| eindhoven | 51.45 | 5.37 | zuid NL: zon, Brabantse zonneparken | land, zon |
| duitsland_noord | 53.30 | 9.00 | Duitse onshore wind (Nedersaksen, Sleeswijk-Holstein) | land, buitenland |

Alle punten staan in `config.yaml` en zijn zonder codewijziging aan te passen.

## Evaluatie van de verversingsruns (besluit 33)

Vraag: maken de lichte verversingen om 19:00, 01:00 en 07:00 (alleen nieuw weer, geen hertraining) de voorspelling
voor dezelfde doeluren beter dan de hoofdrun van 13:15? En verandert het advies erdoor?

### Wat elke run vastlegt (fase 4, in `epv daily` en `epv refresh`)

Elke run, hoofdrun of verversing, schrijft één bestand `data/runs/run_<YYYYMMDD_HHMM>.parquet` met per doeluur:

| Kolom | Betekenis |
|---|---|
| `run_utc`, `run_type` | tijdstip van de run; `hoofd` of `verversing` |
| `origin` | de dag van de laatste hoofdrun (de dag waarop morgen bekend werd) |
| `model_getraind_utc` | wanneer het gebruikte model getraind is |
| `weer_uitgegeven_utc` | tijdstempel van de gebruikte weersverwachting |
| `time_utc`, `horizon_uren_run` | doeluur en afstand in uren vanaf het runmoment |
| `p10`, `p50`, `p90`, `p10_kal`, `p90_kal`, `bekend` | voorspelling (bekende uren ongewijzigd, `bekend = true`) |
| `laadblok_start`, `wasblok_start` | het geadviseerde goedkoopste blok per dag met de standaardinstellingen |

Bekende uren mogen door een verversing nooit veranderen. Dat is een test.

### Hoe we meten (`epv evalueer-verversingen`, wekelijks, rapport `reports/verversingen.md`)

1. **Gepaard per doeluur.** Voor elk doeluur vergelijken we de fout van de hoofdrun met de fout van elke latere
   verversing voor datzelfde uur, zodra de echte prijs bekend is. Alleen paren waar beide runs bestaan.
2. **Per verversingsslot en per doeldag.** Tabel met rijen 19:00, 01:00, 07:00 en kolommen doeldag D+2 .. D+5
   (gezien vanaf de hoofdrun): MAE hoofdrun, MAE verversing, verschil in EUR/MWh en in procent, pinball P10/P90,
   dekking van het 80%-interval. Het belangrijkste vakje is 07:00 voor D+2: dat is "morgen" voor wie 's ochtends kijkt.
3. **Toets.** Diebold-Mariano op de dagelijkse verliesverschillen per slot en doeldag, eenzijdig, met HAC-correctie
   (dezelfde toets als in de backtest, fase 3). Opeenvolgende dagen zijn niet onafhankelijk.
4. **Praktijkmaat.** Hoe vaak verschuift het geadviseerde laadblok door de verversing, en was het nieuwe blok achteraf
   echt goedkoper dan het oude (in EUR/MWh en in ct/kWh)? Zelfde voor het wasblok. Een verversing die het advies
   nooit verandert is niet nuttig, ook al daalt de MAE iets.
5. **Verklaring.** Uit het weerarchief: hoeveel verandert de windverwachting (zee, land) en de stralingsverwachting
   tussen de opeenvolgende uitgiften voor hetzelfde doeluur, en hoeveel dichter zit de latere uitgifte bij de
   uiteindelijke verwachting van lead 1? Zo zien we of de winst uit het weer komt of toeval is.
6. **Betrouwbaarheid.** Aantal mislukte of te late runs per slot, en de doorlooptijd.

### Beslisregel

Na minstens 6 weken (ongeveer 40 dagen met volledige paren):

- Een slot blijft als de MAE voor de eerstvolgende voorspelde dag minstens 3% lager is met DM-toets p < 0,10, **of**
  als het advies in minstens 10% van de dagen verschuift naar een blok dat achteraf goedkoper was.
- Anders gaat het slot eruit. Hoofdrun om 13:15 blijft altijd.
- Uitkomst en cijfers komen in `DECISIONS.md` (besluit 33 wordt dan "besloten") en in de README onder beperkingen.

### Inhaalruns (besluit 50)

Wordt er een dag niet gedraaid, dan rekent de eerstvolgende hoofdrun de gemiste voorspelmomenten alsnog uit met de
weersverwachting zoals die toen was (previous runs), precies zoals de backtest, en archiveert die als `inhaal`. De
historie voor kalibratie en scores heeft daardoor geen gaten. Inhaalruns hebben geen verversingen en tellen in deze
evaluatie niet mee.

### Wat de site toont

Tijdstip van de laatste run en of het een hoofdrun of verversing was. In de uitleg: "Prijzen voor morgen worden
rond 13:00 bekend. Daarna werken we de verwachting een paar keer per dag bij met het nieuwste weer."

## Belangrijkste risico's

- Previous-runs weerdata begint maart 2024: de eerlijke backtest dekt dus ca. sept 2024 t/m nu (na 180 dagen
  trainingsvenster). Prijzen van voor maart 2024 gebruiken we niet voor het hoofdmodel. Zie DECISIONS.md.
- GitHub Actions cron loopt in UTC en kan 10-30 min laat zijn. Oplossing: twee runs plannen, script controleert
  of morgen al volledig bekend is en slaat anders over.
- Energy-Charts geeft geen garanties op beschikbaarheid. ENTSO-E is de fallback, alleen met token.
