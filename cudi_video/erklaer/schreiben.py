"""Erklärvideo zu einem freien Thema: Sprachmodell (Claude oder CUDI_LLM_*) schreibt das Szenen-Skript, der Code prüft.

Quelle ist ein Wikipedia-Artikel. Jede Szene trägt einen wörtlichen Beleg-Satz („beleg“) aus dem Artikel; Zahlen im
Sprechertext und in den Grafikfeldern müssen im Beleg stehen, Namen/Hauptwörter im Artikel, Zitate wörtlich im Artikel.
Szenen, die das nicht bestehen, gehen einmal mit Begründung zur Korrektur zurück, sonst fliegen sie raus. Bleiben zu
wenige Szenen übrig, endet der Auftrag ehrlich – erfunden wird nichts.
"""

from __future__ import annotations

import logging
import re

from .. import facts, handoff, net, textcheck
from ..narrate import unknown_words
from ..render.linien import POSES, VISUALS
from .skript import ScriptError, validate_script

log = logging.getLogger(__name__)

MIN_SCENES = 4
MAX_SCENES = 10
ARTICLE_CHARS = 9000
SCENE_WORDS = (8, 55)
VISUAL_TEXT_KEYS = ("label", "wert", "zitat", "umschrift", "uebersetzung", "quelle", "ueberliefert")

INSTRUCTIONS = (
    "Schreibe ein ruhiges Erklärvideo (Hochformat, 45 bis 120 Sekunden) zum Thema „thema“ als Szenen-Skript. NUR der "
    "Artikeltext unter „quelle“ darf Fakten liefern. Aufbau: Szene 1 = neugierig machende Frage oder Aufhänger (ohne "
    "Spoiler), danach 4 bis 8 Erklär-Szenen (Kernaussage -> Erklärung -> Bedeutung für den Zuschauer), letzte Szene = "
    "ruhiger Schluss. Jede Szene: {\"text\": Sprechertext (8 bis 55 Wörter, gut vorlesbar, Zahlen als Ziffern), "
    "\"beleg\": EIN Satz, wörtlich aus dem Artikel kopiert, der den Sprechertext trägt, \"betont\": [1 bis 3 Wörter, die "
    "im Text stehen], \"kapitel\": optional kurzes Stichwort, \"visual\": {\"typ\": einer aus „visuals“, optional "
    "\"label\" (kurz, ohne neue Zahlen); \"figur\" braucht \"pose\" aus „posen\"; \"zitatkarte\" braucht \"zitat\" "
    "wörtlich aus dem Artikel; \"zahl_zaehler\" braucht \"wert\" als Zahl aus dem Beleg}}. Strenge Regeln: Erfinde "
    "nichts – keine Zahl, kein Name, kein Ort, keine Jahreszahl, die nicht im Beleg der Szene steht; keine Wertungen "
    "wie „der beste“, „unglaublich“; keine Übertreibung. Wenn der Artikel zu wenig hergibt, liefere weniger Szenen. "
    "Antworte mit JSON: {\"titel\": \"…\", \"szenen\": [ … ]}. Ist das Thema mit dem Artikel nicht erklärbar, antworte "
    "mit {\"fehler\": \"Grund\"}."
)
INSTRUCTIONS_FIX = (
    " KORREKTUR: Die Szenen unter „abgelehnt“ haben die Prüfung nicht bestanden (Grund steht dabei). Liefere für jede "
    "eine verbesserte Fassung im selben Format unter „szenen“: Beleg-Satz wörtlich aus dem Artikel, Sprechertext nur mit "
    "Zahlen und Namen aus diesem Beleg, einfache Alltagswörter. Antworte mit {\"szenen\": [ … ]}."
)


def _norm(text: str) -> str:
    return facts._norm(text)


def find_article(topic: str, lang: str) -> tuple[str, str, str]:
    """(Titel, Klartext, Adresse) des passenden Wikipedia-Artikels; leer, wenn keiner gefunden wird."""
    candidates = [topic]
    try:
        data = net.get_json(f"https://{lang}.wikipedia.org/w/api.php",
                            params={"action": "opensearch", "search": topic, "limit": 3, "format": "json"},
                            cache_hours=24, retries=3, max_wait=30)
        candidates += [t for t in (data[1] if isinstance(data, list) and len(data) > 1 else []) if t not in candidates]
    except net.FetchError as exc:
        log.warning("Wikipedia-Suche für %r nicht erreichbar: %s", topic, exc)
    for title in candidates[:4]:
        try:
            text, real = facts.article_text(lang, title, ARTICLE_CHARS)
        except net.FetchError as exc:
            log.warning("Artikel %r nicht abrufbar: %s", title, exc)
            continue
        if len(text) >= facts.MIN_ARTICLE_CHARS:
            return real, text, f"https://{lang}.wikipedia.org/wiki/{real.replace(' ', '_')}"
    return "", "", ""


