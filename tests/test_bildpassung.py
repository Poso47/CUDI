"""Bildpassung (Bild zeigt den Fakt) und Aha-Effekt (Heute gelernt) – ohne Netz."""

from cudi_video import bildcheck, facts, media, metadata, retention, themen
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
            def search(query, used, match=None, motif=""):
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
    assert item.image_path and item.fact["bild"] == {"motiv": "shark teeth", "passt": True, "quelle": "Foto", "wert": None}
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


# --------------------------------------------------------------------------- visuelle Prüfung (Modell per Monkeypatch)

def test_loose_tag_prefilter_needs_only_the_head_noun():
    assert media.motif_matches("shark teeth", "big teeth close", loose=True)
    assert not media.motif_matches("shark teeth", "big teeth close")
    assert not media.motif_matches("shark teeth", "a shark", loose=True)


def test_judge_needs_two_of_three_frames_clearly_ahead(monkeypatch):
    monkeypatch.setattr(bildcheck, "probabilities", lambda motif, images: images)
    ok, mean = bildcheck.judge("x", [0.9, 0.8, 0.1])
    assert ok and abs(mean - 0.6) < 1e-9
    assert bildcheck.judge("x", [0.9, 0.2, 0.1])[0] is False
    assert bildcheck.judge("x", [0.7])[0] is True                 # Foto: ein Bild genügt
    assert bildcheck.judge("x", []) == (False, 0.0)
    assert bildcheck.spread(list("abcdefghij")) == ["c", "f", "i"] and bildcheck.spread([]) == []


def test_visual_check_picks_best_passing_candidate_and_rejects_water_only(monkeypatch):
    """Probe: Pixabay-Clip mit Tag „shark“ zeigte nur Meerwasser – das Bild entscheidet, nicht der Tag."""
    monkeypatch.setattr(bildcheck, "available", lambda: True)
    scores = {"water": 0.05, "okay": 0.6, "best": 0.95}
    monkeypatch.setattr(bildcheck, "judge", lambda motif, frames: (frames[0] >= 0.5, frames[0]))
    built = []
    cands = [((lambda k=k: [scores[k]]), (lambda k=k: built.append(k) or Visual("image", k, k, "q")))
             for k in ("water", "okay", "best")]
    monkeypatch.setattr(bildcheck, "GOOD_ENOUGH", 2.0)            # alle prüfen
    found = visuals._pick(cands, "great white shark")
    assert found.path == "best" and found.score == 0.95 and built == ["best"]
    assert visuals._pick(cands[:1], "great white shark") is None   # nur Wasser: nichts
    monkeypatch.setattr(bildcheck, "GOOD_ENOUGH", 0.5)
    assert visuals._pick(cands[1:], "x").path == "okay"           # früh genug gut: nicht weiter prüfen


def test_model_failure_falls_back_to_tag_check_silently(monkeypatch):
    monkeypatch.setenv("CUDI_BILDPRUEFUNG", "1")
    monkeypatch.setattr(bildcheck, "_state", {"model": None, "failed": False})
    monkeypatch.setattr(bildcheck, "_load", lambda: (_ for _ in ()).throw(RuntimeError("kein Netz")))
    assert bildcheck.available() is False and bildcheck.enabled() is False      # einmal versucht, dann still
    assert visuals._pick([(lambda: [], lambda: Visual("image", "erster", "c", "q"))], "shark teeth").path == "erster"
    Catalog(monkeypatch, photos=["close up of shark teeth"])
    assert facts.find_visuals(tooth_fact(), "", set())["quelle"] == "Foto"       # strenger Tag-Abgleich wie zuvor


def test_find_visuals_with_model_uses_loose_tags_and_reports_score(monkeypatch):
    seen = {}
    Catalog(monkeypatch, photos=["teeth on a table"])
    monkeypatch.setattr(bildcheck, "available", lambda: True)
    real = visuals.pexels_photo

    def fake(query, used, match=None, motif=""):
        seen["motif"] = motif
        found = real(query, used, match, motif)
        if found:
            found.score = 0.87
        return found
    monkeypatch.setattr(visuals, "pexels_photo", fake)
    found = facts.find_visuals(tooth_fact(), "", set())
    assert seen["motif"] == "shark teeth" and found["quelle"] == "Foto" and found["wert"] == 0.87   # „teeth“ reicht als Vorfilter
    item = RankItem(qid="F1", value=1, unit="Q199", rank=1, fact={"motiv": "shark teeth",
                    "bild": {"motiv": "shark teeth", "passt": True, "quelle": "Foto", "wert": 0.87}})
    assert "Bildprüfung 0.87" in metadata.bild_zeile(item)[0]


def test_ranking_clips_are_ranked_by_image_not_excluded(monkeypatch):
    from cudi_video.media import Clip

    item = RankItem(qid="Q1", value=1, unit="Q11573", rank=1, labels={"en": "Mount Everest", "de": "Mount Everest"})
    monkeypatch.setattr(bildcheck, "available", lambda: True)
    monkeypatch.setattr(media.net, "download", lambda url, **k: url)
    monkeypatch.setattr("PIL.Image.open", lambda path: type("I", (), {"convert": lambda self, m: float(path)})())
    monkeypatch.setattr(bildcheck, "judge", lambda motif, frames: (True, frames[0]))
    clips = [Clip("u", 1280, 9, "c", "Pexels", key=k, preview=(v,)) for k, v in (("a", "0.1"), ("b", "0.9"), ("c", "0.5"))]
    clips.append(Clip("u", 1280, 9, "c", "NASA", key="n"))                   # ohne Vorschau: bleibt dabei, in der Mitte
    assert [c.key for c in media.rank_by_image(item, clips)] == ["b", "c", "n", "a"]
    monkeypatch.setattr(bildcheck, "available", lambda: False)
    assert [c.key for c in media.rank_by_image(item, clips)] == ["a", "b", "c", "n"]            # ohne Modell: Reihenfolge bleibt


def test_filter_namen_kollidieren_nicht():
    from cudi_video import media

    assert hasattr(media.NOT_PHOTO, "search")             # Openverse-Filter bleibt ein regulärer Ausdruck
    assert "cartoon" in media.NOT_FOOTAGE
    assert not media.motif_matches("Haifischzahn", "cartoon shark tooth")
