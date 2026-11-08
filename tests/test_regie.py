"""Regie & Psychologie: Checkliste/Scores, Hook-Auswahl ohne Spoiler, Wahrheit hat Vorrang, Wissens-Sammler, natürlicher Klang."""

import json
from datetime import date
from pathlib import Path

import pytest
import yaml

from cudi_video import handoff, regie, tts, wahrheit
from cudi_video.firma import common, wissen
from cudi_video.script import build_script
from tests.test_wahrheit import make_research, make_spec

HEUTE = date(2026, 11, 8)
TOPS = ["Turm Alpha"]


def script_de():
    return build_script(make_spec(), make_research(), "de", use_llm=False)


# --------------------------------------------------------------------------- Checkliste und Scores

def test_checkliste_hat_alle_basis_kriterien_mit_score_und_begruendung():
    s = script_de()
    result = regie.bewerte([(g.kind, g.text) for g in s.segments], "de", "ranking", TOPS)
    ids = {k["id"] for k in result["kriterien"]}
    assert {"hook", "neugier", "musterbruch", "fortschritt", "payoff", "ansprache", "rhythmus", "kernaussage", "loop",
            "natuerlich", "sprechbar"} <= ids
    assert all(0 <= k["score"] <= 1 and k["begruendung"] and k["basis"] and k["name"] for k in result["kriterien"])
    assert 0 < result["gesamt"] <= 1


def test_steifes_skript_schlechter_als_lebendiges():
    steif = [("intro", "Heute betrachten wir die Gebäudehöhen verschiedener Bauwerke in einer systematischen Übersicht, "
                       "welche zudem außerdem weitere Informationen bezüglich der Rangfolge enthält."),
             ("item", "Platz 1: Turm Alpha. Außerdem ist die Höhe hierbei bemerkenswert. Des Weiteren wurde der Turm gebaut."),
             ("outro", "Das war die Übersicht.")]
    lebendig = [("intro", "Wetten, du kennst Platz eins nicht? Die Auflösung kommt am Ende."),
                ("item", "Platz 3: Turm Gamma. Stell dir vor: 632 Meter! Aber es geht noch höher."),
                ("item", "Platz 2: Turm Beta. Nur noch 149 Meter bis zur Spitze. Merk dir diese Zahl."),
                ("outro", "Heute gelernt: Turm Alpha ist vorn. Welcher Turm überrascht dich? Schreib es in die Kommentare!")]
    a, b = regie.bewerte(steif, "de", "ranking", TOPS), regie.bewerte(lebendig, "de", "ranking", TOPS)
    assert b["gesamt"] > a["gesamt"] + 0.2
    by = {k["id"]: k["score"] for k in b["kriterien"]}
    assert by["hook"] == 1.0 and by["natuerlich"] >= 0.9 and by["payoff"] == 1.0


def test_englisch_kontraktionen_werden_belohnt():
    flat = [("intro", "Do not miss this. It is the tallest.")] + [("item", "Number 2 is a tower. It is high. It is old.")] * 8
    live = [("intro", "Don't miss this. It's the tallest.")] + [("item", "Number 2 is a tower. It's high, isn't it? It's old.")] * 8
    na = {k["id"]: k["score"] for k in regie.bewerte(flat, "en", "ranking")["kriterien"]}["natuerlich"]
    nb = {k["id"]: k["score"] for k in regie.bewerte(live, "en", "ranking")["kriterien"]}["natuerlich"]
    assert nb > na


# --------------------------------------------------------------------------- Hook-Auswahl

def test_hook_auswahl_nimmt_neugier_ohne_spoiler():
    alt = "Die höchsten Türme! Platz eins schafft 828 Meter – rate mal, wer das ist."
    ctx = "Die höchsten Türme Turm Alpha Turm Beta 828 679 632"
    kandidaten = ["Turm Alpha ist der höchste von allen – 828 Meter!",                     # Spoiler
                  "Wetten, du kennst die Nummer eins nicht? 828 Meter – die Auflösung kommt am Ende.",
                  "Hier sind Türme."]                                                       # langweilig
    hook, why = regie.waehle_hook(kandidaten, alt, "de", TOPS, ctx)
    assert hook.startswith("Wetten, du kennst") and "Alpha" not in hook and "->" in why
    assert regie.hook_score(kandidaten[0], "de", TOPS) == -1.0                              # Spoiler ist unzulässig


