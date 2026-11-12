"""Schaubild: Erklärvideo in Stationen – je Station ein Bild im gewählten Bildstil, EINE belegte Zahl, Etiketten, Alltagsbezug.

Auftrag `{"art": "schaubild", "thema", "sprache", "stationen": 3–9, "stil", "seitenformat": "9:16"|"16:9"}`.
Wahrheit: Jede Station braucht einen wörtlichen Beleg aus der Quelle (Wikipedia-Artikel zum Thema); Zahlen im Sprechtext
müssen im Beleg stehen, neue Eigennamen gibt es nicht. Unbelegtes fliegt raus, zu wenig Belegtes = ehrlicher Abbruch.
Die Bilder sind Illustrationen (KI oder vom Renderer gezeichnet) und in jedem Bild als solche gekennzeichnet.
Vorbild und Stilregeln: docs/gehirn/vorbilder.md.
"""

from __future__ import annotations

import functools
import json
import re
from datetime import datetime, timezone
from pathlib import Path

from .. import handoff, net, textcheck

TASK = "schaubild"
MIN_STATIONEN, MAX_WORDS, TEXT_LIMIT = 3, 60, 9000
MIN_KANTEN = 3.0                          # mittlere Kantenstärke (0–255), darunter gilt ein Bild als leer/unscharf
FORMATE = ("9:16", "16:9")
KATALOG = Path(__file__).resolve().parent.parent / "data" / "bildstile.json"

INSTRUCTIONS = """Schreibe das Skript für ein kurzes Erklärvideo in Stationen (Stil „Schaubild“) – nur aus den Quellen unter „quellen“.
Antworte mit EINEM JSON-Objekt:
{"titel": "≤ 60 Zeichen", "hook": "eine Frage, die neugierig macht", "versprechen": "ein Satz: was man gleich versteht",
 "stationen": [{"name": "1–2 Wörter", "text": "2–3 gesprochene Sätze", "zahl": "eine Zahl aus dem Beleg, z. B. 20", "einheit": "z. B. Stunden",
                "beleg": "WÖRTLICHES Zitat aus der Quelle (ein bis zwei Sätze, unverändert)", "quelle": "id der Quelle",
                "etiketten": ["1–2 Wörter", "…"], "bild": "englische Bildbeschreibung EINES Motivs, ohne Text im Bild"}],
 "schluss": "ein Satz mit Bezug zum Alltag"}
Regeln:
- Genau {n} Stationen in der natürlichen Reihenfolge des Vorgangs (Anfang → Ende). Jede Station erklärt EINEN Schritt.
- Jede Station hat einen wörtlichen Beleg aus der Quelle. Jede Zahl im Text steht genau so im Beleg. Keine Zahl ohne Beleg –
  dann lieber „zahl“ leer lassen. Keine neuen Namen, keine Wertungen, keine Übertreibung, nichts vermuten.
- Sprache des Textes: {lang}. Einfach und bildhaft: wenn möglich ein Vergleich oder ein Bezug zum Alltag („wie …“).
- Höchstens 3 Etiketten je Station; jedes Etikett ist ein Begriff, der im Text der Station vorkommt.
- Hook, Versprechen und Schluss enthalten keine Zahlen, die nicht in einem Beleg stehen."""

FALLBACK = {"de": {"hook": "Wie funktioniert das eigentlich: {t}?", "schluss": "Jetzt weißt du, wie das funktioniert: {t}.",
                   "quelle": "Quelle", "bilder": "Bilder: Illustrationen (KI-generiert bzw. gezeichnet), keine echten Aufnahmen.",
                   "stand": "Stand"},
            "en": {"hook": "How does this actually work: {t}?", "schluss": "Now you know how it works: {t}.",
                   "quelle": "Source", "bilder": "Images: illustrations (AI-generated or drawn), not real footage.", "stand": "As of"}}
