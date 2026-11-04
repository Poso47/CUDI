"""Schreibaufträge an Claude: erzählte Ranking-Texte und freie Themen – streng geprüft, immer mit Ausweichweg."""

import json

import pytest

from cudi_video import handoff, narrate, planner
from cudi_video.script import build_script
from tests.test_video import make_research, make_spec


@pytest.fixture
def writing(tmp_path, monkeypatch):
    monkeypatch.setenv(handoff.ENV, "1")
    monkeypatch.setenv(handoff.DIR_ENV, str(tmp_path))
    return tmp_path


def answer(path, data):
    task = json.loads(path.read_text("utf-8"))
    task["antwort"] = data
    path.write_text(json.dumps(task, ensure_ascii=False), "utf-8")


def test_inactive_without_flag(monkeypatch):
    monkeypatch.delenv(handoff.ENV, raising=False)
    assert narrate.request(make_spec(), make_research(), ["de"]) == {}


def test_narration_is_asked_once_then_checked(writing):
    spec, research = make_spec(), make_research()
    with pytest.raises(handoff.WritingNeeded) as need:
        narrate.request(spec, research, ["de"])
    task = json.loads(need.value.path.read_text("utf-8"))
    places = task["daten"]["de"]["plaetze"]
    assert [p["platz"] for p in places] == [3, 2, 1] and places[-1]["wert"].startswith("828")
    assert "Turm A ist ein Gebäude" in places[-1]["wikipedia"]
    good = (places[-1]["start"] + " Mit 828 Metern ragt Turm A über alles hinaus. Ganz oben wartet eine "
            "Aussichtsplattform – und eröffnet wurde er 2010.")
    answer(need.value.path, {"de": {
        "1": good,
        "2": places[1]["start"] + " Ganze 679 Meter, gebaut 1999.",               # 1999 steht nirgends -> Baustein
        "3": "Wir starten mit Platz 3, Turm C: 632 Meter, eine lange Linie über dem Wasser.",   # Komma statt Punkt ok
    }})
    with pytest.raises(handoff.WritingNeeded) as fix:                # abgelehnte Plätze gehen einmal zurück
        narrate.request(spec, research, ["de"])
    retry = json.loads(fix.value.path.read_text("utf-8"))["daten"]["de"]["plaetze"]
    assert sorted(p["platz"] for p in retry) == [2] and retry[0]["grund"] == "Zahl ohne Beleg"
    answer(fix.value.path, {"de": {"2": places[1]["start"] + " Ganze 679 Meter, gebaut 1999."}})   # unverändert falsch
    narration = narrate.request(spec, research, ["de"])
    script = build_script(spec, research, "de", use_llm=False, narration=narration["de"])
    texts = {s.rank: s.text for s in script.segments if s.kind == "item"}
    assert texts[1] == good and script.mode == "claude"
    assert "1999" not in texts[2] and "1998" not in texts[2] and "Linie" in texts[3]
    assert sum("übernommen" in c for c in script.checks) == 2 and sum("verworfen" in c for c in script.checks) == 1


def test_narration_rejects_missing_value_rank_claims_and_length():
    place = {"start": "Platz 2: Turm B.", "wert": "679 Meter", "wikipedia": "", "woerter": 20, "platz": 2}
    assert narrate.check("Platz 2: Turm B. Sehr hoch.", place) == "geprüfter Wert fehlt"
    assert narrate.check("Platz 2: Turm B. 679 Meter – das zweithöchste Gebäude.", place) == "Wertung oder Rang-Aussage"
    assert narrate.check("Platz 2: Turm B. 679 Meter. " + "Wort " * 40, place).startswith("zu lang")
    assert narrate.check("Platz 2: Turm B. Stolze 679 Meter hoch!", place) is None