def test_hook_auswahl_lehnt_luege_clickbait_und_schwache_kandidaten_ab():
    alt = "Wetten, du kennst Platz eins nicht? Die Auflösung kommt am Ende."
    ctx = alt + " 828 Meter"
    hook, why = regie.waehle_hook(["Unglaublich, das wirst du nie glauben!", "Platz eins hat 9000 Meter – rate mal, wer?",
                                   "Hier sind Türme."], alt, "de", TOPS, ctx)
    assert hook is None and why


# --------------------------------------------------------------------------- Änderungen und Wahrheit

def test_pruefe_aenderung_zahlen_namen_wertung():
    alt = "Platz 1: Turm Alpha. Er ist 828 Meter hoch."
    ctx = alt
    ok = "Platz 1: Turm Alpha. Rund 830 Meter hoch – stell dir das vor."
    assert regie.pruefe_aenderung(alt, ok, ctx, "de") is None
    assert regie.pruefe_aenderung(alt, "Platz 1: Turm Alpha. Er ist 900 Meter hoch.", ctx, "de") == "neue Zahl"
    assert regie.pruefe_aenderung(alt, "Platz 1: Turm Alpha. Er ist hoch, mein Freund.", ctx, "de") == "Zahl entfallen"
    assert regie.pruefe_aenderung(alt, "Platz 2: Turm Alpha. Er ist 828 Meter hoch.", ctx, "de",
                                  beginnt_mit="Platz 1: Turm Alpha.") == "Platzsatz geändert"
    assert regie.pruefe_aenderung(alt, "Platz 1: Turm Alpha. Er ist 828 Meter hoch. Jessica liebt ihn.", ctx, "de")
    assert regie.pruefe_aenderung(alt, "Platz 1: Turm Alpha. Er ist 828 Meter hoch und krass unfassbar.", ctx, "de")


def _antwort(monkeypatch, answer):
    monkeypatch.setattr(handoff, "active", lambda: True)
    monkeypatch.setattr(handoff, "enabled", lambda: True)
    monkeypatch.setattr(handoff, "request", lambda task, instructions, data: answer if task == "regie" else None)


def test_regie_uebernimmt_gepruefte_aenderungen_und_bewertet_nachher(monkeypatch):
    spec, research = make_spec(), make_research()
    s = script_de()
    p = wahrheit.Pruefer(spec, research, heute=HEUTE)
    s.segments[0].text = "Die höchsten Türme der Welt in einer Übersicht."            # schwacher Einstieg
    item = next(g for g in s.segments if g.rank == 3)
    first = item.text.split(". ")[0] + "."
    _antwort(monkeypatch, {"de": {
        "hook_kandidaten": ["Wetten, du kennst die Nummer eins nicht? Die Auflösung kommt am Ende!", "x", "y"],
        "abschnitte": {str(s.segments.index(item)): f"{first} Stell dir vor: 632 Meter – und es geht noch höher. Eröffnet 2010."},
        "begruendung": {"hook": "Frage statt Aufzählung"}}})
    block = regie.verbessere(spec, research, [s], p)
    assert block["quelle"] == "Claude" and block["nachher"]["de"]["gesamt"] >= block["vorher"]["de"]["gesamt"]
    assert s.segments[0].text.startswith("Wetten, du kennst") and "Stell dir vor" in item.text
    assert {c["ort"] for c in block["aenderungen"]} == {"Hook", "Platz 3"}
    assert "Regie & Psychologie" in regie.review_section(block)


