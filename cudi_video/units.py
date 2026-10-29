"""Einheiten umrechnen und Zahlen sprachgerecht formatieren (Anzeige und Sprechtext)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Unit:
    symbol: str
    spoken: dict[str, str]          # Sprechform je Sprache (Plural)
    factor: float                   # SI-Wert * factor = Wert in dieser Einheit


# Ziel-Einheiten je Wikidata-SI-Einheit. Der erste Eintrag ist der Standard.
UNITS: dict[str, dict[str, Unit]] = {
    "Q11573": {  # Meter
        "m": Unit("m", {"de": "Meter", "en": "meters"}, 1.0),
        "km": Unit("km", {"de": "Kilometer", "en": "kilometers"}, 1e-3),
    },
    "Q25343": {  # Quadratmeter
        "km2": Unit("km²", {"de": "Quadratkilometer", "en": "square kilometers"}, 1e-6),
        "m2": Unit("m²", {"de": "Quadratmeter", "en": "square meters"}, 1.0),
    },
    "Q11570": {  # Kilogramm
        "t": Unit("t", {"de": "Tonnen", "en": "tonnes"}, 1e-3),
        "kg": Unit("kg", {"de": "Kilogramm", "en": "kilograms"}, 1.0),
    },
    "Q182429": {  # Meter pro Sekunde
        "km/h": Unit("km/h", {"de": "Kilometer pro Stunde", "en": "kilometers per hour"}, 3.6),
        "m/s": Unit("m/s", {"de": "Meter pro Sekunde", "en": "meters per second"}, 1.0),
    },
    "Q11574": {  # Sekunde
        "s": Unit("s", {"de": "Sekunden", "en": "seconds"}, 1.0),
    },
    "Q199": {  # ohne Einheit (z. B. Einwohner)
        "": Unit("", {"de": "", "en": ""}, 1.0),
    },
}

_BIG = {
    "de": [(1e12, "Bio.", "Billionen"), (1e9, "Mrd.", "Milliarden"), (1e6, "Mio.", "Millionen")],
    "en": [(1e12, "T", "trillion"), (1e9, "B", "billion"), (1e6, "M", "million")],
}


def resolve_unit(unit_qid: str, wanted: str | None) -> Unit | None:
    options = UNITS.get(unit_qid)
    if not options:
        return None
    if wanted is not None and wanted in options:
        return options[wanted]
    return next(iter(options.values()))


def fmt_number(x: float, lang: str, decimals: int = 0) -> str:
    """1234567.8 -> '1.234.568' (de) bzw. '1,234,568' (en)."""
    s = f"{x:,.{decimals}f}"
    if lang == "de":
        s = s.replace(",", "\0").replace(".", ",").replace("\0", ".")
    return s


def _auto_decimals(x: float) -> int:
    if abs(x) >= 100 or float(x).is_integer():
        return 0
    return 1 if abs(x) >= 10 else 2


@dataclass
class Quantity:
    value: float            # in Anzeige-Einheit
    unit: Unit | None

    def display(self, lang: str, value: float | None = None) -> str:
        """Für die Einblendung. `value` erlaubt animiertes Hochzählen."""
        v = self.value if value is None else value
        symbol = self.unit.symbol if self.unit else ""
        if not symbol and abs(self.value) >= 1e6:
            for threshold, short, _ in _BIG[lang]:
                if abs(self.value) >= threshold:
                    return f"{fmt_number(v / threshold, lang, 2)} {short}"
        text = fmt_number(v, lang, _auto_decimals(self.value))
        return f"{text} {symbol}".strip()

    def spoken(self, lang: str) -> str:
        """Für die Stimme: große Zahlen gerundet in Worten, damit es natürlich klingt."""
        v = self.value
        unit_word = self.unit.spoken[lang] if self.unit else ""
        for threshold, _, word in _BIG[lang]:
            if abs(v) >= threshold:
                scaled = v / threshold
                number = fmt_number(scaled, lang, 0 if scaled >= 100 else 1).removesuffix(",0").removesuffix(".0")
                return f"{number} {word} {unit_word}".strip()
        return f"{fmt_number(v, lang, _auto_decimals(v))} {unit_word}".strip()


def quantity(si_value: float, unit_qid: str, wanted: str | None = None) -> Quantity:
    unit = resolve_unit(unit_qid, wanted)
    factor = unit.factor if unit else 1.0
    return Quantity(si_value * factor, unit)
