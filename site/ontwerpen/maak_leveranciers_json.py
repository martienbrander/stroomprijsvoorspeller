"""Maak site/ontwerpen/leveranciers.json uit data/leveranciers.yaml.

Alleen leveranciers met dynamisch_aanbod: true, alfabetisch, met de velden die de site gebruikt.
In de pipeline wordt dit later site/data/leveranciers.json met dezelfde veldnamen.

Gebruik (vanuit de projectmap):
    .venv\\Scripts\\python site/ontwerpen/maak_leveranciers_json.py
"""
from __future__ import annotations

import json
from pathlib import Path

import yaml

PROJECT = Path(__file__).resolve().parents[2]
BRON = PROJECT / "data" / "leveranciers.yaml"
DOEL = Path(__file__).resolve().parent / "leveranciers.json"
VELDEN = [
    "naam",
    "inkoopvergoeding_ct_kwh_excl_btw",
    "vaste_kosten_maand_eur_incl_btw",
    "status",
    "peildatum",
    "bron_url",
]


def main() -> None:
    data = yaml.safe_load(BRON.read_text(encoding="utf-8"))
    items = [
        {veld: lev.get(veld) for veld in VELDEN}
        for lev in data["leveranciers"]
        if lev.get("dynamisch_aanbod") is True
    ]
    items.sort(key=lambda x: x["naam"].casefold())
    uit = {
        "peildatum_lijst": data.get("peildatum_lijst"),
        "bron_register": data.get("bron_register"),
        "leveranciers": items,
    }
    DOEL.write_text(json.dumps(uit, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(f"{len(items)} leveranciers met dynamisch aanbod -> {DOEL}")


if __name__ == "__main__":
    main()
