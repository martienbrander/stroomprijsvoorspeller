# Literatuurmemo: schattingsmethoden voor day-ahead stroomprijzen, 2 tot 7 dagen vooruit

Datum: 2026-11-01. Input voor de methodenvergelijking in fase 2 en 3 (zie `PLAN.md` en `DECISIONS.md`, besluit 16 en 18).

## Samenvatting in drie zinnen

De literatuur toont dat een goed afgestelde lasso-regressie (LEAR) op asinh-prijzen moeilijk te verslaan is en dat neurale netten er hooguit enkele procenten MAE bovenop doen. Voor intervallen werkt "puntmodel + conformal of QRA" beter dan men verwacht, maar alleen met online bijsturing, want vaste kalibratie dekt na regimewissels te weinig. De enige gevonden studie over meerdere dagen vooruit (korte testperiode) laat zien dat weersverwachtingen op dag 2 tot 4 10 tot 20% RMSE opleveren en vanaf dag 6 niets meer, dus ons ontwerp (weer per lead, naïeve baselines, DM-toets op een rolling-origin backtest) sluit aan op de beste praktijk.

## 1. Wat het beste werkt voor puntvoorspellingen

- **Overzicht.** Weron (2014) is het standaardoverzicht van EPF. Het pleit voor vergelijking op dezelfde data, met robuuste foutmaten en statistische toetsen.
- **Benchmark.** Lago, Marcjasz, De Schutter en Weron (2021) vergelijken twee modellen op vijf markten (EPEX BE, FR, DE, Nord Pool, PJM). Testperiode: de laatste 104 weken.
  - LEAR: lasso op asinh-prijzen. 247 kandidaat-inputs: prijzen van d-1, d-2, d-3 en d-7, twee exogene verwachtingsreeksen en weekdagdummy's. Elke dag opnieuw geschat. Lambda per dag via AIC. Vensters van 56, 84, 1092 en 1456 dagen; de ensemble middelt ze.
  - DNN: vierlaags feed-forward net met 24 uitgangen. Hyperparameters eenmalig afgesteld, gewichten dagelijks bijgewerkt op 4 jaar data.
  - Uitkomst: het DNN wint op MAE in alle vijf markten, maar met een marge van ruwweg 3 tot 12%. Bij RMSE is het wisselend. LEAR rekent in seconden, het DNN in minuten. Dit komt uit een deels samengevatte lezing van de volledige tekst; controleer de tabellen vóór je cijfers overneemt.
