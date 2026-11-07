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
    hook_wert: float = 0.0

    @property
    def dauer(self) -> float:
        return self.ende - self.start


@dataclass
class Fenster:
    start: float
    ende: float
    wert: float
    saetze: list[Satz] = field(default_factory=list)


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
        hook = (2.5 if frage else 0) + min(konflikt, 2) * 1.2 + min(emo, 2) * 0.4 + (0.8 if wiederholung else 0)
        hook += 0.7 if any(t in ANREDE[lg] for t in toks) else 0
        hook += 0.5 * min(max(laut - 1.0, 0), 1.0)
        s.hook_wert = hook


def fenster_finden(saetze: list[Satz], min_s: float = 30.0, max_s: float = 90.0) -> Fenster:
    """Bestes Fenster an Satzgrenzen: Dichte der Punkte, starker Einstieg, Pointe am Ende, Länge."""
    if not saetze:
        raise ValueError("keine Sätze")
    gesamt = saetze[-1].ende - saetze[0].start
    if gesamt <= max_s:
        return Fenster(saetze[0].start, saetze[-1].ende, sum(s.wert for s in saetze), list(saetze))
    min_s = min(min_s, gesamt)
    pref = np.concatenate([[0.0], np.cumsum([s.wert for s in saetze])])
    beste: Fenster | None = None
    for a in range(len(saetze)):
        for b in range(a, len(saetze)):
            dauer = saetze[b].ende - saetze[a].start
            if dauer > max_s:
                break
            if dauer < min_s:
                continue
            dichte = (pref[b + 1] - pref[a]) / dauer * 30.0
            einstieg = 0.4 * saetze[a].hook_wert
            lastend = saetze[b]
            pointe = 0.5 * min(lastend.wert, 4.0) + (0.8 if lastend.dauer < 5 and lastend.wert >= 1.0 else 0)
            laenge = 3.0 * min(dauer, 75.0) / 75.0
            wert = dichte + einstieg + pointe + laenge
            if beste is None or wert > beste.wert:
                beste = Fenster(saetze[a].start, saetze[b].ende, wert, saetze[a:b + 1])
    if beste is None:  # nur riesige Sätze
        beste = Fenster(saetze[0].start, min(saetze[-1].ende, saetze[0].start + max_s), 0.0, saetze[:1])
    return beste


def fenster_erzwingen(saetze: list[Satz], start: float, ende: float) -> Fenster:
    sel = [s for s in saetze if s.ende > start and s.start < ende]
    return Fenster(start, ende, sum(s.wert for s in sel), sel)


def hook_finden(fenster: Fenster, schwelle: float = 2.0) -> Satz | None:
    """Stärkster Hook (2–7 s) im Fenster: ein Satz oder zwei aufeinanderfolgende (Frage + Widerspruch).

    Rückgabe ist ein Satz-Objekt; bei Paaren umfasst es beide Sätze (i0..i1, start..ende)."""
    kand: list[Satz] = []
    sats = fenster.saetze
    for k, s in enumerate(sats):
        if 1.5 <= s.dauer <= 7.0 and s.hook_wert >= schwelle:
            kand.append(s)
        if k + 1 < len(sats):
            n = sats[k + 1]
            if n.start - s.ende < 0.8 and 2.0 <= n.ende - s.start <= 7.0:
                wert = s.hook_wert + 0.8 * n.hook_wert
                if wert >= schwelle and s.hook_wert >= 1.5:
                    kand.append(Satz(s.i0, n.i1, s.start, n.ende, s.text + " " + n.text, s.wert + n.wert, wert))
    if not kand:
        return None
    return max(kand, key=lambda x: (x.hook_wert, -x.start))


def braucht_teaser(hook: Satz, fenster: Fenster, toleranz: float = 1.0) -> bool:
    """Cold Open nötig, wenn der Hook nicht ohnehin am Fensteranfang steht."""
    return hook.start - fenster.start > toleranz