def check_scene(scene: dict, source: str, lang: str) -> str:
    """'' = Szene besteht, sonst der Grund der Ablehnung."""
    if not isinstance(scene, dict):
        return "keine Szene"
    text = re.sub(r"\s+", " ", str(scene.get("text") or "")).strip()
    beleg = re.sub(r"\s+", " ", str(scene.get("beleg") or "")).strip()
    words = len(text.split())
    if not SCENE_WORDS[0] <= words <= SCENE_WORDS[1]:
        return f"Sprechertext hat {words} Wörter (erlaubt {SCENE_WORDS[0]} bis {SCENE_WORDS[1]})"
    if len(beleg) < 20 or _norm(beleg) not in _norm(source):
        return "Der Beleg-Satz steht nicht wörtlich im Artikel"
    backed = textcheck.numbers(beleg, lang) | textcheck.numbers(beleg, "en" if lang == "de" else "de")
    extra = sorted(textcheck.numbers(text, lang) - backed)
    if extra:
        return "Zahlen ohne Beleg im Beleg-Satz: " + ", ".join(extra)
    if textcheck.invented_people(text, source):
        return "Name nicht im Artikel: " + ", ".join(textcheck.invented_people(text, source))
    src_words = frozenset(re.findall(r"[a-zäöüß]{3,}", f"{source} {beleg}".lower()))
    unknown = [w for w in unknown_words(text, {"sprache": lang, "beleg": beleg, "quelle": source})
               if not textcheck.everyday_word(w, lang, src_words)]
    if unknown:
        return "Wörter, die weder im Beleg noch im Artikel stehen: " + ", ".join(unknown[:4])
    from ..script import NOT_NEUTRAL
    if NOT_NEUTRAL.search(text):
        return "Wertende oder übertriebene Wortwahl"
    return ""


def clean_visual(scene: dict, source: str, lang: str) -> tuple[dict, str]:
    """Grafikfelder prüfen: Zahlen müssen im Beleg stehen, Zitate wörtlich im Artikel. Bei Verstoß neutrale Beschriftung."""
    visual = dict(scene.get("visual") or {"typ": "beschriftung"})
    beleg = str(scene.get("beleg") or "")
    backed = textcheck.numbers(beleg, lang) | textcheck.numbers(beleg, "en" if lang == "de" else "de")
    note = ""
    if visual.get("typ") not in VISUALS:
        visual = {"typ": "beschriftung"}
    if visual["typ"] == "figur" and visual.get("pose") not in POSES:
        visual["pose"] = "stehen"
    if "n" in visual:
        try:
            visual["n"] = max(20, min(600, int(visual["n"])))
        except (TypeError, ValueError):
            visual.pop("n")
    bad = False
    for key in VISUAL_TEXT_KEYS:
        value = str(visual.get(key) or "")
        if value and not textcheck.numbers(value, lang) <= backed:
            bad = True
        if key == "zitat" and value and _norm(value) not in _norm(source):
            bad = True
    if visual["typ"] == "zitatkarte" and not str(visual.get("zitat") or "").strip():
        bad = True
    if visual["typ"] == "zahl_zaehler" and not str(visual.get("wert") or "").strip():
        bad = True
    if bad:
        note = f"Grafik „{visual.get('typ')}“ ersetzt (Zahl/Zitat nicht belegt)"
        visual = {"typ": "beschriftung", "label": str(scene.get("kapitel") or "")[:40]}
    return visual, note


def _scenes_of(answer) -> list[dict]:
    scenes = answer.get("szenen") if isinstance(answer, dict) else None
    return [s for s in scenes if isinstance(s, dict)] if isinstance(scenes, list) else []


