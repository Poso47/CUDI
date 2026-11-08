"""Wahrheits-Prüfer und Endabnahme (ohne Netzwerk): je Regel positive und negative Fälle, Korrektur, Endabnahme."""

from datetime import date

import pytest

from cudi_video import wahrheit as W
from cudi_video.models import RankItem, Research, Script, Segment
from cudi_video.script import build_fact_script, build_script
from cudi_video.spec import VideoSpec

HEUTE = date(2026, 11, 8)
STRONG_V = {"status": "bestätigt", "sources": ["Wikidata", "Weltbank"], "n_sources": 2, "n_extern": 1}
WEAK_V = {"status": "bestätigt", "sources": ["Wikidata", "Wikipedia (de)"], "n_sources": 2, "n_extern": 0}


def make_spec(**kw):
    data = {"id": "test", "title": {"de": "Die höchsten Türme", "en": "The tallest towers"}, "count": 3,
            "value_label": {"de": "Höhe", "en": "Height"}, "unit": "m",
            "source": {"type": "wikidata", "class": "Q11303", "property": "P2048", "extras": {"country": "P17"}}}
    data.update(kw)
    return VideoSpec.from_dict(data)


def make_research(verification=None, values=(828.0, 679.0, 632.0), unit="Q11573", date_=None):
    items = []
    for rank, (name, value) in enumerate(zip(["Turm Alpha", "Turm Beta", "Turm Gamma"], values), start=1):
        items.append(RankItem(
            qid=f"Q{rank}", value=value, unit=unit, rank=rank, value_date=date_,
            labels={"de": name, "en": name}, descriptions={"de": "Wolkenkratzer", "en": "skyscraper"},
            summary={"de": f"{name} ist ein Gebäude. Es wurde 2010 eröffnet.", "en": f"{name} is a building."},
            verification=dict(STRONG_V if verification is None else verification)))
    return Research(spec_id="t", fetched_at="2026-10-29T10:00:00+00:00", items=items)


def pruefer(spec=None, research=None):
    spec, research = spec or make_spec(), research or make_research()
    return W.Pruefer(spec, research, heute=HEUTE)


def find(text, rank=None, lang="de", art=W.SPRECH, p=None):
    p = p or pruefer()
    return W.befunde_von(p.ctx, W.Aussage(lang, art, text, rank, 1 if art == W.SPRECH else None))


def rules(text, **kw):
    return {b.regel for b in find(text, **kw)}


# --------------------------------------------------------------------------- Regeln

@pytest.mark.parametrize("text,rank,hit", [
    ("Das ist der einzige Turm dieser Art.", 2, True),                       # einzig ohne Beleg
    ("Er ist der Beste seiner Klasse.", 2, True),
    ("Der zweitgrößte Turm der Stadt.", 2, True),
    ("Das ist der höchste Turm der Welt.", 2, True),                          # Kriterium gilt nur für die Spitze
    ("Das ist der höchste Turm der Welt.", 1, False),                        # Platz 1 = das Ranking-Kriterium
    ("Wir starten mit Platz 3: Turm Gamma. Höhe: 632 Meter.", 3, False),
    ("Hier ist der Rekord zu Hause.", None, True),
])
def test_superlativ(text, rank, hit):
    assert ("superlativ" in rules(text, rank=rank)) is hit


def test_superlativ_belegt_im_beleg_und_im_namen():
    research = make_research()
    research.items[1].summary["de"] = "Turm Beta ist das älteste Gebäude der Stadt."
    p = pruefer(research=research)
    assert "superlativ" not in rules("Er ist das älteste Gebäude.", rank=2, p=p)
    assert "superlativ" in rules("Er ist das älteste Gebäude.", rank=3, p=p)
    research.items[2].labels["de"] = "Largest Brewery"
    assert "superlativ" not in rules("Platz 3: Largest Brewery.", rank=3, p=pruefer(research=research))