- **Nieuwere hybriden.** El Mahtout en Ziel (2026) melden 11 tot 12% lagere RMSE met een lineair+nietlineair net met online hertraining en Bernstein-aggregatie. Alleen het abstract is gelezen.
- **Boomsmodellen.** Gradient boosting komt in de EPF-literatuur zelden als hoofdmodel voor. In de gevonden studies is het één van de vergelijkers (O'Connor e.a. 2025 met LightGBM; Dutot e.a. 2024 met quantile gradient boosting). Voor ons is het toch een logische kandidaat: wind en zon werken niet-lineair via de merit order. Dat is mijn inschatting, geen bewezen bevinding.
- **Transformatie.** Uniejewski (2026) vindt tot 14,6% lagere fouten voor LEAR met een (geparametriseerde) asinh-transformatie, vooral in volatiele periodes. Asinh werkt ook bij negatieve prijzen, een logaritme niet.

## 2. Probabilistische voorspellingen

- **QRA.** Quantile Regression Averaging (Nowotarski en Weron 2015) is kwantielregressie op de puntvoorspellingen van meerdere modellen. De QRA-intervallen waren beter dan empirische intervallen van gecombineerde voorspellingen en dan het beste enkele model.
- **Conformal.** Kath en Ziel (2021) passen conformal prediction toe op Nord Pool en EPEX. Het is gelijk aan of net beter dan QRA op de Winkler-score; QRA faalt vaak op de dekkingstoets van Christoffersen. Ze gebruiken een rolling venster van 330 dagen. Dat deel komt uit een gedeeltelijke lezing.
- **Directe kwantielmodellen versus residuen.** O'Connor e.a. (2025) vinden dat gewone kwantielregressie en QRA te weinig dekking geven, terwijl conformal-methoden de doeldekking halen. Lipiecki, Uniejewski en Weron (2024) vergelijken QRA, conformal en isotone distributieregressie op puntvoorspellingen. Een ensemble van de drie verslaat distributionele neurale netten in Duitsland en Spanje. Marcjasz e.a. (2023) vinden dat een distributioneel neuraal net (Johnson SU) LASSO en DNN+QRA verslaat in Duitsland.
- **Regimewissels.** Dutot e.a. (2024) testen Franse prijzen in 2020-2021. Na september 2021 haalde geen enkele methode de doeldekking. Een naïeve conformal-correctie onderdekte. Een horizon-bewuste conformal-correctie met online aggregatie was het best. Gibbs en Candès (2021) geven daarvoor de basis: ACI stuurt het foutniveau online bij met `alpha_{t+1} = alpha_t + gamma(alpha - err_t)`. Zaffran e.a. (2022) laten op Franse day-ahead prijzen zien dat ACI met γ 0,01 tot 0,05 de smalste intervallen geeft bij juiste dekking.
- **Pinball loss.** Een kwantielvoorspelling beoordeel je met de pinball loss (Gneiting 2011: kwantielen zijn optimaal onder asymmetrisch lineair verlies). Nowotarski en Weron (2018) stellen als doel: zo scherp mogelijk, mits betrouwbaar.

## 3. Langere horizon (2 tot 7 dagen)

- Vrijwel alle EPF-benchmarks voorspellen 1 dag vooruit. Lago e.a. behandelen alleen de dag-vooruit-opzet.
- Sgarlato en Ziel (2023, open access, volledige tekst gelezen) onderzoeken Duitse prijzen tot 10 dagen vooruit met een lasso-ARX en weersverwachtingen. Rolling venster van 84 dagen.
  - Dag 2 tot 4 vooruit: 10 tot 20% lagere RMSE met weer. Op dag 2 en 3 is dat statistisch significant. Dag 1 profiteert van autoregressieve effecten.
  - Dag 5: de winst is kleiner. Vanaf dag 6 maakt weer de voorspelling slechter. Dat past bij de afnemende precisie van de weersverwachting.
  - Windsnelheid in Noord-Duitsland is de sterkste verklarende variabele. Kwadraat en derde macht van het weer helpen niet in het algemeen.
  - De beste regularisatie hangt af van de horizon: een langere horizon wil strengere regularisatie. Het paper noemt middelen over modellen en vensters als vervolg.
  - **Let op de beperking:** de voorspellingen lopen maar van 1 maart tot 16 april 2021 (ruim zes weken). Door de beperkte toegang tot historische weersverwachtingen was er niet meer. De cijfers zijn dus indicatief.
- Dat past bij ons ontwerp: weer per lead en recente prijsniveaus. Het ondersteunt ook de verwachting dat de nauwkeurigheid daalt met de horizon, omdat de weerverwachting minder goed wordt. Een kwantitatieve foutdaling per dag voor de totale prijsfout heb ik niet gevonden. Wel past de grens van 5 dagen in ons project bij dit paper: daarna levert weer niets meer op.
- **Eén model of per horizon?** Hier vond ik geen EPF-studie over. De macro-econometrie geeft een analogie: Marcellino, Stock en Watson (2006) vinden dat geïtereerde voorspellingen meestal beter zijn dan directe, vooral bij lange horizon. Dat geldt voor AR-modellen zonder exogene verwachtingen en is hier dus slechts een analogie. Wij hebben exogene verwachtingen die per lead verschillen. Met `horizon_uren` als feature en weer van de juiste lead is één model een redelijk begin. Per-horizon-groepen (D+2, D+3 tot D+5) blijven een experiment.

## 4. Trainingsvenster, hertrainen en regimewissels

- **Venster kiezen is riskant.** Fezzi en Mosetti (2018/2020) tonen dat de steekproeflengte de nauwkeurigheid sterk beïnvloedt, ook dat een eenvoudig lineair model op een korte steekproef verrassend goed kan zijn. Marcjasz, Serafin en Weron (2018) vinden dat de fout sterk verschilt per vensterlengte en dataset. Hubicka, Marcjasz en Weron (2018) tonen dat middelen over vensters van 28 tot 728 dagen beter is dan één "optimaal" venster kiezen.
- **Hertrainen.** De benchmarks schatten dagelijks opnieuw (Lago e.a.; Kath en Ziel). Voor lineaire modellen is dat goedkoop. Voor LightGBM is dagelijks of wekelijks hertrainen een keuze voor de backtest.
- **Gascrisis 2022.** Onze hoofddata begint in maart 2024 (besluit 7), dus de crisis zit niet in het trainingsvenster. De literatuur laat wel zien dat vaste kalibratie in zulke periodes faalt (Dutot e.a.), en dat variantiestabilisatie dan het meeste helpt (Uniejewski 2026).
- **Negatieve prijzen.** Nederland had volgens Electricity Maps 458 negatieve uren in 2024 en 584 in 2025 (laagste uurprijs -350 euro/MWh op 11 mei 2025). Dat zijn echte, vaste kenmerken van het regime en geen uitschieters. Dat pleit voor asinh in lineaire modellen en voor een eigen blik op de dekking rond het middaguur.
- **Kwartierprijzen.** Sinds de levering van 1 oktober 2025 koppelt SDAC op 15 minuten (Europese Commissie). Het uurgemiddelde van vier kwartieren is consistent met die opzet. Een gemeten effect op voorspelfouten heb ik niet gevonden; een leveranciersblog meldt een tijdelijk "zaagtand"-patroon en veel meer intra-uurvolatiliteit in de eerste maanden, maar dat is geen peer-reviewed bewijs.

## 5. Evaluatie

- **Foutmaten.** MAE en RMSE, plus rMAE (MAE gedeeld door MAE van een naïeve voorspelling). Lago e.a. raden rMAE aan en waarschuwen tegen MAPE bij prijzen rond nul.
- **Naïeve baselines zijn verplicht.** Lago e.a. gebruiken vooral "zelfde uur gisteren" en "zelfde uur vorige week". Het zijn verrassend sterke maatstaven; een model zonder baseline zegt niets. Weron (2014) vraagt om dezelfde data, dezelfde robuuste fout en een toets.
- **Diebold-Mariano.** DM (1995) toetst of het verwachte verliesverschil nul is. Lago e.a. gebruiken een univariate versie (24 toetsen, per uur) en een multivariate versie op de 24-dimensionale foutvector per dag. De `epftoolbox` bevat beide, met l1- of l2-norm. Voor ons: toets op het dagelijkse verlies per horizon, eenzijdig, met een HAC-correctie (mijn aanvulling), omdat opeenvolgende dagen niet onafhankelijk zijn.
- **Intervallen.** Dekking per kwantiel, pinball loss per kwantiel, intervalscore (Winkler) en een toets op de dekking (Christoffersen, zoals Kath en Ziel).
- **Lengte van de test.** Lago e.a. adviseren een testperiode van minstens een jaar. Met start maart 2024 en 180 dagen training hebben we ruim een jaar backtest.

## 6. Aanbevelingen voor dit project

1. **Maak een LEAR-achtige lasso-kwantiel-baseline op asinh-prijzen en leg die naast LightGBM.** Dit is de bewezen sterke standaard in de EPF-literatuur en goedkoop om dagelijks te schatten.
2. **Voeg een conformal-correctie met online ACI-update toe en kies γ in de buurt van 0,01 tot 0,05.** Vaste kalibratie onderdekt na regimewissels (Dutot e.a.; O'Connor e.a.).
3. **Vergelijk drie intervalroutes: directe kwantielen, puntmodel + residuen/QRA en puntmodel + conformal.** De literatuur is verdeeld, dus laat de pinball loss en dekking beslissen.
4. **Begin met één model met `horizon_uren` en weer van de juiste lead; test daarna twee horizongroepen (D+2, D+3 tot D+5).** Voor EPF is hier geen studie gevonden en de macro-analogie is zwak.
5. **Middel over meerdere trainingsvensters (bijvoorbeeld 90, 180 en 365 dagen) in plaats van er één te kiezen.** Vensterkeuze vooraf is riskant (Marcjasz e.a.; Hubicka e.a.).
6. **Rapporteer rMAE tegen twee naïeve baselines, plus pinball loss en dekking per horizon en per uur van de dag.** Zo zie je of het model echt iets toevoegt en waar het interval faalt.
7. **Toets verschillen met Diebold-Mariano op dagelijkse verliezen, eenzijdig, met HAC-correctie.** Zonder toets is een klein verschil in MAE ruis.
8. **Splits de backtest rond 1 oktober 2025 en houd de kwartierdata bij.** Het effect van de kwartierprijzen op de fout is niet in de literatuur gemeten; wij kunnen het zelf meten.

## Bronnen

Geopend (volledige tekst, deels, of abstract):

- Weron (2014), review, abstract: <https://ideas.repec.org/a/eee/intfor/v30y2014i4p1030-1081.html>
- Lago, Marcjasz, De Schutter, Weron (2021), Applied Energy 293, 116983: <https://arxiv.org/abs/2008.08004> (HTML-versie deels gelezen: <https://arxiv.org/html/2008.08004v2>)
- epftoolbox: <https://github.com/jeslago/epftoolbox> en DM-test: <https://epftoolbox.readthedocs.io/en/latest/modules/statest/dm.html>
- Nowotarski en Weron (2015), QRA, abstract: <https://ideas.repec.org/a/spr/compst/v30y2015i3p791-803.html>
- Nowotarski en Weron (2018), review probabilistisch, abstract: <https://ideas.repec.org/a/eee/rensus/v81y2018ip1p1548-1568.html>
- Kath en Ziel (2021), conformal: <https://arxiv.org/abs/1905.07886> (HTML deels gelezen)
- Marcjasz, Narajewski, Weron, Ziel (2023), distributionele netten, abstract: <https://arxiv.org/abs/2207.02832>
- Lipiecki, Uniejewski, Weron (2024), isotone distributieregressie, abstract: <https://arxiv.org/abs/2404.02270>
- El Mahtout en Ziel (2026), abstract: <https://arxiv.org/abs/2601.02856>
- Diebold en Mariano (1995), JBES 13(3), 253-263, abstract: <https://ideas.repec.org/a/bes/jnlbes/v13y1995i3p253-63.html> (de test staat willekeurige verliesfuncties en serieel gecorreleerde, niet-normale fouten toe)
- Gibbs en Candès (2021), ACI: <https://arxiv.org/abs/2106.00170>
- Zaffran e.a. (2022), AgACI: <https://arxiv.org/abs/2202.07282>
- O'Connor e.a. (2025), conformal DA en balancing: <https://arxiv.org/abs/2502.04935>
- Dutot, Zaffran, Féron, Goude (2024), Franse prijzen: <https://arxiv.org/abs/2405.15359>
- Sgarlato en Ziel (2023), weer voorbij day-ahead, IEEE TPWRS 38(3), open access, volledige tekst: <https://ieeexplore.ieee.org/document/9788043>
- Electricity Maps, Grid Review 2025 Nederland (negatieve uren): <https://www.electricitymaps.com/grid-in-review-2025/the-netherlands>
- Fezzi en Mosetti (2018), steekproeflengte, abstract: <https://ideas.repec.org/p/trn/utwprg/2018-10.html>
- Marcjasz, Serafin, Weron (2018), kalibratievensters, abstract: <https://ideas.repec.org/a/gam/jeners/v11y2018i9p2364-d168385.html>
- Hubicka, Marcjasz, Weron (2018), werkdocument, abstract: <https://ideas.repec.org/p/wuu/wpaper/hsc1803.html>
- Uniejewski (2026), variantiestabilisatie: <https://arxiv.org/abs/2511.13603>
- Gneiting (2011), kwantielen als optimale puntvoorspelling, abstract: <https://ideas.repec.org/a/eee/intfor/v27y2011i2p197-207.html>
- Marcellino, Stock, Watson (2005/2006), directe versus geïtereerde voorspellingen, abstract: <https://igier.unibocconi.eu/publications/working-papers/comparison-direct-and-iterated-multistep-ar-methods-forecasting>
- Europese Commissie, 15-minutenmarkt (1 oktober 2025): <https://energy.ec.europa.eu/news/eu-electricity-trading-day-ahead-markets-becomes-more-dynamic-2025-10-01_en>
- OpenWeather-blog over de eerste maanden met 15 minuten (leveranciersbron): <https://openweather.co.uk/blog/post/nine-months-on-how-15-minute-pricing-changed-europes-coupled-day-ahead-power-market>

Alleen metadata, niet als tekst gelezen:

- Uniejewski, Weron, Ziel (2018), VST: <https://dsee.wiwi.uni-due.de/en/research/publications/variance-stabilizing-transformations-for-electricity-spot-price-forecasting-13732/> (alleen metadata; de asinh-bevinding in deze memo komt uit Uniejewski 2026 hierboven)
