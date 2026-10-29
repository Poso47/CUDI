"""Die "Vorgabe" eines Videos: Thema, Datenquelle, Sprachen, Länge."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from pathlib import Path

import yaml

from . import config


@dataclass
class WikidataSource:
    """Ranking aus Wikidata: alle Objekte einer Klasse, sortiert nach einer Mengen-Eigenschaft."""

    cls: str                                   # z. B. Q11303 (Wolkenkratzer)
    property: str                              # z. B. P2048 (Höhe)
    order: str = "desc"                        # desc = größte zuerst
    subclasses: bool = False                   # auch alle Unterklassen (langsam!)
    extra_classes: list[str] = field(default_factory=list)   # gezielt weitere Klassen, z. B. "Insel Japans"
    country: str | None = None                 # nur ein Land, z. B. Q183 (Deutschland)
    where: dict[str, str | list[str]] = field(default_factory=dict)  # weitere Filter, z. B. {"P30": "Q46"} (Europa)
                                                              # oder Pfad {"P17/P30": "Q18"} (Land liegt in Südamerika)
    require_props: list[str] = field(default_factory=list)    # Pflicht-Eigenschaften, z. B. P1619 (eröffnet)
    exclude_classes: list[str] = field(default_factory=list)  # z. B. unfertige Gebäude
    exclude_ended: bool = True                 # aufgelöst/abgerissen (P576) ausschließen
    exclude_props: list[str] = field(default_factory=list)    # Objekte mit dieser Eigenschaft ausschließen (z. B. P297 = Staat/Gebiet)
    min_sitelinks: int | None = None           # nur Objekte mit Artikeln in mind. N Wikipedia-Sprachen
    min_value: float | None = None
    max_value: float | None = None
    extras: dict[str, str] = field(default_factory=dict)      # Zusatzinfos: {"country": "P17", "year": "P1619"}
    max_age_years: float | None = None         # Warnung, wenn ein Wert älter ist


@dataclass
class VideoSpec:
    id: str
    title: dict[str, str]
    source: WikidataSource
    count: int = 10
    langs: list[str] = field(default_factory=lambda: ["de", "en"])
    value_label: dict[str, str] = field(default_factory=dict)  # "Höhe" / "Height"
    unit: str | None = None                    # Anzeige-Einheit erzwingen: m, km, km2, t, ...
    target_seconds: int = 170                  # Zielänge (YouTube Shorts: max. 180 s)
    hashtags: list[str] = field(default_factory=list)
    compare: dict | None = None                # Vergleichsobjekt je Sprache, z. B. {"de": {"qid": "Q4127", "name": "der Bodensee"}}
    image_prop: str = "P18"                    # Bild-Eigenschaft: P18 Foto, P41 Flagge

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "VideoSpec":
        data = dict(data)
        src = dict(data.pop("source"))
        src_type = src.pop("type", "wikidata")
        if src_type != "wikidata":
            raise ValueError(f"Unbekannte Datenquelle: {src_type}")
        if "class" in src:
            src["cls"] = src.pop("class")
        count = data.get("count", 10)
        data["title"] = {k: v.replace("{count}", str(count)) for k, v in data["title"].items()}
        spec = cls(source=WikidataSource(**src), **data)
        spec.validate()
        return spec

    @classmethod
    def from_file_data(cls, data: dict, count: int | None = None) -> "VideoSpec":
        """Wie from_dict, aber mit optional überschriebener Anzahl (Titel passt sich an)."""
        data = dict(data)
        if count:
            data["count"] = count
        return cls.from_dict(data)

    def validate(self) -> None:
        if not re.fullmatch(r"[a-z0-9][a-z0-9_-]{1,60}", self.id):
            raise ValueError(f"Ungültige id: {self.id!r} (erlaubt: a-z, 0-9, -, _)")
        for lang in self.langs:
            if lang not in config.SUPPORTED_LANGS:
                raise ValueError(f"Sprache {lang!r} wird nicht unterstützt")
            if lang not in self.title:
                raise ValueError(f"Titel für Sprache {lang!r} fehlt")
        if not 3 <= self.count <= 20:
            raise ValueError("count muss zwischen 3 und 20 liegen")
        where_ids = [q for v in self.source.where.values() for q in ([v] if isinstance(v, str) else v)]
        for qid in [self.source.cls, self.source.country, *self.source.exclude_classes, *self.source.extra_classes,
                    *where_ids]:
            if qid and not re.fullmatch(r"Q\d+", qid):
                raise ValueError(f"Ungültige Wikidata-ID: {qid!r}")
        for path in self.source.where:
            if not re.fullmatch(r"P\d+\*?(/P\d+\*?){0,2}", path):
                raise ValueError(f"Ungültiger Filter: {path!r}")
        for pid in [self.source.property, *self.source.require_props, *self.source.exclude_props,
                    *self.source.extras.values()]:
            if not re.fullmatch(r"P\d+", pid):
                raise ValueError(f"Ungültige Eigenschaft: {pid!r}")
        if self.image_prop not in ("P18", "P41", "P154", "P94"):
            raise ValueError(f"Ungültige Bild-Eigenschaft: {self.image_prop!r}")
        if self.source.order not in ("asc", "desc"):
            raise ValueError("order muss 'asc' oder 'desc' sein")


def load_spec(path: str | Path, count: int | None = None) -> VideoSpec:
    return VideoSpec.from_file_data(load_raw(path), count)


def load_raw(path: str | Path) -> dict:
    return yaml.safe_load(Path(path).read_text("utf-8"))


def _preset_paths() -> dict[str, Path]:
    return {load_raw(p)["id"]: p for p in sorted(config.PRESETS_DIR.glob("*.yaml"))}


def list_presets() -> list[VideoSpec]:
    return [load_spec(p) for p in _preset_paths().values()]


def preset_raw(preset_id: str) -> dict:
    paths = _preset_paths()
    if preset_id not in paths:
        raise KeyError(f"Vorlage {preset_id!r} nicht gefunden")
    return load_raw(paths[preset_id])


def find_preset(preset_id: str, count: int | None = None) -> VideoSpec:
    return VideoSpec.from_file_data(preset_raw(preset_id), count)
