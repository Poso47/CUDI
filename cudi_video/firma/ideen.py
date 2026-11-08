"""Ideen-Entwickler: aus Trends + Nachrichten (+ Gelerntem) 3–5 Videoideen je Bereich -> firma_daten/ideen.json.

Das Sprachmodell (kostenloses Gemini über CUDI_LLM_*) liefert nur THEMEN und Begründungen aus den vorgelegten Daten;
Fakten und Zahlen entstehen später in der geprüften Pipeline. Ohne Zugang: regelbasierte Ideen aus den Trends.
Ranking-Ideen werden vorgeprüft (Vorlage vorhanden? sonst planbar mit Wikidata-Probe?), der Rest bleibt „Idee“."""

from __future__ import annotations

import hashlib
import json
import re
import time
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeout

from . import common
from .common import iso, now

AREAS = ("ranking", "fakten", "story", "erklaer", "reportage")
PER_AREA = (3, 5)
KEEP_DAYS = 7
MAX_PER_AREA = 15
PLAN_TIMEOUT = 40
PROBE_TIMEOUT = 30
MAX_PROBES = 4

SYSTEM = (
    "Du bist Ideen-Redakteur für kurze Hochformat-Wissensvideos (TikTok/YouTube Shorts, Deutsch). "
    "Du bekommst Listen aktueller Trends und bestätigter Nachrichten. Schlage pro Bereich 3 bis 5 neue Videoideen vor, "
    "die zu diesen Daten passen. STRENGE REGELN: Erfinde nichts. Nenne nur THEMEN, niemals Fakten, Zahlen, Rekorde, "
    "Zitate oder Behauptungen – die entstehen später in einer geprüften Pipeline. Jede Idee muss sich auf genau einen "
    "Eintrag der Listen stützen (exakter Name im Feld quelle_trend). Die Begründung darf nur wiedergeben, was in den "
    "Daten steht (z. B. Platz, Quelle, Meldung). Keine Personen in Verruf bringen, keine Gewalt-/Sexualthemen, keine "
    "unbestätigten Gerüchte. Bereiche: ranking = Liste von Dingen EINER Art, sortierbar nach einer messbaren Zahl "
    "(z. B. höchste Berge, größte Seen; Thema als kurzer Satz) – nur echte Dinge mit festen Messwerten, NIE Listen "
    "über Suchbegriffe, Klickzahlen, Trends, Aufrufe oder Beliebtheit; fakten = Wissens-Fakten zu einem Thema; story = "
    "erzählte Alltagsgeschichte/Reddit-Stimmung (Thema als Stimmungsbeschreibung), NIE zu Nachrichten oder echten "
    "Personen; reportage = sachliche Nachrichtenreportage zu einer bestätigten Meldung; erklaer = ruhiges Erklärvideo, wie etwas "
    "funktioniert oder zusammenhängt. Antworte NUR mit JSON: {\"ideen\": [{\"bereich\": \"ranking|fakten|story|erklaer|reportage\", "
    "\"titel\": \"Videotitel, höchstens 60 Zeichen\", \"thema\": \"Thema in einem Satz\", \"begruendung\": \"…\", "
    "\"quelle_trend\": \"exakter Name aus den Listen\"}]}"
)


# --------------------------------------------------------------------------- Hilfen

def _norm(text: str) -> str:
    return " ".join(re.findall(r"\w+", (text or "").lower()))


def _stems(text: str) -> set[str]:
    return {w[:5] for w in re.findall(r"[^\W\d_]{4,}", text.lower())}


def preset_match(thema: str, presets: dict[str, dict]) -> str | None:
    """Vorlage, deren Titel/Name zum Thema passt (mindestens zwei gemeinsame Wortstämme)."""
    want = _stems(thema)
    best, score = None, 0
    for pid, raw in presets.items():
        title = raw.get("title", {})
        have = _stems(" ".join([pid.replace("-", " "), str(title.get("de", "")), str(title.get("en", ""))]))
        n = len(want & have)
        if n > score:
            best, score = pid, n
    return best if score >= 2 else None


def load_presets() -> dict[str, dict]:
    try:
        from .. import spec
        return {pid: spec.preset_raw(pid) for pid in spec._preset_paths()}
    except Exception:                                     # noqa: BLE001 – ohne Vorlagen nur keine Vorprüfung
        return {}


def _timed(func, seconds: float):
    pool = ThreadPoolExecutor(max_workers=1)
    try:
        return pool.submit(func).result(timeout=seconds)
    except FutureTimeout:
        raise TimeoutError(f"Zeitlimit {seconds:.0f} s") from None
    finally:
        pool.shutdown(wait=False, cancel_futures=True)


