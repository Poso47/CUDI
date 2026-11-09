"""Gemeinsame Test-Hilfen: isolierte CUDI-Instanzen in temporären Ordnern + Fake-Sprachmodell."""

import copy
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from cudi.config.settings import load_settings  # noqa: E402
from cudi.core.application import Application  # noqa: E402
from cudi.models.base import ModelProvider, ModelResponse, ProviderError, ToolCall  # noqa: E402


@pytest.fixture(autouse=True)
def _no_clip_model(monkeypatch):
    """Tests laden nie das CLIP-Modell (kein Download/Install); Bildprüfungs-Tests setzen ihre eigenen Attrappen."""
    monkeypatch.setenv("CUDI_BILDPRUEFUNG", "0")
    monkeypatch.setenv("CUDI_RECHERCHE", "0")        # Recherche-Agent greift in Tests nie ins Netz (Tests dazu: test_recherche.py)
    # Tests laufen ohne echtes Sprachmodell, auch wenn die Umgebung CUDI_LLM_* (Notbetrieb) gesetzt hat;
    # Notbetrieb-Tests setzen ihre eigenen Werte.
    from cudi_video import config as _cfg
    for name in ("CUDI_LLM_BASE_URL", "CUDI_LLM_API_KEY", "CUDI_LLM_MODEL"):
        monkeypatch.delenv(name, raising=False)
    for attr in ("LLM_BASE_URL", "LLM_API_KEY", "LLM_MODEL"):
        monkeypatch.setattr(_cfg, attr, "", raising=False)


class FakeProvider(ModelProvider):
    """Sprachmodell-Attrappe mit Drehbuch: jede Antwort ist Text, ModelResponse oder Funktion."""

    def __init__(self, script=None, name="fake", available=True, error=None, external=False):
        self.name = name
        self.external = external
        self.script = list(script or [])
        self.available = available
        self.error = error
        self.calls = []

    @property
    def model_name(self):
        return "fake-1"

    def status(self):
        return (self.available, "Fake-Modell bereit" if self.available else "Fake-Modell aus")

    def chat(self, system, messages, tools=None):
        self.calls.append({"system": system, "messages": copy.deepcopy(messages), "tools": tools})
        if self.error:
            raise ProviderError(self.error)
        step = self.script.pop(0) if self.script else "OK"
        if callable(step):
            step = step(system, messages, tools)
        if isinstance(step, str):
            return ModelResponse(text=step, provider=self.name, model="fake-1", external=self.external)
        step.provider = self.name
        step.model = step.model or "fake-1"
        return step


def tool_call(name, text="", **arguments):
    return ModelResponse(text=text, tool_calls=[ToolCall(id=f"call_{name}", name=name, arguments=arguments)])


@pytest.fixture
def make_app(tmp_path):
    apps = []

    def _make(providers=None, base=None, **overrides):
        settings = load_settings(base or tmp_path, use_env=False)
        for key, value in overrides.items():
            setattr(settings, key, value)
        app = Application(settings, providers=providers if providers is not None else {})
        apps.append(app)
        return app

    yield _make
    for app in apps:
        app.close()


def make_pdf(path: Path, pages):
    """Erzeugt ein minimales, gültiges PDF mit einer Textzeile pro Seite."""
    objects = ["<< /Type /Catalog /Pages 2 0 R >>", None,
               "<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>"]
    kids = []
    for text in pages:
        safe = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
        stream = f"BT /F1 12 Tf 72 720 Td ({safe}) Tj ET"
        objects.append(f"<< /Length {len(stream)} >>\nstream\n{stream}\nendstream")
        content_no = len(objects)
        objects.append(f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
                       f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_no} 0 R >>")
        kids.append(f"{len(objects)} 0 R")
    objects[1] = f"<< /Type /Pages /Kids [{' '.join(kids)}] /Count {len(kids)} >>"
    out = bytearray(b"%PDF-1.4\n")
    offsets = []
    for i, obj in enumerate(objects, 1):
        offsets.append(len(out))
        out += f"{i} 0 obj\n{obj}\nendobj\n".encode("latin-1")
    xref = len(out)
    out += f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode()
    for off in offsets:
        out += f"{off:010d} 00000 n \n".encode()
    out += f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF\n".encode()
    path.write_bytes(bytes(out))
    return path


@pytest.fixture(autouse=True)
def _cudi_video_offline(monkeypatch):
    """CUDI-Video-Tests laufen ohne Netz: keine Clip-Suche und keine Webseiten-Prüfung nebenbei."""
    try:
        from cudi_video import config as video_config
    except ImportError:
        return
    monkeypatch.setattr(video_config, "RANKING_CLIPS", False)
    monkeypatch.setattr(video_config, "CHECK_WEB", False)
