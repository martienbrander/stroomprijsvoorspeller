# Evaluatie van de verversingsruns

Gemaakt op 2026-11-18 00:08. Archief: 7 hoofdruns, 17 verversingen, 18 inhaalruns. Meetplan en beslisregel: PLAN.md, sectie "Evaluatie van de verversingsruns" (besluit 33).

## 1. Fout per verversingsslot en doeldag

Gepaard per doeluur met de hoofdrun van hetzelfde voorspelmoment; alleen uren waarvan de prijs inmiddels bekend is. `verschil` = MAE verversing min MAE hoofdrun (negatief = verversing beter). Diebold-Mariano eenzijdig (verversing beter), Newey-West-correctie, vanaf 10 dagen.

| slot | dag | n_dagen | n_uren | mae_hoofd | mae_verversing | verschil | verschil_pct | pinball_hoofd | pinball_verversing | dekking_hoofd | dekking_verversing | dm | p |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| 01:00 | 2 | 1 | 24 | 20.05 | 19.21 | -0.84 | -4.2 | 6.98 | 7.28 | 1.000 | 1.000 |  |  |
| 07:00 | 2 | 2 | 48 | 18.27 | 17.74 | -0.53 | -2.9 | 6.29 | 6.51 | 1.000 | 1.000 |  |  |
| 07:00 | 3 | 1 | 24 | 11.27 | 11.27 | 0.00 | +0.0 | 9.00 | 9.00 | 1.000 | 1.000 |  |  |
| 07:00 | 4 | 1 | 24 | 25.45 | 25.45 | 0.00 | +0.0 | 10.07 | 10.07 | 1.000 | 1.000 |  |  |
| 07:00 | 5 | 1 | 24 | 26.10 | 26.10 | 0.00 | +0.0 | 11.50 | 11.50 | 1.000 | 1.000 |  |  |
| 07:00 | 6 | 1 | 24 | 17.33 | 17.33 | 0.00 | +0.0 | 11.68 | 11.68 | 1.000 | 1.000 |  |  |
| 07:00 | 7 | 1 | 24 | 15.48 | 15.48 | 0.00 | +0.0 | 12.14 | 12.14 | 1.000 | 1.000 |  |  |
| 19:00 | 2 | 1 | 24 | 16.48 | 19.33 | 2.84 | +17.3 | 5.60 | 5.67 | 1.000 | 1.000 |  |  |
| 19:00 | 3 | 1 | 24 | 11.27 | 11.68 | 0.41 | +3.6 | 9.00 | 9.35 | 1.000 | 1.000 |  |  |
| 19:00 | 4 | 1 | 24 | 25.45 | 25.32 | -0.13 | -0.5 | 10.07 | 10.06 | 1.000 | 1.000 |  |  |
| 19:00 | 5 | 1 | 24 | 26.10 | 26.16 | 0.06 | +0.2 | 11.50 | 11.52 | 1.000 | 1.000 |  |  |
| 19:00 | 6 | 1 | 24 | 17.33 | 17.46 | 0.13 | +0.7 | 11.68 | 11.66 | 1.000 | 1.000 |  |  |
| 19:00 | 7 | 1 | 24 | 15.48 | 15.60 | 0.12 | +0.8 | 12.14 | 12.21 | 1.000 | 1.000 |  |  |

## 2. Verschuift het advies?

Per doeldag: verschoof het goedkoopste laadblok (3 uur, P50) door de verversing, en was het nieuwe blok achteraf echt goedkoper? `winst_gem` in EUR/MWh (positief = verversing koos beter).

| slot | dag | n_dagen | verschoven | verschoven_en_goedkoper | winst_gem | meerkosten_hoofd | meerkosten_verversing |
|---|---|---|---|---|---|---|---|
| 01:00 | 2 | 1 | 0% | 0% | 0.00 | 2.31 | 2.31 |
| 07:00 | 2 | 2 | 50% | 50% | 1.16 | 5.07 | 3.92 |
| 07:00 | 3 | 1 | 0% | 0% | 0.00 | 4.75 | 4.75 |
| 07:00 | 4 | 1 | 0% | 0% | 0.00 | 0.00 | 0.00 |
| 07:00 | 5 | 1 | 0% | 0% | 0.00 | 16.93 | 16.93 |
| 07:00 | 6 | 1 | 0% | 0% | 0.00 | 5.83 | 5.83 |
| 07:00 | 7 | 1 | 0% | 0% | 0.00 | 1.07 | 1.07 |
| 19:00 | 2 | 1 | 100% | 0% | -3.88 | 7.84 | 11.72 |
| 19:00 | 3 | 1 | 100% | 0% | -0.24 | 4.75 | 4.99 |
| 19:00 | 4 | 1 | 0% | 0% | 0.00 | 0.00 | 0.00 |
| 19:00 | 5 | 1 | 0% | 0% | 0.00 | 16.93 | 16.93 |
| 19:00 | 6 | 1 | 0% | 0% | 0.00 | 5.83 | 5.83 |
| 19:00 | 7 | 1 | 0% | 0% | 0.00 | 1.07 | 1.07 |

## 3. Betrouwbaarheid van de runs

| slot | runs | gelukt | duur_gem_s |
|---|---|---|---|
| 01:00 | 10 | 10 | 97 |
| 07:00 | 3 | 3 | 17 |
| 19:00 | 4 | 4 | 147 |
| hoofd | 7 | 7 | 153 |
| inhaal | 18 | 18 | 0 |
| middag overgeslagen | 1 | 1 | 0 |

## 4. Oordeel volgens de beslisregel

- 01:00: nog 39 dagen te gaan voor de beslisregel (1 van 40); tussenstand MAE -4.2% op dag 2.
- 07:00: nog 38 dagen te gaan voor de beslisregel (2 van 40); tussenstand MAE -2.9% op dag 2.
- 19:00: nog 39 dagen te gaan voor de beslisregel (1 van 40); tussenstand MAE +17.3% op dag 2.

Nog niet gemeten: de verandering in de weersverwachting tussen de uitgiften (punt 5 van het meetplan). Dat komt zodra er genoeg verversingen zijn om een verband te kunnen zien.