def check_ranking(thema: str, count: int, presets: dict[str, dict], probes_left: list[int], use_llm: bool) -> dict:
    """Vorprüfung einer Ranking-Idee. Rückgabe: {geprueft, vorlage?, plan?, hinweis?}."""
    pid = preset_match(thema, presets)
    if pid:
        return {"geprueft": "vorlage", "vorlage": pid, "hinweis": f"passende Vorlage „{pid}“"}
    if not use_llm or probes_left[0] <= 0:
        return {"geprueft": "idee", "hinweis": "nicht vorgeprüft (kein Planer/Limit erreicht)"}
    probes_left[0] -= 1
    try:
        from .. import planner
        try:
            spec = _timed(lambda: planner.plan(thema, count), PLAN_TIMEOUT)
        except Exception as exc:                          # noqa: BLE001 – gratis-Limit des Modells: einmal später noch mal
            if "429" not in str(exc):
                raise
            time.sleep(20)
            spec = _timed(lambda: planner.plan(thema, count), PLAN_TIMEOUT)
        time.sleep(4)                                     # Abstand zur nächsten Modellanfrage
    except Exception as exc:                              # noqa: BLE001 – PlanFailed, Netz, Zeitlimit …
        return {"geprueft": "idee", "hinweis": f"nicht planbar: {common.short_error(exc)}"[:160]}
    src = spec["source"]
    plan = {"klasse": src["class"], "eigenschaft": src["property"], "reihenfolge": src["order"]}
    try:
        from ..sources import wikidata
        from ..spec import VideoSpec
        vs = VideoSpec.from_file_data(spec, count)
        rows = _timed(lambda: wikidata._sparql(wikidata.build_ranking_query(vs.source, limit=8), cache_hours=1),
                      PROBE_TIMEOUT)
    except Exception as exc:                              # noqa: BLE001
        return {"geprueft": "geplant", "plan": plan, "hinweis": f"Wikidata-Probe offen: {common.short_error(exc)}"[:160]}
    if len(rows) >= 3:
        return {"geprueft": "wikidata", "plan": plan, "hinweis": f"Wikidata-Probe: {len(rows)}+ Treffer"}
    return {"geprueft": "geplant", "plan": plan, "hinweis": "Wikidata-Probe mit zu wenigen Treffern"}


def build_order(area: str, idea: dict, check: dict) -> dict | None:
    """Idee im Auftragsformat der CUDI-App (art/vorlage|thema/…). Erklärvideos haben noch keinen App-Auftrag."""
    thema = idea["thema"][:120]
    if area == "ranking":
        order = {"art": "ranking", "plaetze": 10, "sprachen": ["de", "en"]}
        if check.get("vorlage"):
            order["vorlage"] = check["vorlage"]
        else:
            order["thema"] = thema
        return order
    if area == "fakten":
        return {"art": "ranking", "thema": thema, "plaetze": 7, "sprachen": ["de", "en"]}
    if area == "story":
        return {"art": "story", "wunsch": thema[:300], "stimmung": "auto", "sprache": "de", "laenge": "3min"}
    if area == "reportage":                            # sachliche Reportage (reportage/__init__.py), Quellen sucht die Pipeline
        return {"art": "reportage", "thema": re.sub(r"^Sachliche Reportage:\s*", "", thema)[:160], "sprache": "de"}
    return {"art": "erklaer", "thema": thema}


def validate_order(order: dict | None, presets: dict[str, dict]) -> str:
    """Leer = gültig; sonst Grund. Nutzt dieselbe Prüfung wie die App."""
    if not order or order["art"] == "erklaer":
        return ""
    try:
        from .. import job
        job.parse_order({"id": "idee0000", **order}, set(presets))
    except Exception as exc:                              # noqa: BLE001
        return str(exc)[:120]
    return ""


# Aus Leid wird kein Unterhaltungsvideo: Tod, Gewalt, Anschläge, Unglücke, Krieg, Missbrauch, Suizid – solche
META_RANKING = re.compile(r"meist(gesucht|gelesen|geklickt|aufgerufen|gesehen)|suchbegriff|begriffe|aufrufe|klicks|"
                          r"trends?\b|beliebteste", re.I)

# Themen werden ausschließlich zu sachlichen Reportage-Ideen (Bereich „reportage“) mit festen Regeln.
REPORTAGE_REGELN = ("Sachlich und respektvoll wie eine Nachrichtenreportage; nur von mehreren Quellen bestätigte Fakten "
                    "mit Zeitbezug; keine Spannungs-Hooks, kein Clickbait, keine Spekulation, keine reißerische Musik; "
                    "Betroffene nicht zur Schau stellen, keine Namen von Opfern ohne öffentliche Bestätigung; Quellen nennen.")
