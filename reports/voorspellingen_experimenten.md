# Methodenvergelijking (rolling-origin backtest)

Voorspelmomenten: 2024-08-29 t/m 2026-10-23 (786 dagen), elke dag om 13:00 lokaal. Trainingsvenster 180 dagen, hertrainen elke 7 dagen, conformal-kalibratie op 30 dagen.

Fouten in EUR/MWh. `dekking80` = aandeel werkelijke prijzen binnen P10-P90 (doel 0,80). Kolommen met `_kal` zijn na conformal-correctie.


## Dag 2 vooruit

| methode | n | MAE | RMSE | pinball P50 | pinball P10 | pinball P90 | dekking80 | breedte80 | dekking80 kal | breedte80 kal |
|---|---|---|---|---|---|---|---|---|---|---|
| lightgbm_hg | 18865 | 17.63 | 30.66 | 8.82 | 4.61 | 5.46 | 0.578 | 38.6 | 0.793 | 56.8 |
| lightgbm_w365 | 18865 | 19.39 | 33.12 | 9.69 | 4.62 | 5.49 | 0.643 | 43.9 | 0.789 | 59.2 |
| lightgbm_ens | 18865 | 20.00 | 34.33 | 10.00 | 4.99 | 5.57 | 0.611 | 42.3 | 0.789 | 60.1 |
| lightgbm | 18865 | 20.71 | 34.94 | 10.36 | 5.37 | 5.90 | 0.585 | 42.4 | 0.790 | 62.8 |
| lightgbm_w90 | 18865 | 21.95 | 37.46 | 10.98 | 5.73 | 6.19 | 0.546 | 40.5 | 0.789 | 64.6 |


## Dag 3 vooruit

| methode | n | MAE | RMSE | pinball P50 | pinball P10 | pinball P90 | dekking80 | breedte80 | dekking80 kal | breedte80 kal |
|---|---|---|---|---|---|---|---|---|---|---|
| lightgbm_w365 | 18865 | 20.52 | 34.26 | 10.26 | 4.89 | 5.91 | 0.619 | 44.1 | 0.791 | 63.0 |
| lightgbm_ens | 18865 | 21.09 | 35.52 | 10.55 | 5.42 | 5.98 | 0.591 | 42.4 | 0.790 | 63.9 |
| lightgbm | 18865 | 21.85 | 36.19 | 10.93 | 5.87 | 6.26 | 0.566 | 42.5 | 0.787 | 66.4 |
| lightgbm_hg | 18865 | 22.07 | 36.30 | 11.04 | 6.00 | 6.36 | 0.572 | 44.4 | 0.790 | 68.5 |
| lightgbm_w90 | 18865 | 22.98 | 38.61 | 11.49 | 6.24 | 6.66 | 0.529 | 40.8 | 0.785 | 68.7 |


## Dag 4 vooruit

| methode | n | MAE | RMSE | pinball P50 | pinball P10 | pinball P90 | dekking80 | breedte80 | dekking80 kal | breedte80 kal |
|---|---|---|---|---|---|---|---|---|---|---|
| lightgbm_w365 | 18865 | 21.55 | 35.50 | 10.77 | 5.13 | 6.38 | 0.601 | 44.3 | 0.793 | 66.1 |
| lightgbm_ens | 18865 | 21.96 | 36.54 | 10.98 | 5.73 | 6.39 | 0.577 | 42.7 | 0.787 | 66.6 |
| lightgbm | 18865 | 22.71 | 37.20 | 11.35 | 6.28 | 6.65 | 0.552 | 42.7 | 0.787 | 69.5 |
| lightgbm_hg | 18865 | 22.86 | 37.18 | 11.43 | 6.32 | 6.74 | 0.561 | 44.6 | 0.785 | 71.2 |
| lightgbm_w90 | 18865 | 23.71 | 39.47 | 11.86 | 6.56 | 7.03 | 0.517 | 41.2 | 0.786 | 71.5 |


