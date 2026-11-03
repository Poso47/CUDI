"""Cloud-Aufträge der CUDI-App-Seite: Issue lesen, prüfen, starten – und das Ergebnis melden."""

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / ".github" / "scripts"))

import auftrag  # noqa: E402
import report_issue  # noqa: E402

PRESETS = {"hoechste-gebaeude", "groesste-laender"}

RANKING_BODY = """<!-- cudi-auftrag -->
Art: Ranking
Vorlage: hoechste-gebaeude
Thema:
Sprachen: de,en
Plätze: 10
Streng: nein
Nur Skript: ja

Einfach absenden – CUDI startet automatisch. Hinweis: dauert etwa 15 Minuten."""

STORY_BODY = """<!-- cudi-auftrag -->
Art: Story
Stimmung: creepy
Wunsch: gruselige Story: Stalker im Wald
Sprache: de
Länge: 3min
Bilder: videos
Entschärfen: ja
"""


def test_ranking_order_from_issue():
    workflow, inputs = auftrag.build_order(auftrag.parse_body(RANKING_BODY), PRESETS)
    assert workflow == "video.yml"
    assert inputs == {"preset": "hoechste-gebaeude", "langs": "de,en", "count": "10",
                      "streng": "false", "nur_skript": "true"}


def test_story_order_keeps_colons_in_wish():
    workflow, inputs = auftrag.build_order(auftrag.parse_body(STORY_BODY), PRESETS)
    assert workflow == "story.yml"
    assert inputs == {"wunsch": "gruselige Story: Stalker im Wald", "stimmung": "creepy", "sprache": "de",
                      "laenge": "3min", "bilder": "videos", "entschaerfen": "true"}


def test_free_topic_wins_and_german_labels_work():
    fields = auftrag.parse_body("Art: Ranking\nThema: die höchsten Berge in Europa\nSprachen: Deutsch en\nPlätze: 5")
    _, inputs = auftrag.build_order(fields, PRESETS)
    assert inputs["preset"] == "die höchsten Berge in Europa" and inputs["langs"] == "en" and inputs["count"] == "5"
    fields = auftrag.parse_body("Art: Story\nStimmung: Gruselig\nLänge: Kurz (bis 1 Minute)\nBilder: KI-Bilder\nSprache: Englisch")
    _, inputs = auftrag.build_order(fields, PRESETS)
    assert (inputs["stimmung"], inputs["laenge"], inputs["bilder"], inputs["sprache"]) == ("creepy", "kurz", "images", "en")


@pytest.mark.parametrize("body, reason", [
    ("Art: Ranking\nVorlage: gibt-es-nicht", "gibt es nicht"),
    ("Art: Ranking\nVorlage: hoechste-gebaeude\nPlätze: 99", "3 bis 20"),
    ("Art: Ranking\nVorlage: hoechste-gebaeude\nSprachen: fr", "Sprache"),
    ("Art: Story\nStimmung: auto", "Stimmung antippen"),
    ("Art: Story\nStimmung: traurig", "kenne ich nicht"),
    ("Art: Story\nStimmung: creepy\nEntschärfen: vielleicht", "ja oder nein"),
    ("Art: Kochrezept", "Unbekannte Art"),
])
def test_invalid_orders_are_explained(body, reason):
    with pytest.raises(ValueError, match=reason):
        auftrag.build_order(auftrag.parse_body(body), PRESETS)


def test_control_characters_and_length_are_cleaned():
    fields = {"art": "story", "wunsch": "a\x00b\x1b" + "x" * 500, "stimmung": "creepy"}
    _, inputs = auftrag.build_order(fields, PRESETS)
    assert "\x00" not in inputs["wunsch"] and "\x1b" not in inputs["wunsch"] and len(inputs["wunsch"]) == 300


@pytest.mark.parametrize("association, login, ok", [
    ("OWNER", "Poso47", True), ("COLLABORATOR", "freund", True), ("NONE", "Poso47", True),
    ("NONE", "fremder", False), ("CONTRIBUTOR", "fremder", False),
])
def test_only_owner_and_collaborators_may_order(association, login, ok):
    event = {"issue": {"author_association": association, "user": {"login": login}},
             "repository": {"owner": {"login": "Poso47"}}}
    assert auftrag.allowed(event) is ok


