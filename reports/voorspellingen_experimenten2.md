# Methodenvergelijking (rolling-origin backtest)

Voorspelmomenten: 2024-08-29 t/m 2026-10-23 (786 dagen), elke dag om 13:00 lokaal. Trainingsvenster 180 dagen, hertrainen elke 7 dagen, conformal-kalibratie op 30 dagen.

Fouten in EUR/MWh. `dekking80` = aandeel werkelijke prijzen binnen P10-P90 (doel 0,80). Kolommen met `_kal` zijn na conformal-correctie.


## Dag 2 vooruit

| methode | n | MAE | RMSE | pinball P50 | pinball P10 | pinball P90 | dekking80 | breedte80 | dekking80 kal | breedte80 kal |
|---|---|---|---|---|---|---|---|---|---|---|
| lightgbm_w365_hg | 18865 | 17.00 | 29.85 | 8.50 | 4.22 | 5.30 | 0.589 | 36.9 | 0.793 | 54.4 |
| lightgbm_w730 | 18865 | 19.24 | 32.85 | 9.62 | 4.49 | 5.42 | 0.671 | 46.7 | 0.792 | 60.0 |


## Dag 3 vooruit

| methode | n | MAE | RMSE | pinball P50 | pinball P10 | pinball P90 | dekking80 | breedte80 | dekking80 kal | breedte80 kal |
|---|---|---|---|---|---|---|---|---|---|---|
| lightgbm_w730 | 18865 | 20.43 | 34.08 | 10.22 | 4.77 | 5.84 | 0.646 | 46.6 | 0.791 | 63.4 |
| lightgbm_w365_hg | 18865 | 21.07 | 35.24 | 10.53 | 5.06 | 6.04 | 0.617 | 45.9 | 0.793 | 65.1 |


## Dag 4 vooruit

| methode | n | MAE | RMSE | pinball P50 | pinball P10 | pinball P90 | dekking80 | breedte80 | dekking80 kal | breedte80 kal |
|---|---|---|---|---|---|---|---|---|---|---|
| lightgbm_w730 | 18865 | 21.38 | 35.35 | 10.69 | 4.97 | 6.26 | 0.630 | 47.1 | 0.791 | 66.2 |
| lightgbm_w365_hg | 18865 | 21.95 | 36.17 | 10.97 | 5.24 | 6.47 | 0.603 | 46.0 | 0.790 | 67.9 |


## Dag 5 vooruit

| methode | n | MAE | RMSE | pinball P50 | pinball P10 | pinball P90 | dekking80 | breedte80 | dekking80 kal | breedte80 kal |
|---|---|---|---|---|---|---|---|---|---|---|
| lightgbm_w730 | 18865 | 22.65 | 36.79 | 11.33 | 5.32 | 6.81 | 0.612 | 47.7 | 0.790 | 69.6 |
| lightgbm_w365_hg | 18865 | 23.02 | 37.40 | 11.51 | 5.61 | 6.93 | 0.587 | 46.4 | 0.791 | 70.9 |


## Dag 6 vooruit

| methode | n | MAE | RMSE | pinball P50 | pinball P10 | pinball P90 | dekking80 | breedte80 | dekking80 kal | breedte80 kal |
|---|---|---|---|---|---|---|---|---|---|---|
| lightgbm_w730 | 18865 | 24.68 | 39.18 | 12.34 | 6.02 | 7.45 | 0.574 | 47.3 | 0.786 | 74.0 |
| lightgbm_w365_hg | 18865 | 24.94 | 39.72 | 12.47 | 6.26 | 7.73 | 0.557 | 46.4 | 0.782 | 75.3 |


## Dag 7 vooruit

| methode | n | MAE | RMSE | pinball P50 | pinball P10 | pinball P90 | dekking80 | breedte80 | dekking80 kal | breedte80 kal |
|---|---|---|---|---|---|---|---|---|---|---|
| lightgbm_w730 | 18865 | 25.69 | 40.04 | 12.85 | 6.34 | 7.82 | 0.552 | 47.6 | 0.782 | 76.8 |
| lightgbm_w365_hg | 18865 | 26.02 | 40.58 | 13.01 | 6.56 | 8.04 | 0.539 | 46.5 | 0.781 | 77.7 |


## Beste methode per horizon (op MAE)

| dag | methode | MAE |
|---|---|---|
| 2 | lightgbm_w365_hg | 17.00 |
| 3 | lightgbm_w730 | 20.43 |
| 4 | lightgbm_w730 | 21.38 |
| 5 | lightgbm_w730 | 22.65 |
| 6 | lightgbm_w730 | 24.68 |
| 7 | lightgbm_w730 | 25.69 |