HEIKEL = re.compile(
    r"\b(tot|tote[nr]?|getötet|stirbt|starb|gestorben|tod(es)?|leiche|mord\w*|ermordet|erschossen|schütze|amok\w*|"
    r"anschlag\w*|terror\w*|attentat\w*|geisel\w*|krieg\w*|luftangriff\w*|bomb\w*|explosion|opfer|verletzt\w*|"
    r"unglück\w*|absturz|abgestürzt|erdbeben|flut\w*|katastroph\w*|vergewaltig\w*|missbrauch\w*|suizid\w*|selbstmord|"
    r"kill\w*|dead|death\w*|dies|died|murder\w*|shoot\w*|shot|gunman|attack\w*|terror\w*|hostage\w*|war|strikes?|"
    r"bomb\w*|victims?|injur\w*|crash\w*|earthquake|flood\w*|disaster\w*|rape\w*|abuse\w*|suicide)\b", re.I)


def heikel(*texts: str) -> bool:
    return any(HEIKEL.search(t or "") for t in texts)


def candidates(trends: dict, news: dict) -> dict[str, dict]:
    """Erlaubte Quellen für Ideen: Name -> {typ, score, warum, heikel}. Heikle Themen nur als Reportage (siehe finish)."""
    out: dict[str, dict] = {}
    for t in (trends.get("themen") or [])[:25]:
        out[t["thema"]] = {"typ": "trend", "heikel": heikel(t["thema"], t.get("warum", "")), "score": t.get("score"), "kategorie": t.get("kategorie", ""),
                           "warum": t.get("warum", ""), "quellen": sorted({q["quelle"] for q in t.get("quellen", [])})}
    for m in [m for m in (news.get("meldungen") or []) if m.get("status") == "bestätigt"][:15]:
        out.setdefault(m["titel"], {"typ": "news", "score": None, "heikel": heikel(m.get("titel", ""), m.get("kurz", "")), "kategorie": "Ereignis",
                                    "warum": f"bestätigt von {m.get('n_quellen', 2)} Quellen ({m.get('quelle', '')})",
                                    "quellen": [q["quelle"] for q in m.get("quellen", [])][:3]})
    return out


def match_source(name: str, cand: dict[str, dict]) -> str | None:
    if name in cand:
        return name
    n = _norm(name)
    for key in cand:
        if _norm(key) == n:
            return key
    return None


# --------------------------------------------------------------------------- Ideen erzeugen

def llm_ideas(cand: dict[str, dict], lernen: dict | None, notes: list[str]) -> list[dict]:
    from .. import llm
    data = {"trends_und_news": [{"name": k, **{x: v for x, v in c.items() if x in ("typ", "kategorie", "warum")}}
                                for k, c in cand.items()]}
    if lernen:
        data["gelernt"] = json.dumps(lernen, ensure_ascii=False)[:1500]
    user = (f"Daten (JSON):\n{json.dumps(data, ensure_ascii=False)}\n\n"
            f"Je Bereich {PER_AREA[0]} bis {PER_AREA[1]} Ideen: {', '.join(AREAS)}.")
    answer = llm.chat_json(SYSTEM, user, temperature=0.5, timeout=90)
    ideas = answer.get("ideen")
    if not isinstance(ideas, list):
        raise ValueError("Antwort ohne Ideenliste")
    return [i for i in ideas if isinstance(i, dict)]


def rule_ideas(trends: dict, cand: dict[str, dict], presets: dict[str, dict]) -> list[dict]:
    """Ohne Sprachmodell: Ideen direkt aus den Trends (nur Themen, nichts Erfundenes)."""
    ideas = []
    for t in (trends.get("themen") or [])[:25]:
        name, cat = t["thema"], t.get("kategorie", "Thema")
        if name not in cand or len(name) > 70:
            continue
        if cand[name].get("heikel"):
            ideas.append({"bereich": "reportage", "titel": f"Was wir über {name} wissen"[:60],
                          "thema": f"Sachliche Reportage: {name}", "quelle_trend": name})
            continue
        reddit = any(q["quelle"] == "reddit" for q in t.get("quellen", []))
        if reddit:
            ideas.append({"bereich": "story", "titel": name[:60], "thema": f"Geschichte rund um: {name}",
                          "quelle_trend": name})
        elif cat == "Person":
            ideas.append({"bereich": "fakten", "titel": f"Was du über {name} wissen solltest"[:60],
                          "thema": f"Fakten über {name}", "quelle_trend": name})
        elif cat == "Ereignis":
            ideas.append({"bereich": "erklaer", "titel": f"Was steckt hinter {name}?"[:60],
                          "thema": f"Hintergrund erklärt: {name}", "quelle_trend": name})
        else:
            ideas.append({"bereich": "fakten", "titel": f"{name}: die wichtigsten Fakten"[:60],
                          "thema": f"Fakten über {name}", "quelle_trend": name})
        pid = preset_match(name, presets)
        if pid:
            ideas.append({"bereich": "ranking", "titel": presets[pid].get("title", {}).get("de", pid)[:60],
                          "thema": presets[pid].get("title", {}).get("de", pid).replace("{count}", "10"),
                          "quelle_trend": name})
    return ideas