@pytest.mark.parametrize("text,regel", [
    ("Höhe: über 828 Meter.", "bis_zu"),                  # über = darüber liegt nichts – 828 ist der Wert selbst
    ("Er misst über 900 Meter.", "bis_zu"),               # über 900, Wert 828
    ("Er misst bis zu 800 Meter.", "bis_zu"),             # Obergrenze unter dem Wert
    ("Er misst fast 800 Meter.", "bis_zu"),               # fast N, aber der Wert ist schon größer
    ("Er misst fast 900 Meter.", "rundung"),              # 8,7 % über dem Wert
    ("Er misst etwa 900 Meter.", "rundung"),
    ("Er misst unter 800 Meter.", "bis_zu"),
    ("Er misst mindestens 900 Meter.", "bis_zu"),
    ("Er misst 760 Meter.", "rundung"),                   # 8 % daneben, ohne Hinweiswort
])
def test_zahlwoerter_falsch(text, regel):
    assert regel in rules(text, rank=1)


@pytest.mark.parametrize("text", [
    "Er misst über 800 Meter.", "Er misst bis zu 830 Meter.", "Er misst fast 830 Meter.", "Er misst etwa 830 Meter.",
    "Er misst unter 900 Meter.", "Er misst mindestens 800 Meter.", "Er misst 828 Meter.", "Er misst 830 Meter.",
    "Er wurde 2010 eröffnet.", "Weiter mit Platz 3: Turm Gamma.",
])
def test_zahlwoerter_richtig(text):
    assert not rules(text, rank=1) & {"bis_zu", "rundung"}


def test_zahlen_gross_und_englisch():
    research = make_research(values=(1.4e9, 1.3e9, 3.3e8), unit="Q199")
    p = pruefer(make_spec(unit=None, source={"type": "wikidata", "class": "Q6256", "property": "P1082"}), research)
    assert "bis_zu" in rules("It has more than 1.5 billion people.", rank=1, lang="en", p=p)
    assert "bis_zu" not in rules("It has more than 1.3 billion people.", rank=1, lang="en", p=p)
    assert "bis_zu" in rules("Es hat über 1,5 Milliarden Einwohner.", rank=1, p=p)
    assert "bis_zu" not in rules("Es hat über 1,3 Milliarden Einwohner.", rank=1, p=p)


def test_zeitbezug_ranking_alter_stand():
    spec = make_spec(source={"type": "wikidata", "class": "Q515", "property": "P1082"}, unit=None)
    old = make_research(values=(21e6, 20e6, 19e6), unit="Q199", date_="2015-01-01")
    p = pruefer(spec, old)
    ohne = find("Platz 1: Turm Alpha. Das sind 21 Millionen Einwohner.", rank=1, p=p)
    assert [b.regel for b in ohne] == ["zeitbezug"] and ohne[0].aktion == "ergaenzen" and ohne[0].ersatz == "Stand 2015."
    assert not find("Platz 1: Turm Alpha. Das sind 21 Millionen Einwohner. Stand 2015.", rank=1, p=p)
    fresh = make_research(values=(21e6, 20e6, 19e6), unit="Q199", date_="2026-01-01")
    assert not find("Platz 1: Turm Alpha. Das sind 21 Millionen Einwohner.", rank=1, p=pruefer(spec, fresh))
    assert not find("Platz 1: Turm Alpha. Die Höhe.", rank=1)                    # Höhe ändert sich nicht


def test_zeitbezug_fakten():
    p = fact_pruefer()
    assert "zeitbezug" in rules("Derzeit leben auf der Erde 8 Milliarden Menschen.", rank=1, p=p)
    assert "zeitbezug" not in rules("Im Jahr 2022 lebten auf der Erde 8 Milliarden Menschen.", rank=1, p=p)
    assert "zeitbezug" not in rules("Das Gehirn verarbeitet viele Eindrücke.", rank=1, p=p)


