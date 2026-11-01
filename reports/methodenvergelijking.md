# Methodenvergelijking (rolling-origin backtest)

Voorspelmomenten: 2024-08-29 t/m 2026-10-23 (786 dagen), elke dag om 13:00 lokaal. Trainingsvenster 180 dagen, hertrainen elke 7 dagen, conformal-kalibratie op 30 dagen.

Fouten in EUR/MWh. `dekking80` = aandeel werkelijke prijzen binnen P10-P90 (doel 0,80). Kolommen met `_kal` zijn na conformal-correctie.


## Dag 2 vooruit

| methode | n | MAE | RMSE | pinball P50 | pinball P10 | pinball P90 | dekking80 | breedte80 | dekking80 kal | breedte80 kal |
|---|---|---|---|---|---|---|---|---|---|---|
| combinatie | 18865 | 20.59 | 33.16 | 10.29 | 9.50 | 5.10 | 0.746 | 106.2 | 0.794 | 111.7 |
| lightgbm | 18865 | 20.71 | 34.94 | 10.36 | 5.37 | 5.90 | 0.585 | 42.4 | 0.790 | 62.8 |
| lightgbm_asinh | 18865 | 22.03 | 36.50 | 11.02 | 4.78 | 6.12 | 0.617 | 47.1 | 0.792 | 62.8 |
| lineair | 18865 | 24.30 | 37.18 | 12.15 | 15.45 | 5.57 | 0.771 | 170.0 | 0.797 | 172.9 |
| laatste_dag | 18865 | 27.56 | 44.10 | 13.78 | 13.82 | 13.74 | 0.001 | 0.0 | 0.789 | 88.3 |
| profiel_4w | 18865 | 28.37 | 42.80 | 14.18 | 13.64 | 14.73 | 0.000 | 0.0 | 0.790 | 84.9 |
| vorige_week | 18865 | 34.14 | 54.44 | 17.07 | 16.88 | 17.27 | 0.001 | 0.0 | 0.788 | 109.2 |


## Dag 3 vooruit

| methode | n | MAE | RMSE | pinball P50 | pinball P10 | pinball P90 | dekking80 | breedte80 | dekking80 kal | breedte80 kal |
|---|---|---|---|---|---|---|---|---|---|---|
| combinatie | 18865 | 21.73 | 34.94 | 10.87 | 9.26 | 5.48 | 0.724 | 101.0 | 0.792 | 109.5 |
| lightgbm | 18865 | 21.85 | 36.19 | 10.93 | 5.87 | 6.26 | 0.566 | 42.5 | 0.787 | 66.4 |
| lightgbm_asinh | 18865 | 23.55 | 37.92 | 11.77 | 5.26 | 6.57 | 0.593 | 47.2 | 0.793 | 67.2 |
| lineair | 18865 | 25.26 | 39.05 | 12.63 | 14.55 | 5.93 | 0.758 | 159.5 | 0.792 | 164.4 |
| profiel_4w | 18865 | 28.90 | 43.53 | 14.45 | 13.87 | 15.03 | 0.000 | 0.0 | 0.788 | 86.4 |
| vorige_week | 18865 | 34.19 | 54.51 | 17.10 | 16.95 | 17.25 | 0.001 | 0.0 | 0.786 | 109.3 |
| laatste_dag | 18865 | 34.75 | 54.56 | 17.38 | 17.39 | 17.37 | 0.001 | 0.0 | 0.789 | 115.5 |


## Dag 4 vooruit

| methode | n | MAE | RMSE | pinball P50 | pinball P10 | pinball P90 | dekking80 | breedte80 | dekking80 kal | breedte80 kal |
|---|---|---|---|---|---|---|---|---|---|---|
| combinatie | 18865 | 22.63 | 36.14 | 11.32 | 11.23 | 5.80 | 0.698 | 117.7 | 0.791 | 129.3 |
| lightgbm | 18865 | 22.71 | 37.20 | 11.35 | 6.28 | 6.65 | 0.552 | 42.7 | 0.787 | 69.5 |
| lightgbm_asinh | 18865 | 24.50 | 39.02 | 12.25 | 5.43 | 6.91 | 0.582 | 47.8 | 0.790 | 69.1 |
| lineair | 18865 | 26.21 | 40.12 | 13.10 | 18.10 | 6.23 | 0.738 | 192.7 | 0.795 | 200.6 |
| profiel_4w | 18865 | 29.25 | 43.94 | 14.62 | 13.99 | 15.25 | 0.000 | 0.0 | 0.789 | 87.7 |
| vorige_week | 18865 | 34.20 | 54.51 | 17.10 | 16.99 | 17.21 | 0.001 | 0.0 | 0.783 | 109.0 |
| laatste_dag | 18865 | 36.59 | 57.66 | 18.30 | 18.26 | 18.34 | 0.001 | 0.0 | 0.790 | 119.8 |


