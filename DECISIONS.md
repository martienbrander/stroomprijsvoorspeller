# DECISIONS — aannames en keuzes

Doorlopend genummerd. Status: **aanname** (door mij gemaakt, kan worden teruggedraaid), **besloten** (door opdrachtgever
bevestigd) of **open** (keuze ligt bij opdrachtgever).

## Fase 0: planning (2026-11-01)

| # | Onderwerp | Keuze | Reden | Status |
|---|---|---|---|---|
| 1 | Projectmap en naam | `C:\ClaudeCode\stroomprijsvoorspeller`, package `stroomprijsvoorspeller` | Gekozen door opdrachtgever (eerst energieprijsvoorspeller, op 2026-11-01 gewijzigd: het gaat om stroom, niet om gas). | besloten |
| 2 | Python en packaging | Python 3.12 (aanwezig), `pyproject.toml`, installeren met `pip install -e .`; `uv` niet vereist | `uv` staat niet op deze machine. pyproject werkt met beide. | aanname |
| 3 | Prijsbron | Energy-Charts `price?bzn=NL`, vanaf 2022-11-01, geen sleutel. Licentie CC BY 4.0 (bron: Bundesnetzagentur/SMARD via Fraunhofer ISE). Bronvermelding op de site. | Gecontroleerd: 3 jaar levert 28.543 punten in één call, uur t/m sept 2025, kwartier daarna. | aanname |
| 4 | Kwartierprijzen | Bewaard in `prices_nl_quarter.parquet`; model werkt op uurgemiddelden in `prices_nl_hour.parquet` | Conform opdracht. Uurgemiddelde = gemiddelde van de 4 kwartieren. | aanname |
| 5 | ENTSO-E | Alleen als fallback, alleen actief met `ENTSOE_TOKEN` in `.env` | Conform opdracht. | aanname |
| 6 | Weerbron voor trainen/backtest | Open-Meteo **Previous Runs API** met `<var>_previous_dayN` (N = 1..5), model `best_match` | Dit is de verwachting zoals die N dagen eerder bestond. Dat is lekkage-vrij voor horizon dag N. De "Historical Forecast API" geeft alleen de kortste lead-time en is dus te optimistisch voor dag 2-5. | aanname |
| 7 | Startdatum trainingsdata | ca. 2024-03-01 | Previous-runs data bestaat pas vanaf dan (gecontroleerd: 2024-02-15 leeg, 2024-03-01 gevuld). Oudere prijzen (2022-2024) halen we wel op voor baselines, grafieken en latere experimenten, maar niet voor het hoofdmodel. | aanname |
| 8 | Lead-time toewijzing | Backtest op dag D om 13:00 voorspelt doeluur op dag D+k (k = 2..5) met weerfeatures `previous_day{k}` | De run van dag D, k dagen voor het doeluur. Komt overeen met wat de dagelijkse run om 13:30 uit de Forecast API krijgt. | aanname |
| 9 | Weervariabelen | wind_speed_100m, shortwave_radiation, cloud_cover, temperature_2m, uurlijks | Conform opdracht. | aanname |
| 10 | Weerpunten | 14 punten, gekozen op opgesteld windvermogen (CBS 70960ned per provincie, RVO routekaart wind op zee): 5 zee incl. Duitse Bocht, 7 land-wind, 2 zon/vraag. Zie tabel in PLAN.md. | Opdrachtgever wil ook landpunten, gebaseerd op waar de windstroom feitelijk vandaan komt. Flevoland (2,2 GW) en Groningen (0,9 GW) zijn de grootste landprovincies. | besloten |
| 11 | Gasprijs | Weggelaten, definitief | Opdrachtgever wil geen gasprijs in de tool: het doel is juist van het gas af. Daarnaast is er geen betrouwbare gratis TTF-bron. Het recente prijsniveau (laatste 7 dagen) vangt het brandstofregime indirect op. | besloten |
| 12 | Tijdzones | Intern UTC; dag-grenzen voor "dag", stoplicht en goedkoopste blok in Europe/Amsterdam | Zomertijd-dagen hebben 23 of 25 uur; dat moet expliciet goed gaan. Tests hierop. | aanname |
| 13 | Dagelijkse run | GitHub Actions cron twee keer: 12:20 en 13:20 UTC. Script controleert of alle uren van morgen bekend zijn; zo niet, stopt het zonder te publiceren. | EPEX publiceert rond 12:45 CET. Cron is UTC en vaak 10-30 min laat. Twee pogingen + een check is robuuster dan één moment. | aanname |
| 14 | Site-techniek | Plain HTML/CSS/JS, grafiek op `<canvas>` zonder externe library, geen fonts of scripts van derden | Geen tracking, geen afhankelijkheden, laadt snel op mobiel. | aanname |
| 15 | Hosting | Voorlopig alles lokaal op deze pc. Lokale git-repo, lokale dagelijkse run (Windows Taakplanner). Online zetten (GitHub Pages) komt later. | Wens opdrachtgever. De code wordt wel zo gebouwd dat de Actions-workflows er later zonder herbouw bij kunnen. | besloten |
| 16 | Model | LightGBM, drie losse modellen voor q=0.10/0.50/0.90, één model voor alle horizonten met `horizon_uren` als feature, rolling venster 180 dagen | Conform opdracht. Per-horizon modellen zijn een later experiment. | aanname |
| 17 | Toegankelijkheid stoplicht | Kleur + icoon + tekstlabel ("goedkoop", "gemiddeld", "duur") | Niet alleen kleur als drager. | aanname |

| 18 | Evaluatie als econometrische pseudo-out-of-sample test | Rolling-origin backtest: elke dag D om 13:00 wordt het model geschat op data t/m D+1 en voorspelt D+2..D+5; alleen informatie die toen bekend was. In fase 2 vergelijk ik meerdere schattingsmethoden op dezelfde backtest: baselines, lineaire kwantielregressie (LASSO-stijl, standaard in de EPF-literatuur), LightGBM-kwantiel, en een eenvoudige combinatie. De beste wint. | Opdrachtgever: historische voorspellingen op historische data, zoek de beste schattingsmethode. | besloten |
| 19 | Downloads | Pip-packages en publieke data (Energy-Charts, Open-Meteo, CBS) worden gedownload zonder apart te vragen; andere downloads meld ik eerst. | Toestemming opdrachtgever 2026-11-01. | besloten |
| 20 | Mappenstructuur toekomstvast | `src/`-layout met package `stroomprijsvoorspeller`, bronnen als losse modules met gemeenschappelijke interface, één `config.yaml`, data buiten git, `site/` los van Python. Nieuwe bron = één bestand in `sources/`, nieuw model = één bestand in `model/`. | Wens opdrachtgever. | aanname |
| 21 | Ontwerp site | In fase 4 maak ik drie uitgewerkte ontwerpvarianten (HTML, klikbaar, met echte data) en legt die voor; opdrachtgever kiest. Richting: fris, rustig, veel wit, één duidelijke grafiek, geen banners of reclame-look. Gaslicht.com is het tegenvoorbeeld (druk, lelijk). | Wens opdrachtgever 2026-11-01. | besloten |
| 22 | Weergave per horizon | Detail neemt af met de horizon: morgen (bekend) per uur of kwartier, dag 2-3 per uur met onzekerheidsband, dag 4-5 als blokken per dagdeel (nacht, ochtend, middag, avond) met kleur en label. Zo belooft de site niet meer precisie dan het model heeft. | Voorstel opdrachtgever 2026-11-01. Wordt in fase 4 in alle ontwerpvarianten verwerkt. | besloten |

## Open vragen voor opdrachtgever

Geen op dit moment.
