"""Bildpassung (Bild zeigt den Fakt) und Aha-Effekt (Heute gelernt) – ohne Netz."""

from cudi_video import facts, media, metadata, retention, themen
from cudi_video.models import RankItem
from cudi_video.script import build_fact_script
from cudi_video.story import visuals
from cudi_video.story.visuals import Visual
from tests.test_handoff import DE_TEXT, EN_TEXT, _fact
from tests.test_video import make_spec


def test_motif_matches_singular_plural_and_all_words():
    assert media.motif_matches("shark teeth", "close up of a shark tooth on sand")
    assert media.motif_matches("shark tooth", "Sharks teeth collection")
    assert media.motif_matches("shark skin denticles", "shark skin denticle microscope")
    assert not media.motif_matches("shark teeth", "a shark swimming in the ocean")
    assert not media.motif_matches("shark skin denticles", "shark skin")
    assert not media.motif_matches("", "anything") and media.stem("berries") == "berry"


class Catalog:
    """Fake-Suchfunktionen: Beschreibung -> Treffer; wie die echten nehmen sie nur Treffer, die `match` bestehen."""

    def __init__(self, monkeypatch, clips=(), photos=(), commons=()):
        monkeypatch.setattr(media, "too_dark", lambda path: False)

        def lookup(name, entries, kind):
            def search(query, used, match=None):
                for desc in entries:
                    if (name, desc) in used or (match and not match(desc)):
                        continue
                    used.add((name, desc))
                    return Visual(kind, f"/{name}/{desc}", f"{name}: {desc}", query)
                return None
            return search

        monkeypatch.setattr(visuals, "pexels", lookup("pexels", clips, "video"))
        monkeypatch.setattr(visuals, "pixabay", lambda *a, **k: None)
        monkeypatch.setattr(visuals, "pexels_photo", lookup("pexels_photo", photos, "image"))
        monkeypatch.setattr(visuals, "pixabay_photo", lambda *a, **k: None)
        monkeypatch.setattr(visuals, "commons_photo", lookup("commons", commons, "image"))


def tooth_fact(**extra):
    return {"motiv": "shark teeth", "suche": ["shark teeth close up", "shark jaw"], **extra}


def test_tooth_fact_gets_tooth_photo_not_general_shark_clip(monkeypatch):
    Catalog(monkeypatch, clips=["a shark swimming in blue water"], photos=["close up of shark teeth in a jaw"])
    found = facts.find_visuals(tooth_fact(), "shark", set())
    assert not found["clips"] and found["passt"] is True and found["quelle"] == "Foto"
    assert "teeth" in found["photo"].credit


def test_matching_clip_comes_first_and_order_falls_back(monkeypatch):
    Catalog(monkeypatch, clips=["a shark swimming", "shark teeth underwater"], photos=["shark tooth"],
            commons=["Shark teeth.jpg"])
    found = facts.find_visuals(tooth_fact(), "shark", set())
    assert found["quelle"] == "Clip" and found["clips"][0]["credit"].endswith("shark teeth underwater")
    # kein Clip, kein Stockfoto -> Commons-Bild zum Motiv
    Catalog(monkeypatch, clips=["a shark swimming"], photos=["a beach"],
            commons=["Great white shark.jpg", "Shark teeth.jpg"])
    found = facts.find_visuals(tooth_fact(), "shark", set())
    assert found["quelle"] == "Wikimedia Commons" and found["photo"].credit.endswith("Shark teeth.jpg")


def test_general_clip_only_as_marked_mood_picture(monkeypatch):
    Catalog(monkeypatch, clips=["a shark swimming in blue water"])
    found = facts.find_visuals(tooth_fact(), "shark", set())
    assert found["passt"] is False and found["quelle"] == "Stimmungsbild" and found["clips"]
    Catalog(monkeypatch)
    assert facts.find_visuals(tooth_fact(), "shark", set())["quelle"] == "kein Bild"


def test_old_answers_with_single_string_keep_working(monkeypatch):
    Catalog(monkeypatch, clips=["a shark swimming"])
    old = {"suche": "shark swimming"}
    assert facts.searches(old) == ["shark swimming"] and facts.searches({"suche": ["a", "b"]}) == ["a", "b"]
    found = facts.find_visuals(old, "", set())
    assert found["clips"] and found["passt"] is None and found["quelle"] == "ungeprüft"


