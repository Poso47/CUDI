"""Bildqualität (Paket G): Ausschlussliste, Schärfe/Auflösung, pHash-Doppelbilder, Motivprüfung je Platz, Reportage-Szene,
Ken Burns und Hook-Vorlauf."""

import numpy as np
import pytest
from PIL import Image, ImageFilter

from cudi_video import bildguete, media
from cudi_video.models import RankItem


def greenland():
    return RankItem("Q223", 2.1e6, "Q712226", labels={"en": "Greenland", "de": "Grönland"},
                    descriptions={"en": "island and autonomous territory of the Kingdom of Denmark", "de": "Insel"})


def noisy(size=(1400, 1000), seed=1):
    rng = np.random.default_rng(seed)
    base = rng.normal(128, 70, (size[1] // 20, size[0] // 20, 3)).clip(0, 255).astype("uint8")
    return Image.fromarray(base).resize(size, Image.NEAREST)


def test_search_name_has_no_german_type_word():
    assert media.search_name(greenland()) == "Greenland island"          # nicht „Greenland insel“
    assert media.visual_motif(greenland()).startswith("Greenland, an island")


def test_planet_and_globe_tags_are_excluded_for_places():
    it = greenland()
    assert not media.names_match(it, "globe, 3d model, earth, planet, north america, greenland, map")
    assert not media.names_match(it, "moon, planet, island, greenland")
    assert media.names_match(it, "iceberg, ocean, island, coast, fjord, greenland, nature")
    assert media.motif_matches("shark teeth", "close up of shark teeth") and not media.motif_matches(
        "mountain lake", "3d model of mountain lake")
    assert bildguete.excluded("Moon landing", motif="moon landing") == ""      # eigenes Motiv zählt nicht als falsch
    assert bildguete.excluded("planet Mars") == "planet"


def test_sharpness_and_resolution(tmp_path):
    sharp = noisy()
    blurred = sharp.filter(ImageFilter.GaussianBlur(14))
    assert bildguete.sharpness(sharp) > bildguete.MIN_SHARPNESS > bildguete.sharpness(blurred)
    a, b, c = tmp_path / "a.png", tmp_path / "b.png", tmp_path / "c.png"
    sharp.save(a)
    blurred.save(b)
    sharp.resize((640, 400)).save(c)
    assert bildguete.check(a) == (True, "")
    assert "unscharf" in bildguete.check(b)[1]
    assert "zu klein" in bildguete.check(c)[1]


def test_phash_finds_duplicates_in_other_size_and_quality(tmp_path):
    seen = bildguete.Seen()
    one, other = noisy(seed=1), noisy(seed=2)
    first = tmp_path / "1.png"
    one.save(first)
    assert bildguete.check(first, seen)[0]
    bildguete.remember(seen, first)
    again = tmp_path / "1b.jpg"
    one.resize((1200, 860)).save(again, quality=60)                       # gleiches Bild, andere Größe/Güte
    assert bildguete.check(again, seen) == (False, "Doppelbild")
    second = tmp_path / "2.png"
    other.save(second)
    assert bildguete.check(second, seen)[0]


def test_verify_photo_uses_clip_probability(tmp_path, monkeypatch):
    path = tmp_path / "p.png"
    noisy().save(path)
    monkeypatch.setattr(media.bildcheck, "available", lambda: True)
    monkeypatch.setattr(media.bildcheck, "probabilities", lambda motif, imgs: [0.05])
    ok, why = media.verify_photo(greenland(), path)
    assert not ok and "Bildprüfung" in why
    monkeypatch.setattr(media.bildcheck, "probabilities", lambda motif, imgs: [0.8])
    assert media.verify_photo(greenland(), path)[0]


def test_rank_by_image_drops_obviously_wrong_clips(monkeypatch):
    clips = [media.Clip("u1", 1280, 5, "c", "Pixabay", key="a", preview=("x",)),
             media.Clip("u2", 1280, 5, "c", "Pixabay", key="b", preview=("y",))]
    monkeypatch.setattr(media.bildcheck, "available", lambda: True)
    monkeypatch.setattr(media.bildcheck, "judge", lambda motif, frames: (True, 0.04 if frames == ["bad"] else 0.7))
    monkeypatch.setattr(media.net, "download", lambda *a, **k: "unused")
    scores = iter([0.04, 0.7])
    monkeypatch.setattr(media.bildcheck, "judge", lambda motif, frames: (True, next(scores)))
    monkeypatch.setattr("PIL.Image.open", lambda p: Image.new("RGB", (4, 4)))
    ranked = media.rank_by_image(greenland(), clips)
    assert [c.key for c in ranked] == ["b"]


def test_hook_lead_and_ken_burns():
    from cudi_video.erklaer.render import HOOK_LEAD, build_jobs
    from cudi_video.render.video import LEAD

    assert LEAD["intro"] <= 0.15 and HOOK_LEAD <= 0.15


def test_still_photo_always_moves(tmp_path):
    """Standbild: in jedem 3-Sekunden-Fenster ändert sich das Bild (Ken Burns, kein Stillstand)."""
    from cudi_video.render.scenes import make_scene

    path = tmp_path / "p.png"
    noisy((1600, 1200)).save(path)
    item = {"rank": 1, "name": "Turm A", "si_value": 828.0, "unit": "Q11573", "wanted": "m", "value_label": "Höhe",
            "as_of": None, "extras": [], "image_path": str(path), "image_kind": "photo", "credit_short": None,
            "icon": "building", "n_sources": 3, "compare_chip": None}
    job = {"index": 1, "kind": "item", "lang": "de", "title": "T", "text": "Platz 1: Turm A.", "words": [], "lead": 0.4,
           "frames": 240, "duration": 8.0, "fps": 30, "n_items": 3, "max_display": 828.0, "channel": "", "out": "x",
           "item": item}
    scene = make_scene(job)
    for start in (0.5, 2.5, 4.5):
        a = np.asarray(scene._card(start).convert("RGB"), dtype=np.int16)
        b = np.asarray(scene._card(start + 1.0).convert("RGB"), dtype=np.int16)
        assert np.abs(a - b).mean() > 0.3, start


def test_reportage_scene_never_empty_and_text_size(tmp_path):
    from pathlib import Path

    from cudi_video.erklaer.render import build_jobs
    from cudi_video.erklaer.skript import validate_script
    from cudi_video.render import reportage as R
    from cudi_video.render.scenes import make_scene
    from cudi_video.render.theme import H, W

    img = tmp_path / "p.jpg"
    noisy().save(img)
    text = "Am 20. Juli 1969 betrat Neil Armstrong als erster Mensch den Mond, wie zwei Quellen übereinstimmend berichten."
    visuals = [
        {"typ": "reportage", "bild": str(img), "bild_art": "image", "ort": "Houston", "datum": "20. Juli 1969", "jahr": 1969,
         "jahre": [1961, 1969], "quelle": "NASA · Wikipedia", "credit": "Jemand (CC BY 2.0)"},
        {"typ": "reportage", "bild": None, "datum": "1969", "jahr": 1969, "jahre": [1961, 1969], "quelle": "NASA"},
        {"typ": "reportage", "bild": None, "zitat": "Ein belegtes Zitat der Quelle", "quelle": "NASA"},
        {"typ": "reportage", "bild": None, "quelle": "NASA"},                      # nichts bekannt: trotzdem nicht leer
    ]
    script = validate_script({"id": "x", "titel": "t", "szenen": [{"text": text, "visual": v} for v in visuals]})
    voiced = [(Path("x.wav"), [{"text": w, "start": 0.2 * i, "end": 0.2 * i + 0.15} for i, w in enumerate(text.split())], 4.0)
              for _ in visuals]
    jobs = build_jobs(script, voiced, Path("/tmp/none"))
    assert jobs[0]["kind"] == "reportage" and jobs[0]["lead"] <= 0.15
    assert R.TEXT_MIN >= 54
    for job in jobs:
        scene = make_scene(job)
        assert scene.sentence.regular.size >= 54                          # gut lesbarer Haupttext
        frame = scene.frame(job["duration"] * 0.6).convert("RGB")
        assert frame.size == (W, H)
        media_area = np.asarray(frame.crop((0, 150, W, R.MEDIA_H - 100)), dtype=np.float32)
        assert media_area.mean() > 25                                       # Bildbereich nie leer/schwarz
