# Ontwerpvarianten voor de website

Drie klikbare ontwerpen voor de statische site van de stroomprijsvoorspeller. Ze werken alle drie op
dezelfde voorbeelddata en dezelfde gedeelde logica. De opdrachtgever kiest er één; die gaat daarna
één-op-één naar `site/`.

## Lokaal openen

De pagina's laden `voorbeeld-forecast.json` met `fetch`. Dat werkt niet vanaf `file://`, dus start
een klein servertje in de projectmap:

```bash
.venv\Scripts\python -m http.server 8765 --directory site/ontwerpen
```

Open daarna:

- http://localhost:8765/variant-a.html
- http://localhost:8765/variant-b.html
- http://localhost:8765/variant-c.html

In de Claude-app staat dezelfde server als `ontwerpen` in `.claude/launch.json`.

## Bestanden

| Bestand | Wat |
|---|---|
| `voorbeeld-forecast.json` | Voorbeeld van het JSON-contract (uren, kwartieren voor de twee bekende dagen uit `prijzen_nl_kwartier.parquet`, dagen, scores) dat de pipeline straks schrijft. Vandaag en morgen (zo 1 en ma 2 nov 2026) zijn de echte day-ahead prijzen uit `data/processed/prijzen_nl_uur.parquet`; dag 2 t/m 7 zijn gesimuleerd rond het gemiddelde dagprofiel van de laatste 14 dagen, met een band die groeit van ±15% (dag 2) naar ±45% (dag 7). Prijzen in EUR/MWh. Lijst `dagen` met betrouwbaarheid: dag 2–3 hoog (1,1–1,4 ct), dag 4–5 redelijk (1,7–1,9 ct), dag 6–7 laag (2,2–2,5 ct). |
| `gedeeld.js` | Gedeelde logica voor alle varianten: JSON laden, EUR/MWh → ct/kWh (delen door 10) plus eigen tarief, dagen en dagdelen indelen, stoplicht, goedkoopste 3-uursblok, "vaagheid" (bandbreedte t.o.v. niveau), de canvas-grafiek, de tabel als alternatief voor de grafiek en het tariefformulier met `localStorage`. |
| `leveranciers.json` | Keuzelijst "Mijn leverancier": de 41 merken met een dynamisch contract uit `data/leveranciers.yaml`, alfabetisch, met inkoopvergoeding (ct/kWh excl. btw, kan null zijn), vaste kosten, status (`bevestigd_tariefpagina`, `alleen_vergelijker`, `niet_gepubliceerd`), peildatum en bron. Gemaakt met `maak_leveranciers_json.py`; in de pipeline wordt dit `site/data/leveranciers.json` met dezelfde veldnamen. |
| `maak_leveranciers_json.py` | Script dat `leveranciers.json` opnieuw maakt (`.venv\Scripts\python site/ontwerpen/maak_leveranciers_json.py`). Leest alleen, schrijft niet in `data/`. |
| `variant-a.html` | Rustig en redactioneel. |
| `variant-b.html` | Dashboard met kaarten. |
| `variant-c.html` | Kalender/tijdlijn per dag. |

Het JSON-contract (ongewijzigd overnemen in de pipeline):

```json
{"gegenereerd_utc": "2026-11-01T13:32:00Z", "biedzone": "NL", "eenheid": "EUR/MWh",
 "uren": [{"tijd": "2026-11-01T00:00:00+01:00", "p10": 71.2, "p50": 80.5, "p90": 92.0, "bekend": true}],
 "scores": {"periode_dagen": 30, "mae_dag2": 11.4, "mae_dag3": 14.0, "mae_dag4": 16.9, "mae_dag5": 19.2,
            "dekking80_dag2": 0.81, "dekking80_dag5": 0.78}}
```

Daarnaast een lijst per dag (besluit opdrachtgever: standaard 7 dagen vooruit, met per dag een
betrouwbaarheidsindicator):

```json
"dagen": [{"datum": "2026-11-03", "horizon_dag": 2, "betrouwbaarheid": "hoog", "verwachte_afwijking_ct": 1.14}]
```

`betrouwbaarheid` is `bekend` (vandaag en morgen), `hoog`, `redelijk` of `laag`;
`verwachte_afwijking_ct` is de gemiddelde afwijking van het model op die horizon in de afgelopen
30 dagen, in ct/kWh. De site vertaalt dat naar een label met icoon en tekst: ✓ zeker, ●●●
betrouwbaar, ●●○ redelijk, ●○○ onzeker, plus "gemiddeld 2,3 ct/kWh afwijking". Kleur: één tint
(indigo/paars) van verzadigd (zeker) naar bleek (onzeker), bewust los van het rood-oranje-groen
van het stoplicht, zodat "zeker" nooit als "goedkoop" leest. Het icoon en de tekst dragen de
betekenis, de kleur ondersteunt alleen. Ontbreekt `dagen`
in de JSON, dan valt de site terug op de dagindex en `scores`.

