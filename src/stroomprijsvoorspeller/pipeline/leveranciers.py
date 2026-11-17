"""Bewaakt de leeftijd van de leverancierstabel in data/leveranciers.yaml (besluit 36 en 77).

De tabel wordt met de hand bijgehouden. Vier keer per jaar is er een vaste controledatum: de eerste dag van elk
kwartaal. De regel is simpel: na een controledatum moet `peildatum_lijst` op of na die datum liggen. Is dat niet zo,
dan is de lijst toe aan controle. De wekelijkse workflow op GitHub opent dan een issue.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import yaml

from stroomprijsvoorspeller.config import Config

CONTROLEMAANDEN = (1, 4, 7, 10)   # vaste controledatum: de eerste dag van deze maanden
MAANDEN = ("januari", "februari", "maart", "april", "mei", "juni", "juli", "augustus", "september", "oktober",
           "november", "december")


@dataclass(frozen=True)
class Stand:
    """Hoe de lijst er op een bepaalde dag voor staat."""

    peildatum: date | None   # peildatum_lijst uit de yaml; None als die ontbreekt of onleesbaar is
    vorige_controle: date    # laatste vaste controledatum op of voor vandaag
    volgende_controle: date  # eerste vaste controledatum na vandaag
    verouderd: bool          # True als de lijst sinds de vorige controledatum niet is nagelopen


def vorige_controledatum(vandaag: date) -> date:
    """De laatste eerste dag van een kwartaal, op of voor vandaag."""
    maand = max(m for m in CONTROLEMAANDEN if m <= vandaag.month)
    return date(vandaag.year, maand, 1)


def volgende_controledatum(vandaag: date) -> date:
    """De eerste eerste dag van een kwartaal na vandaag."""
    later = [m for m in CONTROLEMAANDEN if m > vandaag.month]
    return date(vandaag.year, later[0], 1) if later else date(vandaag.year + 1, CONTROLEMAANDEN[0], 1)


def lees_peildatum(cfg: Config) -> date | None:
    """`peildatum_lijst` uit data/leveranciers.yaml; None als het bestand of de datum ontbreekt of niet klopt."""
    pad = cfg.root / "data" / "leveranciers.yaml"
    if not pad.exists():
        return None
    waarde = (yaml.safe_load(pad.read_text(encoding="utf-8")) or {}).get("peildatum_lijst")
    try:
        return date.fromisoformat(str(waarde))
    except ValueError:
        return None


def bepaal_stand(cfg: Config, vandaag: date) -> Stand:
    peildatum = lees_peildatum(cfg)
    vorige = vorige_controledatum(vandaag)
    return Stand(peildatum=peildatum, vorige_controle=vorige, volgende_controle=volgende_controledatum(vandaag),
                 verouderd=peildatum is None or peildatum < vorige)


def _datum(dag: date) -> str:
    return f"{dag.day} {MAANDEN[dag.month - 1]} {dag.year}"


def melding(stand: Stand, vandaag: date) -> str:
    """Tekst voor de commandoregel en, als de lijst verouderd is, voor het issue op GitHub."""
    if not stand.verouderd:
        return (f"Leverancierstabel: peildatum {_datum(stand.peildatum)}, {(vandaag - stand.peildatum).days} dagen oud. "
                f"Volgende controle: {_datum(stand.volgende_controle)}.")
    if stand.peildatum is None:
        kop = "De leverancierstabel heeft geen leesbare `peildatum_lijst`."
    else:
        kop = (f"De leverancierstabel is toe aan controle. Peildatum van de lijst: {_datum(stand.peildatum)} "
               f"({(vandaag - stand.peildatum).days} dagen oud). Sinds de vaste controledatum "
               f"{_datum(stand.vorige_controle)} is de lijst niet nagelopen.")
    regels = [
        kop,
        "",
        "Wat te doen:",
        "",
        "1. Loop `data/leveranciers.yaml` na volgens het onderhoudsadvies in `reports/leveranciers-inventarisatie.md`.",
        "2. Zet `peildatum_lijst` op de datum van de controle, ook als er niets is veranderd.",
        "3. Sluit dit issue.",
    ]
    if stand.vorige_controle.month == 1:
        regels += ["", "Let op: per 1 januari wijzigen meestal ook de energiebelasting en de regels voor teruglevering."]
    return "\n".join(regels)
