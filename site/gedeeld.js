/*
 * gedeeld.js: de rekenkant van de stroomprijsvoorspeller-site. Alles hangt aan window.SP.
 *
 * index.html laadt dit bestand en zet daarna de pagina in elkaar. Hier staat wat daarvoor nodig is:
 *
 *   1. constanten              dagdelen, stoplicht, tarieven, sleutels van localStorage
 *   2. opmaak                  getallen, tijden, datums, bedragen, veilige HTML
 *   3. tarief                  de drie prijsstanden (besluit 35)
 *   4. model                   forecast.json omzetten naar dagen, uren, dagdelen en goedkoopste blokken
 *   5. zinnen                  teksten bij een blok of een dag
 *   6. instellingen            lezen, bewaren en de formulieren koppelen (resolutie, apparaten, auto's, tarief)
 *   7. tabel                   dezelfde cijfers als de grafiek, als tabel
 *   8. grafiek                 op een <canvas>, zonder bibliotheek
 *   9. advies                  "start om ..." voor apparaten en "klaar op welke dag?" voor auto's (besluit 85)
 *  10. gegevens ophalen        forecast.json en leveranciers.json
 *
 * Geen afhankelijkheden, geen build-stap. Prijzen komen binnen in EUR/MWh en gaan de pagina op in ct/kWh.
 * De oude ontwerpvarianten in site/ontwerpen/ hebben hun eigen kopie en gebruiken dit bestand niet.
 */