def test_plan_with_claude_checks_ids(writing, monkeypatch):
    labels = {"Q12280": "bridge", "Q12570": "suspension bridge", "Q183": "Germany"}
    monkeypatch.setattr(planner, "_label", lambda q: labels.get(q, "something else"))
    monkeypatch.setattr(planner, "_search", lambda label: None)
    with pytest.raises(handoff.WritingNeeded) as need:
        planner.plan_with_claude("die längsten Brücken Deutschlands", 10)
    assert "P2043" in json.loads(need.value.path.read_text("utf-8"))["daten"]["eigenschaften"]
    answer(need.value.path, {"klasse_qid": "Q12280", "klasse_en": "bridge", "eigenschaft": "P2043",
                             "weitere_klassen": [{"qid": "Q12570", "en": "suspension bridge"}, {"qid": "Q1", "en": "x"}],
                             "land_qid": "Q183", "land_en": "Germany", "spitzenreiter": [{"qid": "", "en": "Some Bridge"}],
                             "titel_de": "Die längsten Brücken Deutschlands",
                             "titel_en": "The {count} Longest Bridges in Germany", "hashtags_de": ["Brücken", "#bau"]})
    spec = planner.plan_with_claude("die längsten Brücken Deutschlands", 10)
    src = spec["source"]
    assert src["class"] == "Q12280" and src["extra_classes"] == ["Q12570"] and src["country"] == "Q183"
    assert spec["title"]["de"] == "Die {count} längsten Brücken Deutschlands" and spec["unit"] == "km"
    assert spec["hashtags"]["de"] == ["ranking", "brücken", "bau"]
    from cudi_video.spec import VideoSpec
    assert VideoSpec.from_dict(spec).title["de"] == "Die 10 längsten Brücken Deutschlands"


def test_plan_with_claude_rejects_wrong_ids_and_explains(writing, monkeypatch):
    monkeypatch.setattr(planner, "_label", lambda q: "human")
    monkeypatch.setattr(planner, "_search", lambda label: None)
    with pytest.raises(handoff.WritingNeeded) as need:
        planner.plan_with_claude("die schönsten Sonnenuntergänge", 10)
    answer(need.value.path, {"fehler": "Schönheit lässt sich nicht messen – wie wäre es mit den höchsten Bergen?"})
    with pytest.raises(planner.PlanFailed, match="nicht messen"):
        planner.plan_with_claude("die schönsten Sonnenuntergänge", 10)
    answer(need.value.path, {"klasse_qid": "Q5", "klasse_en": "bridge", "eigenschaft": "P2043"})
    with pytest.raises(planner.PlanFailed, match="gibt es bei Wikidata"):
        planner.plan_with_claude("die schönsten Sonnenuntergänge", 10)


def test_job_prints_schreiben_and_resumes(writing, monkeypatch, capsys):
    """Freies Thema ohne Vorlage: der Auftrag hält mit SCHREIBEN an und läuft mit --weiter weiter."""
    from types import SimpleNamespace

    from cudi_video import job

    monkeypatch.setattr(job, "job_folder", lambda job_id: writing / f"auftrag-{job_id}")
    monkeypatch.setattr(planner, "_label", lambda q: "bridge")
    calls = []
    monkeypatch.setattr(job, "RETRY_PAUSE", 0)
    monkeypatch.setattr("cudi_video.pipeline.run", lambda spec, **kw: calls.append(spec) or
                        {"videos": {}, "warnings": [], "output_dir": str(kw["out"])})
    order = json.dumps({"id": "brueckentest", "art": "ranking", "thema": "die längsten Brücken", "sprachen": ["de"],
                        "nur_skript": True})
    code = job.main(SimpleNamespace(dokument=None, weiter=None, auftrag=order, adressen=None))
    out = capsys.readouterr().out
    assert code == job.EXIT_WRITE and "SCHREIBEN:" in out and not calls
    path = writing / "auftrag-brueckentest" / "schreiben_planen.json"
    answer(path, {"klasse_qid": "Q12280", "klasse_en": "bridge", "eigenschaft": "P2043",
                  "spitzenreiter": [{"qid": "Q12280", "en": "bridge"}],
                  "titel_de": "Die {count} längsten Brücken der Welt", "titel_en": "The {count} Longest Bridges"})
    assert job.main(SimpleNamespace(dokument=None, weiter="brueckentest", auftrag=None, adressen=None)) == 0
    assert len(calls) == 1 and calls[0].source.cls == "Q12280" and calls[0].title["de"] == "Die 10 längsten Brücken der Welt"


