# Inventarisatie leveranciers dynamische stroomcontracten

Peildatum: 1 november 2026. Uitkomst: `data/leveranciers.yaml` (65 items). Hoort bij besluit 36 in `DECISIONS.md`.

## Samenvatting

Het ACM-register telt 52 actieve vergunninghouders voor levering van elektriciteit aan kleinverbruikers. Daarvan bieden 32 (direct of via een label) een dynamisch contract aan consumenten; 20 zijn zakelijk, gestopt of een groothandelsplatform. Inclusief wederverkopers zonder eigen vergunning zijn er 41 consumentenmerken met een dynamisch aanbod. Voor 37 daarvan is een inkoopvergoeding bekend: 18 bevestigd op de eigen tariefpagina, 19 alleen via een vergelijker. Vier merken publiceren niets en staan nergens.

De opslag loopt van 0,83 tot 2,80 ct/kWh excl. btw. De mediaan ligt rond 1,7 ct excl. btw. Belangrijkste correctie op de eerdere lezing van jeroen.nl: die bedragen (1,0 tot 3,4 ct) zijn **inclusief** btw, niet exclusief. De standaardwaarde van 2,0 ct excl. btw uit besluit 35 is daarmee aan de hoge kant; 1,65 ct excl. (2,0 ct incl.) past beter bij het midden van de markt.

## Werkwijze

1. **Register.** De ACM-pagina "Energieleveranciers met een vergunning" is opgehaald en de tabel "Vergunning elektriciteit" uitgelezen: 52 actieve vergunninghouders, plus een lijst ingetrokken vergunningen (daaruit niets overgenomen).
2. **Vergelijkers als kruiscontrole.** jeroen.nl (33 kaarten, 36 namen in de betaaltabel), salderingswijzer.nl (5 bevestigde bedragen, excl. btw), overstappen.nl (22 rijen, 15-10-2026), keuze.nl (twee artikelen 2026), energievergelijk.nl (30-6-2026), gaslicht.com (per pakket, 28-10-2026) en selectra.nl (per leverancier). Zo kwamen HalloStroom, NieuweStroom, Balans Energie, Centraal Beheer, LiveEnergy, GroeneStroomLokaal en Zonopnaam erbij.
3. **Eigen site per vergunninghouder en per merk.** In zeven parallelle rondes zijn circa 60 bedrijven en merken nagelopen: tariefpagina, tarievenblad (pdf), productvoorwaarden, helpcenter. Waar de pagina het bedrag via JavaScript laadt is naar gestructureerde data (JSON-LD), een publieke API of een pdf gezocht. Van elke vergunninghouder is vastgelegd welk consumentenmerk eronder hangt.
4. **Omrekening.** Elk bedrag is genoteerd zoals de bron het geeft, met de btw-wording erbij. Excl. btw = incl. btw / 1,21. Waar de bron de btw-status niet noemt is die afgeleid uit een ander bedrag op dezelfde pagina of uit een zustermerk, en dat staat dan in de opmerking.

## Aantallen

| | Aantal |
|---|---|
| Actieve vergunninghouders elektriciteit (ACM) | 52 |
| Daarvan met dynamisch consumentenaanbod (direct of via label) | 32 |
| Daarvan zonder (zakelijk, gestopt, platform, geen site) | 20 |
| Consumentenmerken met dynamisch aanbod (incl. wederverkopers) | 41 |
| Opslag bevestigd op eigen tariefpagina | 18 |
| Opslag alleen via vergelijker | 19 |
| Opslag nergens gepubliceerd | 4 |
| Items in de yaml (incl. gestopte merken ter controle) | 65 |

Niet in het register maar wel actief als dynamisch merk: Balans Energie en Quatt Energy (vergunninghouder onbekend), plus negen wederverkopers die op de site van EnergyZero, OpenSource Energie, ServiceHouse of Hezelaer hun vergunninghouder noemen.

## Alle dynamische aanbieders, van lage naar hoge opslag

Opslag in ct/kWh. Vaste kosten in euro per maand incl. btw. Status: B = bevestigd op eigen tariefpagina, V = alleen vergelijker, N = niet gepubliceerd.