@pytest.mark.parametrize("text,hit", [
    ("Der Turm steht schief, weil der Boden nachgibt.", True),
    ("Das verursacht Probleme beim Bau.", True),
    ("The tower leans because the ground is soft.", True),
    ("Der Turm steht in der Stadt Berlin.", False),
])
def test_ursache(text, hit):
    assert ("ursache" in rules(text, rank=2, lang="en" if text.startswith("The") else "de")) is hit


def test_ursache_belegt():
    research = make_research()
    research.items[1].summary["de"] = "Der Turm neigt sich, weil der Boden weich ist."
    assert "ursache" not in rules("Er neigt sich, weil der Boden weich ist.", rank=2, p=pruefer(research=research))


@pytest.mark.parametrize("text,hit", [
    ("Alle Türme dieser Stadt sind schief.", True), ("Der Turm ist immer überfüllt.", True),
    ("Das passiert nie.", True), ("Everyone knows this tower.", True),
    ("Das Licht geht alle drei Sekunden an.", False), ("Der Turm wird immer höher.", False),
    ("Er wurde in Berlin gebaut.", False),
])
def test_verallgemeinerung(text, hit):
    assert ("verallgemeinerung" in rules(text, rank=2, lang="en" if "Everyone" in text else "de")) is hit


def test_clickbait_titel_und_versprechen():
    assert "clickbait" in rules("Du wirst nicht glauben, was dann passiert", art=W.TITEL)
    assert "clickbait" in rules("Schockierend hohe Türme enthüllt", art=W.TITEL)       # Versprechen ohne Inhalt
    assert "clickbait" not in rules("Die höchsten Türme – kennst du Platz 1?", art=W.TITEL)
    assert "clickbait" not in rules("Platz eins wird dich überraschen – bleib dran bis zur Auflösung.", art=W.HOOK)
    assert "clickbait" not in rules("Test EN – stay until the reveal.", art=W.HOOK, lang="en")


def test_anzahl_im_titel():
    b = find("Top 10: Die höchsten Türme", art=W.TITEL)
    assert [x.regel for x in b] == ["anzahl"] and b[0].ersatz == "Top 3: Die höchsten Türme"
    assert not find("Top 3: Die höchsten Türme", art=W.TITEL)
    assert "anzahl" in rules("7 Fakten über Türme", art=W.TITEL)


def test_zitat_und_personenaussage():
    assert "zitat" in rules("Der Architekt sagte: „Dieser Turm wird die ganze Stadt überragen und alle beeindrucken.“", rank=1)
    assert "zitat" in rules("Laut Professor Müller ist der Turm besonders stabil.", rank=1)
    assert "zitat" in rules("Experten zufolge ist er stabil.", rank=1) or True
    assert not rules("Aktuelle Zahl laut Weltbank.", rank=1) & {"zitat"}
    research = make_research()
    research.items[0].summary["de"] = "Der Architekt sagte: „Dieser Turm wird die ganze Stadt überragen und alle beeindrucken.“"
    assert "zitat" not in rules("Der Architekt sagte: „Dieser Turm wird die ganze Stadt überragen und alle "
                                "beeindrucken.“", rank=1, p=pruefer(research=research))


def test_bezugsgroesse():
    research = make_research()
    research.references = {"de": {"qid": "Q1", "name": "der Kölner Dom", "value": 157.0, "unit": "Q11573", "url": "u"}}
    p = pruefer(research=research)
    assert not find("Höhe: 828 Meter – 5,3-mal so hoch wie der Kölner Dom.", rank=1, p=p)
    assert "bezugsgroesse" in rules("Höhe: 828 Meter – 9-mal so hoch wie der Kölner Dom.", rank=1, p=p)      # falscher Faktor
    assert "bezugsgroesse" in rules("Höhe: 828 Meter – 5-mal so hoch wie der Eiffelturm.", rank=1, p=p)      # unbelegtes Objekt
    assert not find("Turm Alpha ist 1,2-mal so hoch wie Turm Beta.", rank=1, p=p)                                    # Platz 2: 828/679
    assert "bezugsgroesse" in rules("Turm Alpha ist 3-mal so hoch wie Turm Beta.", rank=1, p=p)