def test_narration_rejects_invented_details():
    place = {"start": "Platz 4: Abraj Al Bait.", "wert": "607 Meter", "woerter": 30, "platz": 4, "sprache": "de",
             "wikipedia": "Die Abraj Al Bait sind eine Hochhausgruppe in Mekka, entworfen vom US-amerikanischen Architekturbüro X.",
             "beschreibung": "", "zusatz": [], "vergleich": ""}
    assert narrate.check("Platz 4: Abraj Al Bait. 607 Meter in Mekka. Ganz oben thront eine riesige Uhr.",
                         place).startswith("nicht belegt: Uhr")
    assert narrate.check("Platz 4: Abraj Al Bait. 607 Meter hoch, entworfen von einem US-Büro – mitten in Mekka.",
                         place) is None


def test_free_topics_keep_only_confirmed_values(monkeypatch):
    """Freie Themen: Werte ohne unabhängige Bestätigung (z. B. Aquädukt 17 km) fliegen raus, der Nächste rückt nach."""
    from cudi_video import verify as verify_module

    spec, research = make_spec(), make_research()
    spec.confirmed_only, spec.count = True, 2
    status = {"Q1": "nur eine Quelle", "Q2": "bestätigt", "Q3": "bestätigt"}

    def fake(spec, item, checkers):
        item.verification = {"status": status[item.qid], "sources": [], "evidence": [], "outliers": []}
        return item.verification

    monkeypatch.setattr(verify_module, "verify_item", fake)
    verify_module.verify(spec, research)
    assert [it.qid for it in research.items] == ["Q2", "Q3"] and research.items[0].rank == 1
    assert any("Turm A: nicht verwendet" in w for w in research.warnings)
    spec.count, research = 4, make_research()           # 3 von 4 bestätigt -> ehrliche Top 3 statt Lücke
    spec.title = {"de": "Die 4 höchsten Türme", "en": "The 4 Tallest Towers"}
    status["Q1"] = "bestätigt"
    verify_module.verify(spec, research)
    assert spec.count == 3 and spec.title["de"] == "Die 3 höchsten Türme" and len(research.items) == 3
    spec.count, research = 3, make_research()
    status["Q1"] = status["Q2"] = "nur eine Quelle"
    with pytest.raises(ValueError, match="nicht genug"):
        verify_module.verify(spec, research)


STORY = ("I bought a telescope after my divorce. Every night I drove out to Blue Springs to look at the stars. "
         "The park was empty and the woods were silent. On the third night I noticed a light between the trees. "
         "It moved when I moved. I packed up fast, but the light followed my car for 2 miles. "
         "When I got home, there were muddy footprints on my porch. They led to my window and stopped there. "
         "I have not gone back to the park since. My telescope is still in the trunk of my car.")


def test_story_edit_by_claude_is_checked_scene_by_scene(writing, monkeypatch):
    from cudi_video.story import editor
    from cudi_video.story.sources import post_from_text

    post = post_from_text("The light in the woods", STORY, subreddit="shortscarystories")
    with pytest.raises(handoff.WritingNeeded) as need:
        editor.build_skeleton(post, lang="en", mood="creepy", use_llm=False)
    task = json.loads(need.value.path.read_text("utf-8"))
    scenes = task["daten"]["szenen"]
    assert task["daten"]["zielsprache"] == "en" and task["daten"]["entschaerfen"] is True and len(scenes) >= 2
    reply = [{"text": s.replace("I bought", "After the divorce, I bought"), "bild": "a lonely man with a telescope "
              "under a starry sky at the edge of a forest", "suche": "night sky telescope"} for s in scenes]
    reply[-1]["text"] = scenes[-1] + " Jessica never believed me."          # neuer Name -> Regel-Fassung
    answer(need.value.path, {"titel": "Something in the trees", "hook": "The light between the trees moved "
                             "when I moved.", "szenen": reply})
    sk = editor.build_skeleton(post, lang="en", mood="creepy", use_llm=False)
    texts = [s["text"] for p in sk["parts"] for s in p["scenes"]]
    assert sk["editor"] == "Claude-Lektorat" and sk["title"] == "Something in the trees"
    assert sk["hook"].startswith("The light between the trees") and "Jessica" not in texts[-1]
    assert texts[0].startswith("After the divorce") or "After the divorce" in " ".join(texts)
    first = sk["parts"][0]["scenes"][0]
    assert first["query"] == "night sky telescope" and first["prompt"].endswith("no text")
    assert any("Regel-Fassung" in n and "neue Namen: Jessica" in n for n in sk["notes"])


