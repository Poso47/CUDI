"""Tests für Reddit-Story-Videos (ohne Netz)."""

import wave

import pytest

from cudi_video.story import editor, moods, sources
from cudi_video.story.moods import detect_mood, language_of, plan_from_description, seconds_per_word
from cudi_video.story.sources import Post, post_id, word_range

STORY = (
    "Throwaway because my family knows my main account.\n\n"
    "So last summer I (24F) went camping alone in the woods near my hometown. The first night was quiet. "
    "I made a small fire, ate my dinner and crawled into my tent around ten.\n\n"
    "Around two in the morning I woke up because I heard footsteps circling the tent. Slow, heavy footsteps. "
    "I froze and held my breath. Whoever it was stopped right next to my head.\n\n"
    "Then a voice whispered my name. Nobody knew I was there. Not even my BF (26M).\n\n"
    "I grabbed my phone and called the police. When they arrived, they found a second set of tent stakes "
    "fifty meters away, hidden behind the trees. Someone had been camping there for days, watching me.\n\n"
    "EDIT: thanks for all the comments, I'm okay now!\n"
    "TL;DR: someone watched me while camping."
)


def make_post(text=STORY, subreddit="LetsNotMeet", **kw):
    return Post(id="abc123", subreddit=subreddit, author="someone", title="Someone whispered my name while I was camping",
                text=text, score=1234, num_comments=56, **kw)


# --------------------------------------------------------------------------- Stimmung und Suchplan

def test_plan_from_german_description():
    plan = plan_from_description("gruselige Story über einen Stalker im Wald", "de")
    assert plan["mood"] == "creepy"
    assert {"stalker", "woods", "wald"} <= set(plan["keywords"])
    assert "shortscarystories" in plan["subreddits"]


def test_plan_explicit_subreddit_and_german_sources():
    assert plan_from_description("r/ProRevenge Rache am Vermieter")["subreddits"] == ["ProRevenge"]
    drama = plan_from_description("Drama mit der Schwiegermutter", "de")
    assert drama["subreddits"][0] == "BinIchDasArschloch"          # deutsch zuerst – keine Übersetzung nötig
    assert "meinen" not in plan_from_description("lustige Story über meinen Chef")["keywords"]


def test_detect_mood_and_language():
    assert detect_mood("nosleep", "x", "y") == "creepy"
    assert detect_mood("", "TIFU by farting in a meeting", "I accidentally ... everyone laughed lol") == "funny"
    assert language_of("Ich habe mit meiner Mutter gesprochen und sie war nicht begeistert.") == "de"
    assert language_of("I was walking home and it was dark.") == "en"


def test_german_stories_and_narrator_voice():
    from cudi_video.story.moods import narrator_gender, voice_for

    text = "Ich (m40) habe meinen Benziner verkauft. Das führt zu Streit mit meiner Partnerin (w38) und ihrer Tochter."
    assert detect_mood("beziehungen", "Beziehungskrise", text) == "drama"
    assert detect_mood("", "Rache am Chef", "Mein Chef hat mich gekündigt, also habe ich es ihm heimgezahlt. Karma.") == "revenge"
    assert narrator_gender(text) == "m" and narrator_gender("I (24F) went camping") == "f"
    assert narrator_gender("My BF (26M) said no") is None                     # nur der Ich-Erzähler zählt
    assert voice_for("drama", "de", "m")[0] == "de-DE-ConradNeural"
    assert voice_for("drama", "de")[0] == "de-DE-KatjaNeural"


def test_creepy_is_told_slower_than_funny():
    assert seconds_per_word("creepy", "en") > seconds_per_word("funny", "en")
    lo, hi = word_range("3min", "creepy", "en")
    assert 300 < hi < 400 and lo < hi
    assert word_range("teile", "creepy", "en")[1] > hi * 5


# --------------------------------------------------------------------------- Quelle

def test_post_id_from_links():
    assert post_id("https://www.reddit.com/r/nosleep/comments/1abc2de/the_title/") == "1abc2de"
    assert post_id("https://redd.it/1abc2de") == "1abc2de"
    assert post_id("t3_1abc2de") == "1abc2de"
    with pytest.raises(ValueError):
        post_id("https://example.org/story")


