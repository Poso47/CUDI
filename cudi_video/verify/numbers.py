"""Zahlen in Texten verschiedener Sprachen finden und mit einem erwarteten Wert vergleichen.

Beispiele, die erkannt werden: "828 m", "17 098 246 km²", "17,1 millions de km2",
"1,4 Milliarden", "1709.8万平方公里", "٨٢٨ مترًا". Mehrdeutige Schreibweisen wie
"8.849" (Tausender- oder Dezimalpunkt) werden in beiden Lesarten geprüft.
"""

from __future__ import annotations

import re

# Ostarabische/persische Ziffern -> 0-9
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

SCALES = [
    (re.compile(r"^(milliard|milliarden|mil millones|miliardi|bilh|миллиард|млрд|mrd|billion|bn)", re.I), 1e9),
    (re.compile(r"^(million|millionen|millones|milioni|milh|миллион|млн|mln|mio|millón)", re.I), 1e6),
    (re.compile(r"^(億|亿)"), 1e8),
    (re.compile(r"^(万|萬)"), 1e4),
]

_NUMBER = re.compile(
    r"(?<![\d.,])(\d{1,3}(?:[    .,’']\d{3})+(?:[.,]\d+)?|\d+(?:[.,]\d+)?)(?![\d])"
)


def _interpretations(raw: str) -> list[tuple[float, float]]:
    """Mögliche (Wert, Genauigkeit) für eine Zahl-Zeichenkette."""
    s = raw.replace(" ", " ").replace(" ", " ").replace(" ", " ").replace("’", "'")
    out = []
    seps = [c for c in s if c in " .,'"]
    if not seps:
        return [(float(s), 1.0)]
    if " " in s or "'" in s:
        # Leerzeichen/Apostroph = Tausendertrenner, letzter Punkt/Komma evtl. Dezimal
        body = s.replace(" ", "").replace("'", "")
        return _interpretations(body) if body != s else [(float(body), 1.0)]
    dots, commas = s.count("."), s.count(",")
    if dots and commas:
        dec = "." if s.rfind(".") > s.rfind(",") else ","
        thou = "," if dec == "." else "."
        num = s.replace(thou, "").replace(dec, ".")
        decimals = len(num.split(".")[1])
        return [(float(num), 10 ** -decimals)]
    sep = "." if dots else ","
    parts = s.split(sep)
    # Lesart 1: Tausendertrenner (nur wenn alle Gruppen nach dem ersten 3-stellig sind)
    if all(len(p) == 3 for p in parts[1:]):
        out.append((float("".join(parts)), 1.0))
    # Lesart 2: Dezimaltrenner (nur bei genau einem Trenner)
    if len(parts) == 2:
        out.append((float(f"{parts[0]}.{parts[1]}"), 10 ** -len(parts[1])))
    return out


def find_numbers(text: str) -> list[tuple[float, float]]:
    """Alle Zahlen als (Wert, Genauigkeit), inklusive Größenwörtern wie 'Millionen' oder '万'."""
    text = text.translate(_DIGITS)
    found = []
    for m in _NUMBER.finditer(text):
        tail = text[m.end(): m.end() + 14].lstrip("  ")
        scale = 1.0
        for pattern, factor in SCALES:
            if pattern.match(tail):
                scale = factor
                break
        for value, precision in _interpretations(m.group(1)):
            found.append((value * scale, precision * scale))
    return found


def mentions_value(text: str, expected: float, rel_tol: float = 0.002) -> bool:
    """Kommt der erwartete Wert (in der Anzeige-Einheit) im Text vor – exakt oder sinnvoll gerundet?"""
    if not text or not expected:
        return False
    expected = abs(expected)
    for value, precision in find_numbers(text):
        if value <= 0:
            continue
        # Jahreszahlen nicht als Treffer zählen, wenn der Wert offensichtlich keine ist
        if precision == 1.0 and 1000 <= value <= 2100 and not (1000 <= expected <= 2100):
            continue
        tolerance = max(expected * rel_tol, precision / 2 * 1.001)
        # Gerundete Angaben ("17,1 Millionen") nur akzeptieren, wenn sie nicht zu grob sind
        if precision / expected > 0.05:
            continue
        if abs(value - expected) <= tolerance:
            return True
    return False
