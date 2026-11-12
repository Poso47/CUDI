"""Notbetrieb über GitHub-Issues: JSON-Auftrag prüfen (auftrag.py), Kommentar (notbetrieb.py), Issue-Link der App-Seite."""

import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / ".github" / "scripts"
sys.path.insert(0, str(SCRIPTS))


def _load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f"{name}.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


auftrag = _load("auftrag")
notbetrieb = _load("notbetrieb")
PRESETS = {"groesste-seen", "hoechste-berge"}


def body(order: dict) -> str:
    return f"cudi-auftrag\n\nText\n\n```json\n{json.dumps(order)}\n```\n"


def test_extract_json_finds_order_block():
    assert auftrag.extract_json(body({"art": "story", "stimmung": "creepy"})) == {"art": "story", "stimmung": "creepy"}
    assert auftrag.extract_json("cudi-auftrag\nArt: Ranking") is None
    assert auftrag.extract_json("```text\nnix\n```\n```json\n[1]\n```") is None
    with pytest.raises(ValueError):
        auftrag.extract_json("```json\n{kaputt\n```")


def test_json_order_ranking_preset_and_free_topic():
    order = auftrag.build_json_order({"art": "ranking", "vorlage": "groesste-seen", "plaetze": 5, "sprachen": ["de"]},
                                     42, PRESETS)
    assert order["id"] == "gh0042" and order["vorlage"] == "groesste-seen" and order["plaetze"] == 5
    free = auftrag.build_json_order({"art": "ranking", "thema": "die größten Wüsten", "format": "karte"}, 7, PRESETS)
    assert free["thema"] == "die größten Wüsten" and free["format"] == "karte" and free["plaetze"] == 10
    with pytest.raises(ValueError, match="Vorlage"):
        auftrag.build_json_order({"art": "ranking", "vorlage": "gibtsnicht"}, 1, PRESETS)
    with pytest.raises(ValueError):
        auftrag.build_json_order({"art": "ranking", "thema": "x", "plaetze": 99}, 1, PRESETS)
    with pytest.raises(ValueError):
        auftrag.build_json_order({"art": "ranking", "thema": "x", "format": "unbekannt"}, 1, PRESETS)


def test_json_order_story_and_limits():
    story = auftrag.build_json_order({"art": "story", "stimmung": "creepy", "sprache": "de", "laenge": "kurz"}, 9, PRESETS)
    assert story["art"] == "story" and story["stimmung"] == "creepy" and story["laenge"] == "kurz"
    with pytest.raises(ValueError):
        auftrag.build_json_order({"art": "story"}, 9, PRESETS)                     # weder Stimmung noch Wunsch
    clip = auftrag.build_json_order({"art": "clip", "quelle": "https://example.com/v", "bestaetigt_erlaubnis": True}, 9, PRESETS)
    assert clip["art"] == "clip" and clip["bestaetigt_erlaubnis"] is True                 # Clips gehen jetzt auch im Notbetrieb
    direct = auftrag.build_json_order({"art": "story", "stimmung": "creepy", "schritt": "skelett"}, 9, PRESETS)
    assert direct["schritt"] == ""                                                         # Skelett-Schritt = direkt Video
    with pytest.raises(ValueError, match="Verweis"):
        auftrag.build_json_order({"art": "story", "stimmung": "creepy", "schritt": "hochladen",
                                  "hochladen": {"ziel": "youtube", "sichtbarkeit": "privat"}}, 9, PRESETS)
    assert auftrag.build_json_order({"art": "ranking", "vorlage": "groesste-seen", "id": "../x"}, 1, PRESETS)["id"] == "gh0001"


def test_upload_goes_out_directly_unless_freigabe_given():
    raw = {"art": "story", "stimmung": "creepy", "hochladen": {"ziel": "youtube", "sichtbarkeit": "privat"}}
    assert auftrag.build_json_order(raw, 3, PRESETS)["hochladen"]["freigabe"] is False
    raw["hochladen"]["freigabe"] = True
    assert auftrag.build_json_order(raw, 3, PRESETS)["hochladen"]["freigabe"] is True
    with pytest.raises(ValueError):
        auftrag.build_json_order({**raw, "hochladen": {"ziel": "myspace"}}, 3, PRESETS)
    assert auftrag.build_json_order({"art": "story", "stimmung": "funny"}, 3, PRESETS)["hochladen"] is None


def test_summary_line_for_notbetrieb():
    order = auftrag.build_json_order({"art": "ranking", "thema": "Wüsten", "hochladen": {"ziel": "tiktok"}}, 5, PRESETS)
    line = auftrag.summary_line("notbetrieb.yml", {"auftrag": json.dumps(order)})
    assert "Wüsten" in line and "tiktok" in line


def test_comment_success_has_texts_upload_and_review(monkeypatch):
    monkeypatch.setenv("CUDI_YT_REFRESH_TOKEN", "geheimer-token-123")
    data = {"ok": True, "titel": "Die @größten Seen", "hinweise": ["Nur von Wikipedia bestätigt: X", "YouTube: Bereit"],
            "videos": [{"key": "de", "dauer": 61.4, "youtube": "Titel\n\nText #seen", "tiktok": "Kurz #fyp"}],
            "hochgeladen": [{"ziel": "youtube", "ok": True, "url": "https://youtu.be/abc", "sichtbarkeit": "privat"},
                            {"ziel": "tiktok", "ok": False, "fehler": "Token geheimer-token-123 abgelehnt"}],
            "pruefbericht": "# Bericht\n- Quelle A"}
    text = notbetrieb.comment_text(data, "https://github.com/x/actions/runs/1", "https://github.com/x/artifacts/9")
    assert "## ✅ Fertig" in text and "@​größten" in text
    assert "Titel\n\nText #seen" in text and "Kurz #fyp" in text and "DE · 61 s" in text
    assert "https://youtu.be/abc" in text and "TikTok: Hochladen fehlgeschlagen" in text
    assert "geheimer-token-123" not in text and "***" in text
    assert "Nur von Wikipedia" in text and "Bereit" not in text
    assert "Prüfbericht (Kurzform)" in text and "Quelle A" in text
    assert "https://github.com/x/artifacts/9" in text and "actions/runs/1" in text