def test_story_edit_rejects_new_numbers_and_translates_fallback(writing, monkeypatch):
    from cudi_video.story import editor

    monkeypatch.setattr(editor, "translate", lambda texts, target, source="en": ([f"DE: {t}" for t in texts], "Test"))
    scenes = ["I drove out to the park every night for 2 weeks.", "The woods were silent and empty.",
              "Then I saw a light between the trees."]
    with pytest.raises(handoff.WritingNeeded) as need:
        editor.claude_edit("The light", scenes, "de", "en", "creepy", True)
    answer(need.value.path, {"titel": "Das Licht", "hook": "Zwischen den Bäumen bewegte sich ein Licht.",
                             "szenen": [{"text": "Drei Wochen lang fuhr ich jede Nacht in den Park, 3 Wochen.",
                                         "bild": "x", "suche": "!!!"},
                                        {"text": "Der Wald war still und leer.", "bild": "a silent dark forest at night "
                                         "with fog", "suche": "dark forest"},
                                        {"text": "Dann sah ich ein Licht zwischen den Bäumen.", "bild": "a faint light "
                                         "between dark trees at night", "suche": "light trees night"}]})
    title, texts, visuals, hook, notes, figure = editor.claude_edit("The light", scenes, "de", "en", "creepy", True)
    assert texts[0] == "DE: " + scenes[0] and texts[1] == "Der Wald war still und leer." and title == "Das Licht"
    assert hook and visuals[1][0] == "dark forest" and visuals[0][0] != "!!!"
    assert any("1 (neue Zahl)" in n for n in notes)


def test_story_edit_falls_back_to_rules_when_mostly_wrong(writing):
    from cudi_video.story import editor

    scenes = ["One.", "Two scenes here.", "Three scenes here now."]
    with pytest.raises(handoff.WritingNeeded) as need:
        editor.claude_edit("T", scenes, "en", "en", "creepy", True)
    answer(need.value.path, {"titel": "T", "szenen": [{"text": ""}, {"text": ""}, {"text": "Three scenes here now."}]})
    assert editor.claude_edit("T", scenes, "en", "en", "creepy", True) is None


def test_cartoon_prompts_keep_one_main_character():
    from cudi_video.story.visuals import FIGURES, cartoon_prompt

    figure = FIGURES["m"]
    with_person = cartoon_prompt("a lonely man at a telescope, dark cinematic horror photograph, eerie atmosphere, fog, "
                                 "low light, muted colors, film grain, vertical composition, no text", "creepy", figure)
    assert "photograph" not in with_person and with_person.startswith("flat 2D cartoon")   # Stil zuerst
    assert figure in with_person and "no text" in with_person[:160]
    no_person = cartoon_prompt("an empty field beside a dark lake, vertical composition, no text", "creepy", figure)
    assert figure not in no_person and "an empty field beside a dark lake" in no_person
    long = cartoon_prompt("a man " + "very " * 80 + "tall, vertical composition, no text", "creepy", "x " * 150)
    assert long[:400].startswith("flat 2D cartoon") and "no text" in long[:400]   # Stil übersteht die Kürzung


