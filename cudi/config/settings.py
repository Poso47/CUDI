"""Einheitliche Einstellungen für CUDI.

Reihenfolge (spätere Quelle gewinnt):
1. Standardwerte in dieser Datei
2. ``config/settings.json`` (wird von der GUI/CLI geschrieben, nicht versioniert)
3. Umgebungsvariablen bzw. ``.env`` im Projektordner

API-Schlüssel werden ausschließlich aus Umgebungsvariablen/``.env`` gelesen und
niemals in ``settings.json`` gespeichert.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import asdict, dataclass, field, fields
from pathlib import Path
from typing import List, Optional

log = logging.getLogger("cudi.config")

KNOWN_PROVIDERS = ("ollama", "anthropic", "openai")

# Felder, die nie in settings.json landen
SECRET_FIELDS = {"anthropic_api_key", "openai_api_key"}
# Pfadfelder (werden relativ zu base_dir aufgelöst)
PATH_FIELDS = {"data_dir", "workspace_dir", "import_dir", "log_dir"}


@dataclass
class Settings:
    base_dir: Path = Path(".")
    data_dir: Path = Path("data")
    workspace_dir: Path = Path("workspace")
    import_dir: Path = Path("import")
    log_dir: Path = Path("logs")

    # Persönlichkeit / Ansprache
    assistant_name: str = "CUDI"
    user_name: str = ""
    address: str = "du"  # "du" oder "Sie"

    # Sprachmodelle
    provider_order: List[str] = field(default_factory=lambda: ["ollama", "anthropic", "openai"])
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.1"
    anthropic_model: str = "claude-opus-5-5"
    anthropic_effort: str = "medium"
    openai_model: str = "gpt-4o"
    openai_base_url: str = "https://api.openai.com/v1"
    request_timeout: int = 120
    anthropic_api_key: str = ""
    openai_api_key: str = ""

    # Datenschutz
    share_documents_with_external_models: bool = True

    # Verhalten
    auto_approve_level: int = 2  # Stufen bis einschließlich dieser laufen ohne Rückfrage
    history_messages: int = 20
    max_tool_iterations: int = 8
    backups_keep: int = 10
    extra_read_dirs: List[str] = field(default_factory=list)

    # ---------------------------------------------------------------
    @property
    def settings_file(self) -> Path:
        return self.base_dir / "config" / "settings.json"

    @property
    def db_path(self) -> Path:
        return self.data_dir / "cudi_brain.db"

    @property
    def backup_dir(self) -> Path:
        return self.data_dir / "backups"

    def read_roots(self) -> List[Path]:
        """Ordner, aus denen ohne Rückfrage gelesen werden darf."""
        roots = [self.workspace_dir, self.import_dir, self.base_dir]
        roots += [Path(p).expanduser() for p in self.extra_read_dirs]
        return [r.resolve() for r in roots]

    def ensure_dirs(self) -> None:
        for d in (self.data_dir, self.workspace_dir, self.import_dir, self.log_dir, self.backup_dir):
            d.mkdir(parents=True, exist_ok=True)

    def to_public_dict(self) -> dict:
        data = asdict(self)
        for key in SECRET_FIELDS:
            data.pop(key, None)
        data.pop("base_dir", None)
        for key in PATH_FIELDS:
            path = Path(data[key])
            try:
                data[key] = str(path.relative_to(self.base_dir))
            except ValueError:
                data[key] = str(path)
        return data

    def save(self) -> Path:
        self.settings_file.parent.mkdir(parents=True, exist_ok=True)
        self.settings_file.write_text(
            json.dumps(self.to_public_dict(), indent=2, ensure_ascii=False), encoding="utf-8"
        )
        return self.settings_file

    def validate(self) -> List[str]:
        """Korrigiert ungültige Werte und liefert Warnungen zurück."""
        warnings = []
        unknown = [p for p in self.provider_order if p not in KNOWN_PROVIDERS]
        if unknown:
            warnings.append(f"Unbekannte Modellanbieter ignoriert: {', '.join(unknown)}")
            self.provider_order = [p for p in self.provider_order if p in KNOWN_PROVIDERS]
        if not 1 <= self.auto_approve_level <= 4:
            # Stufe 5 (extern/irreversibel) erfordert immer eine Bestätigung
            warnings.append("auto_approve_level muss zwischen 1 und 4 liegen – auf 2 gesetzt")
            self.auto_approve_level = 2
        if self.address not in ("du", "Sie"):
            warnings.append("address muss 'du' oder 'Sie' sein – auf 'du' gesetzt")
            self.address = "du"
        if self.anthropic_effort not in ("low", "medium", "high", "xhigh", "max"):
            warnings.append("anthropic_effort ungültig – auf 'medium' gesetzt")
            self.anthropic_effort = "medium"
        self.history_messages = max(0, int(self.history_messages))
        self.max_tool_iterations = max(1, int(self.max_tool_iterations))
        return warnings


def load_dotenv(path: Path) -> None:
    """Minimaler .env-Leser (KEY=VALUE); überschreibt keine gesetzten Variablen."""
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


_ENV_MAP = {
    "CUDI_DATA_DIR": "data_dir",
    "CUDI_WORKSPACE": "workspace_dir",
    "CUDI_IMPORT_DIR": "import_dir",
    "CUDI_LOG_DIR": "log_dir",
    "CUDI_USER_NAME": "user_name",
    "OLLAMA_HOST": "ollama_host",
    "CUDI_OLLAMA_MODEL": "ollama_model",
    "CUDI_ANTHROPIC_MODEL": "anthropic_model",
    "CUDI_OPENAI_MODEL": "openai_model",
    "OPENAI_BASE_URL": "openai_base_url",
    "ANTHROPIC_API_KEY": "anthropic_api_key",
    "OPENAI_API_KEY": "openai_api_key",
}


def load_settings(base_dir: Optional[Path] = None, use_env: bool = True) -> Settings:
    base = Path(base_dir or Path(__file__).resolve().parents[2]).resolve()
    if use_env:
        load_dotenv(base / ".env")

    settings = Settings(base_dir=base)
    valid = {f.name for f in fields(Settings)} - SECRET_FIELDS - {"base_dir"}

    if settings.settings_file.exists():
        try:
            stored = json.loads(settings.settings_file.read_text(encoding="utf-8"))
            for key, value in stored.items():
                if key in valid:
                    setattr(settings, key, value)
                else:
                    log.warning("Unbekannte Einstellung ignoriert: %s", key)
        except (OSError, json.JSONDecodeError) as e:
            log.error("config/settings.json ist ungültig und wird ignoriert: %s", e)

    if use_env:
        for env_key, attr in _ENV_MAP.items():
            if os.environ.get(env_key):
                setattr(settings, attr, os.environ[env_key])
        if os.environ.get("CUDI_PROVIDER_ORDER"):
            settings.provider_order = [
                p.strip() for p in os.environ["CUDI_PROVIDER_ORDER"].split(",") if p.strip()
            ]

    for key in PATH_FIELDS:
        path = Path(getattr(settings, key)).expanduser()
        if not path.is_absolute():
            path = base / path
        setattr(settings, key, path.resolve())

    for warning in settings.validate():
        log.warning(warning)
    return settings
