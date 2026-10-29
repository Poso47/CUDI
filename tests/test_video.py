"""Tests für cudi_video (ohne Netzwerk)."""

import re

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
            summary={"de": f"{name} ist ein Gebäude. Oben gibt es eine Aussichtsplattform. "
                           "Es wurde 2010 eröffnet und ist 830 Meter hoch.",
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
    # Definitionssatz (doppelt zur Beschreibung) und Satz mit abweichender Zahl fallen weg
    assert sentences == ["Oben gibt es eine Aussichtsplattform."]


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


def test_query_where_paths_and_notability():
    spec = make_spec(source={"type": "wikidata", "class": "Q34038", "property": "P2048",
                             "where": {"P17/P30": "Q18"}, "exclude_props": ["P297"], "min_sitelinks": 10})
    q = build_ranking_query(spec.source)
    assert "?item wdt:P17/wdt:P30 wd:Q18 ." in q
    assert "FILTER NOT EXISTS { ?item wdt:P297 [] }" in q
    assert "FILTER(?sitelinks >= 10)" in q
    with pytest.raises(ValueError):
        make_spec(source={"type": "wikidata", "class": "Q34038", "property": "P2048", "where": {"P17 } x": "Q18"}})


def test_query_contains_filters():
    spec = make_spec(source={"type": "wikidata", "class": "Q11303", "property": "P2048",
                             "require_props": ["P1619"], "exclude_classes": ["Q55965244"], "country": "Q183"})
    q = build_ranking_query(spec.source)
    assert "VALUES ?cls { wd:Q11303 }" in q and "?item wdt:P31 ?cls ." in q
    assert "FILTER EXISTS { ?item wdt:P1619 [] }" in q
    assert "wd:Q55965244" in q and "wd:Q105821051" in q          # Urzeitseen + nie gebaute Bauwerke
    assert "wdt:P376" in q                                       # nur Objekte auf der Erde
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


def _ev(source, value=None, agrees=None, date=None, precision=0.0):
    return Evidence(source, "test", "https://example.org", value, date, agrees, precision=precision)


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


# --------------------------------------------------------------------------- Vergleiche + Skript-Varianten

from cudi_video.compare import comparison  # noqa: E402


def _ref(value, unit="Q11573", qid="Q4176", name="der Kölner Dom", **kw):
    return {"qid": qid, "name": name, "value": value, "unit": unit, "url": "u", **kw}


@pytest.mark.parametrize("value,expected", [
    (828.0, ("fragment", "5,3-mal so hoch wie der Kölner Dom", "5,3× Kölner Dom")),
    (200.0, ("fragment", "27 Prozent höher als der Kölner Dom", "+27 % vs. Kölner Dom")),
    (160.0, ("fragment", "etwa so hoch wie der Kölner Dom", "≈ Kölner Dom")),
    (100.0, ("sentence", "Zum Vergleich: Der Kölner Dom ist 1,6-mal so hoch.", None)),
    (20.0, ("sentence", "Zum Vergleich: Der Kölner Dom ist 7,8-mal so hoch.", None)),
])
def test_comparison_height_de(value, expected):
    item = RankItem(qid="Q1", value=value, unit="Q11573")
    result = comparison(item, _ref(157.0), "P2048", "de")
    assert (result and (result["kind"], result["text"], result["chip"])) == expected or (result is None and expected is None)


def test_comparison_population_and_rounding():
    item = RankItem(qid="Q668", value=1_440_000_000, unit="Q199")
    ref = _ref(83_467_117, unit="Q199", qid="Q183", name="Deutschland", **{"in": "in Deutschland"})
    assert comparison(item, ref, "P1082", "de")["text"] == "17,3-mal so viele wie in Deutschland"
    en_ref = _ref(69_119_155, unit="Q199", qid="Q145", name="the UK", **{"in": "in the UK"})
    assert comparison(item, en_ref, "P1082", "en")["text"] == "20.8 times as many people as in the UK"
    big = RankItem(qid="Q1", value=17_098_000e6, unit="Q25343")
    de_area = _ref(357_588e6, unit="Q25343", qid="Q183", name="Deutschland")
    result = comparison(big, de_area, "P2046", "de")
    assert result["text"] == "rund 48-mal so groß wie Deutschland"
    assert result["chip"] == "48× Deutschland"


def test_comparison_skips_self_and_unit_mismatch():
    ref = _ref(157.0)
    assert comparison(RankItem(qid="Q4176", value=157.0, unit="Q11573"), ref, "P2048", "de") is None
    assert comparison(RankItem(qid="Q1", value=828.0, unit="Q25343"), ref, "P2048", "de") is None


def test_script_has_countdown_dramaturgy():
    spec, research = make_spec(count=3), make_research()
    research.references = {"de": _ref(157.0)}
    texts = [s.text for s in build_script(spec, research, "de", use_llm=False).segments]
    assert texts[1].startswith("Wir starten mit Platz 3: Turm C.")
    assert "– 4-mal so hoch wie der Kölner Dom." in texts[1]
    assert texts[3].startswith("Und auf Platz 1: Turm A!")
    assert "– 5,3-mal so hoch wie der Kölner Dom." in texts[3]
    assert "Stand" not in " ".join(texts)              # Höhe ändert sich nicht -> kein Stichtag


def test_close_values_get_distinct_spoken_precision():
    spec = make_spec(unit=None, value_label={"de": "Einwohner", "en": "Population"},
                     source={"type": "wikidata", "class": "Q3624078", "property": "P1082"})
    research = make_research()
    research.items[0].value, research.items[0].unit = 1_440_000_000, "Q199"
    research.items[1].value, research.items[1].unit = 1_404_000_000, "Q199"
    research.items[2].value, research.items[2].unit = 340_000_000, "Q199"
    text = " ".join(s.text for s in build_script(spec, research, "de", use_llm=False).segments[1:-1])
    assert "1,44 Milliarden" in text and "1,40 Milliarden" in text
    assert "340 Millionen" in text                     # eindeutige Werte bleiben gerundet


from cudi_video.verify.numbers import closest_unit_value  # noqa: E402


@pytest.mark.parametrize("text,expected,unit,found", [
    ("Great Britain … with an area of 209,331 km2 (80,823 sq mi).", 228_938, "km²", 209_331),
    ("La Grande-Bretagne a une superficie de 209 331 km².", 228_938, "km²", 209_331),
    ("本州面积为22.79万平方公里。", 227_940, "km²", 227_900),
    ("Высота 828 метров.", 828, "m", 828),
    ("Die Insel hat 1500 Einwohner und ist 230 000 km² groß.", 228_938, "km²", 230_000),
    ("Sie liegt 40 km vor der Küste.", 228_938, "km²", None),        # falsche Einheit
    ("Der Turm ist 2000 m vom Fluss entfernt.", 828, "m", None),     # außerhalb ±30 %
])
def test_closest_unit_value(text, expected, unit, found):
    result = closest_unit_value(text, expected, unit)
    assert (result[0] if result else None) == found


def test_wikipedia_values_can_correct_wikidata():
    r = evaluate(_item(228_938e6), [
        _ev("Wikidata", 228_938e6),
        _ev("Wikipedia (en)", 209_331e6), _ev("Wikipedia (fr)", 209_331e6), _ev("Wikipedia (es)", 209_300e6),
    ], 0.01)
    assert r["status"] == "korrigiert"
    assert r["value"] == pytest.approx(209_331e6)


# --------------------------------------------------------------------------- Stichwort-Planer

from cudi_video import topics  # noqa: E402

FAKE_COUNTRIES = {
    "deutschland": {"qid": "Q183", "de": "Deutschland", "en": "Germany"},
    "united states": {"qid": "Q30", "de": "Vereinigte Staaten", "en": "United States"},
    "schweiz": {"qid": "Q39", "de": "Schweiz", "en": "Switzerland"},
}


@pytest.fixture
def fake_lookup(monkeypatch):
    monkeypatch.setattr(topics, "_lookup_country", lambda name: FAKE_COUNTRIES.get(name.lower()))


@pytest.mark.parametrize("text,title_de,title_en,prop,where", [
    ("die höchsten Wasserfälle Südamerikas", "Die 10 höchsten Wasserfälle Südamerikas",
     "The 10 Tallest Waterfalls in South America", "P2048", {"P17/P30": "Q18"}),
    ("Top 5 der größten Seen Deutschlands", "Die 5 größten Seen Deutschlands",
     "The 5 Largest Lakes in Germany", "P2046", {"P17": "Q183"}),
    ("tallest buildings in the united states", "Die 10 höchsten Gebäude der USA",
     "The 10 Tallest Buildings in the United States", "P2048", {"P17": "Q30"}),
    ("die größten Seen in der Schweiz", "Die 10 größten Seen in der Schweiz",
     "The 10 Largest Lakes in Switzerland", "P2046", {"P17": "Q39"}),
    ("die bevölkerungsreichsten Länder Ozeaniens", "Die 10 bevölkerungsreichsten Länder Ozeaniens",
     "The 10 Most Populous Countries in Oceania", "P1082", {"P30": ["Q55643", "Q538"]}),
    ("die höchsten Berge der Alpen", "Die 10 höchsten Berge der Alpen",
     "The 10 Highest Mountains in the Alps", "P2044", {"P4552/P361*": "Q1286"}),
])
def test_planner_understands_topics(fake_lookup, text, title_de, title_en, prop, where):
    spec = VideoSpec.from_dict(topics.plan_from_text(text))
    assert spec.title == {"de": title_de, "en": title_en}
    assert spec.source.property == prop
    assert spec.source.where == where


def test_planner_world_scope_and_order(fake_lookup):
    deep = VideoSpec.from_dict(topics.plan_from_text("die tiefsten Seen der Welt"))
    assert deep.source.property == "P4511" and deep.source.min_value == 400
    small = VideoSpec.from_dict(topics.plan_from_text("die kleinsten Länder der Welt"))
    assert small.source.order == "asc" and small.source.min_value is None
    assert small.image_prop == "P41"                       # Länder -> Flaggen


@pytest.mark.parametrize("text", ["die schnellsten Tiere", "größte Länder von Atlantis", "höchste Gebäude von Narnia"])
def test_planner_rejects_unknown(fake_lookup, text):
    with pytest.raises(topics.PlanError):
        topics.plan_from_text(text)


def test_pick_latest_prefers_architectural_height():
    def b(value, criterion=None):
        row = _binding("Q151765", value)
        if criterion:
            row["criterion"] = {"value": f"http://www.wikidata.org/entity/{criterion}"}
        return row
    items = pick_latest([b(300.1, "Q26970842"), b(259.0, "Q24192182")])   # Spitze vs. architektonisch
    assert items["Q151765"].value == 259.0
    tie = pick_latest([b(300.0), b(259.0)])                               # ohne Kennzeichnung
    assert tie["Q151765"].value == 300.0 and tie["Q151765"].alternatives == [259.0]


def test_query_is_lean_and_supports_require_any():
    spec = make_spec(source={"type": "wikidata", "class": "Q8502", "property": "P2044", "where": {"P17": "Q183"},
                             "require_any": ["P1619", "P571"]})
    q = build_ranking_query(spec.source)
    assert "?item wdt:P17 wd:Q183 ." in q
    assert "hint:Query" not in q                          # Wikidatas Optimierer ist schneller (gemessen)
    assert "UNION { FILTER NOT EXISTS" not in q           # Höhe hat Einheit -> nur normalisierter Wert
    assert "FILTER EXISTS { { ?item wdt:P1619 [] } UNION { ?item wdt:P571 [] } }" in q
    population = make_spec(source={"type": "wikidata", "class": "Q3624078", "property": "P1082"})
    assert "psv:P1082" in build_ranking_query(population.source)


# --------------------------------------------------------------------------- Sprachmodell-Pfad (simuliert)

from cudi_video import llm as llm_module  # noqa: E402
from cudi_video import script as script_module  # noqa: E402


def _fake_llm(monkeypatch, continuation, verdict=True):
    """Simuliertes Modell: übernimmt den vorgegebenen Satzanfang und hängt `continuation` an."""
    def chat(system, user, temperature=0.4, timeout=120):
        start = re.search(r'Beginne exakt mit: "(.*?)" Gib nur', user).group(1)
        return f"{start} {continuation}"

    monkeypatch.setattr(llm_module, "chat", chat)
    monkeypatch.setattr(llm_module, "chat_json", lambda *a, **k: {"supported": verdict, "unsupported": []})


def test_llm_text_is_used_when_checks_pass(monkeypatch):
    spec, research = make_spec(), make_research()
    _fake_llm(monkeypatch, "Ein beeindruckender Wolkenkratzer.")
    script = build_script(spec, research, "de", use_llm=True)
    assert script.mode == "llm"
    assert script.segments[1].text == "Wir starten mit Platz 3: Turm C. Ein beeindruckender Wolkenkratzer."
    assert all("übernommen" in c for c in script.checks)


def test_llm_text_with_invented_number_is_rejected(monkeypatch):
    spec, research = make_spec(), make_research()
    _fake_llm(monkeypatch, "Er hat 999 Fenster.")      # 999 steht nirgends in den Fakten
    script = build_script(spec, research, "de", use_llm=True)
    assert "999" not in " ".join(s.text for s in script.segments)
    assert all("Zahl ohne Beleg" in c for c in script.checks)


def test_llm_text_rejected_by_fact_checker(monkeypatch):
    spec, research = make_spec(), make_research()
    _fake_llm(monkeypatch, "Er wurde von Aliens gebaut.", verdict=False)
    script = build_script(spec, research, "de", use_llm=True)
    assert "Aliens" not in " ".join(s.text for s in script.segments)
    assert all("nicht belegt" in c for c in script.checks)


def test_fallback_uses_search_index_when_query_times_out(monkeypatch):
    from cudi_video import net
    from cudi_video.sources import wikidata as wd

    spec = make_spec(source={"type": "wikidata", "class": "Q8502", "property": "P2044", "where": {"P17": "Q183"}})
    calls = {"search": [], "sparql": []}

    def fake_sparql(query, cache_hours=6.0, retry_on=None):
        calls["sparql"].append(query)
        if "ORDER BY" in query:
            raise net.FetchError("https://query.wikidata.org/sparql: HTTP 504")
        return [_binding("Q3375", 2962.06), _binding("Q4168", 2713.0)]

    def fake_get_json(url, params=None, **kw):
        calls["search"].append(params["srsearch"])
        return {"query": {"search": [{"title": "Q3375"}, {"title": "Q4168"}]}}

    monkeypatch.setattr(wd, "_sparql", fake_sparql)
    monkeypatch.setattr(wd.net, "get_json", fake_get_json)
    rows = wd._ranking_bindings(spec.source, fresh=False)
    assert calls["search"] == ["haswbstatement:P31=Q8502 haswbstatement:P2044 haswbstatement:P17=Q183"]
    assert "VALUES ?item { wd:Q3375 wd:Q4168 }" in calls["sparql"][-1]
    assert {wd._qid(r["item"]["value"]) for r in rows} == {"Q3375", "Q4168"}


def test_fallback_resolves_continent_to_countries(monkeypatch):
    from cudi_video.sources import wikidata as wd

    spec = make_spec(source={"type": "wikidata", "class": "Q23397", "property": "P2046", "where": {"P17/P30": "Q46"}})
    searches = []
    monkeypatch.setattr(wd, "_countries_in", lambda continents: ["Q183", "Q40"])
    monkeypatch.setattr(wd.net, "get_json", lambda url, params=None, **kw: searches.append(params) or {"query": {"search": []}})
    wd._search_candidates(spec.source)
    assert searches[0]["srsearch"].endswith("haswbstatement:P17=Q183|P17=Q40")
    assert searches[0]["srsort"] == "incoming_links_desc"


def test_fallback_explains_unsupported_paths():
    from cudi_video.sources import wikidata as wd

    spec = make_spec(source={"type": "wikidata", "class": "Q8502", "property": "P2044", "where": {"P4552/P361*": "Q1286"}})
    with pytest.raises(wd.QueryTooHeavy):
        wd._search_candidates(spec.source)


def test_comparison_half_and_short_name():
    ref = _ref(3.75e6, unit="Q25343", qid="Q260223", name="der Englische Garten in München", short="Englischer Garten")
    monaco = comparison(RankItem(qid="Q235", value=2.08e6, unit="Q25343"), ref, "P2046", "de")
    assert monaco["text"] == "etwa halb so groß wie der Englische Garten in München"
    malta = comparison(RankItem(qid="Q233", value=316e6, unit="Q25343"), ref, "P2046", "de")
    assert malta["chip"] == "84× Englischer Garten"


def test_buildings_world_requires_build_date_but_country_scope_does_not(fake_lookup):
    world = VideoSpec.from_dict(topics.plan_from_text("die höchsten Gebäude der Welt"))
    assert world.source.require_any == ["P1619", "P571"]
    germany = VideoSpec.from_dict(topics.plan_from_text("die höchsten Gebäude Deutschlands"))
    assert germany.source.require_any == []
    assert "Q41176" in germany.source.extra_classes              # auch allgemeine Gebäude (Omniturm)
    q = build_ranking_query(germany.source)
    assert "wdt:P5817 ?state" in q                                # Nutzungszustand "im Bau" usw. ausgeschlossen


def test_extras_skip_values_repeating_the_name():
    from cudi_video.script import extras_lines

    spec = make_spec(source={"type": "wikidata", "class": "Q3624078", "property": "P2046",
                             "extras": {"capital": "P36"}})
    item = RankItem(qid="Q235", value=2.08e6, unit="Q25343", labels={"de": "Monaco"},
                    extras={"capital": {"de": "Monaco"}})
    assert extras_lines(spec, item, "de") == []


def test_rate_limit_block_is_shared_per_wikimedia_domain():
    from cudi_video.net import _block_key

    assert _block_key("fr.wikipedia.org") == _block_key("ja.wikipedia.org") == "wikipedia.org"
    assert _block_key("upload.wikimedia.org") == _block_key("commons.wikimedia.org") == "wikimedia.org"
    assert _block_key("query.wikidata.org") == "query.wikidata.org"      # Pflichtquelle getrennt behandeln


# --------------------------------------------------------------------------- Rendering (Rauchtest)

def _job(kind, **extra):
    base = {"index": 0, "kind": kind, "lang": "de", "title": "Die 3 höchsten Türme", "text": "Platz 1: Turm A.",
            "words": [{"text": "Platz", "start": 0.0, "end": 0.3}, {"text": "1:", "start": 0.3, "end": 0.5}],
            "lead": 0.4, "frames": 30, "duration": 1.0, "fps": 30, "n_items": 3, "max_display": 828.0,
            "channel": "@test", "out": "unused.mp4"}
    base.update(extra)
    return base


@pytest.mark.parametrize("image", ["photo", "flag", None])
def test_scenes_render_without_errors(tmp_path, image):
    from PIL import Image

    from cudi_video.render.scenes import make_scene
    from cudi_video.render.theme import H, W

    path = None
    if image:
        path = tmp_path / "img.png"
        Image.new("RGB", (640, 400), (200, 30, 30)).save(path)
    item = {"rank": 1, "name": "Turm A", "si_value": 828.0, "unit": "Q11573", "wanted": "m", "value_label": "Höhe",
            "as_of": None, "extras": [("Land", "Testland")], "image_path": str(path) if path else None,
            "image_kind": image or "photo", "credit_short": "Jemand (CC BY-SA 4.0)" if image else None,
            "icon": "building", "n_sources": 3, "compare_chip": "5,3× Kölner Dom"}
    jobs = [
        _job("intro", intro={"si_value": 828.0, "unit": "Q11573", "wanted": "m"}),
        _job("item", item=item),
        _job("outro", outro={"rows": [(1, "Turm A", "828 m"), (2, "Turm B", "679 m")], "sources_line": "Quellen: Test"}),
    ]
    for job in jobs:
        frame = make_scene(job).frame(0.8)
        assert frame.size == (W, H)


def test_evaluate_respects_rounding_of_sources():
    # Monaco: CIA "2 sq km" (gerundet) passt zu 2,08 km²; Weltbank 74,9 km² ist ein Ausreißer
    r = evaluate(_item(2.08e6), [
        _ev("Wikidata", 2.08e6), _ev("Weltbank", 74.9e6, precision=0.1e6), _ev("CIA World Factbook", 2e6, precision=1e6),
        _ev("Wikipedia (en)", 2.08e6, precision=0.01e6), _ev("Wikipedia (ar)", 2.08e6, precision=0.01e6),
    ], 0.01)
    assert r["status"] == "bestätigt"
    assert r["outliers"] == ["Weltbank"]


def test_evaluate_largest_group_wins_despite_scattered_outlier():
    # Tuvalu: Weltbank, CIA, ru sagen 26 km², Wikidata 25,1, ar 21 -> 26 gewinnt
    r = evaluate(_item(25.1e6), [
        _ev("Wikidata", 25.1e6), _ev("Weltbank", 26e6), _ev("CIA World Factbook", 26e6),
        _ev("Wikipedia (ru)", 26e6), _ev("Wikipedia (ar)", 21e6),
    ], 0.01)
    assert r["status"] == "korrigiert"
    assert r["value"] == 26e6
    assert r["outliers"] == ["Wikipedia (ar)"]


def test_display_name_strips_disambiguation():
    from cudi_video.sources.wikidata import display_name

    assert display_name("Victoria Island (Canada)") == "Victoria Island"
    assert display_name("Nauru") == "Nauru"
    assert display_name(None) is None
    assert display_name("Volksrepublik China", "de") == "China"
    assert display_name("Vereinigte Staaten", "de") == "USA"
    assert display_name("United States", "en") == "United States"


def test_verify_truncates_after_corrections(monkeypatch):
    import cudi_video.verify as verify_module

    spec = make_spec(count=3, source={"type": "wikidata", "class": "Q3624078", "property": "P2046", "order": "asc"})
    values = {"Q1": 0.44e6, "Q2": 2.08e6, "Q3": 21e6, "Q4": 25e6}
    research = Research(spec_id="t", fetched_at="2026-10-29T10:00:00+00:00", items=[
        RankItem(qid=q, value=v, unit="Q25343", labels={"de": q}) for q, v in values.items()])
    research.items.insert(2, RankItem(qid="Q225", value=10e6, unit="Q25343", labels={"de": "Bosnien"},
                                      alternatives=[51_209e6]))

    def fake_verify_item(spec, item, checkers):
        result = {"status": "bestätigt", "sources": ["Wikidata", "Weltbank"], "outliers": [], "evidence": []}
        if item.qid == "Q225":                       # Abgleich findet den richtigen Wert
            item.value = 51_209e6
            result["alternatives"] = [10e6]
        item.verification = result
        return result

    monkeypatch.setattr(verify_module, "verify_item", fake_verify_item)
    verify_module.verify(spec, research)
    assert [it.qid for it in research.items] == ["Q1", "Q2", "Q3"]
    assert [it.rank for it in research.items] == [1, 2, 3]
    assert any("Bosnien" in w and "nicht mehr in den Top 3" in w for w in research.warnings)


def test_voice_within_limit_drops_optional_text(monkeypatch, tmp_path):
    from cudi_video import pipeline, tts

    spec = make_spec(target_seconds=80)                        # Grenze: 80 + 8 s
    research = make_research()
    calls = []

    def fake_voice(script, out_dir, voice=None, rate=None):
        calls.append(rate)
        for seg in script.segments:
            seg.duration = len(seg.text.split()) * 1.0         # langsame Stimme
            seg.words = []
        return script

    monkeypatch.setattr(tts, "voice_script", fake_voice)
    full = build_script(spec, research, "de", use_llm=False)
    result = pipeline.voice_within_limit(spec, research, full, tmp_path, use_llm=False)
    count = lambda sc: " ".join(s.text for s in sc.segments).count("Aussichtsplattform")
    assert pipeline.video_seconds(result) <= 88
    assert count(result) < count(full)                       # optionale Wikipedia-Sätze zuerst gekürzt
    assert "Platz 1: Turm A" in result.segments[-2].text    # Pflichtinhalte bleiben
    assert len(calls) == 2                                   # gemessen, dann gezielt einmal gekürzt


def test_spoken_sources_are_compact():
    from cudi_video.script import spoken_sources

    names = spoken_sources(["CIA World Factbook", "Weltbank", "Wikipedia (en)", "Wikipedia (fr)", "Wikipedia (zh)"], "de")
    assert names == ["CIA World Factbook", "Weltbank", "Wikipedia"]
    assert spoken_sources(["Wikipedia (de)", "Wikipedia (ja)"], "en") == ["Wikipedia"]


def test_enrich_retries_throttled_images(monkeypatch):
    from cudi_video import enrich as enrich_mod
    from cudi_video import net

    calls = []

    def fake_image(item):
        calls.append(item.qid)
        if len(calls) == 1:
            return False                     # erster Versuch: gedrosselt
        item.image_path = "/tmp/bild.png"
        return True

    monkeypatch.setattr(enrich_mod, "fetch_image", fake_image)
    monkeypatch.setattr(enrich_mod, "RETRY_PAUSE", 0)
    item = RankItem(qid="Q1", value=1, unit="1", labels={"de": "Eins"}, image_file="Eins.jpg")
    research = Research(spec_id="t", fetched_at="", items=[item])
    enrich_mod.enrich(research, ["de"])
    assert calls == ["Q1", "Q1"] and item.image_path
    assert not any("Ohne Bild" in w for w in research.warnings)
    assert net._blocked_hosts == {}


def test_extras_drop_redundant_umbrella_values(monkeypatch):
    from cudi_video.sources import wikidata

    def row(item, key, qid, en):
        return {"item": {"value": f"http://www.wikidata.org/entity/{item}"}, "key": {"value": key},
                "v": {"value": f"http://www.wikidata.org/entity/{qid}"}, "vt_en": {"value": en}}

    rows = [row("Q672", "continent", "Q538", "Insular Oceania"), row("Q672", "continent", "Q55643", "Oceania"),
            row("Q1", "country", "Q1049", "Sudan"), row("Q1", "country", "Q958", "South Sudan"),
            row("Q2", "country", "Q148", "China (country)")]
    monkeypatch.setattr(wikidata, "_sparql", lambda query, **kw: rows)
    out = wikidata._extras(["Q672", "Q1", "Q2"], {"continent": "P30", "country": "P17"}, ["en"])
    assert out["Q672"]["continent"]["en"] == "Oceania"
    assert out["Q1"]["country"]["en"] == "Sudan / South Sudan"
    assert out["Q2"]["country"]["en"] == "China"


def test_tiktok_caption_is_short_and_names_sources():
    from cudi_video.metadata import build_metadata
    from cudi_video.models import Script

    spec, research = make_spec(hashtags=["architektur"]), make_research()
    research.items[0].verification = {"status": "bestätigt",
                                      "sources": ["Wikidata", "Weltbank", "Wikipedia (fr)", "Wikipedia (ja)"]}
    meta = build_metadata(spec, research, Script(lang="de", title="Test DE", segments=[]))
    caption = meta["caption"]
    assert caption.startswith("Test DE 🏆")
    assert "✓ Geprüft mit Wikidata, Weltbank und Wikipedia (2 Sprachen) · Stand 29.10.2026" in caption
    assert "#shorts" not in caption and "#architektur" in caption
    assert len(caption) < 600 and "http" not in caption


def test_hashtags_per_language():
    spec = make_spec(hashtags={"de": ["länder", "Geografie"], "en": ["countries"]})
    assert spec.tags_for("de") == ["länder", "geografie"] and spec.tags_for("en") == ["countries"]
    assert make_spec(hashtags=["natur"]).tags_for("en") == ["natur"]          # Liste gilt für alle Sprachen
    planned = VideoSpec.from_dict(topics.plan_from_text("die kleinsten Länder der Welt"))
    assert "länder" not in planned.tags_for("en") and "countries" in planned.tags_for("en")


def test_wikipedia_checker_falls_back_to_infobox(monkeypatch):
    from cudi_video.verify import checkers

    lead_calls = []
    monkeypatch.setattr(checkers, "fetch_summary", lambda lang, title: "Lake Huron is one of the Great Lakes.")

    def fake_lead(lang, title):
        lead_calls.append(title)
        return "Surface area 23,000 sq mi (59,570 km 2 ) Basin area 51,700 sq mi (134,000 km 2 )"

    monkeypatch.setattr(checkers, "fetch_lead_text", fake_lead)
    spec = make_spec(source={"type": "wikidata", "class": "Q23397", "property": "P2046"}, unit="km2")
    item = RankItem(qid="Q1383", value=59_600e6, unit="Q25343", labels={"en": "Lake Huron"},
                    wiki_titles={"en": "Lake Huron"})
    [ev] = checkers.WikipediaLangChecker("en").check(spec, item)
    assert lead_calls == ["Lake Huron"]
    assert ev.value == pytest.approx(59_570e6) and ev.note.startswith("Infobox")

    item.summary["en"] = "Lake Huron has a surface area of 59,600 km2."   # steht in der Einleitung -> keine Zusatzanfrage
    [ev] = checkers.WikipediaLangChecker("en").check(spec, item)
    assert lead_calls == ["Lake Huron"] and ev.note.startswith("Einleitung")


def test_infobox_ignores_other_quantities_with_same_unit(monkeypatch):
    from cudi_video.verify import checkers

    monkeypatch.setattr(checkers, "fetch_summary", lambda lang, title: "A waterfall in Venezuela.")
    monkeypatch.setattr(checkers, "fetch_lead_text", lambda lang, title: "Elevation 1,150 m Watercourse Kerepakupai Merú")
    spec = make_spec(source={"type": "wikidata", "class": "Q34038", "property": "P2048"})
    item = RankItem(qid="Q1", value=979.0, unit="Q11573", wiki_titles={"en": "Angel Falls"})
    [ev] = checkers.WikipediaLangChecker("en").check(spec, item)
    assert ev.value is None and ev.agrees is None        # 1.150 m Meereshöhe ist keine Fallhöhe
