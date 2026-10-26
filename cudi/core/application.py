"""Zusammenbau aller Komponenten: eine Anwendung, eine Datenbank, ein Orchestrator."""

from __future__ import annotations

import logging
from datetime import date
from pathlib import Path
from typing import Dict, Optional

from ..brain.context_builder import ContextBuilder
from ..brain.conversation import ConversationStore, WorkingMemory
from ..brain.database import Database
from ..brain.episodes import EpisodeLog
from ..brain.knowledge import KnowledgeStore
from ..brain.memory import MemoryStore
from ..brain.projects import ProjectStore
from ..config.logging_config import setup_logging
from ..config.settings import Settings, load_settings
from ..models.anthropic_provider import AnthropicProvider
from ..models.base import ModelProvider
from ..models.model_manager import ModelManager
from ..models.ollama_provider import OllamaProvider
from ..models.openai_provider import OpenAIProvider
from ..tools import document_tools, file_tools, memory_tools, project_tools, system_tools
from ..tools.registry import ToolRegistry, call_signature
from .orchestrator import Orchestrator
from .permissions import PermissionManager

log = logging.getLogger("cudi")


def build_providers(settings: Settings) -> Dict[str, ModelProvider]:
    return {
        "ollama": OllamaProvider(settings.ollama_host, settings.ollama_model, settings.request_timeout),
        "anthropic": AnthropicProvider(settings.anthropic_api_key, settings.anthropic_model,
                                       settings.anthropic_effort, settings.request_timeout),
        "openai": OpenAIProvider(settings.openai_api_key, settings.openai_model, settings.openai_base_url,
                                 settings.request_timeout),
    }


class Application:
    def __init__(self, settings: Settings, providers: Optional[Dict[str, ModelProvider]] = None):
        self.settings = settings
        settings.ensure_dirs()
        setup_logging(settings.log_dir)

        # Digitales Gehirn
        self.db = Database(settings.db_path)
        self.memory = MemoryStore(self.db)
        self.conversations = ConversationStore(self.db)
        self.projects = ProjectStore(self.db)
        self.knowledge = KnowledgeStore(self.db)
        self.episodes = EpisodeLog(self.db)
        self.working = WorkingMemory()
        self.context = ContextBuilder(self)

        # Modelle
        providers = providers if providers is not None else build_providers(settings)
        order = [p for p in settings.provider_order if p in providers] or list(providers)
        self.models = ModelManager(providers, order, on_call=self.episodes.model_call)

        # Werkzeuge + Berechtigungen
        self.permissions = PermissionManager(settings.auto_approve_level)
        self.tools = ToolRegistry()
        for module in (file_tools, memory_tools, project_tools, document_tools, system_tools):
            module.register(self.tools, self)
        self.tools.on_executed = self._log_tool
        self.tools.previous_failure = self.episodes.previous_failure

        self.orchestrator = Orchestrator(self)
        self._daily_backup()
        log.info("CUDI gestartet (Daten: %s)", settings.data_dir)

    def _log_tool(self, tool, args, output, duration_ms) -> None:
        short_args = {k: (v[:200] + "…" if isinstance(v, str) and len(v) > 200 else v) for k, v in args.items()}
        project = self.projects.active()
        self.episodes.record("tool", f"{tool.name}: {output.summary}", data={"args": short_args, "ms": duration_ms},
                             ok=output.ok, signature=call_signature(tool.name, args),
                             project_id=project["id"] if project else None)
        if output.ok:
            self.working.note_step(f"{tool.name}: {output.summary}")

    def _daily_backup(self) -> None:
        """Einmal pro Tag beim Start eine Sicherung (nur wenn es schon Daten gibt)."""
        today = date.today().isoformat()
        if self.db.get_state("last_backup_day") == today:
            return
        if self.memory.count() or self.projects.list() or self.knowledge.documents():
            try:
                self.db.backup(self.settings.backup_dir, keep=self.settings.backups_keep, label="auto")
            except Exception:
                log.exception("Automatische Sicherung fehlgeschlagen")
                return
        self.db.set_state("last_backup_day", today)

    # Bequeme Durchreichungen
    def handle(self, text: str):
        return self.orchestrator.handle(text)

    def resolve(self, pending_id: str, approved: bool, remember_choice: bool = False):
        return self.orchestrator.resolve(pending_id, approved, remember_choice)

    def close(self) -> None:
        self.db.close()


_app: Optional[Application] = None


def create_app(base_dir: Optional[Path] = None, providers: Optional[Dict[str, ModelProvider]] = None,
               settings: Optional[Settings] = None) -> Application:
    settings = settings or load_settings(base_dir)
    return Application(settings, providers)


def get_app() -> Application:
    """Eine gemeinsame Instanz pro Prozess (für die GUI)."""
    global _app
    if _app is None:
        _app = create_app()
    return _app