def test_real_presets_are_found():
    assert {"hoechste-gebaeude", "meiste-einwohner", "tiefste-seen"} <= auftrag.presets()


def test_summary_line_reads_naturally():
    line = auftrag.summary_line("video.yml", {"preset": "hoechste-gebaeude", "langs": "de,en", "count": "10",
                                              "streng": "true", "nur_skript": "false"})
    assert line == "Ranking **hoechste-gebaeude** · Sprachen de,en · Top 10 · streng"
    line = auftrag.summary_line("story.yml", {"wunsch": "", "stimmung": "funny", "sprache": "en",
                                              "laenge": "kurz", "bilder": "images", "entschaerfen": "true"})
    assert line == "Story **funny** · en · kurz · Bilder: images"


# --------------------------------------------------------------------------- Ergebnis melden

def test_asset_names_are_unique_and_url_safe():
    assert report_issue.asset_name("12", "höchste gebäude_de.mp4") == "12_h-chste-geb-ude_de.mp4"
    assert report_issue.asset_name("", "story_x_de.mp4") == "story_x_de.mp4"


def test_fence_survives_backticks_in_text():
    block = report_issue.fenced("Code: ```x```")
    assert block.startswith("````text\n") and block.endswith("\n````")


def _data(**kw):
    data = {"ok": True, "title": "Die 10 höchsten Gebäude der Welt", "warnings": ["Bitte Platz 3 prüfen."],
            "review": "# Prüfbericht\n- Burj Khalifa: bestätigt", "error": "",
            "videos": [{"key": "de", "file": "hoechste-gebaeude_de.mp4", "cover": "c.jpg", "duration": 155.5,
                        "youtube": "Titel\n\nBeschreibung", "tiktok": "Kurztext #ranking"}]}
    data.update(kw)
    return data


def test_success_comment_has_download_texts_and_review():
    links = {"hoechste-gebaeude_de.mp4": {"video": "https://x/v.mp4", "cover": "https://x/c.jpg"}}
    text = report_issue.comment_text(_data(), links, "https://run", "https://rel")
    assert text.startswith("## ✅ Fertig: Die 10 höchsten Gebäude der Welt")
    assert "### 🎬 DE · 156 s" in text and "[⬇️ **Video herunterladen**](https://x/v.mp4)" in text
    assert "```text\nKurztext #ranking\n```" in text and "<summary><b>YouTube-Titel und Beschreibung DE</b>" in text
    assert "- Bitte Platz 3 prüfen." in text and "Prüfbericht mit Quellen" in text
    assert text.rstrip().endswith("Alle Videos: https://rel · Lauf: https://run")


def test_comment_without_upload_points_to_zip_and_story_parts_keep_case():
    data = _data(videos=[{"key": "en · Teil 1", "file": "s_en_teil1.mp4", "duration": 107.4, "youtube": "", "tiktok": ""}])
    text = report_issue.comment_text(data, {}, "https://run", "https://rel")
    assert "### 🎬 EN · Teil 1 · 107 s" in text and "Video im Lauf als ZIP: https://run" in text


def test_script_only_and_failure_comments():
    text = report_issue.comment_text(_data(videos=[]), {}, "https://run", "https://rel")
    assert text.startswith("## ✅ Skript und Prüfbericht fertig") and "nur das Skript" in text
    text = report_issue.comment_text({"ok": False, "error": "RuntimeError: Keine Daten gefunden"}, {}, "https://run", "")
    assert text.startswith("## ❌ Hat leider nicht geklappt") and "Keine Daten gefunden" in text and "https://run" in text


def test_overlong_review_is_left_out_but_downloads_stay():
    links = {"hoechste-gebaeude_de.mp4": {"video": "https://x/v.mp4"}}
    text = report_issue.comment_text(_data(review="x" * 200_000), links, "https://run", "https://rel")
    assert len(text) <= report_issue.MAX_COMMENT and "https://x/v.mp4" in text and "Lauf: https://run" in text


def test_mentions_in_story_texts_do_not_ping_people():
    data = _data(title="Wer ist @jemand?", warnings=["Story von @autor prüfen"], review="Danke an @helfer")
    text = report_issue.comment_text(data, {}, "https://run", "https://rel")
    assert "@jemand" not in text and "@autor" not in text and "@helfer" not in text
    assert "@\u200bjemand" in text and "@\u200bhelfer" in text
