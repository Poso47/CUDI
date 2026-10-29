"""Tests für cudi_video (ohne Netzwerk)."""

import pytest

from cudi_video.models import RankItem, Research
from cudi_video.render.video import _srt_time
from cudi_video.script import (
    _sentences, build_script, has_risky_claims, numbers_supported, usable_summary_sentences,
)
from cudi_video.sources.wikidata import build_ranking_query, check_consistency, pick_latest
from cudi_video.spec import VideoSpec, list_presets
from cudi_video.units import fmt_number, quantity


def make_spec(**kw):
    data = {
        "id": "test", "title": {"de": "Test DE", "en": "Test EN"}, "count": 3,
        "value_label": {"de": "Höhe", "en": "Height"}, "unit": "m",
        "source": {"type": "wikidata", "class": "Q11303", "property": "P2048", "extras": {"country": "P17"}},
    }
    data.update(kw)
    return VideoSpec.from_dict(data)


def make_research():
    items = []
    for rank, (name, value) in enumerate([("Turm A", 828.0), ("Turm B", 679.0), ("Turm C", 632.0)], start=1):
        items.append(RankItem(
            qid=f"Q{rank}", value=value, unit="Q11573", rank=rank,
            labels={"de": name, "en": name}, descriptions={"de": "Wolkenkratzer", "en": "skyscraper"},
            extras={"country": {"de": "Land X", "en": "Country X"}},
            summary={"de": f"{name} ist ein Gebäude. Es wurde 2010 eröffnet und ist 830 Meter hoch.",
                     "en": f"{name} is a building. It is the tallest in the world."},
        ))
    return Research(spec_id="test", fetched_at="2026-10-29T10:00:00+00:00", items=items)


# --------------------------------------------------------------------------- Einheiten

def test_number_format():
    assert fmt_number(1234567, "de") == "1.234.567"
    assert fmt_number(1234567, "en") == "1,234,567"
    assert fmt_number(8.5, "de", 1) == "8,5"


def test_quantity_area_and_population():
    area = quantity(17_075_400_000_000, "Q25343", "km2")
    assert area.display("de") == "17.075.400 km²"
    assert area.spoken("de") == "17,1 Millionen Quadratkilometer"
    assert area.spoken("en") == "17.1 million square kilometers"
    pop = quantity(1_404_890_000, "Q199")
    assert pop.display("de") == "1,40 Mrd."
    assert pop.spoken("en") == "1.4 billion"


def test_quantity_counting_display_keeps_format():
    q = quantity(828, "Q11573", "m")
    assert q.display("de", 414.4) == "414 m"


# --------------------------------------------------------------------------- Faktenschutz

def test_sentence_split_keeps_ordinals_and_abbreviations():
    s = _sentences("Er wurde am 28. August 2008 eröffnet. Leslie E. Robertson plante ihn (geb. 1928). Ende!")
    assert s == ["Er wurde am 28. August 2008 eröffnet.", "Leslie E. Robertson plante ihn.", "Ende!"]


@pytest.mark.parametrize("sentence", [
    "Er ist 830 Meter hoch.",
    "Es ist das elfthöchste Gebäude der Welt.",
    "It is the eighth-tallest building.",
    "As of 2026, it is the tallest in Taiwan.",
    "Derzeit ist es das höchste Gebäude.",
])
def test_risky_sentences_are_rejected(sentence):
    assert has_risky_claims(sentence)


def test_safe_sentence_is_kept():
    assert not has_risky_claims("Das Gebäude wurde 2010 eröffnet.")


def test_summary_filter_drops_conflicting_numbers():
    research = make_research()
    sentences = usable_summary_sentences(research.items[0], "de")
    assert sentences == ["Turm A ist ein Gebäude."]


def test_numbers_supported_guard():
    facts = {"rank": 3, "value_spoken": "632 Meter", "as_of": "2014"}
    assert numbers_supported("Platz 3: 632 Meter hoch, seit 2014.", facts)
    assert not numbers_supported("Platz 3: 640 Meter hoch.", facts)


def test_template_script_uses_only_data():
    spec, research = make_spec(), make_research()
    script = build_script(spec, research, "de", use_llm=False)
    kinds = [s.kind for s in script.segments]
    assert kinds == ["intro", "item", "item", "item", "outro"]
    assert [s.rank for s in script.segments[1:-1]] == [3, 2, 1]          # Countdown
    assert "828 Meter" in script.segments[0].text
    assert "830" not in " ".join(s.text for s in script.segments)        # Wikipedia-Zahl verworfen
    assert "29.10.2026" in script.segments[-1].text
    en = build_script(spec, research, "en", use_llm=False)
    assert "October 29, 2026" in en.segments[-1].text
    assert "tallest" not in " ".join(s.text for s in en.segments)


# --------------------------------------------------------------------------- Wikidata

def _binding(qid, value, date=None, preferred=False):
    b = {
        "item": {"value": f"http://www.wikidata.org/entity/{qid}"},
        "value": {"value": str(value)},
        "unit": {"value": "http://www.wikidata.org/entity/Q199"},
        "rank": {"value": "http://wikiba.se/ontology#" + ("PreferredRank" if preferred else "NormalRank")},
    }
    if date:
        b["date"] = {"value": date + "T00:00:00Z"}
    return b


def test_pick_latest_prefers_newest_date():
    items = pick_latest([
        _binding("Q668", 1_210_000_000, "2011-03-01"),
        _binding("Q668", 1_326_000_000, "2020-07-01"),
        _binding("Q148", 1_404_000_000, "2025-01-01"),
    ])
    assert items["Q668"].value == 1_326_000_000
    assert items["Q668"].value_date == "2020-07-01"