## Dag 5 vooruit

| methode | n | MAE | RMSE | pinball P50 | pinball P10 | pinball P90 | dekking80 | breedte80 | dekking80 kal | breedte80 kal |
|---|---|---|---|---|---|---|---|---|---|---|
| combinatie | 18865 | 23.85 | 37.42 | 11.92 | 13.49 | 6.19 | 0.674 | 138.2 | 0.790 | 152.4 |
| lightgbm | 18865 | 24.04 | 38.79 | 12.02 | 6.59 | 7.17 | 0.538 | 43.3 | 0.785 | 72.5 |
| lightgbm_asinh | 18865 | 25.90 | 40.48 | 12.95 | 5.77 | 7.37 | 0.571 | 48.8 | 0.791 | 72.3 |
| lineair | 18865 | 27.22 | 41.06 | 13.61 | 22.28 | 6.51 | 0.720 | 233.1 | 0.791 | 243.1 |
| profiel_4w | 18865 | 29.58 | 44.32 | 14.79 | 14.09 | 15.49 | 0.000 | 0.0 | 0.785 | 88.3 |
| vorige_week | 18865 | 34.22 | 54.52 | 17.11 | 16.99 | 17.23 | 0.001 | 0.0 | 0.782 | 108.9 |
| laatste_dag | 18865 | 37.68 | 59.21 | 18.84 | 18.73 | 18.95 | 0.001 | 0.0 | 0.786 | 121.8 |


## Dag 6 vooruit

| methode | n | MAE | RMSE | pinball P50 | pinball P10 | pinball P90 | dekking80 | breedte80 | dekking80 kal | breedte80 kal |
|---|---|---|---|---|---|---|---|---|---|---|
| combinatie | 18865 | 25.70 | 39.52 | 12.85 | 9.68 | 6.78 | 0.648 | 95.5 | 0.787 | 113.6 |
| lightgbm | 18865 | 25.86 | 40.92 | 12.93 | 7.26 | 7.87 | 0.516 | 43.7 | 0.782 | 77.3 |
| lightgbm_asinh | 18865 | 28.06 | 43.07 | 14.03 | 6.40 | 8.14 | 0.538 | 49.1 | 0.786 | 77.8 |
| lineair | 18865 | 28.84 | 42.93 | 14.42 | 13.93 | 6.96 | 0.692 | 147.3 | 0.789 | 160.5 |
| profiel_4w | 18865 | 29.91 | 44.84 | 14.95 | 14.16 | 15.74 | 0.000 | 0.0 | 0.779 | 88.4 |
| vorige_week | 18865 | 34.37 | 54.82 | 17.19 | 17.00 | 17.37 | 0.001 | 0.0 | 0.778 | 108.2 |
| laatste_dag | 18865 | 37.90 | 58.92 | 18.95 | 18.75 | 19.15 | 0.001 | 0.0 | 0.782 | 121.0 |


## Dag 7 vooruit

| methode | n | MAE | RMSE | pinball P50 | pinball P10 | pinball P90 | dekking80 | breedte80 | dekking80 kal | breedte80 kal |
|---|---|---|---|---|---|---|---|---|---|---|
| combinatie | 18865 | 26.68 | 40.43 | 13.34 | 13.52 | 7.05 | 0.632 | 131.1 | 0.783 | 151.4 |
| lightgbm | 18865 | 26.97 | 41.96 | 13.49 | 7.49 | 8.26 | 0.492 | 43.6 | 0.777 | 78.8 |
| lightgbm_asinh | 18865 | 29.12 | 44.31 | 14.56 | 6.65 | 8.52 | 0.522 | 48.7 | 0.782 | 79.6 |
| lineair | 18865 | 29.74 | 43.88 | 14.87 | 21.51 | 7.19 | 0.679 | 218.6 | 0.784 | 233.9 |
| profiel_4w | 18865 | 30.16 | 45.18 | 15.08 | 14.22 | 15.94 | 0.000 | 0.0 | 0.776 | 89.1 |
| vorige_week | 18865 | 34.50 | 55.02 | 17.25 | 17.01 | 17.49 | 0.001 | 0.0 | 0.778 | 108.3 |
| laatste_dag | 18865 | 36.26 | 57.03 | 18.13 | 17.85 | 18.41 | 0.001 | 0.0 | 0.784 | 114.8 |


## Beste methode per horizon (op MAE)