def test_known_leaders_are_always_candidates(monkeypatch):
    """Freie Themen: von Claude genannte Spitzenreiter kommen dazu, auch wenn die Klassen-Suche sie nicht findet."""
    from cudi_video.sources import wikidata
    from cudi_video.spec import WikidataSource

    def row(qid, value):
        return {"item": {"value": f"http://www.wikidata.org/entity/{qid}"}, "value": {"value": str(value)},
                "unit": {"value": "http://www.wikidata.org/entity/Q11573"},
                "rank": {"value": "http://wikiba.se/ontology#NormalRank"}}

    queries = []

    def sparql(query, **kw):
        queries.append(query)
        return [row("Q999", 164800)] if "VALUES ?item" in query else [row("Q1", 12700), row("Q2", 4800)]

    monkeypatch.setattr(wikidata, "_sparql", sparql)
    src = WikidataSource(cls="Q12280", property="P2043", seed_items=["Q999"], country="Q148")
    found = wikidata.pick_latest(wikidata._ranking_bindings(src, fresh=False))
    assert set(found) == {"Q1", "Q2", "Q999"} and found["Q999"].value == 164800
    seed_query = next(q for q in queries if "VALUES ?item" in q)
    assert "wdt:P17 wd:Q148" in seed_query                     # Region gilt auch für Spitzenreiter


def test_search_handles_dashes_in_names(monkeypatch):
    """„Changhua–Kaohsiung Viaduct“ (Halbgeviertstrich) findet die Wikidata-Suche nur mit normalem Bindestrich."""
    seen = []

    def get_json(url, params, **kw):
        seen.append(params["search"])
        hits = [{"id": "Q30160840", "label": "Changhua-Kaohsiung Viaduct"}] if "–" not in params["search"] else []
        return {"search": hits}

    monkeypatch.setattr("cudi_video.net.get_json", get_json)
    assert planner._search("Changhua–Kaohsiung Viaduct") == "Q30160840"
    assert seen[0] == "Changhua–Kaohsiung Viaduct" and seen[1] == "Changhua-Kaohsiung Viaduct"


def test_story_edit_checks_names_numbers_and_title_strictly(writing):
    """Copilot-Hinweise: „Mark“ ist nicht durch „market“ belegt, Zahlwörter und Dezimalwerte werttreu, Vornamen
    auch in deutschen Fassungen, Titel ebenso geprüft."""
    from cudi_video.story import editor

    src = "I went to the market for two hours. It cost 1.5 dollars."
    assert editor._edit_problem("I went to the market with Mark for two hours. It cost 1.5 dollars.", src, "en", "en",
                                src).startswith("neue Namen: Mark")
    assert editor._edit_problem("I went to the market for three hours. It cost 1.5 dollars.", src, "en", "en",
                                src) == "neue Zahl"
    assert editor._edit_problem("I went to the market for two hours. It cost 15 dollars.", src, "en", "en",
                                src) == "neue Zahl"
    assert editor._edit_problem("Ich war zwei Stunden auf dem Markt. Es kostete 1,5 Dollar.", src, "de", "en", src) is None
    assert editor._edit_problem("Ich war zwei Stunden mit Jessica auf dem Markt. Es kostete 1,5 Dollar.", src, "de",
                                "en", src).startswith("neue Namen: Jessica")
    assert editor._known("Jessicas", editor._tokens("Jessica said no")) and not editor._known("Mark", editor._tokens("market"))
    assert editor._numbers("1.500 Euro", "de") == {"1500"} and editor._numbers("1,500 dollars", "en") == {"1500"}

    scenes = ["I went to the market for two hours.", "Nobody followed me home.", "The door was open."]
    with pytest.raises(handoff.WritingNeeded) as need:
        editor.claude_edit("The open door", scenes, "en", "en", "creepy", True)
    answer(need.value.path, {"titel": "Jessica followed me home", "hook": "The door was open when I got home.",
                             "szenen": [{"text": s} for s in scenes]})
    title, *_ = editor.claude_edit("The open door", scenes, "en", "en", "creepy", True)
    assert title == "The open door"                                    # erfundene Person im Titel -> Original


def test_seed_query_checks_object_class(monkeypatch):
    from cudi_video.sources import wikidata
    from cudi_video.spec import WikidataSource

    queries = []
    monkeypatch.setattr(wikidata, "_sparql", lambda q, **kw: queries.append(q) or [])
    wikidata._seed_bindings(WikidataSource(cls="Q12570", property="P2043", extra_classes=["Q181348"], seed_items=["Q1"]))
    assert "wdt:P31/wdt:P279* ?cls" in queries[0] and "wd:Q12570 wd:Q181348" in queries[0]