| Leverancier | Excl. btw | Incl. btw | Vaste kosten | Status | Vergunninghouder |
|---|---|---|---|---|---|
| Powerpeers | 0,826 | 1,00 | 6,25 | B | Powerpeers B.V. (Vattenfall) |
| DELTA Energie | 1,037 | 1,2548 | 8,49 | B | DELTA Energie B.V. |
| Innova Energie | 1,231 | 1,49 | 6,96 | V | Innova Energie B.V. |
| Vattenfall | 1,240 | 1,50 | 5,99 | V | Vattenfall Sales Nederland N.V. |
| Budget Thuis | 1,388 | 1,68 | 5,99 | V | Budget Thuis B.V. |
| ANWB Energie | 1,488 | 1,80 | 8,50 | B | ANWB Energie B.V. |
| Pure Energie | 1,488 | 1,80 | 6,05 | V | Pure Energie Levering B.V. |
| Quatt Energy | 1,488 | 1,80 | 7,50 | B | onbekend |
| Tibber | 1,488 | 1,80 | 6,99 | B | Tibber Netherlands B.V. |
| Energiek | 1,490 | 1,8029 | n.b. | B | Energiek B.V. |
| Frank Energie | 1,500 | 1,815 | n.b. | B | Frank Energie B.V. |
| Mega | 1,504 | 1,82 | 6,05 | V | Mega Energie B.V. |
| ENGIE | 1,570 | 1,90 | 6,95 | V | ENGIE Nederland Retail B.V. |
| Noord Energie | 1,603 | 1,94 | 4,82 | V | Noord Energie KZ B.V. |
| Zonopnaam Energie | 1,650 | 1,997 | 8,00 | B | Vrij Op Naam B.V. |
| Balans Energie | 1,653 | 2,00 | 6,65 | B | onbekend (alleen met batterij) |
| Coolblue Energie | 1,653 | 2,00 | 7,49 | V | ServiceHouse B.V. |
| Zonneplan | 1,653 | 2,00 | 6,25 | B | Zonneplan Energie B.V. |
| Energiedirect | 1,694 | 2,05 | n.b. | V | Energie:direct B.V. (Essent) |
| NextEnergy | 1,736 | 2,10 | 5,99 | B | NextEnergy B.V. (ANWB) |
| SamSam | 1,745 | 2,1118 | 7,99 | B | EnergyZero B.V. |
| easyEnergy | 1,800 | 2,178 | 7,00 | B | e-Energy Europe B.V. |
| Hegg Energy | 1,818 | 2,20 | 7,50 | B | EnergyZero B.V. |
| Vandebron | 1,826 | 2,21 | 7,01 | V | Vandebron Energie B.V. |
| Greenchoice | 1,851 | 2,24 | 7,50 | V | Greenchoice B.V. |
| SolarEdge Energie | 1,851 | 2,24 | 7,50 | V | EnergyZero B.V. |
| EnergyZero | 1,853 | 2,242 | n.b. | B | EnergyZero B.V. |
| Sunergy | 1,853 | 2,242 | 7,49 | B | EnergyZero / OpenSource Energie |
| Eneco | 1,885 | 2,281 | 8,99 | B | Eneco Consumenten B.V. |
| Oxxio | 1,901 | 2,30 | 6,49 | V | OXXIO Nederland B.V. (Eneco) |
| GroenPand | 2,000 | 2,42 | 8,47 | V | Chiriqui B.V. |
| TinQE | 2,025 | 2,45 | 5,75 | V | Hezelaer Energy |
| SamenOm | 2,0661 | 2,50 | 8,57 | B | Coöp. Duurzame Energie Unie U.A. |
| Essent | 2,091 | 2,53 | 7,50 | V | Essent Retail Energie B.V. |
| Energie VanOns | 2,397 | 2,90 | 6,99 | V | Coöp. ver. NLD energie U.A. |
| GroeneStroomLokaal | 2,800 | 3,388 | 5,00 | V | EnergyZero B.V. (onzeker) |
| LiveEnergy | 2,800 | 3,388 | 4,95 | V | OpenSource Energie B.V. (onzeker) |
| Clean Energy Dynamics | – | – | – | N | OpenSource Energie B.V. |
| Hezelaer Energy | – | – | – | N | Hezelaer Energy B.V. |
| Holland Energie | – | – | – | N | Nieuw Hollands Energiebedrijf B.V. |
| Ventum | – | – | – | N | Ventum B.V. |

Vaste kosten "n.b." betekent: door de leverancier niet gepubliceerd en door vergelijkers tegenstrijdig opgegeven. De yaml noemt dan de vergelijkerswaarden in de opmerking.

## Gevonden tegenstrijdigheden en hoe ze zijn opgelost

**Btw-verwarring is de rode draad.** Leveranciers publiceren de inkoopvergoeding bijna altijd inclusief btw. jeroen.nl, overstappen.nl, keuze.nl, selectra.nl en gaslicht.com nemen dat bedrag over (gaslicht zegt het expliciet). salderingswijzer.nl rekent om naar exclusief btw. Dat verklaart vier van de vijf eerder gesignaleerde verschillen:

| Leverancier | jeroen.nl | salderingswijzer | Eigen site | Oplossing |
|---|---|---|---|---|
| ANWB Energie | 0,0180 | 0,0149 | "€ 0,018 per kWh (incl. btw)" | zelfde bedrag, incl. en excl. |
| Zonneplan | 0,0200 | 0,0165 | "€ 0,02 (incl. btw)" | zelfde bedrag |
| easyEnergy | 0,0218 | 0,0180 | "2,178 ct/kWh (btw inbegrepen)" | zelfde bedrag |
| Energiedirect | 0,0205 | 0,0169 | niet gepubliceerd | 0,0205 / 1,21 = 0,0169, zelfde bedrag |
| NextEnergy | 0,0219 | 0,0174 | tekst "€ 0,021 (incl. btw)", tabel 0,0219 | eigen site is intern tegenstrijdig; 0,0210 gekozen (expliciete btw-vermelding, komt overeen met salderingswijzer). 0,0219 is vermoedelijk het tarief voor eerdere instapmomenten. |