def write_script(topic: str, lang: str = "de", article=None) -> tuple[dict, dict]:
    """(Skript, Bericht). Bericht: {quelle, url, beleg: [...], hinweise: [...]}.
    Wirft handoff.WritingNeeded (Claude-Sitzung), RuntimeError/ValueError (ehrlicher Abbruch)."""
    if not handoff.active():
        raise handoff.ModelUnavailable("Erklärvideos brauchen ein Sprachmodell zum Schreiben (Claude oder CUDI_LLM_*) – gerade "
                                       "keines erreichbar. Erfunden wird nichts; bitte später erneut versuchen.")
    title, source, url = article or find_article(topic, lang)
    if not source:
        raise ValueError(f"Zu „{topic}“ fand sich kein Wikipedia-Artikel in ausreichender Länge. "
                         "Bitte das Thema etwas anders formulieren.")
    data = {"thema": topic, "sprache": lang, "visuals": VISUALS, "posen": POSES,
            "quelle": {"titel": title, "text": source}}
    notes: list[str] = []
    from .. import animation
    answer = handoff.request("erklaer", INSTRUCTIONS + animation.storyboard_zusatz(), data)   # Storyboard gleich mit (eine Runde weniger)
    if isinstance(answer, dict) and answer.get("fehler"):
        raise ValueError("Das Thema lässt sich mit dem Artikel nicht erklären: " + str(answer["fehler"])[:300])
    scenes = _scenes_of(answer)
    if not scenes:
        raise handoff.ModelUnavailable("Es kam kein Skript zurück (Sprachmodell nicht erreichbar oder Antwort unbrauchbar). "
                                       "Erfunden wird nichts – bitte später erneut versuchen.")
    kept, rejected = [], []
    for scene in scenes[:MAX_SCENES + 2]:
        reason = check_scene(scene, source, lang)
        (rejected if reason else kept).append((scene, reason) if reason else scene)
    if len(kept) < MIN_SCENES and rejected:
        retry = {**data, "regeln": INSTRUCTIONS, "abgelehnt": [{"szene": s, "grund": r} for s, r in rejected]}
        fixed = _scenes_of(handoff.request("erklaer_korrektur", INSTRUCTIONS_FIX, retry))
        for scene in fixed:
            reason = check_scene(scene, source, lang)
            if reason:
                notes.append(f"Szene verworfen: {reason}.")
            else:
                kept.append(scene)
        rejected = []
    for scene, reason in rejected:
        notes.append(f"Szene „{str(scene.get('text', ''))[:50]}…“ verworfen: {reason}.")
    if len(kept) < MIN_SCENES:
        raise ValueError(f"Nur {len(kept)} Szenen bestanden die Prüfung (mindestens {MIN_SCENES} nötig). "
                         "Erfunden wird nichts – bitte das Thema enger fassen oder später erneut versuchen.")
    kept = kept[:MAX_SCENES]
    out_scenes, proof, storyboards = [], [], []
    for scene in kept:
        visual, note = clean_visual(scene, source, lang)
        if note:
            notes.append(note)
        words = [w for w in (scene.get("betont") or []) if isinstance(w, str) and w in str(scene.get("text"))][:3]
        out_scenes.append({"kapitel": str(scene.get("kapitel") or "")[:40], "text": re.sub(r"\s+", " ", str(scene["text"])).strip(),
                           "betont": words, "visual": visual})
        proof.append({"text": out_scenes[-1]["text"], "beleg": re.sub(r"\s+", " ", str(scene["beleg"])).strip()})
        storyboards.append({k: scene.get(k) for k in ("drehbuch", "ohne_bild", "figuren", "figur_wuensche") if scene.get(k)})
    script_id = "erklaer-" + re.sub(r"[^a-z0-9]+", "-", topic.lower())[:30].strip("-")
    try:
        script = validate_script({"id": script_id, "titel": str(answer.get("titel") or title)[:80], "sprache": lang,
                                  "szenen": out_scenes})
    except ScriptError as exc:
        raise ValueError(f"Das Skript ist unbrauchbar: {exc}") from exc
    ok_title = textcheck.numbers(script["titel"], lang) <= textcheck.numbers(source, lang)
    if not ok_title or textcheck.invented_people(script["titel"], source):
        script["titel"] = title
        notes.append("Titel enthielt Unbelegtes und wurde durch den Artikeltitel ersetzt.")
    return script, {"quelle": title, "url": url, "beleg": proof, "hinweise": notes, "storyboard": storyboards}
