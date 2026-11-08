/*
 * gedeeld.js — gedeelde logica voor de ontwerpvarianten van de stroomprijsvoorspeller.
 *
 * Bevat: JSON laden, omrekenen naar ct/kWh, dagen en dagdelen indelen,
 * stoplicht (relatief t.o.v. de hele horizon), goedkoopste 3-uursblok,
 * eigen tarief in localStorage, Nederlandse opmaak, de canvas-grafiek
 * en een tabel-alternatief voor de grafiek.
 *
 * Geen afhankelijkheden. Alles hangt aan window.SP.
 */
(function () {
  'use strict';

  // ---------- constanten ----------
  const DAGDELEN = [
    { naam: 'nacht', label: 'Nacht', van: 0, tot: 6 },
    { naam: 'ochtend', label: 'Ochtend', van: 6, tot: 12 },
    { naam: 'middag', label: 'Middag', van: 12, tot: 18 },
    { naam: 'avond', label: 'Avond', van: 18, tot: 24 },
  ];
  const STOPLICHT = {
    goedkoop: { klasse: 'sl-goedkoop', label: 'goedkoop', icoon: '▼' },
    gemiddeld: { klasse: 'sl-gemiddeld', label: 'gemiddeld', icoon: '■' },
    duur: { klasse: 'sl-duur', label: 'duur', icoon: '▲' },
  };
  // betrouwbaarheid per dag, uit forecast.dagen (code → label, icoon, klasse); nooit alleen kleur
  const BETROUWBAARHEID = {
    bekend: { code: 'bekend', label: 'zeker', icoon: '\u2713', klasse: 'btr-bekend', uitleg: 'prijs staat vast' },
    hoog: { code: 'hoog', label: 'betrouwbaar', icoon: '\u25cf\u25cf\u25cf', klasse: 'btr-hoog', uitleg: 'verwachting' },
    redelijk: { code: 'redelijk', label: 'redelijk', icoon: '\u25cf\u25cf\u25cb', klasse: 'btr-redelijk', uitleg: 'verwachting per dagdeel' },
    laag: { code: 'laag', label: 'onzeker', icoon: '\u25cf\u25cb\u25cb', klasse: 'btr-laag', uitleg: 'alleen een richting' },
  };
  const WEEKDAGEN = ['zondag', 'maandag', 'dinsdag', 'woensdag', 'donderdag', 'vrijdag', 'zaterdag'];
  const WEEKDAGEN_KORT = ['zo', 'ma', 'di', 'wo', 'do', 'vr', 'za'];
  const MAANDEN = ['jan', 'feb', 'mrt', 'apr', 'mei', 'jun', 'jul', 'aug', 'sep', 'okt', 'nov', 'dec'];
  const DETAIL_PER_UUR_TOT = 4; // dagindex 0..3 per uur, vanaf 4 per dagdeel
  // ---------- tarieven 2026 (besluit opdrachtgever, DECISIONS nr. 35) ----------
  // Drie standen, naar voorbeeld van de Frank Energie-app. Belasting en btw staan vast per jaar;
  // de gebruiker vult alleen de inkoopvergoeding van de eigen leverancier in (excl. btw).
  const TARIEF_JAAR = 2026;
  const ENERGIEBELASTING_CT = 9.2;   // ct/kWh excl. btw (11,1 ct incl. btw)
  const BTW_PCT = 21;
  const INKOOP_STANDAARD_CT = 1.65;  // inkoopvergoeding leverancier, ct/kWh excl. btw (2,0 ct incl. btw); besluit 35
  const TARIEF_STANDEN = {
    markt: { code: 'markt', label: 'Marktprijs', uitleg: 'kale beursprijs, zonder btw' },
    marktplus: { code: 'marktplus', label: 'Marktprijs+', uitleg: 'beursprijs plus inkoopvergoeding, met btw' },
    allin: { code: 'allin', label: 'All-in', uitleg: 'zoals op je rekening, met belasting en btw' },
  };
  const TARIEF_STANDAARD = 'allin';  // standaard: dat staat op de rekening
  const OPSLAG_SLEUTEL = 'stroomprijs-tarief-v2';
  const RESOLUTIE_SLEUTEL = 'stroomprijs-resolutie-v2'; // 'uur' of 'kwartier'; standaard kwartier (v2: nieuwe standaard, oude keuze vervalt)
  const LADEN_SLEUTEL = 'stroomprijs-laden-v1';
  const APPARATEN_SLEUTEL = 'stroomprijs-apparaten-v1'; // eigen apparaten: [{ id, naam, uren, kwh }]
  const APPARATEN_STANDAARD = [{ id: 'was', naam: 'Wasmachine', uren: 2, kwh: 1 }];
  // laden: zonder instellingen een vast blok van 3 uur en 30 kWh; met instellingen = kWh / kW, hele uren
  const LAAD_STANDAARD_UREN = 3;
  const LAAD_STANDAARD_KWH = 30;
  const KWH_PER_KM = 0.18;    // hulpje: kilometers naar kWh
  const LAAD_KEUZES_KW = [2.3, 3.7, 7.4, 11, 22];
  // wasmachine: vast blok, vast verbruik
  const WAS_BLOK_UREN = 2;
  const WAS_KWH = 1;
  // netspits: de overheid vraagt om tussen 16 en 21 uur zo min mogelijk stroom te gebruiken (campagne "Zet ook de knop om").
  // Alleen zichtbaar gemaakt (arcering); het advies blijft op prijs. Besluit opdrachtgever 2026-11-01.
  const NETSPITS = { van: 16, tot: 21 };

  // ---------- opmaak ----------
  function fmt(x, dec) {
    if (x === null || x === undefined || Number.isNaN(x)) return '–';
    if (dec === undefined) dec = 1;
    return x.toFixed(dec).replace('.', ',');
  }
  // uren met een fractie (12.25) worden 12:15
  function fmtUur(h) {
    const hh = Math.floor(h + 1e-9);
    const mm = Math.round((h - hh) * 60);
    return (hh < 10 ? '0' : '') + hh + ':' + (mm < 10 ? '0' : '') + mm;
  }

  // 'YYYY-MM-DDTHH:MM:SS+01:00' → lokale onderdelen, zonder tijdzone-gedoe in de browser.
  function parseTijd(s) {
    const d = s.slice(0, 10);
    const uur = parseInt(s.slice(11, 13), 10);
    const dt = new Date(d + 'T12:00:00'); // alleen voor weekdag
    return { datum: d, uur: uur, weekdag: dt.getDay(), dagVdMaand: parseInt(d.slice(8, 10), 10), maand: parseInt(d.slice(5, 7), 10) - 1 };
  }

  // Altijd weekdag + datum, nooit 'vandaag' of 'morgen': een pagina kan een dag later nog openstaan.
  function dagNaam(dag, lang) {
    const wd = lang ? WEEKDAGEN[dag.weekdag] : WEEKDAGEN_KORT[dag.weekdag];
    const naam = wd + ' ' + dag.dagVdMaand + ' ' + MAANDEN[dag.maand];
    return lang ? naam.charAt(0).toUpperCase() + naam.slice(1) : naam;
  }
  function vandaagLokaal() { return new Date().toLocaleDateString('sv-SE', { timeZone: 'Europe/Amsterdam' }); }
  // milliseconden tot de volgende middernacht (Nederlandse tijd), voor de dagwissel op de pagina
  function msTotMiddernacht() {
    const p = new Date().toLocaleTimeString('en-GB', { timeZone: 'Europe/Amsterdam', hour12: false }).split(':').map(Number);
    return Math.max(1000, (86400 - (p[0] % 24) * 3600 - p[1] * 60 - p[2]) * 1000);
  }
  function dagDatumKort(dag) { return WEEKDAGEN_KORT[dag.weekdag] + ' ' + dag.dagVdMaand + ' ' + MAANDEN[dag.maand]; }

  // ---------- tarief ----------
  function standaardTarief() { return { stand: TARIEF_STANDAARD, inkoop: INKOOP_STANDAARD_CT, leverancier: null }; }
  // inkoop mag null zijn (leverancier publiceert geen bedrag); dan rekenen we met de standaard
  function netTarief(t) {
    const st = standaardTarief();
    if (!t) return st;
    return {
      stand: TARIEF_STANDEN[t.stand] ? t.stand : st.stand,
      inkoop: typeof t.inkoop === 'number' && t.inkoop >= 0 ? t.inkoop : (t.inkoop === null ? null : st.inkoop),
      leverancier: typeof t.leverancier === 'string' && t.leverancier ? t.leverancier : null,
    };
  }
  function inkoopEffectief(t) { return typeof t.inkoop === 'number' ? t.inkoop : INKOOP_STANDAARD_CT; }
  // tarief = { stand: 'markt' | 'marktplus' | 'allin', inkoop: ct/kWh excl. btw of null, leverancier: naam of null }; altijd een geldig object
  function leesTarief() {
    try {
      const raw = localStorage.getItem(OPSLAG_SLEUTEL);
      return netTarief(raw ? JSON.parse(raw) : null);
    } catch (e) { return standaardTarief(); }
  }
  function bewaarTarief(t) {
    try { localStorage.setItem(OPSLAG_SLEUTEL, JSON.stringify(netTarief(t))); return true; } catch (e) { return false; }
  }
  // EUR/MWh → ct/kWh in de gekozen stand. Bij een negatieve beursprijs geldt dezelfde som:
  // all-in kan dan nog positief zijn, want belasting en btw komen erbij.
  function naarCt(eurMwh, tarief) {
    const t = netTarief(tarief);
    const kaal = eurMwh / 10;
    if (t.stand === 'markt') return kaal;
    const btw = 1 + BTW_PCT / 100;
    const inkoop = inkoopEffectief(t);
    if (t.stand === 'marktplus') return (kaal + inkoop) * btw;
    return (kaal + inkoop + ENERGIEBELASTING_CT) * btw;
  }
  // een afwijking in ct/kWh (kaal) schaalt in de standen met btw mee; belasting en inkoop zijn vast en tellen niet mee
  function tariefFactor(tarief) { return netTarief(tarief).stand === 'markt' ? 1 : 1 + BTW_PCT / 100; }
  function tariefLabel(tarief) {
    const t = netTarief(tarief);
    return 'ct/kWh, ' + TARIEF_STANDEN[t.stand].label.toLowerCase() + (t.stand === 'markt' ? '' : ' (tarieven ' + TARIEF_JAAR + ')');
  }

  // ---------- verwerken ----------
  function verwerk(forecast, tarief, laadInst, resolutie, apparaten) {
    tarief = netTarief(tarief);
    const factor = tariefFactor(tarief);
    const laad = { inst: laadInst || null, uren: laadBlokUren(laadInst), kwh: laadKwh(laadInst) };
    apparaten = apparaten && apparaten.length ? apparaten : APPARATEN_STANDAARD;
    const perKwartier = resolutie === 'kwartier';
    const perDag = new Map();
    function dagVan(t) {
      if (!perDag.has(t.datum)) perDag.set(t.datum, { datum: t.datum, weekdag: t.weekdag, dagVdMaand: t.dagVdMaand, maand: t.maand, uren: [], kwartieren: [] });
      return perDag.get(t.datum);
    }
    // voorbije dagen verdwijnen: na middernacht toont de pagina de dag van gisteren niet meer. Is alles voorbij
    // (verouderde voorspelling), dan blijft alles staan, met de melding erboven.
    const vanaf = vandaagLokaal();
    let urenBron = forecast.uren.filter(function (u) { return u.tijd.slice(0, 10) >= vanaf; });
    if (!urenBron.length) urenBron = forecast.uren;
    const kwartierenBron = (forecast.kwartieren || []).filter(function (q) { return q.tijd.slice(0, 10) >= urenBron[0].tijd.slice(0, 10); });
    urenBron.forEach(function (u) {
      const t = parseTijd(u.tijd);
      dagVan(t).uren.push({
        tijd: u.tijd, uur: t.uur, duur: 1, bekend: !!u.bekend,
        p10: naarCt(u.p10, tarief), p50: naarCt(u.p50, tarief), p90: naarCt(u.p90, tarief),
        // vaagheid altijd op de kale beursprijs, anders wordt de band "scherper" zodra er belasting bij komt
        vaagheid: vaagheid(u.p10 / 10, u.p50 / 10, u.p90 / 10),
      });
    });
    // kwartierprijzen: alleen voor bekende dagen (de verwachting is per uur)
    kwartierenBron.forEach(function (q) {
      const t = parseTijd(q.tijd);
      const minuut = parseInt(q.tijd.slice(14, 16), 10) || 0;
      const p = naarCt(q.prijs, tarief);
      dagVan(t).kwartieren.push({ tijd: q.tijd, uur: t.uur + minuut / 60, duur: 0.25, bekend: true, p10: p, p50: p, p90: p, vaagheid: 0 });
    });
    const dagen = Array.from(perDag.values()).sort(function (a, b) { return a.datum < b.datum ? -1 : 1; });
    dagen.forEach(function (d) {
      zetPosities(d.uren);
      zetPosities(d.kwartieren);
      const compleet = d.kwartieren.length >= 4 * d.uren.length - 4 && d.uren.every(function (u) { return u.bekend; });
      d.perKwartier = perKwartier && compleet;
      d.reeks = d.perKwartier ? d.kwartieren : d.uren;   // wat getekend en doorzocht wordt
    });
    const dagInfo = {};
    (forecast.dagen || []).forEach(function (x) { dagInfo[x.datum] = x; });
    dagen.forEach(function (d, i) {
      d.index = i;
      d.dagsoort = (dagInfo[d.datum] || {}).dagsoort || null;
      d.feestdag = (dagInfo[d.datum] || {}).feestdag || null;
      d.bekend = d.uren.every(function (u) { return u.bekend; });
      d.betrouwbaarheid = betrouwbaarheidVan(dagInfo[d.datum], d, forecast.scores || {}, factor);
      d.perUur = i < DETAIL_PER_UUR_TOT;
      d.gem = gem(d.uren.map(function (u) { return u.p50; }));
      d.min = Math.min.apply(null, d.uren.map(function (u) { return u.p50; }));
      d.max = Math.max.apply(null, d.uren.map(function (u) { return u.p50; }));
      d.dagdelen = DAGDELEN.map(function (dd) {
        const uren = d.uren.filter(function (u) { return u.uur >= dd.van && u.uur < dd.tot; });
        const p10 = gem(uren.map(function (u) { return u.p10; }));
        const p50 = gem(uren.map(function (u) { return u.p50; }));
        const p90 = gem(uren.map(function (u) { return u.p90; }));
        return { naam: dd.naam, label: dd.label, van: dd.van, tot: dd.tot, p10: p10, p50: p50, p90: p90, bekend: d.bekend, vaagheid: gem(uren.map(function (u) { return u.vaagheid; })), dag: d };
      });
      d.vaagheid = gem(d.dagdelen.map(function (b) { return b.vaagheid; }));
    });
    // blokken: laden mag over middernacht heen lopen in de volgende dag, wassen blijft binnen de dag
    dagen.forEach(function (d, i) {
      const stap = d.perKwartier ? 0.25 : 1;
      let volgende = dagen[i + 1] ? (stap === 1 ? dagen[i + 1].uren : naarKwartieren(dagen[i + 1].reeks)) : [];
      d.laden = goedkoopsteBlok(d.reeks, Math.round(laad.uren / stap), volgende);
      if (d.laden) d.laden.onzekereDag = d.betrouwbaarheid.code === 'laag';
      if (d.laden && d.laden.volgendeDag) d.laden.eindDagNaam = dagNaam(dagen[i + 1], false);
      if (d.laden && d.laden.duurste && d.laden.duurste.volgendeDag) d.laden.duurste.eindDagNaam = dagNaam(dagen[i + 1], false);
      // eigen apparaten: een blok ter lengte van de duur, binnen de dag (per kwartier als die dag kwartierprijzen heeft)
      d.blokken = {};
      apparaten.forEach(function (a) { d.blokken[a.id] = goedkoopsteBlok(d.reeks, Math.max(1, Math.round(a.uren / stap))); });
      d.wassen = d.blokken[apparaten[0].id] || goedkoopsteBlok(d.reeks, Math.round(WAS_BLOK_UREN / stap));
    });
    // stoplicht: tertielen van alle dagdeel-P50's over de hele horizon
    const alle = [];
    dagen.forEach(function (d) { d.dagdelen.forEach(function (b) { alle.push(b.p50); }); });
    alle.sort(function (a, b) { return a - b; });
    const g1 = alle[Math.floor(alle.length / 3)];
    const g2 = alle[Math.floor((2 * alle.length) / 3)];
    const classificeer = function (p50) { return p50 < g1 ? 'goedkoop' : p50 < g2 ? 'gemiddeld' : 'duur'; };
    dagen.forEach(function (d) {
      d.dagdelen.forEach(function (b) { b.stoplicht = classificeer(b.p50); });
      d.uren.forEach(function (u) { u.stoplicht = classificeer(u.p50); });
      d.kwartieren.forEach(function (u) { u.stoplicht = classificeer(u.p50); });
    });
    const scores = forecast.scores || {};
    return {
      dagen: dagen, grenzen: { goedkoop: g1, duur: g2 }, classificeer: classificeer, laad: laad, apparaten: apparaten, resolutie: perKwartier ? 'kwartier' : 'uur',
      gegenereerd: forecast.gegenereerd_utc, tarief: tarief, stand: TARIEF_STANDEN[tarief.stand],
      scores: scoresVan(scores, factor),
      eenheidLabel: tariefLabel(tarief),
    };
  }
  // scores per horizon uit de JSON (mae_dag2..7, dekking80_dag2..7), in ct/kWh van de gekozen stand
  function scoresVan(scores, factor) {
    const mae = {}, dekking = {};
    for (let k = 2; k <= 7; k++) {
      if (typeof scores['mae_dag' + k] === 'number') mae[k] = maal(ct(scores['mae_dag' + k]), factor);
      if (typeof scores['dekking80_dag' + k] === 'number') dekking[k] = scores['dekking80_dag' + k];
    }
    return { periode: scores.periode_dagen, mae: mae, dekking: dekking };
  }
  function ct(x) { return typeof x === 'number' ? x / 10 : null; }
  function maal(x, f) { return typeof x === 'number' ? x * f : null; }
  // positie (in uren vanaf het begin van de dag) per element, robuust voor dagen met 23 of 25 uur
  function zetPosities(reeks) { let pos = 0; reeks.forEach(function (u) { u.pos = pos; pos += u.duur; }); }
  // uurreeks opsplitsen in kwartieren (zelfde prijs), voor een laadblok dat van een kwartierdag in een uurdag doorloopt
  function naarKwartieren(reeks) {
    const uit = [];
    reeks.forEach(function (u) {
      if (u.duur <= 0.25) { uit.push(u); return; }
      for (let k = 0; k < 4; k++) uit.push({ tijd: u.tijd, uur: u.uur + k * 0.25, duur: 0.25, bekend: u.bekend, p10: u.p10, p50: u.p50, p90: u.p90, vaagheid: u.vaagheid, stoplicht: u.stoplicht });
    });
    return uit;
  }
  // uit de JSON; zonder "dagen" in de JSON een nette terugval op de dagindex
  function betrouwbaarheidVan(info, d, scores, factor) {
    let code, afwijking = null, horizon = d.index;
    factor = factor || 1;
    if (info && BETROUWBAARHEID[info.betrouwbaarheid]) {
      code = info.betrouwbaarheid;
      if (typeof info.verwachte_afwijking_ct === 'number') afwijking = info.verwachte_afwijking_ct * factor;
      if (typeof info.horizon_dag === 'number') horizon = info.horizon_dag;
    } else {
      code = d.bekend ? 'bekend' : d.index <= 3 ? 'hoog' : d.index <= 5 ? 'redelijk' : 'laag';
      afwijking = maal(ct(scores['mae_dag' + d.index]), factor);
    }
    const b = BETROUWBAARHEID[code];
    return { code: code, label: b.label, icoon: b.icoon, klasse: b.klasse, uitleg: b.uitleg, afwijking: afwijking, horizon: horizon };
  }
  // "Dag 6: onzeker, gemiddeld 2,3 ct/kWh afwijking" / "bekend, prijs staat vast"
  function betrouwbaarheidTekst(d, metDag) {
    const b = d.betrouwbaarheid;
    let s = b.label;
    if (b.code === 'bekend') s += ', prijs staat vast';
    else if (b.afwijking !== null) s += ', gemiddeld ' + fmt(b.afwijking) + ' ct/kWh afwijking';
    if (metDag && d.index >= 2) s = 'Dag ' + b.horizon + ': ' + s;
    return s;
  }
  function betrouwbaarheidHtml(d, kort) {
    const b = d.betrouwbaarheid;
    const tekst = kort ? b.label : betrouwbaarheidTekst(d, false);
    return '<span class="btr ' + b.klasse + '"><span class="btr-icoon" aria-hidden="true">' + b.icoon + '</span>' + tekst + '</span>';
  }
  function gem(a) { if (!a.length) return NaN; let s = 0; for (let i = 0; i < a.length; i++) s += a[i]; return s / a.length; }

  // relatieve breedte van de band t.o.v. het niveau: 0 = scherp, 1 = heel vaag
  function vaagheid(p10, p50, p90) {
    if (p90 - p10 <= 0) return 0;
    const niveau = Math.max(Math.abs(p50), 1);
    return Math.min(1, (p90 - p10) / niveau);
  }
  // dekking (opacity) stond eerder in verhouding tot de vaagheid; besluit opdrachtgever: prijskleuren en
  // grafiek constant, de band en het betrouwbaarheidslabel dragen de onzekerheid. Blijft 1 voor compatibiliteit.
  function dekking() { return 1; }

  // goedkoopste aaneengesloten blok van n uur (op P50), met marge t.o.v. daggemiddelde
  // goedkoopste aaneengesloten blok van n uur (op P50) dat in deze dag begint; mag doorlopen in `vervolg`
  // (de uren van de volgende dag). Geeft ook het duurste blok van gelijke lengte terug, voor de vergelijking.
  function goedkoopsteBlok(uren, n, vervolg) {
    vervolg = vervolg || [];
    const reeks = uren.concat(vervolg);
    if (!uren.length || reeks.length < n) return null;
    let beste = null, duurste = null;
    const laatsteStart = Math.min(uren.length - 1, reeks.length - n);
    for (let i = 0; i <= laatsteStart; i++) {
      const b = maakBlok(reeks.slice(i, i + n), i + n > uren.length);
      if (!beste || b.p50 < beste.p50) beste = b;
      if (!duurste || b.p50 > duurste.p50) duurste = b;
    }
    const dagGem = gem(uren.map(function (u) { return u.p50; }));
    beste.dagGem = dagGem;
    beste.marge = dagGem - beste.p50;            // ct/kWh goedkoper dan het daggemiddelde (kan net negatief zijn)
    beste.margePct = dagGem !== 0 ? (beste.marge / Math.abs(dagGem)) * 100 : 0;
    beste.duurste = duurste;
    beste.vsDuurste = duurste.p50 - beste.p50;    // ct/kWh goedkoper dan het duurste blok van gelijke lengte
    return beste;
  }
  function maakBlok(blok, volgendeDag) {
    const aantal = blok.length;
    const laatste = blok[aantal - 1];
    const duur = blok.reduce(function (s, u) { return s + u.duur; }, 0);
    const p10 = gem(blok.map(function (u) { return u.p10; }));
    const p50 = gem(blok.map(function (u) { return u.p50; }));
    const p90 = gem(blok.map(function (u) { return u.p90; }));
    return {
      start: blok[0].uur, eind: laatste.uur + laatste.duur, n: Math.round(duur * 100) / 100, aantal: aantal, volgendeDag: !!volgendeDag, eindDagNaam: null,
      p10: p10, p50: p50, p90: p90, uren: blok, onzeker: (p90 - p10) / 2, onzekerPlus: p90 - p50, onzekerMin: p50 - p10,
      vaagheid: gem(blok.map(function (u) { return u.vaagheid; })),
      bekend: blok.every(function (u) { return u.bekend; }),
    };
  }
  // kosten van een blok in euro voor `kwh` kilowattuur
  function blokKosten(blok, kwh) {
    if (!blok) return null;
    const e = function (ct) { return (ct * kwh) / 100; };
    return { kwh: kwh, euro: e(blok.p50), euroLaag: e(blok.p10), euroHoog: e(blok.p90), onzeker: e(blok.onzeker),
      plus: e(blok.onzekerPlus || 0), min: e(blok.onzekerMin || 0),
      vsDuurste: e(blok.vsDuurste || 0), vsGem: e(blok.marge || 0) };
  }
  // onzekerheid als plus- en minbedrag bij de verwachting (wens opdrachtgever: geen 'tussen a en b')
  function plusMinCt(plus, min) { return '+' + fmt(plus) + ' / −' + fmt(min) + ' ct'; }
  function plusMinEuro(plus, min) { return '+' + fmtEuro(plus) + ' / −' + fmtEuro(min); }
  function blokTijd(blok) {
    if (!blok) return '';
    let s = fmtUur(blok.start) + '\u2013' + fmtUur(blok.eind);
    if (blok.volgendeDag && blok.eindDagNaam) s += ' (loopt door tot ' + blok.eindDagNaam + ')';
    else if (blok.volgendeDag) s += ' (loopt door tot de volgende dag)';
    return s;
  }
  // "21,1 ct/kWh, 6,33 euro voor 30 kWh. 2,40 euro minder dan op het duurste moment, 1,23 euro minder dan gemiddeld. Onzeker: plus of min 0,80 euro."
  function laadZin(blok, kwh) {
    if (!blok) return '';
    const k = blokKosten(blok, kwh);
    let s = fmt(blok.p50) + ' ct/kWh, ' + fmtEuro(k.euro) + ' voor ' + fmt(kwh, kwh % 1 ? 1 : 0) + ' kWh. ';
    s += fmtEuro(k.vsDuurste) + ' minder dan op het duurste moment, ';
    s += k.vsGem > 0.005 ? fmtEuro(k.vsGem) + ' minder dan gemiddeld.' : k.vsGem < -0.005 ? fmtEuro(-k.vsGem) + ' meer dan gemiddeld.' : 'gelijk aan gemiddeld.';
    if (!blok.bekend) s += ' Onzeker: ' + plusMinEuro(k.plus, k.min) + '.';
    if (blok.onzekereDag) s += ' Nog onzeker, kijk een dag later opnieuw.';
    return s;
  }
  function wasZin(blok) { return apparaatZin(blok, WAS_KWH); }
  function apparaatZin(blok, kwh) {
    if (!blok) return '';
    const k = blokKosten(blok, kwh);
    let s = fmt(blok.p50) + ' ct/kWh, ' + fmtEuro(k.euro) + ' per beurt';
    if (k.vsDuurste > 0.005) s += ', ' + fmtEuro(k.vsDuurste) + ' minder dan op het duurste moment';
    if (!blok.bekend) s += ' (' + plusMinEuro(k.plus, k.min) + ')';
    return s + '.';
  }

  // ---------- resolutie: per uur of per kwartier (alleen bekende dagen) ----------
  function leesResolutie() {
    try { return localStorage.getItem(RESOLUTIE_SLEUTEL) === 'uur' ? 'uur' : 'kwartier'; } catch (e) { return 'kwartier'; }
  }
  function bewaarResolutie(r) {
    try { localStorage.setItem(RESOLUTIE_SLEUTEL, r === 'kwartier' ? 'kwartier' : 'uur'); return true; } catch (e) { return false; }
  }
  // knoppen met data-resolutie="uur|kwartier" in `container`; zet aria-pressed en roept bijRefresh(resolutie) aan
  function koppelResolutie(container, bijRefresh) {
    const knoppen = Array.from(container.querySelectorAll('[data-resolutie]'));
    function toon(r) { knoppen.forEach(function (b) { b.setAttribute('aria-pressed', b.dataset.resolutie === r ? 'true' : 'false'); }); }
    knoppen.forEach(function (b) {
      b.addEventListener('click', function () { const r = b.dataset.resolutie; bewaarResolutie(r); toon(r); bijRefresh(r); });
    });
    const r = leesResolutie();
    toon(r);
    return r;
  }

  // ---------- eigen apparaten: naam, duur in uren, verbruik in kWh (blijft in de browser) ----------
  function leesApparaten() {
    try {
      const raw = localStorage.getItem(APPARATEN_SLEUTEL);
      if (!raw) return APPARATEN_STANDAARD.map(function (a) { return Object.assign({}, a); });
      const lijst = JSON.parse(raw).filter(function (a) { return a && a.uren > 0; })
        .map(function (a, i) { return { id: String(a.id || 'app' + i), naam: String(a.naam || 'Apparaat'), uren: Math.min(24, Number(a.uren)), kwh: a.kwh > 0 ? Number(a.kwh) : 1 }; });
      return lijst;
    } catch (e) { return APPARATEN_STANDAARD.map(function (a) { return Object.assign({}, a); }); }
  }
  function bewaarApparaten(lijst) {
    try { localStorage.setItem(APPARATEN_SLEUTEL, JSON.stringify(lijst)); return true; } catch (e) { return false; }
  }
  function duurTekst(uren) {
    const h = Math.floor(uren + 1e-9), m = Math.round((uren - h) * 60);
    if (m === 0) return h + ' uur';
    if (h === 0) return m + ' min';
    return h + ' uur ' + (m < 10 ? '0' : '') + m;
  }
  /*
   * koppelApparaten(container, bijRefresh): tekent een bewerkbare lijst (naam, duur, kWh, verwijderen) plus een knop
   * "Apparaat toevoegen". Elke wijziging wordt bewaard en geeft de nieuwe lijst door. Geeft de huidige lijst terug.
   */
  function koppelApparaten(container, bijRefresh) {
    let lijst = leesApparaten();
    function esc(s) { return String(s).replace(/[&<>"]/g, function (c) { return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]; }); }
    function teken() {
      container.innerHTML = lijst.map(function (a, i) {
        return '<div class="app-rij" data-i="' + i + '">' +
          '<label>Apparaat<input type="text" name="naam" value="' + esc(a.naam) + '" maxlength="30" placeholder="bijv. vaatwasser"></label>' +
          '<label>Duur (uren)<input type="number" name="uren" value="' + a.uren + '" step="0.25" min="0.25" max="24" inputmode="decimal"></label>' +
          '<label>Verbruik (kWh)<input type="number" name="kwh" value="' + a.kwh + '" step="0.1" min="0.1" inputmode="decimal"></label>' +
          '<button type="button" class="weg" aria-label="' + esc(a.naam) + ' verwijderen" title="Verwijderen">×</button>' +
          '</div>';
      }).join('') + '<button type="button" class="toevoegen">+ Apparaat toevoegen</button>';
    }
    function getal(el, min) { const v = parseFloat(String(el.value).replace(',', '.')); return v >= min ? v : null; }
    function lees() {
      const rijen = Array.from(container.querySelectorAll('.app-rij'));
      lijst = rijen.map(function (r, i) {
        const oud = lijst[i] || {};
        const uren = getal(r.querySelector('[name=uren]'), 0.25);
        const kwh = getal(r.querySelector('[name=kwh]'), 0.1);
        return { id: oud.id || 'app' + Date.now() + i, naam: r.querySelector('[name=naam]').value.trim() || 'Apparaat',
                 uren: uren !== null ? Math.min(24, Math.round(uren * 4) / 4) : (oud.uren || 1), kwh: kwh !== null ? kwh : (oud.kwh || 1) };
      });
      bewaarApparaten(lijst);
      bijRefresh(lijst);
    }
    container.addEventListener('change', function (e) { if (e.target.matches('input')) { lees(); teken(); } });
    container.addEventListener('click', function (e) {
      if (e.target.matches('.weg')) {
        lijst.splice(parseInt(e.target.closest('.app-rij').dataset.i, 10), 1);
        bewaarApparaten(lijst); teken(); bijRefresh(lijst);
      } else if (e.target.matches('.toevoegen')) {
        lijst.push({ id: 'app' + Date.now(), naam: '', uren: 1, kwh: 1 });
        teken();
        const nieuw = container.querySelector('.app-rij:last-of-type [name=naam]');
        if (nieuw) nieuw.focus();
      }
    });
    teken();
    return lijst;
  }

  // ---------- laadinstellingen (vermogen en hoeveelheid) ----------
  function leesLaadinstellingen() {
    try {
      const raw = localStorage.getItem(LADEN_SLEUTEL);
      if (!raw) return null;
      const t = JSON.parse(raw);
      return { kw: t.kw > 0 ? t.kw : null, kwh: t.kwh > 0 ? t.kwh : null };
    } catch (e) { return null; }
  }
  function bewaarLaadinstellingen(inst) {
    try {
      if (inst && (inst.kw || inst.kwh)) localStorage.setItem(LADEN_SLEUTEL, JSON.stringify(inst));
      else localStorage.removeItem(LADEN_SLEUTEL);
      return true;
    } catch (e) { return false; }
  }
  // bloklengte in hele uren: kWh / kW naar boven afgerond, 1..24; zonder instellingen 3 uur
  function laadBlokUren(inst) {
    if (inst && inst.kw > 0 && inst.kwh > 0) return Math.min(24, Math.max(1, Math.ceil(inst.kwh / inst.kw - 1e-9)));
    return LAAD_STANDAARD_UREN;
  }
  function laadKwh(inst) { return inst && inst.kwh > 0 ? inst.kwh : LAAD_STANDAARD_KWH; }
  function laadUitleg(inst) {
    const n = laadBlokUren(inst);
    if (inst && inst.kw > 0 && inst.kwh > 0) return fmt(inst.kwh, inst.kwh % 1 ? 1 : 0) + ' kWh bij ' + fmt(inst.kw, inst.kw % 1 ? 1 : 0) + ' kW: een blok van ' + n + ' uur.';
    return 'Standaard: een blok van ' + LAAD_STANDAARD_UREN + ' uur en ' + LAAD_STANDAARD_KWH + ' kWh. Vul vermogen en hoeveelheid in voor uw eigen laadbeurt.';
  }
  // formulier koppelen: select[name=kw] (met optie "anders"), input[name=kw-anders], input[name=kwh], input[name=km], element .laad-uitleg
  function koppelLaadinstellingen(form, bijRefresh) {
    const kwSel = form.querySelector('[name=kw]');
    const kwAnders = form.querySelector('[name=kw-anders]');
    const kwhEl = form.querySelector('[name=kwh]');
    const kmEl = form.querySelector('[name=km]');
    const uitlegEl = form.querySelector('.laad-uitleg');
    const bewaard = leesLaadinstellingen();
    if (bewaard) {
      if (bewaard.kw) {
        const keuze = LAAD_KEUZES_KW.find(function (k) { return Math.abs(k - bewaard.kw) < 0.01; });
        if (keuze !== undefined) kwSel.value = String(keuze); else { kwSel.value = 'anders'; kwAnders.value = bewaard.kw; }
      }
      if (bewaard.kwh) kwhEl.value = bewaard.kwh;
    }
    function getal(el) { const v = parseFloat(String(el.value).replace(',', '.')); return v > 0 ? v : null; }
    function huidig() {
      const kw = kwSel.value === 'anders' ? getal(kwAnders) : getal(kwSel);
      const kwh = getal(kwhEl);
      return kw || kwh ? { kw: kw, kwh: kwh } : null;
    }
    function toonAnders() { const wrap = kwAnders.closest('.kw-anders') || kwAnders; wrap.hidden = kwSel.value !== 'anders'; }
    function toonUitleg() { if (uitlegEl) uitlegEl.textContent = laadUitleg(huidig()); }
    function toepassen() { const i = huidig(); bewaarLaadinstellingen(i); toonUitleg(); bijRefresh(i); }
    kwSel.addEventListener('change', function () { toonAnders(); toepassen(); });
    kwAnders.addEventListener('change', toepassen);
    kwhEl.addEventListener('change', function () { if (kmEl) kmEl.value = ''; toepassen(); });
    if (kmEl) kmEl.addEventListener('change', function () {
      const km = getal(kmEl);
      if (km) { kwhEl.value = Math.round(km * KWH_PER_KM * 10) / 10; }
      toepassen();
    });
    form.addEventListener('submit', function (ev) { ev.preventDefault(); toepassen(); });
    toonAnders(); toonUitleg();
    return huidig();
  }

  // zinnen voor de interface
  function blokZin(blok) {
    if (!blok) return '';
    let s = blokTijd(blok) + ': ' + fmt(blok.p50) + ' ct/kWh';
    if (blok.marge > 0.05) s += ', ' + fmt(blok.marge) + ' ct goedkoper dan het daggemiddelde';
    else s += ', ongeveer gelijk aan het daggemiddelde';
    if (!blok.bekend) s += ' (' + plusMinCt(blok.onzekerPlus, blok.onzekerMin) + ')';
    return s;
  }
  function bandZin(p10, p50, p90, bekend) {
    if (bekend) return fmt(p50) + ' ct/kWh';
    return 'verwacht ' + fmt(p50) + ' ct/kWh (' + plusMinCt(p90 - p50, p50 - p10) + ')';
  }
  function betrouwbaarheidsWoord(v) {
    if (v < 0.25) return 'redelijk zeker';
    if (v < 0.5) return 'indicatief';
    return 'ruwe schatting';
  }

  // ---------- tekstsamenvatting en tabel (toegankelijk alternatief) ----------
  function samenvatting(model) {
    return model.dagen.map(function (d) {
      const b = d.laden;
      let z = dagNaam(d, true) + ': ';
      if (d.bekend) z += 'bekend, gemiddeld ' + fmt(d.gem) + ' ct/kWh, van ' + fmt(d.min) + ' tot ' + fmt(d.max) + '.';
      else z += 'voorspeld, ' + betrouwbaarheidTekst(d, false) + ', gemiddeld rond ' + fmt(d.gem) + ' ct/kWh.';
      z += ' Dagdelen: ' + d.dagdelen.map(function (x) { return x.label.toLowerCase() + ' ' + x.stoplicht; }).join(', ') + '.';
      if (b) z += ' Goedkoopste ' + b.n + ' uur om te laden: ' + blokTijd(b) + '.';
      return z;
    }).join(' ');
  }

  function maakTabel(container, model) {
    const frag = document.createDocumentFragment();
    model.dagen.forEach(function (d) {
      const h = document.createElement('h4');
      h.textContent = dagNaam(d, true) + (d.feestdag ? ', ' + d.feestdag : '') + ' (' + betrouwbaarheidTekst(d, true) + ')';
      frag.appendChild(h);
      const t = document.createElement('table');
      t.className = 'sp-tabel';
      const rijen = d.perUur ? d.reeks : d.dagdelen;
      let html = '<thead><tr><th scope="col">' + (d.perUur ? (d.perKwartier ? 'Kwartier' : 'Uur') : 'Dagdeel') + '</th>';
      html += d.bekend ? '<th scope="col">Prijs</th>' : '<th scope="col">Ondergrens</th><th scope="col">Verwacht</th><th scope="col">Bovengrens</th>';
      html += '<th scope="col">Stoplicht</th></tr></thead><tbody>';
      rijen.forEach(function (r) {
        const naam = d.perUur ? fmtUur(r.uur) : r.label + ' ' + fmtUur(r.van) + '–' + fmtUur(r.tot);
        html += '<tr><th scope="row">' + naam + '</th>';
        html += d.bekend ? '<td>' + fmt(r.p50) + '</td>' : '<td>' + fmt(r.p10) + '</td><td>' + fmt(r.p50) + '</td><td>' + fmt(r.p90) + '</td>';
        html += '<td>' + STOPLICHT[r.stoplicht].icoon + ' ' + STOPLICHT[r.stoplicht].label + '</td></tr>';
      });
      t.innerHTML = html + '</tbody>';
      frag.appendChild(t);
    });
    container.innerHTML = '';
    container.appendChild(frag);
  }

  // ---------- stoplicht-element ----------
  function stoplichtHtml(sl, extra) {
    const s = STOPLICHT[sl];
    return '<span class="sl ' + s.klasse + (extra ? ' ' + extra : '') + '"><span class="sl-icoon" aria-hidden="true">' + s.icoon + '</span>' + s.label + '</span>';
  }

  // ---------- grafiek op canvas ----------
  function cssVar(el, naam, standaard) {
    const v = getComputedStyle(el).getPropertyValue(naam).trim();
    return v || standaard;
  }

  /*
   * tekenGrafiek(canvas, model, opties)
   * opties: { maxDagen, hoogte, compact, toonLabels }
   * Per dag: index < 4 per uur (bekend = vlak gevuld, voorspeld = band + lijn),
   * vanaf dagindex 4 blokken per dagdeel. Dekking van band en blokken neemt af
   * met de relatieve breedte van de band (scherp vs. vaag).
   * Hover/aanraking: verticale lijn plus tekstlabel op het canvas.
   */
  function tekenGrafiek(canvas, model, opties) {
    opties = opties || {};
    let dagen, totUren;
    const staat = { hover: null };
    function zetModel(m) {
      model = m;
      dagen = opties.maxDagen ? model.dagen.slice(0, opties.maxDagen) : model.dagen;
      totUren = dagen.reduce(function (s, d) { return s + d.uren.length; }, 0);
      canvas.setAttribute('role', 'img');
      canvas.setAttribute('aria-label', 'Grafiek van de stroomprijs per uur over ' + dagen.length + ' dagen, met ondergrens en bovengrens. ' + samenvatting(model));
      canvas.tabIndex = 0;
    }
    zetModel(model);

    function teken() {
      const dpr = window.devicePixelRatio || 1;
      const breed = canvas.clientWidth || 600;
      const hoog = opties.hoogte || Math.max(220, Math.min(360, breed * 0.5));
      canvas.style.height = hoog + 'px';
      canvas.width = Math.round(breed * dpr);
      canvas.height = Math.round(hoog * dpr);
      const ctx = canvas.getContext('2d');
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, breed, hoog);

      const k = {
        tekst: cssVar(canvas, '--g-tekst', '#333'), zacht: cssVar(canvas, '--g-zacht', '#777'),
        raster: cssVar(canvas, '--g-raster', '#e5e5e5'), lijn: cssVar(canvas, '--g-lijn', '#1f5fbf'),
        bekend: cssVar(canvas, '--g-bekend', '#1f5fbf'), band: cssVar(canvas, '--g-band', '#1f5fbf'),
        nu: cssVar(canvas, '--g-nu', '#d9480f'), vlak: cssVar(canvas, '--g-vlak', '#ffffff'),
      };
      const compact = opties.compact || breed < 480;
      const pad = { l: compact ? 34 : 44, r: 8, t: 10, b: compact ? 40 : 36 };
      const pw = breed - pad.l - pad.r, ph = hoog - pad.t - pad.b;
      const ux = pw / totUren;

      // y-schaal: minimum 0 of lager als er negatieve prijzen zijn
      let ymin = 0, ymax = 1;
      dagen.forEach(function (d) {
        const reeks = d.perUur ? d.uren : d.dagdelen; // blokdagen: alleen wat getekend wordt telt mee
        reeks.forEach(function (u) { ymin = Math.min(ymin, u.p10); ymax = Math.max(ymax, u.p90); });
      });
      ymax = ymax * 1.08; if (ymin < 0) ymin = ymin * 1.1;
      const stap = mooieStap((ymax - ymin) / (compact ? 4 : 6));
      ymax = Math.ceil(ymax / stap) * stap; ymin = Math.floor(ymin / stap) * stap;
      const y = function (v) { return pad.t + ph - ((v - ymin) / (ymax - ymin)) * ph; };
      const x = function (i) { return pad.l + i * ux; };

      // raster en y-as
      ctx.font = (compact ? 11 : 12) + 'px system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';
      ctx.textBaseline = 'middle'; ctx.textAlign = 'right';
      for (let v = ymin; v <= ymax + 1e-9; v += stap) {
        ctx.strokeStyle = k.raster; ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(pad.l, y(v)); ctx.lineTo(breed - pad.r, y(v)); ctx.stroke();
        ctx.fillStyle = k.zacht; ctx.fillText(fmt(v, stap < 1 ? 1 : 0), pad.l - 6, y(v));
      }
      ctx.save(); ctx.translate(10, pad.t + ph / 2); ctx.rotate(-Math.PI / 2);
      ctx.textAlign = 'center'; ctx.fillStyle = k.zacht; ctx.fillText('ct/kWh', 0, 0); ctx.restore();

      // per dag tekenen
      let i0 = 0;
      const dagX = [];
      dagen.forEach(function (d) {
        const n = d.uren.length;
        const xa = x(i0), xb = x(i0 + n);
        dagX.push({ dag: d, xa: xa, xb: xb, i0: i0 });
        // dagscheiding
        ctx.strokeStyle = k.raster; ctx.lineWidth = 1;
        ctx.beginPath(); ctx.moveTo(xa, pad.t); ctx.lineTo(xa, pad.t + ph); ctx.stroke();
        // netspits 16–21 uur: arcering (positie via het uur, zodat 23- en 25-uurdagen goed gaan)
        const sVan = d.uren.find(function (u) { return u.uur === NETSPITS.van; });
        const sTot = d.uren.find(function (u) { return u.uur === NETSPITS.tot; });
        if (sVan && sTot) {
          ctx.fillStyle = arcering(ctx, k.zacht);
          ctx.fillRect(x(i0 + sVan.pos), pad.t, x(i0 + sTot.pos) - x(i0 + sVan.pos), ph);
        }

        if (d.perUur) {
          if (d.bekend) {
            // bekend: vol vlak onder een stapsgewijze lijn
            ctx.beginPath();
            d.reeks.forEach(function (u, j) { const xx = x(i0 + u.pos); if (j === 0) ctx.moveTo(xx, y(u.p50)); else ctx.lineTo(xx, y(u.p50)); ctx.lineTo(xx + ux * u.duur, y(u.p50)); });
            ctx.lineTo(xb, y(Math.max(ymin, 0))); ctx.lineTo(xa, y(Math.max(ymin, 0))); ctx.closePath();
            ctx.globalAlpha = 0.18; ctx.fillStyle = k.bekend; ctx.fill(); ctx.globalAlpha = 1;
            ctx.strokeStyle = k.bekend; ctx.lineWidth = d.perKwartier ? 1.5 : 2; ctx.lineJoin = 'round';
            ctx.beginPath();
            d.reeks.forEach(function (u, j) { const xx = x(i0 + u.pos); if (j === 0) ctx.moveTo(xx, y(u.p50)); else ctx.lineTo(xx, y(u.p50)); ctx.lineTo(xx + ux * u.duur, y(u.p50)); });
            ctx.stroke();
          } else {
            // voorspeld: band (dekking afhankelijk van vaagheid) plus P50-lijn
            ctx.beginPath();
            d.uren.forEach(function (u, j) { const xx = x(i0 + j) + ux / 2; if (j === 0) ctx.moveTo(xa, y(u.p90)); ctx.lineTo(xx, y(u.p90)); });
            ctx.lineTo(xb, y(d.uren[n - 1].p90));
            ctx.lineTo(xb, y(d.uren[n - 1].p10));
            for (let j = n - 1; j >= 0; j--) { ctx.lineTo(x(i0 + j) + ux / 2, y(d.uren[j].p10)); }
            ctx.lineTo(xa, y(d.uren[0].p10)); ctx.closePath();
            ctx.globalAlpha = 0.22; ctx.fillStyle = k.band; ctx.fill(); ctx.globalAlpha = 1;
            ctx.strokeStyle = k.lijn; ctx.lineWidth = 2; ctx.setLineDash([5, 4]);
            ctx.beginPath();
            d.uren.forEach(function (u, j) { const xx = x(i0 + j) + ux / 2; if (j === 0) ctx.moveTo(xa, y(u.p50)); ctx.lineTo(xx, y(u.p50)); });
            ctx.lineTo(xb, y(d.uren[n - 1].p50)); ctx.stroke();
            ctx.setLineDash([]);
          }
        } else {
          // blokken per dagdeel: lichte rechthoek voor de band (hoogte = onzekerheid), streep voor P50
          d.dagdelen.forEach(function (b) {
            const bx = x(i0 + b.van) + 2, bw = (b.tot - b.van) * ux - 4;
            ctx.globalAlpha = 0.22; ctx.fillStyle = k.band;
            afgerond(ctx, bx, y(b.p90), bw, Math.max(2, y(b.p10) - y(b.p90)), 3); ctx.fill();
            ctx.globalAlpha = 1; ctx.fillStyle = k.lijn;
            ctx.fillRect(bx, y(b.p50) - 1.5, bw, 3);
          });
        }
        // daglabel
        ctx.fillStyle = k.tekst; ctx.textAlign = 'left'; ctx.textBaseline = 'alphabetic';
        const lbl = compact ? WEEKDAGEN_KORT[d.weekdag] + ' ' + d.dagVdMaand : dagNaam(d, false);
        if (xb - xa > ctx.measureText(lbl).width + 6 || !compact) {
          ctx.fillText(lbl, xa + 4, hoog - pad.b + 16);
        } else {
          ctx.fillText(WEEKDAGEN_KORT[d.weekdag], xa + 4, hoog - pad.b + 16);
        }
        {
          const b = d.betrouwbaarheid;
          const sub = b.icoon + ' ' + b.label;
          const subKort = b.icoon;
          ctx.fillStyle = k.zacht;
          if (ctx.measureText(sub).width + 8 < xb - xa) ctx.fillText(sub, xa + 4, hoog - pad.b + 30);
          else if (ctx.measureText(subKort).width + 8 < xb - xa) ctx.fillText(subKort, xa + 4, hoog - pad.b + 30);
        }
        i0 += n;
      });
      ctx.textBaseline = 'middle';

      // nullijn
      if (ymin < 0) { ctx.strokeStyle = k.zacht; ctx.lineWidth = 1; ctx.beginPath(); ctx.moveTo(pad.l, y(0)); ctx.lineTo(breed - pad.r, y(0)); ctx.stroke(); }

      // hover
      if (staat.hover !== null) {
        const hx = staat.hover;
        const h = (hx - pad.l) / ux;
        if (h >= 0 && h < totUren) {
          let rest = h, dagI = 0, dagStart = 0;
          while (rest >= dagen[dagI].uren.length) { rest -= dagen[dagI].uren.length; dagStart += dagen[dagI].uren.length; dagI++; }
          const d = dagen[dagI];
          const u = d.reeks.find(function (q) { return rest >= q.pos && rest < q.pos + q.duur; }) || d.reeks[d.reeks.length - 1];
          const cx = x(dagStart + u.pos) + (ux * u.duur) / 2;
          ctx.strokeStyle = k.nu; ctx.lineWidth = 1; ctx.setLineDash([3, 3]);
          ctx.beginPath(); ctx.moveTo(cx, pad.t); ctx.lineTo(cx, pad.t + ph); ctx.stroke(); ctx.setLineDash([]);
          let r1, r2;
          if (d.perUur) {
            r1 = dagNaam(d, false) + ' ' + fmtUur(u.uur) + '–' + fmtUur(u.uur + u.duur);
            r2 = u.bekend ? fmt(u.p50) + ' ct/kWh' : 'verwacht ' + fmt(u.p50) + ' (' + plusMinCt(u.p90 - u.p50, u.p50 - u.p10) + ')';
            ctx.fillStyle = k.nu; ctx.beginPath(); ctx.arc(cx, y(u.p50), 4, 0, Math.PI * 2); ctx.fill();
          } else {
            const b = d.dagdelen.find(function (b) { return u.uur >= b.van && u.uur < b.tot; });
            r1 = dagNaam(d, false) + ', ' + b.label.toLowerCase() + ' ' + fmtUur(b.van) + '–' + fmtUur(b.tot);
            r2 = 'verwacht ' + fmt(b.p50) + ' (' + plusMinCt(b.p90 - b.p50, b.p50 - b.p10) + ')';
          }
          ctx.font = (compact ? 11 : 12) + 'px system-ui, -apple-system, "Segoe UI", Roboto, sans-serif';
          const w = Math.max(ctx.measureText(r1).width, ctx.measureText(r2).width) + 16;
          let bx = cx + 10; if (bx + w > breed - pad.r) bx = cx - 10 - w;
          const by = pad.t + 4;
          ctx.fillStyle = k.vlak; ctx.globalAlpha = 0.95; afgerond(ctx, bx, by, w, 40, 4); ctx.fill(); ctx.globalAlpha = 1;
          ctx.strokeStyle = k.raster; afgerond(ctx, bx, by, w, 40, 4); ctx.stroke();
          ctx.textAlign = 'left'; ctx.fillStyle = k.tekst; ctx.fillText(r1, bx + 8, by + 13);
          ctx.fillStyle = k.zacht; ctx.fillText(r2, bx + 8, by + 29);
        }
      }
    }

    let arceerPatroon = null, arceerKleur = null;
    function arcering(ctx, kleur) {
      if (arceerPatroon && arceerKleur === kleur) return arceerPatroon;
      const c = document.createElement('canvas'); c.width = 8; c.height = 8;
      const g = c.getContext('2d');
      g.strokeStyle = kleur; g.globalAlpha = 0.28; g.lineWidth = 1;
      g.beginPath(); g.moveTo(-2, 10); g.lineTo(10, -2); g.moveTo(-2, 2); g.lineTo(2, -2); g.moveTo(6, 10); g.lineTo(10, 6); g.stroke();
      arceerPatroon = ctx.createPattern(c, 'repeat'); arceerKleur = kleur;
      return arceerPatroon;
    }
    function mooieStap(ruw) {
      const m = Math.pow(10, Math.floor(Math.log10(ruw)));
      const r = ruw / m;
      return (r < 1.5 ? 1 : r < 3.5 ? 2 : r < 7.5 ? 5 : 10) * m;
    }
    function afgerond(ctx, x, y, w, h, r) {
      ctx.beginPath(); ctx.moveTo(x + r, y); ctx.lineTo(x + w - r, y); ctx.quadraticCurveTo(x + w, y, x + w, y + r);
      ctx.lineTo(x + w, y + h - r); ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h); ctx.lineTo(x + r, y + h);
      ctx.quadraticCurveTo(x, y + h, x, y + h - r); ctx.lineTo(x, y + r); ctx.quadraticCurveTo(x, y, x + r, y); ctx.closePath();
    }
    function posX(ev) {
      const r = canvas.getBoundingClientRect();
      const p = ev.touches ? ev.touches[0] : ev;
      return p.clientX - r.left;
    }
    canvas.addEventListener('mousemove', function (ev) { staat.hover = posX(ev); teken(); });
    canvas.addEventListener('mouseleave', function () { staat.hover = null; teken(); });
    canvas.addEventListener('touchstart', function (ev) { staat.hover = posX(ev); teken(); }, { passive: true });
    canvas.addEventListener('touchmove', function (ev) { staat.hover = posX(ev); teken(); }, { passive: true });
    canvas.addEventListener('touchend', function () { staat.hover = null; teken(); });
    if (window.ResizeObserver) new ResizeObserver(function () { teken(); }).observe(canvas);
    else window.addEventListener('resize', teken);
    if (window.matchMedia) window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', teken);
    teken();
    return { teken: teken, update: function (m) { zetModel(m); teken(); } };
  }

  // ---------- startadvies: "start je apparaat om ..." (besluit 58) ----------
  function nuLokaalUur() {
    const p = new Date().toLocaleTimeString('en-GB', { timeZone: 'Europe/Amsterdam', hour12: false }).split(':').map(Number);
    return (p[0] % 24) + p[1] / 60;
  }
  /*
   * startAdvies(model, apparaat, nuUur): het goedkoopste blok ter lengte van de duur dat nog kan beginnen vanaf nu,
   * op de eerste getoonde dag (mag over middernacht heen lopen). Past er vandaag niets meer, dan de volgende dag.
   * `later`: de volgende dag als die duidelijk goedkoper is (minstens 10% en 5 cent per beurt).
   */
  function startAdvies(model, app, nuUur) {
    const dagen = model.dagen;
    if (!dagen.length) return null;
    const d0 = dagen[0], d1 = dagen[1];
    const vandaag = d0.datum === vandaagLokaal();
    const stap = d0.perKwartier ? 0.25 : 1;
    const n = Math.max(1, Math.round(app.uren / stap));
    const reeks = vandaag ? d0.reeks.filter(function (u) { return u.uur + u.duur > nuUur + 1e-9; }) : d0.reeks;
    let vervolg = d1 ? (stap === 1 ? d1.uren : naarKwartieren(d1.reeks)) : [];
    let dag = d0, blok = reeks.length ? goedkoopsteBlok(reeks, n, vervolg) : null;
    if (!blok && d1) { dag = d1; blok = (d1.blokken || {})[app.id] || goedkoopsteBlok(d1.reeks, Math.max(1, Math.round(app.uren / (d1.perKwartier ? 0.25 : 1)))); }
    if (!blok) return null;
    if (blok.volgendeDag && dagen[dag.index + 1]) blok.eindDagNaam = dagNaam(dagen[dag.index + 1], false);
    const k = blokKosten(blok, app.kwh);
    const uit = { apparaat: app, dag: dag, blok: blok, euro: k.euro, later: null };
    const volgende = dagen[dag.index + 1];
    const vb = volgende ? (volgende.blokken || {})[app.id] : null;
    if (vb) {
      const kv = blokKosten(vb, app.kwh);
      if (kv.euro < k.euro - Math.max(0.05, 0.10 * Math.abs(k.euro))) uit.later = { dag: volgende, blok: vb, euro: kv.euro, winst: k.euro - kv.euro };
    }
    return uit;
  }

  // ---------- kosten per handeling: "wat kost het als ik het nu doe?" ----------
  // auto: blok en kWh uit de laadinstellingen (model.laad); was: vast blok en vast verbruik
  const APPARATEN = [
    { id: 'auto', naam: 'Standaardlaadbeurt', streng: true, blok: 'laden' },
    { id: 'was', naam: 'Wasbeurt', streng: false, blok: 'wassen' },
  ];
  // de auto plus de eigen apparaten uit het model
  function apparatenLijst(model) {
    return [APPARATEN[0]].concat((model.apparaten || []).map(function (a) {
      return { id: a.id, naam: a.naam, streng: false, blok: 'apparaat', uren: a.uren, kwh: a.kwh };
    }));
  }
  function fmtEuro(x) {
    if (x === null || x === undefined || Number.isNaN(x)) return '–';
    const a = Math.abs(x);
    if (a < 1) return Math.round(a * 100) + ' cent';
    return '€ ' + a.toFixed(2).replace('.', ',');
  }
  /*
   * kostenAdvies(model, apparaat, drempelEuro)
   * Vergelijkt het goedkoopste 3-uursblok van morgen (zeker) met het goedkoopste
   * verwachte blok in de dagen erna. Alles in euro per handeling (kWh × prijs).
   * streng: wachten alleen aanraden als het ook bij de bovengrens nog loont.
   * Resultaat: { zeker, duurste, beste, winst, winstSlecht, winstGoed, soort, advies }
   * soort: 'gewoon' (scheelt niets), 'nu' (morgen is goedkoop), 'wacht', 'misschien'.
   */
  function kostenAdvies(model, app, drempelEuro) {
    const drempel = typeof drempelEuro === 'number' ? drempelEuro : 0.5;
    const kwh = app.blok === 'laden' ? model.laad.kwh : app.blok === 'apparaat' ? app.kwh : WAS_KWH;
    const blokVan = function (d) { return app.blok === 'apparaat' ? (d.blokken || {})[app.id] : d[app.blok]; };
    const euro = function (ct) { return (ct * kwh) / 100; };
    const morgen = model.dagen[1] || model.dagen[0];
    const mb = blokVan(morgen);
    const later = model.dagen.filter(function (d) { return d.index > morgen.index && !d.bekend && blokVan(d); });
    let beste = null;
    later.forEach(function (d) { if (!beste || blokVan(d).p50 < blokVan(beste).p50) beste = d; });
    const bb = beste ? blokVan(beste) : null;
    const r = {
      apparaat: app, morgen: morgen, kwh: kwh, uren: mb.n,
      zeker: { blok: mb, euro: euro(mb.p50) },
      duurste: { blok: mb.duurste, euro: euro(mb.duurste.p50) },
      beste: beste ? { dag: beste, blok: bb, euro: euro(bb.p50), euroLaag: euro(bb.p10), euroHoog: euro(bb.p90) } : null,
    };
    const naam = dagNaam(morgen, true);
    if (!beste) {
      r.soort = 'nu'; r.winst = 0;
      r.advies = 'Geen verwachting verder vooruit. ' + naam + ' ' + blokTijd(mb) + ' is het goedkoopste moment dat zeker is.';
      return r;
    }
    r.winst = euro(mb.p50 - bb.p50);
    r.winstSlecht = euro(mb.p50 - bb.p90);
    r.winstGoed = euro(mb.p50 - bb.p10);
    const dagL = dagNaam(beste, true).toLowerCase();
    if (Math.abs(r.winst) < drempel) {
      r.soort = 'gewoon';
      r.advies = 'Scheelt vrijwel niets: hooguit ' + fmtEuro(Math.max(Math.abs(r.winst), Math.abs(r.winstGoed))) + ' met ' + dagL + '. Doe het wanneer het uitkomt.';
    } else if (r.winst > 0) {
      if (app.streng && r.winstSlecht < drempel) {
        r.soort = 'misschien';
        r.advies = 'Op ' + dagL + ' waarschijnlijk ' + fmtEuro(r.winst) + ' goedkoper, maar dat is niet zeker (' + plusMinEuro(r.winstGoed - r.winst, r.winst - r.winstSlecht) + '). ' + naam + ' alleen laden wat u nodig hebt is een veilige keuze.';
      } else {
        r.soort = 'wacht';
        r.advies = 'Wachten tot ' + dagL + ' loont: waarschijnlijk ' + fmtEuro(r.winst) + ' goedkoper (' + plusMinEuro(r.winstGoed - r.winst, r.winst - r.winstSlecht) + ').';
      }
    } else {
      r.soort = 'nu';
      r.advies = naam + ' is goedkoper dan de rest van de week: ' + fmtEuro(-r.winst) + ' minder dan ' + dagL + '. Goed moment om het te doen.';
    }
    if (r.soort !== 'nu' && beste.betrouwbaarheid.code === 'laag') r.advies += ' Nog onzeker, kijk een dag later opnieuw.';
    return r;
  }

  // ---------- laden ----------
  function laadForecast(url) {
    return fetch(url, { cache: 'no-store' }).then(function (r) {
      if (!r.ok) throw new Error('Kon de voorspelling niet laden (' + r.status + ').');
      return r.json();
    });
  }

  // tijdstip van genereren, lokaal en leesbaar
  function gegenereerdTekst(iso) {
    try {
      const d = new Date(iso);
      return d.toLocaleString('nl-NL', { weekday: 'long', day: 'numeric', month: 'long', hour: '2-digit', minute: '2-digit', timeZone: 'Europe/Amsterdam' });
    } catch (e) { return iso; }
  }

  // tarief-formulier koppelen: verwacht inputs #opslag, #belasting, #btw, checkbox #tarief-aan, en roept bijRefresh(tarief) aan
  // tariefschakelaar koppelen: opties = { standen: element met knoppen [data-stand], inkoop: input, uitleg: element (optioneel), form: formulier (optioneel) }
  // leverancierslijst (leveranciers.json): { peildatum_lijst, leveranciers: [{ naam, inkoopvergoeding_ct_kwh_excl_btw, vaste_kosten_maand_eur_incl_btw, status, peildatum, bron_url }] }
  function laadLeveranciers(url) {
    return fetch(url, { cache: 'no-store' }).then(function (r) { return r.ok ? r.json() : { leveranciers: [] }; })
      .catch(function () { return { leveranciers: [] }; });
  }
  function datumTekst(iso) {
    if (!iso || iso.length < 10) return '';
    return parseInt(iso.slice(8, 10), 10) + ' ' + MAANDEN[parseInt(iso.slice(5, 7), 10) - 1] + ' ' + iso.slice(0, 4);
  }
  // tekst onder de keuzelijst, per status; nooit jargon
  function leverancierInfo(lev) {
    if (!lev) return '';
    const bedrag = typeof lev.inkoopvergoeding_ct_kwh_excl_btw === 'number' ? fmt(lev.inkoopvergoeding_ct_kwh_excl_btw, 2) + ' ct excl. btw' : null;
    const datum = lev.peildatum ? ', peildatum ' + datumTekst(lev.peildatum) : '';
    if (lev.status === 'bevestigd_tariefpagina' && bedrag) return bedrag + ', bevestigd op tariefpagina' + datum + '.';
    if (lev.status === 'alleen_vergelijker' && bedrag) return bedrag + ', via vergelijker, controleer bij je leverancier' + datum + '.';
    return 'Publiceert geen bedrag, vul zelf in. Tot dan rekenen we met ' + fmt(INKOOP_STANDAARD_CT, 2) + ' ct.';
  }
  /*
   * koppelTarief(opties, bijRefresh)
   * opties: { standen: element met knoppen [data-stand], inkoop: input, uitleg: element (optioneel), form: formulier (optioneel),
   *           leveranciers: select (optioneel), leverancierInfo: element (optioneel), leveranciersNoot: element (optioneel), lijst: leveranciers.json (optioneel) }
   */
  function koppelTarief(opties, bijRefresh) {
    const knoppen = Array.from(opties.standen.querySelectorAll('[data-stand]'));
    const inkoopEl = opties.inkoop;
    const selEl = opties.leveranciers;
    const lijst = (opties.lijst && opties.lijst.leveranciers) || [];
    let t = leesTarief();
    function levVan(naam) { return lijst.find(function (l) { return l.naam === naam; }) || null; }
    if (selEl) {
      selEl.innerHTML = '<option value="">Anders / zelf invullen</option>' + lijst.map(function (l) {
        return '<option value="' + l.naam.replace(/"/g, '&quot;') + '">' + l.naam + '</option>';
      }).join('');
      if (t.leverancier && levVan(t.leverancier)) selEl.value = t.leverancier; else { selEl.value = ''; t.leverancier = null; }
      if (opties.leveranciersNoot) opties.leveranciersNoot.textContent = 'Tarieven veranderen; wij controleren elk kwartaal.' + (opties.lijst && opties.lijst.peildatum_lijst ? ' Peildatum van de lijst: ' + datumTekst(opties.lijst.peildatum_lijst) + '.' : '');
    }
    function toonInkoop() {
      if (!inkoopEl) return;
      inkoopEl.value = typeof t.inkoop === 'number' ? t.inkoop : '';
      inkoopEl.placeholder = fmt(INKOOP_STANDAARD_CT, 2) + ' (standaard)';
    }
    function toonInfo(eigen) {
      if (!opties.leverancierInfo) return;
      const lev = t.leverancier ? levVan(t.leverancier) : null;
      if (eigen && typeof t.inkoop === 'number') opties.leverancierInfo.textContent = 'Eigen bedrag: ' + fmt(t.inkoop, 2) + ' ct excl. btw.';
      else opties.leverancierInfo.textContent = leverancierInfo(lev);
    }
    function toon() {
      knoppen.forEach(function (b) { b.setAttribute('aria-pressed', b.dataset.stand === t.stand ? 'true' : 'false'); });
      if (opties.uitleg) opties.uitleg.textContent = TARIEF_STANDEN[t.stand].label + ': ' + TARIEF_STANDEN[t.stand].uitleg + '.';
    }
    function toepassen() { bewaarTarief(t); toon(); bijRefresh(t); }
    knoppen.forEach(function (b) {
      b.title = TARIEF_STANDEN[b.dataset.stand] ? TARIEF_STANDEN[b.dataset.stand].uitleg : '';
      b.addEventListener('click', function () { t = netTarief({ stand: b.dataset.stand, inkoop: t.inkoop, leverancier: t.leverancier }); toepassen(); });
    });
    if (selEl) selEl.addEventListener('change', function () {
      const lev = levVan(selEl.value);
      const bedrag = lev && typeof lev.inkoopvergoeding_ct_kwh_excl_btw === 'number' ? Math.round(lev.inkoopvergoeding_ct_kwh_excl_btw * 100) / 100 : null;
      t = netTarief({ stand: t.stand, inkoop: lev ? bedrag : t.inkoop, leverancier: lev ? lev.naam : null });
      toonInkoop(); toonInfo(false); toepassen();
    });
    if (inkoopEl) inkoopEl.addEventListener('change', function () {
      const v = parseFloat(String(inkoopEl.value).replace(',', '.'));
      t = netTarief({ stand: t.stand, inkoop: v >= 0 ? v : null, leverancier: t.leverancier });
      toonInkoop(); toonInfo(true); toepassen();
    });
    if (opties.form) opties.form.addEventListener('submit', function (ev) { ev.preventDefault(); toepassen(); });
    toonInkoop();
    const lev0 = t.leverancier ? levVan(t.leverancier) : null;
    const eigen0 = !!(lev0 && typeof t.inkoop === 'number' && Math.abs(t.inkoop - (lev0.inkoopvergoeding_ct_kwh_excl_btw || 0)) > 0.006);
    toonInfo(eigen0);
    toon();
    return t;
  }
  function tariefUitlegTekst() {
    return 'Tarieven ' + TARIEF_JAAR + ': energiebelasting ' + fmt(ENERGIEBELASTING_CT) + ' ct/kWh zonder btw (' + fmt(ENERGIEBELASTING_CT * (1 + BTW_PCT / 100)) + ' ct met btw), btw ' + BTW_PCT + '%.';
  }

  window.SP = {
    DAGDELEN: DAGDELEN, STOPLICHT: STOPLICHT, fmt: fmt, fmtUur: fmtUur, dagNaam: dagNaam, dagDatumKort: dagDatumKort, datumTekst: datumTekst, vandaagLokaal: vandaagLokaal, msTotMiddernacht: msTotMiddernacht,
    leesTarief: leesTarief, bewaarTarief: bewaarTarief, naarCt: naarCt, verwerk: verwerk, vaagheid: vaagheid, dekking: dekking,
    TARIEF_JAAR: TARIEF_JAAR, ENERGIEBELASTING_CT: ENERGIEBELASTING_CT, BTW_PCT: BTW_PCT, INKOOP_STANDAARD_CT: INKOOP_STANDAARD_CT,
    TARIEF_STANDEN: TARIEF_STANDEN, TARIEF_STANDAARD: TARIEF_STANDAARD, tariefFactor: tariefFactor, tariefLabel: tariefLabel, tariefUitlegTekst: tariefUitlegTekst,
    laadLeveranciers: laadLeveranciers, leverancierInfo: leverancierInfo, inkoopEffectief: inkoopEffectief,
    goedkoopsteBlok: goedkoopsteBlok, blokZin: blokZin, bandZin: bandZin, plusMinCt: plusMinCt, plusMinEuro: plusMinEuro, betrouwbaarheidsWoord: betrouwbaarheidsWoord,
    samenvatting: samenvatting, maakTabel: maakTabel, stoplichtHtml: stoplichtHtml, tekenGrafiek: tekenGrafiek,
    laadForecast: laadForecast, gegenereerdTekst: gegenereerdTekst, koppelTarief: koppelTarief,
    APPARATEN: APPARATEN, apparatenLijst: apparatenLijst, kostenAdvies: kostenAdvies, fmtEuro: fmtEuro, startAdvies: startAdvies, nuLokaalUur: nuLokaalUur,
    leesApparaten: leesApparaten, bewaarApparaten: bewaarApparaten, koppelApparaten: koppelApparaten, apparaatZin: apparaatZin, duurTekst: duurTekst,
    BETROUWBAARHEID: BETROUWBAARHEID, betrouwbaarheidTekst: betrouwbaarheidTekst, betrouwbaarheidHtml: betrouwbaarheidHtml,
    blokKosten: blokKosten, blokTijd: blokTijd, laadZin: laadZin, wasZin: wasZin,
    leesLaadinstellingen: leesLaadinstellingen, bewaarLaadinstellingen: bewaarLaadinstellingen, laadBlokUren: laadBlokUren,
    laadKwh: laadKwh, laadUitleg: laadUitleg, koppelLaadinstellingen: koppelLaadinstellingen,
    leesResolutie: leesResolutie, bewaarResolutie: bewaarResolutie, koppelResolutie: koppelResolutie,
    LAAD_STANDAARD_UREN: LAAD_STANDAARD_UREN, LAAD_STANDAARD_KWH: LAAD_STANDAARD_KWH, KWH_PER_KM: KWH_PER_KM,
    LAAD_KEUZES_KW: LAAD_KEUZES_KW, WAS_BLOK_UREN: WAS_BLOK_UREN, WAS_KWH: WAS_KWH, NETSPITS: NETSPITS,
  };
})();