AUTO = (("isometrisch", r"stadt|verkehr|fabrik|logistik|netz|internet|strom|city|factory|network"),
        ("doku", r"geschichte|krieg|antik|mittelalter|history|ancient|geheim|mystery"),
        ("motiongraphics", r"geld|wirtschaft|zins|inflation|steuer|statistik|money|economy|tax"),
        ("wissenschaft3d", r"atom|zelle|dna|virus|physik|chemie|motor|cell|physics|engine|quanten"))


class SchaubildError(RuntimeError):
    """Auftrag nicht erfüllbar (zu wenig Belegtes, kein Sprachmodell) – ehrliche Meldung, nicht wiederholen."""
    wiederholbar = False


@functools.lru_cache(maxsize=1)
def stile() -> dict[str, dict]:
    return {s["id"]: s for s in json.loads(KATALOG.read_text("utf-8"))["stile"]}


def waehle_stil(wunsch: str, thema: str) -> dict:
    alle = stile()
    if wunsch in alle:
        return alle[wunsch]
    if wunsch == "auto":
        for sid, pattern in AUTO:
            if re.search(pattern, thema, re.I):
                return alle[sid]
    return alle["schaubild"]


def _norm(text: str) -> str:
    text = str(text).replace(" ", " ").replace("’", "'").replace("“", '"').replace("”", '"').replace("„", '"')
    return re.sub(r"\s+", " ", text.replace("–", "-").replace("—", "-")).strip().lower()


def quellen_sammeln(thema: str, lang: str) -> list[dict]:
    """Bis zu zwei Wikipedia-Artikel zum Thema (Volltextsuche), als Klartext."""
    from ..facts import article_text

    data = net.get_json(f"https://{lang}.wikipedia.org/w/api.php",
                        params={"action": "query", "list": "search", "srsearch": thema, "srlimit": 3, "format": "json"},
                        cache_hours=24, retries=3, max_wait=30)
    out = []
    for hit in (data.get("query", {}).get("search") or [])[:3]:
        text, title = article_text(lang, hit["title"], TEXT_LIMIT)
        if len(text) > 600:
            out.append({"id": f"q{len(out) + 1}", "name": f"Wikipedia: {title}", "text": text,
                        "url": f"https://{lang}.wikipedia.org/wiki/{title.replace(' ', '_')}"})
        if len(out) == 2:
            break
    return out


def pruefe_station(st: dict, quellen: list[dict], lang: str) -> tuple[dict | None, str]:
    """Eine Station gegen die Quelle prüfen. Rückgabe (bereinigte Station | None, Grund)."""
    if not isinstance(st, dict):
        return None, "kein Objekt"
    text, beleg = str(st.get("text") or "").strip(), str(st.get("beleg") or "").strip()
    name = re.sub(r"\s+", " ", str(st.get("name") or "")).strip()[:28]
    if len(text.split()) < 6 or len(text.split()) > MAX_WORDS:
        return None, "Text zu kurz oder zu lang"
    if len(beleg) < 20:
        return None, "kein Beleg"
    quelle = next((q for q in quellen if _norm(beleg) in _norm(q["text"])), None)
    if quelle is None:
        return None, "Beleg steht nicht wörtlich in der Quelle"
    extra = textcheck.numbers(text, lang) - textcheck.numbers(beleg, lang)
    if extra:
        return None, f"Zahl ohne Beleg: {', '.join(sorted(extra))}"
    people = textcheck.invented_people(text, " ".join(q["text"] for q in quellen))
    if people:
        return None, f"Name ohne Beleg: {', '.join(people)}"
    zahl = re.sub(r"\s+", " ", str(st.get("zahl") or "")).strip()[:12]
    if zahl and not (textcheck.digits(zahl) and textcheck.digits(zahl) <= textcheck.digits(beleg)):
        zahl = ""                                             # Zahl steht nicht im Beleg -> ohne Riesenzahl
    einheit = re.sub(r"\s+", " ", str(st.get("einheit") or "")).strip()[:18] if zahl else ""
    if einheit and _norm(einheit) not in _norm(beleg) and _norm(einheit) not in _norm(text):
        einheit = ""
    low = _norm(text + " " + name)
    etiketten = []
    for e in st.get("etiketten") or []:
        e = re.sub(r"\s+", " ", str(e)).strip()
        if 2 <= len(e) <= 22 and len(e.split()) <= 2 and _norm(e) in low and e not in etiketten:
            etiketten.append(e)
    bild = re.sub(r"[^\x20-\x7e]", "", str(st.get("bild") or ""))[:220].strip()
    return {"name": name or text.split()[0], "text": text, "zahl": zahl, "einheit": einheit, "beleg": beleg,
            "quelle": quelle["name"], "quelle_url": quelle["url"], "etiketten": etiketten[:3], "bild": bild or name}, ""