def test_comment_failure_gives_reason():
    text = notbetrieb.comment_text({"ok": False, "fehler": "LLM nicht erreichbar"}, "https://run")
    assert "❌" in text and "LLM nicht erreichbar" in text and "https://run" in text
    assert "❌" in notbetrieb.comment_text(None, "https://run")


# --------------------------------------------------------------------------- Issue-Link der App-Seite (JS per node)

NODE = shutil.which("node")


def _js_links(orders: list) -> list[str]:
    html = (ROOT / "docs" / "cudi-app-artefakt.html").read_text("utf-8")
    code = html.split("/* nb-issue:start */")[1].split("/* nb-issue:end */")[0]
    script = code + "\nconst orders = JSON.parse(process.argv[1]);\nconsole.log(JSON.stringify(orders.map(nbIssueLink)));"
    res = subprocess.run([NODE, "-e", script, json.dumps(orders)], capture_output=True, text=True, check=True)
    return json.loads(res.stdout)


@pytest.mark.skipif(not NODE, reason="node fehlt")
def test_page_issue_link_roundtrips_into_auftrag_py():
    orders = [
        {"art": "ranking", "thema": "die größten Wüsten", "vorlage": "", "plaetze": 10, "sprachen": ["de", "en"],
         "format": "karte", "streng": False, "schritt": ""},
        {"art": "ranking", "vorlage": "groesste-seen", "plaetze": 5, "sprachen": ["de"]},
        {"art": "story", "wunsch": "Anruf & \"Nachbar\" #1", "stimmung": "creepy", "sprache": "de", "laenge": "kurz",
         "schritt": "skelett", "hochladen": {"ziel": "youtube", "sichtbarkeit": "privat"}},
        {"art": "fakten", "thema": "Haie", "plaetze": 5, "sprache": "de", "streng": True},
        {"art": "ranking", "vorlage": "groesste-seen", "schritt": "bearbeiten"},
    ]
    links = _js_links(orders)
    assert links[4] == ""                                   # Bearbeiten geht nur mit Claude
    for link, order in zip(links[:4], orders[:4]):
        assert link.startswith("https://github.com/Poso47/CUDI/issues/new?") and len(link) < 6000
        query = parse_qs(urlparse(link).query)
        assert query["title"][0].startswith("CUDI-Auftrag (Notbetrieb): ")
        text = query["body"][0]
        assert "cudi-auftrag" in text and "Submit new issue" in text
        raw = auftrag.extract_json(text)
        parsed = auftrag.build_json_order(raw, 11, {"groesste-seen"})
        assert parsed["art"] == order["art"] and parsed.get("schritt", "") == ""
        assert (parsed.get("thema") or parsed.get("vorlage") or parsed.get("wunsch")) == (
            order.get("thema") or order.get("vorlage") or order.get("wunsch"))
    story = auftrag.build_json_order(auftrag.extract_json(parse_qs(urlparse(links[2]).query)["body"][0]), 1, set())
    assert story["hochladen"]["freigabe"] is False


@pytest.mark.skipif(not NODE, reason="node fehlt")
def test_page_issue_link_drops_prefs_when_too_long():
    prefs = {"gut": ["ä" * 150] * 8, "schlecht": ["ö" * 150] * 8}
    link = _js_links([{"art": "story", "stimmung": "funny", "vorlieben": prefs}])[0]
    assert link and len(link) < 6000 and "vorlieben" not in parse_qs(urlparse(link).query)["body"][0]


# --------------------------------------------------------------------------- Workflows

def test_workflows_are_valid_and_cloud_app_is_manual_only():
    for name in ("auftrag", "notbetrieb", "cloud-app"):
        yaml.safe_load((ROOT / ".github" / "workflows" / f"{name}.yml").read_text("utf-8"))
    cloud = yaml.safe_load((ROOT / ".github" / "workflows" / "cloud-app.yml").read_text("utf-8"))
    assert list(cloud[True]) == ["workflow_dispatch"]                        # „on“ wird von YAML zu True
    nb = yaml.safe_load((ROOT / ".github" / "workflows" / "notbetrieb.yml").read_text("utf-8"))
    assert set(nb[True]["workflow_dispatch"]["inputs"]) == {"auftrag", "issue"}


def test_deploy_space_skips_without_token_and_on_402(monkeypatch, capsys):
    deploy = _load("deploy_space")
    monkeypatch.delenv("HF_TOKEN", raising=False)
    assert deploy.main() == 0
    assert "PRO" in capsys.readouterr().out

    def boom():
        raise RuntimeError("402 Client Error: Payment Required")

    monkeypatch.setattr(deploy, "_deploy", boom)
    assert deploy.main() == 0
    assert "Hugging Face verlangt PRO" in capsys.readouterr().out
    monkeypatch.setattr(deploy, "_deploy", lambda: (_ for _ in ()).throw(RuntimeError("anderer Fehler")))
    with pytest.raises(RuntimeError):
        deploy.main()