def test_mascot_env_wins_when_order_does_not_choose(tmp_path, monkeypatch):
    from cudi_video import job

    monkeypatch.setenv("CUDI_MASCOT", "0")
    monkeypatch.setattr(job, "_ranking", lambda order, folder, progress: (_ for _ in ()).throw(ValueError("x")))
    job.run_order({"id": "maskenprobe", "art": "ranking", "maskottchen": None}, tmp_path / "a")
    assert job.os.environ["CUDI_MASCOT"] == "0"
    job.run_order({"id": "maskenprobe", "art": "ranking", "maskottchen": True}, tmp_path / "b")
    assert job.os.environ["CUDI_MASCOT"] == "1"


def test_hook_is_on_the_card_and_counts_for_the_part_length(tmp_path):
    from PIL import Image

    from cudi_video import job
    from cudi_video.story.moods import seconds_per_word
    from cudi_video.story.render import post_card

    sk = {"mood": "creepy", "lang": "en", "title": "The open door", "post": {"subreddit": "x", "author": "y"},
          "parts": [{"intro": "The open door", "outro": "Follow for more stories.", "scenes": []}]}
    plain = Image.open(post_card(sk, 1, 1, tmp_path / "a.png")).size[1]
    sk["hook"] = "The door was open when I got home. Nobody else has a key."
    assert Image.open(post_card(sk, 1, 1, tmp_path / "b.png")).size[1] > plain     # Einstieg lesbar ohne Ton
    words = int(165 / seconds_per_word("creepy", "en"))                             # passt ohne Einstieg knapp
    sk["parts"][0]["scenes"] = [{"text": " ".join(["word"] * (words // 2))}, {"text": " ".join(["word"] * (words // 2))}]
    sk["hook"] = " ".join(["hook"] * 30)
    job.fit_parts(sk)
    assert len(sk["parts"]) == 2                                                   # mit langem Einstieg zu lang


def test_narration_needs_whole_words_as_evidence():
    place = {"start": "Number 3: Tower X.", "wert": "541 meters", "woerter": 30, "platz": 3, "sprache": "en",
             "wikipedia": "Tower X stands next to the old market.", "beschreibung": "", "zusatz": [], "vergleich": ""}
    assert narrate.check("Number 3: Tower X. 541 meters, right by the market.", place) is None
    assert narrate.check("Number 3: Tower X. 541 meters. Mark designed it.", place).startswith("nicht belegt: Mark")


def test_plan_asks_once_more_for_known_leaders(writing, monkeypatch):
    """Probelauf: Haiku ließ die Spitzenreiter leer – dann fragt der Code einmal gezielt nach den Namen."""
    monkeypatch.setattr(planner, "_label", lambda q: "bridge")
    monkeypatch.setattr(planner, "_search", lambda label: {"Danyang–Kunshan Grand Bridge": "Q595768",
                                                           "Tianjin Grand Bridge": "Q1066786"}.get(label))
    with pytest.raises(handoff.WritingNeeded) as need:
        planner.plan_with_claude("die längsten Brücken der Welt", 5)
    answer(need.value.path, {"klasse_qid": "Q12280", "klasse_en": "bridge", "eigenschaft": "P2043",
                             "weitere_klassen": [], "spitzenreiter": [], "titel_de": "Die {count} längsten Brücken"})
    with pytest.raises(handoff.WritingNeeded) as more:
        planner.plan_with_claude("die längsten Brücken der Welt", 5)
    task = json.loads(more.value.path.read_text("utf-8"))
    assert task["aufgabe"] == "spitzenreiter" and task["daten"]["art"] == "bridge"
    answer(more.value.path, {"spitzenreiter": ["Danyang–Kunshan Grand Bridge", "Tianjin Grand Bridge", "Unknown"]})
    spec = planner.plan_with_claude("die längsten Brücken der Welt", 5)
    assert spec["source"]["seed_items"] == ["Q595768", "Q1066786"]