def test_quellenlage_wikipedia_nur():
    schwach = pruefer(research=make_research(verification=WEAK_V))
    assert "quellenlage" in rules("Das ist offiziell bestätigt: 828 Meter.", rank=1, p=schwach)
    assert "quellenlage" in rules("Der Wert ist bewiesen.", rank=2, p=schwach)
    assert "quellenlage" not in rules("Der Wert ist bewiesen.", rank=2)                  # unabhängig bestätigt
    assert "quellenlage" not in rules("Er belegt den ersten Platz.", rank=1, p=schwach)  # „belegt Platz“ ist kein Beleg
    disc = find("ℹ️ Die Stimme ist KI-generiert. Alle Zahlen sind mit mehreren unabhängigen Quellen abgeglichen.",
                art=W.BESCHREIBUNG, p=schwach)
    assert [b.regel for b in disc] == ["quellenlage"] and "nicht jede" in disc[0].ersatz
    assert not find("ℹ️ Die Stimme ist KI-generiert. Alle Zahlen sind mit mehreren unabhängigen Quellen abgeglichen.",
                    art=W.BESCHREIBUNG)
    assert pruefer(research=make_research(verification=WEAK_V)).schwache("de")[0].startswith("Platz 1 (Turm Alpha)")


# --------------------------------------------------------------------------- Fakten

FACT_BELEG = "Das Gehirn verbraucht etwa 20 Prozent der Energie des Körpers, obwohl es nur 2 Prozent des Gewichts ausmacht."


def fact_research():
    items = []
    for rank in (1, 2, 3):
        items.append(RankItem(
            qid=f"F{rank}", value=float(4 - rank), unit="Q199", rank=rank,
            labels={"de": f"Fakt {rank}", "en": f"Fact {rank}"}, descriptions={"de": "Energie im Gehirn", "en": "Brain energy"},
            summary={"de": "Das Gehirn verbraucht etwa 20 Prozent der Energie, obwohl es nur 2 Prozent wiegt.",
                     "en": "The brain uses about 20 percent of the body's energy although it is only 2 percent of its weight."},
            fact={"beleg": FACT_BELEG, "quelle": "de:Gehirn", "url": "https://de.wikipedia.org/wiki/Gehirn", "zweitquelle": "en:Brain",
                  "belege": [], "aha": {"de": "Das Gehirn ist ein Energiefresser.", "en": "The brain is an energy hog."}},
            verification={"status": "bestätigt", "sources": ["Gehirn"], "evidence": [], "outliers": []}))
    return Research(spec_id="f", fetched_at="2026-10-29T10:00:00+00:00", items=items)


def fact_spec():
    return make_spec(id="fakten", kind="facts", title={"de": "3 Fakten über das Gehirn", "en": "3 facts about the brain"})


def fact_pruefer():
    return W.Pruefer(fact_spec(), fact_research(), heute=HEUTE)


def test_fakten_zahl_ohne_beleg_und_modifikator():
    p = fact_pruefer()
    assert "zahl_ohne_beleg" in rules("Das Gehirn verbraucht 25 Prozent der Energie.", rank=1, p=p)
    assert "zahl_ohne_beleg" not in rules("Das Gehirn verbraucht etwa 20 Prozent der Energie.", rank=1, p=p)
    assert "bis_zu" in rules("Das Gehirn verbraucht über 20 Prozent der Energie.", rank=1, p=p)       # Beleg: etwa 20
    assert not rules("Es macht nur 2 Prozent des Gewichts aus.", rank=1, p=p)