def test_find_stories_uses_archive_filters_and_ranks(monkeypatch):
    long_text = "word " * 250
    pool = [
        make_post(text=long_text + " stalker in the woods", subreddit="nosleep"),
        Post("b", "nosleep", "x", "Popular but unrelated tale", long_text, score=900),
        Post("c", "nosleep", "x", "Too short", "word " * 20, score=5000),
        Post("d", "nosleep", "x", "NSFW story here", long_text + " stalker", score=800, over_18=True),
        Post("e", "nosleep", "x", "The stalker and the naked truth", long_text + " stalker", score=700),
    ]
    pool[0].id = "a"
    for post in pool:
        post.source = "archiv"

    def no_reddit(sub, keywords):
        raise sources.net.FetchError("blocked")

    monkeypatch.setattr(sources, "_reddit_candidates", no_reddit)
    monkeypatch.setattr(sources, "_arctic_candidates", lambda sub, rnd, **kw: [p for p in pool])
    posts, notes = sources.find_stories({"mood": "creepy", "subreddits": ["nosleep"], "keywords": ["stalker"]},
                                        length="3min", lang="en")
    assert [p.id for p in posts] == ["a", "e"]                  # relevant, passende Länge, nicht NSFW
    assert posts[1].sensitive and not posts[0].sensitive        # heikle Story bleibt – wird umschrieben
    assert any("Archiv" in n for n in notes)


def test_rights_note_for_nosleep():
    notes = sources.rights_note(make_post(subreddit="nosleep"))
    assert any("Erlaubnis" in n and "nosleep" in n for n in notes)


# --------------------------------------------------------------------------- Lektorat

def test_clean_text_removes_meta_and_edits():
    text, notes = editor.clean_text(STORY)
    assert "Throwaway" not in text and "EDIT" not in text and "TL;DR" not in text
    assert "watching me." in text
    assert len(notes) == 2


def test_speakable_expands_and_softens():
    text, notes = editor.speakable("AITA for telling my MIL (54F) that her food is shit? My SO (30M) agrees lol.")
    assert text == "Am I the A-hole for telling my mother-in-law, 54, that her food is crap? My partner, 30, agrees."
    assert len(notes) == 3
    de, _ = editor.speakable("BIDA, weil ich (28w) meiner SchwiMu z.B. gesagt habe, das war Scheiße?", lang="de")
    assert de == "Bin ich das A-Loch, weil ich, 28, meiner Schwiegermutter zum Beispiel gesagt habe, das war Mist?"


def test_scenes_and_parts():
    text = " ".join(f"This is sentence number {i} of the story." for i in range(60))
    scenes = editor.make_scenes(text)
    assert all(30 <= len(s.split()) <= 60 for s in scenes[:-1])
    seconds = [editor.estimate_seconds(s, "en", "-12%", 0.6) for s in scenes]
    parts = editor.split_parts(seconds, 60)
    assert sorted(i for p in parts for i in p) == list(range(len(scenes)))
    assert all(sum(seconds[i] for i in p) <= 51 for p in parts)


def test_visuals_follow_the_scene():
    query, prompt = editor.visual_for("I heard footsteps circling the tent near the campfire.", "creepy", 0)
    assert query == "campfire night" and "horror" in prompt          # „night“ steckt schon drin
    assert editor.visual_for("The office was empty.", "creepy", 0)[0] == "office dark"
    assert editor.visual_for("Ich ging in den Keller.", "creepy", 0)[0] == "dark basement stairs"
    assert editor.visual_for("Nothing to see.", "funny", 1)[0] == moods.MOODS["funny"]["default_queries"][1]