def pruefe_satz(text: str, erlaubt: set[str], quellen_text: str, lang: str) -> bool:
    """Hook/Versprechen/Schluss: keine Zahl außerhalb der Belege, kein Name außerhalb der Quellen."""
    text = str(text or "").strip()
    return bool(text) and len(text.split()) <= 34 and not (textcheck.numbers(text, lang) - erlaubt) \
        and not textcheck.invented_people(text, quellen_text)


def wahrheit(stationen: list[dict], lang: str) -> tuple[list[dict], list[tuple[str, str]]]:
    """Derselbe Wahrheits-Prüfer wie bei Fakten-Videos (über die Satire-Brücke): Satz gegen seinen Beleg."""
    from ..satire import wahrheit_fakten

    saetze = [{"text": s["text"], "belege": [{"zitat": s["beleg"], "name": s["quelle"]}]} for s in stationen]
    ok, rejected = wahrheit_fakten(saetze, lang)
    keep = {s["text"] for s in ok}
    return [s for s in stationen if s["text"] in keep], rejected


def baue_skript(ident: str, titel: str, hook: str, versprechen: str, stationen: list[dict], schluss: str, lang: str,
                stil: dict, seitenformat: str) -> dict:
    szenen = [{"typ": "intro", "text": " ".join(x for x in (hook, versprechen) if x), "kopf": titel, "name": titel.split()[0]}]
    for i, st in enumerate(stationen, start=1):
        szenen.append({"typ": "station", "station": i, **st})
    szenen.append({"typ": "outro", "text": schluss, "kopf": titel, "name": titel.split()[0]})
    return {"id": ident, "titel": titel, "sprache": lang, "stil": stil, "seitenformat": seitenformat, "szenen": szenen}


def bild_brauchbar(path: str) -> bool:
    """KI-Bilder sind manchmal nur ein unscharfer Farbverlauf – solche Bilder zeigen nichts und fliegen raus."""
    from PIL import Image, ImageFilter, ImageStat

    try:
        with Image.open(path) as im:
            kanten = im.convert("L").resize((256, 256)).filter(ImageFilter.FIND_EDGES)
            return ImageStat.Stat(kanten.crop((8, 8, 248, 248))).mean[0] >= MIN_KANTEN
    except OSError:
        return False


def bilder(skript: dict, work: Path, notes: list[str]) -> None:
    """Je Szene ein Bild: KI-Illustration (nacheinander) → freies Foto → vom Renderer gezeichnete Grafik."""
    stil = skript["stil"]
    if stil["modus"] == "code":
        return
    from ..story import visuals

    stationen = [s for s in skript["szenen"] if s["typ"] == "station"]
    used: set = set()
    fehlt = 0
    for i, sz in enumerate(stationen):
        prompt = f"{sz['bild']}, {stil['prompt']}"
        vis = visuals.ai_image(prompt, seed=1000 + i)
        if vis is not None and not bild_brauchbar(vis.path):   # einmal mit anderem Startwert, sonst Ausweichweg
            vis = visuals.ai_image(prompt, seed=2000 + i)
            vis = vis if vis is not None and bild_brauchbar(vis.path) else None
        if vis is not None:
            sz.update(bild_datei=vis.path, ki=True, bild_quelle="KI-Illustration (Pollinations)", bild_prompt=prompt)
            continue
        try:
            foto = visuals.commons_photo(sz["bild"], used)
        except Exception:                                     # Bild ist optional
            foto = None
        if foto is not None:
            sz.update(bild_datei=foto.path, ki=False, bild_quelle=f"Foto: {foto.credit}", bild_prompt="")
        else:
            fehlt += 1
    if fehlt:
        notes.append(f"{fehlt} Station(en) ohne Bild – dort zeichnet der Renderer eine schlichte Grafik.")
    erste = next((s for s in stationen if s.get("bild_datei")), None)
    if erste:                                                 # Einstieg und Schluss zeigen ein vorhandenes Bild erneut
        letzte = next((s for s in reversed(stationen) if s.get("bild_datei")), erste)
        for sz, src in ((skript["szenen"][0], erste), (skript["szenen"][-1], letzte)):
            sz.update({k: src[k] for k in ("bild_datei", "ki", "bild_quelle", "bild_prompt")})


