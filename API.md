# API

De site publiceert dezelfde gegevens die de pagina zelf gebruikt als statische JSON. Er is geen server, geen sleutel en
geen limiet anders dan die van de hosting. Lokaal staat alles onder `site/`; online onder de domeinnaam van de site.

| Pad | Inhoud | Ververst |
|---|---|---|
| `/api/v1/voorspelling.json` | de actuele voorspelling (uren, kwartieren, dagen, scores) | elke run (hoofdrun rond 13:15, verversingen) |
| `/data/forecast.json` | identiek; dit leest de pagina zelf | idem |
| `/data/leveranciers.json` | leveranciers met een dynamisch contract en hun inkoopvergoeding | elke run, bron `data/leveranciers.yaml` |

Versie `v1` verandert niet meer van betekenis: velden kunnen erbij komen, bestaande velden veranderen niet van naam,
eenheid of betekenis. Een wijziging die dat wel doet krijgt `/api/v2/`.

## `/api/v1/voorspelling.json`

```json
{
  "gegenereerd_utc": "2026-11-02T12:20:33Z",
  "run_type": "hoofd",
  "voorspelmoment": "2026-11-02",
  "prijzen_bekend_tot": "2026-11-03",
  "model": {"methode": "lightgbm_d2", "getraind_tot": "2026-11-02", "venster_dagen": 365},
  "weer_uitgegeven_utc": "2026-11-02T12:18:05Z",
  "biedzone": "NL",
  "eenheid": "EUR/MWh",
  "uren": [{"tijd": "2026-11-02T00:00:00+01:00", "p10": 243.0, "p50": 243.0, "p90": 243.0, "bekend": true}],
  "kwartieren": [{"tijd": "2026-11-02T00:15:00+01:00", "prijs": 251.04}],
  "dagen": [{"datum": "2026-11-04", "horizon_dag": 2, "betrouwbaarheid": "hoog", "verwachte_afwijking_ct": 1.9}],
  "scores": {"periode_dagen": 30, "mae_dag2": 19.1, "dekking80_dag2": 0.78, "n_dagen_dag2": 30},
  "bronnen": "Prijzen: Energy-Charts (Fraunhofer ISE), data Bundesnetzagentur | SMARD.de, CC BY 4.0. Weer: Open-Meteo, CC BY 4.0."
}
```

| Veld | Betekenis |
|---|---|
| `gegenereerd_utc` | moment van de run, UTC |
| `run_type` | `hoofd` (dagelijkse run met hertraining), `verversing` (alleen nieuw weer) of `inhaal` (achteraf uitgerekende gemiste dag) |
| `voorspelmoment` | de dag waarop de laatst bekende day-ahead dag bekend werd; horizon 2 is twee dagen na deze dag |
| `prijzen_bekend_tot` | laatste lokale dag waarvan alle uurprijzen vaststaan; is dit vandaag, dan zijn de prijzen voor morgen nog niet binnen |
| `model` | gebruikte methode, trainingsdag en trainingsvenster |
| `weer_uitgegeven_utc` | uitgiftemoment van de gebruikte weersverwachting |
| `eenheid` | prijzen in EUR/MWh, kale beursprijs zonder btw, belasting of inkoopvergoeding; delen door 10 geeft ct/kWh |
| `uren[]` | per uur, lokale tijd met offset (zomertijd-dagen hebben 23 of 25 uren). `p50` is de verwachting, `p10` en `p90` de gekalibreerde onder- en bovengrens van het 80%-interval. Bij `bekend: true` zijn alle drie de echte prijs |
| `kwartieren[]` | alleen voor bekende dagen: de kwartierprijzen van de beurs |
| `dagen[]` | per dag: `horizon_dag` (0 = de dag van het voorspelmoment), `betrouwbaarheid` (`bekend`, `hoog`, `redelijk`, `laag`), `verwachte_afwijking_ct` (de gemiddelde afwijking van het model op die horizon over de laatste 30 dagen, in ct/kWh), `dagsoort` (`werkdag`, `schoolvakantie`, `brugdag`, `weekend`, `feestdag`) en `feestdag` (naam van de feestdag, anders `null`) |
| `feestdag_effect` | hoeveel procent de daggemiddelde beursprijs op feestdagen afweek van de werkdagen eromheen, over de laatste twee jaar: `pct_tov_werkdag` (negatief = goedkoper), `aantal_feestdagen`, `vanaf`, `tot` |
| `scores` | per horizon over de laatste 30 voorspelmomenten met bekende uitkomst: `mae_dagK` (EUR/MWh), `dekking80_dagK` (aandeel uren binnen het interval, doel 0,80) en `n_dagen_dagK` |

De betrouwbaarheid is relatief: `hoog` betekent dat het model de laatste 30 dagen duidelijk beter was dan een naïef
uurprofiel, niet dat de fout klein is. Kijk voor de fout zelf naar `verwachte_afwijking_ct` of `scores`.

## `/data/leveranciers.json`

```json
{"peildatum_lijst": "2026-11-01", "bron_register": "https://www.acm.nl/...",
 "leveranciers": [{"naam": "Frank Energie", "inkoopvergoeding_ct_kwh_excl_btw": 1.49, "vaste_kosten_maand_eur_incl_btw": 5.99,
                   "status": "bevestigd_tariefpagina", "peildatum": "2026-11-01", "bron_url": "https://..."}]}
```

`status` is `bevestigd_tariefpagina`, `alleen_vergelijker` of `niet_gepubliceerd`. Bedragen kunnen `null` zijn.

## Gebruik en voorwaarden

- De gegevens zijn afgeleid van Energy-Charts en Open-Meteo (beide CC BY 4.0) en worden onder dezelfde licentie
  doorgegeven: vrij te gebruiken, met vermelding van "stroomprijsvoorspeller" en de bronnen.
- Het is een hulpmiddel, geen garantie: een inschatting op basis van openbare gegevens en een statistisch model, geen
  advies. De werkelijke prijzen kunnen afwijken; gebruik is op eigen risico en de maker is niet aansprakelijk voor
  beslissingen die op deze cijfers worden gebaseerd. De leverancier bepaalt wat een huishouden betaalt.
- Haal de JSON niet vaker op dan nodig; de inhoud verandert hooguit enkele keren per dag. `gegenereerd_utc` zegt of er
  iets nieuws is.
- Geen persoonsgegevens, geen cookies, geen tracking.