def test_wahrheitsbefund_verwirft_aenderung_alter_text_bleibt(monkeypatch):
    spec, research = make_spec(), make_research()
    s = script_de()
    p = wahrheit.Pruefer(spec, research, heute=HEUTE)
    idx = next(i for i, g in enumerate(s.segments) if g.rank == 2)
    old = s.segments[idx].text
    first = old.split(". ")[0] + "."
    bad = f"{first} Das ist der einzige Turm dieser Art, und {old.split('. ', 1)[1]}"
    monkeypatch.setattr(regie, "pruefe_aenderung", lambda *a, **k: None)         # erste Schicht aus: die Wahrheits-Prüfung entscheidet
    _antwort(monkeypatch, {"de": {"hook_kandidaten": [], "abschnitte": {str(idx): bad}}})
    block = regie.verbessere(spec, research, [s], p)
    assert s.segments[idx].text == old
    assert any("Wahrheits-Prüfung" in v["grund"] and v["ort"] == "Platz 2" for v in block["verworfen"])
    assert not any(c["ort"] == "Platz 2" for c in block["aenderungen"])


def test_ohne_modell_nur_bewertung_nichts_umgeschrieben(monkeypatch):
    monkeypatch.setattr(handoff, "active", lambda: False)
    spec, research = make_spec(), make_research()
    s = script_de()
    before = [g.text for g in s.segments]
    block = regie.verbessere(spec, research, [s], wahrheit.Pruefer(spec, research, heute=HEUTE))
    assert [g.text for g in s.segments] == before and block["aenderungen"] == [] and "nur bewertet" in block["hinweis"]
    assert block["vorher"]["de"]["kriterien"]


def test_regie_ist_genau_eine_schreibrunde(tmp_path, monkeypatch):
    monkeypatch.setenv(handoff.ENV, "1")
    monkeypatch.setenv(handoff.DIR_ENV, str(tmp_path))
    spec, research = make_spec(), make_research()
    s = script_de()
    with pytest.raises(handoff.WritingNeeded) as need:
        regie.verbessere(spec, research, [s], wahrheit.Pruefer(spec, research, heute=HEUTE))
    task = json.loads(need.value.path.read_text("utf-8"))
    assert need.value.path.name == "schreiben_regie.json" and task["daten"]["de"]["nicht_verraten"] == ["Turm Alpha"]
    assert any(c["herkunft"] == "Basis" for c in task["daten"]["de"]["checkliste"])
    assert "hook_kandidaten" in task["anleitung"] and "ABSOLUTER VORRANG" in task["anleitung"]


def test_story_regie_prueft_wie_das_lektorat(monkeypatch):
    _antwort(monkeypatch, {"en": {
        "hook_kandidaten": ["Bet you can't guess what moved between the trees? The answer comes at the end.", "a", "b"],
        "abschnitte": {"1": "I drove to the park every night, you know, for 2 weeks.",
                       "2": "The woods were silent and empty, said Jessica."}}})
    scenes = ["I drove to the park every night for 2 weeks.", "The woods were silent and empty.", "Then I saw a light."]
    hook, new, block = regie.verbessere_story("The light", "", scenes, "en", "creepy", " ".join(scenes) + " The light")
    assert hook.startswith("Bet you can't guess") and "you know" in new[0] and new[1] == scenes[1]
    assert any(v["ort"] == "Szene 2" for v in block["verworfen"]) and block["nachher"]["en"]["gesamt"] >= 0


# --------------------------------------------------------------------------- Wissens-Sammler

RSS = b"""<rss><channel><item><title>New retention tools for Shorts creators</title>
<description>&lt;p&gt;YouTube Shorts creators now see how many viewers stay past the first seconds.&lt;/p&gt;</description>
<link>https://blog.youtube/news/shorts-retention</link><pubDate>Tue, 03 Nov 2026 10:00:00 GMT</pubDate></item>
<item><title>Company picnic</title><description>Food</description><link>https://blog.youtube/picnic</link></item></channel></rss>"""
PMC = {"resultList": {"result": [{"title": "Attention in short video", "abstractText": "Viewers decide within 3 seconds.",
                                  "pmcid": "PMC1", "id": "1", "source": "MED", "journalTitle": "J Media",
                                  "firstPublicationDate": "2026-05-02"}]}}


class Resp:
    def __init__(self, content=b"", data=None):
        self.content, self._data = content, data

    def json(self):
        return self._data


