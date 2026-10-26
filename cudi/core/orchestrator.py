"""Orchestrator: zentrale Ablaufsteuerung von CUDI.

Nutzer → Absicht → Kontext/Gedächtnis → Modell oder Werkzeug → Berechtigung →
Ausführung → Qualitätsprüfung → Ergebnis → kontrollierte Speicherung.

Die GUI/CLI ruft nur ``handle(text)`` und ``resolve(pending_id, approved)`` auf.
"""

from __future__ import annotations

import logging
import threading
import uuid
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any, Dict, List, Optional

from ..brain.memory import canonical_statement
from ..brain.projects import ENTRY_KINDS
from ..models.base import ToolCall
from ..models.model_manager import SETUP_HINT, NoModelAvailable
from ..tools.registry import ToolOutput
from . import intent_router
from .intent_router import Intent
from .permissions import LEVEL_LABELS, Level
from .persona import system_prompt
from .results import ANSWER, CONFIRM, ERROR, QUESTION, Action, Result

if TYPE_CHECKING:  # pragma: no cover
    from .application import Application

log = logging.getLogger("cudi.core")

NO_MODEL_NOTE = ("Hinweis: Gerade ist kein Sprachmodell verbunden. Befehle, Gedächtnis, Projekte und "
                 "Dokumentsuche funktionieren trotzdem – /hilfe zeigt alles. /modelle erklärt die Einrichtung.")

HELP_TEXT = """Du kannst ganz normal mit mir reden. Zusätzlich gibt es Kurzbefehle:

Gedächtnis
  „Merke dir: …“ / /merke TEXT     etwas dauerhaft speichern
  /erinnerungen [Suchwort]         gespeicherte Erinnerungen anzeigen
  /korrigiere ID NEUER TEXT        Erinnerung korrigieren
  „Vergiss #ID“ / /vergiss ID      Erinnerung löschen (mit Rückfrage)
  „Künftig …“                      Vorliebe für die Zukunft festhalten
  „Das war richtig/falsch“         Feedback zur letzten Antwort

Projekte & Aufgaben
  /projekt neu NAME | ZWECK        Projekt anlegen
  /projekt NAME                    Projekt wechseln
  /projekte, /projektstand         Übersicht / Stand des aktiven Projekts
  /entscheidung, /problem, /lösung, /schritt, /ziel, /notiz, /erkenntnis TEXT
  /aufgabe TEXT, /aufgaben, /erledigt ID

Dokumente & Dateien
  /import PFAD                     Dokument importieren (PDF, DOCX, TXT, MD, JSON, CSV)
  /importordner                    alles aus dem Ordner „import“ übernehmen
  /dokumente, /suche TEXT          Dokumente anzeigen / durchsuchen
  /dateien [PFAD], /lesen PFAD     Arbeitsordner anzeigen / Datei lesen

System
  /status                          Selbstdiagnose
  /modelle                         Sprachmodelle und Einrichtung
  /sicherung, /sicherungen, /wiederherstellen DATEI, /export
  /altwissen                       altes CUDI-Wissen (vorläufig) übernehmen
  /erlauben WERKZEUG               Werkzeug für diese Sitzung ohne Rückfrage erlauben
  /neu                             neues Gespräch beginnen"""

ENTRY_COMMANDS = {
    "entscheidung": "decision", "problem": "issue", "lösung": "solution", "loesung": "solution",
    "schritt": "next_step", "ziel": "goal", "notiz": "note", "erkenntnis": "insight",
    "anforderung": "requirement",
}


@dataclass
class LoopState:
    """Zustand einer laufenden Modell-Werkzeug-Schleife (für Unterbrechung durch Rückfrage)."""

    system: str
    messages: List[Dict[str, Any]]
    provider: Optional[str] = None
    model_label: Optional[str] = None
    iterations: int = 0
    actions: List[Action] = field(default_factory=list)
    sources: List[str] = field(default_factory=list)
    remaining_calls: List[ToolCall] = field(default_factory=list)