## Dag 5 vooruit

| methode | n | MAE | RMSE | pinball P50 | pinball P10 | pinball P90 | dekking80 | breedte80 | dekking80 kal | breedte80 kal |
|---|---|---|---|---|---|---|---|---|---|---|
| lightgbm_w365 | 18865 | 22.72 | 36.95 | 11.36 | 5.51 | 6.88 | 0.583 | 44.8 | 0.787 | 69.3 |
| lightgbm_ens | 18865 | 23.21 | 38.00 | 11.60 | 6.08 | 6.90 | 0.562 | 43.3 | 0.785 | 69.9 |
| lightgbm | 18865 | 24.04 | 38.79 | 12.02 | 6.59 | 7.17 | 0.538 | 43.3 | 0.785 | 72.5 |
| lightgbm_hg | 18865 | 24.08 | 38.61 | 12.04 | 6.58 | 7.22 | 0.550 | 45.0 | 0.784 | 73.8 |
| lightgbm_w90 | 18865 | 24.98 | 40.80 | 12.49 | 6.92 | 7.52 | 0.504 | 41.7 | 0.786 | 74.7 |


## Dag 6 vooruit

| methode | n | MAE | RMSE | pinball P50 | pinball P10 | pinball P90 | dekking80 | breedte80 | dekking80 kal | breedte80 kal |
|---|---|---|---|---|---|---|---|---|---|---|
| lightgbm_w365 | 18865 | 24.82 | 39.44 | 12.41 | 6.25 | 7.62 | 0.547 | 44.5 | 0.786 | 74.1 |
| lightgbm_ens | 18865 | 25.12 | 40.21 | 12.56 | 6.75 | 7.63 | 0.530 | 43.3 | 0.783 | 74.7 |
| lightgbm | 18865 | 25.86 | 40.92 | 12.93 | 7.26 | 7.87 | 0.516 | 43.7 | 0.782 | 77.3 |
| lightgbm_hg | 18865 | 25.93 | 40.93 | 12.97 | 7.26 | 7.94 | 0.521 | 45.1 | 0.783 | 78.5 |
| lightgbm_w90 | 18865 | 26.74 | 42.70 | 13.37 | 7.52 | 8.21 | 0.482 | 41.6 | 0.784 | 78.6 |


## Dag 7 vooruit

| methode | n | MAE | RMSE | pinball P50 | pinball P10 | pinball P90 | dekking80 | breedte80 | dekking80 kal | breedte80 kal |
|---|---|---|---|---|---|---|---|---|---|---|
| lightgbm_w365 | 18865 | 25.86 | 40.31 | 12.93 | 6.53 | 7.97 | 0.527 | 45.0 | 0.784 | 76.2 |
| lightgbm_ens | 18865 | 26.23 | 41.06 | 13.11 | 7.04 | 8.01 | 0.507 | 43.4 | 0.776 | 76.4 |
| lightgbm | 18865 | 26.97 | 41.96 | 13.49 | 7.49 | 8.26 | 0.492 | 43.6 | 0.777 | 78.8 |
| lightgbm_hg | 18865 | 27.06 | 41.98 | 13.53 | 7.55 | 8.24 | 0.505 | 45.0 | 0.781 | 79.9 |
| lightgbm_w90 | 18865 | 27.78 | 43.29 | 13.89 | 7.91 | 8.58 | 0.464 | 41.5 | 0.779 | 80.5 |


## Beste methode per horizon (op MAE)

| dag | methode | MAE |
|---|---|---|
| 2 | lightgbm_hg | 17.63 |
| 3 | lightgbm_w365 | 20.52 |
| 4 | lightgbm_w365 | 21.55 |
| 5 | lightgbm_w365 | 22.72 |
| 6 | lightgbm_w365 | 24.82 |
| 7 | lightgbm_w365 | 25.86 |