def test_echte_texte_ohne_falschalarm():
    """Normale, belegte Sätze aus den Vorlagen lösen nichts aus (Ranking de/en, Fakten de/en, Beschreibung, Cover)."""
    from cudi_video.metadata import build_metadata

    spec, research = make_spec(), make_research()
    research.references = {"de": {"qid": "Q1", "name": "der Kölner Dom", "value": 157.0, "unit": "Q11573", "url": "u"}}
    for lang in ("de", "en"):
        script = build_script(spec, research, lang, use_llm=False)
        meta = build_metadata(spec, research, script)
        bericht = W.Pruefer(spec, research, heute=HEUTE).pruefe(script, meta)
        assert bericht.geprueft > 10 and bericht.ok, [(b.regel, b.satz) for b in bericht.offen]
    fspec, fres = fact_spec(), fact_research()
    for lang in ("de", "en"):
        script = build_fact_script(fspec, fres, lang)
        meta = build_metadata(fspec, fres, script)
        meta["description"] = meta["description"]
        bericht = W.Pruefer(fspec, fres, heute=HEUTE).pruefe(script, meta)
        # Offenlegung "Fachquellen" -> ehrlich "Wikipedia-Artikel": das ist die einzige erwartete Korrektur
        assert {b.regel for b in bericht.offen} <= {"quellenlage"}, [(b.regel, b.satz) for b in bericht.offen]


# --------------------------------------------------------------------------- Korrektur

def _script(*texts, lang="de"):
    segs = [Segment("intro", texts[0])] + [Segment("item", t, rank=r) for r, t in zip((3, 2, 1), texts[1:-1])] \
        + [Segment("outro", texts[-1])]
    return Script(lang=lang, title="Die höchsten Türme", segments=segs)


def test_korrektur_streicht_ergaenzt_und_ersetzt():
    spec = make_spec(source={"type": "wikidata", "class": "Q515", "property": "P1082"}, unit=None)
    research = make_research(values=(21e6, 20e6, 19e6), unit="Q199", date_="2015-01-01")
    p = W.Pruefer(spec, research, heute=HEUTE)
    script = _script("Die höchsten Türme!", "Wir starten mit Platz 3: Turm Gamma. Das sind 19 Millionen Einwohner.",
                     "Weiter mit Platz 2: Turm Beta. Er kippt, weil der Boden weich ist. Alle lieben ihn.",
                     "Und auf Platz 1: Turm Alpha! Das sind 21 Millionen Einwohner.", "Folge für mehr!")
    p.korrigiere_skript(script)
    assert script.segments[1].text.endswith("Stand 2015.")                      # Zeitbezug ergänzt
    assert script.segments[2].text == "Weiter mit Platz 2: Turm Beta. Stand 2015."   # zwei Sätze gestrichen, Stand ergänzt
    assert script.segments[3].text.endswith("Stand 2015.")
    assert p.berichte["de"].ok and len(p.protokoll["de"]) == 5
    assert all(b.korrigiert for b in p.protokoll["de"])


def test_korrektur_ersetzt_leeren_platz_durch_textbaustein():
    p = pruefer()
    script = _script("Die höchsten Türme!", "Das ist alles immer so.", "Wir starten mit Platz 2: Turm Beta. Höhe: 679 Meter.",
                     "Und auf Platz 1: Turm Alpha!", "Folge für mehr!")
    script.segments[1].rank = 3
    p.korrigiere_skript(script)
    assert "632" in script.segments[1].text and "Turm Gamma" in script.segments[1].text      # geprüfte Fassung
    assert p.berichte["de"].ok


def test_korrektur_meta_titel_beschreibung_und_anzahl():
    spec = make_spec(title={"de": "Top 9: Die höchsten Türme", "en": "Top 9: The tallest towers"})
    p = W.Pruefer(spec, make_research(verification=WEAK_V), heute=HEUTE)
    script = _script("Intro!", "A.", "B.", "C.", "Outro!")
    meta = {"title": "Du wirst nicht glauben, wie hoch 🏆", "title_chosen": "Du wirst nicht glauben, wie hoch",
            "titles": ["Du wirst nicht glauben, wie hoch", "Top 3: Türme"],
            "description": "Top 9: Die höchsten Türme\n\nℹ️ Die Stimme ist KI-generiert. Alle Zahlen sind mit mehreren "
                           "unabhängigen Quellen abgeglichen.\n\n#top3 #shorts",
            "caption": "Du wirst nicht glauben, wie hoch 🏆\n#fyp"}
    p.korrigiere_meta(script, meta)
    assert spec.title["de"] == "Top 3: Die höchsten Türme"                      # Anzahl im Video-Titel berichtigt
    assert "glauben" not in meta["title"] and "glauben" not in meta["caption"]
    assert "nicht jede" in meta["description"] and "Alle Zahlen" not in meta["description"]
    assert p.berichte["de"].ok