@dataclass
class Pending:
    id: str
    tool: str
    args: Dict[str, Any]
    description: str
    level: int
    loop: Optional[LoopState] = None
    call_id: Optional[str] = None


class Orchestrator:
    def __init__(self, app: "Application"):
        self.app = app
        self.pending: Dict[str, Pending] = {}
        self._lock = threading.RLock()

    # ================================================================ Einstieg
    def handle(self, text: str) -> Result:
        text = (text or "").strip()
        if not text:
            return Result(QUESTION, "Ich habe keine Nachricht erhalten – was soll ich tun?")
        with self._lock:
            app = self.app
            user_msg_id = app.conversations.add("user", text)
            try:
                result = self._dispatch(text, user_msg_id)
            except Exception as e:  # letzte Absicherung – Fehler sichtbar machen, nie verschweigen
                log.exception("Unerwarteter Fehler bei der Verarbeitung")
                app.episodes.record("error", f"Unerwarteter Fehler: {e}", ok=False)
                result = Result(
                    ERROR,
                    "Da ist intern etwas schiefgegangen – ich habe den Fehler protokolliert (logs/cudi.log). "
                    "Deine Daten sind unverändert. Versuch es bitte noch einmal oder gib /status ein.",
                    details=f"{type(e).__name__}: {e}",
                )
            self._store_reply(result)
            return result

    def resolve(self, pending_id: str, approved: bool, remember_choice: bool = False) -> Result:
        """Antwort des Nutzers auf eine Bestätigungsfrage (Ja/Nein)."""
        with self._lock:
            pending = self.pending.pop(pending_id, None)
            if not pending:
                result = Result(ERROR, "Diese Rückfrage ist nicht mehr offen (vielleicht schon beantwortet).")
            else:
                self.app.conversations.add("user", "Ja" if approved else "Nein")
                if approved and remember_choice:
                    self.app.permissions.grant_for_session(pending.tool)
                result = self._continue_pending(pending, approved)
            self._store_reply(result)
            return result

    def run_tool(self, name: str, args: Optional[Dict[str, Any]] = None) -> Result:
        """Direkter Werkzeugaufruf aus der Oberfläche (z. B. Knopf „Dokument importieren“)."""
        with self._lock:
            result = self._tool_result(name, args or {}, user_initiated=True)
            self._store_reply(result)
            return result

    def new_conversation(self) -> None:
        with self._lock:
            self.pending.clear()
            self.app.working.open_question = None
            self.app.conversations.new_conversation()

    # ============================================================ Verteilung
    def _dispatch(self, text: str, user_msg_id: int) -> Result:
        app = self.app
        # 1. Offene Rückfragen (Bestätigung oder Widerspruch) mit Ja/Nein beantworten
        if self.pending and (intent_router.is_yes(text) or intent_router.is_no(text)):
            pending = list(self.pending.values())[-1]
            del self.pending[pending.id]
            return self._continue_pending(pending, intent_router.is_yes(text))
        question = app.working.open_question
        if question and (intent_router.is_yes(text) or intent_router.is_no(text)):
            app.working.open_question = None
            return self._answer_open_question(question, intent_router.is_yes(text))
        app.working.open_question = None  # neue Anfrage statt Antwort
        if self.pending:
            # Neue Anfrage statt Antwort: offene Bestätigungen verfallen sichtbar
            dropped = ", ".join(p.tool for p in self.pending.values())
            self.pending.clear()
            log.info("Offene Bestätigung verworfen: %s", dropped)

        intent = intent_router.route(text)
        handler = {
            "command": self._command,
            "remember": self._remember,
            "forget": self._forget,
            "preference": self._preference,
            "feedback": self._feedback,
            "solution_feedback": self._solution_feedback,
            "save_insight": self._save_insight,
        }.get(intent.kind)
        if handler:
            return handler(intent)

        if app.models.has_model():
            return self._llm_turn(text, user_msg_id)
        return self._offline(intent, text)

    def _store_reply(self, result: Result) -> None:
        meta = {"kind": result.kind, "model": result.model,
                "actions": [a.line() for a in result.actions], "sources": result.sources}
        self.app.conversations.add("assistant", result.render(), meta=meta)

    # ======================================================= Werkzeugaufrufe
    def _tool_result(self, name: str, args: Dict[str, Any], user_initiated: bool = False,
                     intro: str = "") -> Result:
        """Werkzeug außerhalb der Modellschleife ausführen (Befehle, Regeln, Oberfläche)."""
        tool = self.app.tools.get(name)
        if tool is None:
            return Result(ERROR, f"Das Werkzeug '{name}' gibt es nicht.")
        # Vom Nutzer direkt in der Oberfläche ausgewählt (z. B. Datei im Dialog gewählt) gilt als
        # Freigabe für das Lesen dieser Datei; die Grundstufe des Werkzeugs gilt weiterhin.
        level = tool.level if user_initiated else tool.effective_level(args)
        if self.app.permissions.needs_confirmation(name, level):
            return self._ask_confirmation(Pending(uuid.uuid4().hex[:10], name, args, tool.call_text(args), level),
                                          intro)
        output = self.app.tools.execute(name, args)
        return self._output_result(name, output, intro)

    def _output_result(self, name: str, output: ToolOutput, intro: str = "") -> Result:
        action = Action(name, output.ok, output.summary, "ausgeführt" if output.ok else "fehlgeschlagen")
        text = (intro + "\n\n" if intro else "") + output.content
        return Result(ANSWER if output.ok else ERROR, text, actions=[action], sources=output.sources)

    def _ask_confirmation(self, pending: Pending, intro: str = "") -> Result:
        self.pending[pending.id] = pending
        label = LEVEL_LABELS.get(Level(min(pending.level, 5)), "")
        text = (f"{intro}\n\n" if intro else "") + (
            f"Bevor ich das mache, brauche ich deine Freigabe:\n• {pending.description}\n"
            f"(Stufe {pending.level}: {label}) – Soll ich? (ja/nein)"
        )
        model_label = pending.loop.model_label if pending.loop else None
        actions = pending.loop.actions[:] if pending.loop else []
        return Result(CONFIRM, text, pending_id=pending.id, model=model_label, actions=actions)

    def _continue_pending(self, pending: Pending, approved: bool) -> Result:
        if approved:
            output = self.app.tools.execute(pending.tool, pending.args)
            status = "ausgeführt" if output.ok else "fehlgeschlagen"
        else:
            output = ToolOutput(False, "Der Nutzer hat diese Aktion abgelehnt. Nicht erneut versuchen, "
                                       "sondern eine Alternative anbieten oder nachfragen.",
                                summary="vom Nutzer abgelehnt")
            status = "abgelehnt"
            self.app.episodes.record("permission_denied", pending.description, ok=False)
        action = Action(pending.tool, output.ok, output.summary, status)

        if pending.loop is None:
            if not approved:
                return Result(ANSWER, "Alles klar, ich lasse es.", actions=[action])
            return Result(ANSWER if output.ok else ERROR, output.content, actions=[action], sources=output.sources)

        loop = pending.loop
        loop.actions.append(action)
        loop.sources += output.sources
        loop.messages.append({"role": "tool", "tool_call_id": pending.call_id, "name": pending.tool,
                              "content": output.content, "is_error": not output.ok})
        return self._run_loop(loop)

    # ================================================== Regelbasierte Anliegen
    def _remember(self, intent: Intent) -> Result:
        content = canonical_statement(intent.data["content"])
        project = self.app.projects.active()
        result = self.app.memory.add(content, source="nutzer (ausdrücklich gespeichert)",
                                     project_id=project["id"] if project else None)
        if result.status == "duplicate":
            return Result(ANSWER, f"Das weiß ich schon: „{result.memory.content}“ (#{result.memory.id}).",
                          actions=[Action("remember", True, f"bereits gespeichert (#{result.memory.id})")])
        if result.status == "conflict":
            olds = result.conflicts
            self.app.working.open_question = {"type": "memory_conflict", "content": content,
                                              "old_ids": [m.id for m in olds]}
            listed = "\n".join(f"• #{m.id} „{m.content}“ (gespeichert {m.created_at[:10]}, Quelle: {m.source})"
                               for m in olds)
            return Result(QUESTION, f"Moment – das widerspricht dem, was ich gespeichert habe:\n{listed}\n"
                                    f"Neu: „{content}“\nSoll die neue Angabe die alte ersetzen? (ja/nein)")
        m = result.memory
        self.app.episodes.record("memory", f"gespeichert #{m.id}: {m.content}", ok=True)
        return Result(ANSWER, f"Gemerkt: „{m.content}“.",
                      actions=[Action("remember", True, f"gespeichert als #{m.id}")])

    def _answer_open_question(self, question: Dict[str, Any], yes: bool) -> Result:
        if question.get("type") == "memory_conflict":
            if yes:
                new = self.app.memory.replace(question["old_ids"], question["content"],
                                              source="nutzer (Korrektur bestätigt)")
                old = ", ".join(f"#{i}" for i in question["old_ids"])
                self.app.episodes.record("memory", f"Korrektur: {old} → #{new.id}", ok=True)
                return Result(ANSWER, f"Erledigt. Ab jetzt gilt: „{new.content}“. Die alte Angabe habe ich als "
                                      f"veraltet markiert (nicht gelöscht).",
                              actions=[Action("replace_memory", True, f"{old} → #{new.id}")])
            return Result(ANSWER, "Gut, ich behalte die bisherige Angabe und speichere die neue nicht.")
        return Result(ANSWER, "Alles klar.")

    def _forget(self, intent: Intent) -> Result:
        query = intent.data["query"].lstrip("#").strip()
        if query.isdigit():
            return self._tool_result("forget_memory", {"memory_id": int(query)})
        hits = self.app.memory.search(query, limit=5)
        if not hits:
            return Result(ANSWER, f"Ich habe nichts zu „{query}“ im Gedächtnis gefunden.")
        if len(hits) == 1:
            return self._tool_result("forget_memory", {"memory_id": hits[0].id},
                                     intro=f"Gefunden: {hits[0].line()}")
        listed = "\n".join(f"• {m.line()}" for m in hits)
        return Result(QUESTION, f"Ich habe mehrere passende Erinnerungen gefunden:\n{listed}\n"
                                f"Welche soll ich löschen? Schreib z. B. „vergiss #{hits[0].id}“.")

    def _preference(self, intent: Intent) -> Result:
        content = intent.data.get("content", "").strip()
        if not content:
            last = self.app.conversations.last_assistant_message()
            if not last:
                return Result(QUESTION, "Gern – wie genau möchtest du es künftig haben?")
            excerpt = last["content"].strip().replace("\n", " ")[:300]
            content = f"Der Nutzer möchte Antworten künftig so wie diese: „{excerpt}“"
        else:
            content = f"Vorliebe: künftig {content}"
        result = self.app.memory.add(content, source="nutzer (Vorliebe)", category="preference",
                                     check_conflicts=False)
        self.app.episodes.record("preference", content, ok=True)
        return Result(ANSWER, "Verstanden – das berücksichtige ich ab jetzt.",
                      actions=[Action("remember", True, f"Vorliebe gespeichert (#{result.memory.id})")])

    def _feedback(self, intent: Intent) -> Result:
        last = self.app.conversations.last_assistant_message()
        rating = intent.data["rating"]
        self.app.episodes.add_feedback(rating, intent.data.get("comment", ""), last["id"] if last else None)
        self.app.episodes.record("feedback", f"{'positiv' if rating > 0 else 'negativ'}: {intent.data.get('comment')}",
                                 ok=rating > 0)
        if rating > 0:
            return Result(ANSWER, "Danke, gut zu wissen – ich habe das als gelungen vermerkt.",
                          actions=[Action("feedback", True, "positives Feedback gespeichert")])
        return Result(QUESTION, "Danke für die Korrektur, ich habe sie vermerkt. Was ist richtig? "
                                "Wenn du es mir sagst, korrigiere ich es (bei gespeicherten Angaben auch im Gedächtnis).",
                      actions=[Action("feedback", True, "negatives Feedback gespeichert")])

    def _solution_feedback(self, intent: Intent) -> Result:
        worked = intent.data["worked"]
        last = self.app.conversations.last_assistant_message()
        excerpt = (last["content"].strip().replace("\n", " ")[:400] if last else "")
        project = self.app.projects.active()
        actions = []
        if project and excerpt:
            kind = "solution" if worked else "issue"
            prefix = "Funktioniert: " if worked else "Funktioniert NICHT: "
            self.app.projects.add_entry(project["id"], kind, prefix + excerpt, source="nutzer-feedback")
            actions.append(Action("add_project_entry", True, f"{ENTRY_KINDS[kind]} im Projekt „{project['name']}“"))
        self.app.episodes.add_feedback(1 if worked else -1, "Lösung " + ("funktioniert" if worked else "funktioniert nicht"),
                                       last["id"] if last else None)
        self.app.episodes.record("solution", ("funktioniert: " if worked else "gescheitert: ") + excerpt[:200],
                                 ok=worked, project_id=project["id"] if project else None)
        if worked:
            return Result(ANSWER, "Sehr gut! Ich habe die Lösung als funktionierend vermerkt"
                                  + (" – auch im Projekt." if actions else "."), actions=actions)
        return Result(QUESTION, "Schade. Ich habe vermerkt, dass dieser Ansatz nicht funktioniert, damit ich ihn "
                                "nicht wiederhole. Was genau passiert – gibt es eine Fehlermeldung?", actions=actions)

    def _save_insight(self, intent: Intent) -> Result:
        project = self.app.projects.active()
        last = self.app.conversations.last_assistant_message()
        if not project:
            return Result(QUESTION, "Für welches Projekt? Lege eins an mit /projekt neu NAME oder wechsle mit /projekt NAME.")
        if not last:
            return Result(QUESTION, "Welche Erkenntnis genau soll ich speichern?")
        content = last["content"].strip()[:1000]
        return self._tool_result("add_project_entry", {"kind": intent.data["kind"], "content": content,
                                                       "project": project["name"]})

    # ================================================================ Befehle
    def _command(self, intent: Intent) -> Result:
        name, arg = intent.data["name"], intent.data["arg"]
        app = self.app
        simple = {
            "status": ("system_diagnosis", {}), "diagnose": ("system_diagnosis", {}),
            "projekte": ("list_projects", {}), "projektstand": ("project_status", {}),
            "aufgaben": ("list_tasks", {}), "dokumente": ("list_documents", {}),
            "importordner": ("import_folder", {}), "sicherung": ("create_backup", {}),
            "sicherungen": ("list_backups", {}), "export": ("export_data", {}),
            "altwissen": ("import_legacy_knowledge", {}),
        }
        if name in ("hilfe", "help", "?"):
            return Result(ANSWER, HELP_TEXT)
        if name in simple:
            tool, args = simple[name]
            return self._tool_result(tool, args)
        if name in ("modelle", "modell", "models"):
            return Result(ANSWER, self.models_text())
        if name in ("neu", "new"):
            self.new_conversation()
            return Result(ANSWER, "Neues Gespräch gestartet. Gedächtnis und Projekte bleiben natürlich erhalten.")
        if name in ("merke", "merken"):
            return self._remember(Intent("remember", {"content": arg})) if arg else Result(QUESTION, "Was soll ich mir merken?")
        if name == "erinnerungen":
            if arg:
                return self._tool_result("search_memory", {"query": arg})
            items = app.memory.active(limit=50)
            text = "\n".join(m.line() for m in items) or "Noch keine Erinnerungen gespeichert."
            return Result(ANSWER, text)
        if name in ("vergiss", "vergessen"):
            return self._forget(Intent("forget", {"query": arg})) if arg else Result(QUESTION, "Was soll ich vergessen?")
        if name in ("korrigiere", "korrektur"):
            mem_id, _, content = arg.lstrip("#").partition(" ")
            if not mem_id.isdigit() or not content.strip():
                return Result(QUESTION, "So geht's: /korrigiere ID NEUER TEXT")
            return self._tool_result("replace_memory", {"memory_id": int(mem_id), "content": content.strip()})
        if name == "projekt":
            if arg.lower().startswith("neu "):
                rest = arg[4:]
                pname, _, purpose = rest.partition("|")
                return self._tool_result("create_project", {"name": pname.strip(), "purpose": purpose.strip()})
            if arg:
                return self._tool_result("switch_project", {"name": arg})
            return self._tool_result("project_status", {})
        if name in ENTRY_COMMANDS:
            if not arg:
                return Result(QUESTION, f"Was soll ich als {ENTRY_KINDS[ENTRY_COMMANDS[name]]} festhalten?")
            return self._tool_result("add_project_entry", {"kind": ENTRY_COMMANDS[name], "content": arg})
        if name == "aufgabe":
            return self._tool_result("add_task", {"title": arg}) if arg else Result(QUESTION, "Wie lautet die Aufgabe?")
        if name == "erledigt":
            if not arg.lstrip("#").isdigit():
                return Result(QUESTION, "So geht's: /erledigt ID (die ID zeigt /aufgaben)")
            return self._tool_result("update_task", {"task_id": int(arg.lstrip("#")), "status": "erledigt"})
        if name == "import":
            return self._tool_result("import_document", {"path": arg}) if arg else Result(QUESTION, "Welche Datei? /import PFAD")
        if name == "suche":
            if not arg:
                return Result(QUESTION, "Wonach soll ich suchen? /suche BEGRIFF")
            return self._lookup(arg, intro="")
        if name == "dateien":
            return self._tool_result("list_files", {"path": arg or "."})
        if name == "lesen":
            return self._tool_result("read_file", {"path": arg}) if arg else Result(QUESTION, "Welche Datei? /lesen PFAD")
        if name == "wiederherstellen":
            return self._tool_result("restore_backup", {"file": arg}) if arg else self._tool_result("list_backups", {})
        if name == "erlauben":
            tool = app.tools.get(arg)
            if not tool:
                return Result(ERROR, f"Werkzeug '{arg}' gibt es nicht. Verfügbar: "
                                     + ", ".join(t.name for t in app.tools.all()))
            if tool.level >= Level.EXTERNAL:
                return Result(ERROR, "Externe/irreversible Aktionen brauchen immer eine Einzelfreigabe.")
            app.permissions.grant_for_session(tool.name)
            return Result(ANSWER, f"'{tool.name}' läuft in dieser Sitzung ohne Rückfrage. Nach einem Neustart frage ich wieder.")
        return Result(QUESTION, f"Den Befehl /{name} kenne ich nicht. /hilfe zeigt alle Befehle – "
                                f"oder sag mir einfach in eigenen Worten, was du brauchst.")

    def models_text(self) -> str:
        lines = ["Sprachmodelle (in dieser Reihenfolge versucht):"]
        any_ok = False
        for name, ok, info in self.app.models.status():
            any_ok = any_ok or ok
            lines.append(f"{'✅' if ok else '➖'} {name}: {info}")
        stats = self.app.episodes.model_stats()
        if stats:
            lines.append("Bisherige Nutzung: " + "; ".join(
                f"{s['provider']}/{s['model']}: {s['aufrufe']} Aufrufe, Ø {s['mittlere_ms']} ms, "
                f"{s['input_tokens']}+{s['output_tokens']} Tokens" for s in stats))
        if not any_ok:
            lines.append("")
            lines.append(SETUP_HINT)
        return "\n".join(lines)

    # ======================================================== Ohne Sprachmodell
    def _offline(self, intent: Intent, text: str) -> Result:
        english = intent_router.looks_english(text)
        name = self.app.settings.user_name
        if intent.kind == "greeting":
            if english:
                return Result(ANSWER, f"Hello{(' ' + name) if name else ''}! I'm here. Note: no language model is "
                                      "connected right now – commands, memory and document search still work. Type /hilfe.")
            return Result(ANSWER, f"Hallo{(' ' + name) if name else ''}! Schön, dass du da bist. {NO_MODEL_NOTE}")
        if intent.kind == "thanks":
            return Result(ANSWER, "Gern geschehen!")
        if intent.kind == "help":
            return Result(ANSWER, HELP_TEXT + "\n\n" + NO_MODEL_NOTE)
        if intent.kind == "capability":
            return Result(QUESTION, self._capability_answer(intent.data.get("topic", ""), english))
        if intent.kind == "recall":
            return self._recall(intent)
        return self._lookup(text, intro="Ohne Sprachmodell kann ich nur nachschlagen.", fallback_hint=True)

    def _capability_answer(self, topic: str, english: bool) -> str:
        t = topic.lower()
        coding = any(k in t for k in ("programm", "code", "coden", "skript", "script", "software", "app", "website",
                                      "webseite", "python"))
        if coding:
            base = ("Ja. Ich kann Code schreiben, bestehende Dateien analysieren und Ergebnisse direkt in deinem "
                    "Arbeitsordner speichern. Was möchtest du bauen – und in welcher Sprache?")
            if english:
                base = ("Yes. I can write code, analyse existing files and save results straight to your workspace. "
                        "What do you want to build, and in which language?")
        else:
            base = (f"Das kommt drauf an – erzähl mir kurz, wofür du „{topic}“ brauchst, dann sage ich dir ehrlich, "
                    f"ob und wie ich das mit meinen Werkzeugen erledigen kann.")
        return base + "\n\n" + ("(No language model connected yet – see /modelle.)" if english
                                else "(Für freie Aufgaben brauche ich ein Sprachmodell – gerade ist keins verbunden, "
                                     "siehe /modelle.)")

    def _recall(self, intent: Intent) -> Result:
        memory = self.app.memory
        subject = intent.data.get("subject")
        hits = memory.by_subject(subject) if subject else []
        if not hits:
            hits = memory.search(intent.data.get("query", ""), limit=5)
        if not hits:
            return self._lookup(intent.data.get("query", ""), fallback_hint=not self.app.models.has_model())
        memory.touch(hits)
        if subject and len({h.content for h in hits}) > 1:
            listed = "\n".join(f"• {h.line()}" for h in hits)
            return Result(QUESTION, f"Dazu habe ich widersprüchliche Angaben:\n{listed}\nWelche stimmt?",
                          sources=[f"Erinnerung #{h.id}" for h in hits])
        lines = [f"• {h.line()}" for h in hits]
        intro = "Laut meinem Gedächtnis:" if hits[0].status == "confirmed" else "Unsicher (vorläufige Angabe):"
        return Result(ANSWER, intro + "\n" + "\n".join(lines), sources=[f"Erinnerung #{h.id}" for h in hits])

    def _lookup(self, query: str, intro: str = "", fallback_hint: bool = False) -> Result:
        memories = self.app.memory.search(query, limit=5)
        hits = self.app.knowledge.search(query, limit=3)
        parts, sources = [], []
        if memories:
            parts.append("Aus meinem Gedächtnis:\n" + "\n".join(f"• {m.line()}" for m in memories))
            sources += [f"Erinnerung #{m.id}" for m in memories]
        if hits:
            parts.append("Aus deinen Dokumenten:\n" + "\n".join(
                f"• {h.document}, {h.location}: „{self.app.knowledge.snippet(h, query)}“" for h in hits))
            sources += [h.source for h in hits]
        if not parts:
            text = (intro + " " if intro else "") + f"Zu „{query}“ habe ich weder im Gedächtnis noch in deinen Dokumenten etwas gefunden."
            if fallback_hint:
                text += "\n\nFür freie Antworten brauche ich ein Sprachmodell.\n" + SETUP_HINT
            return Result(ANSWER, text)
        text = (intro + " Das habe ich gefunden:\n\n" if intro else "") + "\n\n".join(parts)
        return Result(ANSWER, text, sources=sources)

    # ============================================== Sprachmodell + Werkzeuge
    def _llm_turn(self, text: str, user_msg_id: int) -> Result:
        app = self.app
        history = app.conversations.history(app.settings.history_messages, before_id=user_msg_id)
        while history and history[0]["role"] != "user":
            history.pop(0)  # Verlauf muss mit einer Nutzernachricht beginnen
        # Vorsichtig: Könnte (z. B. als Ausweichmodell) ein externer Anbieter antworten, gilt die
        # Datenschutzeinstellung für externe Modelle.
        external = any(p.external for p in app.models.available())
        context, sources = app.context.build(text, external_model=external)
        messages = [{"role": h["role"], "content": h["content"]} for h in history]
        messages.append({"role": "user", "content": f"{context}\n\n{text}"})
        loop = LoopState(system=system_prompt(app.settings), messages=messages, sources=list(sources))
        return self._run_loop(loop)

    def _run_loop(self, loop: LoopState) -> Result:
        app = self.app
        # Zuerst noch offene Werkzeugaufrufe der letzten Modellantwort abarbeiten
        suspended = self._process_calls(loop)
        if suspended:
            return suspended

        tools = app.tools.specs()
        while loop.iterations < app.settings.max_tool_iterations:
            loop.iterations += 1
            try:
                response = app.models.chat(loop.system, loop.messages, tools, preferred=loop.provider)
            except NoModelAvailable as e:
                done = "\n".join(a.line() for a in loop.actions)
                text = e.explain() + (f"\n\nBis dahin erledigt:\n{done}" if done else "")
                return Result(ERROR, text, actions=loop.actions, sources=loop.sources, details=str(e))
            loop.provider = response.provider
            loop.model_label = response.label()
            loop.messages.append(response.as_message())
            if not response.tool_calls:
                return self._finish(response.text, loop)
            loop.remaining_calls = list(response.tool_calls)
            suspended = self._process_calls(loop, intro=response.text)
            if suspended:
                return suspended

        text = (f"Ich habe nach {app.settings.max_tool_iterations} Arbeitsschritten angehalten, damit nichts aus "
                f"dem Ruder läuft. Soll ich weitermachen?")
        return Result(QUESTION, text, actions=loop.actions, sources=loop.sources, model=loop.model_label)

    def _process_calls(self, loop: LoopState, intro: str = "") -> Optional[Result]:
        app = self.app
        while loop.remaining_calls:
            call = loop.remaining_calls.pop(0)
            tool = app.tools.get(call.name)
            if tool is None:
                output = ToolOutput(False, f"Unbekanntes Werkzeug '{call.name}'. Verfügbar: "
                                           + ", ".join(t.name for t in app.tools.all()))
            else:
                level = tool.effective_level(call.arguments)
                if app.permissions.needs_confirmation(call.name, level):
                    pending = Pending(uuid.uuid4().hex[:10], call.name, call.arguments,
                                      tool.call_text(call.arguments), level, loop=loop, call_id=call.id)
                    return self._ask_confirmation(pending, intro=intro.strip())
                output = app.tools.execute(call.name, call.arguments)
            loop.actions.append(Action(call.name, output.ok, output.summary,
                                       "ausgeführt" if output.ok else "fehlgeschlagen"))
            loop.sources += output.sources
            loop.messages.append({"role": "tool", "tool_call_id": call.id, "name": call.name,
                                  "content": output.content, "is_error": not output.ok})
        return None

    def _finish(self, text: str, loop: LoopState) -> Result:
        """Qualitätsprüfung: Antwort und tatsächlicher Werkzeugstatus müssen zusammenpassen."""
        text = (text or "").strip()
        failed = [a for a in loop.actions if a.status == "fehlgeschlagen"]
        if not text:
            if loop.actions:
                text = "Erledigt." if not failed else "Nicht alles hat geklappt."
            else:
                text = "Ich habe darauf leider keine Antwort erhalten. Magst du die Frage anders formulieren?"
        if failed and not any(w in text.lower() for w in ("fehl", "nicht", "leider", "error", "failed", "konnte")):
            text += "\n\n⚠️ Achtung: Mindestens eine Aktion ist fehlgeschlagen – siehe Status unten."
        kind = QUESTION if text.rstrip().endswith("?") else ANSWER
        return Result(kind, text, actions=loop.actions, sources=loop.sources, model=loop.model_label)