def texte(skript: dict, quellen: list[dict], lang: str) -> tuple[str, str]:
    s = FALLBACK[lang]
    namen = [sz["name"] for sz in skript["szenen"] if sz["typ"] == "station"]
    used = sorted({(sz["quelle"], sz["quelle_url"]) for sz in skript["szenen"] if sz.get("quelle_url")})
    stand = datetime.now(timezone.utc).date().isoformat()
    yt = "\n".join([skript["titel"], "", skript["szenen"][0]["text"], "", " → ".join(namen), "",
                    *(f"{s['quelle']}: {n} – {u}" for n, u in used), f"{s['stand']}: {stand}", s["bilder"], "", "#shorts #wissen #erklaert"])
    tt = f"{skript['titel']} – {' → '.join(namen)}\n{s['bilder']}\n#fyp #wissen #erklaert"
    return yt, tt


def pruefbericht(skript: dict, quellen: list[dict], rejected: list[tuple[str, str]], notes: list[str]) -> str:
    stil = skript["stil"]
    lines = [f"# Prüfbericht Schaubild: {skript['titel']}", "",
             f"- Bildstil: {stil['name']} ({stil['id']}, {'KI-Illustration' if stil['modus'] == 'bild' else 'vom Renderer gezeichnet'}), "
             f"Seitenformat {skript['seitenformat']}",
             "- Bewegung: Zoom/Schwenk/Parallaxe/Ruckeln – keine animierten Figuren. Alle Bilder sind als Illustration gekennzeichnet.",
             "", "## Stationen (Sprechtext → wörtlicher Beleg)"]
    for sz in skript["szenen"]:
        if sz["typ"] != "station":
            continue
        lines += [f"{sz['station']}. **{sz['name']}** – {sz['text']}", f"   - Beleg ({sz['quelle']}): „{sz['beleg']}“",
                  f"   - Bild: {sz.get('bild_quelle') or 'vom Renderer gezeichnet'}"
                  + (f" · Zahl im Bild: {sz['zahl']} {sz['einheit']}".rstrip() if sz.get("zahl") else "")]
    lines += ["", "## Quellen", *(f"- {q['name']} – {q['url']}" for q in quellen)]
    if rejected:
        lines += ["", "## Abgelehnt (nicht im Video)", *(f"- {t} – {why}" for t, why in rejected)]
    if notes:
        lines += ["", "## Hinweise", *(f"- {n}" for n in notes)]
    return "\n".join(lines) + "\n"


