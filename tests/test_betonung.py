"""Betonung: Spannung wird gesprochen (Teile mit eigenem Tempo/Tonhöhe + Pausen), Wortzeiten wandern mit."""

import shutil
import wave

import numpy as np
import pytest

from cudi_video import config, tts
from cudi_video.models import Script, Segment

needs_ffmpeg = pytest.mark.skipif(not shutil.which("ffmpeg"), reason="ffmpeg fehlt")


def test_base_rate_is_normal_not_faster():
    assert config.VOICE_RATE == "+0%"


def test_question_gets_a_pause_after_it_and_is_slower():
    parts = tts.plan_parts("Wusstest du das? Der Hai lebt im Meer.", "intro")
    assert [p.role for p in parts] == ["frage", "normal"]
    assert parts[0].rate < 0 and parts[0].pitch < 0
    assert parts[1].pause == tts.PAUSE_AFTER_QUESTION


def test_pause_before_place_and_before_the_number():
    parts = tts.plan_parts("Der Hai ist gefährlich und schnell. Platz 1: Das Krokodil, es wird rund 6 Meter lang.", "item")
    texts = [p.text for p in parts]
    assert any(t.startswith("Platz 1") for t in texts)
    place = next(p for p in parts if p.text.startswith("Platz 1"))
    assert place.role == "platz" and place.pause >= tts.PAUSE_BEFORE_PLACE
    number = next(p for p in parts if p.text.startswith("rund 6"))       # „rund“ gehört zur Zahl
    assert number.role == "zahl" and number.pause >= tts.PAUSE_BEFORE_NUMBER and number.rate < 0


def test_split_before_place_inside_a_sentence():
    parts = tts.plan_parts("Und jetzt kommt der Spitzenreiter des ganzen Rankings Platz eins", "item")
    assert [p.role for p in parts][-1] == "platz" and parts[-1].pause >= tts.PAUSE_BEFORE_PLACE


def test_dash_and_ellipsis_split_with_pause():
    parts = tts.plan_parts("Der Hai – und das ist der Clou – hat 300 Zähne… Wirklich viele Zähne.", "item")
    assert len(parts) >= 3
    assert all(p.pause >= tts.PAUSE_AFTER_BREAK for p in parts[1:3])
    assert " – " not in " ".join(p.text for p in parts)


def test_abbreviations_do_not_end_a_sentence():
    parts = tts.plan_parts("Er wiegt ca. 300 Kilogramm und lebt lange.", "item")
    assert len(parts) == 1 or all("ca." not in p.text.split()[-1:] for p in parts)


def test_words_keep_their_order_and_parts_are_limited():
    text = "Eins zwei drei vier. " * 20 + "Platz 1: Ende."
    parts = tts.plan_parts(text, "item")
    assert 1 <= len(parts) <= 8
    assert tts.plan_parts("   ", "item")[0].text.strip() == ""
    short = "Das ist ein langer Satz mit vielen Wörtern. Noch einer hier."
    assert " ".join(p.text for p in tts.plan_parts(short, "item")) == short


def test_prosody_strings_follow_the_base_rate():
    part = tts.Part("x", rate=-9, pitch=-2, volume=6)
    assert tts.part_prosody(part, "+0%") == ("-9%", "-2Hz", "+6%")
    assert tts.part_prosody(part, "+8%")[0] == "-1%"
    assert tts.part_prosody(tts.Part("x", rate=-90), "+0%")[0] == "-45%"


def _fake_synth(calls):
    async def fake(text, voice, out_path, rate, pitch="+0Hz", volume="+0%"):
        calls.append((text, rate, pitch, volume))
        sr = 24000
        tone = (np.sin(np.arange(int(0.5 * sr)) / 8) * 9000).astype(np.int16)
        pcm = np.concatenate([np.zeros(int(0.2 * sr), np.int16), tone, np.zeros(int(0.3 * sr), np.int16)])   # Rand-Stille
        with wave.open(str(out_path), "wb") as f:
            f.setnchannels(1)
            f.setsampwidth(2)
            f.setframerate(sr)
            f.writeframes(pcm.tobytes())
        n = max(1, len(text.split()))
        return [{"text": w, "start": round(0.2 + 0.5 * k / n, 3), "end": round(0.2 + 0.5 * (k + 0.9) / n, 3)}
                for k, w in enumerate(text.split())]
    return fake