Overige tegenstrijdigheden:

- **EnergyZero.** Het helpcenter zegt in het ene artikel "inkoopvergoeding 2026: € 0,02800 exclusief btw" (24-7-2026) en in het andere "verkoopvergoeding € 0,02242 inclusief btw, gelijk aan de inkoopvergoeding" (28-8-2026). Gekozen voor 0,02242 incl., omdat jeroen.nl (dagelijks vernieuwd) en de labels Sunergy en Hegg hetzelfde tonen. Overstappen.nl toont nog 0,03388 (= 0,028 incl.); dat lijkt het oude tarief van vóór 16 april 2026. De 0,0339 van Hegg en SamSam bij jeroen.nl en overstappen.nl is om dezelfde reden verouderd: hun eigen sites tonen 0,022 en 0,021118.
- **Eneco.** Eigen combinatiepagina 0,02281 incl. btw; jeroen.nl 0,0189 (dat is precies de excl.-waarde), overstappen.nl 0,02297. Eigen site gevolgd.
- **Vattenfall.** jeroen.nl en overstappen.nl 0,0150; overstappen (juli 2026) 0,0255; selectra 0,0158. Vattenfall publiceert het bedrag niet. 0,0150 overgenomen, als onzeker gemarkeerd.
- **Innova.** jeroen.nl 0,0149, overstappen.nl 0,01243: precies een btw-factor uit elkaar, maar onbekend welke incl. is. jeroen.nl als incl. aangenomen; onzeker.
- **Vandebron.** gaslicht 0,0221 (incl., 28-10-2026), jeroen.nl 0,0219, overstappen.nl en energievergelijk 0,0257. gaslicht gevolgd; 0,0257 is waarschijnlijk ouder.
- **Pure Energie.** gaslicht 0,0180 (28-10-2026), jeroen.nl 0,0199. gaslicht gevolgd.
- **Coolblue.** selectra en overstappen 0,0200, jeroen.nl 0,0227. Meerderheid gevolgd.
- **Noord Energie.** jeroen.nl 0,0194 / 4,82 per maand; selectra 0,0182 / 10,88 per maand. Niet op te lossen zonder eigen tariefpagina; jeroen.nl gevolgd, onzeker.
- **ENGIE.** jeroen.nl 0,0190 is op de ENGIE-site alleen als verkoopvergoeding terug te vinden; selectra noemt 0,0157, wat precies 0,0190 excl. btw is. Aangenomen dat inkoop- en verkoopvergoeding gelijk zijn (zoals bij Tibber, Quatt, Sunergy en SamenOm).
- **Powerpeers.** Eigen site rondt af op "€ 0,01"; energievergelijk noemt 0,0085, wat 0,01 excl. btw is. Opgenomen als 1,00 incl. / 0,826 excl.
- **jeroen.nl 33 versus 36.** De drie namen zonder kaart zijn HalloStroom (gestopt februari 2026), NieuweStroom (alleen zakelijk) en Balans Energie (alleen met eigen batterij). Geen van de drie hoort in de gewone keuzelijst; Balans staat erin met een opmerking.

## Wie de opslag niet op de eigen site publiceert

Bedrag alleen via vergelijkers (19): Budget Thuis, Coolblue Energie, Energie VanOns, Energiedirect, ENGIE, Essent, Greenchoice, GroenPand, GroeneStroomLokaal, Innova Energie, LiveEnergy, Mega, Noord Energie, Oxxio, Pure Energie, SolarEdge Energie, TinQE, Vandebron, Vattenfall. Het patroon: de grote vijf (Eneco deels, Essent, Energiedirect, Vattenfall, Greenchoice) en de meeste labels tonen het bedrag pas in de aanmeldcalculator na postcode, in de app of in "Mijn"-omgeving. De productvoorwaarden zeggen dan "de hoogte staat in de leveringsovereenkomst".

Nergens een bedrag (4): Clean Energy Dynamics, Hezelaer Energy (VolFlex), Holland Energie, Ventum. Deze vier staan in geen enkele vergelijker en horen pas in de keuzelijst als er een bedrag is.

Half gepubliceerd: Frank Energie (alleen via de eigen prijs-API, niet als tekst), Energiek (alleen in gestructureerde data van de pagina), Eneco (alleen op de combinatiepagina), EnergyZero (alleen in het helpcenter, met twee verschillende bedragen).

## Geblokkeerde of onbereikbare sites

