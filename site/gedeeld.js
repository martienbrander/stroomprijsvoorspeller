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
 *   6. instellingen            lezen, bewaren en de formulieren koppelen (resolutie, apparaten, auto, tarief)
 *   7. tabel                   dezelfde cijfers als de grafiek, als tabel
 *   8. grafiek                 op een <canvas>, zonder bibliotheek
 *   9. advies                  "start je apparaat om ..." (besluit 58) en "de auto: nu of later?"
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
  const LADEN_SLEUTEL = 'stroomprijs-laden-v1';         // { kw, kwh, horizon }
  const APPARATEN_SLEUTEL = 'stroomprijs-apparaten-v1'; // [{ id, naam, uren, kwh, stap }]

  // eigen apparaten (besluit 55, 63)
  const APPARATEN_STANDAARD = [{ id: 'was', naam: 'Wasmachine', uren: 2, kwh: 1, stap: 1, maxUitstel: 8 }];
  const MAX_UITSTEL_KEUZES = [4, 6, 8, 12, 16, 24];  // hoeveel uitstel iemand hooguit wil, per apparaat (besluit 67)
  const MAX_UITSTEL_STANDAARD = 8;
  // Twee soorten apparaten (besluit 73): 'start' = vandaag of morgen aanzetten met uitstel, 'laden' = deze week
  // laden op de goedkoopste dag, met een horizon in dagen.
  const HORIZON_KEUZES = [2, 3, 5, 7];
  const HORIZON_STANDAARD = 5;
  const WEEK_MIN_WINST_EURO = 0.10;   // eigen laadapparaat: wachten moet 10 cent ...
  const WEEK_MIN_WINST_DEEL = 0.10;   // ... en 10% schelen; voor de auto geldt LAAD_DREMPEL_EURO
  const UITSTEL_STAPPEN = [1, 0.5, 0.25];  // waarin het uitstel op het apparaat is in te stellen (uren)
  const UITSTEL_LABELS = { 1: '1 uur', 0.5: 'half uur', 0.25: 'kwartier' };
  const MINUTEN_KEUZES = [0, 15, 30, 45];
  const KWARTIER = 0.25;
  const MAX_DUUR_UREN = 24;

  // de auto (besluit 32, 63): zonder instellingen een blok van 3 uur en 30 kWh
  const LAAD_STANDAARD_UREN = 3;
  const LAAD_STANDAARD_KWH = 30;
  const LAAD_KEUZES_KW = [2.3, 3.7, 7.4, 11, 22];
  const LAAD_DREMPEL_EURO = 0.5;     // onder dit verschil: "doe het wanneer het uitkomt"

  // startadvies (besluit 58)
  const MAX_UITSTEL_UREN = 24;       // verder dan 24 uur vooruit kijkt het advies nooit (besluit 66)
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
  // bedrag per handeling: onder de euro in centen, altijd zonder minteken
  function fmtEuro(x) {
    if (ontbreekt(x)) return '–';
    const bedrag = Math.abs(x);
    return bedrag < 1 ? `${Math.round(bedrag * 100)} cent` : `€ ${bedrag.toFixed(2).replace('.', ',')}`;
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
  function plusMinCt(plus, min) { return `+${fmt(plus)} / −${fmt(min)} ct`; }
  function plusMinEuro(plus, min) { return `+${fmtEuro(plus)} / −${fmtEuro(min)}`; }

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
   * verwerk(forecast, tarief, laadInstellingen, resolutie, apparaten) -> model
   *
   * model = { dagen, laad, apparaten, scores, gegenereerd, eenheidLabel }
   * dag   = { datum, weekdag, dagVdMaand, maand, index, feestdag, bekend, betrouwbaarheid,
   *           uren, kwartieren, reeks (wat getekend en doorzocht wordt), perKwartier, perUur,
   *           gem, min, max, dagdelen, laden (goedkoopste laadblok), blokken (per apparaat-id) }
   * uur   = { uur, duur (in uren: 1 of 0,25), pos (uren vanaf het begin van de dag), bekend,
   *           p10, p50, p90 (ct/kWh in de gekozen stand), stoplicht }
   */
  function verwerk(forecast, tarief, laadInstellingen, resolutie, apparaten) {
    tarief = netTarief(tarief);
    apparaten = apparaten && apparaten.length ? apparaten : APPARATEN_STANDAARD;
    const factor = tariefFactor(tarief);
    const laad = {
      inst: laadInstellingen || null,
      uren: laadBlokUren(laadInstellingen),
      kwh: laadKwh(laadInstellingen),
      horizon: geldigeHorizon(laadInstellingen && laadInstellingen.horizon),
    };
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
    dagen.forEach((dag, i) => { zoekBlokken(dag, dagen[i + 1], laad, apparaten); });
    zetStoplicht(dagen);

    return {
      dagen: dagen,
      laad: laad,
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

  // ---------- goedkoopste blokken ----------

  // De blokken van één dag: het laadblok van de auto en per eigen apparaat een blok ter lengte van de duur.
  // Laden mag over middernacht doorlopen in de volgende dag; een apparaat blijft binnen de dag.
  function zoekBlokken(dag, volgendeDag, laad, apparaten) {
    const stap = dag.perKwartier ? KWARTIER : 1;
    let vervolg = [];
    if (volgendeDag) vervolg = stap === 1 ? volgendeDag.uren : naarKwartieren(volgendeDag.reeks);

    dag.laden = goedkoopsteBlok(dag.reeks, Math.round(laad.uren / stap), vervolg);
    if (dag.laden) {
      dag.laden.onzekereDag = dag.betrouwbaarheid.code === 'laag';
      [dag.laden, dag.laden.duurste].forEach((blok) => {
        if (blok.volgendeDag) blok.eindDagNaam = dagNaam(volgendeDag, false);
      });
    }
    dag.blokken = {};
    apparaten.forEach((a) => {
      dag.blokken[a.id] = goedkoopsteBlok(dag.reeks, Math.max(1, Math.round(a.uren / stap)));
    });
  }

  // Goedkoopste aaneengesloten blok van n elementen (op P50) dat in `reeks` begint; het mag doorlopen in
  // `vervolg` (het begin van de volgende dag). Het duurste blok van dezelfde lengte gaat mee, voor de
  // vergelijking. null als er te weinig uren zijn.
  function goedkoopsteBlok(reeks, n, vervolg = []) {
    const alles = reeks.concat(vervolg);
    if (!reeks.length || alles.length < n) return null;
    let beste = null, duurste = null;
    const laatsteStart = Math.min(reeks.length - 1, alles.length - n);
    for (let i = 0; i <= laatsteStart; i++) {
      const blok = maakBlok(alles.slice(i, i + n), i + n > reeks.length);
      if (!beste || blok.p50 < beste.p50) beste = blok;
      if (!duurste || blok.p50 > duurste.p50) duurste = blok;
    }
    const dagGemiddelde = gemiddeldeVan(reeks, 'p50');
    beste.marge = dagGemiddelde - beste.p50;      // ct/kWh goedkoper dan het daggemiddelde (kan net negatief zijn)
    beste.duurste = duurste;
    beste.vsDuurste = duurste.p50 - beste.p50;    // ct/kWh goedkoper dan het duurste blok van dezelfde lengte
    return beste;
  }
  function maakBlok(elementen, loopDoor) {
    const laatste = elementen[elementen.length - 1];
    const duur = elementen.reduce((som, u) => som + u.duur, 0);
    const p10 = gemiddeldeVan(elementen, 'p10');
    const p50 = gemiddeldeVan(elementen, 'p50');
    const p90 = gemiddeldeVan(elementen, 'p90');
    return {
      start: elementen[0].uur, eind: laatste.uur + laatste.duur, n: Math.round(duur * 100) / 100,  // n = duur in uren
      volgendeDag: !!loopDoor, eindDagNaam: null,
      p10: p10, p50: p50, p90: p90, onzekerPlus: p90 - p50, onzekerMin: p50 - p10,
      bekend: elementen.every((u) => u.bekend),
    };
  }
  // kosten van een blok in euro voor `kwh` kilowattuur
  function blokKosten(blok, kwh) {
    const euro = (ct) => (ct * kwh) / 100;
    return {
      euro: euro(blok.p50), plus: euro(blok.onzekerPlus || 0), min: euro(blok.onzekerMin || 0),
      vsDuurste: euro(blok.vsDuurste || 0), vsGem: euro(blok.marge || 0),
    };
  }

  // ==================== 5. zinnen ====================

  // '23:45–02:45 (loopt door tot wo 18 nov)'
  function blokTijd(blok) {
    if (!blok) return '';
    const tijd = `${fmtUur(blok.start)}–${fmtUur(blok.eind)}`;
    if (!blok.volgendeDag) return tijd;
    return `${tijd} (loopt door tot ${blok.eindDagNaam || 'de volgende dag'})`;
  }
  // "21,1 ct/kWh, € 6,33 voor 30 kWh. € 2,40 minder dan op het duurste moment, € 1,23 minder dan gemiddeld."
  function laadZin(blok, kwh) {
    if (!blok) return '';
    const k = blokKosten(blok, kwh);
    let tovGemiddeld = 'gelijk aan gemiddeld.';
    if (k.vsGem > 0.005) tovGemiddeld = `${fmtEuro(k.vsGem)} minder dan gemiddeld.`;
    else if (k.vsGem < -0.005) tovGemiddeld = `${fmtEuro(-k.vsGem)} meer dan gemiddeld.`;
    let zin = `${fmt(blok.p50)} ct/kWh, ${fmtEuro(k.euro)} voor ${fmtKort(kwh)} kWh. ` +
      `${fmtEuro(k.vsDuurste)} minder dan op het duurste moment, ${tovGemiddeld}`;
    if (!blok.bekend) zin += ` Onzeker: ${plusMinEuro(k.plus, k.min)}.`;
    if (blok.onzekereDag) zin += ' Nog onzeker, kijk een dag later opnieuw.';
    return zin;
  }
  // "34,2 ct/kWh, 34 cent per beurt, 5 cent minder dan op het duurste moment."
  function apparaatZin(blok, kwh) {
    if (!blok) return '';
    const k = blokKosten(blok, kwh);
    let zin = `${fmt(blok.p50)} ct/kWh, ${fmtEuro(k.euro)} per beurt`;
    if (k.vsDuurste > 0.005) zin += `, ${fmtEuro(k.vsDuurste)} minder dan op het duurste moment`;
    if (!blok.bekend) zin += ` (${plusMinEuro(k.plus, k.min)})`;
    return `${zin}.`;
  }
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
  function betrouwbaarheidHtml(dag) {
    const b = dag.betrouwbaarheid;
    return `<span class="btr ${b.klasse}"><span class="btr-icoon" aria-hidden="true">${b.icoon}</span>` +
      `${betrouwbaarheidTekst(dag, false)}</span>`;
  }
  function stoplichtHtml(kleur) {
    const s = STOPLICHT[kleur];
    return `<span class="sl ${s.klasse}"><span class="sl-icoon" aria-hidden="true">${s.icoon}</span>${s.label}</span>`;
  }
  const dagdelenTekst = (dag) => dag.dagdelen.map((deel) => `${deel.label.toLowerCase()} ${deel.stoplicht}`).join(', ');

  // de hele voorspelling in woorden, voor schermlezers (als beschrijving van de grafiek)
  function samenvatting(model) {
    return model.dagen.map((dag) => {
      let zin = `${dagNaam(dag, true)}: `;
      if (dag.bekend) zin += `bekend, gemiddeld ${fmt(dag.gem)} ct/kWh, van ${fmt(dag.min)} tot ${fmt(dag.max)}.`;
      else zin += `voorspeld, ${betrouwbaarheidTekst(dag, false)}, gemiddeld rond ${fmt(dag.gem)} ct/kWh.`;
      zin += ` Dagdelen: ${dagdelenTekst(dag)}.`;
      if (dag.laden) zin += ` Goedkoopste ${duurTekst(dag.laden.n)} om te laden: ${blokTijd(dag.laden)}.`;
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
  // apparaat = { id, naam, uren (duur, per kwartier), kwh (per beurt), stap (uitstelstap op het apparaat, in uren) }

  const standaardApparaten = () => APPARATEN_STANDAARD.map((a) => Object.assign({}, a));
  const geldigeStap = (stap) => (UITSTEL_STAPPEN.indexOf(Number(stap)) >= 0 ? Number(stap) : 1);
  const geldigMaxUitstel = (uren) =>
    (MAX_UITSTEL_KEUZES.indexOf(Number(uren)) >= 0 ? Number(uren) : MAX_UITSTEL_STANDAARD);
  const geldigeHorizon = (dagen) =>
    (HORIZON_KEUZES.indexOf(Number(dagen)) >= 0 ? Number(dagen) : HORIZON_STANDAARD);
  const geldigeSoort = (soort) => (soort === 'laden' ? 'laden' : 'start');

  function leesApparaten() {
    try {
      const bewaard = lees(APPARATEN_SLEUTEL);
      if (!bewaard) return standaardApparaten();
      return JSON.parse(bewaard).filter((a) => a && a.uren > 0).map((a, i) => ({
        id: String(a.id || `app${i}`),
        naam: String(a.naam || 'Apparaat'),
        uren: Math.min(MAX_DUUR_UREN, Number(a.uren)),
        kwh: a.kwh > 0 ? Number(a.kwh) : 1,
        stap: geldigeStap(a.stap),
        maxUitstel: geldigMaxUitstel(a.maxUitstel),
        soort: geldigeSoort(a.soort),
        horizon: geldigeHorizon(a.horizon),
      }));
    } catch (e) { return standaardApparaten(); }
  }
  function bewaarApparaten(lijst) { bewaar(APPARATEN_SLEUTEL, JSON.stringify(lijst)); }

  function apparaatRijHtml(a, i) {
    const duur = splitsUren(a.uren);
    const minuten = MINUTEN_KEUZES.map((m) => optieHtml(m, m, duur.minuten === m)).join('');
    const stappen = UITSTEL_STAPPEN
      .map((stap) => optieHtml(stap, UITSTEL_LABELS[stap], Math.abs((a.stap || 1) - stap) < 1e-9)).join('');
    const maxKeuzes = MAX_UITSTEL_KEUZES
      .map((uren) => optieHtml(uren, `${uren} uur`, geldigMaxUitstel(a.maxUitstel) === uren)).join('');
    const laden = a.soort === 'laden';
    const soorten = optieHtml('start', 'Vandaag starten', !laden) + optieHtml('laden', 'Laden deze week', laden);
    const horizonKeuzes = HORIZON_KEUZES
      .map((dagen) => optieHtml(dagen, `${dagen} dagen`, geldigeHorizon(a.horizon) === dagen)).join('');
    // een laadapparaat heeft een horizon in dagen, een startapparaat een uitstelstap en een grens in uren
    const planning = laden
      ? `<label>Vooruitkijken<select name="horizon">${horizonKeuzes}</select></label>`
      : `<label>Uitstelstap<select name="stap">${stappen}</select></label>` +
        `<label>Hoogstens uitstel<select name="max">${maxKeuzes}</select></label>`;
    return [
      `<div class="app-rij${laden ? ' laden' : ''}" data-i="${i}">`,
      `<label>Apparaat<input type="text" name="naam" value="${esc(a.naam)}" maxlength="30"`,
      ' placeholder="bijv. vaatwasser"></label>',
      `<label>Uren<input type="number" name="uren" value="${duur.uren}" step="1" min="0" max="24"`,
      ' inputmode="numeric"></label>',
      `<label>Minuten<select name="min">${minuten}</select></label>`,
      `<label>Verbruik (kWh)<input type="number" name="kwh" value="${a.kwh}" step="0.1" min="0.1"`,
      ' inputmode="decimal"></label>',
      `<label>Soort<select name="soort">${soorten}</select></label>`,
      planning,
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
        // de velden die bij de andere soort horen staan niet in de rij: die houden hun vorige waarde
        stap: veld('stap') ? geldigeStap(parseFloat(veld('stap').value)) : geldigeStap(vorige.stap),
        maxUitstel: veld('max') ? geldigMaxUitstel(parseFloat(veld('max').value)) : geldigMaxUitstel(vorige.maxUitstel),
        soort: geldigeSoort(veld('soort').value),
        horizon: veld('horizon') ? geldigeHorizon(parseFloat(veld('horizon').value)) : geldigeHorizon(vorige.horizon),
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
        lijst.push({ id: `app${Date.now()}`, naam: '', uren: 1, kwh: 1, soort: 'start' });
        teken();
        const naamVeld = container.querySelector('.app-rij:last-of-type [name=naam]');
        if (naamVeld) naamVeld.focus();
      }
    });
    teken();
    return lijst;
  }

  // ---------- de auto: laadvermogen en hoeveelheid (besluit 32, 63) ----------
  // instellingen = { kw, kwh, horizon } (kw en kwh een getal of null; horizon in dagen), of null als er niets is
  // ingevuld

  const positief = (x) => (x > 0 ? x : null);
  const volledig = (inst) => !!inst && inst.kw > 0 && inst.kwh > 0;

  function leesLaadinstellingen() {
    try {
      const bewaard = lees(LADEN_SLEUTEL);
      if (!bewaard) return null;
      const inst = JSON.parse(bewaard);
      return { kw: positief(inst.kw), kwh: positief(inst.kwh), horizon: geldigeHorizon(inst.horizon) };
    } catch (e) { return null; }
  }
  function bewaarLaadinstellingen(inst) {
    bewaar(LADEN_SLEUTEL, inst ? JSON.stringify(inst) : null);
  }
  // Lengte van het laadblok in uren: kWh / kW, naar boven afgerond op een kwartier, minstens een kwartier en
  // hoogstens een dag. Zonder volledige instellingen 3 uur.
  function laadBlokUren(inst) {
    if (!volledig(inst)) return LAAD_STANDAARD_UREN;
    const kwartieren = Math.ceil(inst.kwh / inst.kw * 4 - 1e-9);
    return Math.min(MAX_DUUR_UREN, Math.max(KWARTIER, kwartieren * KWARTIER));
  }
  function laadKwh(inst) { return inst && inst.kwh > 0 ? inst.kwh : LAAD_STANDAARD_KWH; }
  function laadUitleg(inst) {
    if (volledig(inst)) {
      return `${fmtKort(inst.kwh)} kWh bij ${fmtKort(inst.kw)} kW: laden duurt ${duurTekst(laadBlokUren(inst))} ` +
        '(afgerond op een kwartier).';
    }
    return `Standaard: ${LAAD_STANDAARD_KWH} kWh in een blok van ${LAAD_STANDAARD_UREN} uur. ` +
      'Vul laadsnelheid en hoeveelheid in voor uw eigen laadbeurt.';
  }

  // formulier met select[name=kw] (met de optie "anders"), input[name=kw-anders] in een .kw-anders,
  // input[name=kwh], select[name=horizon] (dagen vooruit) en een element .laad-uitleg
  function koppelLaadinstellingen(formulier, bijWijziging) {
    const kwKeuze = formulier.querySelector('[name=kw]');
    const kwAnders = formulier.querySelector('[name=kw-anders]');
    const kwhVeld = formulier.querySelector('[name=kwh]');
    const horizonKeuze = formulier.querySelector('[name=horizon]');
    const uitleg = formulier.querySelector('.laad-uitleg');

    const bewaard = leesLaadinstellingen();
    if (bewaard && bewaard.kw) {
      const keuze = LAAD_KEUZES_KW.find((kw) => Math.abs(kw - bewaard.kw) < 0.01);
      if (keuze !== undefined) kwKeuze.value = String(keuze);
      else { kwKeuze.value = 'anders'; kwAnders.value = bewaard.kw; }
    }
    if (bewaard && bewaard.kwh) kwhVeld.value = bewaard.kwh;
    if (horizonKeuze) {
      horizonKeuze.innerHTML = HORIZON_KEUZES.map((dagen) => optieHtml(dagen, `${dagen} dagen`, false)).join('');
      horizonKeuze.value = String(geldigeHorizon(bewaard && bewaard.horizon));
    }

    function huidig() {
      const kw = positief(leesGetal(kwKeuze.value === 'anders' ? kwAnders : kwKeuze));
      const kwh = positief(leesGetal(kwhVeld));
      const horizon = geldigeHorizon(horizonKeuze && horizonKeuze.value);
      return kw || kwh || horizon !== HORIZON_STANDAARD ? { kw: kw, kwh: kwh, horizon: horizon } : null;
    }
    function toonAndersVeld() { (kwAnders.closest('.kw-anders') || kwAnders).hidden = kwKeuze.value !== 'anders'; }
    function toonUitleg() { if (uitleg) uitleg.textContent = laadUitleg(huidig()); }
    function toepassen() {
      const inst = huidig();
      bewaarLaadinstellingen(inst);
      toonUitleg();
      bijWijziging(inst);
    }
    kwKeuze.addEventListener('change', () => { toonAndersVeld(); toepassen(); });
    kwAnders.addEventListener('change', toepassen);
    kwhVeld.addEventListener('change', toepassen);
    if (horizonKeuze) horizonKeuze.addEventListener('change', toepassen);
    formulier.addEventListener('submit', (ev) => { ev.preventDefault(); toepassen(); });
    toonAndersVeld();
    toonUitleg();
    return huidig();
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
    lijn: ['--g-lijn', '#1f5fbf'], bekend: ['--g-bekend', '#1f5fbf'], band: ['--g-band', '#1f5fbf'],
    nu: ['--g-nu', '#d9480f'], vlak: ['--g-vlak', '#ffffff'],
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
   * tekenGrafiek(canvas, model, opties) -> { teken(), update(model) }
   * opties: { maxDagen, hoogte, compact }
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
    return { teken: teken, update: (nieuw) => { zetModel(nieuw); teken(); } };
  }

  // ==================== 9. advies ====================

  // ---------- "start je apparaat om ...": hoeveel uitstel stel ik nu in? (besluit 58) ----------

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

  /*
   * startAdvies(model, apparaat, nuUur) -> advies of null
   *
   * De vraag is: "de machine is vol, zet ik hem nu aan of loont een paar uur wachten?" (besluit 67). Kandidaten
   * zijn de starttijden nu + k x stap (de uitstelstap van het apparaat). Binnen de grens die de gebruiker per
   * apparaat toestaat (`maxUitstel`, standaard 8 uur) wint niet het allergoedkoopste moment, maar het eerste dat
   * bijna zo goedkoop is (binnen 2 cent of 5%): eerder is beter. Scheelt dat met meteen starten minder dan
   * 5 cent of 10%, dan is het advies 'nu'.
   * Is de eerste getoonde dag niet vandaag (een verouderde voorspelling), dan geldt die dag als venster vanaf 0:00.
   *
   *   uitstel     uren uitstel om in te stellen (0 = nu)
   *   beste       { start, eind (uur van de dag), dagStart, euro, bekend, isNu }
   *   nu          { euro }: wat meteen starten kost
   *   winst       euro goedkoper dan meteen starten (0 bij 'nu')
   *   maxWinst    wat wachten binnen de grens hooguit oplevert
   *   maxUitstel  de grens in uren
   *   verder      { uitstel, start, eind, dagStart, euro, winst, bekend }: een moment na de grens maar binnen
   *               24 uur dat duidelijk goedkoper is (10 cent en 20%), of null
   *   andereDag   { dag, blok, euro, winst }: een latere dag die duidelijk goedkoper is, of null
   */
  function startAdvies(model, apparaat, nuUur) {
    const [vandaag, morgen] = model.dagen;
    if (!vandaag) return null;
    // tijd in uren vanaf middernacht van de eerste dag: morgen 02:00 is 26
    const opTijdlijn = (dag, verschuiving) =>
      naarKwartieren(dag.reeks).map((u) => Object.assign({}, u, { abs: u.uur + verschuiving }));
    const tijdlijn = opTijdlijn(vandaag, 0).concat(morgen ? opTijdlijn(morgen, 24) : []);
    const dagVan = (tijd) => (tijd >= 24 && morgen ? morgen : vandaag);
    const euro = (ct) => (ct * apparaat.kwh) / 100;

    // alle starttijden tot 24 uur vooruit, zolang het blok binnen de bekende reeks valt
    const stap = apparaat.stap || 1;
    const eersteStart = vandaag.datum === vandaagLokaal() ? nuUur : 0;
    const kandidaten = [];
    for (let k = 0; k * stap <= MAX_UITSTEL_UREN + 1e-9; k++) {
      const blok = blokOpTijd(tijdlijn, eersteStart + k * stap, apparaat.uren);
      if (!blok) break;
      blok.uitstel = k * stap;
      blok.euro = euro(blok.p50);
      kandidaten.push(blok);
    }
    if (!kandidaten.length) return null;
    const goedkoopste = (lijst) => lijst.reduce((beste, b) => (b.euro < beste.euro - 1e-9 ? b : beste));
    const duidelijkMinder = (bedrag) => bedrag - Math.max(ANDERE_DAG_MIN_EURO, ANDERE_DAG_MIN_DEEL * Math.abs(bedrag));

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

    const alsMoment = (b) => ({
      uitstel: b.uitstel, start: b.start % 24, eind: b.eind % 24, dagStart: dagVan(b.start),
      euro: b.euro, bekend: b.bekend,
    });
    const advies = {
      uitstel: gekozen.uitstel,
      beste: Object.assign(alsMoment(gekozen), { isNu: gekozen.uitstel === 0 }),
      nu: { euro: meteen.euro },
      winst: meteen.euro - gekozen.euro,
      maxWinst: meteen.euro - laagste.euro,
      maxUitstel: maxUitstel,
      verder: null,
      andereDag: null,
    };
    // na de grens maar binnen 24 uur: alleen noemen als het duidelijk goedkoper is
    const naGrens = kandidaten.filter((b) => b.uitstel > maxUitstel + 1e-9);
    if (naGrens.length) {
      const later = goedkoopste(naGrens);
      if (later.euro < duidelijkMinder(gekozen.euro)) {
        advies.verder = Object.assign(alsMoment(later), { winst: gekozen.euro - later.euro });
      }
    }
    // een latere dag (na morgen, niet 'onzeker') die minstens 20% en 10 cent goedkoper is
    const drempel = duidelijkMinder(gekozen.euro);
    model.dagen.slice(morgen ? 2 : 1).forEach((dag) => {
      const blok = dag.blokken[apparaat.id];
      if (!blok || dag.betrouwbaarheid.code === 'laag') return;
      const kosten = euro(blok.p50);
      if (kosten < drempel && (!advies.andereDag || kosten < advies.andereDag.euro)) {
        advies.andereDag = { dag: dag, blok: blok, euro: kosten, winst: gekozen.euro - kosten };
      }
    });
    return advies;
  }

  // ---------- "laden deze week": welke dag en welk blok (besluit 73) ----------

  // De apparaten die per week geladen worden: de auto (uit de laadinstellingen) en eigen apparaten van de soort
  // 'laden'. Bij de auto raden we wachten alleen aan als het ook in het slechte geval loont (streng).
  function laadApparaten(model) {
    const auto = {
      id: 'auto', naam: 'Auto', auto: true, streng: true,
      kwh: model.laad.kwh, uren: model.laad.uren, horizon: model.laad.horizon,
    };
    const eigen = model.apparaten.filter((a) => a.soort === 'laden').map((a) => ({
      id: a.id, naam: a.naam, auto: false, streng: false, kwh: a.kwh, uren: a.uren, horizon: geldigeHorizon(a.horizon),
    }));
    return [auto].concat(eigen);
  }

  // het goedkoopste blok van een dag voor dit apparaat; van vandaag tellen alleen de uren die nog komen
  function weekBlok(model, apparaat, dag, nuUur) {
    const kant = apparaat.auto ? dag.laden : dag.blokken[apparaat.id];
    if (dag.datum !== vandaagLokaal()) return kant;
    const volgende = model.dagen[dag.index + 1];
    const stap = dag.perKwartier ? KWARTIER : 1;
    const straks = dag.reeks.filter((u) => u.uur >= nuUur - 1e-9);
    let vervolg = [];
    if (apparaat.auto && volgende) vervolg = stap === 1 ? volgende.uren : naarKwartieren(volgende.reeks);
    const blok = goedkoopsteBlok(straks, Math.max(1, Math.round(apparaat.uren / stap)), vervolg);
    if (blok && blok.volgendeDag && volgende) blok.eindDagNaam = dagNaam(volgende, false);
    return blok;
  }

  /*
   * weekAdvies(model, apparaat, nuUur) -> advies of null
   *
   * Per dag binnen de horizon het goedkoopste blok en wat de laadbeurt dan kost. Het advies vergelijkt de eerste
   * mogelijkheid (vandaag, of anders de eerste dag) met de goedkoopste dag verderop.
   *
   *   dagen     [{ dag, blok, euro, euroLaag, euroHoog, zeker, zwak }], een per dag binnen de horizon
   *   gekozen   het element uit `dagen` dat het advies aanwijst
   *   soort     'nu' (de eerste dag is de goedkoopste), 'gewoon' (scheelt te weinig), 'wacht' (wachten loont) of
   *             'misschien' (loont waarschijnlijk, maar niet zeker; alleen bij de auto)
   *   advies    de zin die erbij hoort
   */
  function weekAdvies(model, apparaat, nuUur) {
    const euro = (ct) => (ct * apparaat.kwh) / 100;
    const dagen = [];
    model.dagen.slice(0, apparaat.horizon).forEach((dag) => {
      const blok = weekBlok(model, apparaat, dag, nuUur);
      if (!blok) return;
      dagen.push({
        dag: dag, blok: blok, euro: euro(blok.p50), euroLaag: euro(blok.p10), euroHoog: euro(blok.p90),
        zeker: blok.bekend, zwak: dag.betrouwbaarheid.code === 'laag',
      });
    });
    if (!dagen.length) return null;
    const eerste = dagen[0];
    const goedkoopste = dagen.reduce((beste, d) => (d.euro < beste.euro - 1e-9 ? d : beste));
    const naam = (d) => dagNaam(d.dag, true);
    const advies = { apparaat: apparaat, dagen: dagen, gekozen: eerste, goedkoopste: goedkoopste };

    if (dagen.length === 1) {
      advies.soort = 'nu';
      advies.advies = `Geen verwachting verder vooruit. ${naam(eerste)} ${blokTijd(eerste.blok)} is het goedkoopste moment.`;
      return advies;
    }
    if (goedkoopste === eerste) {
      advies.soort = 'nu';
      advies.advies = `Laad ${naam(eerste).toLowerCase()}: later wordt het niet goedkoper.`;
      return advies;
    }
    const winst = eerste.euro - goedkoopste.euro;             // wat wachten naar verwachting oplevert
    const winstSlecht = eerste.euro - goedkoopste.euroHoog;   // als de prijs later hoog uitvalt
    const winstGoed = eerste.euro - goedkoopste.euroLaag;     // als de prijs later laag uitvalt
    const drempel = apparaat.auto
      ? LAAD_DREMPEL_EURO
      : Math.max(WEEK_MIN_WINST_EURO, WEEK_MIN_WINST_DEEL * Math.abs(eerste.euro));
    const later = naam(goedkoopste).toLowerCase();
    if (winst < drempel) {
      advies.soort = 'gewoon';
      advies.advies = `Scheelt weinig: hooguit ${fmtEuro(winst)} met ${later}. Laad wanneer het uitkomt.`;
    } else if (apparaat.streng && !goedkoopste.zeker && winstSlecht < drempel) {
      advies.soort = 'misschien';
      advies.advies = `Op ${later} waarschijnlijk ${fmtEuro(winst)} goedkoper, maar dat is niet zeker ` +
        `(${plusMinEuro(winstGoed - winst, winst - winstSlecht)}). Laad nu alleen wat u nodig hebt.`;
    } else {
      advies.soort = 'wacht';
      advies.gekozen = goedkoopste;
      advies.advies = `Wacht tot ${later}: ${goedkoopste.zeker ? '' : 'waarschijnlijk '}${fmtEuro(winst)} goedkoper.`;
    }
    if (goedkoopste.zwak) advies.advies += ' Nog onzeker, kijk een dag later opnieuw.';
    return advies;
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

  // Wat index.html gebruikt. Al het andere in dit bestand is intern.
  window.SP = {
    // opmaak
    fmt: fmt, fmtKort: fmtKort, fmtUur: fmtUur, fmtEuro: fmtEuro, duurTekst: duurTekst, plusMinEuro: plusMinEuro,
    dagNaam: dagNaam, datumTekst: datumTekst, gegenereerdTekst: gegenereerdTekst, esc: esc,
    // klok
    vandaagLokaal: vandaagLokaal, morgenLokaal: morgenLokaal, nuLokaalUur: nuLokaalUur,
    msTotMiddernacht: msTotMiddernacht,
    // model en zinnen
    STOPLICHT: STOPLICHT, verwerk: verwerk, blokTijd: blokTijd, laadZin: laadZin, apparaatZin: apparaatZin,
    bandZin: bandZin, betrouwbaarheidHtml: betrouwbaarheidHtml, stoplichtHtml: stoplichtHtml,
    tariefUitlegTekst: tariefUitlegTekst,
    // instellingen
    koppelResolutie: koppelResolutie, koppelApparaten: koppelApparaten, koppelLaadinstellingen: koppelLaadinstellingen,
    koppelTarief: koppelTarief,
    // tabel, grafiek, advies
    maakTabel: maakTabel, tekenGrafiek: tekenGrafiek, startAdvies: startAdvies, weekAdvies: weekAdvies, laadApparaten: laadApparaten,
    // gegevens
    laadForecast: laadForecast, laadLeveranciers: laadLeveranciers,
  };
})();