En optioneel kwartierprijzen, alleen voor de bekende dagen (de verwachting blijft per uur):

```json
"kwartieren": [{"tijd": "2026-11-01T00:15:00+01:00", "prijs": 251.04}]
```

De site heeft een schakelaar "Per uur / Per kwartier" (bewaard in `localStorage`,
`stroomprijs-resolutie-v1`). Per kwartier geldt alleen voor dagen waarvan alle kwartieren in de
JSON staan en alle uren bekend zijn; andere dagen blijven per uur. In kwartierstand worden ook
het goedkoopste laadblok en het wasblok op kwartieren gezocht (een blok kan dan om 23:45
beginnen); loopt zo'n blok door in een uurdag, dan worden die uren in vieren gedeeld.

Bij bekende uren is p10 = p50 = p90 = de echte prijs. `tijd` staat in lokale tijd met offset; de site
leest datum en uur rechtstreeks uit de tekst, zodat zomertijd-dagen met 23 of 25 uur goed gaan.

## Wat alle drie de varianten doen

- Standaard 7 dagen vooruit (vandaag plus 7 dagen). Per dag een betrouwbaarheidslabel met icoon en
  tekst en de verwachte afwijking, bovenop de scherpte-versus-vaagheid van de band; dag 6 en 7 zijn
  dagdeelblokken met het label "onzeker". Bij het beste laadmoment op zo'n dag staat "nog onzeker,
  kijk morgen opnieuw". In de uitleg: "Hoe verder vooruit, hoe onzekerder. Bij dag 6 en 7 geven we
  alleen een richting." Op mobiel schuift de grafiek horizontaal (minimaal 620 px breed) met een hint.
- Netspits 16–21 uur (overheidsadvies "Zet ook de knop om") als arcering in de grafiek en in de
  stroken van C, met legenda-item en één zin uitleg. Alleen zichtbaar gemaakt; het advies van de site
  blijft op prijs (keuze opdrachtgever). Constante `NETSPITS` in `gedeeld.js`.
- Eén grafiek over de hele horizon: bekende uren vol gevuld, voorspelde uren als gestreepte lijn met
  een band tussen onder- en bovengrens. Vanaf dag 4 geen uren meer maar blokken per dagdeel. De
  hoogte van de band of het blok is de onzekerheid. Kleuren en dekking zijn overal constant (besluit
  opdrachtgever 2026-11-01: geen vervaging; de band en het betrouwbaarheidslabel dragen de
  onzekerheid, het stoplicht alleen de prijs). De grafiek past zich aan het aantal dagen in de JSON
  aan: 5 of 7 dagen vooruit werkt allebei.
- Aanwijzen of aanraken geeft per uur (of per dagdeel) de prijs of de bandbreedte.
- Stoplicht per dagdeel, relatief ten opzichte van de hele periode (goedkoopste derde groen, duurste
  derde rood), altijd kleur + icoon (▼ ■ ▲) + tekst.
- Beste moment om te laden en te wassen: goedkoopste aaneengesloten 3 uur per dag, met de marge
  ten opzichte van het daggemiddelde en bij voorspelde dagen de onzekerheid (± ct).
- Prijsschakelaar met drie standen bij de grafiek (DECISIONS nr. 35, naar voorbeeld van de Frank
  Energie-app): **Marktprijs** (kale beursprijs, zonder btw), **Marktprijs+** ((beursprijs +
  inkoopvergoeding) × btw) en **All-in** ((beursprijs + inkoopvergoeding + energiebelasting) × btw,
  standaard). Vaste tarieven per jaar als constanten bovenin `gedeeld.js` (`TARIEF_JAAR` 2026,
  energiebelasting 9,2 ct/kWh excl. btw, btw 21%); de gebruiker vult alleen de inkoopvergoeding in
  (standaard 1,65 ct/kWh excl. btw, dat is 2,0 ct incl.). Stand, inkoopvergoeding en gekozen
  leverancier in `localStorage`
  (`stroomprijs-tarief-v2`, try/catch). Alle bedragen volgen de stand, ook de scores en de
  verwachte afwijking (die schalen met btw mee; belasting en inkoop zijn vast). Bij een negatieve
  beursprijs blijft de som gelden, dus all-in kan positief zijn; de uitleg zegt waarom.