Automatische toegang geweigerd: klantenservice.frankenergie.nl (403), support.energyzero.nl HTML (403, de publieke API werkte), solaredge.com (403), coolblue.nl via fetch (403, curl werkte), beebie.nl (429), groenestroomlokaal.zendesk.com (403). Technisch stuk: groenestroomlokaal.nl (certificaat verlopen), samsamenergie.nl en hegg.nl (verkeerde domeinen; de echte zijn samsam.nu en hegg.energy), innova-energie.nl (onbereikbaar; echt domein innovaenergie.nl), deunie.nl (time-out), kikker.nl (alleen JavaScript), digiwatt.nl (geparkeerd), enie.nl (geblokkeerd bij registrar). Essent en Energiedirect toonden op 1-11-2026 een storingsmelding voor de dynamische tarieven.

## Opgeheven of veranderde namen

- HalloStroom: gestopt februari 2026, klanten naar NextEnergy. Staat nog bij overstappen.nl en jeroen.nl.
- WoonEnergie (CEN B.V.): gestopt 1 november 2025, naar Eneco.
- Mijndomein Energie: verwijst door naar Hegg Energy.
- Shell Energy: consumenten gestopt 1 oktober 2023.
- Vrijopnaam heet sinds 29 juni 2026 Zonopnaam Energie (vergunninghouder blijft Vrij Op Naam B.V.).
- Budget Energie heet Budget Thuis; Yebbo heet Noord Energie; om | nieuwe energie is SamenOm; NLD energie (Energie VanOns) en DE Unie (SamenOm) fuseren per 1 juli 2026 tot "Energie van Ons".
- NextEnergy is overgenomen door ANWB (2026); GGP ging per 1 november 2026 naar Eneco Zakelijk.
- Centraal Beheer Energie staat alleen nog in de overstappen.nl-tabel; op centraalbeheer.nl is niets te vinden. Buiten de keuzelijst gehouden.

## Onderhoudsadvies

- **Frequentie.** Elk kwartaal een volledige ronde; daarnaast per 1 januari (nieuwe tarieven, energiebelasting) en per 1 juli (veel leveranciers wijzigen halfjaarlijks). EnergyZero en Vattenfall mogen tot vier keer per jaar wijzigen; GroenPand wijzigt maandelijks.
- **Snelle check (een uur).** Open jeroen.nl/dynamische-energie/aanbieders en salderingswijzer.nl/dynamische-energie/inkoopvergoeding en vergelijk met de kolom incl. respectievelijk excl. btw. Een afwijking is een signaal om de eigen site te openen. Let op dat jeroen.nl bedragen incl. btw toont.
- **Diepe check (een dag).** Per leverancier de bron_url in de yaml openen. Voor de 18 bevestigde bedragen is dat de eigen pagina of pdf; voor de 19 vergelijkerswaarden eerst kijken of de leverancier het bedrag inmiddels wel publiceert, dan status ophogen.
- **Register.** Een keer per halfjaar de ACM-pagina vergelijken met de lijst vergunninghouders in de yaml (nieuwe namen, intrekkingen, naamswijzigingen). Nieuws over fusies en overnames (Solar Magazine, overstappen.nl nieuws) volgen.
- **Waar op letten.** Btw-wording bij elk bedrag; de eigen site van EnergyZero-labels (die lopen vaak achter op het platform); het verschil tussen inkoopvergoeding en verkoopvergoeding (ENGIE, Frank); instapmoment-afhankelijke tarieven (NextEnergy).
- **Site.** De peildatum uit de yaml tonen bij de keuzelijst, en bij items met status alleen_vergelijker of een opmerking "onzeker" een hint tonen dat het bedrag niet door de leverancier is bevestigd.

## Bronnen

Register en vergelijkers:

- https://www.acm.nl/nl/energie/elektriciteit-en-gas/energie-verkopen/energie-leveren-met-vergunning/energieleveranciers-met-een-vergunning
- https://www.acm.nl/nl/energie/elektriciteit-en-gas/energie-verkopen/energie-leveren-met-vergunning/eisen-energievergunning
- https://jeroen.nl/dynamische-energie/aanbieders ; https://jeroen.nl/dynamische-energie/aanbieders?weergave=tabel ; https://jeroen.nl/dynamische-energie/ ; https://jeroen.nl/sitemaps/aanbieders.xml ; https://jeroen.nl/dynamische-energie/aanbieders/quatt-energy
- https://www.salderingswijzer.nl/dynamische-energie/inkoopvergoeding ; https://www.salderingswijzer.nl/bronnen
- https://www.overstappen.nl/energie/leveranciers/dynamisch ; https://www.overstappen.nl/nieuws/dit-zijn-de-grootste-leveranciers-met-een-dynamisch-energiecontract/ ; https://www.overstappen.nl/nieuws/energieleverancier-woonenergie-stopt-eneco-neemt-klanten-over/ ; https://www.overstappen.nl/energie/leveranciers/groenestroomlokaal/ ; https://www.overstappen.nl/energie/leveranciers/centraal-beheer/
- https://www.keuze.nl/beste-keuze/beste-dynamische-energieleverancier ; https://www.keuze.nl/nieuws/zo-groot-zijn-de-prijsverschillen-tussen-dynamische-energieleveranciers-in-januari-2026 ; https://www.keuze.nl/nieuws/zo-anders-gaan-dynamische-leveranciers-om-met-terugleveren-bij-zonnepanelen ; https://www.keuze.nl/energie/energieleveranciers/budget-energie/dynamisch-contract ; https://www.keuze.nl/energie/energieleveranciers/nextenergy ; https://www.keuze.nl/energie/energieleveranciers/frank-energie ; https://www.keuze.nl/energie/energieleveranciers/innova-energie
- https://www.energievergelijk.nl/nieuws/deze-dynamische-energiecontracten-zijn-het-goedkoopst-per-30-juni-2026 ; https://www.energievergelijk.nl/dynamisch-energiecontract/prijzen ; https://www.energievergelijk.nl/energieleverancier/easyenergy ; https://www.energievergelijk.nl/energieleverancier/unitedconsumers ; https://www.energievergelijk.nl/energieleverancier/samsam ; https://www.energievergelijk.nl/energieleverancier/energyzero ; https://www.energievergelijk.nl/energieleverancier/nieuw-hollands-energiebedrijf
- https://www.gaslicht.com/stroom-vergelijken/budgetenergie/nederlandse-groene-stroom-dynamisch-5130 ; https://www.gaslicht.com/stroom-vergelijken/vandebron/nl-groene-stroom-dynamisch-5235 ; https://www.gaslicht.com/stroom-vergelijken/raedthuys-pure-energie/nederlandse-groene-stroom-dynamisch-5118 ; https://www.gaslicht.com/energie-vergelijken/raedthuys-pure-energie/groene-stroom-en-co2-gecompenseerd-gas-dynamisch-5115 ; https://www.gaslicht.com/stroom-vergelijken/delta/groene-stroom-dynamisch-5456 ; https://www.gaslicht.com/stroom-vergelijken/mega/stroom-dynamisch-5324 ; https://www.gaslicht.com/energieleveranciers/innova-energie/pakketten ; https://www.gaslicht.com/energieleveranciers/coolblue-energie/pakketten ; https://www.gaslicht.com/energieleveranciers/vanhelder/pakketten ; https://www.gaslicht.com/energieleveranciers/elix ; https://www.gaslicht.com/energieleveranciers/shell-energy ; https://www.gaslicht.com/energieleveranciers/centraal-beheer
- https://selectra.nl/energie/energieleverancier/budget-thuis/tarieven ; https://selectra.nl/energie/energieleverancier/coolblue-energie/tarieven ; https://selectra.nl/energie/energieleverancier/noord-energie/tarieven ; https://selectra.nl/energie/energieleverancier/kikker-energie ; https://selectra.nl/energie/energieleverancier/clean-energy ; https://selectra.nl/energie/energieleverancier/hegg-energy/tarieven ; https://selectra.nl/energie/energieleverancier/mijndomein-energie ; https://selectra.nl/energie/energieleverancier/nieuwestroom/tarieven ; https://selectra.nl/energie/energieleverancier/samsam-energie
- https://solarmagazine.nl/nieuws-zonne-energie/i43020/nextenergy-neemt-600-klanten-hallostroom-over ; https://solarmagazine.nl/nieuws-zonne-energie/i44287/energieleveranciers-vanons-en-om-fuseren-tot-energie-van-ons ; https://solarmagazine.nl/nieuws-zonne-energie/i43575/solaredge-breidt-ecosysteem-uit-met-dynamisch-energiecontract
- https://www.dynamische-energieprijzen.nl/actuele-prijzen/ ; https://www.dynamischegasprijzen.nl/Leveranciers/dynamisch-energiecontract-quatt-energy

Leveranciers (eigen pagina's, pdf's, helpcenters):