def test_build_skeleton_rules_only(monkeypatch):
    monkeypatch.setattr(editor.llm, "available", lambda: False)
    sk = editor.build_skeleton(make_post(), lang="en", length="3min")
    assert sk["mood"] == "creepy" and sk["voice"]["name"] == "en-US-AriaNeural"   # Erzählerin „I (24F)“
    assert any("weiblich" in n for n in sk["notes"])
    assert sk["title"].startswith("Someone whispered")
    assert len(sk["parts"]) == 1 and sk["parts"][0]["intro"] == sk["title"]
    scenes = sk["parts"][0]["scenes"]
    assert all(s["text"] and s["query"] and s["prompt"] for s in scenes)
    assert "girlfriend" not in " ".join(s["text"] for s in scenes)      # nichts hinzugedichtet
    assert "boyfriend" in " ".join(s["text"] for s in scenes)
    assert "comments" in sk["parts"][-1]["outro"]


def test_build_skeleton_translates_when_needed(monkeypatch):
    monkeypatch.setattr(editor.llm, "available", lambda: False)
    monkeypatch.setattr(editor, "translate", lambda texts, target, source="en": ([f"[de] {t}" for t in texts], "Test"))
    sk = editor.build_skeleton(make_post(), lang="de")
    assert sk["title"].startswith("[de]") and sk["voice"]["name"] == "de-DE-AmalaNeural"
    assert any("Übersetzt mit Test" in n for n in sk["notes"])
    assert sk["parts"][0]["scenes"][0]["source"].startswith("So last summer")   # Bildsuche nutzt das Original


def test_long_story_is_split_into_parts(monkeypatch):
    monkeypatch.setattr(editor.llm, "available", lambda: False)
    long_story = "\n\n".join(STORY.split("\n\n")[1:5]) * 6
    sk = editor.build_skeleton(make_post(text=long_story), lang="en", length="teile")
    assert len(sk["parts"]) >= 2
    assert "Part 2" in sk["parts"][0]["outro"] and sk["parts"][1]["intro"].startswith("Part 2.")
    assert all(p["estimated_seconds"] <= 179 for p in sk["parts"])


# --------------------------------------------------------------------------- Video-Bausteine

def test_caption_groups_and_ass(tmp_path):
    from cudi_video.story.render import build_ass, caption_groups

    words = [{"text": w, "start": i * 0.4, "end": i * 0.4 + 0.35} for i, w in enumerate("I heard footsteps outside my tent".split())]
    groups = caption_groups(words)
    assert [len(g) for g in groups] == [3, 3]
    ass = build_ass(tmp_path / "c.ass", words, "Inter", "creepy", "TEIL 1/2", "TEIL 2 FOLGT", 2.0, 4.0).read_text()
    assert ass.count("Dialogue: 1,") == 6                          # ein Ereignis je Wort (Hervorhebung)
    assert "&H003A28E8" in ass                                      # Rot (E8283A) im ASS-Format BBGGRR
    assert "TEIL 1/2" in ass and "TEIL 2 FOLGT" in ass


def test_post_card_and_music(tmp_path):
    from cudi_video.story.music import make_music
    from cudi_video.story.render import post_card

    sk = {"mood": "funny", "lang": "de", "title": "Heute habe ich im Meeting aus Versehen gefurzt",
          "post": {"subreddit": "tifu", "author": "someone", "score": 12345, "num_comments": 678}}
    card = post_card(sk, 1, 2, tmp_path / "card.png")
    from PIL import Image
    with Image.open(card) as img:
        assert img.width == 940 and img.mode == "RGBA"
    music = make_music("pluck", 3.0, tmp_path / "m.wav")
    with wave.open(str(music)) as f:
        assert f.getnchannels() == 2 and abs(f.getnframes() / f.getframerate() - 3.0) < 0.01


def test_metadata_credits_author_and_ai():
    from cudi_video.story.pipeline import metadata, validate_skeleton
    from cudi_video.story.visuals import Visual

    sk = {"lang": "de", "mood": "creepy", "title": "Jemand flüsterte meinen Namen",
          "post": {"author": "someone", "subreddit": "LetsNotMeet", "url": "https://www.reddit.com/r/LetsNotMeet/comments/abc123/"},
          "parts": [{"scenes": [{"text": "a"}]}, {"scenes": [{"text": "b"}]}]}
    meta = metadata(sk, 0, [Visual("image", "x.jpg", "KI-Bild (Pollinations)")])
    assert "(Teil 1/2)" in meta["title"] and "u/someone auf r/LetsNotMeet" in meta["description"]
    assert "KI-generierte Symbolbilder" in meta["description"] and "KI-Stimme" in meta["caption"]
    with pytest.raises(ValueError):
        validate_skeleton({**sk, "parts": [{"scenes": [{"text": " "}]}]})


