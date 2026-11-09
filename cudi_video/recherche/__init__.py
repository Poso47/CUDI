"""Recherche-Agent: sucht, öffnet und liest Webseiten wie ein Mensch, prüft Datum und Herkunft und gleicht mit unabhängigen Quellen ab.

    suche(anfrage, sprache, zeitraum)  -> {"treffer", "schritte"}
    lese(url)                          -> Haupttext, Datum, Betreiber, Eigentümer, Seitentyp
    recherchiere(frage, bereich)       -> {"aussagen", "widersprueche", "quellen", "stand", "schritte"}

Aus ist die Recherche mit CUDI_RECHERCHE=0 (Tests). Doku: docs/recherche.md, Skill `recherche`.
"""

from __future__ import annotations

import os

from .ablauf import BEREICHE, MAX_ALTER, anfragen_planen, bericht, recherchiere, seiten_als_quellen  # noqa: F401
from .cache import neuer_lauf  # noqa: F401
from .lesen import lese, parse_datum  # noqa: F401
from .suche import suche  # noqa: F401
from .wikipedia import darf_belegen, pruefe_seite  # noqa: F401


def aktiv() -> bool:
    return os.environ.get("CUDI_RECHERCHE") != "0"