def run(order: dict, folder: Path, progress=lambda stage, f: None) -> dict:
    """Schaubild-Auftrag -> Ergebnis im Format von job._summary."""
    from .render import render_schaubild

    lang, thema = order["sprache"], order["thema"]
    out = folder / "schaubild"
    out.mkdir(parents=True, exist_ok=True)
    if not handoff.active():
        raise SchaubildError("Schaubild braucht ein Sprachmodell zum Formulieren (Claude oder CUDI_LLM_*) – gerade keines erreichbar. "
                             "Erfunden wird nichts; bitte später erneut versuchen.")
    cache = folder / "schaubild_quellen.json"                 # ein Weiterlauf prüft gegen dieselben Texte
    if cache.exists():
        quellen = json.loads(cache.read_text("utf-8"))
    else:
        progress("Quellen sammeln", 0.05)
        quellen = quellen_sammeln(thema, lang)
        cache.write_text(json.dumps(quellen, ensure_ascii=False), "utf-8")
    if not quellen:
        raise SchaubildError(f"Schaubild nicht möglich: Zu „{thema}“ fand sich kein Artikel als Quelle. Bitte das Thema genauer nennen.")
    stil = waehle_stil(order.get("stil") or "schaubild", thema)
    progress("Skript schreiben", 0.15)
    answer = handoff.request(TASK, INSTRUCTIONS.replace("{n}", str(order["stationen"])).replace("{lang}", "Deutsch" if lang == "de" else "English"),
                             {"thema": thema, "sprache": lang, "stationen": order["stationen"],
                              "quellen": [{"id": q["id"], "name": q["name"], "text": q["text"]} for q in quellen]})
    if not isinstance(answer, dict):
        raise SchaubildError("Schaubild nicht möglich: Das Sprachmodell hat kein Skript geliefert. Es wird nichts erfunden – bitte später erneut versuchen.")
    rejected: list[tuple[str, str]] = []
    stationen = []
    for st in (answer.get("stationen") or [])[:9]:
        ok, why = pruefe_station(st, quellen, lang)
        if ok:
            stationen.append(ok)
        else:
            rejected.append((str((st or {}).get("text") if isinstance(st, dict) else st)[:120], why))
    stationen, rej = wahrheit(stationen, lang)
    rejected += rej
    if len(stationen) < MIN_STATIONEN:
        raise SchaubildError(f"Schaubild nicht möglich: Nur {len(stationen)} Station(en) ließen sich wörtlich belegen "
                             f"(nötig: {MIN_STATIONEN}). Es wird nichts ergänzt.")
    erlaubt = set().union(*(textcheck.numbers(s["beleg"], lang) for s in stationen))
    qtext = " ".join(q["text"] for q in quellen)
    notes: list[str] = []
    titel = re.sub(r"\s+", " ", str(answer.get("titel") or "")).strip()
    if not (4 <= len(titel) <= 60 and pruefe_satz(titel, erlaubt, qtext, lang)):
        titel = thema[:60]
    fb = FALLBACK[lang]
    hook = str(answer.get("hook") or "").strip()
    if not pruefe_satz(hook, erlaubt, qtext, lang):
        hook = fb["hook"].format(t=titel)
        notes.append("Einstieg aus der Regel-Fassung (der Vorschlag enthielt Unbelegtes).")
    versprechen = str(answer.get("versprechen") or "").strip()
    if not pruefe_satz(versprechen, erlaubt, qtext, lang):
        versprechen = ""
    schluss = str(answer.get("schluss") or "").strip()
    if not pruefe_satz(schluss, erlaubt, qtext, lang):
        schluss = fb["schluss"].format(t=titel)
    skript = baue_skript("schaubild", titel, hook, versprechen, stationen, schluss, lang, stil, order.get("seitenformat") or "9:16")
    progress("Bilder", 0.3)
    bilder(skript, out / "work", notes)
    yt, tt = texte(skript, quellen, lang)
    (out / "youtube.txt").write_text(yt, "utf-8")
    (out / "tiktok.txt").write_text(tt, "utf-8")
    (out / "spec.json").write_text(json.dumps({"title": {"de": titel, "en": titel}}, ensure_ascii=False), "utf-8")
    (out / "review.md").write_text(pruefbericht(skript, quellen, rejected, notes), "utf-8")
    progress("Video rendern", 0.4)
    result = render_schaubild(skript, out, progress=lambda f: progress("Video rendern", 0.4 + 0.55 * f))
    files = {"video": result["video"], "cover": result["cover"], "duration": result["duration"], "qa": result.get("qa"),
             "description_file": "youtube.txt", "caption_file": "tiktok.txt", "abnahme": {"ok": True, "gruende": []}}
    return {"output_dir": str(out), "videos": {lang: files}, "kind": "schaubild", "warnings": notes}