- ANWB: https://www.anwb.nl/energie/actuele-tarieven ; https://www.anwb.nl/energie/hoe-werkt-anwb-energie ; https://www.anwb.nl/energie/zo-werken-de-eerlijke-tarieven-van-anwb-energie ; https://www.anwb.nl/energie/dynamische-energiecontracten-vergelijken ; https://www.anwb.nl/energie/wat-kost-1-kwh ; https://www.anwb.nl/energie/voorwaarden ; https://merk.anwb.nl/m/16ce315977a4caae/original/ANWB-Energie-Productvoorwaarden-Dynamisch-Elektriciteit-en-Gas.pdf
- AllureNRG: https://www.allurenrg.nl/
- Audax: https://audaxenergy.nl/ ; https://www.audaxrenewables.nl/
- Balans Energie: https://balansenergie.nl/ ; https://balansenergie.nl/dynamisch/ ; https://balansenergie.nl/algemene-voorwaarden/
- Budget Thuis: https://www.budgetthuis.nl/energie/dynamisch-energiecontract ; https://www.budgetthuis.nl/docs/productvoorwaarden_dynamisch_contract.pdf ; https://www.budgetthuis.nl/energie/klantenservice/dynamische-tarieven/termijnbedrag
- Clean Energy / CE Dynamics: https://www.cleanenergy.nl/groene-stroom-en-gas ; https://ce-dynamics.nl/ ; https://ce-dynamics.nl/dynamische-energie-tarieven
- ConceptsnSolutions: https://www.cns.energy/
- Coolblue Energie: https://www.coolblue.nl/energiecontracten/dynamische-energie ; https://www.coolblue.nl/energie/dynamisch-energiecontract ; https://www.coolblue.nl/energiecontracten/tarieven ; https://www.coolblue.nl/energiecontracten/advies/wat-is-dynamische-energie ; https://www.gaslicht.com/userfiles/pdf/energie/coolblue-energie/pakketten/pakket-voorwaarden/PV260108-Contractvoorwaarden-Coolblue-Energie.pdf
- DELTA: https://www.deltaenergie.nl/stroom-gas/dynamisch-energiecontract/ ; https://www.deltaenergie.nl/stroom-gas/dynamisch-energiecontract/actuele-prijzen/ ; https://www.deltaenergie.nl/media/ohjb20ah/dynamisch-delta-groene-stroom-delta-gas-consumenten-23-april-2026.pdf ; https://www.deltaenergie.nl/media/2agnd14r/dynamisch-delta-groene-stroom-delta-gas-zakelijk-23-april-2026.pdf ; https://files.deltaenergie.nl/media/productvoorwaarden/Productvoorwaarden-DELTA-Dynamisch-1februari2026.pdf
- DigiWatt: http://digiwatt.nl/ ; https://www.acm.nl/system/files/documents/besluit-naamswijziging-digiwatt-openbaar.pdf
- easyEnergy: https://www.easyenergy.com/klantenservice/ons-aanbod/wat-kost-energie-bij-easyenergy ; https://www.easyenergy.com/klantenservice/onze-tarieven ; https://www.easyenergy.com/dynamische-energie/prijzen ; https://www.easyenergy.com/media/hdgd2moo/productvoorwaarden-dynamische-elektriciteit-kleine-aansluiting.pdf ; https://www.easyenergy.com/media/hknncvmx/kwaliteitscriteria-easyenergy.pdf ; https://www.easyenergy.com/media/axjiloqu/algemene-voorwaarden-2026-levering-en-teruglevering-elektriciteit-en-gas-huishoudelijk.pdf ; https://www.acm.nl/nl/publicaties/voorschriften-verbonden-aan-de-leveringsvergunningen-van-slim-met-energie-en-e-energy-europe
- ELIX: https://www.elix.nl/
- Eneco: https://www.eneco.nl/duurzame-energie/dynamisch-energiecontract/ ; https://www.eneco.nl/duurzame-energie/dynamisch-energiecontract/dynamische-tarieven/ ; https://www.eneco.nl/duurzame-energie/combinatie-dynamisch-en-vast/ ; https://www.eneco.nl/klantenservice/dynamisch-energiecontract/ ; https://www.eneco.nl/klantenservice/opbouw-energietarieven/ ; https://www.eneco.nl/duurzame-energie/energieprijzen/ ; https://www.eneco.nl/zakelijk/ ; https://www.eneco.nl/mkb/ ; https://www.eneco.nl/zakelijk/ggp/
- Energie VanOns / SamenOm: https://energie.vanons.org/dynamisch-contract/ ; https://energie.vanons.org/tarieven/ ; https://energie.vanons.org/tarieven/contracten-overzicht/ ; https://energie.vanons.org/vaste-kosten-teruglevering/ ; https://www.samenom.nl/tarieven/ ; https://www.samenom.nl/fusie/ ; https://www.samenom.nl/voorwaarden/ ; https://www.samenom.nl/wp-content/uploads/2026/08/20260814-Overeenkomstvoorwaarden-Consument-Dynamisch.pdf
- Energiedirect: https://www.energiedirect.nl/energie/energiecontract/dynamisch ; https://www.energiedirect.nl/energie/energieprijzen ; https://www.energiedirect.nl/klantenservice/contract/terugleverkosten ; https://www.energiedirect.nl/-/media/energiedirect/documenten/productvoorwaarden/productvoorwaarden-dynamisch.pdf
- Energiek: https://www.energiek.nl/energie/dynamisch ; https://www.energiek.nl/voordelen/scherp-tarief ; https://www.energiek.nl/voorwaarden ; https://www.energiek.nl/klantenservice/terugleverkost-vs-terugleververgoeding ; https://cdn.sanity.io/files/0zn3hqut/production/0eae6b02bd214e6ec4de370b1605fe17868ac8a4.pdf
- EnergyZero: https://www.energyzero.nl/ ; https://www.energyzero.nl/dynamisch-contract ; https://www.energyzero.nl/algemene-voorwaarden ; https://support.energyzero.nl/hc/nl/articles/7986421808285-Hoe-is-de-inkoopvergoeding-opgebouwd-voor-consumenten ; https://support.energyzero.nl/hc/nl/articles/34692105423773-Hoe-hoog-is-de-verkoopvergoeding ; https://static2.gaslicht.com/v/2026715-3-1/userfiles/pdf/energie/energyzero/pakketten/pakket-voorwaarden/PV260413-EnergyZero-Productvoorwaarden-Dynamisch-Stroom.pdf
- Energyhouse: https://energyhouse.nl/dynamische-energie/
- ENGIE: https://www.engie.nl/dynamisch ; https://www.engie.nl/energie/dynamisch-energiecontract ; https://www.engie.nl/energie/dynamisch-energiecontract/zonnepanelen ; https://www.engie.nl/energie/dynamisch-energiecontract/dynamische-energieprijzen ; https://energie.engie.nl/consument-dynamisch ; https://www.engie.nl/-/media/engie/over/_downloads/voorwaarden/engie-energie-b2c/productvoorwaarden-engie-dynamisch-20261-10.pdf
- EP Commodities: https://ttep.nl/
- Essent: https://www.essent.nl/energie/energiecontract/dynamisch ; https://www.essent.nl/dynamische-tarieven ; https://www.essent.nl/energie/energieprijzen ; https://www.essent.nl/klantenservice/contract/terugleverkosten ; https://www.essent.nl/-/media/essent/documenten/productvoorwaarden/202601_essent_productvoorwaarden_dynamisch.pdf
- Frank Energie: https://www.frankenergie.nl/ ; https://www.frankenergie.nl/dynamisch-energiecontract ; https://www.frankenergie.nl/nl/aanmelden/samenstellen ; https://www.frankenergie.nl/nl/factuurvoorspeller ; https://www.frankenergie.nl/nl/modelcontract ; https://frank-graphql-prod.graphcdn.app/ (query marketPrices)
- Greenchoice: https://www.greenchoice.nl/stroom-en-gas/dynamisch-energiecontract/ ; https://www.greenchoice.nl/stroom-en-gas/dynamisch-energiecontract/met-zonnepanelen/ ; https://www.greenchoice.nl/zakelijk/ ; https://www.greenchoice.nl/mkb/stroom-gas/dynamisch-energiecontract-zakelijk/
- GroenPand: https://groenpand.nl/groene-stroom-en-gas/tarieven ; https://groenpand.nl/groene-stroom-en-gas/dynamisch-contract ; https://www.groenpand.nl/blog/nieuws-5/stroometiket-groenpand-energie-2024-74 ; https://www.leonzeewolde.nl/
- GroeneStroomLokaal: https://groenestroomlokaal.nl/ ; https://groenestroomlokaal.nl/hoe-werkt-het ; https://groenestroomlokaal.nl/wie-zijn-wij
- HalloStroom: https://hallostroom.nl/ ; https://www.hallostroom.nl/particulier
- Hegg Energy: https://hegg.energy/dynamisch-energiecontract ; https://hegg.energy/voorwaarden ; https://www.mijndomein.nl/energie
- Hezelaer: https://www.hezelaer.nl/ ; https://www.hezelaer.nl/energie-voor-thuis
- Holland Energie: https://holland-energie.nl/ ; https://holland-energie.nl/dynamische-energie/ ; https://holland-energie.nl/dynamisch-contract/
- Innova: https://www.innovaenergie.nl/innova-dynamisch/ ; https://www.innovaenergie.nl/dynamisch-energiecontract/ ; https://www.innovaenergie.nl/tarieven/ ; https://www.innovaenergie.nl/over-innova/bedrijfsgegevens/
- Kikker Energie: https://www.kikker.nl/
- LiveEnergy: https://www.liveenergy.nl/stroom-gas ; https://www.liveenergy.nl/energieproducten ; https://www.liveenergy.nl/modelcontract-variabel ; https://bestanden.liveenergy.nl/productvoorwaarden-kvb.pdf
- Mega: https://www.mega.nl/dynamisch-energiecontract/ ; https://www.mega.nl/voorwaarden/ ; https://s3.eu-west-3.amazonaws.com/mega.nl/files/MegaDynamisch+productvoorwaarden.pdf
- NextEnergy: https://www.nextenergy.nl/dynamische-energie ; https://www.nextenergy.nl/dynamisch-energiecontracten-vergelijken ; https://www.nextenergy.nl/actuele-energieprijzen ; https://www.nextenergy.nl/meer-info/nextenergy-referentietarieven
- NieuweStroom: https://nieuwestroom.nl/ ; https://nieuwestroom.nl/producten/gas-stroom-product ; https://nieuwestroom.nl/energieprijzen ; https://www.acm.nl/system/files/documents/openbare-besluit-intrekking-aanvullende-vergunningsvoorschriften-slim-met-energie.pdf
- Noord Energie: https://www.noordenergie.nl/ ; https://www.noordenergie.nl/energiezaken/tarieven ; https://www.noordenergie.nl/energieaanbiedingen ; https://www.noordenergie.nl/marktprijzen ; https://www.noordenergie.nl/energiezaken/modelcontracten
- OpenSource Energie: https://www.opensourceenergie.nl/ ; https://www.opensourceenergie.nl/dynamische-energiecontracten
- Oxxio: https://www.oxxio.nl/energiecontract-afsluiten/dynamisch-energiecontract/ ; https://www.oxxio.nl/klantenservice/energiekosten/ ; https://www.oxxio.nl/klantenservice/terugleveren/ ; https://www.gaslicht.com/userfiles/pdf/energie/oxxio/pakketten/pakket-voorwaarden/PV260923-Oxxio-Productvoorwaarden-Dynamisch.pdf
- Powerpeers: https://www.powerpeers.nl/tarieven ; https://powerpeers.nl/tarieven/lage-inkoopvergoeding/ ; https://powerpeers.nl/dynamische-energie/terugleverkosten-en-dynamische-energie/ ; https://powerpeers.nl/veelgestelde-vragen/dynamische-energie/
- Pure Energie: https://pure-energie.nl/energiecontract/dynamisch-energiecontract/ ; https://pure-energie.nl/kennisbank/inkoop-en-verkoopvergoeding-dynamisch-contract/ ; https://pure-energie.nl/groene-stroom/tarieven/
- Quatt: https://www.quatt.io/quatt-energy ; https://www.quatt.io/waarom-quatt/energy/prijs-dynamisch-contract ; https://support.quatt.io/nl/articles/15693656-waarom-rekent-quatt-een-inkoopvergoeding-over-mijn-verbruikte-en-teruggeleverde-stroom ; https://support.quatt.io/nl/articles/12165656-hoe-werkt-de-prijsopbouw ; https://aanmelden-quatt.eabo.nl/
- SamSam: https://samsam.nu/groene-energie ; https://samsam.nu/vraag-antwoord
- Scholt: https://www.scholt.com/
- SEFE: https://www.sefe-energy.nl/
- ServiceHouse: https://servicehouse.nl/partners ; https://servicehouse.nl/modelcontract
- Shell: https://www.shell.nl/media/nieuwsberichten/2023/shell-energy-voor-consumenten-is-gestopt-in-nederland.html
- SolarEdge Energie: https://solaredge-energie.energyzero.nl/dynamisch-contract
- Sunergy: https://www.sunergy.nl/dynamische-energie ; https://www.sunergy.nl/actuele-tarieven
- Tibber: https://tibber.com/nl/energiecontract ; https://tibber.com/nl/stroomprijs ; https://tibber.com/nl/prijscalculator
- TinQE: https://www.tinqe.nl/TinQE-DynamischSlim ; https://tinqenergie.nl/
- UnitedConsumers: https://www.unitedconsumers.com/energie ; https://www.unitedconsumers.com/energie/energieprijzen
- Vandebron: https://vandebron.nl/energie/dynamisch ; https://vandebron.nl/energie/tarieven ; https://www.gaslicht.com/userfiles/pdf/energie/vandebron/pakketten/pakket-voorwaarden/PV260106-Vandebron-Leveringsvoorwaarden-Dynamisch.pdf
- VanHelder: https://vanhelder.nl/ ; https://www.gaslicht.com/userfiles/pdf/energie/vanhelder/pakketten/pakket-voorwaarden/PV250428-Productvoorwaarden-Dynamisch-elektriciteit-en-of-gas-kleinverbruik.pdf
- Vattenfall: https://www.vattenfall.nl/energie/dynamisch-energiecontract/ ; https://www.vattenfall.nl/klantenservice/alles-over-je-dynamische-contract/ ; https://www.vattenfall.nl/flexprijs-tarieven ; https://www.vattenfall.nl/energie/dynamisch-energiecontract/zonnepanelen/
- Ventum: https://www.ventum.nl/dynamisch-energiecontract/ ; https://ventum.nl/tarieven/
- WoonEnergie: https://www.woonenergie.nl/ ; https://www.woonenergie.nl/stroom-en-gas/naar-eneco/ ; https://www.woonenergie.nl/bedrijfsgegevens/
- Zonneplan: https://www.zonneplan.nl/energie/dynamisch-energiecontract ; https://www.zonneplan.nl/energie/vergelijken ; https://www.zonneplan.nl/energie/dynamische-energieprijzen
- Zonopnaam: https://www.zonopnaam.nl/tarieven ; https://www.zonopnaam.nl/dynamisch-contract ; https://www.zonopnaam.nl/voorwaarden ; https://www.zonopnaam.nl/files/ZON_Tarievenblad_2026M11_Dynamisch_V01.pdf