def test_visuals_writes_choice_into_item_and_review(monkeypatch):
    Catalog(monkeypatch, photos=["shark teeth"])
    item = RankItem(qid="F1", value=1, unit="Q199", rank=1, labels={"en": "Shark", "de": "Hai"}, fact=tooth_fact())
    facts._visuals(type("R", (), {"items": [item]})())
    assert item.image_path and item.fact["bild"] == {"motiv": "shark teeth", "passt": True, "quelle": "Foto"}
    assert "Motiv: shark teeth · Bild passt (Foto)" in metadata.bild_zeile(item)[0]
    item.fact["bild"] = {"motiv": "shark teeth", "passt": False, "quelle": "Stimmungsbild"}
    assert "Bild zeigt nicht genau den Fakt" in metadata.bild_zeile(item)[0]


SOURCES = [{"id": "de:Unbewusstes", "sprache": "de", "titel": "Unbewusstes", "text": DE_TEXT, "url": "u1"},
           {"id": "en:Unconscious mind", "sprache": "en", "titel": "Unconscious mind", "text": EN_TEXT, "url": "u2"}]
BELEG = ("Nach Schätzungen verarbeitet das Gehirn pro Sekunde etwa 11 Millionen Sinneseindrücke, von denen nur ein "
         "winziger Teil bewusst wird.")
TEXT = ("Stell dir vor: Pro Sekunde erreichen dein Gehirn etwa 11 Millionen Sinneseindrücke. Bewusst wird dir davon "
        "nur ein winziger Teil.")


def test_aha_sentence_must_pass_the_same_checks_but_never_rejects_the_fact():
    good = dict(_fact(1, BELEG, TEXT), aha_de="Nur ein winziger Teil der 11 Millionen Eindrücke wird dir bewusst.")
    assert facts.check_fact(good, SOURCES, ["de"], 10) == (None, "bestätigt")
    assert good["_aha"]["de"].startswith("Nur ein winziger Teil")
    new_number = dict(_fact(1, BELEG, TEXT), aha_de="Es sind sogar 40 Millionen Eindrücke pro Sekunde.")
    assert facts.check_fact(new_number, SOURCES, ["de"], 10) == (None, "bestätigt") and new_number["_aha"] == {}
    new_name = dict(_fact(1, BELEG, TEXT), aha_de="Sigmund Freud wusste das schon vor langer Zeit.")
    assert facts.check_fact(new_name, SOURCES, ["de"], 10)[0] is None and new_name["_aha"] == {}
    too_long = dict(_fact(1, BELEG, TEXT), aha_de=" ".join(["Eindrücke"] * 40))
    facts.check_fact(too_long, SOURCES, ["de"], 10)
    assert too_long["_aha"] == {}


def fact_research(aha_top="Nur ein winziger Teil der Eindrücke wird dir bewusst."):
    items = [RankItem(qid=f"F{r}", value=float(4 - r), unit="Q199", rank=r,
                      labels={"de": f"Fakt {r}", "en": f"Fact {r}"}, summary={"de": f"Text {r}.", "en": f"Text {r}."},
                      fact={"url": "u", "aha": {"de": a}})
             for r, a in ((1, aha_top), (2, "Anderer Satz."), (3, ""))]
    return type("R", (), {"items": items, "fetched_at": "2026-01-01", "references": {}, "warnings": []})()


def test_outro_says_what_was_learned_from_the_top_fact():
    spec = make_spec()
    spec.kind = "facts"
    script = build_fact_script(spec, fact_research(), "de")
    assert script.segments[-1].text.startswith("Heute gelernt: Nur ein winziger Teil der Eindrücke wird dir bewusst.")
    assert "Kommentare" in script.segments[-1].text
    # ohne geprüften Aha-Satz oder beim stärksten Kürzen: nur die Kommentarfrage
    assert build_fact_script(spec, fact_research(""), "de").segments[-1].text == retention.FACT_OUTRO["de"]
    assert build_fact_script(spec, fact_research(), "de", detail=0).segments[-1].text == retention.FACT_OUTRO["de"]


def test_rules_ask_for_aha_and_motif():
    assert "Aha-Effekt" in themen.TOPIC_RULES and "Aha" in retention.story_rules("creepy")
    for needed in ("Aha-Effekt", "aha_<sprache>", "„motiv“", "shark teeth", "Liste"):
        assert needed in facts.INSTRUCTIONS
