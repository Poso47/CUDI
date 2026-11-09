"""Höhepunkt und Hook per Regeln (ohne KI)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import numpy as np

FRAGEWOERTER = {"de": {"wie", "warum", "wieso", "weshalb", "was", "wer", "wann", "wo", "welche", "woher", "wohin", "wozu"},
                "en": {"how", "why", "what", "who", "when", "where", "which"}}
EMOTION = {
    "de": {"nein", "niemals", "nie", "warum", "wieso", "krass", "ehrlich", "ehrlicherweise", "unfassbar", "verrückt",
           "wahnsinn", "scheiße", "scheisse", "lüge", "luege", "lügst", "falsch", "stimmt", "quatsch", "blödsinn",
           "bullshit", "hass", "angst", "schlimm", "geil", "absolut", "komplett", "wirklich", "echt", "unmöglich",
           "gefährlich", "schockierend", "peinlich", "respektlos", "dumm", "schwachsinn",
           "beweis", "beweise", "sorry", "boah"},
    "en": {"no", "never", "why", "crazy", "honestly", "insane", "wrong", "lie", "liar", "bullshit", "hate", "fear",
           "terrible", "shocking", "stupid", "impossible", "dangerous", "seriously", "actually", "literally", "proof"},
}
KONFLIKT = {
    "de": {"nein", "niemals", "lüge", "luege", "falsch", "glaube nicht", "stimmt nicht", "quatsch", "blödsinn",
           "unmöglich", "recherchierst", "beweis", "bullshit", "schwachsinn", "du lügst", "keine ahnung"},
    "en": {"no", "never", "lie", "wrong", "don't think", "not true", "bullshit", "impossible", "prove"},
}
ANREDE = {"de": {"du", "dich", "dir", "dein", "deine", "sie", "ihr", "euch"}, "en": {"you", "your"}}
STOP = {"de": {"der", "die", "das", "den", "dem", "des", "ein", "eine", "einen", "und", "oder", "aber", "ich", "du", "er",
               "sie", "es", "wir", "ihr", "ist", "sind", "war", "hat", "haben", "nicht", "auch", "nur", "noch", "dass",
               "wenn", "weil", "mit", "von", "für", "auf", "bei", "aus", "nach", "wie", "was", "wer", "als", "zu",
               "im", "in", "an", "am", "um", "so", "da", "dann", "mal", "ja", "doch", "den", "mich", "mir", "dich",
               "dir", "sich", "man", "wird", "kann", "muss", "habe", "bin", "bist", "sein", "ganz", "schon", "hier",
               "dort", "denn", "also", "eben", "halt", "mein", "meine", "dein", "deine", "diese", "dieser", "dieses",
               "gibt", "gar", "sehr", "viel", "mehr", "wenn", "wurde", "worden", "etwas", "jetzt", "immer", "wieder"},
        "en": {"the", "a", "an", "and", "or", "but", "i", "you", "he", "she", "it", "we", "they", "is", "are", "was",
               "were", "have", "has", "had", "not", "to", "of", "in", "on", "at", "for", "with", "that", "this", "so",
               "just", "like", "my", "your", "be", "do", "does", "did", "what", "how", "if", "then", "there"}}


def _norm(w: str) -> str:
    return re.sub(r"[^\wäöüßÄÖÜ]", "", w.lower())


def _lang(sprache: str | None) -> str:
    return "en" if sprache == "en" else "de"


@dataclass
class Satz:
    i0: int  # Index erstes Wort
    i1: int  # Index letztes Wort (einschließlich)
    start: float
    ende: float
    text: str
    wert: float = 0.0
    hook_wert: float = 0.0   # beste Hook-Punkte eines Kandidaten, der an diesem Satz beginnt
    hook_n: int = 1          # Sätze dieses Kandidaten (1 oder 2)
    laut: float = 1.0

    @property
    def dauer(self) -> float:
        return self.ende - self.start


@dataclass
class Fenster:
    start: float
    ende: float
    wert: float
    saetze: list[Satz] = field(default_factory=list)
    signale: dict = field(default_factory=dict)      # Einzelwerte der Auswahl (für Prüfbericht und Kalibrierung)


def saetze_bilden(words: list[dict]) -> list[Satz]:
    """Sätze an . ? ! … oder langen Pausen (> 0.8 s); lange Sätze ohne Zeichen zusätzlich bei Pausen > 0.45 s ab 8 s."""
    out: list[Satz] = []
    i0 = 0
    for i, w in enumerate(words):
        letzt = i == len(words) - 1
        ende_zeichen = bool(re.search(r"[.?!…]+[\"”“)]*$", w["w"]))
        luecke = (words[i + 1]["s"] - w["e"]) if not letzt else 99
        lang = words[i]["e"] - words[i0]["s"]
        if letzt or ende_zeichen or luecke > 0.8 or (lang > 8 and luecke > 0.45) or lang > 14:
            out.append(Satz(i0, i, words[i0]["s"], w["e"], " ".join(x["w"] for x in words[i0:i + 1])))
            i0 = i + 1
    return out


def bewerte(saetze: list[Satz], words: list[dict], audio_rms: np.ndarray, audio_offset: float,
            sprache: str | None = "de", rms_schritt: float = 0.1) -> None:
    """Setzt `wert` (Gesamtpunkte) und `hook_wert` (Frage/Konflikt) je Satz."""
    lg = _lang(sprache)
    median = float(np.median(audio_rms[audio_rms > 1e-5])) if (audio_rms > 1e-5).any() else 1e-5
    raten = [(s.i1 - s.i0 + 1) / max(s.dauer, 0.3) for s in saetze]
    med_rate = float(np.median(raten)) if raten else 2.5
    for s, rate in zip(saetze, raten):
        toks = [_norm(w["w"]) for w in words[s.i0:s.i1 + 1]]
        text = " ".join(toks)
        frage = s.text.rstrip().endswith("?") or (toks and toks[0] in FRAGEWOERTER[lg] and len(toks) >= 4)
        ausruf = s.text.rstrip().endswith("!")
        emo = sum(1 for t in toks if t in EMOTION[lg])
        konflikt = sum(1 for k in KONFLIKT[lg] if re.search(r"\b" + re.escape(k) + r"\b", text))
        wiederholung = any(a == b and a for a, b in zip(toks, toks[1:]))
        zahlen = sum(1 for t in toks if t.isdigit())
        a, b = int((s.start - audio_offset) / rms_schritt), int((s.ende - audio_offset) / rms_schritt) + 1
        seg = audio_rms[max(0, a):max(a + 1, b)]
        laut = float(seg.mean()) / median if len(seg) else 1.0
        spitze = float(seg.max()) / median if len(seg) else 1.0
        wert = (2.0 if frage else 0) + (1.0 if ausruf else 0) + min(emo, 3) * 0.8 + min(konflikt, 2) * 1.0
        wert += 1.0 if wiederholung else 0
        wert += 0.5 * min(zahlen, 2)
        wert += 1.2 * min(max(laut - 1.0, 0), 1.5) + 0.4 * min(max(spitze - 2.0, 0), 2)
        wert += 0.6 if rate > 1.2 * med_rate else 0
        s.wert = wert
        s.laut = laut
        s.frage, s.ausruf = bool(frage), ausruf
    _hooks_bewerten(saetze, words, lg)


NEGATION = {"de": {"nein", "niemals", "nie", "quatsch", "falsch", "blödsinn", "stimmt nicht", "doch"},
            "en": {"no", "never", "wrong", "nonsense", "not true", "nope"}}
KONFRONTATION = {"de": [r"\bich glaub(e)? (das )?nicht\b", r"\bstimmt das\b", r"\bglaubst du\b", r"\bbist du\b",
                        r"\bhast du\b", r"\bwillst du\b", r"\bdu (lügst|hast|bist|kannst|musst|sagst)\b",
                        r"\bwie kannst du\b", r"\bwarum (tust|machst|sagst|glaubst) du\b"],
                 "en": [r"\bi don'?t think\b", r"\bis that true\b", r"\bdo you (really|even)\b", r"\byou('re| are)\b",
                        r"\bhow (can|could|do) you\b"]}


def _hook_punkte(toks: list[str], text: str, frage: bool, lg: str) -> float:
    anrede = any(t in ANREDE[lg] for t in toks)
    p = 0.0
    if frage:
        p += 1.5
    if frage and anrede:
        p += 3.0                                  # direkte Frage ans Gegenüber
    p += 2.0 * min(sum(1 for r in KONFRONTATION[lg] if re.search(r, text)), 2) / 1.0 * 0.6
    p += min(sum(1 for k in KONFLIKT[lg] if re.search(r"\b" + re.escape(k) + r"\b", text)), 2) * 1.0
    p += 0.6 if anrede else 0
    return p


def _hooks_bewerten(saetze: list[Satz], words: list[dict], lg: str) -> None:
    """Hook-Kandidaten (1–2 Sätze, 1,5–8,5 s): Konfrontation (du + Frage, „ich glaube nicht“, „stimmt das“)
    plus starke Reaktion im Anschluss (Verneinung, Wiederholung, laut)."""
    n = len(saetze)
    for i, s in enumerate(saetze):
        beste, bn = 0.0, 1
        for k in (1, 2):
            j = i + k - 1
            if j >= n or (k == 2 and saetze[j].start - saetze[j - 1].ende > 0.8):
                break
            dauer = saetze[j].ende - s.start
            if dauer > 8.5 or (k == 1 and dauer < 1.5):
                continue
            ws = words[s.i0:saetze[j].i1 + 1]
            toks = [_norm(w["w"]) for w in ws]
            text = " ".join(toks)
            frage = any(x.text.rstrip().endswith("?") for x in saetze[i:j + 1])
            p = _hook_punkte(toks, text, frage, lg)
            nach = saetze[j + 1] if j + 1 < n and saetze[j + 1].start - saetze[j].ende < 1.5 else None
            if nach is not None and p > 0:
                nt = [_norm(w["w"]) for w in words[nach.i0:nach.i1 + 1]]
                ntext = " ".join(nt)
                reaktion = 0.0
                if any(t in NEGATION[lg] for t in nt[:4]):
                    reaktion += 2.0
                if any(a == b and a for a, b in zip(nt, nt[1:])):
                    reaktion += 1.5
                reaktion += min(max(nach.laut - 1.0, 0), 1.0) + (0.5 if nach.text.rstrip().endswith("!") else 0)
                p += reaktion
            if k == 2:
                p -= 0.3          # lieber der knappe Hook
            if p > beste:
                beste, bn = p, k
        s.hook_wert, s.hook_n = beste, bn


OFFEN_ENDE = {"de": {"und", "aber", "oder", "weil", "dass", "denn", "also", "dann", "sondern", "wenn", "als", "mit",
                     "der", "die", "das", "ein", "eine", "zu", "von", "für", "ich", "wir", "es", "ja", "ähm", "äh"},
              "en": {"and", "but", "or", "because", "that", "so", "then", "if", "when", "the", "a", "an", "to", "of",
                     "with", "i", "we", "it", "um", "uh"}}
RUECKBEZUG = {"de": {"das", "dann", "deshalb", "deswegen", "darum", "also", "und", "aber", "dort", "dabei", "danach",
                     "daher", "genau", "eben", "ja", "sie", "er", "es", "dieser", "diese", "dieses"},
              "en": {"and", "but", "so", "then", "that", "this", "those", "these", "he", "she", "they", "it"}}


def offenes_ende(text: str, sprache: str | None = "de") -> bool:
    """Endet der Satz mitten im Gedanken (kein Satzzeichen, Bindewort/Artikel am Schluss, Gedankenstrich)?"""
    t = text.strip()
    if not t:
        return True
    if re.search(r"[.?!…][\"”“)]*$", t):
        return bool(re.search(r"(\.\.\.|…)$", t))
    letzt = _norm(t.split()[-1])
    return bool(re.search(r"[,;:–-]$", t)) or letzt in OFFEN_ENDE[_lang(sprache)]


def rueckbezug_start(text: str, sprache: str | None = "de") -> bool:
    """Beginnt der Ausschnitt mit einem Rückbezug („und dann“, „das war“) – ohne Vorwissen schwer verständlich?"""
    toks = [_norm(w) for w in text.split()[:2]]
    return bool(toks) and toks[0] in RUECKBEZUG[_lang(sprache)]


def titel_treffer(satz_text: str, titel: str, sprache: str | None = "de") -> int:
    """Wie viele Inhaltswörter des Videotitels kommen im Text vor?"""
    lg = _lang(sprache)
    tw = {_norm(w) for w in titel.split() if len(_norm(w)) >= 4 and _norm(w) not in STOP[lg]}
    sw = {_norm(w) for w in satz_text.split()}
    return len(tw & sw)


def _gewicht(g: dict | None, name: str) -> float:
    return float((g or {}).get(name, 1.0))


def fenster_rangliste(saetze: list[Satz], min_s: float = 30.0, max_s: float = 90.0, schnitte: list[float] | None = None,
                      titel: str = "", gewichte: dict | None = None, sprache: str | None = "de",
                      anzahl: int = 3) -> list[Fenster]:
    """Die besten Fenster (sich nicht überlappend) an Satzgrenzen. Bewertet werden: Dichte der Punkte, starker Einstieg,
    Pointe am Ende, Länge, Treffer des Videotitels, Episodenanfang (Szenenschnitt) bzw. Schnitt mitten im Fenster
    (zwei Episoden) und ein offenes Ende (endet mitten im Gedanken)."""
    if not saetze:
        raise ValueError("keine Sätze")
    schnitte = schnitte or []
    gesamt = saetze[-1].ende - saetze[0].start
    if gesamt <= max_s and not schnitte:
        return [Fenster(saetze[0].start, saetze[-1].ende, sum(s.wert for s in saetze), list(saetze))]
    min_s = min(min_s, gesamt)
    pref = np.concatenate([[0.0], np.cumsum([s.wert for s in saetze])])
    treffer = [titel_treffer(s.text, titel, sprache) if titel else 0 for s in saetze]
    th = np.concatenate([[0], np.cumsum(treffer)])
    offen = [offenes_ende(s.text, sprache) for s in saetze]
    alle: list[Fenster] = []
    for a in range(len(saetze)):
        for b in range(a, len(saetze)):
            dauer = saetze[b].ende - saetze[a].start
            if dauer > max_s:
                break
            if dauer < min_s and not (a == 0 and b == len(saetze) - 1):
                continue
            dichte = (pref[b + 1] - pref[a]) / max(dauer, 1.0) * 30.0
            einstieg = 1.2 * saetze[a].hook_wert
            lastend = saetze[b]
            pointe = 0.5 * min(lastend.wert, 4.0) + (0.8 if lastend.dauer < 5 and lastend.wert >= 1.0 else 0)
            laenge = 3.0 * min(dauer, 75.0) / 75.0
            t_wert = 1.0 * min(int(th[b + 1] - th[a]), 3)
            kreuzt = sum(1 for c in schnitte if saetze[a].start + 1.5 < c < saetze[b].ende - 1.0)
            episode = any(-0.6 <= saetze[a].start - c <= 1.5 for c in schnitte)
            szene = (2.0 if episode else 0.0) - 8.0 * min(kreuzt, 2)
            offen_w = -3.0 if offen[b] else 0.0
            sig = {"dichte": dichte, "einstieg": einstieg, "pointe": pointe, "laenge": laenge, "titel": t_wert,
                   "szene": szene, "offen": offen_w}
            wert = sum(_gewicht(gewichte, k) * v for k, v in sig.items())
            sig = {k: round(v, 2) for k, v in sig.items()}
            sig.update(kreuzt_schnitt=bool(kreuzt), episodenstart=bool(episode), offenes_ende=bool(offen[b]))
            alle.append(Fenster(saetze[a].start, saetze[b].ende, wert, saetze[a:b + 1], sig))
    if not alle:   # nur riesige Sätze
        return [Fenster(saetze[0].start, min(saetze[-1].ende, saetze[0].start + max_s), 0.0, saetze[:1])]
    alle.sort(key=lambda f: -f.wert)
    out: list[Fenster] = []
    for f in alle:
        if all(f.ende <= o.start or f.start >= o.ende for o in out):
            out.append(f)
            if len(out) >= anzahl:
                break
    return out


def fenster_finden(saetze: list[Satz], min_s: float = 30.0, max_s: float = 90.0, schnitte: list[float] | None = None,
                   titel: str = "", gewichte: dict | None = None, sprache: str | None = "de") -> Fenster:
    """Bestes Fenster (siehe `fenster_rangliste`)."""
    return fenster_rangliste(saetze, min_s, max_s, schnitte, titel, gewichte, sprache, 1)[0]


def fenster_erzwingen(saetze: list[Satz], start: float, ende: float) -> Fenster:
    sel = [s for s in saetze if s.ende > start and s.start < ende]
    return Fenster(start, ende, sum(s.wert for s in sel), sel)


def _span(fenster: Fenster, k: int) -> Satz:
    s = fenster.saetze[k]
    if s.hook_n == 2 and k + 1 < len(fenster.saetze):
        n = fenster.saetze[k + 1]
        return Satz(s.i0, n.i1, s.start, n.ende, s.text + " " + n.text, s.wert + n.wert, s.hook_wert)
    return Satz(s.i0, s.i1, s.start, s.ende, s.text, s.wert, s.hook_wert)


def hook_kandidaten(fenster: Fenster, anzahl: int = 5, schwelle: float = 2.0) -> list[Satz]:
    """Beste Hook-Kandidaten im Fenster (Satz oder Satzpaar), nach Punkten sortiert."""
    out = []
    for k, s in enumerate(fenster.saetze):
        if s.hook_wert >= schwelle:
            sp = _span(fenster, k)
            if 1.5 <= sp.dauer <= 8.5:
                out.append((sp.hook_wert - 0.03 * (sp.start - fenster.start), sp))
    out.sort(key=lambda x: -x[0])
    return [sp for _w, sp in out[:anzahl]]


def hook_finden(fenster: Fenster, schwelle: float = 2.0) -> Satz | None:
    """Stärkster Hook im Fenster (Satz oder Satzpaar); bei Gleichstand der frühere."""
    kand = hook_kandidaten(fenster, 1, schwelle)
    return kand[0] if kand else None


def braucht_teaser(hook: Satz, fenster: Fenster, toleranz: float = 1.0) -> bool:
    """Cold Open nötig, wenn der Hook nicht ohnehin am Fensteranfang steht."""
    return hook.start - fenster.start > toleranz