| dag | methode | MAE |
|---|---|---|
| 2 | combinatie | 20.59 |
| 3 | combinatie | 21.73 |
| 4 | combinatie | 22.63 |
| 5 | combinatie | 23.85 |
| 6 | combinatie | 25.70 |
| 7 | combinatie | 26.68 |

## Conclusies fase 2 (handmatig toegevoegd, 2026-11-01; de tabellen hierboven worden door `epv compare` opnieuw gegenereerd)

Testperiode: 786 voorspelmomenten van 29 augustus 2024 tot 23 oktober 2026, elke dag om 13:00, horizon dag 2 t/m 7,
hertrainen elke 7 dagen op een rolling venster van 180 dagen. Alle fouten in EUR/MWh.

**1. LightGBM (zonder transformatie) is het hoofdmodel.** MAE 20,7 op dag 2, oplopend tot 27,0 op dag 7. Het 4-weeks
profiel, de sterkste baseline vanaf dag 3, zit op 28,4 tot 30,2. De relatieve fout (rMAE) t.o.v. het profiel is 0,73 op
dag 2, 0,76 (dag 3), 0,78 (dag 4), 0,81 (dag 5), 0,87 (dag 6) en 0,89 (dag 7). Het model is beter dan het profiel in
elk kwartaal, elk seizoen en elk uur van de dag. De kleinste winst: dag 7 in de winter (rMAE 0,94) en dag 5 in het vierde
kwartaal van 2024 (0,92).

**2. De combinatie en het lineaire model voegen niets toe.** De combinatie (gemiddelde van lineair en LightGBM) is 0,1
EUR/MWh beter op MAE, maar wint maar op 47% van de dagen en heeft een twee keer zo breed interval. Het lineaire
kwantielmodel op asinh-prijzen zit op rMAE 0,86 tot 0,99 en zijn P90 loopt na terugtransformatie op tot onbruikbaar
brede intervallen (170 tot 230 EUR/MWh). LightGBM op asinh is op alle horizonten slechter dan LightGBM op ruwe prijzen.
Deze drie vallen af voor de operationele run; ze blijven beschikbaar in de backtest als vergelijking.

**3. De eigen intervallen van LightGBM zijn te smal; conformal-correctie is noodzakelijk.** Zonder correctie dekt het
P10-P90-interval 58% (dag 2) tot 49% (dag 7) van de werkelijke prijzen in plaats van 80%. Met de conformal-correctie op
een venster van 30 dagen komt de dekking op 78 tot 79% voor alle horizonten en alle methoden. De correctie is fors:
mediaan 9 EUR/MWh op dag 2 tot 15 op dag 7; het gekalibreerde interval is 63 (dag 2) tot 79 (dag 7) EUR/MWh breed.

**4. Baselines.** "Laatst bekende dag" is op dag 2 vrijwel even goed als het profiel (27,6 tegen 28,4), daarna veel
slechter (35 tot 38). "Zelfde uur vorige week" is overal het slechtst (34). Het 4-weeks profiel is de lat voor dag 3+.

**5. Waar het model het moeilijk heeft.**
- Overdag, 10 tot 17 uur: MAE 25 tot 28 en dekking 70 tot 74%, tegen 13 EUR/MWh en 84% 's nachts. De zonnedip met
  negatieve prijzen is het lastigste deel van de dag; precies daar zit ook het goedkoopste blok.
- Oktober 2026: MAE 36 op dag 2 en dekking 63 tot 70%. Het prijsniveau sprong naar 172 EUR/MWh en zowel het model
  (venster 180 dagen) als de kalibratie (venster 30 dagen) lopen achter. Dit is het argument voor een online
  bijgestuurde kalibratie (ACI) in fase 3.
- Kwartierprijzen sinds 1 oktober 2025: MAE iets hoger (21,3 tegen 20,2 op dag 2) bij een hoger prijsniveau; de
  relatieve fout is gelijk. Geen aanwijzing dat de overgang het model heeft gebroken.

**6. Horizon en betrouwbaarheidsindicator.** Dag 6 en 7 zijn gemiddeld nog 11 tot 14% beter dan het profiel, maar in de
winter op dag 7 nog maar 6%. De indeling hoog (dag 2-3, rMAE < 0,80), redelijk (dag 4-5, 0,80 tot 0,85) en laag
(dag 6-7, > 0,85) past bij deze cijfers en wordt in fase 3 definitief geijkt, per seizoen.

**Nog niet gedaan, voor fase 3:** praktijkmaat goedkoopste 3-uursblok, Diebold-Mariano-toets, grafieken, feature-belang,
experiment met horizongroepen en met middelen over trainingsvensters, online kalibratie (ACI), rapport `backtest.md`.