- Keuzelijst "Mijn leverancier" (besluit 36) bescheiden achter een inklapbaar "Mijn tarief" naast de
  drie prijsstanden (A en C), in B achter de knop "Mijn tarief" naast de standen die de
  instellingendialoog opent; met "Anders / zelf invullen". De standaard 1,65 ct geeft zonder
  instelling al een goed beeld.
  Kiezen vult de inkoopvergoeding in en toont eronder "1,49 ct excl. btw, bevestigd op
  tariefpagina, peildatum 1 nov 2026", "via vergelijker, controleer bij je leverancier" of
  "publiceert geen bedrag, vul zelf in" (veld leeg, we rekenen dan met de standaard). De
  inkoopvergoeding blijft altijd handmatig aanpasbaar; dan staat er "Eigen bedrag". Onder de lijst:
  "Tarieven veranderen; wij controleren elk kwartaal." met de peildatum van de lijst.
- Laadinstellingen naast het tarief: laadvermogen (keuzelijst 2,3 / 3,7 / 7,4 / 11 / 22 kW of vrij
  invullen) en hoeveel kWh er geladen moet worden (vrij veld). Het kilometerhulpje is op verzoek van de
  opdrachtgever weggelaten; `KWH_PER_KM` staat nog in `gedeeld.js` voor later. Bloklengte = kWh gedeeld door kW, naar boven afgerond op hele uren, 1 tot 24. Zonder
  instellingen een vast blok van 3 uur en 30 kWh. Bewaard in `localStorage` (`stroomprijs-laden-v1`).
- Beste moment om te laden per dag: goedkoopste aaneengesloten blok van die lengte, met begin- en
  eindtijd, de gemiddelde prijs in ct/kWh, de kosten in euro voor die laadbeurt, en hoeveel euro het
  scheelt met het duurste blok van gelijke lengte en met het daggemiddelde. Bij voorspelde dagen de
  onzekerheid in euro. Een blok mag over middernacht heen lopen (nachtladen) als alle uren bekend
  of voorspeld zijn; de site zegt dan "loopt door tot di 3 nov".
- De wasmachine houdt een vast blok van 2 uur en 1 kWh per beurt (constanten `WAS_BLOK_UREN` en
  `WAS_KWH` in `gedeeld.js`).
- Uitleg wat zeker is en wat voorspeld, blok "Afgelopen 30 dagen" met de gemiddelde afwijking per
  horizon en de dekking van de band.
- Disclaimer en bronvermelding (Energy-Charts / Fraunhofer ISE, Open-Meteo, CC BY 4.0). Geen cookies,
  geen tracking, geen externe fonts of scripts.
- Mobiel eerst (getest op 375 px), donkere modus via `prefers-color-scheme`, systeemfonts,
  `aria-label` op de grafiek met een tekstsamenvatting, en dezelfde cijfers als tabel achter een
  uitklapknop.
- Nederlandse teksten zonder jargon: "ondergrens", "bovengrens", "waarschijnlijk tussen … en …",
  "redelijk zeker / indicatief / ruwe schatting".

## Variant A: rustig en redactioneel

**Idee.** Eén kolom, veel wit, serif-koppen. De site leest als een kort artikel: een kop in gewone
taal ("Morgen is stroom het goedkoopst tussen 12:00 en 15:00"), één grote grafiek, daaronder per
dag een korte alinea met vier dagdeelblokjes en de beste momenten. Uitleg en tarief staan onderaan
als rustige kaders.

**Sterk.** Het rustigst en het verst weg van gaslicht.com. De kop geeft meteen het antwoord. Grafiek
krijgt de volle breedte en alle aandacht. Weinig interface, dus weinig om verkeerd te begrijpen.
Donkere modus oogt hier het natuurlijkst.

**Zwak.** Langere pagina: om dag 5 te zien moet je scrollen. Geen vergelijking van dagen naast
elkaar. Minder "app"-gevoel; wie dagelijks snel wil kijken mist een compact overzicht.

**Voor wie.** Mensen die één keer per dag kijken en een duidelijk antwoord willen, en lezers die
de uitleg over onzekerheid op prijs stellen.

## Variant B: dashboard met kaarten

**Idee.** Lichte grijze achtergrond met witte kaarten. Bovenaan vier tegels met het antwoord
(laden, wassen, goedkoopste dag, hoe raak de verwachting was), dan de grafiek in een kaart met een
schakelaar 5 / 7 dagen (standaard 7), daaronder een raster met één kaart per dag: dagdelen als gekleurde vakjes
met prijs en stoplicht, en de beste momenten. Tarief zit achter een knop in een dialoogvenster.

