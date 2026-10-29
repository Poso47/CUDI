"""Datenmodelle, die zwischen den Pipeline-Stufen als JSON gespeichert werden."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field


@dataclass
class RankItem:
    qid: str
    value: float
    unit: str                       # Wikidata-Einheit, z. B. Q11573 (Meter), Q199 (ohne Einheit)
    value_date: str | None = None   # Stichtag des Werts (pq:P585), falls angegeben
    rank: int = 0
    labels: dict[str, str] = field(default_factory=dict)
    descriptions: dict[str, str] = field(default_factory=dict)
    wiki_titles: dict[str, str] = field(default_factory=dict)
    image_file: str | None = None   # Dateiname auf Wikimedia Commons
    extras: dict[str, dict[str, str]] = field(default_factory=dict)  # {"country": {"de": "...", "en": "..."}}
    summary: dict[str, str] = field(default_factory=dict)            # Wikipedia-Einleitung je Sprache
    image_path: str | None = None
    image_credit: str | None = None
    codes: dict[str, str] = field(default_factory=dict)          # {"iso3": "RUS", "fips": "RS"}
    verification: dict = field(default_factory=dict)            # Ergebnis des Quellen-Abgleichs

    @property
    def wikidata_url(self) -> str:
        return f"https://www.wikidata.org/wiki/{self.qid}"

    def wiki_url(self, lang: str) -> str | None:
        title = self.wiki_titles.get(lang)
        return f"https://{lang}.wikipedia.org/wiki/{title.replace(' ', '_')}" if title else None


@dataclass
class Research:
    spec_id: str
    fetched_at: str
    items: list[RankItem]
    query: str = ""
    warnings: list[str] = field(default_factory=list)
    references: dict = field(default_factory=dict)   # Vergleichsobjekt je Sprache

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Research":
        data = dict(data)
        data["items"] = [RankItem(**it) for it in data["items"]]
        return cls(**data)


@dataclass
class Segment:
    """Ein Abschnitt des Videos (Intro, ein Platz, Outro) mit gesprochenem Text."""

    kind: str                       # intro | item | outro
    text: str                       # gesprochener Text
    rank: int | None = None
    sources: list[str] = field(default_factory=list)
    audio_path: str | None = None
    duration: float = 0.0
    words: list[dict] = field(default_factory=list)   # [{"text":..., "start":s, "end":s}]


@dataclass
class Script:
    lang: str
    title: str
    segments: list[Segment]
    mode: str = "template"          # template | llm
    checks: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Script":
        data = dict(data)
        data["segments"] = [Segment(**s) for s in data["segments"]]
        return cls(**data)