def test_captions_break_at_sentence_ends():
    from cudi_video.story.render import caption_groups, mark_punctuation

    text = "I ran into the woods. The setup was quiet, almost too quiet."
    spoken = ["I", "ran", "into", "the", "woods", "The", "setup", "was", "quiet", "almost", "too", "quiet"]
    words = mark_punctuation([{"text": w, "start": i, "end": i + 0.5} for i, w in enumerate(spoken)], text)
    assert words[4]["punct"] == "." and words[8]["punct"] == ","
    groups = [" ".join(w["text"] for w in g) for g in caption_groups(words)]
    assert "woods The" not in " | ".join(groups)
    assert groups == ["I ran into", "the woods", "The setup was", "quiet", "almost too quiet"]


def test_llm_editor_keeps_originals_where_details_were_invented(monkeypatch):
    calls = []

    def fake_chat_json(system, user, **kw):
        calls.append(system)
        if "Prüfe" in system:                                   # Prüfer: Szene 2 enthält Erfundenes
            return {"added": [2]}
        return {"title": "Jemand flüsterte meinen Namen", "scenes": [
            {"text": "Letzten Sommer war ich allein zelten.", "visual": "a lonely tent in a dark forest", "query": "tent forest"},
            {"text": "Ein Bär mit roten Augen stand vor dem Zelt.", "visual": "a bear", "query": "bear"},
        ]}

    monkeypatch.setattr(editor.llm, "available", lambda: True)
    monkeypatch.setattr(editor.llm, "chat_json", fake_chat_json)
    monkeypatch.setattr(editor, "translate", lambda texts, target, source="en": ([f"[de] {t}" for t in texts], "Test"))
    monkeypatch.setattr(editor, "make_scenes", lambda text: ["Last summer I went camping alone.", "I heard footsteps."])
    sk = editor.build_skeleton(make_post(), lang="de")
    texts = [s["text"] for s in sk["parts"][0]["scenes"]]
    assert texts[0] == "Letzten Sommer war ich allein zelten."            # geglättet übernommen
    assert texts[1] == "[de] I heard footsteps." and "Bär" not in " ".join(texts)   # Erfundenes ersetzt
    assert sk["editor"] == "KI-Lektorat" and sk["title"] == "Jemand flüsterte meinen Namen"
    assert sk["parts"][0]["scenes"][0]["query"] == "tent forest"
    assert len(calls) == 2


def test_contractions_without_apostrophes_are_fixed():
    text, notes = editor.speakable("so im sitting there and i didnt know it wasnt muted. thats on me")
    assert text == "so I'm sitting there and I didn't know it wasn't muted. that's on me"
    assert any("Apostroph" in n for n in notes)
    assert editor.speakable("I live in an IM chat and a dim room")[0] == "I live in an IM chat and a dim room"


def test_sensitive_passages_are_rephrased_not_removed():
    text, notes = editor.speakable("We had sex for the first time and she was naked. Later he killed himself. "
                                   "It was sexual harassment.")
    assert text == ("We got intimate for the first time and she was without clothes. Later he unalived himself. "
                    "It was harassment.")
    assert any("umschrieben" in n for n in notes)
    de, _ = editor.speakable("Wir hatten Sex und sie war nackt. Er hat Suizid begangen. Es war sexuelle Belästigung.",
                             lang="de")
    assert de == "Wir wurden intim und sie war unbekleidet. Er hat sich das Leben genommen. Es war Belästigung."
    assert editor.speakable("We had sex.", soften=False)[0] == "We had sex."          # nur auf Wunsch