@pytest.fixture
def daten(tmp_path, monkeypatch):
    monkeypatch.setattr(common, "DATA_DIR", tmp_path / "firma_daten")
    monkeypatch.setattr("cudi_video.config.LLM_BASE_URL", "http://llm")
    monkeypatch.setattr("cudi_video.config.LLM_MODEL", "m")
    return tmp_path


def test_wissen_sammler_mit_gemockten_feeds(daten, monkeypatch):
    def fake_fetch(url, **kw):
        if "europepmc" in url:
            return Resp(data=PMC)
        if url.startswith("https://blog.youtube/rss"):
            return Resp(RSS)
        raise common.requests.RequestException("down")                       # TikTok & zweiter Feed fallen aus

    monkeypatch.setattr(wissen, "fetch", fake_fetch)
    seen = {}

    def fake_chat(system, user, **kw):
        seen["user"] = user
        return {"regeln": [
            {"id": "q0", "regel": "Zeige früh, wie viele Zuschauer bleiben, und baue die ersten Sekunden danach.",
             "beleg": "see how many viewers stay past the first seconds"},
            {"id": "q1", "regel": "Zuschauer entscheiden innerhalb von 3 Sekunden, ob sie bleiben.",
             "beleg": "Viewers decide within 3 seconds"},
            {"id": "q1", "regel": "Zuschauer bleiben im Schnitt 99 Prozent länger.",
             "beleg": "Viewers decide within 3 seconds"},                                              # Zahl nicht im Auszug
            {"id": "q1", "regel": "Zuschauer lieben lange Videos in jedem Fall und immer.",
             "beleg": "Viewers love very long videos"},                                                 # Beleg steht nicht in der Quelle
            {"id": "q9", "regel": "Eine Regel ohne vorhandene Quelle sollte hier nie ankommen.",
             "beleg": "irgendein Satz"}]}                                                               # Quelle gibt es nicht

    monkeypatch.setattr("cudi_video.llm.chat_json", fake_chat)
    data = wissen.run()
    assert "Company picnic" not in seen["user"]                                  # nur passende Quellen
    texts = [r["regel"] for r in data["regeln"]]
    assert len(texts) == 2 and not any("99" in t or "ohne vorhandene" in t for t in texts)
    for r in data["regeln"]:
        assert r["link"].startswith("https://") and r["datum"] and r["quelle"]       # jede Regel mit Quelle + Datum
    assert {r["art"] for r in data["regeln"]} == {"offiziell", "studie"}
    assert len(data["basis"]) == len(wissen.BASIS) >= 10 and all(b["art"] == "basis" for b in data["basis"])
    assert common.read_json("status.json")["mitarbeiter"]["wissen"]["ergebnis"] == "ok"
    assert regie.lernstoff()[0]["quelle"]                                         # die Regie liest die Regeln


def test_wissen_ohne_modell_behaelt_alte_regeln_und_erfindet_nichts(daten, monkeypatch):
    common.write_json("wissen.json", {"erzeugt": "x", "regeln": [
        {"regel": "Alte Regel mit Quelle und Datum.", "quelle": "Q", "titel": "t", "link": "https://x",
         "datum": date.today().isoformat(), "art": "offiziell"}]})
    monkeypatch.setattr("cudi_video.config.LLM_BASE_URL", "")
    monkeypatch.setattr(wissen, "fetch", lambda url, **kw: Resp(RSS) if "blog.youtube/rss" in url else Resp(data=PMC))
    data = wissen.run()
    assert [r["regel"] for r in data["regeln"]] == ["Alte Regel mit Quelle und Datum."] and data["neue_regeln"] == 0
    assert any("Kein Sprachmodell" in h for h in data["hinweise"])


def test_wissen_alle_quellen_aus_ist_kein_absturz(daten, monkeypatch):
    def down(url, **kw):
        raise common.requests.RequestException("down")

    monkeypatch.setattr(wissen, "fetch", down)
    data = wissen.run()
    assert data["regeln"] == [] and data["basis"] and len(data["hinweise"]) >= 2