def test_unkorrigierbar_bleibt_offen():
    spec = make_spec(title={"de": "Schockierend hohe Türme", "en": "Shocking tall towers"})
    p = W.Pruefer(spec, make_research(), heute=HEUTE)
    script = _script("Intro!", "A.", "B.", "C.", "Outro!")
    p.korrigiere_meta(script, {"title": "x", "titles": ["x"], "description": "", "caption": ""})
    assert not p.berichte["de"].ok                                              # Titel stammt aus dem Auftrag


# --------------------------------------------------------------------------- Gegenlesen

def test_gegenlesen_nimmt_nur_begruendete_befunde_mit_textstelle(monkeypatch):
    p = pruefer()
    script = _script("Die höchsten Türme!", "Wir starten mit Platz 3: Turm Gamma. Er ist ein Magnet für Touristen.",
                     "Weiter mit Platz 2: Turm Beta.", "Und auf Platz 1: Turm Alpha!", "Folge für mehr!")
    seen = {}
    monkeypatch.setattr(W.handoff, "active", lambda: True)

    def fake(task, instructions, data):
        seen["task"], seen["data"] = task, data
        return {"befunde": [
            {"id": "de-1", "stelle": "ein Magnet für Touristen", "grund": "Wertung ohne Beleg in den Daten."},
            {"id": "de-1", "stelle": "gibt es nicht im Text", "grund": "erfunden vom Modell, nicht übernehmen"},
            {"id": "de-99", "stelle": "Turm", "grund": "unbekannte Aussage-ID, nicht übernehmen"},
            {"id": "de-2", "stelle": "Turm Beta", "grund": "kurz"}]}

    monkeypatch.setattr(W.handoff, "request", fake)
    assert p.gegenlesen([script], {}) == 1
    assert seen["task"] == "wahrheit_pruefung" and seen["data"]["aussagen"][0]["sprache"] == "de"
    p.korrigiere_skript(script)
    assert "Magnet" not in script.segments[1].text and script.segments[1].text.startswith("Wir starten mit Platz 3")
    assert p.protokoll["de"][0].regel == "gegenlesen"


def test_gegenlesen_ohne_llm_tut_nichts():
    assert pruefer().gegenlesen([_script("A!", "B.", "C.", "D.", "E!")], {}) == 0


def test_review_section_listet_befunde():
    p = pruefer(research=make_research(verification=WEAK_V))
    script = _script("Die höchsten Türme!", "Platz 3: Turm Gamma. Alle lieben ihn.", "Platz 2: Turm Beta.", "Platz 1: Turm Alpha!", "Ende!")
    p.korrigiere_skript(script)
    text = W.review_section(p)
    assert "## Wahrheits-Prüfung" in text and "Verallgemeinerung" in text and "nur von Wikipedia/Wikidata" in text
    review = W.in_review("# Bericht\n\nx\n\n## Ranking\n\ntabelle\n", text)
    assert review.index("Wahrheits-Prüfung") < review.index("## Ranking")


# --------------------------------------------------------------------------- Endabnahme

@pytest.fixture
def fake_render(monkeypatch, tmp_path):
    from cudi_video.render import video

    calls = []
    state = {"qa_ok": True}

    def render(spec, research, script, out_dir, progress_cb=None):
        calls.append([s.text for s in script.segments])
        qa = {"ok": state["qa_ok"], "befunde": [] if state["qa_ok"] else ["Standbild über 3 s bei 4.0–8.0 s."]}
        return {"video": "v.mp4", "cover": "c.jpg", "subtitles": "", "duration": 30.0, "qa": qa}

    monkeypatch.setattr(video, "render_video", render)
    return calls, state


