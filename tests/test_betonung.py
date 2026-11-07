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
