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
| 2 | Baselines + LightGBM-kwantielmodel + kalibratie | `stroomprijsvoorspeller/model/`, `python -m stroomprijsvoorspeller train` |
| 3 | Backtest met dagelijkse 13:00-simulatie | `reports/backtest.md` + png's, tests op lekkage |
| 4 | Dagelijkse run + statische site | `site/` leest `site/data/forecast.json` |
| 5 | README + lokale planner; later GitHub Actions + Pages | eerst alles lokaal op deze pc, pas daarna online |

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
│   │   └── dataset.py         bouwt data/processed uit data/raw
│   ├── model/                 fase 2: baselines, kwantielmodellen, kalibratie, methodenvergelijking
│   ├── evaluation/            fase 3: backtest (13:00-simulatie), metrics, rapport
│   └── publish/               fase 4: forecast.json en scores.json voor de site
│
├── scripts/                   fase 4/5: daily.py, weekly_backtest.py, Windows Taakplanner-registratie
├── tests/                     pytest: tijd, prijzen, kalender, bronnen (zonder netwerk), config
│
├── data/                      niet in git
│   ├── raw/                   prijzen_nl_ruw.parquet, weer_prev_runs_<punt>.parquet, weer_forecast_<punt>.parquet
│   └── processed/             prijzen_nl_uur.parquet, prijzen_nl_kwartier.parquet, basis_uur.parquet, weer_prev_runs.parquet
├── models/                    laatst getrainde modellen (niet in git)
├── reports/                   backtest.md + figures/*.png (wel in git)
├── site/                      fase 4: statische site, plain HTML + JS; site/data/ bevat de gegenereerde JSON
└── .github/workflows/         fase 5 (later, pas als we online gaan)
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

## Belangrijkste risico's

- Previous-runs weerdata begint maart 2024: de eerlijke backtest dekt dus ca. sept 2024 t/m nu (na 180 dagen
  trainingsvenster). Prijzen van voor maart 2024 gebruiken we niet voor het hoofdmodel. Zie DECISIONS.md.
- GitHub Actions cron loopt in UTC en kan 10-30 min laat zijn. Oplossing: twee runs plannen, script controleert
  of morgen al volledig bekend is en slaat anders over.
- Energy-Charts geeft geen garanties op beschikbaarheid. ENTSO-E is de fallback, alleen met token.