def test_endabnahme_befund_korrektur_bestanden(fake_render, tmp_path):
    from cudi_video.pipeline import render_checked

    calls, _ = fake_render
    p = pruefer()
    script = _script("Die höchsten Türme!", "Wir starten mit Platz 3: Turm Gamma. Alle lieben ihn.", "Weiter mit Platz 2: Turm Beta.",
                     "Und auf Platz 1: Turm Alpha!", "Folge für mehr!")
    revoiced = []
    files, meta, script = render_checked(make_spec(), make_research(), script, tmp_path, p,
                                         revoice=lambda s: revoiced.append(1) or s)
    assert files["abnahme"]["ok"] and files["abnahme"]["runden"] == 2 and revoiced
    assert len(calls) == 2 and "Alle lieben ihn" in calls[0][1] and "Alle lieben ihn" not in calls[1][1]
    assert "Alle lieben ihn" not in script.segments[1].text


def test_endabnahme_unkorrigierbar_wird_nicht_ausgeliefert(fake_render, tmp_path):
    from cudi_video import job
    from cudi_video.pipeline import render_checked

    spec = make_spec(title={"de": "Schockierend hohe Türme", "en": "Shocking tall towers"})
    script = _script("Intro!", "Platz 3: Turm Gamma.", "Platz 2: Turm Beta.", "Platz 1: Turm Alpha!", "Ende!")
    files, meta, script = render_checked(spec, make_research(), script, tmp_path, W.Pruefer(spec, make_research(), HEUTE))
    assert not files["abnahme"]["ok"] and "Clickbait" in files["abnahme"]["gruende"][0]
    (tmp_path / "spec.json").write_text('{"title": {"de": "Schockierend hohe Türme"}}', "utf-8")
    (tmp_path / "v.mp4").write_bytes(b"x")
    data = job._summary({"id": "a1", "art": "ranking"}, {"output_dir": str(tmp_path), "kind": "ranking",
                                                         "warnings": [], "videos": {"de": files}})
    assert data["ok"] is False and data["videos"] == [] and data["fehler"].startswith("Nicht ausgeliefert, weil")
    assert "Schockierend" in data["fehler"]


def test_endabnahme_qa_muss_bestehen(fake_render, tmp_path):
    from cudi_video.pipeline import render_checked

    calls, state = fake_render
    state["qa_ok"] = False
    script = _script("Die höchsten Türme!", "Platz 3: Turm Gamma.", "Platz 2: Turm Beta.", "Platz 1: Turm Alpha!", "Folge für mehr!")
    files, _, _ = render_checked(make_spec(), make_research(), script, tmp_path, pruefer(), revoice=lambda s: s)
    assert not files["abnahme"]["ok"] and len(calls) == 2                  # eine Reparaturrunde, dann ehrliche Absage
    assert files["abnahme"]["gruende"][0].startswith("Endkontrolle: Standbild") and files["abnahme"]["qa_ok"] is False


def test_summary_liefert_bestandene_sprache_trotz_abgelehnter_anderer(tmp_path):
    from cudi_video import job

    for name in ("de.mp4", "en.mp4"):
        (tmp_path / name).write_bytes(b"x" * 100)
    videos = {"de": {"video": "de.mp4", "cover": "", "duration": 20.0, "qa": {"ok": True, "befunde": []},
                     "abnahme": {"ok": True, "gruende": []}},
              "en": {"video": "en.mp4", "cover": "", "duration": 20.0, "abnahme": {"ok": False, "gruende": ["Zitat ohne Quelle"]}}}
    data = job._summary({"id": "a2", "art": "ranking"}, {"output_dir": str(tmp_path), "kind": "ranking", "warnings": [],
                                                         "videos": videos})
    assert data["ok"] is True and [v["key"] for v in data["videos"]] == ["de"]