**Sterk.** Alles in één oogopslag op desktop: dagen staan naast elkaar en zijn direct te
vergelijken. De 5/7-dagenschakelaar laat zien dat de langere horizon er zo bij kan. Voorspelde dagen
hebben een stippellijnrand en een betrouwbaarheidslabel. Voelt als een
hulpmiddel dat je dagelijks opent.

**Zwak.** Het drukst van de drie: meer kaders, meer kleurvlakken. Op mobiel wordt het een lange
stapel kaarten. Het risico op "dashboard-look" is het grootst; de stoplichtvakjes moeten
ingetogen blijven.

**Voor wie.** Mensen met thuisbatterij, laadpaal of warmtepomp die vaker per dag kijken en dagen
tegen elkaar afwegen.

## Variant C: kalender / tijdlijn per dag

**Idee.** Boven een compacte grafiek, daaronder de dagen onder elkaar als een tijdlijn. Elke dag is
een rij met links de datum en rechts een strook van 24 uur, ingekleurd met het stoplicht. Dag 4 en
verder tonen vier brede blokken met label. Het goedkoopste blok staat als een beugel met
laadicoon boven de strook. Klik op een dag en de rij klapt uit met het betrouwbaarheidslabel, de beste
momenten en bij dag 4 en verder de vier dagdelen met bandbreedte. De losse uurprijzen staan niet
in het uitklapdeel (wens opdrachtgever); aanwijzen op een cel toont ze, en ze staan in de tabel.

**Sterk.** De strook is het meest intuïtieve beeld van "wanneer op de dag": je ziet in één blik dat
de middag groen is en de avond rood. Het afnemende detail is letterlijk zichtbaar: 24 cellen worden
4 blokken, en het label bij de dag zegt hoe betrouwbaar de verwachting is. Werkt goed op mobiel omdat elke rij de volle breedte
heeft. Open- en dichtklappen houdt de pagina kort.

**Blok "Nu of later?"** (alleen in C, na keuze opdrachtgever; kaartjes "Standaardlaadbeurt" en
"Wasbeurt", bedragen "Morgen, goedkoopst", "Morgen, duurst", "Later deze week"). Bovenaan
een blok per apparaat (auto op basis van de laadinstellingen, wasbeurt 1 kWh in 2 uur) met drie
bedragen in euro: morgen goedkoopste blok, morgen duurste blok van gelijke lengte, en het
goedkoopste verwachte blok later in de week (met onder- en bovengrens). Een blok dat in voorspelde
uren doorloopt heet "deels verwacht". Daaronder één advieszin. Regels, in `SP.kostenAdvies` in
`gedeeld.js`:

- verschil onder 0,50 euro: "scheelt vrijwel niets, doe het wanneer het uitkomt";
- auto (streng): wachten alleen aanraden als het ook bij de bovengrens van de latere dag nog loont,
  anders "waarschijnlijk goedkoper, maar niet zeker; laad alleen wat u nodig hebt";
- wasbeurt (gemiddeld): wachten aanraden als de verwachting lager is;
- morgen goedkoper dan de rest van de week: "goed moment om het te doen".

Het idee: euro per handeling stuurt gedrag, ct/kWh niet. Wassen scheelt centen, de auto laden
euro's. De site mag dus ook "doe maar gewoon" zeggen.

**Zwak.** Prijsniveau per uur zie je pas na klikken; de strook toont alleen de klasse. Twee
grafieken (lijn en strook) vertellen deels hetzelfde verhaal. De datumkolom is krap op 375 px.

**Voor wie.** Mensen die plannen per dagdeel ("wanneer vandaag de wasmachine aan?") en op de
telefoon kijken.

## Aanbeveling

Opdrachtgever heeft op 2026-11-01 voor variant C gekozen. Het advies hieronder is daarmee
afgehandeld; het kostenblok is daarna als prototype in C gebouwd.

Variant C als basis, met de kop en de uitlegtekst van A. De tijdlijn maakt het principe "detail
neemt af met de horizon" het best zichtbaar en werkt het prettigst op de telefoon. Als de
opdrachtgever liever dagen naast elkaar vergelijkt op een groot scherm, is B de betere keuze.
A is de veiligste keuze als rust het zwaarst weegt.

Alle drie delen `gedeeld.js`, dus de stoplichtlogica, het goedkoopste blok en de grafiek zijn
hetzelfde; de keuze gaat over indeling en toon, niet over functionaliteit.
