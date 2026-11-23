# Evaluatie van de verversingsruns

Gemaakt op 2026-11-23 07:00. Archief: 11 hoofdruns, 28 verversingen, 19 inhaalruns. Meetplan en beslisregel: PLAN.md, sectie "Evaluatie van de verversingsruns" (besluit 33).

## 1. Fout per verversingsslot en doeldag

Gepaard per doeluur met de hoofdrun van hetzelfde voorspelmoment; alleen uren waarvan de prijs inmiddels bekend is. `verschil` = MAE verversing min MAE hoofdrun (negatief = verversing beter). Diebold-Mariano eenzijdig (verversing beter), Newey-West-correctie, vanaf 10 dagen.

| slot | dag | n_dagen | n_uren | mae_hoofd | mae_verversing | verschil | verschil_pct | pinball_hoofd | pinball_verversing | dekking_hoofd | dekking_verversing | dm | p |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01:00 | 2 | 4 | 96 | 20.10 | 20.94 | 0.84 | +4.2 | 6.72 | 6.50 | 0.948 | 0.917 |  |  |
| 01:00 | 3 | 4 | 96 | 11.91 | 13.47 | 1.56 | +13.1 | 9.59 | 9.53 | 1.000 | 1.000 |  |  |
| 01:00 | 4 | 3 | 72 | 11.71 | 14.81 | 3.10 | +26.4 | 9.38 | 9.35 | 1.000 | 1.000 |  |  |
| 01:00 | 5 | 3 | 72 | 14.67 | 13.93 | -0.75 | -5.1 | 11.53 | 11.51 | 1.000 | 1.000 |  |  |
| 01:00 | 6 | 2 | 48 | 14.48 | 16.36 | 1.88 | +13.0 | 12.40 | 12.17 | 1.000 | 1.000 |  |  |
| 01:00 | 7 | 1 | 24 | 22.06 | 30.79 | 8.73 | +39.6 | 13.34 | 13.25 | 1.000 | 1.000 |  |  |
| 07:00 | 2 | 3 | 72 | 23.40 | 25.48 | 2.08 | +8.9 | 6.95 | 6.66 | 0.931 | 0.875 |  |  |
| 07:00 | 3 | 3 | 72 | 9.86 | 11.45 | 1.59 | +16.1 | 9.23 | 9.29 | 1.000 | 1.000 |  |  |
| 07:00 | 4 | 3 | 72 | 16.38 | 14.79 | -1.58 | -9.7 | 9.57 | 9.41 | 1.000 | 1.000 |  |  |
| 07:00 | 5 | 3 | 72 | 15.90 | 18.80 | 2.90 | +18.2 | 11.05 | 11.27 | 1.000 | 1.000 |  |  |
| 07:00 | 6 | 3 | 72 | 15.43 | 14.18 | -1.25 | -8.1 | 12.16 | 11.99 | 1.000 | 1.000 |  |  |
| 07:00 | 7 | 2 | 48 | 18.77 | 21.65 | 2.88 | +15.4 | 12.74 | 13.00 | 1.000 | 1.000 |  |  |
| 19:00 | 2 | 5 | 120 | 18.41 | 19.03 | 0.62 | +3.4 | 6.41 | 6.23 | 0.958 | 0.950 |  |  |
| 19:00 | 3 | 4 | 96 | 11.91 | 15.02 | 3.11 | +26.1 | 9.83 | 9.96 | 1.000 | 1.000 |  |  |
| 19:00 | 4 | 3 | 72 | 17.31 | 15.86 | -1.45 | -8.4 | 9.80 | 9.70 | 1.000 | 1.000 |  |  |
| 19:00 | 5 | 3 | 72 | 19.02 | 16.45 | -2.57 | -13.5 | 12.06 | 12.20 | 1.000 | 1.000 |  |  |
| 19:00 | 6 | 2 | 48 | 15.61 | 16.23 | 0.62 | +4.0 | 12.73 | 12.84 | 1.000 | 1.000 |  |  |
| 19:00 | 7 | 1 | 24 | 15.48 | 15.60 | 0.12 | +0.8 | 12.14 | 12.21 | 1.000 | 1.000 |  |  |

## 2. Verschuift het advies?

Per doeldag: verschoof het goedkoopste laadblok (3 uur, P50) door de verversing, en was het nieuwe blok achteraf echt goedkoper? `winst_gem` in EUR/MWh (positief = verversing koos beter).

| slot | dag | n_dagen | verschoven | verschoven_en_goedkoper | winst_gem | meerkosten_hoofd | meerkosten_verversing |
|---|---|---|---|---|---|---|---|
| 01:00 | 2 | 4 | 75% | 25% | -6.58 | 5.65 | 12.23 |
| 01:00 | 3 | 4 | 25% | 0% | -0.17 | 6.32 | 6.49 |
| 01:00 | 4 | 3 | 67% | 67% | 0.98 | 7.14 | 6.16 |
| 01:00 | 5 | 3 | 0% | 0% | 0.00 | 6.43 | 6.43 |
| 01:00 | 6 | 2 | 50% | 0% | -9.68 | 0.26 | 9.94 |
| 01:00 | 7 | 1 | 100% | 0% | -0.28 | 0.00 | 0.28 |
| 07:00 | 2 | 3 | 67% | 33% | -7.55 | 6.48 | 14.04 |
| 07:00 | 3 | 3 | 67% | 67% | 3.12 | 6.71 | 3.59 |
| 07:00 | 4 | 3 | 33% | 33% | 0.80 | 6.97 | 6.16 |
| 07:00 | 5 | 3 | 33% | 33% | 3.13 | 12.07 | 8.94 |
| 07:00 | 6 | 3 | 67% | 0% | -6.54 | 2.12 | 8.66 |
| 07:00 | 7 | 2 | 0% | 0% | 0.00 | 0.54 | 0.54 |
| 19:00 | 2 | 5 | 60% | 20% | 0.78 | 5.63 | 4.85 |
| 19:00 | 3 | 4 | 25% | 0% | -0.06 | 5.81 | 5.87 |
| 19:00 | 4 | 3 | 0% | 0% | 0.00 | 3.47 | 3.47 |
| 19:00 | 5 | 3 | 0% | 0% | 0.00 | 8.77 | 8.77 |
| 19:00 | 6 | 2 | 0% | 0% | 0.00 | 2.91 | 2.91 |
| 19:00 | 7 | 1 | 0% | 0% | 0.00 | 1.07 | 1.07 |

## 3. Betrouwbaarheid van de runs

| slot | runs | gelukt | duur_gem_s |
|---|---|---|---|
| 01:00 | 14 | 14 | 366 |
| 07:00 | 4 | 4 | 375 |
| 19:00 | 10 | 10 | 200 |
| hoofd | 11 | 11 | 182 |
| inhaal | 19 | 19 | 0 |
| middag overgeslagen | 1 | 1 | 0 |

## 4. Oordeel volgens de beslisregel

- 01:00: nog 36 dagen te gaan voor de beslisregel (4 van 40); tussenstand MAE +4.2% op dag 2.
- 07:00: nog 37 dagen te gaan voor de beslisregel (3 van 40); tussenstand MAE +8.9% op dag 2.
- 19:00: nog 35 dagen te gaan voor de beslisregel (5 van 40); tussenstand MAE +3.4% op dag 2.

Nog niet gemeten: de verandering in de weersverwachting tussen de uitgiften (punt 5 van het meetplan). Dat komt zodra er genoeg verversingen zijn om een verband te kunnen zien.