def test_pick_latest_prefers_preferred_rank_without_dates():
    items = pick_latest([_binding("Q1", 5), _binding("Q1", 7, preferred=True)])
    assert items["Q1"].value == 7


def test_consistency_warns_about_mixed_years():
    spec = make_spec()
    research = make_research()
    research.items[0].value_date = "2025-01-01"
    research.items[1].value_date = "2021-01-01"
    warnings = check_consistency(spec, research)
    assert any("unterschiedlichen Jahren" in w for w in warnings)


def test_query_contains_filters():
    spec = make_spec(source={"type": "wikidata", "class": "Q11303", "property": "P2048",
                             "require_props": ["P1619"], "exclude_classes": ["Q55965244"], "country": "Q183"})
    q = build_ranking_query(spec.source)
    assert "wdt:P31 wd:Q11303" in q
    assert "FILTER EXISTS { ?item wdt:P1619 [] }" in q
    assert "FILTER NOT EXISTS { ?item wdt:P31 wd:Q55965244 }" in q
    assert "?item wdt:P17 wd:Q183" in q
    assert "ORDER BY DESC(?value)" in q


# --------------------------------------------------------------------------- Vorgaben

def test_spec_validation_rejects_injection():
    with pytest.raises(ValueError):
        make_spec(source={"type": "wikidata", "class": "Q1 } DELETE {", "property": "P2048"})
    with pytest.raises(ValueError):
        make_spec(langs=["fr"])


def test_presets_are_valid():
    presets = list_presets()
    assert len(presets) >= 4
    assert len({p.id for p in presets}) == len(presets)


def test_srt_time():
    assert _srt_time(3723.5) == "01:02:03,500"


# --------------------------------------------------------------------------- Quellen-Abgleich

from cudi_video.verify import compact_sources, evaluate  # noqa: E402
from cudi_video.verify.checkers import Evidence  # noqa: E402
from cudi_video.verify.numbers import mentions_value  # noqa: E402


def _item(value):
    return RankItem(qid="Q1", value=value, unit="Q25343", labels={"de": "X", "en": "X"})


def _ev(source, value=None, agrees=None, date=None):
    return Evidence(source, "test", "https://example.org", value, date, agrees)


def test_evaluate_confirmed_by_independent_source():
    r = evaluate(_item(100.0), [_ev("Wikidata", 100.0), _ev("Weltbank", 100.5)], 0.01)
    assert r["status"] == "bestätigt"
    assert r["sources"] == ["Weltbank", "Wikidata"]


def test_evaluate_majority_ignores_single_outlier():
    r = evaluate(_item(9_984_670.0), [
        _ev("Wikidata", 9_984_670.0), _ev("Weltbank", 15_634_410.0), _ev("CIA World Factbook", 9_984_670.0),
        _ev("Wikipedia (zh)", agrees=True), _ev("Wikipedia (ja)", agrees=True),
    ], 0.01)
    assert r["status"] == "bestätigt"
    assert r["outliers"] == ["Weltbank"]
    assert r["value"] == 9_984_670.0


def test_evaluate_corrects_outdated_value_when_sources_agree():
    r = evaluate(_item(1_326_000_000.0), [
        _ev("Wikidata", 1_326_000_000.0, date="2020-07-01"),
        _ev("Weltbank", 1_438_000_000.0, date="2024-12-31"),
        _ev("CIA World Factbook", 1_410_000_000.0, date="2025-07-01"),
    ], 0.05)
    assert r["status"] == "korrigiert"
    assert r["value"] == pytest.approx(1_424_000_000.0)
    assert r["date"] == "2025-07-01"


def test_evaluate_contradiction_without_majority():
    r = evaluate(_item(100.0), [_ev("Wikidata", 100.0), _ev("Weltbank", 130.0)], 0.01)
    assert r["status"] == "widersprüchlich"


def test_evaluate_single_source():
    r = evaluate(_item(100.0), [_ev("Wikidata", 100.0), _ev("Wikipedia (fr)", agrees=None)], 0.01)
    assert r["status"] == "nur eine Quelle"


@pytest.mark.parametrize("text,expected,ok", [
    ("La superficie est de 17 098 246 km².", 17_098_246, True),
    ("environ 17,1 millions de km2", 17_075_400, True),
    ("面积1709.8万平方公里", 17_098_246, True),
    ("ارتفاعه ٨٢٨ مترًا", 828, True),
    ("Der Berg ist 8.849 m hoch", 8849, True),
    ("Es ist 830 Meter hoch", 828, False),
    ("etwa 17 Millionen km²", 17_075_400, False),     # zu grob gerundet
    ("eröffnet 2010", 828, False),
])
def test_mentions_value(text, expected, ok):
    assert mentions_value(text, expected) is ok


def test_compact_sources():
    assert compact_sources(["Weltbank", "Wikipedia (ru)", "Wikipedia (zh)"]) == "Weltbank, Wikipedia (ru, zh)"


@pytest.mark.parametrize("sentence", [
    "Bis heute werden ihr schwere Menschenrechtsverletzungen vorgeworfen.",
    "Er liegt in der umstrittenen Region Kaschmir.",
    "The country has been criticized for its policies.",
])
def test_non_neutral_sentences_are_rejected(sentence):
    assert has_risky_claims(sentence)


def test_evaluate_outdated_wikidata_is_replaced_even_if_close():
    r = evaluate(_item(275_440_000.0), [
        _ev("Wikidata", 275_440_000.0, date="2021-01-01"),
        _ev("Weltbank", 285_720_000.0, date="2024-12-31"),
        _ev("CIA World Factbook", 283_590_000.0, date="2025-07-01"),
    ], 0.05)
    assert r["status"] == "korrigiert"
    assert r["value"] == pytest.approx(284_655_000.0)
