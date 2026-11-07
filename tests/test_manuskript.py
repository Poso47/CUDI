"""Tests für den Stil „manuskript“ und das Erklärvideo (ohne Netzwerk, ohne Stimme)."""

import json
from pathlib import Path

import pytest

from cudi_video.render import linien, manuskript as M, theme


@pytest.fixture(autouse=True)
def _reset_style():
    yield
    theme.apply_style({"name": "neon", "format": "karte", "motion": "gleiten"})


def test_format_manuskript_is_selectable_and_brings_its_own_design():
    assert "manuskript" in theme.FORMAT_NAMES and "manuskript" in theme.STYLES
    pick = theme.pick_style("abc", "mountain", wanted="manuskript")
    assert pick["format"] == "manuskript" and pick["name"] == "manuskript"
    picks = [theme.pick_style(f"v{i}", None) for i in range(60)]
    assert all((p["name"] == "manuskript") == (p["format"] == "manuskript") for p in picks)
    theme.apply_style(pick)
    assert theme.STYLE["bg"] == "manuskript" and theme.STYLE["effect"] == "staub"
    assert theme.background(0.5).size == (theme.W, theme.H)
    from cudi_video.job import _format
    assert _format("Manuskript") == "manuskript"


def test_fonts_for_manuskript_are_there():
    index = theme._font_index()
    for name in M.FILES.values():
        assert name.lower() in index, name
    for ofl in ("EBGaramond-OFL.txt", "Amiri-OFL.txt", "Inter-OFL.txt"):
        assert (theme.config.ASSETS_DIR / "fonts" / ofl).exists()
    theme.apply_style({"name": "manuskript", "format": "manuskript", "motion": "gleiten"})
    assert theme.font("black", 60).getname()[0] == "EB Garamond"


def test_align_tokens_uses_voice_times():
    words = [{"text": w, "start": i * 0.4, "end": i * 0.4 + 0.3} for i, w in enumerate("Gibt es den Schnitt".split())]
    assert M.align_tokens("Gibt es den Schnitt?", words) == pytest.approx([0.0, 0.4, 0.8, 1.2])
    # Die Stimme teilt anders (Zahl in zwei Teile): jedes Wort bekommt trotzdem eine nicht rückwärts laufende Zeit
    spoken = [{"text": "Wert", "start": 0.0, "end": 0.2}, {"text": "1", "start": 0.3, "end": 0.4},
              {"text": "618", "start": 0.5, "end": 0.9}]
    starts = M.align_tokens("Wert 1,618", spoken)
    assert len(starts) == 2 and starts == sorted(starts)


def test_sentence_reveals_word_by_word_and_shrinks_long_text():
    words = [{"text": w, "start": 0.2 + i * 0.3, "end": 0.45 + i * 0.3} for i, w in enumerate("Der Goldene Schnitt ist eine Zahl".split())]
    s = M.Sentence("Der Goldene Schnitt ist eine Zahl", words, 0.0, bold=["Goldene", "Schnitt"])
    early, late = M.background(0), M.background(0)
    s.draw(early, 0.1, 300)
    s.draw(late, 3.0, 300)
    assert early.tobytes() == M.background(0).tobytes()          # vor dem ersten Wort ist nichts zu sehen
    assert late.tobytes() != early.tobytes()
    long = " ".join(["Wort"] * 60)
    big = M.Sentence(long, [], 0.0, max_h=330)
    assert big.height <= 330 or big.height < M.Sentence(long, [], 0.0).height


@pytest.mark.parametrize("name", linien.VISUALS)
def test_every_visual_draws(name):
    params = {"pose": "zwei", "wert": "1,618...", "n": 120}
    layer = linien.draw_visual(name, params, 1.0, 2.0)
    if name == "zitatkarte":
        assert layer is None
        return
    assert layer.size == (linien.SIZE, linien.SIZE)
    assert layer.getchannel("A").getbbox() is not None
    early = linien.draw_visual(name, params, 0.0, 0.0)
    assert early.tobytes() != layer.tobytes()                      # die Grafik baut sich auf


@pytest.mark.parametrize("pose", linien.POSES)
def test_poses(pose):
    assert linien.draw_visual("figur", {"pose": pose}, 1.0, 1.0).getchannel("A").getbbox() is not None


def test_script_validation():
    from cudi_video.erklaer.skript import ScriptError, validate_script

    ok = validate_script({"szenen": [{"text": "Hallo", "visual": {"typ": "baum"}}]})
    assert ok["szenen"][0]["visual"]["typ"] == "baum" and ok["sprache"] == "de"
    for bad in ({}, {"szenen": []}, {"szenen": [{"visual": {"typ": "baum"}}]},
                {"szenen": [{"text": "x", "visual": {"typ": "unbekannt"}}]},
                {"szenen": [{"text": "x", "visual": {"typ": "figur", "pose": "fliegen"}}]},
                {"szenen": [{"text": "x", "visual": {"typ": "zitatkarte"}}]}):
        with pytest.raises(ScriptError):
            validate_script(bad)


def test_example_script_and_scene_frames():
    from cudi_video.erklaer import load_script
    from cudi_video.erklaer.render import LEAD, STYLE, build_jobs
    from cudi_video.render.scenes import make_scene

    path = Path(__file__).resolve().parent.parent / "examples" / "erklaer_goldener_schnitt.json"
    script = load_script(path)
    assert 6 <= len(script["szenen"]) <= 8
    assert {sz["visual"]["typ"] for sz in script["szenen"]} <= set(linien.VISUALS)
    text = json.dumps(script, ensure_ascii=False).lower()
    assert not any(w in text for w in ("allah", "quran", "prophet", "gott"))      # keine religiösen Aussagen
    voiced = []
    for sz in script["szenen"]:
        toks = sz["text"].split()
        voiced.append((Path("x.wav"), [{"text": w, "start": 0.3 * i, "end": 0.3 * i + 0.25} for i, w in enumerate(toks)],
                       0.3 * len(toks)))
    jobs = build_jobs(script, voiced, Path("/tmp/none"))
    assert jobs[0]["style"] == STYLE and jobs[0]["lead"] == LEAD
    for job in jobs:
        scene = make_scene(job)
        for frac in (0.05, 0.5, 0.97):
            assert scene.frame(frac * job["duration"]).size == (theme.W, theme.H)
