"""Optional: Claude wählt Hook und Fenster (Schreibaufgabe „clip_hook“ über handoff, nur mit CUDI_SCHREIBEN=1).

Ohne Antwort oder bei ungültiger Antwort gelten die Regeln aus highlights.py."""

from __future__ import annotations

from .highlights import Fenster, Satz, hook_kandidaten

ANLEITUNG = (
    "Wähle für einen Hochformat-Clip (TikTok/Shorts) aus einem Gespräch den stärksten Hook. Gut ist eine direkte "
    "Konfrontation oder provokante Frage ans Gegenüber (du/dir/dich, „ich glaube nicht …“, „stimmt das …“), auf die "
    "eine starke Reaktion folgt (Verneinung, Wiederholung, Lautstärke, Sprecherwechsel). Der Hook soll am Anfang des "
    "Clips stehen; der Clip beginnt dann genau dort und läuft 30–90 s weiter bis zu einer Pointe. Du bekommst die "
    "besten Kandidaten (nr, Text, Zeit, Punkte) mit dem vorgeschlagenen Clip-Ende. Antworte als JSON: "
    '{"nr": <Nummer>, "begruendung": "<ein Satz>"}. Erfinde nichts, wähle nur aus den Kandidaten.'
)


def _fenster_ab(saetze: list[Satz], start_idx: int, max_s: float, ziel_s: float = 60.0) -> Fenster:
    """Fenster ab Satz `start_idx`: möglichst nahe `ziel_s`, höchstens `max_s`, an Satzenden."""
    a = saetze[start_idx]
    ende_idx = start_idx
    for j in range(start_idx, len(saetze)):
        d = saetze[j].ende - a.start
        if d > max_s:
            break
        ende_idx = j
        if d >= ziel_s:
            break
    sel = saetze[start_idx:ende_idx + 1]
    return Fenster(a.start, sel[-1].ende, sum(s.wert for s in sel), sel)


def claude_waehlen(saetze: list[Satz], max_s: float) -> tuple[Fenster, Satz] | None:
    """(Fenster, Hook) laut Claude oder None. Wirft handoff.WritingNeeded, wenn die Aufgabe erst abgelegt wurde."""
    from .. import handoff

    if not handoff.enabled() or not saetze:
        return None
    alle = Fenster(saetze[0].start, saetze[-1].ende, 0.0, list(saetze))
    kand = hook_kandidaten(alle, 5)
    if not kand:
        return None
    daten = {"kandidaten": [], "max_laenge_s": max_s}
    for nr, k in enumerate(kand, 1):
        idx = next(i for i, s in enumerate(saetze) if s.i0 == k.i0)
        fe = _fenster_ab(saetze, idx, max_s)
        daten["kandidaten"].append({"nr": nr, "text": k.text, "start": round(k.start, 1), "ende": round(k.ende, 1),
                                    "punkte": round(k.hook_wert, 1), "clip_ende": round(fe.ende, 1)})
    antwort = handoff.request("clip_hook", ANLEITUNG, daten)
    try:
        nr = int(antwort["nr"]) if isinstance(antwort, dict) else int(antwort)
    except (TypeError, ValueError, KeyError):
        return None
    if not 1 <= nr <= len(kand):
        return None
    k = kand[nr - 1]
    idx = next(i for i, s in enumerate(saetze) if s.i0 == k.i0)
    return _fenster_ab(saetze, idx, max_s), k