def finish(raw: list[dict], cand: dict[str, dict], presets: dict[str, dict], use_llm: bool, notes: list[str],
           known: set[str]) -> list[dict]:
    per_area = {a: 0 for a in AREAS}
    probes = [MAX_PROBES]
    out = []
    for r in raw:
        area = str(r.get("bereich", "")).strip().lower()
        titel, thema = str(r.get("titel", "")).strip()[:80], str(r.get("thema", "")).strip()[:160]
        src = match_source(str(r.get("quelle_trend", "")), cand)
        if area not in AREAS or not titel or not thema or not src:
            continue                                      # ohne Beleg in den Daten keine Idee
        if area == "ranking" and META_RANKING.search(f"{titel} {thema}"):
            continue                                      # Ranking über Klicks/Suchbegriffe: keine messbaren Dinge
        if area == "story" and cand[src].get("typ") == "news":
            area = "reportage"                            # echte Nachrichten nie als erzählte Story
        if cand[src].get("heikel") or area == "reportage":
            area = "reportage"                            # Leid nie als Unterhaltung – nur sachliche Reportage
        ident = "idee-" + hashlib.sha1(f"{area}|{_norm(thema)}".encode()).hexdigest()[:8]
        if ident in known or per_area[area] >= PER_AREA[1]:
            continue
        per_area[area] += 1
        check = (check_ranking(thema, 10, presets, probes, use_llm) if area == "ranking"
                 else {"geprueft": "idee", "hinweis": REPORTAGE_REGELN if area == "reportage"
                       else "Fakten entstehen erst in der geprüften Pipeline"})
        order = build_order(area, {"thema": thema}, check)
        problem = validate_order(order, presets)
        if problem:
            check = {"geprueft": "idee", "hinweis": f"Auftrag unvollständig: {problem}"}
            order = build_order(area, {"thema": thema}, {})
        entry = {"id": ident, "bereich": area, "titel": titel, "thema": thema,
                 "begruendung": str(r.get("begruendung") or cand[src]["warum"])[:240],
                 "quelle": {"name": src, **{k: v for k, v in cand[src].items() if k in ("typ", "score", "quellen")}},
                 "geprueft": check["geprueft"], "hinweis": check.get("hinweis", ""),
                 "auftrag": order, "app_auftrag": bool(order and order["art"] != "erklaer"), "erstellt": iso()}
        if area == "reportage":
            entry["regeln"] = REPORTAGE_REGELN
        if check.get("plan"):
            entry["plan"] = check["plan"]
        out.append(entry)
    return out


def run() -> dict:
    started = time.monotonic()
    notes: list[str] = []
    trends = common.read_json("trends.json", {}) or {}
    news = common.read_json("news.json", {}) or {}
    lernen = common.read_json("lernen.json")
    previous = common.read_json("ideen.json", {}) or {}
    cand = candidates(trends, news)
    if not cand:
        common.record_status("ideen", started, False, "keine Trends/News vorhanden", ["erst Trend-Scout/News-Reporter laufen lassen"])
        return previous
    presets = load_presets()
    from .. import llm
    use_llm, mode, raw = llm.available(), "regeln", []
    if use_llm:
        try:
            try:
                raw = llm_ideas(cand, lernen, notes)
            except Exception as exc:                      # noqa: BLE001 – Gratis-Limit: einmal nach Pause wiederholen
                if "429" not in str(exc):
                    raise
                time.sleep(45)
                raw = llm_ideas(cand, lernen, notes)
            mode = "llm"
        except Exception as exc:                          # noqa: BLE001
            notes.append(f"Sprachmodell nicht nutzbar, regelbasiert: {common.short_error(exc)}")
            use_llm = False
    else:
        notes.append("kein Sprachmodell (CUDI_LLM_*) – regelbasierte Ideen")
    if not raw:
        raw = rule_ideas(trends, cand, presets)
    old = common.thin_by_age(previous.get("ideen", []), "erstellt", KEEP_DAYS)
    new = finish(raw, cand, presets, use_llm, notes, {i["id"] for i in old})
    ideas = new + old
    capped, count = [], {a: 0 for a in AREAS}
    for i in ideas:
        if count[i["bereich"]] < MAX_PER_AREA:
            count[i["bereich"]] += 1
            capped.append(i)
    data = {"erzeugt": iso(), "modus": mode, "hinweise": notes, "anzahl": len(capped),
            "neu": len(new), "ideen": capped}
    changed = common.write_json("ideen.json", data)
    common.record_status("ideen", started, True, f"{len(new)} neue Ideen ({mode})" + ("" if changed else " (unverändert)"), notes)
    return data