@needs_ffmpeg
def test_voice_script_inserts_pauses_and_shifts_word_times(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(tts, "_synthesize", _fake_synth(calls))
    script = Script(lang="de", title="t", segments=[
        Segment(kind="intro", text="Wusstest du das? Der Hai lebt im Meer."),
        Segment(kind="item", text="Kurz gesagt."),
    ])
    tts.voice_script(script, tmp_path, "de-DE-ConradNeural", "+0%")
    intro, item = script.segments
    # je Teil ein Aufruf, mit eigener Prosodie (Frage: langsamer und tiefer)
    assert calls[0][0] == "Wusstest du das?" and calls[0][1].startswith("-") and calls[0][2].startswith("-")
    assert calls[1][1] == "+0%"
    words = intro.words
    assert [w["text"] for w in words] == "Wusstest du das? Der Hai lebt im Meer.".split()
    starts = [w["start"] for w in words]
    assert starts == sorted(starts) and starts[0] < 0.1                   # Randstille ist weg
    gap = words[3]["start"] - words[2]["end"]                             # „das?“ -> „Der“
    assert gap >= tts.PAUSE_AFTER_QUESTION - 0.02                         # Spannungspause steht in den Wortzeiten
    assert abs(intro.duration - (words[-1]["end"] + 0.07)) < 0.15
    assert item.duration > 0.4 and (tmp_path / "01_item.wav").exists()
    assert all(w["end"] <= intro.duration + 1e-6 for w in words)


@needs_ffmpeg
def test_assemble_parts_without_pause_keeps_parts_back_to_back(tmp_path, monkeypatch):
    import asyncio

    calls = []
    fake = _fake_synth(calls)
    parts = [tts.Part("Eins zwei"), tts.Part("drei vier", pause=0.5)]
    spoken = [(tmp_path / f"s{i}.wav", asyncio.run(fake(p.text, "v", tmp_path / f"s{i}.wav", "+0%"))) for i, p in enumerate(parts)]
    words, duration = tts.assemble_parts(parts, spoken, tmp_path / "out.wav")
    assert [w["text"] for w in words] == ["Eins", "zwei", "drei", "vier"]
    assert 0.55 < words[2]["start"] - words[1]["end"] < 0.85              # 0,5 s Pause + Ränder
    assert duration > words[-1]["end"]


# --------------------------------------------------------------------------- Story je Stimmung

STORY = ("Ich wohnte allein am Waldrand. Jede Nacht hörte ich Schritte auf dem Dachboden. "
         "Ich redete mir ein, es sei der Wind. Dann sah ich es: Die Luke stand offen.")


def test_creepy_story_waits_before_the_turn_and_is_slower():
    parts = tts.plan_story_parts(STORY, "creepy")
    assert [p.role for p in parts] == ["normal", "wendung"]                 # Fließtext bleibt ein Stück
    assert parts[0].pause == 0 and "Waldrand" in parts[0].text and "Wind" in parts[0].text
    assert parts[1].pause >= 0.7 and parts[1].rate < parts[0].rate and parts[1].pitch < parts[0].pitch


def test_funny_story_pauses_before_the_punchline_not_after():
    text = "Mein Chef bat mich um eine Präsentation. Ich war vorbereitet. Und dann öffnete ich meine Einkaufsliste."
    parts = tts.plan_story_parts(text, "funny")
    assert parts[-1].role == "pointe" and parts[-1].pause >= 0.45           # Pause davor
    assert parts[0].pause == 0 and len(parts) == 2                           # nichts Extra danach (kein Teil, keine Stille)


def test_reveal_and_question_in_drama():
    parts = tts.plan_story_parts("Wir stritten ständig. Es stellte sich heraus, dass er gelogen hatte. Warum tat er das?", "drama")
    roles = [p.role for p in parts]
    assert roles[1] == "wendung" and parts[1].pause >= 0.6 and roles[-1] == "frage"


def test_story_parts_are_limited_and_unknown_mood_works():
    text = " ".join(f"Dann kam Schritt {i}." for i in range(30))
    assert len(tts.plan_story_parts(text, "creepy")) <= 12
    assert tts.plan_story_parts("Nur ein Satz.", "unbekannt")[0].text == "Nur ein Satz."


def test_story_prosody_adds_to_the_voice_values():
    part = tts.Part("x", rate=-9, pitch=-4)
    assert tts.part_prosody(part, "-12%", "-6Hz") == ("-21%", "-10Hz", "+0%")


@needs_ffmpeg
def test_voice_texts_with_mood_inserts_the_pause_and_keeps_old_path(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(tts, "_synthesize", _fake_synth(calls))
    res = tts.voice_texts([STORY, "Kurzer Text."], tmp_path / "a", "de-DE-KillianNeural", "-12%", "-6Hz", 0.6, mood="creepy")
    wav, words, duration = res[0]
    assert [w["text"] for w in words] == STORY.split()
    turn = next(i for i, w in enumerate(words) if w["text"] == "Dann")
    assert words[turn]["start"] - words[turn - 1]["end"] >= 0.7 and wav.exists() and duration > words[-1]["end"]
    assert calls[1][1] == "-21%" and calls[1][2] == "-10Hz"                  # Tempo/Tonhöhe der Wendung auf die Stimme gerechnet
    calls.clear()
    old = tts.voice_texts([STORY, "Kurzer Text."], tmp_path / "b", "de-DE-KillianNeural", "-12%", "-6Hz", 0.6)
    assert len(calls) == 2 and calls[0][1] == "-12%" and len(old) == 2     # ohne Stimmung wie bisher: ein Text, ein Stück


# --------------------------------------------------------------------------- Sprechprofile je Videoart

TEXT = "Wusstest du, dass Bienen tanzen? Tatsächlich übermitteln sie so die Richtung. Der Tanz dauert rund 15 Sekunden."


def test_profile_is_chosen_from_the_video_kind_and_env_overrides(monkeypatch):
    monkeypatch.delenv("CUDI_SPEECH_PROFILE", raising=False)
    assert tts.speech_profile("numbers") == "ranking" and tts.speech_profile(None) == "ranking"
    assert tts.speech_profile("facts") == "fakten" and tts.speech_profile("erklaer") == "erklaer"
    monkeypatch.setenv("CUDI_SPEECH_PROFILE", "erklaer")
    assert tts.speech_profile("numbers") == "erklaer"
    monkeypatch.setenv("CUDI_SPEECH_PROFILE", "unsinn")
    assert tts.speech_profile("facts") == "fakten"                          # ungültiger Wert wird ignoriert


def test_every_profile_defines_all_roles_it_detects():
    for name, prof in tts.SPEECH_PROFILES.items():
        for role in prof["erkennt"]:
            assert role in prof["rollen"], (name, role)
        assert {"normal", "hook", "frage"} <= set(prof["rollen"]) and {"satz", "frage", "umbruch"} <= set(prof["pausen"])


def test_ranking_is_tense_fakten_explains_erklaer_is_even():
    ranking = tts.plan_parts(TEXT, "item", "ranking")
    fakten = tts.plan_parts(TEXT, "item", "fakten")
    erklaer = tts.plan_parts(TEXT, "item", "erklaer")
    assert ranking[1].role == "normal" and ranking[1].rate == 0                       # Ranking: Fließtext normal
    assert fakten[1].role == "kern" and fakten[1].pause >= 0.5 and fakten[1].rate < 0  # Aha-Satz: Pause davor, langsamer
    assert all(p.rate <= -3 for p in fakten if p.role == "normal")                   # Erklärteil ruhig und etwas langsamer
    assert all(p.pause <= 0.4 for p in erklaer)                                        # kurze, gleichmäßige Pausen
    assert max(p.pause for p in ranking) > 0.4 and not any(p.role == "platz" for p in erklaer)


def test_erklaer_stresses_terms_lightly_without_splitting_numbers():
    text = "Der Vorgang heißt „Photosynthese“. Pflanzen brauchen dafür Licht und 6 Moleküle Wasser am Tag."
    parts = tts.plan_parts(text, "item", "erklaer")
    assert parts[0].role == "fachbegriff" and parts[0].volume > 0 and parts[0].rate > -9
    assert any("6 Moleküle" in p.text and p.text.startswith("Pflanzen") for p in parts)   # Zahl bleibt im Satzfluss


@needs_ffmpeg
def test_aus_switches_expressive_speech_off(tmp_path, monkeypatch):
    calls = []
    monkeypatch.setattr(tts, "_synthesize", _fake_synth(calls))
    monkeypatch.setenv("CUDI_SPEECH_PROFILE", "aus")
    script = Script(lang="de", title="t", segments=[Segment(kind="item", text=TEXT)])
    tts.voice_script(script, tmp_path, "de-DE-ConradNeural", "+0%", profile="fakten")
    assert len(calls) == 1 and calls[0][0] == TEXT                                       # ganzer Text am Stück
    tts.voice_texts([STORY], tmp_path / "s", "de-DE-KillianNeural", mood="creepy")
    assert len(calls) == 2                                                               # Story ebenfalls am Stück