def test_wissen_workflow_yaml():
    path = Path(__file__).resolve().parent.parent / ".github/workflows/firma-wissen.yml"
    wf = yaml.safe_load(path.read_text("utf-8"))
    assert wf[True]["schedule"][0]["cron"].split()[-1] == "1" and "workflow_dispatch" in wf[True]       # wöchentlich (montags)
    assert wf["permissions"]["contents"] == "write" and wf["concurrency"]["group"] == "firma-daten"
    steps = wf["jobs"]["wissen"]["steps"]
    assert any("cudi_video.firma wissen" in s.get("run", "") for s in steps)
    assert any("firma_commit.sh" in s.get("run", "") for s in steps)
    assert any("CUDI_LLM_MODEL" in (s.get("env") or {}) for s in steps)


# --------------------------------------------------------------------------- Natürlicher Klang

LONG = ("Der Turm steht seit vielen Jahren mitten in der Stadt, und von oben sieht man bei klarer Sicht bis zum Horizont. "
        "Kurz gesagt: ein Rekord! Wer hier hochfährt, vergisst den Alltag; denn der Blick ist einfach gewaltig.")


def test_natuerlicher_klang_verliert_kein_wort_und_ist_deterministisch():
    a = tts.plan_parts(LONG, "item", "ranking", seed="Video A|de|1")
    b = tts.plan_parts(LONG, "item", "ranking", seed="Video A|de|1")
    assert " ".join(p.text for p in a).split() == LONG.split() and a == b
    assert len(a) > len(tts.plan_parts(LONG, "item", "ranking"))                  # Atempausen an Komma/Satzende
    c = tts.plan_parts(LONG, "item", "ranking", seed="Video B|de|1")
    assert [(p.rate, p.pitch) for p in a] != [(p.rate, p.pitch) for p in c]       # je Video leicht anders, nicht monoton


def test_natuerlicher_klang_variation_bleibt_klein_und_nur_bei_normalen_teilen():
    parts = tts.plan_parts("Wetten, du errätst das nicht? " + LONG, "intro", "ranking", seed="s")
    base = tts.SPEECH_PROFILES["ranking"]["rollen"]
    for p in parts:
        r = base.get(p.role, base["normal"])
        if p.role == "normal":
            assert abs(p.rate - r[0]) <= 2 and abs(p.pitch - r[1]) <= 1
        else:
            assert (p.rate, p.pitch) == r[:2]                                      # Betonung bleibt unberührt


def test_natuerlicher_klang_abschaltbar(monkeypatch):
    monkeypatch.setenv("CUDI_NATUERLICH", "0")
    assert tts.plan_parts(LONG, "item", "ranking", seed="x") == tts.plan_parts(LONG, "item", "ranking")


def test_natuerlicher_klang_story_und_teilelimit():
    text = " ".join(f"Dann kam Schritt {i}, und alles wurde noch ein bisschen anders als gedacht." for i in range(30))
    parts = tts.plan_story_parts(text, "creepy", seed="s")
    assert " ".join(p.text for p in parts).split() == text.split()
    many = tts.plan_parts(text, "item", "ranking", seed="s")
    assert len(many) <= tts.MAX_PARTS and " ".join(p.text for p in many).split() == text.split()


def test_bewertung_ist_streng_gegen_abgehackte_aufzaehlung():
    abgehackt = "Wir starten mit Platz 3: Kangchendzönga. Berg im Himalaya. Das sind 8.586 Meter. Er liegt an der Grenze zweier Länder."
    erzaehlt = ("Stell dir vor: Du stehst auf 8.586 Metern – höher als jedes Flugzeug im Landeanflug. Das ist Platz 3, "
                "Kangchendzönga. Aber warte, es geht noch höher! Wer ist ganz oben?")
    a, b = (regie.bewerte([("item", t)], "de", "ranking") for t in (abgehackt, erzaehlt))
    by = {k["id"]: k["score"] for k in a["kriterien"]}
    assert 0.4 <= a["gesamt"] <= 0.72 and b["gesamt"] >= 0.85
    assert by["einordnung"] == 0.0 and by["ansprache"] == 0.0 and by["rhythmus"] < 0.2     # Zahl ohne Bild, kein „du“, Telegramm
    assert "Das sind" in {k["id"]: k["begruendung"] for k in a["kriterien"]}["natuerlich"]
