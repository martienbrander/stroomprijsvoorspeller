"""Markdown-tabellen voor de rapporten in reports/ (backtest, methodenvergelijking, verversingen)."""

from __future__ import annotations

import numpy as np
import pandas as pd

# kolommen met aantallen: een heel getal staat er zonder decimalen, ook als pandas er een kommagetal van gemaakt heeft
TELKOLOMMEN = ("horizon_dag", "dag", "n", "count", "n_dagen", "dagen", "n_uren")


def _cel(waarde, opmaak: str | None, telkolom: bool) -> str:
    if not isinstance(waarde, str) and pd.isna(waarde):
        return ""
    if opmaak:
        return opmaak.format(waarde)
    is_komma = isinstance(waarde, (float, np.floating))
    if isinstance(waarde, (int, np.integer)) or (telkolom and is_komma and float(waarde).is_integer()):
        return str(int(waarde))
    if is_komma:
        return f"{waarde:.2f}"
    return str(waarde)


def md_tabel(df: pd.DataFrame, fmt: dict[str, str] | None = None, hernoem: dict[str, str] | None = None,
             leeg: str | None = None) -> str:
    """Zet een DataFrame om in een markdown-tabel.

    fmt:     opmaak per kolom, bijvoorbeeld {"dekking": "{:.3f}"}. Zonder opmaak: gehele getallen kaal,
             kommagetallen met twee decimalen, de rest als tekst.
    hernoem: kolomkoppen, bijvoorbeeld {"horizon_dag": "dag"}; `fmt` gebruikt de oorspronkelijke kolomnamen.
    leeg:    tekst in plaats van een tabel als het frame geen rijen heeft.
    Ontbrekende waarden worden een lege cel.
    """
    if leeg is not None and df.empty:
        return leeg
    fmt = fmt or {}
    hernoem = hernoem or {}
    kop = "| " + " | ".join(str(hernoem.get(c, c)) for c in df.columns) + " |"
    lijn = "|" + "|".join("---" for _ in df.columns) + "|"
    rijen = ["| " + " | ".join(_cel(rij[c], fmt.get(c), c in TELKOLOMMEN) for c in df.columns) + " |"
             for _, rij in df.iterrows()]
    return "\n".join([kop, lijn, *rijen])
