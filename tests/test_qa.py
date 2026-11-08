"""Endkontrolle (qa.py) und Mixer (render/audio.py) mit synthetischen ffmpeg-Clips."""

import subprocess

import numpy as np
import pytest

from cudi_video import qa
from cudi_video.render import audio

pytestmark = pytest.mark.skipif(subprocess.run(["which", "ffmpeg"], capture_output=True).returncode != 0,
                                reason="ffmpeg fehlt")


def clip(path, seconds=6, size="1080x1920", video="testsrc2", volume=0.25, black=None):
    vf = f"drawbox=enable='between(t,{black[0]},{black[1]})':w=iw:h=ih:color=black:t=fill" if black else "null"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"{video}=s={size}:r=10:d={seconds}",
                    "-f", "lavfi", "-i", f"sine=f=440:d={seconds}", "-vf", vf, "-af", f"volume={volume}",
                    "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(path)], check=True)
    return path


def test_loudness_is_corrected_once(tmp_path):
    f = clip(tmp_path / "leise.mp4", volume=0.02)
    result = qa.check(f, "ranking")
    assert result["korrigiert"] and result["lufs_vor"] < -20
    assert abs(result["lufs_nach"] - qa.TARGET_LUFS) <= qa.LUFS_TOLERANCE
    assert result["true_peak"] <= qa.MAX_TRUE_PEAK


def test_black_section_and_resolution_are_reported(tmp_path):
    f = clip(tmp_path / "schwarz.mp4", size="540x960", black=(2, 4))
    result = qa.check(f, "ranking", fix=False)
    assert result["schwarz"] and not result["ok"]
    assert any("Auflösung" in b for b in result["befunde"])
    assert any("Schwarze" in b for b in result["befunde"])


def test_freeze_only_for_ranking(tmp_path):
    f = clip(tmp_path / "still.mp4", video="color", seconds=6)
    assert qa.check(f, "ranking", fix=False)["standbild"]
    assert qa.check(f, "story", fix=False)["standbild"] == []


def test_duration_limit(tmp_path):
    f = clip(tmp_path / "lang.mp4", size="1080x1920", seconds=4)
    assert any("Dauer" in b for b in qa.check(f, "story", max_seconds=2, fix=False)["befunde"])


def test_layout_boxes_in_ui_zones():
    assert qa.layout_findings({"Text": (100, 1500, 500, 1700)})
    assert qa.layout_findings({"Text": (100, 200, 1060, 400)})
    assert qa.layout_findings({"Text": (100, 200, 800, 400)}) == []
    assert qa.layout_findings() == []        # die echten Untertitel liegen in der sicheren Zone


def test_music_style_switch(monkeypatch):
    monkeypatch.setenv("CUDI_MUSIK", "0")
    assert audio.music_style("ranking") is None
    monkeypatch.setenv("CUDI_MUSIK", "1")
    assert audio.music_style("ranking") == "pulse" and audio.music_style("erklaer", "manuskript") == "pad"
    assert audio.music_style("facts", topic="Tiere im Meer") == "warm"


def test_music_is_ducked_under_voice():
    rate = audio.SR
    voice = np.zeros(rate * 4, dtype=np.float32)
    voice[rate:rate * 2] = 0.3 * np.sin(2 * np.pi * 220 * np.arange(rate) / rate)
    music = (0.5 * np.sin(2 * np.pi * 110 * np.arange(len(voice)) / rate)).astype(np.float32)
    mixed = audio.mix_music(voice, music)
    speaking, pause = np.abs(mixed[int(rate * 1.4):int(rate * 1.7)]).mean(), np.abs(mixed[int(rate * 3):int(rate * 3.5)]).mean()
    assert pause > 0 and speaking < pause * 0.5