(function () {
  'use strict';

  // ==================== 1. constanten ====================

  const TIJDZONE = 'Europe/Amsterdam';
  const DAGDELEN = [
    { label: 'Nacht', van: 0, tot: 6 },
    { label: 'Ochtend', van: 6, tot: 12 },
    { label: 'Middag', van: 12, tot: 18 },
    { label: 'Avond', van: 18, tot: 24 },
  ];
  // nooit alleen kleur: elk niveau heeft ook een icoon en een woord (besluit 17)
  const STOPLICHT = {
    goedkoop: { klasse: 'sl-goedkoop', label: 'goedkoop', icoon: '▼' },
    gemiddeld: { klasse: 'sl-gemiddeld', label: 'gemiddeld', icoon: '■' },
    duur: { klasse: 'sl-duur', label: 'duur', icoon: '▲' },
  };
  // betrouwbaarheid per dag, uit forecast.dagen (besluit 34)
  const BETROUWBAARHEID = {
    bekend: { label: 'zeker', icoon: '✓', klasse: 'btr-bekend' },
    hoog: { label: 'betrouwbaar', icoon: '●●●', klasse: 'btr-hoog' },
    redelijk: { label: 'redelijk', icoon: '●●○', klasse: 'btr-redelijk' },
    laag: { label: 'onzeker', icoon: '●○○', klasse: 'btr-laag' },
  };
  const WEEKDAGEN = ['zondag', 'maandag', 'dinsdag', 'woensdag', 'donderdag', 'vrijdag', 'zaterdag'];
  const WEEKDAGEN_KORT = ['zo', 'ma', 'di', 'wo', 'do', 'vr', 'za'];
  const MAANDEN = ['jan', 'feb', 'mrt', 'apr', 'mei', 'jun', 'jul', 'aug', 'sep', 'okt', 'nov', 'dec'];
  const DETAIL_PER_UUR_TOT = 4; // de eerste vier dagen per uur, daarna per dagdeel (besluit 22)

  // Tarieven 2026 (besluit 35). Belasting en btw staan vast per jaar; de gebruiker kiest alleen de leverancier
  // of vult de inkoopvergoeding in. Jaarlijks bijwerken.
  const TARIEF_JAAR = 2026;
  const ENERGIEBELASTING_CT = 9.2;   // ct/kWh zonder btw (11,1 ct met btw)
  const BTW_PCT = 21;
  const INKOOP_STANDAARD_CT = 1.65;  // inkoopvergoeding, ct/kWh zonder btw (2,0 ct met btw): het midden van de markt
  const TARIEF_STANDEN = {
    markt: { label: 'Marktprijs', uitleg: 'kale beursprijs, zonder btw' },
    marktplus: { label: 'Marktprijs+', uitleg: 'beursprijs plus inkoopvergoeding, met btw' },
    allin: { label: 'All-in', uitleg: 'zoals op je rekening, met belasting en btw' },
  };
  const TARIEF_STANDAARD = 'allin';  // dat staat op de rekening

  // Wat de browser onthoudt (localStorage). De sleutels en de vorm van de inhoud niet veranderen:
  // bestaande instellingen van bezoekers moeten blijven werken.
  const TARIEF_SLEUTEL = 'stroomprijs-tarief-v2';       // { stand, inkoop, leverancier }
  const RESOLUTIE_SLEUTEL = 'stroomprijs-resolutie-v2'; // 'uur' of 'kwartier'
  const LADEN_SLEUTEL = 'stroomprijs-laden-v1';         // { kw, kwh, horizon }: de oude instelling van één auto
  const APPARATEN_SLEUTEL = 'stroomprijs-apparaten-v1'; // [{ id, naam, uren, kwh, stap, maxUitstel }]
  const AUTOS_SLEUTEL = 'stroomprijs-autos-v1';         // [{ id, naam, kwh, kw, vanaf, klaar }] (besluit 85)

  // eigen apparaten (besluit 55, 63)
  const APPARATEN_STANDAARD = [{ id: 'was', naam: 'Wasmachine', uren: 2, kwh: 1, stap: 1, maxUitstel: 8 }];
  const MAX_UITSTEL_KEUZES = [4, 6, 8, 12];  // hoeveel uitstel iemand hooguit wil, per apparaat (besluit 67, 85)
  const MAX_UITSTEL_STANDAARD = 8;
  const UITSTEL_STAPPEN = [1, 0.5, 0.25];  // waarin het uitstel op het apparaat is in te stellen (uren)
  const UITSTEL_LABELS = { 1: '1 uur', 0.5: 'half uur', 0.25: 'kwartier' };
  const MINUTEN_KEUZES = [0, 15, 30, 45];
  const KWARTIER = 0.25;
  const MAX_DUUR_UREN = 24;

  // auto's (besluit 85): zonder instellingen 30 kWh bijladen met 11 kW, aan de lader van 18:00 tot 08:00
  const LAAD_STANDAARD_KWH = 30;
  const LAAD_STANDAARD_KW = 11;
  const LAAD_STANDAARD_VANAF = 18;
  const LAAD_KLAAR_KEUZES = [8, 18]; // "klaar om": 's ochtends, of aan het eind van de middag (dan telt de dag mee)
  const LAAD_DAGEN = 3;              // voor zoveel dagen laten we zien wat de laadbeurt kost

  // startadvies (besluit 58)
  const MAX_UITSTEL_UREN = 12;       // verder dan 12 uur vooruit kijkt het advies nooit (besluit 85)
  const START_BIJNA_EURO = 0.02;     // 'bijna net zo goedkoop' als het goedkoopste moment: binnen 2 cent ...
  const START_BIJNA_DEEL = 0.05;     // ... of 5%; het eerste moment dat daaraan voldoet wint (besluit 67)
  const START_MIN_WINST_EURO = 0.05; // uitstel moet minstens 5 cent ...
  const START_MIN_WINST_DEEL = 0.10; // ... en 10% schelen, anders is het advies 'nu'
  const ANDERE_DAG_MIN_EURO = 0.10;  // een andere dag noemen we pas bij 10 cent ...
  const ANDERE_DAG_MIN_DEEL = 0.20;  // ... en 20% goedkoper

  // Netspits: de overheid vraagt om tussen 16 en 21 uur zo min mogelijk stroom te gebruiken. Alleen zichtbaar
  // gemaakt (arcering); het advies blijft op prijs.
  const NETSPITS = { van: 16, tot: 21 };

  // ==================== 2. opmaak ====================

  const ontbreekt = (x) => x === null || x === undefined || Number.isNaN(x);

  // getal met een komma: fmt(12.34) -> '12,3'
  function fmt(x, decimalen = 1) {
    return ontbreekt(x) ? '–' : x.toFixed(decimalen).replace('.', ',');
  }
  // zonder overbodige nul: 30 -> '30', 7.4 -> '7,4'
  function fmtKort(x) { return fmt(x, x % 1 ? 1 : 0); }
  // bedrag per handeling: onder de euro in centen, altijd zonder minteken; met een vaste spatie, zodat het bedrag
  // niet over twee regels breekt
  function fmtEuro(x) {
    if (ontbreekt(x)) return '–';
    const bedrag = Math.abs(x);
    return bedrag < 1 ? `${Math.round(bedrag * 100)} cent` : `€ ${bedrag.toFixed(2).replace('.', ',')}`;
  }
  // uren en minuten uit een aantal uren: 1.75 -> { uren: 1, minuten: 45 }
  function splitsUren(aantal) {
    const uren = Math.floor(aantal + 1e-9);
    return { uren: uren, minuten: Math.round((aantal - uren) * 60) };
  }
  const tweeCijfers = (n) => (n < 10 ? '0' : '') + n;
  // tijdstip: 12.25 -> '12:15'
  function fmtUur(uur) {
    const t = splitsUren(uur);
    return `${tweeCijfers(t.uren)}:${tweeCijfers(t.minuten)}`;
  }
  // duur: 1.75 -> '1 uur 45 min'
  function duurTekst(aantalUren) {
    const t = splitsUren(aantalUren);
    if (t.minuten === 0) return `${t.uren} uur`;
    if (t.uren === 0) return `${t.minuten} min`;
    return `${t.uren} uur ${t.minuten} min`;
  }
  // onzekerheid als plus- en minbedrag bij de verwachting, nooit 'tussen a en b' (besluit 56)
  // ⁠ houdt het minteken bij het bedrag als de regel afbreekt
  function plusMinCt(plus, min) { return `+${fmt(plus)} / −⁠${fmt(min)} ct`; }
  function plusMinEuro(plus, min) { return `+${fmtEuro(plus)} / −⁠${fmtEuro(min)}`; }

  // 'YYYY-MM-DDTHH:MM:SS+01:00' -> lokale onderdelen. De tijd in de JSON is al Nederlandse tijd, dus we lezen de
  // cijfers zoals ze er staan en laten de tijdzone van de browser erbuiten.
  function parseTijd(iso) {
    const datum = iso.slice(0, 10);
    return {
      datum: datum,
      uur: parseInt(iso.slice(11, 13), 10),
      minuut: parseInt(iso.slice(14, 16), 10) || 0,
      weekdag: new Date(`${datum}T12:00:00`).getDay(),
      dagVdMaand: parseInt(datum.slice(8, 10), 10),
      maand: parseInt(datum.slice(5, 7), 10) - 1,
    };
  }
  // Altijd weekdag en datum, nooit 'vandaag' of 'morgen': een pagina kan een dag later nog openstaan (besluit 53).
  // lang: 'Dinsdag 17 nov', anders 'di 17 nov'
  function dagNaam(dag, lang) {
    const datum = `${dag.dagVdMaand} ${MAANDEN[dag.maand]}`;
    if (!lang) return `${WEEKDAGEN_KORT[dag.weekdag]} ${datum}`;
    const weekdag = WEEKDAGEN[dag.weekdag];
    return `${weekdag.charAt(0).toUpperCase()}${weekdag.slice(1)} ${datum}`;
  }
  // '2026-11-01' -> '1 nov 2026'
  function datumTekst(iso) {
    if (!iso || iso.length < 10) return '';
    return `${parseInt(iso.slice(8, 10), 10)} ${MAANDEN[parseInt(iso.slice(5, 7), 10) - 1]} ${iso.slice(0, 4)}`;
  }
  // tijdstip van genereren, lokaal en leesbaar: 'maandag 16 november om 17:28'
  function gegenereerdTekst(iso) {
    try {
      return new Date(iso).toLocaleString('nl-NL', {
        weekday: 'long', day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit', timeZone: TIJDZONE,
      });
    } catch (e) { return iso; }
  }

  // De klok in Nederland, los van de tijdzone van de browser.
  const datumLokaal = (moment) => moment.toLocaleDateString('sv-SE', { timeZone: TIJDZONE });  // 'YYYY-MM-DD'
  function vandaagLokaal() { return datumLokaal(new Date()); }
  function morgenLokaal() { return datumLokaal(new Date(Date.now() + 24 * 3600 * 1000)); }
  function klokLokaal() {
    const [uur, minuut, seconde] = new Date()
      .toLocaleTimeString('en-GB', { timeZone: TIJDZONE, hour12: false }).split(':').map(Number);
    return { uur: uur % 24, minuut: minuut, seconde: seconde };
  }
  // het uur van nu, met de minuten als fractie: 14:30 -> 14.5
  function nuLokaalUur() {
    const k = klokLokaal();
    return k.uur + k.minuut / 60;
  }
  // milliseconden tot de volgende middernacht, voor de dagwissel op de pagina
  function msTotMiddernacht() {
    const k = klokLokaal();
    return Math.max(1000, (86400 - k.uur * 3600 - k.minuut * 60 - k.seconde) * 1000);
  }

  // tekst veilig in HTML zetten (ook binnen een attribuut)
  const HTML_TEKENS = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' };
  function esc(tekst) { return String(tekst).replace(/[&<>"]/g, (teken) => HTML_TEKENS[teken]); }
  function optieHtml(waarde, label, gekozen) {
    return `<option value="${esc(waarde)}"${gekozen ? ' selected' : ''}>${esc(label)}</option>`;
  }
  // wat iemand in een getalveld typt, met punt of komma; NaN als het geen getal is
  function leesGetal(veld) { return parseFloat(String(veld.value).replace(',', '.')); }

  function gemiddelde(getallen) {
    if (!getallen.length) return NaN;
    let som = 0;
    for (let i = 0; i < getallen.length; i++) som += getallen[i];
    return som / getallen.length;
  }
  const gemiddeldeVan = (lijst, veld) => gemiddelde(lijst.map((x) => x[veld]));

  // ==================== 3. tarief ====================
  // tarief = { stand: 'markt' | 'marktplus' | 'allin', inkoop: ct/kWh zonder btw of null, leverancier: naam of null }

  function standaardTarief() { return { stand: TARIEF_STANDAARD, inkoop: INKOOP_STANDAARD_CT, leverancier: null }; }

  // maakt van wat er ook bewaard was een geldig tarief. inkoop mag null zijn (de leverancier publiceert geen
  // bedrag); dan rekenen we met de standaard.
  function netTarief(t) {
    const standaard = standaardTarief();
    if (!t) return standaard;
    let inkoop = standaard.inkoop;
    if (typeof t.inkoop === 'number' && t.inkoop >= 0) inkoop = t.inkoop;
    else if (t.inkoop === null) inkoop = null;
    return {
      stand: TARIEF_STANDEN[t.stand] ? t.stand : standaard.stand,
      inkoop: inkoop,
      leverancier: typeof t.leverancier === 'string' && t.leverancier ? t.leverancier : null,
    };
  }
  function leesTarief() {
    try {
      const bewaard = localStorage.getItem(TARIEF_SLEUTEL);
      return netTarief(bewaard ? JSON.parse(bewaard) : null);
    } catch (e) { return standaardTarief(); }
  }
  function bewaarTarief(t) {
    bewaar(TARIEF_SLEUTEL, JSON.stringify(netTarief(t)));
  }
  const btwFactor = 1 + BTW_PCT / 100;

  // EUR/MWh -> ct/kWh in de gekozen stand. Bij een negatieve beursprijs geldt dezelfde som: all-in kan dan nog
  // positief zijn, want belasting en btw komen erbij.
  function naarCt(eurMwh, tarief) {
    const kaal = eurMwh / 10;
    if (tarief.stand === 'markt') return kaal;
    const inkoop = typeof tarief.inkoop === 'number' ? tarief.inkoop : INKOOP_STANDAARD_CT;
    if (tarief.stand === 'marktplus') return (kaal + inkoop) * btwFactor;
    return (kaal + inkoop + ENERGIEBELASTING_CT) * btwFactor;
  }
  // Een afwijking in ct/kWh (kaal) schaalt in de standen met btw mee; belasting en inkoop zijn vast en tellen
  // daar niet in mee.
  function tariefFactor(tarief) { return tarief.stand === 'markt' ? 1 : btwFactor; }
  function tariefLabel(tarief) {
    const jaar = tarief.stand === 'markt' ? '' : ` (tarieven ${TARIEF_JAAR})`;
    return `ct/kWh, ${TARIEF_STANDEN[tarief.stand].label.toLowerCase()}${jaar}`;
  }
  function tariefUitlegTekst() {
    return `Tarieven ${TARIEF_JAAR}: energiebelasting ${fmt(ENERGIEBELASTING_CT)} ct/kWh zonder btw ` +
      `(${fmt(ENERGIEBELASTING_CT * btwFactor)} ct met btw), btw ${BTW_PCT}%.`;
  }

  // ==================== 4. model ====================

  /*
   * verwerk(forecast, tarief, resolutie, apparaten) -> model
   *
   * model = { dagen, apparaten, scores, gegenereerd, eenheidLabel }
   * dag   = { datum, weekdag, dagVdMaand, maand, index, feestdag, bekend, betrouwbaarheid,
   *           uren, kwartieren, reeks (wat getekend en doorzocht wordt), perKwartier, perUur,
   *           gem, min, max, dagdelen }
   * uur   = { uur, duur (in uren: 1 of 0,25), pos (uren vanaf het begin van de dag), bekend,
   *           p10, p50, p90 (ct/kWh in de gekozen stand), stoplicht }
   */
  function verwerk(forecast, tarief, resolutie, apparaten) {
    tarief = netTarief(tarief);
    apparaten = apparaten || [];
    const factor = tariefFactor(tarief);
    const dagen = dagenUit(forecast, tarief);
    const infoPerDatum = {};
    (forecast.dagen || []).forEach((info) => { infoPerDatum[info.datum] = info; });

    dagen.forEach((dag, i) => {
      const info = infoPerDatum[dag.datum];
      dag.index = i;
      dag.feestdag = (info || {}).feestdag || null;
      dag.bekend = dag.uren.every((u) => u.bekend);
      dag.betrouwbaarheid = betrouwbaarheidVan(info, dag, forecast.scores || {}, factor);
      // kwartierprijzen alleen als de gebruiker dat kiest en de dag er (vrijwel) compleet mee is
      const heeftKwartieren = dag.bekend && dag.kwartieren.length >= 4 * dag.uren.length - 4;
      dag.perKwartier = resolutie === 'kwartier' && heeftKwartieren;
      dag.reeks = dag.perKwartier ? dag.kwartieren : dag.uren;
      dag.perUur = i < DETAIL_PER_UUR_TOT;
      zetPosities(dag.uren);
      zetPosities(dag.kwartieren);
      const p50 = dag.uren.map((u) => u.p50);
      dag.gem = gemiddelde(p50);
      dag.min = Math.min.apply(null, p50);
      dag.max = Math.max.apply(null, p50);
      dag.dagdelen = DAGDELEN.map((deel) => {
        const uren = dag.uren.filter((u) => u.uur >= deel.van && u.uur < deel.tot);
        return {
          label: deel.label, van: deel.van, tot: deel.tot,
          p10: gemiddeldeVan(uren, 'p10'), p50: gemiddeldeVan(uren, 'p50'), p90: gemiddeldeVan(uren, 'p90'),
        };
      });
    });
    zetStoplicht(dagen);

    return {
      dagen: dagen,
      apparaten: apparaten,
      scores: scoresVan(forecast.scores || {}, factor),
      gegenereerd: forecast.gegenereerd_utc,
      eenheidLabel: tariefLabel(tarief),
    };
  }

  // De uren en kwartieren uit de JSON, gegroepeerd per dag en omgerekend naar ct/kWh.
  // Voorbije dagen vallen weg: na middernacht toont de pagina de dag van gisteren niet meer. Is alles voorbij
  // (een verouderde voorspelling), dan blijft alles staan; de pagina zet er een melding boven.
  function dagenUit(forecast, tarief) {
    const vandaag = vandaagLokaal();
    let uren = forecast.uren.filter((u) => u.tijd.slice(0, 10) >= vandaag);
    if (!uren.length) uren = forecast.uren;
    const eersteDatum = uren[0].tijd.slice(0, 10);
    const kwartieren = (forecast.kwartieren || []).filter((k) => k.tijd.slice(0, 10) >= eersteDatum);

    const perDatum = new Map();
    const dagVan = (t) => {
      if (!perDatum.has(t.datum)) {
        perDatum.set(t.datum, {
          datum: t.datum, weekdag: t.weekdag, dagVdMaand: t.dagVdMaand, maand: t.maand, uren: [], kwartieren: [],
        });
      }
      return perDatum.get(t.datum);
    };
    uren.forEach((u) => {
      const t = parseTijd(u.tijd);
      dagVan(t).uren.push({
        uur: t.uur, duur: 1, bekend: !!u.bekend,
        p10: naarCt(u.p10, tarief), p50: naarCt(u.p50, tarief), p90: naarCt(u.p90, tarief),
      });
    });
    // kwartierprijzen zijn er alleen voor bekende dagen; de verwachting is per uur
    kwartieren.forEach((k) => {
      const t = parseTijd(k.tijd);
      const prijs = naarCt(k.prijs, tarief);
      dagVan(t).kwartieren.push({
        uur: t.uur + t.minuut / 60, duur: KWARTIER, bekend: true, p10: prijs, p50: prijs, p90: prijs,
      });
    });
    return Array.from(perDatum.values()).sort((a, b) => (a.datum < b.datum ? -1 : 1));
  }

  // positie (in uren vanaf het begin van de dag) per element; klopt ook op dagen met 23 of 25 uur
  function zetPosities(reeks) {
    let pos = 0;
    reeks.forEach((u) => { u.pos = pos; pos += u.duur; });
  }

  // een reeks opsplitsen in kwartieren (een uur wordt vier kwartieren met dezelfde prijs)
  function naarKwartieren(reeks) {
    const uit = [];
    reeks.forEach((u) => {
      if (u.duur <= KWARTIER) { uit.push(u); return; }
      for (let k = 0; k < 4; k++) {
        uit.push({ uur: u.uur + k * KWARTIER, duur: KWARTIER, bekend: u.bekend, p10: u.p10, p50: u.p50, p90: u.p90 });
      }
    });
    return uit;
  }

  // Betrouwbaarheid van een dag: uit de JSON; ontbreekt "dagen" daar, dan een schatting op de dagindex.
  // De afwijking is de gemiddelde fout van de afgelopen 30 dagen op die horizon, in de gekozen prijsstand.
  function betrouwbaarheidVan(info, dag, scores, factor) {
    let code, afwijking = null, horizon = dag.index;
    if (info && BETROUWBAARHEID[info.betrouwbaarheid]) {
      code = info.betrouwbaarheid;
      if (typeof info.verwachte_afwijking_ct === 'number') afwijking = info.verwachte_afwijking_ct * factor;
      if (typeof info.horizon_dag === 'number') horizon = info.horizon_dag;
    } else {
      if (dag.bekend) code = 'bekend';
      else code = dag.index <= 3 ? 'hoog' : dag.index <= 5 ? 'redelijk' : 'laag';
      const mae = scores[`mae_dag${dag.index}`];
      afwijking = typeof mae === 'number' ? (mae / 10) * factor : null;
    }
    const niveau = BETROUWBAARHEID[code];
    return {
      code: code, label: niveau.label, icoon: niveau.icoon, klasse: niveau.klasse,
      afwijking: afwijking, horizon: horizon,
    };
  }

  // scores per horizon uit de JSON (mae_dag2..7 in EUR/MWh, dekking80_dag2..7), in ct/kWh van de gekozen stand
  function scoresVan(scores, factor) {
    const mae = {}, dekking = {};
    for (let dag = 2; dag <= 7; dag++) {
      if (typeof scores[`mae_dag${dag}`] === 'number') mae[dag] = (scores[`mae_dag${dag}`] / 10) * factor;
      if (typeof scores[`dekking80_dag${dag}`] === 'number') dekking[dag] = scores[`dekking80_dag${dag}`];
    }
    return { periode: scores.periode_dagen, mae: mae, dekking: dekking };
  }

  // Stoplicht: goedkoop, gemiddeld of duur ten opzichte van de hele getoonde periode. De grenzen zijn de
  // tertielen van de P50 van alle dagdelen.
  function zetStoplicht(dagen) {
    const alle = [];
    dagen.forEach((dag) => { dag.dagdelen.forEach((deel) => { alle.push(deel.p50); }); });
    alle.sort((a, b) => a - b);
    const grensGoedkoop = alle[Math.floor(alle.length / 3)];
    const grensDuur = alle[Math.floor((2 * alle.length) / 3)];
    const kleur = (p50) => (p50 < grensGoedkoop ? 'goedkoop' : p50 < grensDuur ? 'gemiddeld' : 'duur');
    dagen.forEach((dag) => {
      [dag.dagdelen, dag.uren, dag.kwartieren].forEach((reeks) => {
        reeks.forEach((x) => { x.stoplicht = kleur(x.p50); });
      });
    });
  }

  // ==================== 5. zinnen ====================

  // "38,2 ct/kWh" of "verwacht 38,2 ct/kWh (+2,1 / −1,8 ct)"
  function bandZin(p10, p50, p90, bekend) {
    if (bekend) return `${fmt(p50)} ct/kWh`;
    return `verwacht ${fmt(p50)} ct/kWh (${plusMinCt(p90 - p50, p50 - p10)})`;
  }
  // "onzeker, gemiddeld 2,3 ct/kWh afwijking" / "zeker, prijs staat vast"; met metDag: "Dag 6: ..."
  function betrouwbaarheidTekst(dag, metDag) {
    const b = dag.betrouwbaarheid;
    let tekst = b.label;
    if (b.code === 'bekend') tekst += ', prijs staat vast';
    else if (b.afwijking !== null) tekst += `, gemiddeld ${fmt(b.afwijking)} ct/kWh afwijking`;
    return metDag && dag.index >= 2 ? `Dag ${b.horizon}: ${tekst}` : tekst;
  }
  const dagdelenTekst = (dag) => dag.dagdelen.map((deel) => `${deel.label.toLowerCase()} ${deel.stoplicht}`).join(', ');

  // de hele voorspelling in woorden, voor schermlezers (als beschrijving van de grafiek)
  function samenvatting(model) {
    return model.dagen.map((dag) => {
      let zin = `${dagNaam(dag, true)}: `;
      if (dag.bekend) zin += `bekend, gemiddeld ${fmt(dag.gem)} ct/kWh, van ${fmt(dag.min)} tot ${fmt(dag.max)}.`;
      else zin += `voorspeld, ${betrouwbaarheidTekst(dag, false)}, gemiddeld rond ${fmt(dag.gem)} ct/kWh.`;
      zin += ` Dagdelen: ${dagdelenTekst(dag)}.`;
      return zin;
    }).join(' ');
  }

  // ==================== 6. instellingen ====================
  // Elke koppel-functie leest de bewaarde instelling, zet het formulier goed, bewaart wijzigingen en roept
  // daarna bijWijziging(nieuweWaarde) aan. De functie geeft de waarde van dit moment terug.

  function lees(sleutel) {
    try { return localStorage.getItem(sleutel); } catch (e) { return null; }
  }
  function bewaar(sleutel, waarde) {
    try {
      if (waarde === null) localStorage.removeItem(sleutel);
      else localStorage.setItem(sleutel, waarde);
    } catch (e) { /* privévenster of opslag vol: de pagina werkt door, alleen onthoudt ze niets */ }
  }
  // knoppen die samen één keuze vormen: de gekozen knop krijgt aria-pressed="true"
  function markeerKeuze(knoppen, gekozen) {
    knoppen.forEach((knop) => { knop.setAttribute('aria-pressed', gekozen(knop) ? 'true' : 'false'); });
  }

  // ---------- per uur of per kwartier ----------

  function leesResolutie() { return lees(RESOLUTIE_SLEUTEL) === 'uur' ? 'uur' : 'kwartier'; }

  // knoppen met data-resolutie="uur|kwartier" in `container`
  function koppelResolutie(container, bijWijziging) {
    const knoppen = Array.from(container.querySelectorAll('[data-resolutie]'));
    const toon = (resolutie) => markeerKeuze(knoppen, (knop) => knop.dataset.resolutie === resolutie);
    knoppen.forEach((knop) => {
      knop.addEventListener('click', () => {
        const resolutie = knop.dataset.resolutie === 'kwartier' ? 'kwartier' : 'uur';
        bewaar(RESOLUTIE_SLEUTEL, resolutie);
        toon(resolutie);
        bijWijziging(resolutie);
      });
    });
    const resolutie = leesResolutie();
    toon(resolutie);
    return resolutie;
  }

  // ---------- eigen apparaten (besluit 55, 63) ----------
  // apparaat = { id, naam, uren (duur, per kwartier), kwh (per beurt), stap (uitstelstap op het apparaat, in uren),
  //              maxUitstel (hoogstens zoveel uur uitstel) }

  const standaardApparaten = () => APPARATEN_STANDAARD.map((a) => Object.assign({}, a));
  const geldigeStap = (stap) => (UITSTEL_STAPPEN.indexOf(Number(stap)) >= 0 ? Number(stap) : 1);
  // een oude instelling van 16 of 24 uur wordt 12 uur (besluit 85)
  function geldigMaxUitstel(uren) {
    const aantal = Number(uren);
    if (aantal > MAX_UITSTEL_UREN) return MAX_UITSTEL_UREN;
    return MAX_UITSTEL_KEUZES.indexOf(aantal) >= 0 ? aantal : MAX_UITSTEL_STANDAARD;
  }

  // Wat er bewaard is, zoals het er staat. Een oude lijst kan nog laadapparaten bevatten (soort 'laden',
  // besluit 73): die zijn nu auto's en staan in hun eigen lijst.
  function leesBewaardeApparaten() {
    try {
      const bewaard = lees(APPARATEN_SLEUTEL);
      const lijst = bewaard ? JSON.parse(bewaard) : null;
      return Array.isArray(lijst) ? lijst.filter((a) => a && a.uren > 0) : null;
    } catch (e) { return null; }
  }
  function leesApparaten() {
    const bewaard = leesBewaardeApparaten();
    if (!bewaard) return standaardApparaten();
    return bewaard.filter((a) => a.soort !== 'laden').map((a, i) => ({
      id: String(a.id || `app${i}`),
      naam: String(a.naam || 'Apparaat'),
      uren: Math.min(MAX_DUUR_UREN, Number(a.uren)),
      kwh: a.kwh > 0 ? Number(a.kwh) : 1,
      stap: geldigeStap(a.stap),
      maxUitstel: geldigMaxUitstel(a.maxUitstel),
    }));
  }
  function bewaarApparaten(lijst) { bewaar(APPARATEN_SLEUTEL, JSON.stringify(lijst)); }

  function apparaatRijHtml(a, i) {
    const duur = splitsUren(a.uren);
    const minuten = MINUTEN_KEUZES.map((m) => optieHtml(m, m, duur.minuten === m)).join('');
    const stappen = UITSTEL_STAPPEN
      .map((stap) => optieHtml(stap, UITSTEL_LABELS[stap], Math.abs((a.stap || 1) - stap) < 1e-9)).join('');
    const maxKeuzes = MAX_UITSTEL_KEUZES
      .map((uren) => optieHtml(uren, `${uren} uur`, geldigMaxUitstel(a.maxUitstel) === uren)).join('');
    return [
      `<div class="app-rij" data-i="${i}">`,
      `<label class="breed">Apparaat<input type="text" name="naam" value="${esc(a.naam)}" maxlength="30"`,
      ' placeholder="bijv. vaatwasser"></label>',
      `<label>Uren<input type="number" name="uren" value="${duur.uren}" step="1" min="0" max="24"`,
      ' inputmode="numeric"></label>',
      `<label>Minuten<select name="min">${minuten}</select></label>`,
      `<label>Verbruik (kWh)<input type="number" name="kwh" value="${a.kwh}" step="0.1" min="0.1"`,
      ' inputmode="decimal"></label>',
      `<label>Uitstelstap<select name="stap">${stappen}</select></label>`,
      `<label>Hoogstens uitstel<select name="max">${maxKeuzes}</select></label>`,
      `<button type="button" class="weg" aria-label="${esc(a.naam)} verwijderen" title="Verwijderen">×</button>`,
      '</div>',
    ].join('');
  }

  // Tekent in `container` een bewerkbare lijst (naam, duur, verbruik, uitstelstap, grens, verwijderen) met een knop
  // "Apparaat toevoegen".
  function koppelApparaten(container, bijWijziging) {
    let lijst = leesApparaten();

    function teken() {
      container.innerHTML = lijst.map(apparaatRijHtml).join('') +
        '<button type="button" class="toevoegen">+ Apparaat toevoegen</button>';
    }
    // één rij van het formulier als apparaat; een leeg of ongeldig veld houdt de vorige waarde
    function leesRij(rij, i) {
      const vorige = lijst[i] || {};
      const veld = (naam) => rij.querySelector(`[name=${naam}]`);
      const heleUren = leesGetal(veld('uren'));
      const minuten = parseInt(veld('min').value, 10) || 0;
      const kwh = leesGetal(veld('kwh'));
      let uren = vorige.uren || 1;
      if (heleUren >= 0) {
        const perKwartier = Math.round((heleUren + minuten / 60) / KWARTIER) * KWARTIER;
        uren = Math.min(MAX_DUUR_UREN, Math.max(KWARTIER, perKwartier));
      }
      return {
        id: vorige.id || `app${Date.now()}${i}`,
        naam: veld('naam').value.trim() || 'Apparaat',
        uren: uren,
        kwh: kwh >= 0.1 ? kwh : (vorige.kwh || 1),
        stap: geldigeStap(parseFloat(veld('stap').value)),
        maxUitstel: geldigMaxUitstel(parseFloat(veld('max').value)),
      };
    }
    function bewaarEnMeld() {
      bewaarApparaten(lijst);
      bijWijziging(lijst);
    }

    container.addEventListener('change', (ev) => {
      if (!ev.target.matches('input, select')) return;
      lijst = Array.from(container.querySelectorAll('.app-rij')).map(leesRij);
      bewaarEnMeld();
      teken();
    });
    container.addEventListener('click', (ev) => {
      if (ev.target.matches('.weg')) {
        lijst.splice(parseInt(ev.target.closest('.app-rij').dataset.i, 10), 1);
        teken();
        bewaarEnMeld();
      } else if (ev.target.matches('.toevoegen')) {
        // de nieuwe rij wordt pas bewaard als er iets in is ingevuld
        lijst.push({ id: `app${Date.now()}`, naam: '', uren: 1, kwh: 1 });
        teken();
        const naamVeld = container.querySelector('.app-rij:last-of-type [name=naam]');
        if (naamVeld) naamVeld.focus();
      }
    });
    teken();
    return lijst;
  }

  // ---------- auto's: hoeveel bijladen, hoe snel, en tussen welke tijden (besluit 85) ----------
  // auto = { id, naam, kwh (bij te laden), kw (laadvermogen), vanaf (uur van de dag waarop de auto aan de lader
  //          gaat), klaar (uur van de dag waarop de auto klaar moet zijn: 8 of 18) }
  // Zo vult iemand het ook in bij een leverancier die slim laadt: "klaar om 08:00". Met 18:00 tellen de uren
  // overdag mee. "Klaar om" staat niet in het formulier maar als schakelaar bij de auto op de pagina.

  const UREN_VAN_DE_DAG = Array.from({ length: 24 }, (_, uur) => uur);
  const geldigUur = (x, standaard) => (typeof x === 'number' && x >= 0 && x < 24 ? Math.floor(x) : standaard);

  function netAuto(a, i) {
    return {
      id: String(a.id || `auto${i}`),
      naam: String(a.naam || 'Auto'),
      kwh: a.kwh > 0 ? Number(a.kwh) : LAAD_STANDAARD_KWH,
      kw: a.kw > 0 ? Number(a.kw) : LAAD_STANDAARD_KW,
      vanaf: geldigUur(a.vanaf, LAAD_STANDAARD_VANAF),
      klaar: LAAD_KLAAR_KEUZES.indexOf(a.klaar) >= 0 ? a.klaar : LAAD_KLAAR_KEUZES[0],
    };
  }
  // De eerste keer: de auto uit de oude instelling (stroomprijs-laden-v1) en de laadapparaten uit de oude
  // apparatenlijst worden auto's, zodat niemand opnieuw hoeft in te vullen. Een laadapparaat had een duur en een
  // verbruik; het laadvermogen is het een gedeeld door het ander.
  function autosUitOudeInstellingen() {
    let oud = null;
    try { oud = JSON.parse(lees(LADEN_SLEUTEL) || 'null'); } catch (e) { /* onleesbaar: de standaard */ }
    const lijst = [netAuto({ id: 'auto', naam: 'Auto', kwh: oud && oud.kwh, kw: oud && oud.kw }, 0)];
    (leesBewaardeApparaten() || []).filter((a) => a.soort === 'laden').forEach((a, i) => {
      const kwh = a.kwh > 0 ? Number(a.kwh) : LAAD_STANDAARD_KWH;
      lijst.push(netAuto({ id: a.id, naam: a.naam, kwh: kwh, kw: Math.round((kwh / a.uren) * 10) / 10 }, i + 1));
    });
    return lijst;
  }
  // geeft { lijst, nieuw }: nieuw is true als er nog geen eigen lijst met auto's bewaard was
  function leesAutos() {
    try {
      const bewaard = lees(AUTOS_SLEUTEL);
      const lijst = bewaard ? JSON.parse(bewaard) : null;
      if (Array.isArray(lijst)) return { lijst: lijst.filter((a) => a).map(netAuto), nieuw: false };
    } catch (e) { /* onleesbaar: opnieuw opbouwen */ }
    return { lijst: autosUitOudeInstellingen(), nieuw: true };
  }
  function bewaarAutos(lijst) { bewaar(AUTOS_SLEUTEL, JSON.stringify(lijst)); }
  // hoe lang laden duurt, in uren (hoogstens een etmaal)
  function laadUren(auto) { return Math.min(MAX_DUUR_UREN, auto.kwh / auto.kw); }

  function autoRijHtml(a, i) {
    const uurKeuzes = (gekozen) => UREN_VAN_DE_DAG.map((uur) => optieHtml(uur, fmtUur(uur), uur === gekozen)).join('');
    return [
      `<div class="app-rij" data-i="${i}">`,
      `<label class="breed">Auto<input type="text" name="naam" value="${esc(a.naam)}" maxlength="30"></label>`,
      `<label>Bijladen (kWh)<input type="number" name="kwh" value="${a.kwh}" step="1" min="1"`,
      ' inputmode="decimal"></label>',
      `<label>Laadvermogen (kW)<input type="number" name="kw" value="${a.kw}" step="0.1" min="0.5"`,
      ' inputmode="decimal"></label>',
      `<label>Aan de lader vanaf<select name="vanaf">${uurKeuzes(a.vanaf)}</select></label>`,
      `<button type="button" class="weg" aria-label="${esc(a.naam)} verwijderen" title="Verwijderen">×</button>`,
      `<p class="rij-noot">Laden duurt ${duurTekst(Math.ceil(laadUren(a) * 4 - 1e-9) / 4)}.</p>`,
      '</div>',
    ].join('');
  }

  // Tekent in `container` de lijst met auto's en een knop "Auto toevoegen". Geeft { lijst, zetKlaar(id, uur) }
  // terug: de lijst van dit moment, en de functie waarmee de pagina "klaar om" van een auto verzet.
  function koppelAutos(container, bijWijziging) {
    const gelezen = leesAutos();
    let lijst = gelezen.lijst;
    // meteen vastleggen wat uit de oude instellingen is overgenomen: de apparatenlijst wordt hierna zonder
    // laadapparaten bewaard
    if (gelezen.nieuw) bewaarAutos(lijst);

    function teken() {
      container.innerHTML = lijst.map(autoRijHtml).join('') +
        '<button type="button" class="toevoegen">+ Auto toevoegen</button>';
    }
    function leesRij(rij, i) {
      const vorige = lijst[i] || {};
      const veld = (naam) => rij.querySelector(`[name=${naam}]`);
      const kwh = leesGetal(veld('kwh')), kw = leesGetal(veld('kw'));
      return netAuto({
        id: vorige.id || `auto${Date.now()}${i}`,
        naam: veld('naam').value.trim() || 'Auto',
        kwh: kwh > 0 ? kwh : vorige.kwh,
        kw: kw > 0 ? kw : vorige.kw,
        vanaf: parseInt(veld('vanaf').value, 10),
        klaar: vorige.klaar,
      }, i);
    }
    function bewaarEnMeld() {
      bewaarAutos(lijst);
      bijWijziging(lijst);
    }

    container.addEventListener('change', (ev) => {
      if (!ev.target.matches('input, select')) return;
      lijst = Array.from(container.querySelectorAll('.app-rij')).map(leesRij);
      bewaarEnMeld();
      teken();
    });
    container.addEventListener('click', (ev) => {
      if (ev.target.matches('.weg')) {
        lijst.splice(parseInt(ev.target.closest('.app-rij').dataset.i, 10), 1);
        teken();
        bewaarEnMeld();
      } else if (ev.target.matches('.toevoegen')) {
        // een nieuwe auto staat er meteen, met de standaardwaarden en een eigen naam
        lijst.push(netAuto({ id: `auto${Date.now()}`, naam: lijst.length ? `Auto ${lijst.length + 1}` : 'Auto' }, lijst.length));
        teken();
        bewaarEnMeld();
        const naamVeld = container.querySelector('.app-rij:last-of-type [name=naam]');
        if (naamVeld) { naamVeld.focus(); naamVeld.select(); }
      }
    });
    teken();
    return {
      lijst: lijst,
      zetKlaar: (id, uur) => {
        lijst = lijst.map((a, i) => (a.id === id ? netAuto(Object.assign({}, a, { klaar: uur }), i) : a));
        bewaarEnMeld();
      },
    };
  }

  // ---------- prijsstand, leverancier en inkoopvergoeding (besluit 35, 36) ----------

  const inkoopVan = (leverancier) => (leverancier ? leverancier.inkoopvergoeding_ct_kwh_excl_btw : undefined);

  // tekst onder de keuzelijst, per status van het bedrag
  function leverancierInfo(leverancier) {
    if (!leverancier) return '';
    const bedrag = typeof inkoopVan(leverancier) === 'number' ? `${fmt(inkoopVan(leverancier), 2)} ct excl. btw` : null;
    const peildatum = leverancier.peildatum ? `, peildatum ${datumTekst(leverancier.peildatum)}` : '';
    if (leverancier.status === 'bevestigd_tariefpagina' && bedrag) {
      return `${bedrag}, bevestigd op tariefpagina${peildatum}.`;
    }
    if (leverancier.status === 'alleen_vergelijker' && bedrag) {
      return `${bedrag}, via vergelijker, controleer bij je leverancier${peildatum}.`;
    }
    return `Publiceert geen bedrag, vul zelf in. Tot dan rekenen we met ${fmt(INKOOP_STANDAARD_CT, 2)} ct.`;
  }

  /*
   * koppelTarief(opties, bijWijziging)
   * opties: { standen: element met knoppen [data-stand], inkoop: input, lijst: inhoud van leveranciers.json,
   *           leveranciers: select, leverancierInfo, leveranciersNoot, uitleg: elementen voor tekst,
   *           form: formulier }. Alles behalve `standen` mag ontbreken.
   */
  function koppelTarief(opties, bijWijziging) {
    const knoppen = Array.from(opties.standen.querySelectorAll('[data-stand]'));
    const inkoopVeld = opties.inkoop;
    const keuzelijst = opties.leveranciers;
    const leveranciers = (opties.lijst && opties.lijst.leveranciers) || [];
    const leverancierMetNaam = (naam) => leveranciers.find((l) => l.naam === naam) || null;
    let tarief = leesTarief();

    function toonStand() {
      markeerKeuze(knoppen, (knop) => knop.dataset.stand === tarief.stand);
      const stand = TARIEF_STANDEN[tarief.stand];
      if (opties.uitleg) opties.uitleg.textContent = `${stand.label}: ${stand.uitleg}.`;
    }
    function toonInkoop() {
      if (!inkoopVeld) return;
      inkoopVeld.value = typeof tarief.inkoop === 'number' ? tarief.inkoop : '';
      inkoopVeld.placeholder = `${fmt(INKOOP_STANDAARD_CT, 2)} (standaard)`;
    }
    // onder de keuzelijst: het bedrag van de leverancier, of het eigen bedrag als dat is ingevuld
    function toonInfo(eigenBedrag) {
      if (!opties.leverancierInfo) return;
      opties.leverancierInfo.textContent = eigenBedrag && typeof tarief.inkoop === 'number'
        ? `Eigen bedrag: ${fmt(tarief.inkoop, 2)} ct excl. btw.`
        : leverancierInfo(leverancierMetNaam(tarief.leverancier));
    }
    function toepassen() {
      bewaarTarief(tarief);
      toonStand();
      bijWijziging(tarief);
    }

    if (keuzelijst) {
      keuzelijst.innerHTML = optieHtml('', 'Anders / zelf invullen', false) +
        leveranciers.map((l) => optieHtml(l.naam, l.naam, false)).join('');
      if (!leverancierMetNaam(tarief.leverancier)) tarief.leverancier = null;
      keuzelijst.value = tarief.leverancier || '';
      keuzelijst.addEventListener('change', () => {
        const gekozen = leverancierMetNaam(keuzelijst.value);
        let inkoop = tarief.inkoop;   // "anders": het bedrag blijft staan
        if (gekozen) inkoop = typeof inkoopVan(gekozen) === 'number' ? Math.round(inkoopVan(gekozen) * 100) / 100 : null;
        tarief = netTarief({ stand: tarief.stand, inkoop: inkoop, leverancier: gekozen ? gekozen.naam : null });
        toonInkoop();
        toonInfo(false);
        toepassen();
      });
    }
    if (opties.leveranciersNoot) {
      const peildatum = opties.lijst && opties.lijst.peildatum_lijst;
      opties.leveranciersNoot.textContent = 'Tarieven veranderen; wij controleren elk kwartaal.' +
        (peildatum ? ` Peildatum van de lijst: ${datumTekst(peildatum)}.` : '');
    }
    knoppen.forEach((knop) => {
      const stand = TARIEF_STANDEN[knop.dataset.stand];
      knop.title = stand ? stand.uitleg : '';
      knop.addEventListener('click', () => {
        tarief = netTarief({ stand: knop.dataset.stand, inkoop: tarief.inkoop, leverancier: tarief.leverancier });
        toepassen();
      });
    });
    if (inkoopVeld) {
      inkoopVeld.addEventListener('change', () => {
        const bedrag = leesGetal(inkoopVeld);
        tarief = netTarief({ stand: tarief.stand, inkoop: bedrag >= 0 ? bedrag : null, leverancier: tarief.leverancier });
        toonInkoop();
        toonInfo(true);
        toepassen();
      });
    }
    if (opties.form) opties.form.addEventListener('submit', (ev) => { ev.preventDefault(); toepassen(); });

    // bij het laden: is het bewaarde bedrag anders dan dat van de leverancier, dan is het een eigen bedrag
    const bewaardeLeverancier = leverancierMetNaam(tarief.leverancier);
    const wijktAf = !!bewaardeLeverancier && typeof tarief.inkoop === 'number' &&
      Math.abs(tarief.inkoop - (inkoopVan(bewaardeLeverancier) || 0)) > 0.006;
    toonInkoop();
    toonInfo(wijktAf);
    toonStand();
    return tarief;
  }

  // ==================== 7. tabel ====================

  // dezelfde cijfers als de grafiek, per dag een tabel: per uur of kwartier, vanaf dag 5 per dagdeel
  function maakTabel(container, model) {
    const cel = (inhoud) => `<td>${inhoud}</td>`;
    const kop = (tekst) => `<th scope="col">${tekst}</th>`;
    container.innerHTML = '';
    model.dagen.forEach((dag) => {
      const titel = document.createElement('h4');
      const feestdag = dag.feestdag ? `, ${dag.feestdag}` : '';
      titel.textContent = `${dagNaam(dag, true)}${feestdag} (${betrouwbaarheidTekst(dag, true)})`;
      container.appendChild(titel);

      const eersteKolom = dag.perKwartier ? 'Kwartier' : 'Uur';   // alle dagen per uur, zoals de grafiek (besluit 72)
      const prijsKoppen = dag.bekend ? kop('Prijs') : kop('Ondergrens') + kop('Verwacht') + kop('Bovengrens');
      const rijen = dag.reeks.map((r) => {
        const naam = fmtUur(r.uur);
        const prijzen = dag.bekend ? cel(fmt(r.p50)) : cel(fmt(r.p10)) + cel(fmt(r.p50)) + cel(fmt(r.p90));
        const stoplicht = STOPLICHT[r.stoplicht];
        return `<tr><th scope="row">${naam}</th>${prijzen}${cel(`${stoplicht.icoon} ${stoplicht.label}`)}</tr>`;
      }).join('');
      const tabel = document.createElement('table');
      tabel.className = 'sp-tabel';
      tabel.innerHTML = `<thead><tr>${kop(eersteKolom)}${prijsKoppen}${kop('Stoplicht')}</tr></thead>` +
        `<tbody>${rijen}</tbody>`;
      container.appendChild(tabel);
    });
  }

  // ==================== 8. grafiek ====================

  const GRAFIEK_KLEUREN = {   // CSS-variabele op het canvas -> terugval als die ontbreekt
    tekst: ['--g-tekst', '#333'], zacht: ['--g-zacht', '#777'], raster: ['--g-raster', '#e5e5e5'],
    lijn: ['--g-lijn', '#17335c'], bekend: ['--g-bekend', '#17335c'], band: ['--g-band', '#17335c'],
    nu: ['--g-nu', '#d9480f'], vlak: ['--g-vlak', '#ffffff'], laden: ['--g-laden', '#16a34a'],
  };
  const GRAFIEK_FONT = 'px system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';
  // hoe stevig een verwachte dag getekend wordt, per betrouwbaarheid (besluit 71): dekking van lijn en band, lijndikte
  const LIJNSTERKTE = {
    hoog: { lijn: 1, band: 0.22, dikte: 2 },
    redelijk: { lijn: 0.7, band: 0.18, dikte: 2 },
    laag: { lijn: 0.4, band: 0.13, dikte: 1.5 },
  };

  function grafiekKleuren(canvas) {
    const stijl = getComputedStyle(canvas);
    const kleuren = {};
    Object.keys(GRAFIEK_KLEUREN).forEach((naam) => {
      kleuren[naam] = stijl.getPropertyValue(GRAFIEK_KLEUREN[naam][0]).trim() || GRAFIEK_KLEUREN[naam][1];
    });
    return kleuren;
  }
  // een ronde stap voor de y-as: 1, 2, 5 of 10 maal een macht van tien
  function mooieStap(ruw) {
    const macht = Math.pow(10, Math.floor(Math.log10(ruw)));
    const deel = ruw / macht;
    return (deel < 1.5 ? 1 : deel < 3.5 ? 2 : deel < 7.5 ? 5 : 10) * macht;
  }
  // pad van een rechthoek met afgeronde hoeken (vullen of omlijnen doet de aanroeper)
  function afgerondeRechthoek(ctx, x, y, w, h, r) {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.lineTo(x + w - r, y); ctx.quadraticCurveTo(x + w, y, x + w, y + r);
    ctx.lineTo(x + w, y + h - r); ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
    ctx.lineTo(x + r, y + h); ctx.quadraticCurveTo(x, y + h, x, y + h - r);
    ctx.lineTo(x, y + r); ctx.quadraticCurveTo(x, y, x + r, y);
    ctx.closePath();
  }
  function lijn(ctx, x1, y1, x2, y2) {
    ctx.beginPath();
    ctx.moveTo(x1, y1);
    ctx.lineTo(x2, y2);
    ctx.stroke();
  }

  /*
   * tekenGrafiek(canvas, model, opties) -> { teken(), update(model), markeer(blokken) }
   * opties: { maxDagen, hoogte, compact }
   * markeer([{ start, eind }]) kleurt die uren groen over de volle hoogte: de gekozen laaduren (besluit 85). De
   * tijden zijn uren vanaf het begin van de eerste dag.
   *
   * Alle dagen naast elkaar op één tijdas, allemaal per uur (besluit 71): een bekende dag als gevuld vlak onder
   * een trapjeslijn (per kwartier als dat gekozen is), een verwachte dag als band (P10-P90) met een gestreepte
   * lijn (P50). Hoe minder betrouwbaar de dag, hoe lichter lijn en band. De netspits is gearceerd. Bewegen of
   * aanraken toont een leeslijn met de prijs.
   */
  function tekenGrafiek(canvas, model, opties = {}) {
    let dagen, totaalUren;
    let hoverX = null;         // x-positie van muis of vinger op het canvas, of null
    let arcering = null;       // { kleur, patroon }: de arcering van de netspits, één keer gemaakt per kleur
    let markering = [];        // [{ start, eind }]: de gekozen laaduren

    function zetModel(nieuw) {
      model = nieuw;
      dagen = opties.maxDagen ? model.dagen.slice(0, opties.maxDagen) : model.dagen;
      totaalUren = dagen.reduce((som, dag) => som + dag.uren.length, 0);
      canvas.setAttribute('role', 'img');
      canvas.setAttribute('aria-label', `Grafiek van de stroomprijs per uur over ${dagen.length} dagen, ` +
        `met ondergrens en bovengrens. ${samenvatting(model)}`);
      canvas.tabIndex = 0;
    }

    function teken() {
      // canvas op de juiste maat, scherp op schermen met een hoge pixeldichtheid
      const dpr = window.devicePixelRatio || 1;
      const breed = canvas.clientWidth || 600;
      const hoog = opties.hoogte || Math.max(220, Math.min(360, breed * 0.5));
      canvas.style.height = `${hoog}px`;
      canvas.width = Math.round(breed * dpr);
      canvas.height = Math.round(hoog * dpr);
      const ctx = canvas.getContext('2d');
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, breed, hoog);

      // tekenvlak: marges rond de grafiek en de breedte van één uur
      const compact = opties.compact || breed < 480;
      const marge = { links: compact ? 34 : 44, rechts: 8, boven: 10, onder: compact ? 40 : 36 };
      const vlakHoog = hoog - marge.boven - marge.onder;
      const uurBreed = (breed - marge.links - marge.rechts) / totaalUren;

      // y-as: vanaf 0, of lager als er negatieve prijzen zijn; alleen wat getekend wordt telt mee
      let ymin = 0, ymax = 1;
      dagen.forEach((dag) => {
        dag.uren.forEach((u) => {
          ymin = Math.min(ymin, u.p10);
          ymax = Math.max(ymax, u.p90);
        });
      });
      ymax = ymax * 1.08;
      if (ymin < 0) ymin = ymin * 1.1;
      const stap = mooieStap((ymax - ymin) / (compact ? 4 : 6));
      ymax = Math.ceil(ymax / stap) * stap;
      ymin = Math.floor(ymin / stap) * stap;

      const t = {   // alles wat de tekenfuncties hieronder nodig hebben
        ctx: ctx, kleur: grafiekKleuren(canvas), compact: compact, breed: breed, hoog: hoog,
        links: marge.links, rechts: breed - marge.rechts, boven: marge.boven, onder: marge.boven + vlakHoog,
        vlakHoog: vlakHoog, uurBreed: uurBreed, ymin: ymin,
        x: (uur) => marge.links + uur * uurBreed,
        y: (prijs) => marge.boven + vlakHoog - ((prijs - ymin) / (ymax - ymin)) * vlakHoog,
      };
      tekenAssen(t, stap, ymax);
      tekenMarkering(t);
      let eersteUur = 0;   // het uur op de tijdas waarop deze dag begint
      dagen.forEach((dag) => {
        tekenDag(t, dag, eersteUur);
        eersteUur += dag.uren.length;
      });
      ctx.textBaseline = 'middle';
      if (ymin < 0) {   // nullijn
        ctx.strokeStyle = t.kleur.zacht; ctx.lineWidth = 1;
        lijn(ctx, t.links, t.y(0), t.rechts, t.y(0));
      }
      if (hoverX !== null) tekenLeeslijn(t);
    }

    function tekenAssen(t, stap, ymax) {
      const ctx = t.ctx;
      ctx.font = (t.compact ? 11 : 12) + GRAFIEK_FONT;
      ctx.textBaseline = 'middle'; ctx.textAlign = 'right';
      for (let prijs = t.ymin; prijs <= ymax + 1e-9; prijs += stap) {
        ctx.strokeStyle = t.kleur.raster; ctx.lineWidth = 1;
        lijn(ctx, t.links, t.y(prijs), t.rechts, t.y(prijs));
        ctx.fillStyle = t.kleur.zacht;
        ctx.fillText(fmt(prijs, stap < 1 ? 1 : 0), t.links - 6, t.y(prijs));
      }
      // eenheid, gekanteld langs de y-as
      ctx.save();
      ctx.translate(10, t.boven + t.vlakHoog / 2);
      ctx.rotate(-Math.PI / 2);
      ctx.textAlign = 'center'; ctx.fillStyle = t.kleur.zacht;
      ctx.fillText('ct/kWh', 0, 0);
      ctx.restore();
    }

    // de gekozen laaduren: een groen vlak over de volle hoogte, minstens drie pixels breed
    function tekenMarkering(t) {
      const ctx = t.ctx;
      ctx.fillStyle = t.kleur.laden; ctx.globalAlpha = 0.25;
      markering.forEach((blok) => {
        const x0 = Math.max(t.links, t.x(blok.start)), x1 = Math.min(t.rechts, t.x(blok.eind));
        if (x1 > x0) ctx.fillRect(x0, t.boven, Math.max(3, x1 - x0), t.vlakHoog);
      });
      ctx.globalAlpha = 1;
    }

    function tekenDag(t, dag, eersteUur) {
      const ctx = t.ctx;
      const xBegin = t.x(eersteUur), xEind = t.x(eersteUur + dag.uren.length);
      // scheidingslijn aan het begin van de dag
      ctx.strokeStyle = t.kleur.raster; ctx.lineWidth = 1;
      lijn(ctx, xBegin, t.boven, xBegin, t.onder);
      tekenNetspits(t, dag, eersteUur);
      const xNu = xVanNu(t, dag, eersteUur);
      if (xNu === null) {
        tekenPrijzen(t, dag, eersteUur, xBegin, xEind);
      } else {
        // vandaag: de uren die voorbij zijn in grijs, de rest in kleur, met een dunne lijn op 'nu' (besluit 66)
        const grijs = Object.assign({}, t, {
          kleur: Object.assign({}, t.kleur, { bekend: t.kleur.zacht, band: t.kleur.zacht, lijn: t.kleur.zacht }),
        });
        binnenStrook(t, xBegin, xNu, () => tekenPrijzen(grijs, dag, eersteUur, xBegin, xEind));
        binnenStrook(t, xNu, xEind, () => tekenPrijzen(t, dag, eersteUur, xBegin, xEind));
        ctx.strokeStyle = t.kleur.zacht; ctx.lineWidth = 1;
        lijn(ctx, xNu, t.boven, xNu, t.onder);
        ctx.font = (t.compact ? 10 : 11) + GRAFIEK_FONT;
        ctx.fillStyle = t.kleur.zacht; ctx.textBaseline = 'top';
        const past = xNu + 20 < xEind;
        ctx.textAlign = past ? 'left' : 'right';
        ctx.fillText('nu', xNu + (past ? 3 : -3), t.boven + 1);
        ctx.font = (t.compact ? 11 : 12) + GRAFIEK_FONT;
      }
      tekenDaglabel(t, dag, xBegin, xEind);
    }
    function tekenPrijzen(t, dag, eersteUur, xBegin, xEind) {
      if (dag.bekend) tekenBekendeDag(t, dag, eersteUur, xBegin, xEind);
      else tekenVerwachteDag(t, dag, eersteUur, xBegin, xEind);
    }
    // x-positie van 'nu' als deze dag vandaag is, anders null; `pos` telt goed op dagen met 23 of 25 uur
    function xVanNu(t, dag, eersteUur) {
      if (dag.datum !== vandaagLokaal()) return null;
      const nu = nuLokaalUur();
      const uur = dag.uren.find((u) => u.uur === Math.floor(nu));
      return t.x(eersteUur + (uur ? uur.pos + (nu - uur.uur) : nu));
    }
    // tekent alleen binnen de verticale strook van x0 tot x1
    function binnenStrook(t, x0, x1, tekenen) {
      const ctx = t.ctx;
      ctx.save();
      ctx.beginPath(); ctx.rect(x0, 0, Math.max(0, x1 - x0), t.hoog); ctx.clip();
      tekenen();
      ctx.restore();
    }

    // netspits 16-21 uur: arcering. De positie komt uit het uur zelf, zodat dagen met 23 of 25 uur goed gaan.
    function tekenNetspits(t, dag, eersteUur) {
      const van = dag.uren.find((u) => u.uur === NETSPITS.van);
      const tot = dag.uren.find((u) => u.uur === NETSPITS.tot);
      if (!van || !tot) return;
      t.ctx.fillStyle = arceerPatroon(t.ctx, t.kleur.zacht);
      t.ctx.fillRect(t.x(eersteUur + van.pos), t.boven, t.x(eersteUur + tot.pos) - t.x(eersteUur + van.pos), t.vlakHoog);
    }
    function arceerPatroon(ctx, kleur) {
      if (arcering && arcering.kleur === kleur) return arcering.patroon;
      const tegel = document.createElement('canvas');
      tegel.width = 8; tegel.height = 8;
      const g = tegel.getContext('2d');
      g.strokeStyle = kleur; g.globalAlpha = 0.28; g.lineWidth = 1;
      g.beginPath();
      g.moveTo(-2, 10); g.lineTo(10, -2);
      g.moveTo(-2, 2); g.lineTo(2, -2);
      g.moveTo(6, 10); g.lineTo(10, 6);
      g.stroke();
      arcering = { kleur: kleur, patroon: ctx.createPattern(tegel, 'repeat') };
      return arcering.patroon;
    }

    // bekende dag: gevuld vlak onder een trapjeslijn (elk uur of kwartier een vlak stukje)
    function tekenBekendeDag(t, dag, eersteUur, xBegin, xEind) {
      const ctx = t.ctx;
      const trapjes = () => {
        ctx.beginPath();
        dag.reeks.forEach((u, i) => {
          const x = t.x(eersteUur + u.pos);
          if (i === 0) ctx.moveTo(x, t.y(u.p50)); else ctx.lineTo(x, t.y(u.p50));
          ctx.lineTo(x + t.uurBreed * u.duur, t.y(u.p50));
        });
      };
      const bodem = t.y(Math.max(t.ymin, 0));
      trapjes();
      ctx.lineTo(xEind, bodem); ctx.lineTo(xBegin, bodem); ctx.closePath();
      ctx.globalAlpha = 0.18; ctx.fillStyle = t.kleur.bekend; ctx.fill(); ctx.globalAlpha = 1;
      ctx.strokeStyle = t.kleur.bekend; ctx.lineWidth = dag.perKwartier ? 1.5 : 2; ctx.lineJoin = 'round';
      trapjes();
      ctx.stroke();
    }

    // verwachte dag: band van P10 tot P90 met de gestreepte P50-lijn erdoor, punten midden in elk uur.
    // De betrouwbaarheid van de dag bepaalt hoe stevig lijn en band zijn (besluit 71).
    function tekenVerwachteDag(t, dag, eersteUur, xBegin, xEind) {
      const ctx = t.ctx;
      const sterkte = LIJNSTERKTE[dag.betrouwbaarheid.code] || LIJNSTERKTE.hoog;
      const uren = dag.uren;
      const laatste = uren[uren.length - 1];
      const midden = (i) => t.x(eersteUur + i) + t.uurBreed / 2;
      const lijnLangs = (veld) => {   // van de linkerrand via het midden van elk uur naar de rechterrand
        ctx.moveTo(xBegin, t.y(uren[0][veld]));
        uren.forEach((u, i) => { ctx.lineTo(midden(i), t.y(u[veld])); });
        ctx.lineTo(xEind, t.y(laatste[veld]));
      };
      ctx.beginPath();
      lijnLangs('p90');
      ctx.lineTo(xEind, t.y(laatste.p10));
      for (let i = uren.length - 1; i >= 0; i--) ctx.lineTo(midden(i), t.y(uren[i].p10));
      ctx.lineTo(xBegin, t.y(uren[0].p10));
      ctx.closePath();
      ctx.globalAlpha = sterkte.band; ctx.fillStyle = t.kleur.band; ctx.fill();

      ctx.globalAlpha = sterkte.lijn;
      ctx.strokeStyle = t.kleur.lijn; ctx.lineWidth = sterkte.dikte; ctx.setLineDash([5, 4]);
      ctx.beginPath();
      lijnLangs('p50');
      ctx.stroke();
      ctx.setLineDash([]);
      ctx.globalAlpha = 1;
    }

    // onder de as: de dag en daaronder de betrouwbaarheid, ingekort als het niet past
    function tekenDaglabel(t, dag, xBegin, xEind) {
      const ctx = t.ctx;
      const ruimte = xEind - xBegin;
      const past = (tekst, marge) => ctx.measureText(tekst).width + marge < ruimte;
      const weekdag = WEEKDAGEN_KORT[dag.weekdag];
      ctx.fillStyle = t.kleur.tekst; ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic';
      const label = t.compact ? `${weekdag} ${dag.dagVdMaand}` : dagNaam(dag, false);
      ctx.fillText(!t.compact || past(label, 6) ? label : weekdag, xBegin + 4, t.onder + 16);

      const b = dag.betrouwbaarheid;
      ctx.fillStyle = t.kleur.zacht;
      const lang = `${b.icoon} ${b.label}`;
      if (past(lang, 8)) ctx.fillText(lang, xBegin + 4, t.onder + 30);
      else if (past(b.icoon, 8)) ctx.fillText(b.icoon, xBegin + 4, t.onder + 30);
    }

    // leeslijn onder de muis of vinger: een verticale stippellijn met een tekstvak
    function tekenLeeslijn(t) {
      const ctx = t.ctx;
      const uurOpAs = (hoverX - t.links) / t.uurBreed;
      if (uurOpAs < 0 || uurOpAs >= totaalUren) return;
      // welke dag, en welk uur of kwartier daarbinnen
      let rest = uurOpAs, dagIndex = 0, eersteUur = 0;
      while (rest >= dagen[dagIndex].uren.length) {
        rest -= dagen[dagIndex].uren.length;
        eersteUur += dagen[dagIndex].uren.length;
        dagIndex++;
      }
      const dag = dagen[dagIndex];
      const u = dag.reeks.find((e) => rest >= e.pos && rest < e.pos + e.duur) || dag.reeks[dag.reeks.length - 1];
      const x = t.x(eersteUur + u.pos) + (t.uurBreed * u.duur) / 2;

      ctx.strokeStyle = t.kleur.nu; ctx.lineWidth = 1; ctx.setLineDash([3, 3]);
      lijn(ctx, x, t.boven, x, t.onder);
      ctx.setLineDash([]);

      const regel1 = `${dagNaam(dag, false)} ${fmtUur(u.uur)}–${fmtUur(u.uur + u.duur)}`;
      const regel2 = u.bekend
        ? `${fmt(u.p50)} ct/kWh`
        : `verwacht ${fmt(u.p50)} (${plusMinCt(u.p90 - u.p50, u.p50 - u.p10)})`;
      ctx.fillStyle = t.kleur.nu;
      ctx.beginPath(); ctx.arc(x, t.y(u.p50), 4, 0, Math.PI * 2); ctx.fill();
      // tekstvak rechts van de lijn, of links als het rechts niet past
      ctx.font = (t.compact ? 11 : 12) + GRAFIEK_FONT;
      const vakBreed = Math.max(ctx.measureText(regel1).width, ctx.measureText(regel2).width) + 16;
      const vakX = x + 10 + vakBreed > t.rechts ? x - 10 - vakBreed : x + 10;
      const vakY = t.boven + 4;
      ctx.fillStyle = t.kleur.vlak; ctx.globalAlpha = 0.95;
      afgerondeRechthoek(ctx, vakX, vakY, vakBreed, 40, 4); ctx.fill();
      ctx.globalAlpha = 1;
      ctx.strokeStyle = t.kleur.raster;
      afgerondeRechthoek(ctx, vakX, vakY, vakBreed, 40, 4); ctx.stroke();
      ctx.textAlign = 'left';
      ctx.fillStyle = t.kleur.tekst; ctx.fillText(regel1, vakX + 8, vakY + 13);
      ctx.fillStyle = t.kleur.zacht; ctx.fillText(regel2, vakX + 8, vakY + 29);
    }

    function volg(ev) {
      const punt = ev.touches ? ev.touches[0] : ev;
      hoverX = punt.clientX - canvas.getBoundingClientRect().left;
      teken();
    }
    function laatLos() { hoverX = null; teken(); }
    canvas.addEventListener('mousemove', volg);
    canvas.addEventListener('mouseleave', laatLos);
    canvas.addEventListener('touchstart', volg, { passive: true });
    canvas.addEventListener('touchmove', volg, { passive: true });
    canvas.addEventListener('touchend', laatLos);
    if (window.ResizeObserver) new ResizeObserver(() => teken()).observe(canvas);
    else window.addEventListener('resize', teken);
    if (window.matchMedia) window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', teken);

    zetModel(model);
    teken();
    return {
      teken: teken,
      update: (nieuw) => { zetModel(nieuw); teken(); },
      markeer: (blokken) => { markering = blokken || []; teken(); },
    };
  }

  // ==================== 9. advies ====================

  // ---------- "start om ...": hoeveel uitstel stel ik nu in? (besluit 58, 85) ----------

  // Gemiddelde prijs van het blok [start, start + duur] op een tijdlijn van kwartieren, gewogen naar de tijd die
  // elk kwartier in het blok valt. null als het blok (deels) buiten de tijdlijn valt.
  function blokOpTijd(tijdlijn, start, duur) {
    const eind = start + duur;
    let gedekt = 0, som = 0, bekend = true;
    tijdlijn.forEach((u) => {
      const overlap = Math.min(eind, u.abs + u.duur) - Math.max(start, u.abs);
      if (overlap <= 1e-9) return;
      gedekt += overlap;
      som += overlap * u.p50;
      bekend = bekend && u.bekend;
    });
    if (gedekt < duur - 1e-6) return null;
    return { start: start, eind: eind, p50: som / gedekt, bekend: bekend };
  }
  // de dagen van het model achter elkaar, per kwartier; `abs` is de tijd in uren vanaf middernacht van de eerste dag
  function tijdlijnVan(dagen) {
    const uit = [];
    dagen.forEach((dag, i) => {
      naarKwartieren(dag.reeks).forEach((u) => { uit.push(Object.assign({}, u, { abs: i * 24 + u.uur })); });
    });
    return uit;
  }
  // het moment 'nu' op die tijdlijn; bij een verouderde voorspelling (de eerste dag is niet vandaag) het begin
  function nuOpTijdlijn(model, nuUur) {
    return model.dagen[0].datum === vandaagLokaal() ? nuUur : 0;
  }

  /*
   * startAdvies(model, apparaat, nuUur) -> advies of null
   *
   * De vraag is: "de machine is vol, zet ik hem nu aan of loont een paar uur wachten?" (besluit 67). Kandidaten
   * zijn de starttijden nu + k x stap (de uitstelstap van het apparaat), tot 12 uur vooruit en alleen zolang het
   * hele programma in uren met een vaste prijs valt (besluit 85): het advies is een som, geen verwachting. Voor de
   * publicatie van de prijzen voor de volgende dag (rond 13:30) kijkt het dus tot middernacht.
   * Binnen de grens die de gebruiker per apparaat toestaat (`maxUitstel`, standaard 8 uur) wint niet het
   * allergoedkoopste moment, maar het eerste dat bijna zo goedkoop is (binnen 2 cent of 5%): eerder is beter.
   * Scheelt dat met meteen starten minder dan 5 cent of 10%, dan is het advies 'nu'.
   *
   *   uitstel     uren uitstel om in te stellen (0 = nu)
   *   beste       { start, eind (uur van de dag), euro, isNu }
   *   nu          { euro }: wat meteen starten kost
   *   winst       euro goedkoper dan meteen starten (0 bij 'nu')
   *   maxWinst    wat wachten binnen de grens hooguit oplevert
   *   maxUitstel  de grens in uren
   *   verder      { uitstel, start, eind, euro, winst }: een moment na de grens maar binnen 12 uur dat duidelijk
   *               goedkoper is (10 cent en 20%), of null
   *   ingekort    true als de vaste prijzen eerder ophouden dan de grens
   */
  function startAdvies(model, apparaat, nuUur) {
    if (!model.dagen.length) return null;
    const tijdlijn = tijdlijnVan(model.dagen.slice(0, 2));
    const euro = (ct) => (ct * apparaat.kwh) / 100;

    const stap = apparaat.stap || 1;
    const eersteStart = nuOpTijdlijn(model, nuUur);
    const kandidaten = [];
    for (let k = 0; k * stap <= MAX_UITSTEL_UREN + 1e-9; k++) {
      const blok = blokOpTijd(tijdlijn, eersteStart + k * stap, apparaat.uren);
      if (!blok || !blok.bekend) break;
      blok.uitstel = k * stap;
      blok.euro = euro(blok.p50);
      kandidaten.push(blok);
    }
    if (!kandidaten.length) return null;
    const goedkoopste = (lijst) => lijst.reduce((beste, b) => (b.euro < beste.euro - 1e-9 ? b : beste));

    const maxUitstel = Math.min(MAX_UITSTEL_UREN, apparaat.maxUitstel || MAX_UITSTEL_STANDAARD);
    const meteen = kandidaten[0];
    const binnenGrens = kandidaten.filter((b) => b.uitstel <= maxUitstel + 1e-9);
    const laagste = goedkoopste(binnenGrens);
    // eerder is beter: het eerste moment dat bijna zo goedkoop is als het goedkoopste binnen de grens
    const bijna = laagste.euro + Math.max(START_BIJNA_EURO, START_BIJNA_DEEL * Math.abs(laagste.euro));
    const eerste = binnenGrens.find((b) => b.euro <= bijna);
    // wachten loont als het goedkoopste moment genoeg scheelt; het eerdere moment telt alleen als dat zelf ook genoeg scheelt
    const genoeg = Math.max(START_MIN_WINST_EURO, START_MIN_WINST_DEEL * Math.abs(meteen.euro));
    let gekozen = meteen;
    if (meteen.euro - laagste.euro >= genoeg) gekozen = meteen.euro - eerste.euro >= genoeg ? eerste : laagste;

    const alsMoment = (b) => ({ uitstel: b.uitstel, start: b.start % 24, eind: b.eind % 24, euro: b.euro });
    const advies = {
      uitstel: gekozen.uitstel,
      beste: Object.assign(alsMoment(gekozen), { isNu: gekozen.uitstel === 0 }),
      nu: { euro: meteen.euro },
      winst: meteen.euro - gekozen.euro,
      maxWinst: meteen.euro - laagste.euro,
      maxUitstel: maxUitstel,
      verder: null,
      ingekort: kandidaten[kandidaten.length - 1].uitstel + stap <= maxUitstel + 1e-9,
    };
    // na de grens maar binnen 12 uur: alleen noemen als het duidelijk goedkoper is
    const naGrens = kandidaten.filter((b) => b.uitstel > maxUitstel + 1e-9);
    if (naGrens.length) {
      const later = goedkoopste(naGrens);
      const duidelijkMinder = gekozen.euro - Math.max(ANDERE_DAG_MIN_EURO, ANDERE_DAG_MIN_DEEL * Math.abs(gekozen.euro));
      if (later.euro < duidelijkMinder) {
        advies.verder = Object.assign(alsMoment(later), { winst: gekozen.euro - later.euro });
      }
    }
    return advies;
  }

  // ---------- "klaar op welke dag?": wat kost de laadbeurt van een auto, per dag (besluit 85) ----------

  // De laadbeurt in het venster [start, klaar] (uren op de tijdlijn): de goedkoopste kwartieren tot `nodig` uren
  // vol zijn, zoals een leverancier die slim laadt het ook doet. De uren hoeven niet aaneen te liggen.
  // null als de tijdlijn het venster niet helemaal dekt.
  function laadBeurt(tijdlijn, start, klaar, nodig, kw) {
    const stukken = [];
    let gedekt = 0, zeker = true;
    tijdlijn.forEach((u) => {
      const van = Math.max(start, u.abs), tot = Math.min(klaar, u.abs + u.duur);
      if (tot - van <= 1e-9) return;
      stukken.push({ van: van, tot: tot, u: u });
      gedekt += tot - van;
      zeker = zeker && u.bekend;
    });
    if (!stukken.length || gedekt < klaar - start - 1e-6) return null;

    const opPrijs = stukken.slice().sort((a, b) => (a.u.p50 - b.u.p50) || (a.van - b.van));
    let rest = nodig, euro = 0, euroLaag = 0, euroHoog = 0;
    const gekozen = [];
    opPrijs.forEach((stuk) => {
      if (rest <= 1e-9) return;
      const duur = Math.min(stuk.tot - stuk.van, rest);
      const kwh = kw * duur;
      euro += (stuk.u.p50 * kwh) / 100;
      euroLaag += (stuk.u.p10 * kwh) / 100;
      euroHoog += (stuk.u.p90 * kwh) / 100;
      gekozen.push({ start: stuk.van, eind: stuk.van + duur });
      rest -= duur;
    });
    // aansluitende kwartieren samen tot blokken
    gekozen.sort((a, b) => a.start - b.start);
    const blokken = [];
    gekozen.forEach((stuk) => {
      const vorige = blokken[blokken.length - 1];
      if (vorige && stuk.start <= vorige.eind + 1e-9) vorige.eind = Math.max(vorige.eind, stuk.eind);
      else blokken.push({ start: stuk.start, eind: stuk.eind });
    });
    // van en tot op hele kwartieren, voor de tekst: het laatste kwartier wordt zelden helemaal gebruikt
    return {
      klaar: klaar, blokken: blokken,
      van: Math.floor(blokken[0].start * 4 + 1e-6) / 4, tot: Math.ceil(blokken[blokken.length - 1].eind * 4 - 1e-6) / 4,
      euro: euro, euroLaag: euroLaag, euroHoog: euroHoog, zeker: zeker, teKort: rest > 1e-6,
    };
  }

  /*
   * laadAdvies(model, auto, nuUur) -> advies of null
   *
   * Voor de eerstvolgende drie dagen waarop de auto op tijd klaar kan zijn: wat de laadbeurt kost als de auto op
   * die dag om `klaar` vol moet zijn. Het venster loopt van `vanaf` tot `klaar`; staat `klaar` niet later op de dag
   * dan `vanaf`, dan begint het venster de dag ervoor (18:00 tot 07:00). Van het eerste venster tellen alleen de
   * uren die nog komen.
   *
   *   dagen        [{ dag (de dag waarop de auto klaar is), klaar, blokken [{ start, eind }], van, tot, euro,
   *                   euroLaag, euroHoog, zeker (alle prijzen in het venster staan vast), zwak, teKort }]
   *                tijden in uren vanaf middernacht van de eerste dag van het model
   *   eerste       de eerste dag uit `dagen`
   *   goedkoopste  de goedkoopste dag uit `dagen`
   */
  function laadAdvies(model, auto, nuUur) {
    if (!model.dagen.length) return null;
    const tijdlijn = tijdlijnVan(model.dagen);
    const nu = nuOpTijdlijn(model, nuUur);
    const venster = ((auto.klaar - auto.vanaf + 24) % 24) || 24;
    const nodig = laadUren(auto);
    const dagen = [];
    for (let d = 0; d < model.dagen.length && dagen.length < LAAD_DAGEN; d++) {
      const klaar = d * 24 + auto.klaar;
      const start = Math.max(klaar - venster, nu);
      // te laat voor deze dag: er is minder tijd over dan de laadbeurt (of het hele venster) vraagt
      if (klaar - start < Math.min(nodig, venster) - 1e-9) continue;
      const beurt = laadBeurt(tijdlijn, start, klaar, nodig, auto.kw);
      if (!beurt) continue;
      const dag = model.dagen[d];
      dagen.push(Object.assign(beurt, { dag: dag, zwak: dag.betrouwbaarheid.code === 'laag' }));
    }
    if (!dagen.length) return null;
    return {
      auto: auto, dagen: dagen, eerste: dagen[0],
      goedkoopste: dagen.reduce((beste, d) => (d.euro < beste.euro - 1e-9 ? d : beste)),
    };
  }

  // ==================== 10. gegevens ophalen ====================

  function laadForecast(url) {
    return fetch(url, { cache: 'no-store' }).then((antwoord) => {
      if (!antwoord.ok) throw new Error(`Kon de voorspelling niet laden (${antwoord.status}).`);
      return antwoord.json();
    });
  }
  // { peildatum_lijst, leveranciers: [{ naam, inkoopvergoeding_ct_kwh_excl_btw, status, peildatum, ... }] };
  // zonder lijst werkt de pagina ook, dan vult de gebruiker de inkoopvergoeding zelf in
  function laadLeveranciers(url) {
    const leeg = { leveranciers: [] };
    return fetch(url, { cache: 'no-store' })
      .then((antwoord) => (antwoord.ok ? antwoord.json() : leeg))
      .catch(() => leeg);
  }

  // Wat index.html en uitleg.html gebruiken. Al het andere in dit bestand is intern.
  window.SP = {
    // opmaak
    fmt: fmt, fmtKort: fmtKort, fmtUur: fmtUur, fmtEuro: fmtEuro, duurTekst: duurTekst, plusMinEuro: plusMinEuro,
    dagNaam: dagNaam, weekdagNaam: (dag) => WEEKDAGEN[dag.weekdag], datumTekst: datumTekst,
    gegenereerdTekst: gegenereerdTekst, esc: esc,
    // klok
    vandaagLokaal: vandaagLokaal, morgenLokaal: morgenLokaal, nuLokaalUur: nuLokaalUur,
    msTotMiddernacht: msTotMiddernacht,
    // model en zinnen
    STOPLICHT: STOPLICHT, verwerk: verwerk, bandZin: bandZin, tariefUitlegTekst: tariefUitlegTekst,
    // instellingen
    leesTarief: leesTarief, leesResolutie: leesResolutie, leesApparaten: leesApparaten,
    koppelResolutie: koppelResolutie, koppelApparaten: koppelApparaten, koppelAutos: koppelAutos,
    koppelTarief: koppelTarief,
    // tabel, grafiek, advies
    maakTabel: maakTabel, tekenGrafiek: tekenGrafiek, startAdvies: startAdvies, laadAdvies: laadAdvies,
    laadDrempelEuro: 0.5,   // onder dit verschil met de eerste dag zegt de pagina "scheelt weinig"
    laadKlaarKeuzes: LAAD_KLAAR_KEUZES,
    // gegevens
    laadForecast: laadForecast, laadLeveranciers: laadLeveranciers,
  };
})();
