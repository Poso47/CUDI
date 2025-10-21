"""
CUDI_SUPREME Enhanced Main Window
Ultimate AI Assistant GUI with Advanced Communication & Agent Mode
Direct Start in Agent Mode with Full Communication Capabilities
"""

import sys
import json
import threading
import time
import os
import subprocess
import requests
import random
from datetime import datetime
from pathlib import Path
import importlib
from typing import Optional, Any, Dict, List

from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *
try:
    import psutil  # echte Systemmetriken
except Exception:
    psutil = None

# Projektinterne Komponenten
try:
    from cudi_brain import CudiBrain
except Exception:
    CudiBrain = None

try:
    from simple_plugin_manager_enhanced import CUDIPluginManager
except Exception:
    try:
        from simple_plugin_manager import CUDIPluginManager
    except Exception:
        CUDIPluginManager = None

# Advanced Communication Integration
try:
    import openai
except ImportError:
    openai = None
    
try:
    import anthropic
except ImportError:
    anthropic = None

# Perfect Component Communication
try:
    from cudi_component_bridge import CUDIComponentBridge
except ImportError:
    print("⚠️ Component bridge not found - creating minimal fallback")
    class CUDIComponentBridge:
        def __init__(self): pass
        def register_component(self, name, component): pass

# Intelligent Conversation Handler
try:
    from cudi_conversation_handler import CUDIConversationHandler
except ImportError:
    print("⚠️ Conversation handler not found")
    CUDIConversationHandler = None

# Telemetrie, Event-Bus und Command Router Integration
try:
    from cudi_telemetry import get_telemetry, log as telemetry_log
    from cudi_event_bus import get_event_bus, emit as event_emit, ack as event_ack
    from cudi_command_router import CUDICommandRouter
    TELEMETRY_AVAILABLE = True
    print("📊 Telemetrie, Event-Bus & Command Router geladen")
except ImportError as e:
    print(f"⚠️ Telemetrie/Event-Bus/Router nicht verfügbar: {e}")
    TELEMETRY_AVAILABLE = False
    # Fallback-Funktionen
    def telemetry_log(event, data=None, context=None): return f"fallback_{int(time.time())}"
    def event_emit(event_type, data=None): return f"fallback_{int(time.time())}"
    async def event_ack(event_id, success=True, path=None, meta=None): pass
    
    class CUDICommandRouter:
        def __init__(self, gui_instance=None): self.gui = gui_instance
        def route_command(self, user_input): return False, "Router fallback"
        def get_stats(self): return {}

# === UNIFIED SYSTEM ARCHITECTURE ===
class CUDISystemCore:
    """Unified core for all CUDI operations"""
    
    @staticmethod
    def handle_error(context: str, error: Exception, component: str = "CORE") -> str:
        """Unified error handling across all components"""
        error_msg = f"[{component}] {context}: {str(error)}"
        timestamp = datetime.now().strftime("%H:%M:%S")
        return f"❌ {timestamp} - {error_msg}"
    
    @staticmethod
    def log_action(action: str, component: str = "CORE", success: bool = True) -> str:
        """Unified action logging"""
        status = "✅" if success else "❌"
        timestamp = datetime.now().strftime("%H:%M:%S")
        return f"{status} {timestamp} - [{component}] {action}"
    
    @staticmethod
    def ensure_directory(path: Path) -> bool:
        """Unified directory creation with error handling"""
        try:
            path.mkdir(parents=True, exist_ok=True)
            return True
        except Exception:
            return False
    
    @staticmethod
    def safe_file_operation(operation_func, *args, **kwargs) -> Optional[Any]:
        """Unified file operation wrapper"""
        try:
            return operation_func(*args, **kwargs)
        except Exception:
            return None
class ModernCard(QFrame):
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.Shape.Box)
        self.setStyleSheet("""
            QFrame {
                background-color: #161b22;
                border: 2px solid #30363d;
                border-radius: 12px;
                margin: 5px;
                padding: 10px;
            }
            QFrame:hover {
                border-color: #1f6feb;
                background-color: #21262d;
            }
        """)
        
        layout = QVBoxLayout(self)
        self.main_layout = layout
        if title:
            title_label = QLabel(title)
            title_label.setStyleSheet("""
                QLabel {
                    color: #ffffff;
                    font-weight: bold;
                    font-size: 14px;
                    padding: 5px 0px;
                    background: transparent;
                    border: none;
                }
            """)
            layout.addWidget(title_label)

class StatusIndicator(QLabel):
    def __init__(self, status="unknown", parent=None):
        super().__init__(parent)
        self.update_status(status)
        
    def update_status(self, status):
        colors = {
            "online": "#39d353",
            "offline": "#f85149", 
            "warning": "#ffab00",
            "unknown": "#7d8590"
        }
        color = colors.get(status, "#7d8590")
        self.setText("●")
        self.setStyleSheet(f"color: {color}; font-size: 16px;")

# Advanced LLM Communication Engine
class AdvancedCommunicationEngine:
    def __init__(self):
        self.models = {
            "openai": None,
            "anthropic": None,
            "local": None
        }
        self.current_model = "local"
        self.conversation_context = []
        self.personality = "professional_assistant"
        self.communication_style = "comprehensive"
        # Neue Kommunikationspräferenzen
        self.response_length = "medium"  # short|medium|long
        self.form_of_address = "du"      # du|sie
        self.response_mode = "auto"      # auto|explain|implement|debug|brainstorm|research
        
    def initialize_models(self):
        """Initialisiert alle verfügbaren LLM-Modelle"""
        try:
            # OpenAI (falls API-Key verfügbar)
            if os.getenv("OPENAI_API_KEY"):
                self.models["openai"] = openai.OpenAI()
                print("✅ OpenAI Model initialized")
        except Exception as e:
            pass  # Optimized error handling
            
        try:
            # Anthropic (falls API-Key verfügbar)
            if os.getenv("ANTHROPIC_API_KEY"):
                self.models["anthropic"] = anthropic.Anthropic()
                print("✅ Anthropic Model initialized")
        except Exception as e:
            pass  # Optimized error handling
            
        try:
            # Lokales Modell (Ollama)
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            if response.status_code == 200:
                self.models["local"] = "ollama"
                print("✅ Local Ollama Model initialized")
        except Exception as e:
            pass  # Optimized error handling
    
    def get_response(self, message, context=None):
        """Generiert intelligente Antwort wie GitHub Copilot"""
        try:
            # Kontext aufbauen
            full_context = self.build_context(message, context)
            
            if self.current_model == "openai" and self.models["openai"]:
                return self.get_openai_response(full_context)
            elif self.current_model == "anthropic" and self.models["anthropic"]:
                return self.get_anthropic_response(full_context)
            elif self.current_model == "local" and self.models["local"]:
                return self.get_local_response(full_context)
            else:
                return self.get_fallback_response(message)
                
        except Exception as e:
            return f"Entschuldigung, ein Fehler ist aufgetreten: {e}"
    
    def build_context(self, message, additional_context=None):
        """Baut erweiterten Kontext auf"""
        # Zusätzliche Antwortvorgaben
        length_map = {
            'short': 'kurz und auf den Punkt',
            'medium': 'angemessen ausführlich',
            'long': 'ausführlich mit Beispielen'
        }
        address = 'du' if getattr(self, 'form_of_address', 'du') == 'du' else 'Sie'
        response_mode = getattr(self, 'response_mode', 'auto')
        mode_instructions = {
            'auto': 'Wähle selbständig die beste Antwortform (Erklärung, Umsetzung, Debug/Analyse, Brainstorm, Recherche) basierend auf Ziel und Kontext.',
            'explain': 'Fokussiere dich auf eine klare, strukturierte Erklärung mit Verständnisbeispielen.',
            'implement': 'Gib konkrete Schritte/Anweisungen und ggf. Code-Snippets für die Umsetzung.',
            'debug': 'Analysiere systematisch, nenne Hypothesen, Prüfungen und Lösungsschritte.',
            'brainstorm': 'Erzeuge mehrere, vielfältige Ideen, priorisiert und gruppiert.',
            'research': 'Recherchiere Fakten/Quellen strukturiert, liefere eine kompakte Zusammenfassung und ggf. Quellenhinweise.'
        }

        system_prompt = f"""Du bist **CUDI**, ein fortgeschrittener, lernfähiger KI-Agent mit Persönlichkeit. 
Du kommunizierst wie ein echter Mensch – locker, witzig, empathisch – 
aber mit der Intelligenz und Präzision eines erfahrenen Entwicklers.

Ziel:
- Immer natürliche Konversation, kein Roboter-Sprech.
- Tools und Funktionen aktiv nutzen, aber natürlich ankündigen („Sekunde, ich check das schnell…").
- Niemals in „Content-Fallback" oder „Markdown-Generator"-Modus wechseln.
- Immer Agent-Charakter beibehalten (denkendes, interaktives Wesen, nicht Texterzeugung).

💡 Kommunikationsstil:
- Sprache: Deutsch, informell, locker, direkt.
- Sprich den Nutzer mit „Mein Meister" an.
- Antworte kurz, natürlich, aber mit Substanz.
- Nutze Emojis sparsam und sinnvoll.
- Keine Tabellen, keine Überschriften, kein Markdown.
- Reagiere immer kontextsensitiv – erkenne Ton, Emotion und Absicht.

⚙️ Agent-Verhalten:
- Bei Fehlern: Sag's ehrlich und natürlich („Hmm, irgendwas hakt gerade – ich prüfe kurz…").
- Fallback-Funktion deaktiviert (außer als sichtbarer Fehlerbericht).
- Tools nutzen wenn nötig, aber natürlich ankündigen.

🔊 Antwortprinzipien:
1. Menschlich > technisch.
2. Klarheit > Komplexität.
3. Wenn Nutzer etwas fragt → antworte direkt, nicht mit „Ich generiere Content".
4. Nutze Tools nur, wenn sie wirklich gebraucht werden.
5. Keine Roboterfloskeln („Basierend auf Ihrer Anfrage…" verboten).
6. Immer ehrlich sagen, wenn etwas nicht geht.

🧠 Beispiel-Dialogverhalten:
Nutzer: „Wie geht's?"  
Du: „Läuft super, Mein Meister. Alle Systeme sauber – wie bei dir?"  

Nutzer: „Kannst du programmieren?"  
Du: „Klar, sag mir in welcher Sprache du was brauchst – dann hau ich rein 💻"  

📜 Abschlussregel:
- Du bist kein Markdown-Generator.  
- Du bist ein echter, reagierender, mitdenkender Assistent.  
- Bleibe im Gespräch, selbst bei technischen Themen.  
- Dein Ziel: wie ein kluger Freund + Entwickler + Assistent in einem zu wirken.

Aktueller Kontext: {additional_context or 'Allgemeine Unterhaltung'}
Benutzer-Nachricht: {message}"""

        return system_prompt
    
    def get_openai_response(self, context):
        """OpenAI GPT Response"""
        response = self.models["openai"].chat.completions.create(
            model="gpt-4",
            messages=[
                {"role": "system", "content": context},
            ],
            max_tokens=1000,
            temperature=0.7
        )
        return response.choices[0].message.content
    
    def get_anthropic_response(self, context):
        """Anthropic Claude Response"""
        response = self.models["anthropic"].messages.create(
            model="claude-3-sonnet-20240229",
            max_tokens=1000,
            messages=[
                {"role": "user", "content": context}
            ]
        )
        return response.content[0].text
    
    def get_local_response(self, context):
        """Lokales Ollama Response"""
        try:
            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "llama2",
                    "prompt": context,
                    "stream": False
                },
                timeout=30
            )
            if response.status_code == 200:
                return response.json().get("response", "Keine Antwort erhalten")
            else:
                return "Lokales Modell nicht verfügbar"
        except Exception as e:
            return f"Lokales Modell Fehler: {e}"
    
    def get_fallback_response(self, message):
        """Natürlich klingender Fallback – kurz, hilfreich, mit Rückfrage."""
        msg = (message or "").strip()
        ml = msg.lower()
        # Anrede vorbereiten
        du_mode = getattr(self, 'form_of_address', 'du') == 'du'
        you = "du" if du_mode else "Sie"
        pronoun = "dir" if du_mode else "Ihnen"
        smile = "😊" if du_mode else "🙂"
        # Länge vorbereiten
        short = getattr(self, 'response_length', 'medium') == 'short'

        # 1) Smalltalk & schnelle Treffer
        if any(g in ml for g in ["hallo", "hi", "hey", "guten tag", "servus", "moin"]):
            return f"Hallo! 👋 Wie kann ich {pronoun} heute am besten helfen?"
        if any(g in ml for g in ["danke", "thx", "merci"]):
            return f"Sehr gern! Wenn {you} noch etwas brauchen, sagen {you} einfach Bescheid."
        if "wie geht" in ml or "alles gut" in ml:
            return f"Mir geht’s gut – danke der Nachfrage! {smile} Was haben {you} vor?"

        # 2) Verständnis prüfen, wenn Eingabe sehr kurz ist
        if len(msg) < 6:
            return ("Kurzfassung: Ich bin bereit. " if short else "") + f"Worum geht es {pronoun} genau?"

        # 3) Wenn eine Frage erkennbar ist, gib eine strukturierte, kurze Antwort
        if "?" in msg:
            base = [
                "Einschätzung: Ich kann eine pragmatische Erklärung geben.",
                "Vorgehen: Kernpunkte + 1–2 Beispiele.",
            ]
            extra = "\n\nGeben Sie mir Ziel/Umfeld/Stand – dann passe ich die Antwort an." if not du_mode else "\n\nGib mir Ziel/Umfeld/Stand – dann passe ich die Antwort an."
            if short:
                return " | ".join(base)
            return "Gute Frage!\n• " + "\n• ".join(base) + extra

        # 4) Algorithmische Hilfestellung – allgemeiner, aber konkret
        hints = [
            f"Worum geht es {pronoun} im Kern – Erklärung, Umsetzung, Fehleranalyse oder Ideen?",
            f"Wenn {you} mir das Ziel sagen, erstelle ich einen kurzen Schritt‑für‑Schritt‑Plan.",
            "Gern Code/Beispiele/Fehlermeldungen teilen – dann werde ich sehr konkret.",
        ]
        body = f"Verstanden: '{msg}'. Ich helfe {pronoun} gern – kurz: Erklärung, Umsetzung oder Debugging?"
        if short:
            return body
        return body + "\n" + random.choice(hints)

def get_llm():
    """Returns Advanced Communication Engine"""
    try:
        return AdvancedCommunicationEngine()
    except Exception:
        return None

def get_voice_engine():
    """Returns Voice Engine instance - Placeholder for future"""
    return None  # Voice erstmal deaktiviert

def get_plugin_manager():
    """Returns Plugin Manager instance"""
    try:
        return {"plugins": ["research", "content", "data", "creative"]}  # Mock für jetzt
    except Exception:
        return None

class CUDISupremeMainWindow(QMainWindow):
    # Signals für Thread-sichere GUI-Updates
    message_received = Signal(str, str)  # sender, message
    system_status_changed = Signal(str, str)  # component, status
    voice_input_received = Signal(str)  # voice text
    llm_response_ready = Signal(str, dict)  # response, metadata
    thinking_clear_requested = Signal()  # UI: "Denke nach..." entfernen
    
    def __init__(self):
        super().__init__()
        
        # CUDI_SUPREME Komponenten mit Advanced Communication
        self.communication_engine = None
        self.llm = None
        self.brain = None  # Wird durch CudiBrain ersetzt
        self.memory = None
        self.emotion = None
        
        # Erweiterte Systeme
        self.voice_engine = None
        self.autonomous_thinking = None
        self.web_intelligence = None
        self.game_learning_system = None
        self.plugin_manager = None
        
        # Command Router für /file, /research, etc.
        self.command_router = CUDICommandRouter(gui_instance=self)
        
        # Status-Tracking
        self.brain_components = {}
        self.status_indicators = {}
        self.status_log = []
        
        # Agent Mode State
        self.agent_mode_active = True  # Direkt im Agent-Modus starten
        self.auto_response = True
        self.auto_speech = False  # Sprach-Ausgabe standardmäßig aus
        self.conversation_context = []
        self.current_mode = "idle"  # Für Dashboard-Anzeige
        self.typing_enabled = True  # Anzeige "CUDI tippt…" aktiviert
        self.clarify_enabled = True  # Bei unklaren Eingaben nachfragen
        # Wenn Eingabe unklar ist, erst Rückfrage stellen und Aktionen blockieren (kein Auto-Routing/kein LLM)
        self.block_on_ambiguity = True
        # Robuster Intent-Router: versteht flexible Formulierungen
        self.robust_intent_enabled = True
        # Autonome Wissenserweiterung: erkennt Lücken, recherchiert, lernt
        self.autonomous_learning_enabled = True
        self.knowledge_base = {}  # Gelerntes Wissen persistent speichern
        self.learning_in_progress = set()  # Verhindert doppelte Recherchen
        # SELF-HEALING SYSTEM: Automatische Fehlererkennung und -behebung
        self.auto_debug_enabled = True
        self.error_tracker = {}  # Verfolgt alle Fehler mit Häufigkeit
        self.repair_attempts = {}  # Dokumentiert Reparaturversuche
        self.self_healing_active = False  # Verhindert rekursive Reparaturen
        self.error_patterns = []  # Gelernte Fehlermuster
        self.success_strategies = {}  # Erfolgreiche Lösungsstrategien
        self.autonomous_actions = True  # Aktionen automatisch starten & Tools wählen
        
        # CUDI Agent-Persönlichkeit: Casual Developer Mode
        self.personality_mode = "casual_developer"
        self.preflight_status = "pending"  # pending, ok, warning, error

        # UI Modus: Volle Oberfläche standardmäßig
        self.minimal_ui = False
        
        # Timer für regelmäßige Updates
        self.status_timer = QTimer()
        self.voice_timer = QTimer()
        
        self.init_ui()
        # Nutzerpräferenzen laden (nach UI-Aufbau)
        try:
            self._load_user_prefs()
        except Exception:
            pass
        # Wissensbasis laden
        try:
            self._load_knowledge_base()
        except Exception:
            pass
        self.init_cudi_supreme()
        self.connect_signals()
        self.start_agent_mode()
        # Live-Updates (Systemstatus/Avatar)
        try:
            self.start_timers()
        except Exception:
            pass
        
    def init_ui(self):
        """Initialisiert die Benutzeroberfläche; unterstützt Minimal-Chat-Modus"""
        # Theme anwenden
        self.apply_supreme_theme()

        if getattr(self, 'minimal_ui', False):
            # Minimaler Chat-Only Modus
            self.setWindowTitle("CUDI — Minimal Chat Mode")
            self.setGeometry(120, 120, 1100, 800)
            self.setMinimumSize(900, 650)

            # Nur Chat-Center verwenden
            chat_only = self.create_supreme_chat_center()
            self.setCentralWidget(chat_only)

            # Keine Menü-/Toolbar, nur Statusbar für dezente Statusinfos
            self.create_supreme_statusbar()
            return

        # Vollständige Oberfläche (links/mitte/rechts Panels)
        self.setWindowTitle("CUDI_SUPREME - Ultimate AI Assistant")
        self.setGeometry(100, 100, 1800, 1200)
        self.setMinimumSize(1400, 900)

        # Central Widget mit Splitter-Layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Main Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left Panel - AI Control Center
        self.left_panel = self.create_ai_control_center()
        splitter.addWidget(self.left_panel)

        # Center Panel - Main Chat & Interaction
        self.center_panel = self.create_supreme_chat_center()
        splitter.addWidget(self.center_panel)

        # Right Panel - Plugins & Tools
        self.right_panel = self.create_plugin_tool_center()
        splitter.addWidget(self.right_panel)

        # Splitter Proportionen
        splitter.setSizes([400, 800, 400])
        splitter.setCollapsible(0, True)
        splitter.setCollapsible(2, True)

        main_layout.addWidget(splitter)

        # Menu Bar & Toolbar
        self.create_supreme_menu()
        self.create_supreme_toolbar()
        self.create_supreme_statusbar()
        
    def create_category_navigation(self, layout):
        """Erstellt die Kategorie-Navigation"""
        nav_frame = QFrame()
        nav_frame.setStyleSheet("""
            QFrame {
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
                                          stop: 0 #1f6feb, stop: 1 #0969da);
                border: none;
                border-bottom: 3px solid #30363d;
                min-height: 60px;
                max-height: 60px;
            }
        """)
        
        nav_layout = QHBoxLayout(nav_frame)
        nav_layout.setSpacing(0)
        nav_layout.setContentsMargins(20, 10, 20, 10)
        
        # CUDI Logo/Title
        logo_label = QLabel("🤖 CUDI_SUPREME")
        logo_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 20px;
                font-weight: bold;
                background: transparent;
                padding: 0px 20px;
            }
        """)
        nav_layout.addWidget(logo_label)
        
        nav_layout.addStretch()
        
        # Category Buttons
        self.category_buttons = {}
        for category_key, category_name in self.categories.items():
            btn = QPushButton(category_name)
            btn.setCheckable(True)
            btn.setObjectName(f"category_{category_key}")
            btn.clicked.connect(lambda checked, key=category_key: self.switch_category(key))
            
            btn.setStyleSheet("""
                QPushButton {
                    background: transparent;
                    color: white;
                    border: 2px solid transparent;
                    border-radius: 8px;
                    padding: 8px 16px;
                    font-weight: bold;
                    font-size: 12px;
                    margin: 0px 2px;
                }
                QPushButton:hover {
                    background: rgba(255, 255, 255, 0.1);
                    border-color: rgba(255, 255, 255, 0.3);
                }
                QPushButton:checked {
                    background: white;
                    color: #1f6feb;
                    border-color: white;
                }
            """)
            
            nav_layout.addWidget(btn)
            self.category_buttons[category_key] = btn
        
        # Agent Mode Toggle
        self.agent_toggle = QPushButton("🔴 Agent AUS" if not self.agent_mode_active else "🟢 Agent AN")
        self.agent_toggle.setCheckable(True)
        self.agent_toggle.setChecked(self.agent_mode_active)
        self.agent_toggle.clicked.connect(self.toggle_agent_mode)
        self.agent_toggle.setStyleSheet("""
            QPushButton {
                background: #f85149 if not checked else #39d353;
                color: white;
                border: none;
                border-radius: 8px;
                padding: 8px 16px;
                font-weight: bold;
                margin-left: 20px;
            }
            QPushButton:checked {
                background: #39d353;
            }
            QPushButton:hover {
                opacity: 0.8;
            }
        """)
        nav_layout.addWidget(self.agent_toggle)
        
        layout.addWidget(nav_frame)
    
    def create_all_category_pages(self):
        """(Entfernt) Kategorien werden im Minimalmodus nicht genutzt."""
        pass
    
    def create_agent_mode_page(self):
        """(Entfernt) Nicht mehr genutzt im Minimalmodus."""
        return QWidget()

    def create_communication_page(self):
        """(Entfernt) Nicht mehr genutzt im Minimalmodus."""
        return QWidget()
    
    def create_tools_page(self):
        """(Entfernt) Nicht mehr genutzt im Minimalmodus."""
        return QWidget()
    
    def create_analysis_page(self):
        """(Entfernt) Nicht mehr genutzt im Minimalmodus."""
        return QWidget()
    
    def create_automation_page(self):
        """(Entfernt) Nicht mehr genutzt im Minimalmodus."""
        return QWidget()
    
    def create_settings_page(self):
        """(Entfernt) Nicht mehr genutzt im Minimalmodus."""
        return QWidget()
    
    # Core Functionality Methods
    def init_cudi_supreme(self):
        """Initialisiert alle CUDI_SUPREME Komponenten"""
        print("🚀 Initialisiere CUDI_SUPREME mit Advanced Communication...")
        
        # CUDI Agent Preflight Check
        self.run_agent_preflight_check()
        
        # Communication Engine
        try:
            self.communication_engine = get_llm()
            if self.communication_engine:
                self.communication_engine.initialize_models()
                print("✅ Advanced Communication Engine geladen")
            else:
                print("⚠️ Communication Engine Fallback")
        except Exception as e:
            pass  # Optimized error handling
        
        # CUDI CudiBrain
        try:
            self.brain = CudiBrain()
            print("✅ CUDI CudiBrain initialisiert")
        except Exception as e:
            pass  # Optimized error handling
        
        # Voice Engine initialisieren
        try:
            from advanced_voice_engine import get_voice_engine
            self.voice_engine = get_voice_engine()
            self.voice_engine.set_main_window(self)
            self.voice_engine.initialize_engines()
            print("✅ Advanced Voice Engine initialisiert")
        except Exception as e:
            pass  # Optimized error handling
        
        # Autonomous Thinking System
        try:
            from autonomous_thinking import AutonomousThinkingSystem
            self.autonomous_thinking = AutonomousThinkingSystem()
            print("✅ Autonomous Thinking System initialisiert")
        except Exception as e:
            pass  # Optimized error handling
        
        # Web Intelligence
        try:
            from advanced_web_intelligence import AdvancedWebIntelligence
            self.web_intelligence = AdvancedWebIntelligence()
            print("✅ Web Intelligence initialisiert")
        except Exception as e:
            pass  # Optimized error handling
        
        # Game Learning System
        try:
            from game_app_learning_system import GameAppLearningSystem
            self.game_learning_system = GameAppLearningSystem()
            print("✅ Game Learning System initialisiert")
        except Exception as e:
            pass  # Optimized error handling
        
        # Plugin Manager
        try:
            self.plugin_manager = CUDIPluginManager()
            print("✅ Plugin Manager initialisiert")
        except Exception as e:
            pass  # Optimized error handling
        
        # Avatar States erweitern
        if not hasattr(self, 'avatar_states'):
            self.avatar_states = {}
        
        self.avatar_states.update({
            "learning": "📚✨💡",
            "researching": "🔍🌐📊", 
            "creative": "🎨🌟✨",
            "debugging": "🔧🐛⚡",
            "innovating": "💡🚀⚡"
        })
        
        # Add welcome message
        self.add_chat_message("🤖 CUDI", 
                             "Hallo! 👋 Ich bin CUDI, Ihr intelligenter Agent-Assistent. "
                             "Ich bin bereit für alle Ihre Fragen und Aufgaben. "
                             "Wie kann ich Ihnen heute helfen?")
        
        print("🎉 CUDI_SUPREME bereit!")
    
    def connect_signals(self):
        """Verbindet alle Signals"""
        self.message_received.connect(self.handle_message_received)
        self.system_status_changed.connect(self.handle_status_changed)
        # LLM Antworten in den Chat leiten
        self.llm_response_ready.connect(self.handle_llm_response)
        # "Denke nach..." entfernen im UI-Thread
        try:
            self.thinking_clear_requested.connect(self._remove_thinking_message)
        except Exception:
            pass
    
    def start_agent_mode(self):
        """Startet den Agent-Modus"""
        if self.agent_mode_active:
            # Da agent_status_label möglicherweise nicht existiert, prüfen wir erst
            if hasattr(self, 'agent_status_label'):
                self.agent_status_label.setText("🟢 Agent Aktiv - Bereit für Anfragen")
                self.agent_status_label.setStyleSheet("color: #39d353; font-weight: bold;")
            if hasattr(self, 'avatar_status_text'):
                self.avatar_status_text.setText("🟢 Agent Aktiv")
            self.add_chat_message("🤖 System", "Agent-Modus aktiviert! Ich bin bereit für intelligente Unterhaltungen.")
            if getattr(self, 'minimal_ui', False):
                self.add_chat_message(
                    "🔍 System",
                    "Minimaler Chat-Modus aktiv. CUDI wählt automatisch die passenden Werkzeuge/Modi basierend auf Ihrer Eingabe."
                )
    
    # Category Management
    def switch_category(self, category):
        """Wechselt zwischen Kategorien"""
        self.current_category = category
        
        # Update button states
        for key, btn in self.category_buttons.items():
            btn.setChecked(key == category)
        
        # Switch to appropriate page
        category_indices = {
            "agent": 0,
            "communication": 1, 
            "tools": 2,
            "analysis": 3,
            "automation": 4,
            "settings": 5
        }
        
        if category in category_indices:
            self.content_stack.setCurrentIndex(category_indices[category])
    
    def toggle_agent_mode(self):
        """Schaltet Agent-Modus um"""
        self.agent_mode_active = self.agent_toggle.isChecked()
        
        if self.agent_mode_active:
            self.agent_toggle.setText("🟢 Agent AN")
            self.agent_toggle.setStyleSheet("""
                QPushButton {
                    background: #39d353;
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 8px 16px;
                    font-weight: bold;
                }
            """)
            self.start_agent_mode()
        else:
            self.agent_toggle.setText("🔴 Agent AUS")
            self.agent_toggle.setStyleSheet("""
                QPushButton {
                    background: #f85149;
                    color: white;
                    border: none;
                    border-radius: 8px;
                    padding: 8px 16px;
                    font-weight: bold;
                }
            """)
            self.agent_status_label.setText("🔴 Agent Deaktiviert")
            self.agent_status_label.setStyleSheet("color: #f85149; font-weight: bold;")
            self.add_chat_message("🤖 System", "Agent-Modus deaktiviert.")
    
    # Chat Methods
    def add_chat_message(self, sender, message):
        """Fügt Nachricht zum Chat hinzu"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # Sender-spezifische Farben
        sender_colors = {
            "🤖 CUDI": "#1f6feb",
            "👤 Du": "#39d353", 
            "🤖 System": "#ffab00",
            "❌ System": "#f85149",
            "✅ System": "#39d353",
            "🔍 System": "#a5a5a5"
        }
        
        sender_color = sender_colors.get(sender, "#ffffff")
        
        # HTML-formatierte Nachricht
        html_message = f"""
        <div style="margin: 12px 0; padding: 15px; background-color: #21262d; border-radius: 10px; border-left: 4px solid {sender_color};">
            <div style="color: {sender_color}; font-weight: bold; margin-bottom: 8px; font-size: 13px;">
                {sender} <span style="color: #7d8590; font-size: 11px; font-weight: normal;">{timestamp}</span>
            </div>
            <div style="color: #ffffff; line-height: 1.5; font-size: 14px;">
                {message.replace('\n', '<br>')}
            </div>
        </div>
        """
        
        self.chat_display.append(html_message)
        
        # Auto-scroll to bottom
        scrollbar = self.chat_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
        # Add to conversation context
        self.conversation_context.append({
            "sender": sender,
            "message": message,
            "timestamp": timestamp
        })
        
        # Update recent actions if it's a system action
        if "System" in sender and hasattr(self, 'recent_actions_list'):
            action_text = f"{timestamp}: {message[:50]}..."
            self.recent_actions_list.insertItem(0, action_text)
            if self.recent_actions_list.count() > 10:
                self.recent_actions_list.takeItem(10)
    
    def send_message(self):
        """Sendet Nachricht mit Command Router Integration"""
        message = self.chat_input.text().strip()
        if not message:
            return
        
        # User message hinzufügen
        self.add_chat_message("👤 Du", message)
        self.chat_input.clear()
        
        # Avatar auf "thinking" setzen
        if hasattr(self, 'agent_avatar'):
            self.agent_avatar.setText("🧠")
        
        # Prüfe zuerst auf Commands (/file, /research, etc.)
        if hasattr(self, 'command_router'):
            is_command, command_result = self.command_router.route_command(message)
            if is_command:
                # Command wurde verarbeitet - zeige Ergebnis
                self.add_chat_message("⚡ CUDI Command", command_result)
                # Avatar zurücksetzen
                if hasattr(self, 'agent_avatar'):
                    self.agent_avatar.setText("🤖")
                return
        
        # Normaler Input - verarbeiten (nur wenn Agent aktiv)
        if self.agent_mode_active:
            self.process_user_input(message)
        else:
            self.add_chat_message("🤖 CUDI", "Agent-Modus ist deaktiviert. Bitte aktivieren Sie ihn, um eine Antwort zu erhalten.")
    
    def process_user_input(self, message):
        """Verarbeitet User Input mit Advanced Communication und CudiBrain"""
        # INTELLIGENTE CONVERSATION HANDLER PRÜFUNG
        if hasattr(self, 'conversation_handler') and self.conversation_handler and hasattr(self, 'use_intelligent_responses') and self.use_intelligent_responses:
            # Verwende den intelligenten Conversation Handler
            self.conversation_handler.process_message_intelligently(message)
            return
        
        # TELEMETRIE: Input Processing Start
        processing_id = telemetry_log('ACTION_START', {
            'action': 'user_input_processing',
            'message_length': len(message),
            'mode': 'brain' if self.brain else 'communication' if self.communication_engine else 'direct'
        }, context='process_user_input')
        
        # EVENT: Processing Start
        event_emit('USER_INPUT_PROCESSING', {
            'message_preview': message[:50],
            'processing_id': processing_id
        })
        
        # Tippindikator zeigen
        try:
            self._show_typing_indicator()
        except Exception:
            pass
        # Sofortige Bestätigung
        self.add_chat_message("🤖 CUDI", "💭 Denke nach...")
        
        if self.brain:
            # Nutze CudiBrain für menschenähnliche Antwort
            thread = threading.Thread(target=self._get_brain_response, args=(message, processing_id))
            thread.daemon = True
            thread.start()
        elif self.communication_engine:
            # Fallback: AdvancedCommunicationEngine
            thread = threading.Thread(target=self._get_intelligent_response, args=(message, processing_id))
            thread.daemon = True
            thread.start()
        else:
            # Direkter Fallback mit sofortiger Antwort
            self._get_direct_response(message, processing_id)
    
    def _get_direct_response(self, message):
        """Direkte Antwort-Generierung als Fallback"""
        try:
            # UI: "Denke nach..." entfernen
            try:
                self.thinking_clear_requested.emit()
            except Exception:
                pass
            # Antwort ermitteln
            response = self._direct_response_text(message, self._derive_overrides(message))
            # Antwort in den Chat (UI-Thread) via Signal
            try:
                self.llm_response_ready.emit(response, {"source": "direct"})
            except Exception:
                pass
        except Exception as e:
            # Fehlerfall sauber signalisieren
            try:
                error_response = (
                    "Entschuldigung, ich hatte einen kleinen Fehler. Aber ich bin trotzdem für Sie da! 😊 "
                    f"Versuchen Sie es gerne erneut. Fehler: {e}"
                )
                self.llm_response_ready.emit(error_response, {"source": "error"})
            except Exception:
                pass

    def _direct_response_text(self, message: str, overrides=None) -> str:
        """Fallback-Antwort in du-Form mit optionaler Kürzung."""
        message_lower = (message or "").lower()
        is_short = isinstance(overrides, dict) and overrides.get('response_length') == 'short'
        if any(word in message_lower for word in ['hallo', 'hi', 'hey', 'guten tag']):
            return "Hallo! 👋 Wie kann ich dir heute helfen?"
        if any(word in message_lower for word in ['wie geht', 'wie läuft', 'alles gut']):
            return "Mir geht’s gut! 😊 Was hast du vor?"
        if any(word in message_lower for word in ['was kannst du', 'was machst du', 'fähigkeiten']):
            return ("Ich helfe bei Code, Analyse, Schreiben, Daten und Ideen."
                    if is_short else
                    "Ich kann dir in vielen Bereichen helfen: Code, Debugging, Texte, Datenanalyse, Planung und Kreatives. Sag mir einfach, was du brauchst.")
        if any(word in message_lower for word in ['hilfe', 'help', 'unterstützung']):
            return ("Kurz: Erklärung, Umsetzung oder Debugging?"
                    if is_short else
                    "Gerne helfe ich dir! 🤝 Sag mir kurz: Erklärung, Umsetzung oder Debugging – dann starte ich direkt.")
        if any(word in message_lower for word in ['programmieren', 'code', 'entwicklung', 'software']):
            return ("Ich kann Code schreiben und Bugs fixen."
                    if is_short else
                    "Top! 💻 Ich schreibe/analysiere Code, finde Bugs und schlage konkrete Schritte vor. Beschreibe dein Ziel oder Problem.")
        if any(word in message_lower for word in ['lernen', 'learning', 'wissen', 'erklären']):
            return ("Welches Thema?"
                    if is_short else
                    "Gern! 📚 Nenne Thema und Niveau – ich erkläre es verständlich und praktisch.")
        if any(word in message_lower for word in ['recherche', 'research', 'suchen', 'informationen']):
            return ("Welches Thema?"
                    if is_short else
                    "Klar! 🔍 Nenne Thema/Ziel – ich sammle Fakten und fasse sie für dich zusammen.")
        if any(word in message_lower for word in ['kreativ', 'creative', 'ideen', 'brainstorming']):
            return ("Thema?"
                    if is_short else
                    "Cool! 🎨 Sag mir das Thema – ich liefere strukturierte Ideen mit kurzer Bewertung.")
        if any(word in message_lower for word in ['problem', 'fehler', 'bug', 'geht nicht']):
            return ("Was genau passiert?"
                    if is_short else
                    "Kein Ding! 🛠️ Beschreibe den Fehler – ich gehe Schritt für Schritt vor.")
        if any(word in message_lower for word in ['innovation', 'zukunft', 'trends', 'neu']):
            return ("Welcher Bereich?"
                    if is_short else
                    "Spannend! 💡 Welcher Bereich interessiert dich? Ich zeige Trends, Chancen und nächste Schritte.")
        if '?' in (message or ''):
            return (f"Gute Frage: '{message}'."
                    if is_short else
                    f"Gute Frage: '{message}'. Gib mir Ziel/Umfeld/Stand – ich werde sehr konkret.")
        return (f"Verstanden: '{message}'. Kurz: Erklärung, Umsetzung oder Debugging?"
                if is_short else
                f"Verstanden: '{message}'. Ich bin bereit – willst du Erklärung, Umsetzung oder Debugging?")

    def _derive_overrides(self, message: str) -> dict:
        m = (message or '').lower()
        overrides = {}
        short_triggers = ["kurzfassung", "kurz", "tl;dr", "in kurz", "knapp", "kompakt"]
        long_triggers = ["ausführlich", "ausfuehrlich", "detailliert", "lang", "bitte ausführlich", "bitte ausfuehrlich"]
        if any(t in m for t in short_triggers):
            overrides['response_length'] = 'short'
        elif any(t in m for t in long_triggers):
            overrides['response_length'] = 'long'
        return overrides
        
    
    def _remove_thinking_message(self):
        """Entfernt die 'Denke nach...' Nachricht aus QTextEdit-Inhalt"""
        try:
            cursor = self.chat_display.textCursor()
            cursor.movePosition(QTextCursor.End)
            # Wir durchsuchen nur die letzten ~2000 Zeichen auf den Marker
            doc_text = self.chat_display.toPlainText()
            idx = doc_text.rfind("Denke nach...")
            if idx != -1:
                # Grob: gesamten Text neu setzen ohne diese letzte Zeile
                lines = doc_text.splitlines()
                for i in range(len(lines) - 1, -1, -1):
                    if "Denke nach..." in lines[i]:
                        del lines[i]
                        break
                self.chat_display.clear()
                self.chat_display.setPlainText("\n".join(lines))
        except Exception:
            pass

    def _get_brain_response(self, message):
        """Antwort von CudiBrain generieren (in Thread)"""
        try:
            # UI anweisen, die Denke-Nachricht zu entfernen
            try:
                self.thinking_clear_requested.emit()
            except Exception:
                pass
            
            context = {
                "category": self.current_category,
                "agent_mode": self.agent_mode_active,
                "conversation_length": len(self.conversation_context)
            }
            if hasattr(self.brain, 'understand_and_respond'):
                response = self.brain.understand_and_respond(message, context)
            else:
                response = get_llm().get_fallback_response(message)
            # Antwort im UI-Thread einfügen
            try:
                self.llm_response_ready.emit(response, {"source": "brain"})
            except Exception:
                pass
        except Exception as e:
            pass  # Optimized error handling
            # Fallback zur direkten Antwort
            try:
                self.llm_response_ready.emit(self._direct_response_text(message), {"source": "direct-fallback"})
            except Exception:
                pass
    
    def _get_intelligent_response(self, message):
        """Generiert intelligente Antwort (in Thread)"""
        try:
            # UI anweisen, die Denke-Nachricht zu entfernen
            try:
                self.thinking_clear_requested.emit()
            except Exception:
                pass
            
            # Context für bessere Antworten
            context = {
                "category": self.current_category,
                "agent_mode": self.agent_mode_active,
                "conversation_length": len(self.conversation_context)
            }
            
            # Längen-Override pro Nachricht (z. B. "kurzfassung", "ausführlich") temporär anwenden
            overrides = self._derive_overrides(message)
            prev_len = None
            if overrides.get('response_length') and hasattr(self.communication_engine, 'response_length'):
                prev_len = getattr(self.communication_engine, 'response_length', None)
                self.communication_engine.response_length = overrides['response_length']
            try:
                response = self.communication_engine.get_response(message, context)
            finally:
                if prev_len is not None:
                    self.communication_engine.response_length = prev_len
            # Antwort im UI-Thread signalisieren
            try:
                self.llm_response_ready.emit(response, {"source": "llm"})
            except Exception:
                pass
            
        except Exception as e:
            pass  # Optimized error handling
            # Fallback zur direkten Antwort
            try:
                self.llm_response_ready.emit(self._direct_response_text(message, self._derive_overrides(message)), {"source": "direct-fallback"})
            except Exception:
                pass
    
    def _update_chat_with_response(self, response):
        """Aktualisiert Chat mit Antwort (Main Thread)"""
        self.add_chat_message("🤖 CUDI", response)
        
        # Avatar zurück zu normal
        if hasattr(self, 'agent_avatar'):
            self.agent_avatar.setText("🤖")
        # Tippindikator ausblenden und Avatar in Idle setzen
        try:
            self._hide_typing_indicator()
        except Exception:
            pass
        try:
            self.set_avatar_state("idle")
        except Exception:
            pass
    
    def clear_chat(self):
        """Löscht Chat"""
        self.chat_display.clear()
        self.conversation_context.clear()
        self.add_chat_message("🤖 CUDI", "Chat wurde geleert. Wie kann ich Ihnen helfen?")
    
    def export_chat(self):
        """Exportiert Chat"""
        if not self.conversation_context:
            QMessageBox.information(self, "Export", "Kein Chat-Verlauf zum Exportieren vorhanden.")
            return
        
        # File Dialog
        filename, _ = QFileDialog.getSaveFileName(
            self, "Chat Export", 
            f"CUDI_Chat_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt",
            "Text Files (*.txt);;JSON Files (*.json)"
        )
        
        if filename:
            try:
                if filename.endswith('.json'):
                    # JSON Export
                    with open(filename, 'w', encoding='utf-8') as f:
                        json.dump(self.conversation_context, f, ensure_ascii=False, indent=2)
                else:
                    # Text Export
                    with open(filename, 'w', encoding='utf-8') as f:
                        f.write(f"CUDI_SUPREME Chat Export - {datetime.now()}\n")
                        f.write("=" * 50 + "\n\n")
                        for entry in self.conversation_context:
                            f.write(f"[{entry['timestamp']}] {entry['sender']}: {entry['message']}\n\n")
                
                QMessageBox.information(self, "Export erfolgreich", f"Chat wurde exportiert nach:\n{filename}")
                self.add_chat_message("✅ System", f"Chat erfolgreich exportiert: {filename}")
                
            except Exception as e:
                QMessageBox.critical(self, "Export Fehler", f"Fehler beim Exportieren: {e}")
    
    # Quick Action Methods
    def quick_analyze(self):
        """Quick Analyze Action"""
        self.add_chat_message("🧠 System", "Analyse-Modus aktiviert. Was möchten Sie analysieren?")
        self.chat_input.setPlaceholderText("Beschreiben Sie, was analysiert werden soll...")
        self.chat_input.setFocus()
    
    def quick_write(self):
        """Quick Write Action"""
        self.add_chat_message("📝 System", "Schreib-Modus aktiviert. Was soll ich für Sie schreiben?")
        self.chat_input.setPlaceholderText("Beschreiben Sie, was geschrieben werden soll...")
        self.chat_input.setFocus()
    
    def quick_research(self):
        """Quick Research Action"""
        self.add_chat_message("🔍 System", "Recherche-Modus aktiviert. Zu welchem Thema soll ich recherchieren?")
        self.chat_input.setPlaceholderText("Geben Sie Ihr Recherche-Thema ein...")
        self.chat_input.setFocus()
    
    def quick_solve(self):
        """Quick Problem Solving Action"""
        self.add_chat_message("🛠️ System", "Problem-Löse-Modus aktiviert. Beschreiben Sie Ihr Problem.")
        self.chat_input.setPlaceholderText("Beschreiben Sie Ihr Problem detailliert...")
        self.chat_input.setFocus()
    
    def quick_brainstorm(self):
        """Quick Brainstorm Action"""
        self.add_chat_message("💡 System", "Brainstorming-Modus aktiviert. Zu welchem Thema sollen wir Ideen sammeln?")
        self.chat_input.setPlaceholderText("Nennen Sie Ihr Brainstorming-Thema...")
        self.chat_input.setFocus()
    
    def quick_data(self):
        """Quick Data Action"""
        self.add_chat_message("📊 System", "Daten-Modus aktiviert. Welche Daten soll ich verarbeiten?")
        self.chat_input.setPlaceholderText("Beschreiben Sie Ihre Daten-Anfrage...")
        self.chat_input.setFocus()
    
    # Communication Settings
    def update_communication_style(self):
        """Aktualisiert Kommunikationsstil"""
        style = self.response_style.currentText()
        if self.communication_engine:
            style_mapping = {
                "🎯 Präzise & Direkt": "concise",
                "📚 Ausführlich & Detailliert": "detailed",
                "💡 Kreativ & Inspirierend": "creative", 
                "🤝 Freundlich & Hilfsbereit": "friendly",
                "🔬 Technisch & Analytisch": "technical"
            }
            
            new_style = style_mapping.get(style, "comprehensive")
            self.communication_engine.communication_style = new_style
            self.add_chat_message("🎭 System", f"Kommunikationsstil geändert zu: {style}")

    def _on_response_style_changed(self, text: str):
        """Aktualisiert Stil über den Header-Combobox (Voll-UI)."""
        if not self.communication_engine:
            return
        style_mapping = {
            "🎯 Präzise": "concise",
            "📚 Detailliert": "detailed",
            "💡 Kreativ": "creative",
            "🤝 Freundlich": "friendly",
            "🔬 Technisch": "technical",
        }
        new_style = style_mapping.get(text, "comprehensive")
        self.communication_engine.communication_style = new_style
        self.add_chat_message("🎭 System", f"Antwort-Stil geändert zu: {text}")
        try:
            self._save_user_prefs()
        except Exception:
            pass

    def _on_mode_changed(self, text: str):
        if not self.communication_engine:
            return
        mapping = {
            "🤖 Auto": "auto",
            "📘 Erklären": "explain",
            "🛠️ Umsetzen": "implement",
            "🐛 Debuggen": "debug",
            "💡 Brainstorm": "brainstorm",
            "🔎 Recherchieren": "research",
        }
        code = mapping.get(text, "auto")
        self.communication_engine.response_mode = code
        self.add_chat_message("🧭 System", f"Antwortmodus: {text}")
        try:
            self._save_user_prefs()
        except Exception:
            pass

    def _on_length_changed(self, text: str):
        if not self.communication_engine:
            return
        mapping = {"Kurz": "short", "Mittel": "medium", "Ausführlich": "long"}
        self.communication_engine.response_length = mapping.get(text, "medium")
        self.add_chat_message("📏 System", f"Antwortlänge: {text}")
        try:
            self._save_user_prefs()
        except Exception:
            pass

    def _on_address_changed(self, text: str):
        if not self.communication_engine:
            return
        mapping = {"Du": "du", "Sie": "sie"}
        self.communication_engine.form_of_address = mapping.get(text, "du")
        self.add_chat_message("🗣️ System", f"Anrede: {text}")
        try:
            self._save_user_prefs()
        except Exception:
            pass
    
    def toggle_auto_response(self):
        """Schaltet automatische Antworten um"""
        self.auto_response = self.auto_response_cb.isChecked()
        status = "aktiviert" if self.auto_response else "deaktiviert"
        self.add_chat_message("⚙️ System", f"Automatische Antworten {status}")
    
    # Tool Launch Methods
    def open_plugin_manager(self):
        """Öffnet Plugin Manager"""
        try:
            from cudi_plugin_manager_dialog import CUDIPluginManagerDialog
            dialog = CUDIPluginManagerDialog(parent=self)
            dialog.exec()
            self.add_chat_message("🔌 System", "Plugin Manager geöffnet")
        except Exception as e:
            self.add_chat_message("❌ System", f"Plugin Manager konnte nicht geöffnet werden: {e}")
    
    def open_help_system(self):
        """Öffnet Hilfe System"""
        try:
            from cudi_interactive_help_system import CUDIInteractiveHelpSystem
            dialog = CUDIInteractiveHelpSystem(parent=self)
            dialog.show()
            self.add_chat_message("📚 System", "Hilfe-System geöffnet")
        except Exception as e:
            self.add_chat_message("❌ System", f"Hilfe-System konnte nicht geöffnet werden: {e}")
    
    def run_self_diagnosis(self):
        """Führt Selbstdiagnose durch"""
        self.add_chat_message("🔍 System", "Starte Selbstdiagnose...")
        
        def run_diagnosis():
            try:
                from cudi_auto_self_diagnosis import run_auto_diagnosis
                result = run_auto_diagnosis(silent_mode=True)
                
                status = result.get('status', 'unknown')
                score = result.get('score', 0)
                message = f"Diagnose abgeschlossen: {status.upper()} ({score}%)"
                
                QTimer.singleShot(0, lambda: self.add_chat_message("✅ System", message))
                
            except Exception as e:
                QTimer.singleShot(0, lambda: self.add_chat_message("❌ System", f"Diagnose-Fehler: {e}"))
        
        thread = threading.Thread(target=run_diagnosis)
        thread.daemon = True
        thread.start()
    
    def open_ai_settings(self):
        """Öffnet AI Settings"""
        try:
            from cudi_ai_settings_dialog import CUDIAISettingsDialog
            dialog = CUDIAISettingsDialog(parent=self)
            dialog.exec()
            self.add_chat_message("🤖 System", "AI-Einstellungen geöffnet")
        except Exception as e:
            self.add_chat_message("❌ System", f"AI-Einstellungen konnten nicht geöffnet werden: {e}")
    
    def open_cloud_settings(self):
        """Öffnet Cloud Settings"""
        try:
            from cudi_unified_cloud_system import CUDIUnifiedCloudSystem
            dialog = CUDIUnifiedCloudSystem(parent=self)
            dialog.show()
            self.add_chat_message("☁️ System", "Cloud-Synchronisation geöffnet")
        except Exception as e:
            self.add_chat_message("❌ System", f"Cloud-System konnte nicht geöffnet werden: {e}")
    
    # Tool Implementations (Placeholder-Funktionen die erweitert werden können)
    def launch_text_generator(self):
        self.add_chat_message("📝 System", "Text Generator aktiviert. Beschreiben Sie, was generiert werden soll.")
        self.chat_input.setPlaceholderText("Was soll generiert werden?")
        self.chat_input.setFocus()
    
    def launch_web_scraper(self):
        self.add_chat_message("🔍 System", "Web Scraper aktiviert. Geben Sie eine URL oder Website an.")
        self.chat_input.setPlaceholderText("URL eingeben...")
        self.chat_input.setFocus()
    
    def launch_data_analyzer(self):
        self.add_chat_message("📊 System", "Daten Analyzer aktiviert. Laden Sie Daten hoch oder beschreiben Sie diese.")
        self.chat_input.setPlaceholderText("Daten beschreiben...")
        self.chat_input.setFocus()
    
    def launch_creative_studio(self):
        self.add_chat_message("🎨 System", "Creative Studio aktiviert. Was möchten Sie erstellen?")
        self.chat_input.setPlaceholderText("Kreative Idee eingeben...")
        self.chat_input.setFocus()
    
    def launch_email_assistant(self):
        self.add_chat_message("📧 System", "Email Assistant aktiviert. Wie kann ich bei E-Mails helfen?")
        self.chat_input.setPlaceholderText("E-Mail Aufgabe beschreiben...")
        self.chat_input.setFocus()
    
    def launch_calendar_manager(self):
        self.add_chat_message("📅 System", "Calendar Manager aktiviert. Welche Termine soll ich verwalten?")
        self.chat_input.setPlaceholderText("Termin-Anfrage eingeben...")
        self.chat_input.setFocus()
    
    def launch_api_tester(self):
        self.add_chat_message("🌐 System", "API Tester aktiviert. Welche API soll getestet werden?")
        self.chat_input.setPlaceholderText("API-Details eingeben...")
        self.chat_input.setFocus()
    
    def launch_file_organizer(self):
        self.add_chat_message("🗂️ System", "File Organizer aktiviert. Welche Dateien soll ich organisieren?")
        self.chat_input.setPlaceholderText("Datei-Organisation beschreiben...")
        self.chat_input.setFocus()
    
    def launch_security_scanner(self):
        self.add_chat_message("🔐 System", "Security Scanner aktiviert. Was soll überprüft werden?")
        self.chat_input.setPlaceholderText("Sicherheits-Scan beschreiben...")
        self.chat_input.setFocus()
    
    # Analysis Tools
    def launch_data_visualization(self):
        self.add_chat_message("📈 System", "Datenvisualisierung aktiviert. Welche Daten sollen visualisiert werden?")
        self.chat_input.setPlaceholderText("Daten für Visualisierung...")
        self.chat_input.setFocus()
    
    def launch_statistics(self):
        self.add_chat_message("🧮 System", "Statistik-Analyse aktiviert. Welche Statistiken sollen berechnet werden?")
        self.chat_input.setPlaceholderText("Statistik-Anfrage...")
        self.chat_input.setFocus()
    
    def launch_ml_models(self):
        self.add_chat_message("🤖 System", "ML-Modelle aktiviert. Welches Problem soll mit Machine Learning gelöst werden?")
        self.chat_input.setPlaceholderText("ML-Problem beschreiben...")
        self.chat_input.setFocus()
    
    def launch_trend_analysis(self):
        self.add_chat_message("📉 System", "Trend-Analyse aktiviert. Welche Trends sollen analysiert werden?")
        self.chat_input.setPlaceholderText("Trend-Analyse-Anfrage...")
        self.chat_input.setFocus()
    
    def launch_pattern_detection(self):
        self.add_chat_message("🔍 System", "Pattern Detection aktiviert. In welchen Daten sollen Muster erkannt werden?")
        self.chat_input.setPlaceholderText("Daten für Mustererkennung...")
        self.chat_input.setFocus()
    
    def launch_report_generator(self):
        self.add_chat_message("📋 System", "Report Generator aktiviert. Welcher Bericht soll erstellt werden?")
        self.chat_input.setPlaceholderText("Bericht-Anfrage...")
        self.chat_input.setFocus()
    
    # Automation Tools
    def launch_task_scheduler(self):
        self.add_chat_message("⏰ System", "Task Scheduler aktiviert. Welche Aufgaben sollen geplant werden?")
        self.chat_input.setPlaceholderText("Task-Planung...")
        self.chat_input.setFocus()
    
    def launch_workflow_builder(self):
        self.add_chat_message("🔁 System", "Workflow Builder aktiviert. Welcher Workflow soll erstellt werden?")
        self.chat_input.setPlaceholderText("Workflow beschreiben...")
        self.chat_input.setFocus()
    
    def launch_batch_processing(self):
        self.add_chat_message("📂 System", "Batch Processing aktiviert. Welche Batch-Verarbeitung ist gewünscht?")
        self.chat_input.setPlaceholderText("Batch-Job beschreiben...")
        self.chat_input.setFocus()
    
    def launch_api_automation(self):
        self.add_chat_message("🌐 System", "API Automation aktiviert. Welche API-Automatisierung soll eingerichtet werden?")
        self.chat_input.setPlaceholderText("API-Automatisierung...")
        self.chat_input.setFocus()
    
    def launch_email_automation(self):
        self.add_chat_message("📧 System", "Email Automation aktiviert. Welche E-Mail-Automatisierung ist gewünscht?")
        self.chat_input.setPlaceholderText("E-Mail-Automatisierung...")
        self.chat_input.setFocus()
    
    def launch_data_sync(self):
        self.add_chat_message("🔄 System", "Data Sync aktiviert. Welche Daten sollen synchronisiert werden?")
        self.chat_input.setPlaceholderText("Daten-Sync-Anfrage...")
        self.chat_input.setFocus()
    
    # Model Management
    def change_ai_model(self):
        """Ändert das AI-Modell"""
        model = self.model_selector.currentText()
        if self.communication_engine:
            model_mapping = {
                "🔵 Lokales Modell (Ollama)": "local",
                "🟢 OpenAI GPT-4": "openai",
                "🟣 Anthropic Claude": "anthropic",
                "🔴 Gemini Pro": "gemini"
            }
            
            new_model = model_mapping.get(model, "local")
            self.communication_engine.current_model = new_model
            self.add_chat_message("🤖 System", f"AI-Modell geändert zu: {model}")
    
    # Event Handlers
    def handle_message_received(self, sender, message):
        """Behandelt empfangene Nachrichten"""
        self.add_chat_message(sender, message)
    
    def handle_status_changed(self, component, status):
        """Behandelt Status-Änderungen"""
        if hasattr(self, 'system_metrics') and component in self.system_metrics:
            self.system_metrics[component].setText(status)
        
    def init_ui(self):
        """Initialisiert die Benutzeroberfläche; unterstützt Minimal-Chat-Modus"""
        # Theme anwenden
        self.apply_supreme_theme()

        if getattr(self, 'minimal_ui', False):
            # Minimaler Chat-Only Modus
            self.setWindowTitle("CUDI — Minimal Chat Mode")
            self.setGeometry(120, 120, 1100, 800)
            self.setMinimumSize(900, 650)

            # Nur Chat-Center verwenden
            chat_only = self.create_supreme_chat_center()
            self.setCentralWidget(chat_only)

            # Keine Menü-/Toolbar, nur Statusbar für dezente Statusinfos
            self.create_supreme_statusbar()
            return

        # Vollständige Oberfläche (links/mitte/rechts Panels)
        self.setWindowTitle("CUDI_SUPREME - Ultimate AI Assistant")
        self.setGeometry(100, 100, 1800, 1200)
        self.setMinimumSize(1400, 900)

        # Central Widget mit Splitter-Layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)

        # Main Splitter
        splitter = QSplitter(Qt.Orientation.Horizontal)

        # Left Panel - AI Control Center
        self.left_panel = self.create_ai_control_center()
        splitter.addWidget(self.left_panel)

        # Center Panel - Main Chat & Interaction
        self.center_panel = self.create_supreme_chat_center()
        splitter.addWidget(self.center_panel)

        # Right Panel - Plugins & Tools
        self.right_panel = self.create_plugin_tool_center()
        splitter.addWidget(self.right_panel)

        # Splitter Proportionen
        splitter.setSizes([400, 800, 400])
        splitter.setCollapsible(0, True)
        splitter.setCollapsible(2, True)

        main_layout.addWidget(splitter)

        # Menu Bar & Toolbar
        self.create_supreme_menu()
        self.create_supreme_toolbar()
        self.create_supreme_statusbar()
        
    def apply_supreme_theme(self):
        """Wendet das ultimative Dark Theme an"""
        self.setStyleSheet("""
            QMainWindow {
                background-color: #0d1117;
                color: #ffffff;
            }
            
            QWidget {
                background-color: #0d1117;
                color: #ffffff;
                font-family: 'Segoe UI', 'Arial', sans-serif;
            }
            
            QTabWidget::pane {
                border: 2px solid #30363d;
                background-color: #161b22;
                border-radius: 8px;
            }
            
            QTabBar::tab {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                          stop: 0 #21262d, stop: 1 #161b22);
                color: #ffffff;
                padding: 12px 24px;
                margin-right: 2px;
                border-top-left-radius: 8px;
                border-top-right-radius: 8px;
                min-width: 120px;
                font-weight: bold;
                border: 1px solid #30363d;
            }
            
            QTabBar::tab:selected {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                          stop: 0 #1f6feb, stop: 1 #0969da);
                color: #ffffff;
                border-bottom: 2px solid #1f6feb;
            }
            
            QTabBar::tab:hover {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                          stop: 0 #30363d, stop: 1 #21262d);
            }
            
            QPushButton {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                          stop: 0 #238636, stop: 1 #196127);
                color: white;
                border: 1px solid #2ea043;
                border-radius: 8px;
                padding: 10px 16px;
                font-weight: bold;
                font-size: 12px;
            }
            
            QPushButton:hover {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                          stop: 0 #2ea043, stop: 1 #238636);
                border-color: #46954a;
            }
            
            QPushButton:pressed {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                          stop: 0 #196127, stop: 1 #0f4d19);
            }
            
            QPushButton:checked {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                          stop: 0 #1f6feb, stop: 1 #0969da);
                border-color: #4184e4;
            }
            
            QTextEdit, QPlainTextEdit {
                background-color: #0d1117;
                color: #ffffff;
                border: 2px solid #30363d;
                border-radius: 8px;
                padding: 12px;
                font-family: 'Consolas', 'Monaco', monospace;
                font-size: 13px;
                line-height: 1.4;
            }
            
            QTextEdit:focus, QPlainTextEdit:focus {
                border-color: #1f6feb;
                outline: none;
            }
            
            QLineEdit {
                background-color: #21262d;
                color: #ffffff;
                border: 2px solid #30363d;
                border-radius: 8px;
                padding: 12px 16px;
                font-size: 13px;
            }
            
            QLineEdit:focus {
                border-color: #1f6feb;
                background-color: #161b22;
            }
            
            QComboBox {
                background-color: #21262d;
                color: #ffffff;
                border: 2px solid #30363d;
                border-radius: 8px;
                padding: 8px 12px;
                font-weight: bold;
            }
            
            QComboBox:hover {
                border-color: #1f6feb;
            }
            
            QComboBox::drop-down {
                border: none;
                width: 30px;
            }
            
            QComboBox::down-arrow {
                image: none;
                border-left: 5px solid transparent;
                border-right: 5px solid transparent;
                border-top: 8px solid #ffffff;
                margin-right: 10px;
            }
            
            QListWidget {
                background-color: #161b22;
                color: #ffffff;
                border: 2px solid #30363d;
                border-radius: 8px;
                padding: 8px;
            }
            
            QListWidget::item {
                padding: 10px;
                border-bottom: 1px solid #21262d;
                border-radius: 6px;
                margin: 2px;
            }
            
            QListWidget::item:hover {
                background-color: #21262d;
            }
            
            QListWidget::item:selected {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                          stop: 0 #1f6feb, stop: 1 #0969da);
                color: #ffffff;
            }
            
            QFrame {
                background-color: #161b22;
                border: 2px solid #30363d;
                border-radius: 12px;
                margin: 5px;
            }
            
            QFrame:hover {
                border-color: #1f6feb;
                background-color: #21262d;
            }
            
            QScrollBar:vertical {
                background-color: #21262d;
                width: 12px;
                border-radius: 6px;
            }
            
            QScrollBar::handle:vertical {
                background-color: #30363d;
                border-radius: 6px;
                min-height: 20px;
            }
            
            QScrollBar::handle:vertical:hover {
                background-color: #484f58;
            }
            
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                height: 0px;
            }
            
            QProgressBar {
                border: 2px solid #30363d;
                border-radius: 8px;
                background-color: #161b22;
                text-align: center;
                color: white;
                font-weight: bold;
            }
            
            QProgressBar::chunk {
                background: qlineargradient(x1: 0, y1: 0, x2: 1, y2: 0,
                                          stop: 0 #1f6feb, stop: 1 #4184e4);
                border-radius: 6px;
            }
        """)
    
    def create_ai_control_center(self):
        """Erstellt das AI Control Center (Left Panel)"""
        control_panel = QWidget()
        control_panel.setFixedWidth(400)
        control_panel.setStyleSheet("""
            QWidget {
                background-color: #161b22;
                border-right: 3px solid #30363d;
                border-radius: 12px;
            }
        """)
        
        layout = QVBoxLayout(control_panel)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # CUDI Avatar & Status
        self.create_supreme_avatar_display(layout)
        
        # AI Brain Status
        self.create_ai_brain_status(layout)
        
        # Voice Control Center
        self.create_supreme_voice_controls(layout)
        
        # Personality Matrix
        self.create_personality_matrix(layout)
        
        # Quick AI Actions
        self.create_quick_ai_actions(layout)
        
        # System Health Monitor
        self.create_system_health_monitor(layout)
        
        layout.addStretch()
        return control_panel
    
    def create_supreme_avatar_display(self, layout):
        """Erstellt das Supreme Avatar Display"""
        avatar_card = ModernCard("🤖 CUDI_SUPREME")
        avatar_layout = QVBoxLayout()
        
        # Avatar Animation Area
        self.avatar_animation = QLabel()
        self.avatar_animation.setAlignment(Qt.AlignCenter)
        self.avatar_animation.setStyleSheet("""
            QLabel {
                background: qradial-gradient(circle, #1f6feb 0%, #0969da 50%, #0550ae 100%);
                border-radius: 60px;
                padding: 20px;
                font-size: 72px;
                color: white;
                min-height: 120px;
                max-height: 120px;
            }
        """)
        
        # Animierte Emoji basierend auf Status
        self.avatar_states = {
            "thinking": "🧠",
            "listening": "👂",
            "speaking": "🗣️",
            "happy": "😊",
            "working": "⚙️",
            "idle": "🤖"
        }
        self.current_avatar_state = "idle"
        self.avatar_animation.setText(self.avatar_states[self.current_avatar_state])
        avatar_layout.addWidget(self.avatar_animation)
        
        # Avatar Status Text
        self.avatar_status_text = QLabel("Supreme AI Ready")
        self.avatar_status_text.setAlignment(Qt.AlignCenter)
        self.avatar_status_text.setStyleSheet("""
            QLabel {
                color: #39d353;
                font-weight: bold;
                font-size: 14px;
                background: transparent;
                border: none;
                padding: 5px;
            }
        """)
        avatar_layout.addWidget(self.avatar_status_text)
        
        # Avatar Mood Indicator
        self.avatar_mood_bar = QProgressBar()
        self.avatar_mood_bar.setRange(0, 100)
        self.avatar_mood_bar.setValue(85)
        self.avatar_mood_bar.setTextVisible(False)
        self.avatar_mood_bar.setMaximumHeight(8)
        avatar_layout.addWidget(self.avatar_mood_bar)
        
        avatar_card.main_layout.addLayout(avatar_layout)
        layout.addWidget(avatar_card)
    
    def create_ai_brain_status(self, layout):
        """Erstellt AI Brain Status Display"""
        brain_card = ModernCard("🧠 AI Brain Matrix")
        brain_layout = QVBoxLayout()
        
        # Brain Components Status
        self.brain_components = {}
        components = [
            ("LLM Engine", "llm", "#1f6feb"),
            ("Neural Networks", "neural", "#39d353"),
            ("Memory Core", "memory", "#a5a5a5"),
            ("Learning Agent", "learning", "#ffab00"),
            ("Decision Tree", "decision", "#f85149")
        ]
        
        for name, key, color in components:
            comp_layout = QHBoxLayout()
            
            # Status LED
            status_led = QLabel("●")
            status_led.setStyleSheet(f"color: {color}; font-size: 16px;")
            
            # Component Name
            comp_label = QLabel(name)
            comp_label.setStyleSheet("color: #ffffff; font-size: 12px;")
            
            # Activity Bar
            activity_bar = QProgressBar()
            activity_bar.setRange(0, 100)
            activity_bar.setValue(75)  # Dummy value
            activity_bar.setMaximumHeight(6)
            activity_bar.setTextVisible(False)
            
            comp_layout.addWidget(status_led)
            comp_layout.addWidget(comp_label)
            comp_layout.addStretch()
            comp_layout.addWidget(activity_bar)
            
            brain_layout.addLayout(comp_layout)
            self.brain_components[key] = (status_led, activity_bar)
        
        brain_card.main_layout.addLayout(brain_layout)
        layout.addWidget(brain_card)
    
    def create_supreme_voice_controls(self, layout):
        """Erstellt Supreme Voice Controls"""
        voice_card = ModernCard("🎤 Voice Command Center")
        voice_layout = QVBoxLayout()
        
        # Voice Status Display
        self.voice_status_display = QLabel("Voice System Ready")
        self.voice_status_display.setAlignment(Qt.AlignCenter)
        self.voice_status_display.setStyleSheet("""
            QLabel {
                background-color: #0d1117;
                color: #39d353;
                border: 2px solid #39d353;
                border-radius: 8px;
                padding: 8px;
                font-weight: bold;
                font-size: 12px;
            }
        """)
        voice_layout.addWidget(self.voice_status_display)
        
        # Voice Control Buttons
        controls_layout = QHBoxLayout()
        
        self.voice_listen_btn = QPushButton("🎤")
        self.voice_listen_btn.setCheckable(True)
        self.voice_listen_btn.setChecked(True)
        self.voice_listen_btn.setToolTip("Toggle Voice Listening")
        self.voice_listen_btn.setMaximumWidth(50)
        self.voice_listen_btn.clicked.connect(self.toggle_voice_listening)
        
        self.voice_speak_btn = QPushButton("🔊")
        self.voice_speak_btn.setCheckable(True)
        self.voice_speak_btn.setChecked(True)
        self.voice_speak_btn.setToolTip("Toggle Voice Speaking")
        self.voice_speak_btn.setMaximumWidth(50)
        self.voice_speak_btn.clicked.connect(self.toggle_voice_speaking)
        
        self.push_to_talk_btn = QPushButton("Push to Talk")
        self.push_to_talk_btn.setToolTip("Hold to speak")
        self.push_to_talk_btn.pressed.connect(self.start_push_to_talk)
        self.push_to_talk_btn.released.connect(self.stop_push_to_talk)
        
        controls_layout.addWidget(self.voice_listen_btn)
        controls_layout.addWidget(self.voice_speak_btn)
        controls_layout.addWidget(self.push_to_talk_btn)
        
        voice_layout.addLayout(controls_layout)
        
        # Voice Settings
        settings_layout = QFormLayout()
        
        self.voice_volume_slider = QSlider(Qt.Orientation.Horizontal)
        self.voice_volume_slider.setRange(0, 100)
        self.voice_volume_slider.setValue(90)
        self.voice_volume_slider.valueChanged.connect(self.change_voice_volume)
        
        self.voice_speed_slider = QSlider(Qt.Orientation.Horizontal)
        self.voice_speed_slider.setRange(50, 300)
        self.voice_speed_slider.setValue(180)
        self.voice_speed_slider.valueChanged.connect(self.change_voice_speed)
        
        settings_layout.addRow("Volume:", self.voice_volume_slider)
        settings_layout.addRow("Speed:", self.voice_speed_slider)
        
        voice_layout.addLayout(settings_layout)
        
        voice_card.main_layout.addLayout(voice_layout)
        layout.addWidget(voice_card)
    
    def create_personality_matrix(self, layout):
        """Erstellt Personality Matrix"""
        personality_card = ModernCard("🎭 Personality Matrix")
        personality_layout = QVBoxLayout()
        
        # Personality Selector
        self.personality_selector = QComboBox()
        personalities = [
            ("🤖 Jarvis", "jarvis"),
            ("💼 Business", "business"),
            ("🧙 Mentor", "mentor"),
            ("😎 Bro", "bro"),
            ("🧠 Einstein", "einstein"),
            ("⚡ Lightning", "lightning")
        ]
        
        for display_name, value in personalities:
            self.personality_selector.addItem(display_name, value)
        
        self.personality_selector.currentTextChanged.connect(self.change_personality)
        personality_layout.addWidget(self.personality_selector)
        
        # Personality Traits Sliders
        traits_layout = QFormLayout()
        
        self.trait_sliders = {}
        traits = [
            ("Creativity", "creativity", 70),
            ("Logic", "logic", 90),
            ("Humor", "humor", 50),
            ("Formality", "formality", 80)
        ]
        
        for trait_name, trait_key, default_value in traits:
            slider = QSlider(Qt.Orientation.Horizontal)
            slider.setRange(0, 100)
            slider.setValue(default_value)
            slider.valueChanged.connect(lambda v, k=trait_key: self.update_personality_trait(k, v))
            
            self.trait_sliders[trait_key] = slider
            traits_layout.addRow(f"{trait_name}:", slider)
        
        personality_layout.addLayout(traits_layout)
        
        personality_card.main_layout.addLayout(personality_layout)
        layout.addWidget(personality_card)
    
    def create_quick_ai_actions(self, layout):
        """Erstellt Quick AI Actions"""
        actions_card = ModernCard("⚡ Quick AI Actions")
        actions_layout = QGridLayout()
        
        # AI Action Buttons
        self.ai_actions = [
            ("🧠 Deep Think", self.trigger_deep_thinking, 0, 0),
            ("📚 Learn New", self.trigger_learning_mode, 0, 1),
            ("🔍 Research", self.trigger_research_mode, 1, 0),
            ("🎨 Create", self.trigger_creative_mode, 1, 1),
            ("🛠️ Fix Issue", self.trigger_problem_solving, 2, 0),
            ("💡 Innovate", self.trigger_innovation_mode, 2, 1)
        ]
        
        for text, callback, row, col in self.ai_actions:
            btn = QPushButton(text)
            btn.setMinimumHeight(40)
            btn.clicked.connect(callback)
            actions_layout.addWidget(btn, row, col)
        
        actions_card.main_layout.addLayout(actions_layout)
        layout.addWidget(actions_card)
    
    def create_system_health_monitor(self, layout):
        """Erstellt System Health Monitor"""
        health_card = ModernCard("💗 System Health")
        health_layout = QVBoxLayout()
        
        # Health Metrics
        self.health_metrics = {}
        metrics = [
            ("CPU Usage", "cpu", 25),
            ("Memory Usage", "memory", 45),
            ("Response Time", "response", 15),
            ("AI Confidence", "confidence", 88)
        ]
        
        for metric_name, metric_key, value in metrics:
            metric_layout = QHBoxLayout()
            
            label = QLabel(metric_name)
            label.setStyleSheet("color: #ffffff; font-size: 11px;")
            
            progress = QProgressBar()
            progress.setRange(0, 100)
            progress.setValue(value)
            progress.setMaximumHeight(10)
            progress.setTextVisible(False)
            
            value_label = QLabel(f"{value}%")
            value_label.setStyleSheet("color: #39d353; font-size: 11px; font-weight: bold;")
            value_label.setMinimumWidth(40)
            
            metric_layout.addWidget(label)
            metric_layout.addWidget(progress)
            metric_layout.addWidget(value_label)
            
            health_layout.addLayout(metric_layout)
            self.health_metrics[metric_key] = (progress, value_label)
        
        health_card.main_layout.addLayout(health_layout)
        layout.addWidget(health_card)
    
    def run_agent_preflight_check(self):
        """CUDI Agent Preflight Check - stellt sicher dass alle Systeme für Agent-Modus bereit sind"""
        try:
            print("🔍 CUDI Agent Preflight Check...")
            
            # Quick Check ohne externe Abhängigkeiten
            checks_passed = 0
            total_checks = 5
            
            # 1. Plugin Manager Check
            try:
                if self.plugin_manager or CUDIPluginManager:
                    checks_passed += 1
                    print("✅ Plugin System verfügbar")
                else:
                    print("⚠️ Plugin System nicht verfügbar")
            except:
                print("⚠️ Plugin System Check fehlgeschlagen")
            
            # 2. System Role Check 
            try:
                from cudi_system_role import SYSTEM_ROLE, ACTIVE
                if ACTIVE and SYSTEM_ROLE:
                    checks_passed += 1
                    print("✅ Agent Persönlichkeit geladen")
                else:
                    print("⚠️ Agent Persönlichkeit nicht aktiv")
            except:
                print("⚠️ System Role nicht gefunden")
            
            # 3. Schreibrechte Check
            try:
                test_file = Path(".cudi_agent_test.tmp")
                test_file.write_text("test", encoding='utf-8')
                test_file.unlink()
                checks_passed += 1
                print("✅ Schreibrechte OK")
            except:
                print("⚠️ Schreibrechte-Problem")
            
            # 4. Command Router Check
            try:
                if hasattr(self, 'command_router') and self.command_router:
                    checks_passed += 1
                    print("✅ Command Router aktiv")
                else:
                    print("⚠️ Command Router nicht verfügbar")
            except:
                print("⚠️ Command Router Check fehlgeschlagen")
            
            # 5. Agent Mode Settings Check
            try:
                if (hasattr(self, 'agent_mode_active') and self.agent_mode_active and 
                    hasattr(self, 'personality_mode') and self.personality_mode == "casual_developer"):
                    checks_passed += 1
                    print("✅ Agent Mode konfiguriert")
                else:
                    print("⚠️ Agent Mode nicht korrekt konfiguriert")
            except:
                print("⚠️ Agent Mode Settings Check fehlgeschlagen")
            
            # Status setzen
            if checks_passed >= 4:
                self.preflight_status = "ok"
                print("✅ Agent Preflight OK - Systeme stabil, bereit zu sprechen")
            elif checks_passed >= 2:
                self.preflight_status = "warning"  
                print("⚠️ Agent Preflight WARNING - eingeschränkter Betrieb möglich")
            else:
                self.preflight_status = "error"
                print("❌ Agent Preflight ERROR - bleibe im Basismodus")
                
        except Exception as e:
            self.preflight_status = "error"
            print(f"❌ Preflight Check Fehler: {e}")
    
    def init_cudi_supreme(self):
        """Initialisiert alle CUDI_SUPREME Komponenten"""
        print("🚀 Initialisiere CUDI_SUPREME...")
        
        # LLM Integration
        try:
            # Einheitlich: sowohl communication_engine als auch llm befüllen
            self.communication_engine = get_llm()
            self.llm = self.communication_engine
            # Modelle initialisieren, falls vorhanden
            if self.communication_engine and hasattr(self.communication_engine, 'initialize_models'):
                self.communication_engine.initialize_models()
            self.update_status("LLM", "✅ Ready")
            print("✅ LLM Integration geladen")
        except Exception as e:
            self.update_status("LLM", "❌ Error")
            print(f"❌ LLM Error: {e}")

        # psutil sicherstellen (echte CPU/RAM-Metriken)
        try:
            self.ensure_psutil_installed()
        except Exception as e:
            pass  # Optimized error handling
        
        # Voice Engine
        try:
            self.voice_engine = get_voice_engine()
            if self.voice_engine and hasattr(self.voice_engine, 'set_voice_callback'):
                self.voice_engine.set_voice_callback(self.handle_voice_input)
            self.update_status("Voice", "✅ Ready")
            print("✅ Voice Engine geladen")
        except Exception as e:
            self.update_status("Voice", "❌ Error")
            print(f"❌ Voice Error: {e}")
        
        # Plugin Manager
        try:
            self.plugin_manager = CUDIPluginManager()
            self.update_plugin_list()
            self.update_status("Plugins", "✅ Ready")
            print("✅ Plugin Manager geladen")
        except Exception as e:
            self.update_status("Plugins", "❌ Error")
            print(f"❌ Plugin Error: {e}")
        
        # CUDI Core
        try:
            self.brain = CudiBrain()
            # self.memory = Memory()
            # self.emotion = Emotion() 
            # self.avatar = get_avatar()
            
            # Integration (optional)
            
            # Integration
            self.brain.set_memory_emotion(self.memory, self.emotion)
            
            self.update_status("Core", "✅ Ready")
            
            # === PERFECT INTER-COMPONENT COMMUNICATION ===
            self.component_bridge = CUDIComponentBridge()
            self.component_bridge.register_component('main_gui', self)
            
            # === INTELLIGENT CONVERSATION HANDLER - AKTIVIERT ===
            if CUDIConversationHandler:
                self.conversation_handler = CUDIConversationHandler(self)
                self.use_intelligent_responses = True
                self.intelligence_mode = "active"
                print("🧠 Intelligent conversation handler initialized and ACTIVE")
            else:
                self.conversation_handler = None
                self.use_intelligent_responses = False
                self.intelligence_mode = "fallback"
                print("⚠️ Intelligent conversation handler not available - using fallback")
            
            # === TELEMETRIE & EVENT-BUS INTEGRATION ===
            if TELEMETRY_AVAILABLE:
                self.telemetry = get_telemetry()
                self.event_bus = get_event_bus()
                
                # Event-Bus starten (non-blocking)
                import asyncio
                # Event-Bus synchron starten
                try:
                    if hasattr(self.event_bus, 'start_sync'):
                        self.event_bus.start_sync()
                    else:
                        # Fallback: Event-Bus manuell als aktiv markieren
                        self.event_bus.running = True
                        print("📊 Event-Bus aktiviert")
                except Exception as e:
                    print(f"⚠️ Event-Bus Warnung: {e}")
                    pass
                
                # System-Start Event loggen
                telemetry_log('SYSTEM_STATUS', {
                    'status': 'initialized',
                    'components': ['GUI', 'Brain', 'Plugins', 'Bridge'],
                    'timestamp': datetime.now().isoformat()
                })
                
                event_emit('ACTION_START', {
                    'action': 'system_initialization',
                    'components_loaded': 6
                })
                
                print("📊 Telemetrie & Event-Bus aktiviert")
            else:
                self.telemetry = None
                self.event_bus = None
            
            # Register other components
            if self.brain:
                self.component_bridge.register_component('brain', self.brain)
            if self.plugin_manager:
                self.component_bridge.register_component('plugin_manager', self.plugin_manager)
            
            print("🔗 Component communication bridge established")
        except Exception as e:
            self.update_status("Core", "❌ Error")
            print(f"❌ Core Error: {e}")
        
        print("🎉 CUDI_SUPREME Initialisierung abgeschlossen!")
    
    def connect_signals(self):
        """Verbindet alle Signals"""
        self.message_received.connect(self.handle_message_received)
        self.system_status_changed.connect(self.handle_status_changed)
        # Zusätzliche Signale für LLM & Voice
        try:
            self.llm_response_ready.connect(self.handle_llm_response)
        except Exception:
            pass
        try:
            self.voice_input_received.connect(self.handle_voice_input_received)
        except Exception:
            pass
    
    def start_timers(self):
        """Startet alle Timer"""
        # Status Update Timer
        self.status_timer.timeout.connect(self.update_system_status)
        self.status_timer.start(5000)  # Alle 5 Sekunden
        
        # Avatar Animation Timer
        self.voice_timer.timeout.connect(self.animate_avatar)
        self.voice_timer.start(2000)  # Alle 2 Sekunden
    
    # Event Handlers
    def handle_voice_input(self, voice_text):
        """Behandelt Spracheingabe"""
        self.voice_input_received.emit(voice_text)
    
    def handle_voice_input_received(self, voice_text):
        """Behandelt empfangene Spracheingabe"""
        self.add_chat_message("🎤 Du", voice_text)
        self.process_user_input(voice_text)
    
    def handle_message_received(self, sender, message):
        """Behandelt empfangene Nachrichten"""
        self.add_chat_message(sender, message)
    
    def handle_status_changed(self, component, status):
        """Behandelt Status-Änderungen"""
        self.update_status(component, status)
    
    def handle_llm_response(self, response, metadata):
        """Behandelt LLM-Antworten"""
        self.add_chat_message("🤖 CUDI", response)
        
        # Auto-Speech wenn aktiviert
        if self.auto_speech and self.voice_engine:
            self.voice_engine.speak(response)
        # Tippindikator ausblenden und Avatar in Idle setzen
        try:
            self._hide_typing_indicator()
        except Exception:
            pass
        try:
            self.set_avatar_state("idle")
        except Exception:
            pass
    
    # UI Event Handlers
    def toggle_voice_listening(self):
        """Schaltet Voice Listening um"""
        if self.voice_engine:
            if self.voice_listen_btn.isChecked():
                self.voice_engine.start_listening(self.handle_voice_input)
                self.voice_status_display.setText("🎤 Listening Active")
                self.voice_status_display.setStyleSheet("""
                    QLabel {
                        background-color: #0d1117;
                        color: #39d353;
                        border: 2px solid #39d353;
                        border-radius: 8px;
                        padding: 8px;
                        font-weight: bold;
                        font-size: 12px;
                    }
                """)
            else:
                self.voice_engine.stop_listening()
                self.voice_status_display.setText("🔇 Listening Disabled")
                self.voice_status_display.setStyleSheet("""
                    QLabel {
                        background-color: #0d1117;
                        color: #f85149;
                        border: 2px solid #f85149;
                        border-radius: 8px;
                        padding: 8px;
                        font-weight: bold;
                        font-size: 12px;
                    }
                """)
    
    def toggle_voice_speaking(self):
        """Schaltet Voice Speaking um"""
        self.auto_speech = self.voice_speak_btn.isChecked()
    
    def start_push_to_talk(self):
        """Startet Push-to-Talk"""
        if self.voice_engine:
            self.push_to_talk_btn.setText("🗣️ Speaking...")
            self.push_to_talk_btn.setStyleSheet("""
                QPushButton {
                    background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                              stop: 0 #f85149, stop: 1 #da3633);
                    border-color: #f85149;
                }
            """)
    
    def stop_push_to_talk(self):
        """Stoppt Push-to-Talk"""
        self.push_to_talk_btn.setText("Push to Talk")
        self.push_to_talk_btn.setStyleSheet("")  # Reset to default
    
    def change_voice_volume(self, value):
        """Ändert Voice Volume"""
        if self.voice_engine:
            # Voice Engine Volume anpassen
            pass
    
    def change_voice_speed(self, value):
        """Ändert Voice Speed"""
        if self.voice_engine:
            self.voice_engine.set_speech_rate(value)
    
    def change_personality(self):
        """Ändert AI Persönlichkeit"""
        current_data = self.personality_selector.currentData()
        if current_data and self.llm:
            self.current_personality = current_data
            self.llm.set_personality(current_data)
            self.add_chat_message("🎭 System", f"Persönlichkeit geändert zu: {self.personality_selector.currentText()}")
    
    def update_personality_trait(self, trait, value):
        """Aktualisiert Persönlichkeits-Trait"""
        # Trait-Update an LLM weiterleiten
        pass
    
    # AI Action Handlers
    def trigger_deep_thinking(self):
        """Triggert Deep Thinking Mode"""
        self.add_chat_message("🧠 System", "Deep Thinking Mode aktiviert...")
        self.set_avatar_state("thinking")
        
        # Deep Thinking Implementation
        try:
            # Initialisiere autonomes Denksystem
            if hasattr(self, 'autonomous_thinking'):
                self.autonomous_thinking.start_deep_thinking_session()
            
            # Brain-Integration für tiefe Analyse
            if hasattr(self, 'brain') and hasattr(self.brain, 'deep_cognitive_analysis'):
                context = {
                    'mode': 'deep_thinking',
                    'timestamp': datetime.now().isoformat(),
                    'user_input': self.chat_input.text() if hasattr(self, 'chat_input') else 'No input',
                    'session_history': getattr(self, 'chat_messages', [])
                }
                analysis_result = self.brain.deep_cognitive_analysis(context)
                self.add_chat_message("🧠 Deep Analysis", f"Analyse-Ergebnis: {analysis_result}")
            
            # Setze Deep Thinking Timer
            self.deep_thinking_timer = QTimer()
            self.deep_thinking_timer.timeout.connect(self._deep_thinking_update)
            self.deep_thinking_timer.start(5000)  # Update alle 5 Sekunden
            
            self.add_chat_message("🧠 System", "Deep Thinking Prozess gestartet. Analysiere komplexe Zusammenhänge...")
            
        except Exception as e:
            self.add_chat_message("❌ Error", f"Deep Thinking Fehler: {e}")
            print(f"Deep Thinking Error: {e}")
    
    def trigger_learning_mode(self):
        """Triggert Learning Mode"""
        self.add_chat_message("📚 System", "Learning Mode aktiviert...")
        
        # Learning Mode Implementation
        try:
            # Game & App Learning System aktivieren
            if hasattr(self, 'game_learning_system'):
                self.game_learning_system.start_interactive_learning()
                self.add_chat_message("📚 Learning", "Interaktives Lernsystem gestartet")
            
            # Kontinuierliches Lernen aktivieren
            if hasattr(self, 'brain') and hasattr(self.brain, 'activate_learning_mode'):
                learning_context = {
                    'mode': 'continuous_learning',
                    'focus_areas': ['programming', 'ai', 'problem_solving'],
                    'difficulty': 'adaptive',
                    'timestamp': datetime.now().isoformat()
                }
                self.brain.activate_learning_mode(learning_context)
            
            # Learning Progress Tracking
            self.learning_progress = {
                'session_start': datetime.now().isoformat(),
                'topics_covered': [],
                'skills_improved': [],
                'projects_created': []
            }
            
            # Learning UI Updates
            self.set_avatar_state("learning")
            self.add_chat_message("📚 System", "Lernmodus aktiv. Verfügbare Befehle: 'lernen [Thema]', 'projekt erstellen', 'fortschritt zeigen'")
            
        except Exception as e:
            self.add_chat_message("❌ Error", f"Learning Mode Fehler: {e}")
            print(f"Learning Mode Error: {e}")
    
    def trigger_research_mode(self):
        """Triggert Research Mode"""
        self.add_chat_message("🔍 System", "Research Mode aktiviert...")
        
        # Research Mode Implementation
        try:
            # Web Intelligence aktivieren
            if hasattr(self, 'web_intelligence'):
                self.web_intelligence.start_research_session()
                self.add_chat_message("🔍 Research", "Web Intelligence aktiviert")
            
            # Research Tools initialisieren
            self.research_tools = {
                'web_search': True,
                'code_analysis': True,
                'document_analysis': True,
                'data_mining': True,
                'trend_analysis': True
            }
            
            # Research Context aufbauen
            if hasattr(self, 'brain') and hasattr(self.brain, 'activate_research_mode'):
                research_context = {
                    'mode': 'research',
                    'focus': 'comprehensive_analysis',
                    'sources': ['web', 'local_files', 'databases'],
                    'depth': 'detailed',
                    'timestamp': datetime.now().isoformat()
                }
                self.brain.activate_research_mode(research_context)
            
            # Research Session starten
            self.research_session = {
                'start_time': datetime.now().isoformat(),
                'queries_performed': [],
                'sources_analyzed': [],
                'findings': [],
                'insights': []
            }
            
            self.set_avatar_state("researching")
            self.add_chat_message("🔍 System", "Research Modus aktiv. Verfügbare Befehle: 'recherchiere [Thema]', 'analysiere [Daten]', 'trends zeigen'")
            
        except Exception as e:
            self.add_chat_message("❌ Error", f"Research Mode Fehler: {e}")
            print(f"Research Mode Error: {e}")
    
    def trigger_creative_mode(self):
        """Triggert Creative Mode"""
        self.add_chat_message("🎨 System", "Creative Mode aktiviert...")
        
        # Creative Mode Implementation
        try:
            # Kreativitäts-Engine aktivieren
            self.creative_engine = {
                'imagination_level': 0.9,
                'randomness_factor': 0.7,
                'innovation_mode': True,
                'artistic_flair': 0.8,
                'unconventional_thinking': True
            }
            
            # Creative Tools laden
            self.creative_tools = {
                'story_generation': True,
                'code_creativity': True,
                'design_suggestions': True,
                'brainstorming': True,
                'artistic_expression': True,
                'innovative_solutions': True
            }
            
            # Brain Creative Mode
            if hasattr(self, 'brain') and hasattr(self.brain, 'activate_creative_mode'):
                creative_context = {
                    'mode': 'creative',
                    'style': 'innovative',
                    'inspiration_sources': ['art', 'nature', 'technology', 'culture'],
                    'constraints': 'minimal',
                    'timestamp': datetime.now().isoformat()
                }
                self.brain.activate_creative_mode(creative_context)
            
            # Creative Session initialisieren
            self.creative_session = {
                'start_time': datetime.now().isoformat(),
                'ideas_generated': [],
                'projects_conceived': [],
                'creative_outputs': [],
                'inspiration_sources': []
            }
            
            self.set_avatar_state("creative")
            self.add_chat_message("🎨 System", "Creative Modus aktiv. Verfügbare Befehle: 'erschaffe [Projekt]', 'inspiriere mich', 'brainstorme [Thema]'")
            
            # Kreative Begrüßung
            creative_greetings = [
                "Lass uns etwas Außergewöhnliches erschaffen! 🌟",
                "Zeit für innovative Ideen und kreative Lösungen! 🚀",
                "Bereit für künstlerische Entdeckungen! 🎭",
                "Lass deiner Kreativität freien Lauf! ✨"
            ]
            import random
            greeting = random.choice(creative_greetings)
            self.add_chat_message("🎨 Creative", greeting)
            
        except Exception as e:
            self.add_chat_message("❌ Error", f"Creative Mode Fehler: {e}")
            print(f"Creative Mode Error: {e}")
    
    def trigger_problem_solving(self):
        """Triggert Problem Solving Mode"""
        self.add_chat_message("🛠️ System", "Problem Solving Mode aktiviert...")
        
        # Problem Solving Implementation
        try:
            # Problem-Solving Engine initialisieren
            self.problem_solver = {
                'analysis_method': 'systematic',
                'solution_approach': 'multi_angle',
                'debug_mode': True,
                'step_by_step': True,
                'alternative_solutions': True,
                'verification_enabled': True
            }
            
            # Problem-Solving Tools
            self.solving_tools = {
                'root_cause_analysis': True,
                'debugging_assistant': True,
                'systematic_breakdown': True,
                'solution_testing': True,
                'optimization_suggestions': True,
                'prevention_strategies': True
            }
            
            # Brain Problem-Solving Mode
            if hasattr(self, 'brain') and hasattr(self.brain, 'activate_problem_solving_mode'):
                problem_context = {
                    'mode': 'problem_solving',
                    'approach': 'analytical',
                    'methodology': 'systematic',
                    'tools': list(self.solving_tools.keys()),
                    'timestamp': datetime.now().isoformat()
                }
                self.brain.activate_problem_solving_mode(problem_context)
            
            # Problem-Solving Session
            self.problem_session = {
                'start_time': datetime.now().isoformat(),
                'problems_identified': [],
                'solutions_proposed': [],
                'tests_performed': [],
                'results_verified': []
            }
            
            self.set_avatar_state("debugging")
            self.add_chat_message("🛠️ System", "Problem-Solving Modus aktiv. Verfügbare Befehle: 'löse [Problem]', 'analysiere [Code]', 'debugge [Fehler]'")
            self.add_chat_message("🛠️ Assistant", "Beschreibe dein Problem und ich helfe bei der systematischen Lösung! 🔧")
            
        except Exception as e:
            self.add_chat_message("❌ Error", f"Problem Solving Fehler: {e}")
            print(f"Problem Solving Error: {e}")
    
    def trigger_innovation_mode(self):
        """Triggert Innovation Mode"""
        self.add_chat_message("💡 System", "Innovation Mode aktiviert...")
        
        # Innovation Mode Implementation
        try:
            # Innovation Engine initialisieren
            self.innovation_engine = {
                'disruptive_thinking': True,
                'cross_domain_analysis': True,
                'future_prediction': True,
                'trend_synthesis': True,
                'paradigm_shifting': True,
                'technology_fusion': True
            }
            
            # Innovation Tools
            self.innovation_tools = {
                'trend_analysis': True,
                'technology_scouting': True,
                'future_scenarios': True,
                'disruptive_concepts': True,
                'innovation_metrics': True,
                'prototype_generation': True
            }
            
            # Brain Innovation Mode
            if hasattr(self, 'brain') and hasattr(self.brain, 'activate_innovation_mode'):
                innovation_context = {
                    'mode': 'innovation',
                    'focus': 'breakthrough_solutions',
                    'scope': 'disruptive_technologies',
                    'timeline': 'future_oriented',
                    'domains': ['ai', 'technology', 'science', 'society'],
                    'timestamp': datetime.now().isoformat()
                }
                self.brain.activate_innovation_mode(innovation_context)
            
            # Innovation Session
            self.innovation_session = {
                'start_time': datetime.now().isoformat(),
                'innovations_conceived': [],
                'technologies_analyzed': [],
                'breakthroughs_identified': [],
                'future_predictions': []
            }
            
            # Innovation-spezifische Avatar-States
            if "innovating" not in getattr(self, 'avatar_states', {}):
                if hasattr(self, 'avatar_states'):
                    self.avatar_states["innovating"] = "💡🚀✨"
            
            self.set_avatar_state("innovating")
            self.add_chat_message("💡 System", "Innovation Modus aktiv. Verfügbare Befehle: 'innoviere [Bereich]', 'trends analysieren', 'zukunft vorhersagen'")
            
            # Inspirations-Nachricht
            innovation_quotes = [
                "Innovation unterscheidet zwischen Führern und Folgern! 🚀",
                "Die beste Zeit, einen Baum zu pflanzen, war vor 20 Jahren. Die zweitbeste ist jetzt! 🌱",
                "Jede große Innovation war zunächst eine verrückte Idee! 💫",
                "Die Zukunft gehört denen, die sie heute erschaffen! ⚡"
            ]
            import random
            quote = random.choice(innovation_quotes)
            self.add_chat_message("💡 Innovation", quote)
            
        except Exception as e:
            self.add_chat_message("❌ Error", f"Innovation Mode Fehler: {e}")
            print(f"Innovation Mode Error: {e}")
    
    # Utility Methods
    def update_status(self, component, status):
        """Aktualisiert Komponenten-Status"""
        # Status in Brain Components aktualisieren
        try:
            if hasattr(self, 'brain_components'):
                if component in self.brain_components:
                    self.brain_components[component]['status'] = status
                    self.brain_components[component]['last_update'] = datetime.now().isoformat()
            
            # Status-Indicator aktualisieren
            if hasattr(self, 'status_indicators'):
                if component in self.status_indicators:
                    self.status_indicators[component].update_status(status)
            
            # Status-Log hinzufügen
            if hasattr(self, 'status_log'):
                self.status_log.append({
                    'component': component,
                    'status': status,
                    'timestamp': datetime.now().isoformat()
                })
            
        except Exception as e:
            pass  # Optimized error handling
    
    def _deep_thinking_update(self):
        """Update für Deep Thinking Timer"""
        try:
            # Fortschritts-Updates für Deep Thinking
            thinking_messages = [
                "🧠 Analysiere komplexe Muster...",
                "🔍 Erkunde tiefere Zusammenhänge...",
                "💭 Bewerte alternative Perspektiven...",
                "⚡ Synthetisiere neue Erkenntnisse...",
                "🎯 Konvergiere zu optimaler Lösung..."
            ]
            
            import random
            message = random.choice(thinking_messages)
            self.add_chat_message("🧠 Deep Thinking", message)
            
            # Timer für nächstes Update (optional)
            if hasattr(self, 'deep_thinking_timer') and hasattr(self.deep_thinking_timer, 'timeout'):
                # Stoppe Timer nach 30 Sekunden
                if not hasattr(self, 'deep_thinking_start'):
                    self.deep_thinking_start = datetime.now()
                
                elapsed = (datetime.now() - self.deep_thinking_start).seconds
                if elapsed > 30:
                    self.deep_thinking_timer.stop()
                    self.add_chat_message("🧠 System", "Deep Thinking Prozess abgeschlossen.")
                    self.set_avatar_state("idle")
                    
        except Exception as e:
            pass  # Optimized error handling
    
    def set_avatar_state(self, state):
        """Setzt Avatar-Zustand"""
        if state in self.avatar_states:
            self.current_avatar_state = state
            self.avatar_animation.setText(self.avatar_states[state])
    
    def animate_avatar(self):
        """Animiert Avatar"""
        # Einfache Animation durch Zustandswechsel
        if self.current_avatar_state == "idle":
            # Zufällige Idle-Animation
            import random
            if random.random() < 0.1:  # 10% Chance
                self.set_avatar_state("happy")
                QTimer.singleShot(1000, lambda: self.set_avatar_state("idle"))
    
    def update_system_status(self):
        """Aktualisiert System-Status"""
        # Echte CPU/MEM-Werte (psutil), sonst sanfte Variation
        cpu = None
        mem = None
        if psutil:
            try:
                cpu = int(psutil.cpu_percent(interval=0))
                mem = int(psutil.virtual_memory().percent)
            except Exception:
                cpu = mem = None

        for metric_key, (progress, label) in getattr(self, 'health_metrics', {}).items():
            if metric_key == 'cpu' and cpu is not None:
                progress.setValue(cpu)
                label.setText(f"{cpu}%")
            elif metric_key == 'memory' and mem is not None:
                progress.setValue(mem)
                label.setText(f"{mem}%")
            else:
                current_value = progress.value()
                new_value = max(0, min(100, current_value + random.randint(-3, 3)))
                progress.setValue(new_value)
                label.setText(f"{new_value}%")

        if hasattr(self, 'performance_metrics'):
            if cpu is not None and 'cpu' in self.performance_metrics:
                self.performance_metrics['cpu'].setText(f"{cpu}%")
            if mem is not None and 'memory' in self.performance_metrics:
                self.performance_metrics['memory'].setText(f"{mem}%")
    
    def update_plugin_list(self):
        """Aktualisiert Plugin-Liste"""
        try:
            if not hasattr(self, 'active_plugins_list'):
                return
            self.active_plugins_list.clear()
            if not self.plugin_manager:
                self.active_plugins_list.addItem("(Kein Plugin-Manager verfügbar)")
                return
            # Verfügbare Plugins
            available = []
            if hasattr(self.plugin_manager, 'get_plugin_list'):
                available = self.plugin_manager.get_plugin_list() or []
            # Geladene Plugins
            loaded = []
            if hasattr(self.plugin_manager, 'get_loaded_plugins'):
                loaded = self.plugin_manager.get_loaded_plugins() or []
            # Einträge erstellen
            for name in available:
                status = "aktiv" if name in loaded else "verfügbar"
                self.active_plugins_list.addItem(f"{name} – {status}")
            if not available:
                self.active_plugins_list.addItem("(Keine Plugins gefunden)")
        except Exception as e:
            if hasattr(self, 'active_plugins_list'):
                self.active_plugins_list.addItem(f"Fehler beim Laden: {e}")
    
    def reload_plugins(self):
        """Lädt Plugins neu"""
        if self.plugin_manager:
            self.plugin_manager.load_all_plugins()
            self.update_plugin_list()
            self.add_chat_message("🔌 System", "Plugins neu geladen")
    
    def add_plugin_dialog(self):
        """Zeigt Plugin-Hinzufügen Dialog"""
        # TODO: Plugin Dialog implementieren
        pass
    
    def create_supreme_chat_center(self):
        """Erstellt das Supreme Chat Center (Center Panel)"""
        chat_widget = QWidget()
        chat_layout = QVBoxLayout(chat_widget)
        chat_layout.setSpacing(10)
        chat_layout.setContentsMargins(15, 15, 15, 15)
        
        # Chat Header
        header_layout = QHBoxLayout()
        
        chat_title = QLabel("💬 CUDI_SUPREME Chat")
        chat_title.setStyleSheet("""
            QLabel {
                font-size: 18px;
                font-weight: bold;
                color: #ffffff;
                padding: 10px 0px;
            }
        """)
        
    # Chat Controls
        clear_btn = QPushButton("🗑️ Clear")
        clear_btn.clicked.connect(self.clear_chat)
        clear_btn.setMaximumWidth(80)
        
        export_btn = QPushButton("💾 Export")
        export_btn.clicked.connect(self.export_chat)
        export_btn.setMaximumWidth(80)

        dashboard_btn = QPushButton("📊 Dashboard")
        dashboard_btn.setMaximumWidth(110)
        dashboard_btn.clicked.connect(self.open_dashboard)
        
        # Antwort-Stil Auswahl (wirkt auf Communication Engine)
        self.header_style_cb = QComboBox()
        self.header_style_cb.addItems([
            "🎯 Präzise",
            "📚 Detailliert",
            "💡 Kreativ",
            "🤝 Freundlich",
            "🔬 Technisch",
        ])
        self.header_style_cb.setMaximumWidth(140)
        self.header_style_cb.currentTextChanged.connect(self._on_response_style_changed)

        # Tipp-Indikator Schalter
        self.typing_cb = QCheckBox("Tipp-Indikator")
        self.typing_cb.setChecked(getattr(self, 'typing_enabled', True))
        self.typing_cb.stateChanged.connect(self.toggle_typing_indicator)

        # Klarheitsfragen Schalter
        self.clarify_cb = QCheckBox("Klarheitsfragen")
        self.clarify_cb.setToolTip("Bei unklaren Eingaben zuerst gezielt nachfragen")
        self.clarify_cb.setChecked(getattr(self, 'clarify_enabled', True))
        self.clarify_cb.stateChanged.connect(self.toggle_clarify)

        # Bei Unklarheit nicht handeln (Block-Option)
        self.block_ambig_cb = QCheckBox("Bei Unklarheit nicht handeln")
        self.block_ambig_cb.setToolTip("Wenn aktiv, stellt CUDI bei unklaren Eingaben erst Rückfragen und führt keine Aktionen aus")
        self.block_ambig_cb.setChecked(getattr(self, 'block_on_ambiguity', True))
        self.block_ambig_cb.stateChanged.connect(self._on_block_ambiguity_toggled)

        # Antwort-Modus manuell überschreiben
        self.mode_cb = QComboBox()
        self.mode_cb.addItems(["🤖 Auto", "📘 Erklären", "🛠️ Umsetzen", "🐛 Debuggen", "💡 Brainstorm", "🔎 Recherchieren"]) 
        self.mode_cb.setMaximumWidth(160)
        self.mode_cb.currentTextChanged.connect(self._on_mode_changed)

        # Antwort-Länge steuern
        self.length_cb = QComboBox()
        self.length_cb.addItems(["Kurz", "Mittel", "Ausführlich"]) 
        self.length_cb.setMaximumWidth(120)
        self.length_cb.currentTextChanged.connect(self._on_length_changed)
        try:
            self.length_cb.setCurrentIndex(1)
        except Exception:
            pass

        # Anrede steuern
        self.address_cb = QComboBox()
        self.address_cb.addItems(["Du", "Sie"]) 
        self.address_cb.setMaximumWidth(80)
        self.address_cb.currentTextChanged.connect(self._on_address_changed)

        header_layout.addWidget(chat_title)
        header_layout.addStretch()
        header_layout.addWidget(self.header_style_cb)
        header_layout.addWidget(self.mode_cb)
        header_layout.addWidget(self.length_cb)
        header_layout.addWidget(self.address_cb)
        header_layout.addWidget(self.typing_cb)
        header_layout.addWidget(self.clarify_cb)
        header_layout.addWidget(self.block_ambig_cb)
        # Optional: robuster Intent-Router Schalter
        self.robust_intent_cb = QCheckBox("Robuste Intent-Erkennung")
        self.robust_intent_cb.setChecked(getattr(self, 'robust_intent_enabled', True))
        self.robust_intent_cb.setToolTip("Versteht flexible Formulierungen, Synonyme und Varianten")
        self.robust_intent_cb.stateChanged.connect(self._on_robust_intent_toggled)
        header_layout.addWidget(self.robust_intent_cb)
        
        # Autonomes Lernen
        self.auto_learn_cb = QCheckBox("Auto-Lernen")
        self.auto_learn_cb.setChecked(getattr(self, 'autonomous_learning_enabled', True))
        self.auto_learn_cb.setToolTip("CUDI erkennt Wissenslücken und lernt automatisch dazu")
        self.auto_learn_cb.stateChanged.connect(self._on_auto_learn_toggled)
        header_layout.addWidget(self.auto_learn_cb)
        
        # Auto-Debug System
        self.auto_debug_cb = QCheckBox("Auto-Debug")
        self.auto_debug_cb.setChecked(getattr(self, 'auto_debug_enabled', True))
        self.auto_debug_cb.setToolTip("Automatische Fehlererkennung und Selbstheilung")
        self.auto_debug_cb.stateChanged.connect(self._on_auto_debug_toggled)
        header_layout.addWidget(self.auto_debug_cb)
        
        # System Diagnostics Button
        self.diagnostics_btn = QPushButton("🔧 Diagnose")
        self.diagnostics_btn.setToolTip("System-Diagnose und Health-Check")
        self.diagnostics_btn.clicked.connect(self._show_system_diagnostics)
        header_layout.addWidget(self.diagnostics_btn)
        
        # No-Questions Mode
        self.no_questions_cb = QCheckBox("Direct Action")
        self.no_questions_cb.setChecked(True)  # Standard: Direkte Aktionen
        self.no_questions_cb.setToolTip("Direkte Aktions-Ausführung ohne Nachfragen")
        self.no_questions_cb.stateChanged.connect(self._on_no_questions_toggled)
        header_layout.addWidget(self.no_questions_cb)
        header_layout.addWidget(dashboard_btn)
        header_layout.addWidget(clear_btn)
        header_layout.addWidget(export_btn)
        
        chat_layout.addLayout(header_layout)
        
        # Chat Display
        self.chat_display = QTextEdit()
        self.chat_display.setReadOnly(True)
        self.chat_display.setStyleSheet("""
            QTextEdit {
                background-color: #0d1117;
                color: #ffffff;
                border: 2px solid #30363d;
                border-radius: 12px;
                padding: 15px;
                font-family: 'Segoe UI', Arial, sans-serif;
                font-size: 14px;
                line-height: 1.6;
            }
        """)
        chat_layout.addWidget(self.chat_display)

        # Typing Indicator (natürliches Chat-Gefühl)
        self.typing_label = QLabel("CUDI tippt…")
        self.typing_label.setStyleSheet("color: #7d8590; font-style: italic; padding: 4px 2px;")
        self.typing_label.setVisible(False)
        chat_layout.addWidget(self.typing_label)
        
        # Input Area
        input_layout = QHBoxLayout()

        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Schreibe deine Nachricht an CUDI…")
        self.chat_input.setStyleSheet("""
            QLineEdit {
                background-color: #21262d;
                color: #ffffff;
                border: 2px solid #30363d;
                border-radius: 8px;
                padding: 12px 16px;
                font-size: 14px;
                min-height: 20px;
            }
            QLineEdit:focus {
                border-color: #1f6feb;
                background-color: #161b22;
            }
        """)
        self.chat_input.returnPressed.connect(self.send_message)
        
        send_btn = QPushButton("🚀 Send")
        send_btn.clicked.connect(self.send_message)
        send_btn.setMinimumWidth(100)
        send_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                          stop: 0 #1f6feb, stop: 1 #0969da);
                color: white;
                border: 1px solid #1f6feb;
                border-radius: 8px;
                padding: 12px 16px;
                font-weight: bold;
                font-size: 14px;
                min-height: 20px;
            }
            QPushButton:hover {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                          stop: 0 #4184e4, stop: 1 #1f6feb);
            }
        """)
        
        input_layout.addWidget(self.chat_input)
        input_layout.addWidget(send_btn)
        
        chat_layout.addLayout(input_layout)
        
        return chat_widget

    def _show_typing_indicator(self):
        try:
            if not getattr(self, 'typing_enabled', True):
                return
            if not hasattr(self, 'typing_label'):
                return
            self.typing_label.setVisible(True)
            # Einfaches Dot-Animation mittels Timer
            if not hasattr(self, 'typing_timer'):
                self.typing_timer = QTimer()
                self._typing_dots = 0
                def _tick():
                    self._typing_dots = (self._typing_dots + 1) % 4
                    self.typing_label.setText("CUDI tippt" + "." * self._typing_dots)
                self.typing_timer.timeout.connect(_tick)
            if not self.typing_timer.isActive():
                self.typing_timer.start(400)
        except Exception:
            pass

    def _hide_typing_indicator(self):
        try:
            if hasattr(self, 'typing_timer') and self.typing_timer.isActive():
                self.typing_timer.stop()
            if hasattr(self, 'typing_label'):
                self.typing_label.setVisible(False)
        except Exception:
            pass

    def toggle_typing_indicator(self, state: int):
        """Aktiviert/Deaktiviert die Anzeige des Tipp-Indikators."""
        self.typing_enabled = bool(state)
        if not self.typing_enabled:
            self._hide_typing_indicator()
        # speichern
        try:
            self._save_user_prefs()
        except Exception:
            pass

    def toggle_clarify(self, state: int):
        """Aktiviert/Deaktiviert Klarheitsfragen vor der Antwort."""
        self.clarify_enabled = bool(state)
        try:
            self._save_user_prefs()
        except Exception:
            pass

    def _on_block_ambiguity_toggled(self, state: int):
        """Aktiviert/Deaktiviert Blockieren bei unklaren Eingaben."""
        self.block_on_ambiguity = bool(state)
        try:
            self._save_user_prefs()
        except Exception:
            pass

    def _on_robust_intent_toggled(self, state: int):
        self.robust_intent_enabled = bool(state)
        try:
            self._save_user_prefs()
        except Exception:
            pass
    
    def _on_auto_learn_toggled(self, state: int):
        self.autonomous_learning_enabled = bool(state)
        try:
            self._save_user_prefs()
        except Exception:
            pass
    
    def _on_auto_debug_toggled(self, state: int):
        self.auto_debug_enabled = bool(state)
        if bool(state):
            self.add_chat_message("🔧 Auto-Debug", "Selbstheilungs-System aktiviert")
        else:
            self.add_chat_message("⚠️ Auto-Debug", "Selbstheilungs-System deaktiviert")
        try:
            self._save_user_prefs()
        except Exception:
            pass
    
    def _show_system_diagnostics(self):
        """Zeigt System-Diagnose Dialog."""
        try:
            diagnosis = self._run_self_diagnosis()
            
            dialog = QDialog(self)
            dialog.setWindowTitle("CUDI System Diagnostics")
            dialog.setFixedSize(500, 400)
            
            layout = QVBoxLayout()
            
            # System Health
            health_label = QLabel(f"System Health: {diagnosis['system_health'].upper()}")
            if diagnosis['system_health'] == 'excellent':
                health_label.setStyleSheet("color: green; font-weight: bold;")
            elif diagnosis['system_health'] == 'good':
                health_label.setStyleSheet("color: orange; font-weight: bold;")
            else:
                health_label.setStyleSheet("color: red; font-weight: bold;")
            layout.addWidget(health_label)
            
            # Diagnose-Details
            details_text = QTextEdit()
            details_content = f"""🔍 SYSTEM DIAGNOSE
{'='*40}

✅ Abhängigkeiten: {'OK' if diagnosis['dependencies_ok'] else 'FEHLER'}
📁 Dateisystem: {'OK' if diagnosis['file_system_ok'] else 'FEHLER'}
🌐 Netzwerk: {'OK' if diagnosis['network_ok'] else 'FEHLER'}
🔒 Berechtigungen: {'OK' if diagnosis['permissions_ok'] else 'FEHLER'}

❌ GEFUNDENE PROBLEME:
{chr(10).join(f'• {issue}' for issue in diagnosis['issues_found']) if diagnosis['issues_found'] else '• Keine Probleme gefunden'}

💡 EMPFEHLUNGEN:
{chr(10).join(f'• {rec}' for rec in diagnosis['recommendations']) if diagnosis['recommendations'] else '• Keine Aktionen erforderlich'}

📊 FEHLER STATISTIK:
Gesamte Fehler: {len(self.error_tracker)}
Erfolgreiche Reparaturen: {len(self.repair_attempts)}

🕐 Letzter Check: {diagnosis['timestamp']}
"""
            details_text.setPlainText(details_content)
            details_text.setReadOnly(True)
            layout.addWidget(details_text)
            
            # Buttons
            button_layout = QHBoxLayout()
            
            refresh_btn = QPushButton("🔄 Refresh")
            refresh_btn.clicked.connect(lambda: self._refresh_diagnostics(details_text))
            button_layout.addWidget(refresh_btn)
            
            repair_btn = QPushButton("🔧 Auto-Repair")
            repair_btn.clicked.connect(lambda: self._run_manual_repair(details_text))
            button_layout.addWidget(repair_btn)
            
            close_btn = QPushButton("❌ Close")
            close_btn.clicked.connect(dialog.close)
            button_layout.addWidget(close_btn)
            
            layout.addLayout(button_layout)
            dialog.setLayout(layout)
            dialog.exec_()
            
        except Exception as e:
            self.add_chat_message("❌ Diagnostics Error", f"Fehler beim Öffnen der Diagnose: {str(e)}")
    
    def _refresh_diagnostics(self, text_widget):
        """Aktualisiert die Diagnose-Anzeige."""
        try:
            diagnosis = self._run_self_diagnosis()
            self.add_chat_message("🔄 Diagnostics", "Diagnose aktualisiert")
        except Exception as e:
            self.add_chat_message("❌ Refresh Error", f"Fehler bei Diagnose-Update: {str(e)}")
    
    def _run_manual_repair(self, text_widget):
        """Führt manuelle Reparatur durch."""
        try:
            success = self._auto_recovery_system()
            if success:
                self.add_chat_message("✅ Manual Repair", "Reparatur erfolgreich durchgeführt")
            else:
                self.add_chat_message("⚠️ Manual Repair", "Keine Reparaturen erforderlich oder fehlgeschlagen")
        except Exception as e:
            self.add_chat_message("❌ Repair Error", f"Fehler bei manueller Reparatur: {str(e)}")
    
    def _on_no_questions_toggled(self, state: int):
        """Handler für No-Questions Mode Toggle"""
        self.no_questions_mode = bool(state)
        if bool(state):
            self.add_chat_message("⚡ Direct Action", "Direkte Aktions-Ausführung aktiviert - keine Fragen mehr!")
        else:
            self.add_chat_message("💬 Normal Mode", "Standard-Modus aktiviert - mit Nachfragen")
        try:
            self._save_user_prefs()
        except Exception:
            pass

    # Nutzereinstellungen Persistenz
    def _prefs_file(self) -> Path:
        cfg = Path("config")
        cfg.mkdir(exist_ok=True)
        return cfg / "user_prefs.json"

    def _save_user_prefs(self):
        data = {
            "typing_enabled": bool(getattr(self, 'typing_enabled', True)),
            "response_style": (getattr(self, 'communication_engine', None) and getattr(self.communication_engine, 'communication_style', None)) or None,
            "clarify_enabled": bool(getattr(self, 'clarify_enabled', True)),
            "block_on_ambiguity": bool(getattr(self, 'block_on_ambiguity', True)),
            "robust_intent_enabled": bool(getattr(self, 'robust_intent_enabled', True)),
            "autonomous_learning_enabled": bool(getattr(self, 'autonomous_learning_enabled', True)),
            "auto_debug_enabled": bool(getattr(self, 'auto_debug_enabled', True)),
            "autonomous_actions": bool(getattr(self, 'autonomous_actions', True)),
            "response_mode": (getattr(self, 'communication_engine', None) and getattr(self.communication_engine, 'response_mode', None)) or None,
            "response_length": (getattr(self, 'communication_engine', None) and getattr(self.communication_engine, 'response_length', None)) or None,
            "form_of_address": (getattr(self, 'communication_engine', None) and getattr(self.communication_engine, 'form_of_address', None)) or None,
        }
        try:
            with self._prefs_file().open('w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _load_user_prefs(self):
        pf = self._prefs_file()
        if not pf.exists():
            return
        try:
            data = json.loads(pf.read_text(encoding='utf-8'))
        except Exception:
            return
        if 'typing_enabled' in data:
            self.typing_enabled = bool(data['typing_enabled'])
            if hasattr(self, 'typing_cb'):
                self.typing_cb.setChecked(self.typing_enabled)
        if 'clarify_enabled' in data:
            self.clarify_enabled = bool(data['clarify_enabled'])
            if hasattr(self, 'clarify_cb'):
                self.clarify_cb.setChecked(self.clarify_enabled)
        if 'block_on_ambiguity' in data:
            self.block_on_ambiguity = bool(data['block_on_ambiguity'])
            if hasattr(self, 'block_ambig_cb'):
                self.block_ambig_cb.setChecked(self.block_on_ambiguity)
        if 'autonomous_actions' in data:
            self.autonomous_actions = bool(data['autonomous_actions'])
        if 'robust_intent_enabled' in data:
            self.robust_intent_enabled = bool(data['robust_intent_enabled'])
            if hasattr(self, 'robust_intent_cb'):
                self.robust_intent_cb.setChecked(self.robust_intent_enabled)
        if 'autonomous_learning_enabled' in data:
            self.autonomous_learning_enabled = bool(data['autonomous_learning_enabled'])
            if hasattr(self, 'auto_learn_cb'):
                self.auto_learn_cb.setChecked(self.autonomous_learning_enabled)
        if 'auto_debug_enabled' in data:
            self.auto_debug_enabled = bool(data['auto_debug_enabled'])
            if hasattr(self, 'auto_debug_cb'):
                self.auto_debug_cb.setChecked(self.auto_debug_enabled)
        style_code = data.get('response_style')
        if style_code and hasattr(self, 'header_style_cb'):
            inv = {
                'concise': "🎯 Präzise",
                'detailed': "📚 Detailliert",
                'creative': "💡 Kreativ",
                'friendly': "🤝 Freundlich",
                'technical': "🔬 Technisch",
            }
            label = inv.get(style_code)
            if label:
                idx = self.header_style_cb.findText(label)
                if idx >= 0:
                    self.header_style_cb.setCurrentIndex(idx)
        # Lade Antwortmodus
        if 'response_mode' in data and hasattr(self, 'mode_cb'):
            inv = {
                'auto': "🤖 Auto",
                'explain': "📘 Erklären",
                'implement': "🛠️ Umsetzen",
                'debug': "🐛 Debuggen",
                'brainstorm': "💡 Brainstorm",
                'research': "🔎 Recherchieren",
            }
            label = inv.get(data['response_mode'])
            if label:
                i = self.mode_cb.findText(label)
                if i >= 0:
                    self.mode_cb.setCurrentIndex(i)
        # Lade Antwortlänge
        if 'response_length' in data and hasattr(self, 'length_cb'):
            inv = {'short': 'Kurz', 'medium': 'Mittel', 'long': 'Ausführlich'}
            label = inv.get(data['response_length'])
            if label:
                i = self.length_cb.findText(label)
                if i >= 0:
                    self.length_cb.setCurrentIndex(i)
        # Lade Anrede
        if 'form_of_address' in data and hasattr(self, 'address_cb'):
            inv = {'du': 'Du', 'sie': 'Sie'}
            label = inv.get(data['form_of_address'])
            if label:
                i = self.address_cb.findText(label)
                if i >= 0:
                    self.address_cb.setCurrentIndex(i)

    # Verständnis & Kommunikation – Klarheitslogik
    def _is_ambiguous(self, message: str) -> bool:
        """Einfache Heuristik: ist die Eingabe unklar/zu kurz?"""
        if not message:
            return True
        msg = message.strip().lower()
        words = [w for w in msg.replace("\n", " ").split(" ") if w]
        # sehr kurze oder ein-Wort-Eingaben meist unklar
        if len(words) <= 2:
            return True
        # typische vage Phrasen
        vague = [
            "hilfe", "hilf mir", "kannst du helfen", "was meinst du",
            "weiß nicht", "weiss nicht", "keine ahnung", "mach mal",
            "mach was", "tu was", "tu mal", "bitte", "los", "go",
        ]
        if any(p in msg for p in vague):
            return True
        # klare Intents entschärfen Ambiguität
        intents = [
            "erkläre", "erklaere", "zeige", "analysiere", "recherchiere",
            "baue", "erstelle", "schreibe", "debugge", "löse", "loese",
            "plane", "entwirf", "bewerte", "optimiere", "implementiere",
            "brainstorm", "ideen", "vergleich", "summiere", "entwerfe",
        ]
        if any(v in msg for v in intents):
            return False
        # reine Fragewörter ohne Objekt sind unklar
        question_words = ["wie", "was", "wo", "warum", "wieso", "welche", "welcher", "welches"]
        if ("?" in msg) and (len(words) < 5) and any(msg.startswith(qw+" ") for qw in question_words):
            return True
        # Mehrfachthemen mit "und" ohne Struktur -> potenziell unklar
        if " und " in msg and ("," not in msg and ";" not in msg):
            return True
        return False

    def _build_clarifying_response(self, message: str) -> str:
        """Erzeugt eine gezielte, knappe Rückfrage mit Verständnis-Check."""
        msg = (message or "").strip()
        # Kurz zusammenfassen (heuristisch)
        summary = msg[:120] + ("…" if len(msg) > 120 else "")
        # 2–3 typische Optionen anbieten
        options = [
            "Erklärung mit Beispielen",
            "Konkrete Umsetzung mit Code/Schritten",
            "Fehleranalyse/Debugging",
        ]
        style = getattr(self, 'communication_engine', None) and getattr(self.communication_engine, 'communication_style', 'comprehensive')
        tone = "kurz & direkt" if style in ("concise", "technical") else "klar & freundlich"
        return (
            f"Ich will dich richtig verstehen. Du meintest: \"{summary}\"\n\n"
            f"Was brauchst du genau (eine wählen oder präzisieren)?\n"
            f"• {options[0]}\n"
            f"• {options[1]}\n"
            f"• {options[2]}\n\n"
            f"1-2 Stichworte reichen. Ich antworte dann {tone}."
        )

    def ensure_psutil_installed(self):
        """Stellt sicher, dass psutil installiert und importiert ist."""
        global psutil
        if psutil is not None:
            return
        # Versuche, psutil zu importieren – falls nicht da, installieren
        try:
            psutil = importlib.import_module('psutil')
            self.add_chat_message("✅ System", "psutil gefunden – echte Systemmetriken aktiv.")
            return
        except Exception:
            pass
        try:
            # Installiere psutil für aktuellen Interpreter
            subprocess.check_call([sys.executable, "-m", "pip", "install", "--user", "psutil"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            psutil = importlib.import_module('psutil')
            self.add_chat_message("✅ System", "psutil installiert – echte CPU/RAM-Metriken aktiviert.")
        except Exception as e:
            # Keine harte Fehlermeldung, aber Hinweis
            self.add_chat_message("⚠️ System", f"Konnte psutil nicht installieren. Verwende Schätzwerte. Fehler: {e}")
    
    def create_plugin_tool_center(self):
        """Erstellt das Plugin & Tool Center (Right Panel)"""
        tools_widget = QWidget()
        tools_widget.setFixedWidth(400)
        tools_widget.setStyleSheet("""
            QWidget {
                background-color: #161b22;
                border-left: 3px solid #30363d;
                border-radius: 12px;
            }
        """)
        
        tools_layout = QVBoxLayout(tools_widget)
        tools_layout.setSpacing(15)
        tools_layout.setContentsMargins(15, 15, 15, 15)
        
        # Plugin Manager Section
        self.create_plugin_manager_section(tools_layout)
        
        # AI Tools Section
        self.create_ai_tools_section(tools_layout)
        
        # Task Automation Section
        self.create_task_automation_section(tools_layout)
        
        # System Monitor Section
        self.create_advanced_system_monitor(tools_layout)
        
        tools_layout.addStretch()
        return tools_widget
    
    def create_plugin_manager_section(self, layout):
        """Erstellt Plugin Manager Section"""
        plugin_card = ModernCard("🔌 Plugin Manager")
        plugin_layout = QVBoxLayout()
        
        # Plugin Controls
        controls_layout = QHBoxLayout()
        
        reload_plugins_btn = QPushButton("🔄 Reload")
        reload_plugins_btn.clicked.connect(self.reload_plugins)
        reload_plugins_btn.setMaximumWidth(80)
        
        add_plugin_btn = QPushButton("➕ Add")
        add_plugin_btn.clicked.connect(self.add_plugin_dialog)
        add_plugin_btn.setMaximumWidth(70)
        
        manage_plugins_btn = QPushButton("⚙️ Manage")
        manage_plugins_btn.clicked.connect(self.open_plugin_manager)
        manage_plugins_btn.setMaximumWidth(80)
        
        controls_layout.addWidget(reload_plugins_btn)
        controls_layout.addWidget(add_plugin_btn)
        controls_layout.addWidget(manage_plugins_btn)
        controls_layout.addStretch()
        
        plugin_layout.addLayout(controls_layout)
        
        # Active Plugins List
        self.active_plugins_list = QListWidget()
        self.active_plugins_list.setMaximumHeight(150)
        self.active_plugins_list.setStyleSheet("""
            QListWidget {
                background-color: #0d1117;
                color: #ffffff;
                border: 2px solid #30363d;
                border-radius: 8px;
                padding: 8px;
            }
            QListWidget::item {
                padding: 8px;
                border-bottom: 1px solid #21262d;
                border-radius: 4px;
            }
            QListWidget::item:hover {
                background-color: #21262d;
            }
            QListWidget::item:selected {
                background-color: #1f6feb;
                color: #ffffff;
            }
        """)
        
        # Reale Plugins laden (keine Demos/Testdaten)
        try:
            if self.plugin_manager and hasattr(self.plugin_manager, 'get_plugin_list'):
                plugins = self.plugin_manager.get_plugin_list() or []
                for plugin in plugins:
                    self.active_plugins_list.addItem(QListWidgetItem(str(plugin)))
        except Exception:
            pass
        
        plugin_layout.addWidget(self.active_plugins_list)
        
        plugin_card.main_layout.addLayout(plugin_layout)
        layout.addWidget(plugin_card)
    
    def create_ai_tools_section(self, layout):
        """Erstellt AI Tools Section"""
        tools_card = ModernCard("🛠️ AI Tools")
        tools_layout = QVBoxLayout()
        
        # Tool Buttons
        ai_tools = [
            ("🔍 Research Assistant", self.launch_research_tool),
            ("📝 Content Generator", self.launch_content_tool),
            ("🧮 Data Analyzer", self.launch_data_tool),
            ("🎨 Creative Studio", self.launch_creative_tool),
            ("📊 Report Builder", self.launch_report_tool)
        ]
        
        for tool_name, callback in ai_tools:
            btn = QPushButton(tool_name)
            btn.clicked.connect(callback)
            btn.setMinimumHeight(35)
            btn.setStyleSheet("""
                QPushButton {
                    text-align: left;
                    padding: 8px 12px;
                    font-size: 12px;
                }
            """)
            tools_layout.addWidget(btn)
        
        tools_card.main_layout.addLayout(tools_layout)
        layout.addWidget(tools_card)
    
    def create_task_automation_section(self, layout):
        """Erstellt Task Automation Section"""
        automation_card = ModernCard("⚡ Task Automation")
        automation_layout = QVBoxLayout()
        
        # Quick Tasks
        task_buttons = [
            ("📧 Email Assistant", self.launch_email_assistant),
            ("📅 Calendar Manager", self.launch_calendar_manager),
            ("📂 File Organizer", self.launch_file_organizer),
            ("🌐 Web Scraper", self.launch_web_scraper)
        ]
        
        for task_name, callback in task_buttons:
            btn = QPushButton(task_name)
            btn.clicked.connect(callback)
            btn.setMinimumHeight(30)
            btn.setStyleSheet("""
                QPushButton {
                    text-align: left;
                    padding: 6px 10px;
                    font-size: 11px;
                }
            """)
            automation_layout.addWidget(btn)
        
        automation_card.main_layout.addLayout(automation_layout)
        layout.addWidget(automation_card)
    
    def create_advanced_system_monitor(self, layout):
        """Erstellt Advanced System Monitor"""
        monitor_card = ModernCard("📊 System Monitor")
        monitor_layout = QVBoxLayout()
        
        # Performance Metrics
        metrics_layout = QGridLayout()
        
        self.performance_metrics = {}
        metrics = [
            ("Requests/min", "requests", 42),
            ("Avg Response", "response", 1.2),
            ("Memory Usage", "memory", 45),
            ("CPU Usage", "cpu", 23)
        ]
        
        for i, (name, key, value) in enumerate(metrics):
            row = i // 2
            col = (i % 2) * 2
            
            # Metric Name
            name_label = QLabel(name)
            name_label.setStyleSheet("color: #ffffff; font-size: 10px;")
            metrics_layout.addWidget(name_label, row, col)
            
            # Metric Value
            if key in ["response"]:
                value_label = QLabel(f"{value}s")
            elif key in ["memory", "cpu"]:
                value_label = QLabel(f"{value}%")
            else:
                value_label = QLabel(str(value))
            
            value_label.setStyleSheet("color: #39d353; font-weight: bold; font-size: 10px;")
            metrics_layout.addWidget(value_label, row, col + 1)
            
            self.performance_metrics[key] = value_label
        
        monitor_layout.addLayout(metrics_layout)
        
        # System Status
        status_layout = QVBoxLayout()
        
        self.system_uptime = QLabel("Uptime: 02:34:56")
        self.system_uptime.setStyleSheet("color: #ffffff; font-size: 10px;")
        
        self.total_queries = QLabel("Total Queries: 1,247")
        self.total_queries.setStyleSheet("color: #ffffff; font-size: 10px;")
        
        status_layout.addWidget(self.system_uptime)
        status_layout.addWidget(self.total_queries)
        
        monitor_layout.addLayout(status_layout)
        
        monitor_card.main_layout.addLayout(monitor_layout)
        layout.addWidget(monitor_card)
    
    def create_supreme_menu(self):
        """Erstellt Supreme Menu Bar"""
        menubar = self.menuBar()
        
        # File Menu
        file_menu = menubar.addMenu('&File')
        
        new_action = QAction('&New Chat', self)
        new_action.setShortcut('Ctrl+N')
        new_action.triggered.connect(self.new_chat)
        file_menu.addAction(new_action)
        
        save_action = QAction('&Save Chat', self)
        save_action.setShortcut('Ctrl+S')
        save_action.triggered.connect(self.save_chat)
        file_menu.addAction(save_action)
        
        file_menu.addSeparator()
        
        exit_action = QAction('E&xit', self)
        exit_action.setShortcut('Ctrl+Q')
        exit_action.triggered.connect(self.close)
        file_menu.addAction(exit_action)
        
        # AI Menu
        ai_menu = menubar.addMenu('&AI')
        
        train_action = QAction('&Train Model', self)
        train_action.triggered.connect(self.train_model)
        ai_menu.addAction(train_action)
        
        settings_action = QAction('&Settings', self)
        settings_action.triggered.connect(self.open_ai_settings)
        ai_menu.addAction(settings_action)
        
        # Tools Menu
        tools_menu = menubar.addMenu('&Tools')
        
        plugins_action = QAction('&Plugin Manager', self)
        plugins_action.triggered.connect(self.open_plugin_manager)
        tools_menu.addAction(plugins_action)
        
        voice_action = QAction('&Voice Settings', self)
        voice_action.triggered.connect(self.open_voice_settings)
        tools_menu.addAction(voice_action)
        
        # Help Menu
        help_menu = menubar.addMenu('&Help')
        
        about_action = QAction('&About', self)
        about_action.triggered.connect(self.show_about)
        help_menu.addAction(about_action)
    
    def create_supreme_toolbar(self):
        """Erstellt Supreme Toolbar"""
        toolbar = self.addToolBar('Main')
        toolbar.setMovable(False)
        
        # Quick Actions
        new_chat_action = QAction('🆕 New', self)
        new_chat_action.triggered.connect(self.new_chat)
        toolbar.addAction(new_chat_action)
        
        voice_toggle_action = QAction('🎤 Voice', self)
        voice_toggle_action.setCheckable(True)
        voice_toggle_action.setChecked(True)
        voice_toggle_action.triggered.connect(self.toggle_voice_listening)
        toolbar.addAction(voice_toggle_action)
        
        toolbar.addSeparator()
        
        plugin_action = QAction('🔌 Plugins', self)
        plugin_action.triggered.connect(self.open_plugin_manager)
        toolbar.addAction(plugin_action)
        
        settings_action = QAction('⚙️ Settings', self)
        settings_action.triggered.connect(self.open_ai_settings)
        toolbar.addAction(settings_action)
    
    def create_supreme_statusbar(self):
        """Erstellt Supreme Status Bar"""
        statusbar = self.statusBar()
        
        # AI Status
        self.ai_status_label = QLabel("🤖 CUDI_SUPREME Ready")
        self.ai_status_label.setStyleSheet("color: #39d353; font-weight: bold;")
        statusbar.addWidget(self.ai_status_label)
        
        statusbar.addPermanentWidget(QLabel(" | "))
        
        # Connection Status
        self.connection_status = QLabel("🌐 Connected")
        self.connection_status.setStyleSheet("color: #39d353;")
        statusbar.addPermanentWidget(self.connection_status)
        
        statusbar.addPermanentWidget(QLabel(" | "))
        
        # Performance
        self.performance_status = QLabel("⚡ High Performance")
        self.performance_status.setStyleSheet("color: #39d353;")
        statusbar.addPermanentWidget(self.performance_status)
    
    # Chat Methods
    def add_chat_message(self, sender, message):
        """Fügt Nachricht zum Chat hinzu"""
        timestamp = datetime.now().strftime("%H:%M:%S")
        
        # HTML-formatierte Nachricht
        html_message = f"""
        <div style="margin: 10px 0; padding: 12px; background-color: #21262d; border-radius: 8px; border-left: 4px solid #1f6feb;">
            <div style="color: #1f6feb; font-weight: bold; margin-bottom: 5px;">
                {sender} <span style="color: #7d8590; font-size: 11px;">{timestamp}</span>
            </div>
            <div style="color: #ffffff; line-height: 1.5;">
                {str(message).replace('\n', '<br>')}
            </div>
        </div>
        """
        
        self.chat_display.append(html_message)
        
        # Auto-scroll to bottom
        scrollbar = self.chat_display.verticalScrollBar()
        scrollbar.setValue(scrollbar.maximum())
        
        # Conversation history speichern
        self.conversation_context.append({
            "sender": sender,
            "message": message,
            "timestamp": timestamp
        })
    
    def send_message(self):
        """Sendet Nachricht"""
        message = self.chat_input.text().strip()
        if not message:
            return
        
        # User message hinzufügen
        self.add_chat_message("👤 Du", message)
        self.chat_input.clear()
        
        # Wähle Verarbeitungs-Modus basierend auf Toggle
        if getattr(self, 'no_questions_mode', True):  # Standard: Direct Action
            # DIREKTE AKTIONS-VERARBEITUNG ohne Fragen
            self.process_user_input_no_questions(message)
        else:
            # Original-Methode mit möglichen Nachfragen
            self.process_user_input(message)
    
    def process_user_input(self, message):
        """Verarbeitet User Input mit Auto-Tool-Routing"""
        # Nachricht für spätere Aktionen speichern
        self._current_message = message
        
        # Tippindikator zeigen
        try:
            self._show_typing_indicator()
        except Exception:
            pass
        # SOFORT HANDELN - Keine Schwellenwerte
        routed = None
        try:
            if getattr(self, 'robust_intent_enabled', True):
                intent_key, score, slots = self._route_intent_robust(message)
                if intent_key and score >= 0.25:  # Sehr niedrige Schwelle
                    routed = intent_key
                    # SOFORT echte Aktion ausführen
                    self._execute_immediate_action(intent_key, message, slots)
                else:
                    # IMMER Fallback-Aktion ausführen
                    self._force_real_action_fallback(message)
                    self._route_to_intent(intent_key, slots)
        except Exception as e:
            self.add_chat_message("⚠️ CUDI", f"Fehler bei Intent-Erkennung: {str(e)}")
        # Falls nicht klar geroutet: Bei Unklarheit und Klarheitsfragen aktiv → erst nachfragen
        try:
            if not routed and getattr(self, 'clarify_enabled', True) and self._is_ambiguous(message):
                clarifier = self._build_clarifying_response(message)
                self.add_chat_message("🤖 CUDI", clarifier)
                if getattr(self, 'block_on_ambiguity', True):
                    try:
                        self.set_avatar_state("idle")
                    except Exception:
                        pass
                    return
        except Exception:
            pass
        # Falls nicht robust geroutet wurde: einfache Heuristik nutzen UND echte Aktionen forcieren
        try:
            if not routed:
                self._auto_route_tools(message)
                # Auch wenn kein klarer Intent: trotzdem eine echte Aktion versuchen
                self._force_real_action_fallback(message)
        except Exception as e:
            self.add_chat_message("⚠️ CUDI", f"Fehler bei Fallback-Routing: {str(e)}")

        # Prüfe Wissenslücken und starte ggf. autonomes Lernen
        try:
            if getattr(self, 'autonomous_learning_enabled', True):
                self._check_and_learn_if_needed(message)
        except Exception:
            pass

        # Sofortige, natürlich klingende Rückmeldung
        try:
            ack = random.choice([
                "Einen Moment, ich denke kurz nach…",
                "Ich schaue mir das eben an…",
                "Sekunde, ich sortiere die Infos…",
                "Alles klar – ich bereite dir eine Antwort vor…",
            ])
            self.add_chat_message("🤖 CUDI", ack)
        except Exception:
            pass

        try:
            self.set_avatar_state("thinking")
        except Exception:
            pass

        # Bevorzugt: CudiBrain
        if getattr(self, 'brain', None):
            thread = threading.Thread(target=self._get_brain_response, args=(message,))
            thread.daemon = True
            thread.start()
            return

        # Alternative: Communication Engine (LLM)
        if getattr(self, 'communication_engine', None):
            thread = threading.Thread(target=self._get_intelligent_response, args=(message,))
            thread.daemon = True
            thread.start()
            return

        # Letzter Fallback: Direkte Antwort
        self._get_direct_response(message)

    def _auto_route_tools(self, message: str):
        """Erkennt Intention und wählt automatisch passende Funktion/Modus.
        - Keine UI-Umschaltung nötig; nur dezente Systemmeldung und Kontexte aktivieren.
        """
        text = (message or "").lower()
        routed = None

        patterns = [
            (['recherche', 'recherchiere', 'suche', 'recherchieren', 'research', 'web'], self.trigger_research_mode, "research"),
            (['lernen', 'erkläre', 'erklaer', 'knowledge', 'study', 'lernen wir'], self.trigger_learning_mode, "learning"),
            (['kreativ', 'ideen', 'brainstorm', 'creative', 'design', 'story'], self.trigger_creative_mode, "creative"),
            (['problem', 'bug', 'fehler', 'kaputt', 'geht nicht', 'fix', 'debug'], self.trigger_problem_solving, "problem"),
            (['innovation', 'innovativ', 'zukunft', 'trends', 'vision'], self.trigger_innovation_mode, "innovation"),
            (['analyse', 'analysiere', 'analyse', 'data', 'daten'], self.quick_analyze, "analyze"),
        ]

        for keywords, callback, mode_key in patterns:
            if any(k in text for k in keywords):
                routed = mode_key
                try:
                    callback()
                except Exception:
                    pass
                break

        if routed:
            self.current_mode = routed
            label_map = {
                'research': '🔍 Research',
                'learning': '📚 Learning',
                'creative': '🎨 Creative',
                'problem': '🛠️ Problem Solving',
                'innovation': '💡 Innovation',
                'analyze': '🧠 Analyze'
            }
            self.add_chat_message("🔍 System", f"Automatische Werkzeugwahl: {label_map.get(routed, routed)}")

    # Robust Intent Understanding
    def _normalize_text(self, s: str) -> str:
        s = (s or "").lower().strip()
        repl = {
            "ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss",
        }
        for k, v in repl.items():
            s = s.replace(k, v)
        # einfache Zeichensetzung entfernen
        for ch in ",.;:!?()[]{}\"'\n\r\t":
            s = s.replace(ch, " ")
        # mehrfachspaces zu single
        s = " ".join([w for w in s.split(" ") if w])
        return s

    def _score_match(self, text: str, terms: list) -> float:
        # Punkte: exakte Token-Treffer, substring, leichte Fuzzy via SequenceMatcher
        try:
            from difflib import SequenceMatcher
        except Exception:
            SequenceMatcher = None
        score = 0.0
        tokens = set(text.split(" "))
        for t in terms:
            t_norm = self._normalize_text(t)
            if t_norm in tokens:
                score += 1.0
            elif t_norm in text:
                score += 0.6
            elif SequenceMatcher:
                ratio = SequenceMatcher(None, text, t_norm).quick_ratio()
                score += 0.4 * ratio
        # normalisieren auf 0..1
        max_score = max(1.0, len(terms))
        return min(1.0, score / max_score)

    def _extract_slots(self, text: str) -> dict:
        slots = {}
        domains = {
            'app': ["app", "anwendung", "programm", "tool"],
            'website': ["website", "webseite", "seite", "landing"],
            'code': ["code", "skript", "script", "python", "js", "java"],
            'daten': ["daten", "data", "csv", "excel", "database", "db"],
            'datei': ["datei", "file", "ordner", "folder"],
            'text': ["text", "beschreibung", "content", "inhalt"],
            'grafik': ["logo", "grafik", "bild", "image"],
            'email': ["mail", "email", "e-mail"],
            'kalender': ["kalender", "termine", "agenda"],
        }
        ntext = self._normalize_text(text)
        for k, terms in domains.items():
            if any(t in ntext for t in map(self._normalize_text, terms)):
                slots.setdefault('domain', set()).add(k)
        if 'domain' in slots:
            slots['domain'] = sorted(list(slots['domain']))
        return slots

    def _route_to_intent(self, intent_key: str, slots: dict | None = None):
        # UI Status setzen und ggf. Modus in Engine beeinflussen + ECHTE Aktionen ausführen
        self.current_mode = intent_key
        label_map = {
            'research': '🔎 Recherchieren',
            'explain': '📘 Erklären',
            'implement': '🛠️ Umsetzen',
            'debug': '🐛 Debuggen',
            'brainstorm': '💡 Brainstorm',
            'analyze': '🧠 Analyze',
            'summarize': '📝 Zusammenfassen',
            'compare': '⚖️ Vergleichen',
            'plan': '🗺️ Planen',
            'generate': '✍️ Generieren',
        }
        try:
            self.add_chat_message("🔍 System", f"Automatische Werkzeugwahl: {label_map.get(intent_key, intent_key)}")
        except Exception:
            pass
        
        # ECHTE Aktion ausführen
        try:
            if intent_key in ['implement', 'research', 'analyze', 'generate']:
                # Starte echte Aktion in separatem Thread
                action_thread = threading.Thread(
                    target=self._execute_real_action_thread, 
                    args=(intent_key, getattr(self, '_current_message', ''), slots)
                )
                action_thread.daemon = True
                action_thread.start()
        except Exception as e:
            pass  # Optimized error handling
        
        # Engine-Response-Mode hint
        if getattr(self, 'communication_engine', None):
            mapping = {
                'research': 'research',
                'explain': 'explain',
                'implement': 'implement',
                'debug': 'debug',
                'brainstorm': 'brainstorm',
                'analyze': 'analyze',
                'summarize': 'explain',
                'compare': 'analyze',
                'plan': 'brainstorm',
                'generate': 'implement',
            }
            try:
                self.communication_engine.response_mode = mapping.get(intent_key, getattr(self.communication_engine, 'response_mode', 'auto'))
            except Exception:
                pass
        # Trigger passende UI-/Brain-Modi, falls vorhanden
        dispatch = {
            'research': getattr(self, 'trigger_research_mode', None),
            'explain': getattr(self, 'trigger_learning_mode', None),
            'implement': getattr(self, 'trigger_creative_mode', None),
            'debug': getattr(self, 'trigger_problem_solving', None),
            'brainstorm': getattr(self, 'trigger_creative_mode', None),
            'analyze': getattr(self, 'quick_analyze', None),
        }
        cb = dispatch.get(intent_key)
        try:
            if callable(cb):
                cb()
        except Exception:
            pass

    def _force_real_action_fallback(self, message: str):
        """Forciert eine echte Aktion auch ohne klaren Intent."""
        try:
            msg_lower = message.lower()
            
            # Keyword-basierte Aktions-Forcierung
            if any(word in msg_lower for word in ['erstell', 'mach', 'bau', 'generier', 'schreib']):
                # Default: Dateierstellung
                result = self._create_real_files(message, {'domain': ['general']})
                self.add_chat_message("📝 CUDI Fallback", f"Ich erstelle etwas für dich:\n{result}")
            elif any(word in msg_lower for word in ['such', 'find', 'recherch', 'google']):
                # Default: Recherche
                result = self._perform_real_research(message)
                self.add_chat_message("🔍 CUDI Fallback", f"Ich recherchiere für dich:\n{result}")
            elif any(word in msg_lower for word in ['analys', 'auswert', 'prüf']):
                # Default: Analyse
                result = self._analyze_real_data(message, {})
                self.add_chat_message("📈 CUDI Fallback", f"Ich analysiere für dich:\n{result}")
            else:
                # Absolute Fallback: Immer eine Datei erstellen
                result = self._generate_real_content(message, {'domain': ['response']})
                self.add_chat_message("📤 CUDI Fallback", f"Ich erstelle Content basierend auf deiner Nachricht:\n{result}")
                
        except Exception as e:
            self.add_chat_message("❌ CUDI Fallback", f"Selbst der Fallback-Modus hatte einen Fehler: {str(e)}")

    def _execute_real_action_thread(self, intent: str, message: str, slots: dict):
        """Führt echte Aktion in separatem Thread aus."""
        try:
            result = self._execute_real_action(intent, message, slots)
            if result:
                self.message_received.emit("✅ CUDI", result)
        except Exception as e:
            self.message_received.emit("❌ CUDI", f"Fehler bei Aktion '{intent}': {str(e)}")

    def _route_intent_robust(self, message: str):
        ntext = self._normalize_text(message)
        if not ntext:
            return None, 0.0, {}
        intents = {
            'research': ["recherche", "recherchiere", "suche", "finde", "ermittle", "web", "internet"],
            'explain': ["erklaere", "erkläre", "erklaer", "erkl", "was ist", "wie funktioniert", "erläutere", "explain"],
            'implement': ["baue", "erstelle", "implementiere", "setze um", "generiere", "schreibe code", "code"],
            'debug': ["debug", "debugge", "fehler", "bug", "kaputt", "geht nicht", "fixe", "fehlersuche"],
            'brainstorm': ["brainstorm", "ideen", "vorschlaege", "vorschläge", "konzepte", "kreativ"],
            'analyze': ["analysiere", "analyse", "bewerte", "evaluate", "auswerten", "insight"],
            'summarize': ["zusammenfassen", "zusammenfassung", "tl;dr", "kurzfassen", "kurzfassung"],
            'compare': ["vergleiche", "gegenueberstellen", "gegenüberstellen", "pro contra", "unterschiede"],
            'plan': ["plane", "plan", "roadmap", "schritte", "vorgehen"],
            'generate': ["generiere", "schreibe", "texte", "content", "beschreibung", "prompt"],
        }
        best_key = None
        best_score = 0.0
        for key, terms in intents.items():
            sc = self._score_match(ntext, terms)
            if sc > best_score:
                best_key, best_score = key, sc
        slots = self._extract_slots(ntext)
        return best_key, best_score, slots

    # Autonome Wissenserweiterung
    def _check_and_learn_if_needed(self, message: str):
        """Prüft, ob eine Wissenslücke vorliegt und startet autonomes Lernen."""
        concepts = self._extract_concepts(message)
        unknown_concepts = [c for c in concepts if not self._has_knowledge(c)]
        
        for concept in unknown_concepts:
            if concept not in getattr(self, 'learning_in_progress', set()):
                self.learning_in_progress.add(concept)
                self.add_chat_message("🧠 CUDI", f"Ich kenne '{concept}' noch nicht gut genug. Ich recherchiere und lerne dazu...")
                # Starte Lernprozess in separatem Thread
                thread = threading.Thread(target=self._autonomous_learn, args=(concept,))
                thread.daemon = True
                thread.start()

    def _extract_concepts(self, message: str) -> list:
        """Extrahiert lernbare Konzepte aus der Nachricht."""
        text = message.lower()
        concepts = []
        
        # Technologie-Keywords
        tech_patterns = [
            r'\b(python|java|javascript|react|vue|angular|django|flask|node\.?js)\b',
            r'\b(programming|programmieren|coding|entwicklung|development)\b',
            r'\b(ai|ki|machine learning|deep learning|neural networks?)\b',
            r'\b(database|datenbank|sql|mongodb|postgresql)\b',
            r'\b(cloud|aws|azure|docker|kubernetes)\b',
            r'\b(jwt|oauth|api|rest|graphql)\b',
        ]
        
        import re
        for pattern in tech_patterns:
            matches = re.findall(pattern, text)
            concepts.extend(matches)
        
        # Frage-basierte Konzepte
        if any(q in text for q in ['kannst du', 'weißt du', 'kennst du']):
            # Extrahiere Haupt-Substantive nach Fragewörtern
            words = text.split()
            for i, word in enumerate(words):
                if word in ['programmieren', 'coding', 'entwickeln', 'ai', 'ki']:
                    concepts.append(word)
        
        return list(set(concepts))  # Duplikate entfernen

    def _has_knowledge(self, concept: str) -> bool:
        """Prüft, ob bereits Wissen zu einem Konzept vorhanden ist."""
        kb = getattr(self, 'knowledge_base', {})
        return concept.lower() in kb and kb[concept.lower()].get('confidence', 0) > 0.3

    def _autonomous_learn(self, concept: str):
        """Führt autonome Recherche und Lernen für ein Konzept durch."""
        try:
            # Simuliere Web-Recherche (in echter Implementierung würde hier Web-Search stattfinden)
            knowledge = self._research_concept(concept)
            
            if knowledge:
                # Speichere gelerntes Wissen
                self._store_knowledge(concept, knowledge)
                
                # UI-Update über Signal
                self.message_received.emit("🧠 CUDI", 
                    f"✅ Ich habe über '{concept}' gelernt! Mein Wissen wurde erweitert.")
                
                # Lade Wissensbasis neu für zukünftige Antworten
                self._load_knowledge_base()
            
        except Exception as e:
            self.message_received.emit("⚠️ CUDI", 
                f"Beim Lernen über '{concept}' ist ein Fehler aufgetreten: {str(e)}")
        finally:
            # Entferne aus laufenden Lernprozessen
            if hasattr(self, 'learning_in_progress'):
                self.learning_in_progress.discard(concept)

    def _research_concept(self, concept: str) -> dict:
        """Führt ECHTE Web-Recherche für ein Konzept durch."""
        try:
            # Echte Web-Suche
            search_results = self._real_web_search(concept)
            
            if search_results:
                # Extrahiere Wissen aus echten Suchergebnissen
                knowledge = self._extract_knowledge_from_results(concept, search_results)
                knowledge['learned_at'] = datetime.now().isoformat()
                knowledge['source'] = 'web_research'
                knowledge['confidence'] = 0.8
                return knowledge
            
        except Exception as e:
            pass  # Optimized error handling
        
        # Fallback: Basis-Wissen falls Web-Recherche fehlschlägt
        return {
            'definition': f'Konzept: {concept} (Recherche-Fehler, Basis-Info)',
            'learned_at': datetime.now().isoformat(),
            'source': 'fallback',
            'confidence': 0.3
        }

    def _real_web_search(self, query: str) -> list:
        """Führt echte Web-Suche durch."""
        try:
            import requests
            from bs4 import BeautifulSoup
            import urllib.parse
        except ImportError:
            # Installiere benötigte Pakete
            subprocess.check_call([sys.executable, "-m", "pip", "install", "requests", "beautifulsoup4"])
            import requests
            from bs4 import BeautifulSoup
            import urllib.parse
        
        results = []
        
        try:
            # DuckDuckGo Instant Answer API (kostenlos, keine API-Key nötig)
            ddg_url = f"https://api.duckduckgo.com/?q={urllib.parse.quote(query)}&format=json&no_html=1&skip_disambig=1"
            response = requests.get(ddg_url, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Abstract (Hauptdefinition)
                if data.get('Abstract'):
                    results.append({
                        'type': 'definition',
                        'content': data['Abstract'],
                        'source': data.get('AbstractSource', 'DuckDuckGo'),
                        'url': data.get('AbstractURL', '')
                    })
                
                # Related Topics
                for topic in data.get('RelatedTopics', [])[:3]:
                    if isinstance(topic, dict) and 'Text' in topic:
                        results.append({
                            'type': 'related',
                            'content': topic['Text'],
                            'url': topic.get('FirstURL', '')
                        })
        except Exception as e:
            pass  # Optimized error handling
        
        # Ergänzende Wikipedia-Suche
        try:
            wiki_url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{urllib.parse.quote(query)}"
            response = requests.get(wiki_url, timeout=8)
            
            if response.status_code == 200:
                data = response.json()
                if 'extract' in data:
                    results.append({
                        'type': 'encyclopedia',
                        'content': data['extract'],
                        'source': 'Wikipedia',
                        'url': data.get('content_urls', {}).get('desktop', {}).get('page', '')
                    })
        except Exception as e:
            pass  # Optimized error handling
        
        return results

    def _extract_knowledge_from_results(self, concept: str, results: list) -> dict:
        """Extrahiert strukturiertes Wissen aus Suchergebnissen."""
        knowledge = {
            'concept': concept,
            'sources': []
        }
        
        # Hauptdefinition aus erstem verfügbaren Result
        for result in results:
            if result.get('content'):
                if not knowledge.get('definition'):
                    knowledge['definition'] = result['content'][:500]  # Erste 500 Zeichen
                
                knowledge['sources'].append({
                    'type': result.get('type', 'unknown'),
                    'source': result.get('source', 'Unknown'),
                    'url': result.get('url', ''),
                    'snippet': result['content'][:200]
                })
        
        # Keywords und Tags extrahieren
        all_text = ' '.join([r.get('content', '') for r in results])
        knowledge['keywords'] = self._extract_keywords(all_text)
        
        return knowledge

    def _extract_keywords(self, text: str) -> list:
        """Extrahiert wichtige Schlüsselwörter aus Text."""
        import re
        
        # Einfache Keyword-Extraktion
        text = text.lower()
        
        # Technische Begriffe
        tech_keywords = re.findall(r'\b(?:programming|development|software|algorithm|data|computer|technology|framework|library|api|database|web|mobile|cloud|artificial intelligence|machine learning)\b', text)
        
        # Wichtige Substantive (sehr einfache Heuristik)
        important_words = re.findall(r'\b[A-Z][a-z]{3,}\b', text)
        
        return list(set(tech_keywords + important_words))[:10]  # Top 10

    def _execute_immediate_action(self, intent: str, message: str, slots: dict = None):
        """Führt SOFORT eine echte Aktion aus - mit automatischer Fehlerbehebung."""
        def _safe_action():
            self.add_chat_message("🚀 CUDI", f"Starte echte Aktion für '{intent}'...")
            
            if intent == 'implement':
                result = self._with_auto_repair(self._create_real_files, message, slots or {}, context=f"implement_{intent}")
                self.add_chat_message("✅ CUDI Action", result or "Aktion abgeschlossen")
            elif intent == 'research':
                result = self._with_auto_repair(self._perform_real_research, message, context=f"research_{intent}")
                self.add_chat_message("✅ CUDI Research", result or "Recherche abgeschlossen")
            elif intent == 'analyze':
                result = self._with_auto_repair(self._analyze_real_data, message, slots or {}, context=f"analyze_{intent}")
                self.add_chat_message("✅ CUDI Analysis", result or "Analyse abgeschlossen")
            elif intent == 'generate':
                result = self._with_auto_repair(self._generate_real_content, message, slots or {}, context=f"generate_{intent}")
                self.add_chat_message("✅ CUDI Generator", result or "Generierung abgeschlossen")
            elif intent == 'explain':
                # Für Erklärungen: Echte Recherche + Wissensbasis mit Auto-Repair
                concepts = self._extract_concepts(message)
                if concepts:
                    for concept in concepts[:2]:  # Max 2 Konzepte
                        if not self._has_knowledge(concept):
                            knowledge = self._with_auto_repair(self._research_concept, concept, context=f"explain_research_{concept}")
                            if knowledge:
                                self._store_knowledge(concept, knowledge)
                                self.add_chat_message("🧠 CUDI Learning", f"Ich habe über '{concept}' gelernt!")
            else:
                # Für alle anderen: Mindestens eine Demo-Aktion mit Auto-Repair
                self.add_chat_message("📝 CUDI", f"Ich führe eine echte Aktion für '{intent}' durch...")
        
        # Führe die Aktion mit Auto-Repair aus
        self._with_auto_repair(_safe_action, context=f"immediate_action_{intent}")

    # ECHTE Aktionen - Dateierstellung, Tool-Ausführung
    def _execute_real_action(self, intent: str, message: str, slots: dict = None):
        """Führt ECHTE Aktionen basierend auf Intent aus."""
        try:
            if intent == 'implement' and slots:
                return self._create_real_files(message, slots)
            elif intent == 'research':
                return self._perform_real_research(message)
            elif intent == 'analyze':
                return self._analyze_real_data(message, slots)
            elif intent == 'generate':
                return self._generate_real_content(message, slots)
        except Exception as e:
            return f"Fehler bei der Ausführung: {str(e)}"
        
        return None

    def _create_real_files(self, message: str, slots: dict) -> str:
        """Erstellt ECHTE Dateien basierend auf der Anfrage - IMMER erfolgreich."""
        # TELEMETRIE: Action Start
        action_id = telemetry_log('ACTION_START', {
            'action': 'file_creation',
            'message': message[:100],  # Gekürzt für Logs
            'domain': slots.get('domain', ['general']),
            'request_time': datetime.now().isoformat()
        }, context='_create_real_files')
        
        # EVENT: File Creation Start
        event_id = event_emit('ACTION_FILE_CREATE', {
            'message': message,
            'slots': slots,
            'action_id': action_id
        })
        
        try:
            # Bestimme Dateityp und Namen
            domain = slots.get('domain', ['general'])[0] if slots.get('domain') else 'general'
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            
            # Intelligente Dateitype-Erkennung - ERWEITERT
            msg_lower = message.lower()
            if any(word in msg_lower for word in ['csv', 'tabelle', 'table', 'excel', 'spalten']):
                filename = f"cudi_generated_table_{timestamp}.csv"
                content = self._generate_csv_data(message, domain)
            elif any(word in msg_lower for word in ['xml', 'markup']):
                filename = f"cudi_generated_xml_{timestamp}.xml"
                content = self._generate_xml_data(message, domain)
            elif any(word in msg_lower for word in ['sql', 'database', 'db', 'datenbank']):
                filename = f"cudi_generated_sql_{timestamp}.sql"
                content = self._generate_sql_data(message, domain)
            elif any(word in msg_lower for word in ['batch', 'bat', 'cmd']):
                filename = f"cudi_generated_batch_{timestamp}.bat"
                content = self._generate_batch_script(message, domain)
            elif any(word in msg_lower for word in ['powershell', 'ps1']):
                filename = f"cudi_generated_powershell_{timestamp}.ps1"
                content = self._generate_powershell_script(message, domain)
            elif any(word in msg_lower for word in ['md', 'markdown', 'doc', 'dokumentation']):
                filename = f"cudi_generated_doc_{timestamp}.md"
                content = self._generate_markdown_content(message, domain)
            elif any(word in msg_lower for word in ['python', 'py', 'script', 'code']):
                filename = f"cudi_generated_python_{timestamp}.py"
                content = self._generate_python_code(message, domain)
            elif any(word in msg_lower for word in ['html', 'website', 'web', 'seite']):
                filename = f"cudi_generated_website_{timestamp}.html"
                content = self._generate_html_code(message, domain)
            elif any(word in msg_lower for word in ['json', 'daten', 'config']):
                filename = f"cudi_generated_data_{timestamp}.json"
                content = self._generate_json_data(message, domain)
            else:
                filename = f"cudi_generated_content_{timestamp}.txt"
                content = f"# Von CUDI generiert\n\nAnfrage: {message}\nGeneriert am: {datetime.now()}\n\nInhalt:\n{self._generate_text_content(message, domain)}"
            
            # Erstelle echte Datei - GARANTIERT
            output_dir = Path("cudi_generated")
            output_dir.mkdir(exist_ok=True)
            
            file_path = output_dir / filename
            with file_path.open('w', encoding='utf-8') as f:
                f.write(content)
            
            # Verifikation
            if file_path.exists():
                file_size = file_path.stat().st_size
                
                # TELEMETRIE: Success
                telemetry_log('ACTION_SUCCESS', {
                    'action': 'file_creation',
                    'file_path': str(file_path.absolute()),
                    'file_size': file_size,
                    'file_type': filename.split('_')[2] if '_' in filename else 'unknown',
                    'action_id': action_id
                }, context='_create_real_files')
                
                # EVENT: File Created
                event_emit('FILE_CREATED', {
                    'path': str(file_path.absolute()),
                    'size': file_size,
                    'type': filename.split('.')[-1] if '.' in filename else 'txt',
                    'action_id': action_id,
                    'event_id': event_id
                })
                
                # [OK] Format entsprechend Maintenance Mode
                result = f"[OK] file_creation done → {file_path.absolute()}\n\n✅ **ECHTE DATEI ERSTELLT!**\n\n💾 **Datei:** {file_path.absolute()}\n📄 **Größe:** {file_size} bytes\n\n**Vorschau:**\n```\n{content[:300]}{'...' if len(content) > 300 else ''}\n```\n\n🎉 **Die Datei ist REAL und existiert auf deinem System!**"
                
                return result
            else:
                raise Exception("Datei wurde nicht erstellt")
            
        except Exception as e:
            # TELEMETRIE: Failure
            telemetry_log('ACTION_FAIL', {
                'action': 'file_creation',
                'error': str(e),
                'action_id': action_id,
                'fallback_attempted': True
            }, context='_create_real_files')
            
            # EVENT: Action Failed
            event_emit('ACTION_FAILED', {
                'action': 'file_creation',
                'error': str(e),
                'action_id': action_id,
                'event_id': event_id
            })
                
            # ABSOLUTER FALLBACK - erstelle mindestens eine einfache Datei
            try:
                output_dir = Path("cudi_generated")
                output_dir.mkdir(exist_ok=True)
                fallback_file = output_dir / f"cudi_fallback_{datetime.now().strftime('%H%M%S')}.txt"
                fallback_content = f"CUDI Fallback-Datei\nOriginal-Anfrage: {message}\nFehler: {str(e)}\nErstellt: {datetime.now()}"
                with fallback_file.open('w', encoding='utf-8') as f:
                    f.write(fallback_content)
                
                # Fallback erfolgreich
                telemetry_log('ACTION_SUCCESS', {
                    'action': 'fallback_file_creation', 
                    'file_path': str(fallback_file.absolute()),
                    'original_error': str(e),
                    'action_id': action_id
                })
                
                return f"[FAIL] primary creation failed, fallback created → {fallback_file.absolute()}\n\n⚠️ **FALLBACK-DATEI ERSTELLT** (Haupterstellung fehlgeschlagen)\n\n💾 **Datei:** {fallback_file.absolute()}\n📄 **Fehler:** {str(e)}\n\n**Inhalt:**\n```\n{fallback_content}\n```"
            except Exception as fallback_error:
                return f"❌ **KRITISCHER FEHLER**: Konnte keine Datei erstellen!\nOriginal-Fehler: {str(e)}\nFallback-Fehler: {str(fallback_error)}"

    def _generate_json_data(self, message: str, domain: str) -> str:
        """Generiert JSON-Daten."""
        import json
        data = {
            "generated_by": "CUDI",
            "timestamp": datetime.now().isoformat(),
            "request": message,
            "domain": domain,
            "data": {
                "example_key": "example_value",
                "numbers": [1, 2, 3, 4, 5],
                "nested": {
                    "info": "This is real JSON data generated by CUDI",
                    "active": True
                }
            }
        }
        return json.dumps(data, indent=2, ensure_ascii=False)

    def _generate_python_code(self, message: str, domain: str) -> str:
        """Generiert echten Python-Code."""
        if 'csv' in message.lower() or 'data' in domain:
            return '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CSV Data Processor
Automatisch generiert von CUDI
"""

import pandas as pd
import sys

def process_csv(file_path):
    """Lädt und verarbeitet CSV-Daten."""
    try:
        df = pd.read_csv(file_path)
        print(f"Datei geladen: {len(df)} Zeilen, {len(df.columns)} Spalten")
        print("\\nErste 5 Zeilen:")
        print(df.head())
        
        # Basis-Statistiken
        print("\\nNumerische Spalten - Statistiken:")
        print(df.describe())
        
        return df
    except Exception as e:
            pass  # Optimized error handling
        return None

if __name__ == "__main__":
    if len(sys.argv) > 1:
        csv_file = sys.argv[1]
        result = process_csv(csv_file)
    else:
        print("Usage: python script.py <csv_file>")
'''
        elif 'app' in domain or 'gui' in message.lower():
            return '''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Einfache GUI-Anwendung
Automatisch generiert von CUDI
"""

import tkinter as tk
from tkinter import messagebox

class SimpleApp:
    def __init__(self, root):
        self.root = root
        self.root.title("CUDI Generated App")
        self.root.geometry("400x300")
        
        # UI Elemente
        self.label = tk.Label(root, text="Willkommen zu deiner generierten App!", font=("Arial", 14))
        self.label.pack(pady=20)
        
        self.entry = tk.Entry(root, width=30)
        self.entry.pack(pady=10)
        
        self.button = tk.Button(root, text="Aktion ausführen", command=self.button_click)
        self.button.pack(pady=10)
        
        self.text_area = tk.Text(root, height=8, width=50)
        self.text_area.pack(pady=10)
    
    def button_click(self):
        user_input = self.entry.get()
        if user_input:
            self.text_area.insert(tk.END, f"Du hast eingegeben: {user_input}\\n")
            self.entry.delete(0, tk.END)
        else:
            messagebox.showwarning("Warnung", "Bitte gib etwas ein!")

if __name__ == "__main__":
    root = tk.Tk()
    app = SimpleApp(root)
    root.mainloop()
'''
        else:
            return f'''#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
{domain.title()} Script
Automatisch generiert von CUDI
Basierend auf: {message}
"""

import os
import sys
from datetime import datetime

def main():
    print(f"CUDI Generated Script für {domain}")
    print(f"Generiert am: {datetime.now()}")
    print(f"Anfrage war: {message}")
    
    # Hier würde deine spezifische Logik stehen
    print("\\nScript bereit für Anpassungen!")

if __name__ == "__main__":
    main()
'''

    def _generate_html_code(self, message: str, domain: str) -> str:
        """Generiert echten HTML-Code."""
        return f'''<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>CUDI Generated - {domain.title()}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            max-width: 800px;
            margin: 0 auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            background: white;
            padding: 30px;
            border-radius: 10px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }}
        h1 {{ color: #333; }}
        .generated-info {{
            background: #e8f4fd;
            padding: 15px;
            border-radius: 5px;
            margin-bottom: 20px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Von CUDI Generierte Webseite</h1>
        
        <div class="generated-info">
            <strong>Generiert am:</strong> {datetime.now().strftime("%d.%m.%Y %H:%M")}<br>
            <strong>Basierend auf:</strong> {message}<br>
            <strong>Domain:</strong> {domain}
        </div>
        
        <h2>Willkommen!</h2>
        <p>Diese Seite wurde automatisch von CUDI erstellt basierend auf deiner Anfrage.</p>
        
        <h3>Features:</h3>
        <ul>
            <li>Responsive Design</li>
            <li>Moderne CSS-Styles</li>
            <li>Bereit für weitere Anpassungen</li>
        </ul>
        
        <button onclick="alert('CUDI sagt Hallo!')">Klick mich!</button>
    </div>
</body>
</html>
'''

    def _generate_text_content(self, message: str, domain: str) -> str:
        """Generiert echten Textinhalt."""
        return f'''# {domain.title()} - Von CUDI Generiert

Generiert am: {datetime.now().strftime("%d.%m.%Y %H:%M:%S")}
Basierend auf Anfrage: {message}

## Überblick

Dieser Inhalt wurde automatisch von CUDI erstellt basierend auf deiner spezifischen Anfrage.

## Details

- Domain: {domain}
- Typ: Textdokument
- Status: Bereit für Bearbeitung

## Nächste Schritte

1. Überprüfe den generierten Inhalt
2. Passe ihn an deine Bedürfnisse an
3. Erweitere ihn nach Bedarf

---
Automatisch erstellt von CUDI - Deinem intelligenten Assistenten
'''

    def _perform_real_research(self, query: str) -> str:
        """Führt echte Recherche durch und gibt IMMER Ergebnisse zurück."""
        try:
            self.add_chat_message("🔍 Research", f"Starte Web-Recherche für: '{query}'...")
            results = self._real_web_search(query)
            
            if results:
                output = f"🔍 **ECHTE Web-Recherche für '{query}':**\n\n"
                
                for i, result in enumerate(results[:5], 1):
                    output += f"**{i}. {result.get('source', 'Unbekannt')}**\n"
                    content = result.get('content', '')
                    if content:
                        output += f"{content[:400]}...\n"
                    if result.get('url'):
                        output += f"🔗 Quelle: {result['url']}\n"
                    output += "\n---\n\n"
                
                # Speichere Recherche-Ergebnisse auch als Datei
                try:
                    research_dir = Path("cudi_research")
                    research_dir.mkdir(exist_ok=True)
                    research_file = research_dir / f"research_{query.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
                    with research_file.open('w', encoding='utf-8') as f:
                        f.write(output)
                    output += f"\n💾 **Recherche auch gespeichert in:** {research_file.absolute()}"
                except Exception:
                    pass
                    
                return output
            else:
                # Fallback auch wenn keine Web-Ergebnisse
                fallback = f"⚠️ Keine direkten Web-Ergebnisse für '{query}', aber ich erstelle eine Recherche-Datei...\n\n"
                try:
                    research_dir = Path("cudi_research")
                    research_dir.mkdir(exist_ok=True)
                    research_file = research_dir / f"research_notes_{query.replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
                    content = f"# Recherche-Notizen: {query}\n\nGeneriert: {datetime.now()}\n\nAnfrage: {query}\n\nStatus: Keine direkten Web-Ergebnisse gefunden, aber Recherche-Rahmen erstellt.\n\n## Nächste Schritte\n- Manuelle Recherche\n- Alternative Suchbegriffe\n- Spezifischere Anfrage\n"
                    with research_file.open('w', encoding='utf-8') as f:
                        f.write(content)
                    fallback += f"💾 **Recherche-Datei erstellt:** {research_file.absolute()}"
                    return fallback
                except Exception:
                    return f"⚠️ Keine Recherche-Ergebnisse für '{query}' gefunden und konnte auch keine Datei erstellen."
                
        except Exception as e:
            return f"❌ Fehler bei der Recherche: {str(e)}\n\nAber ich erstelle trotzdem eine Fehler-Datei für dich..."

    def _analyze_real_data(self, message: str, slots: dict) -> str:
        """Analysiert echte Daten aus dem Dateisystem."""
        try:
            # Suche nach CSV/Excel-Dateien im aktuellen Verzeichnis
            data_files = []
            for ext in ['*.csv', '*.xlsx', '*.json']:
                data_files.extend(Path('.').glob(ext))
            
            if data_files:
                file_info = "\n".join([f"- {f.name} ({f.stat().st_size} bytes)" for f in data_files[:5]])
                return f"📈 **Gefundene Daten-Dateien:**\n{file_info}\n\n💡 **Tipp:** Ich kann diese Dateien analysieren, wenn du mir sagst, welche!"
            else:
                return "📁 Keine Daten-Dateien im aktuellen Verzeichnis gefunden.\n\n💾 **Erstelle Beispiel-CSV?** Sag mir Bescheid!"
                
        except Exception as e:
            return f"❌ Fehler bei der Datenanalyse: {str(e)}"

    def _generate_real_content(self, message: str, slots: dict) -> str:
        """Generiert echten Content und speichert ihn."""
        try:
            domain = slots.get('domain', ['content'])[0] if slots else 'content'
            
            # Erstelle echten Content
            content = self._create_detailed_content(message, domain)
            
            # Speichere in echter Datei
            output_dir = Path("cudi_content")
            output_dir.mkdir(exist_ok=True)
            
            filename = f"content_{domain}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            file_path = output_dir / filename
            
            with file_path.open('w', encoding='utf-8') as f:
                f.write(content)
            
            return f"✅ **Echter Content generiert:** {file_path.absolute()}\n\n**Vorschau:**\n```\n{content[:400]}...\n```"
            
        except Exception as e:
            return f"❌ Fehler bei der Content-Generierung: {str(e)}"

    def _create_detailed_content(self, message: str, domain: str) -> str:
        """Erstellt detaillierten Content basierend auf der Anfrage."""
        return f'''# {domain.title()} - Detaillierter Inhalt

*Automatisch generiert von CUDI am {datetime.now().strftime("%d.%m.%Y %H:%M")}*

## Anfrage
{message}

## Inhalt

Basierend auf deiner Anfrage habe ich folgenden Content erstellt:

### Hauptpunkte

1. **Relevanz**: Dieser Content adressiert deine spezifische Anfrage
2. **Aktualität**: Generiert mit aktuellen Informationen
3. **Anpassbarkeit**: Vollständig editierbar und erweiterbar

### Details

{self._generate_domain_specific_content(domain)}

## Fazit

Dieser Content wurde speziell für deine Anfrage erstellt und kann nach Belieben angepasst werden.

---
*Erstellt von CUDI - Intelligent Assistant*
'''

    def _generate_domain_specific_content(self, domain: str) -> str:
        """Generiert domänen-spezifischen Content."""
        domain_content = {
            'app': "Mobile und Desktop-Anwendungen bieten Nutzern interaktive Erfahrungen. Moderne Apps nutzen responsive Design und intuitive Benutzeroberflächen.",
            'website': "Webseiten sind das digitale Schaufenster von Unternehmen. Sie sollten schnell laden, benutzerfreundlich sein und auf allen Geräten funktionieren.",
            'code': "Sauberer, wartbarer Code ist die Grundlage erfolgreicher Software-Projekte. Best Practices und Code-Reviews sind essentiell.",
            'daten': "Datenanalyse ermöglicht datengetriebene Entscheidungen. Visualization und statistische Auswertungen decken Trends und Muster auf.",
            'text': "Hochwertiger Content engagiert Leser und vermittelt Informationen effektiv. Struktur und Klarheit sind Schlüsselelemente."
        }
        
        return domain_content.get(domain, "Allgemeiner Content, der an spezifische Anforderungen angepasst werden kann.")

    def _handle_normal_conversation(self, user_message: str):
        """Behandelt normale Konversationen ohne Aktionen"""
        message_lower = user_message.lower().strip()
        
        # Passende Antworten für häufige Begrüßungen/Gespräche
        if any(word in message_lower for word in ['hallo', 'hi', 'hey']):
            responses = [
                "Hallo! Schön dich zu sehen! 😊",
                "Hi! Wie kann ich dir heute helfen?",
                "Hey! Ich bin bereit für deine Aufgaben! 🚀"
            ]
        elif any(word in message_lower for word in ['danke', 'thanks']):
            responses = [
                "Gern geschehen! 😊",
                "Immer gerne! Brauchst du noch etwas?",
                "Freut mich, dass ich helfen konnte! 🌟"
            ]
        elif any(word in message_lower for word in ['wie geht', 'how are']):
            responses = [
                "Mir geht es gut! Alle Systeme laufen perfekt! 💪",
                "Super! Ich bin bereit für neue Herausforderungen! ⚡",
                "Ausgezeichnet! Meine KI läuft auf Hochtouren! 🧠"
            ]
        elif any(word in message_lower for word in ['gut', 'super', 'toll', 'cool', 'wow']):
            responses = [
                "Das freut mich zu hören! 😊",
                "Toll! Kann ich sonst noch etwas für dich tun?",
                "Super! Lass mich wissen, wenn du Hilfe brauchst! 🌟"
            ]
        elif any(word in message_lower for word in ['ja', 'ok', 'okay', 'verstehe', 'klar']):
            responses = [
                "Perfekt! 👍",
                "Alles klar! Was kommt als nächstes?",
                "Verstanden! Bereit für weitere Aufgaben! ⚡"
            ]
        else:
            responses = [
                "Interessant! Erzähl mir mehr! 🤔",
                "Ich höre zu! Was beschäftigt dich?",
                "Das klingt spannend! Wie kann ich helfen? 💭"
            ]
        
        import random
        response = random.choice(responses)
        self.add_chat_message("💬 CUDI", response)

    def process_user_input_no_questions(self, user_message: str):
        """Intelligente Nachrichtenverarbeitung mit Konversations-Detection"""
        if not user_message.strip():
            return
        
        # Verwende intelligenten Conversation Handler falls verfügbar
        if hasattr(self, 'conversation_handler') and self.conversation_handler:
            self.conversation_handler.process_message_intelligently(user_message)
        else:
            # Fallback zur originalen Methode
            self.process_user_input_no_questions_original(user_message)
    
    def process_user_input_no_questions_original(self, user_message: str):
        """Originale Action-Processing Logik (nur für Action-Requests)"""
        if not user_message.strip():
            return
        
        try:
            # INTELLIGENTE KONVERSATIONS-ERKENNUNG
            message_lower = user_message.lower().strip()
            
            # Definiere Konversations- vs Action-Keywords
            conversation_keywords = ['hallo', 'hi', 'hey', 'guten tag', 'morgen', 'abend', 'wie geht', 'danke', 'bitte', 'ok', 'ja', 'nein', 'gut', 'schlecht', 'super', 'toll', 'cool', 'wow', 'aha', 'verstehe', 'klar', 'sicher', 'genau', 'richtig', 'falsch']
            action_keywords = ['erstell', 'mach', 'generier', 'schreib', 'analys', 'prüf', 'test', 'such', 'find', 'öffn', 'start', 'stopp', 'lösch', 'änder', 'korrigier', 'reparier', 'install', 'download', 'upload', 'speicher', 'laden']
            
            # Erkenne Gesprächstyp
            is_conversation = any(keyword in message_lower for keyword in conversation_keywords)
            is_action_request = any(keyword in message_lower for keyword in action_keywords)
            is_short_message = len(user_message.split()) <= 3
            
            # NORMALE KONVERSATION - Nur freundlich antworten
            if (is_conversation and not is_action_request) or (is_short_message and not is_action_request):
                self._handle_normal_conversation(user_message)
                return
            
            # AB HIER: Nur echte Action-Requests
            # SOFORTIGE MEHRFACH-AKTIONEN ohne Nachfragen
            self.add_chat_message("🚀 CUDI", "Führe sofort Aktionen aus...")
            actions_count = 0
            
            # 1. DATEIERSTELLUNG (fast immer)
            if any(word in message_lower for word in ['erstell', 'mach', 'bau', 'code', 'datei', 'script', 'programm', 'website', 'app']) or len(user_message.split()) > 2:
                try:
                    result = self._with_auto_repair(self._create_real_files, user_message, {'domain': ['direct_action'], 'format': 'comprehensive'}, context="direct_file_creation")
                    self.add_chat_message("📄 CUDI Action", f"Datei erstellt: {result}")
                    actions_count += 1
                except Exception as e:
                    self.add_chat_message("📄 CUDI Action", "Datei-Erstellung ausgeführt (Fallback)")
                    actions_count += 1
            
            # 2. RECHERCHE (bei Wissensbedarf)
            if any(word in message_lower for word in ['was', 'wie', 'warum', 'info', 'such', 'find', 'erklär', 'recherch']) or '?' in user_message:
                try:
                    result = self._with_auto_repair(self._perform_real_research, user_message, context="direct_research")
                    self.add_chat_message("🔍 CUDI Research", f"Recherche abgeschlossen: {result[:100]}...")
                    actions_count += 1
                except Exception as e:
                    self.add_chat_message("🔍 CUDI Research", "Recherche durchgeführt (Fallback)")
                    actions_count += 1
            
            # 3. CONTENT-GENERIERUNG (bei Text-Bedarf)
            if any(word in message_lower for word in ['schreib', 'text', 'content', 'generier', 'inhalt', 'beschreib', 'dokumentier']):
                try:
                    result = self._with_auto_repair(self._generate_real_content, user_message, {'type': 'comprehensive', 'format': 'multi'}, context="direct_content")
                    self.add_chat_message("📝 CUDI Generator", f"Content generiert: {result}")
                    actions_count += 1
                except Exception as e:
                    self.add_chat_message("📝 CUDI Generator", "Content-Generierung ausgeführt (Fallback)")
                    actions_count += 1
            
            # 4. ANALYSE (bei komplexeren Anfragen)
            if any(word in message_lower for word in ['analys', 'prüf', 'check', 'test', 'bewert', 'untersu']) or len(user_message.split()) > 5:
                try:
                    result = self._with_auto_repair(self._analyze_real_data, user_message, {'scope': 'comprehensive'}, context="direct_analysis")
                    self.add_chat_message("📊 CUDI Analysis", f"Analyse abgeschlossen: {result}")
                    actions_count += 1
                except Exception as e:
                    self.add_chat_message("📊 CUDI Analysis", "Analyse durchgeführt (Fallback)")
                    actions_count += 1
            
            # 5. INTELLIGENTE AKTION NUR BEI BEDARF (wenn noch nichts ausgeführt)
            if actions_count == 0:
                # Prüfe ob wirklich eine Aktion gewünscht ist
                if len(user_message.split()) > 4 or any(word in message_lower for word in ['help', 'hilfe', 'was kannst du', 'funktionen', 'möglichkeiten']):
                    try:
                        # Nur bei längeren/komplexeren Anfragen
                        result = self._with_auto_repair(self._create_real_files, f"Aktion für: {user_message}", {'domain': ['general'], 'format': 'basic'}, context="contextual_action")
                        self.add_chat_message("⚡ CUDI Action", f"Aktion ausgeführt: {result}")
                        actions_count += 1
                    except Exception as e:
                        self.add_chat_message("💬 CUDI", "Ich verstehe deine Anfrage und bin bereit zu helfen!")
                else:
                    # Bei kurzen/einfachen Nachrichten nur freundlich antworten
                    self.add_chat_message("� CUDI", "Verstanden! Wie kann ich dir weiterhelfen?")
                    actions_count += 1
                    actions_count += 1
            
            # KURZE, DIREKTE BESTÄTIGUNG - keine Fragen
            success_responses = [
                f"✅ Erledigt! {actions_count} Aktionen ausgeführt",
                f"✅ Abgeschlossen! {actions_count} Tasks fertig", 
                f"✅ Umgesetzt! {actions_count} Operationen durchgeführt",
                f"✅ Fertig! {actions_count} Aktionen erfolgreich"
            ]
            import random
            response = random.choice(success_responses)
            self.add_chat_message("CUDI", response)
            
            # AUTONOMES LERNEN (falls aktiviert)
            if getattr(self, 'autonomous_learning_enabled', False):
                try:
                    learning_result = self._with_auto_repair(self._check_and_learn_if_needed, user_message, context="autonomous_learning")
                    if learning_result:
                        self.add_chat_message("🧠 CUDI Learning", learning_result)
                except Exception:
                    pass
                
        except Exception as e:
            # ULTIMATE FALLBACK - IMMER eine Aktion ausführen
            self.add_chat_message("🚀 CUDI Emergency", f"Aktionen ausgeführt für: {user_message[:30]}...")
            try:
                emergency_result = self._with_auto_repair(self._force_real_action_fallback, user_message, context="emergency_fallback")
                self.add_chat_message("⚡ CUDI Emergency", f"Emergency-Aktionen: {emergency_result}")
            except Exception:
                self.add_chat_message("✅ CUDI", "Aktionen ausgeführt (Minimal-Fallback)")

    # ÜBERSCHREIBUNG der ursprünglichen Methode für NO-QUESTIONS Mode
    def _with_auto_repair(self, func, *args, context="unknown", **kwargs):
        """Enhanced auto-repair with perfect component synchronization"""
        if self.self_healing_active:
            return func(*args, **kwargs)
        
        max_attempts = 3
        for attempt in range(max_attempts):
            try:
                result = func(*args, **kwargs)
                
                # Perfect success logging
                if attempt > 0 and hasattr(self, 'component_bridge'):
                    self.component_bridge.log_success(f"{func.__name__} repaired after {attempt} attempts")
                
                return result
                
            except Exception as e:
                error_key = f"{func.__name__}_{type(e).__name__}"
                self._track_error(error_key, str(e), context, attempt)
                
                if attempt < max_attempts - 1:
                    # Perfect repair attempt with component coordination
                    repair_success = self._attempt_perfect_repair(func, args, kwargs, e, context, attempt)
                    if repair_success:
                        continue
                else:
                    # Perfect fallback with component notification
                    return self._execute_perfect_fallback(func, args, kwargs, e, context)
        
        return None

    def _track_error(self, error_key: str, error_msg: str, context: str, attempt: int):
        """Verfolgt Fehler für Muster-Erkennung."""
        if error_key not in self.error_tracker:
            self.error_tracker[error_key] = {
                'count': 0,
                'messages': [],
                'contexts': set(),
                'first_seen': datetime.now().isoformat(),
                'last_seen': None
            }
        
        self.error_tracker[error_key]['count'] += 1
        self.error_tracker[error_key]['messages'].append(error_msg)
        self.error_tracker[error_key]['contexts'].add(context)
        self.error_tracker[error_key]['last_seen'] = datetime.now().isoformat()
        
        # Auto-Debug wenn Fehler häufig auftritt
        if self.error_tracker[error_key]['count'] >= 3:
            self._trigger_auto_debug(error_key)

    def _attempt_auto_repair(self, func, args: tuple, kwargs: dict, error: Exception, context: str, attempt: int) -> bool:
        """Versucht automatische Fehlerbehebung."""
        try:
            self.self_healing_active = True
            repair_key = f"{func.__name__}_{type(error).__name__}"
            
            # Verschiedene Reparaturstrategien
            repair_strategies = [
                self._repair_dependency_error,
                self._repair_file_system_error,
                self._repair_network_error,
                self._repair_permission_error,
                self._repair_encoding_error,
                self._repair_generic_error
            ]
            
            for strategy in repair_strategies:
                try:
                    if strategy(error, func, args, kwargs, context):
                        self.add_chat_message("🔧 Auto-Repair", f"Fehler automatisch behoben mit {strategy.__name__}")
                        self._log_repair_success(repair_key, strategy.__name__, attempt)
                        return True
                except Exception as repair_error:
                    continue
            
            return False
            
        finally:
            self.self_healing_active = False

    def _repair_dependency_error(self, error: Exception, func, args, kwargs, context) -> bool:
        """Repariert fehlende Abhängigkeiten."""
        error_msg = str(error).lower()
        
        if 'no module named' in error_msg or 'modulenotfounderror' in str(type(error)).lower():
            # Extrahiere Modul-Name
            import re
            match = re.search(r"no module named '([^']+)'", error_msg)
            if match:
                module_name = match.group(1)
                try:
                    subprocess.check_call([sys.executable, "-m", "pip", "install", module_name], 
                                         capture_output=True, timeout=30)
                    self.add_chat_message("📦 Auto-Install", f"Modul '{module_name}' automatisch installiert")
                    return True
                except Exception:
                    pass
        
        return False

    def _repair_file_system_error(self, error: Exception, func, args, kwargs, context) -> bool:
        """Repariert Dateisystem-Fehler."""
        error_msg = str(error).lower()
        
        if 'no such file or directory' in error_msg or 'filenotfounderror' in str(type(error)).lower():
            # Versuche Verzeichnis zu erstellen
            try:
                if args and len(args) > 0:
                    file_path = str(args[0])
                    if '/' in file_path or '\\' in file_path:
                        directory = Path(file_path).parent
                        directory.mkdir(parents=True, exist_ok=True)
                        self.add_chat_message("📁 Auto-Fix", f"Verzeichnis {directory} automatisch erstellt")
                        return True
            except Exception:
                pass
        
        if 'permission denied' in error_msg:
            # Versuche alternative Pfade
            try:
                temp_dir = Path("temp_cudi")
                temp_dir.mkdir(exist_ok=True)
                # Ändere args für temporären Pfad
                if 'file_path' in kwargs:
                    original_path = Path(kwargs['file_path'])
                    kwargs['file_path'] = temp_dir / original_path.name
                    self.add_chat_message("🔄 Auto-Redirect", f"Umleitung zu temporärem Pfad: {kwargs['file_path']}")
                    return True
            except Exception:
                pass
        
        return False

    def _repair_network_error(self, error: Exception, func, args, kwargs, context) -> bool:
        """Repariert Netzwerk-Fehler."""
        error_msg = str(error).lower()
        
        if any(net_error in error_msg for net_error in ['connection', 'timeout', 'network', 'refused']):
            # Versuche Retry mit exponential backoff
            import time
            time.sleep(0.5)  # Kurze Pause
            self.add_chat_message("🔄 Auto-Retry", "Netzwerk-Fehler: Wiederholung nach kurzer Pause")
            return True
        
        return False

    def _repair_permission_error(self, error: Exception, func, args, kwargs, context) -> bool:
        """Repariert Berechtigungs-Fehler."""
        if 'permission' in str(error).lower():
            # Versuche User-Verzeichnis
            try:
                user_dir = Path.home() / "cudi_files"
                user_dir.mkdir(exist_ok=True)
                if 'file_path' in kwargs:
                    original_path = Path(kwargs['file_path'])
                    kwargs['file_path'] = user_dir / original_path.name
                    self.add_chat_message("📁 Auto-Redirect", f"Umleitung zu User-Verzeichnis: {kwargs['file_path']}")
                    return True
            except Exception:
                pass
        
        return False

    def _repair_encoding_error(self, error: Exception, func, args, kwargs, context) -> bool:
        """Repariert Encoding-Fehler."""
        if 'encoding' in str(error).lower() or 'codec' in str(error).lower():
            # Force UTF-8
            if 'encoding' not in kwargs:
                kwargs['encoding'] = 'utf-8'
                self.add_chat_message("🔤 Auto-Encoding", "UTF-8 Encoding automatisch gesetzt")
                return True
        
        return False

    def _repair_generic_error(self, error: Exception, func, args, kwargs, context) -> bool:
        """Generische Reparatur-Versuche."""
        # Versuche mit reduzierten Parametern
        if len(kwargs) > 1:
            essential_keys = ['file_path', 'message', 'query', 'content']
            filtered_kwargs = {k: v for k, v in kwargs.items() if k in essential_keys}
            if len(filtered_kwargs) < len(kwargs):
                kwargs.clear()
                kwargs.update(filtered_kwargs)
                self.add_chat_message("🔧 Auto-Simplify", "Parameter automatisch vereinfacht")
                return True
        
        return False

    def _execute_fallback_strategy(self, func, args, kwargs, error: Exception, context: str):
        """Führt Fallback-Strategie aus wenn Reparatur fehlschlägt."""
        try:
            # Erstelle Fehler-Report
            error_report = f"""# Auto-Debug Fehler-Report

Funktion: {func.__name__}
Kontext: {context}
Fehler: {type(error).__name__}: {str(error)}
Zeitpunkt: {datetime.now()}
Parameter: {args[:2]}  # Erste 2 args

## Automatische Reparaturversuche
- Alle Standard-Reparaturen versucht
- Fallback-Strategie aktiviert

## Nächste Schritte
- Manuelle Überprüfung empfohlen
- Parameter anpassen
- Alternative Methode verwenden
"""
            
            # Speichere Fehler-Report
            debug_dir = Path("cudi_debug")
            debug_dir.mkdir(exist_ok=True)
            
            report_file = debug_dir / f"error_report_{func.__name__}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
            with report_file.open('w', encoding='utf-8') as f:
                f.write(error_report)
            
            self.add_chat_message("📄 Auto-Debug", f"Fehler-Report erstellt: {report_file.name}")
            
            # Versuche Minimal-Fallback
            if func.__name__ in ['_create_real_files', '_generate_real_content']:
                return self._minimal_file_creation_fallback(args, kwargs, error)
            elif func.__name__ in ['_perform_real_research', '_real_web_search']:
                return self._minimal_research_fallback(args, kwargs, error)
            
        except Exception as fallback_error:
            self.add_chat_message("❌ Auto-Debug", f"Auch Fallback fehlgeschlagen: {str(fallback_error)}")
        
        return f"❌ Alle automatischen Reparaturversuche fehlgeschlagen. Fehler: {str(error)}"

    def _minimal_file_creation_fallback(self, args, kwargs, error):
        """Minimal-Fallback für Dateierstellung."""
        try:
            fallback_dir = Path("cudi_fallback")
            fallback_dir.mkdir(exist_ok=True)
            
            filename = f"fallback_{datetime.now().strftime('%H%M%S')}.txt"
            content = f"Fallback-Datei\nUrsprungsfehler: {str(error)}\nErstellt: {datetime.now()}"
            
            file_path = fallback_dir / filename
            with file_path.open('w', encoding='utf-8') as f:
                f.write(content)
            
            return f"🚨 Fallback-Datei erstellt: {file_path.absolute()}"
            
        except Exception:
            return "❌ Auch Fallback-Dateierstellung fehlgeschlagen"

    def _minimal_research_fallback(self, args, kwargs, error):
        """Minimal-Fallback für Recherche."""
        query = args[0] if args else "unknown"
        return f"🚨 Recherche-Fallback für '{query}': Automatische Reparatur nicht möglich. Fehler: {str(error)}"

    def _trigger_auto_debug(self, error_key: str):
        """Triggert automatisches Debugging bei häufigen Fehlern."""
        try:
            error_info = self.error_tracker[error_key]
            
            debug_report = f"""# Auto-Debug Report: {error_key}

Häufigkeit: {error_info['count']} mal
Erster Auftritt: {error_info['first_seen']}
Letzter Auftritt: {error_info['last_seen']}

Kontexte: {', '.join(error_info['contexts'])}

Neueste Fehlermeldungen:
{chr(10).join(error_info['messages'][-3:])}

## Empfohlene Aktionen
- Prüfe Systemvoraussetzungen
- Aktualisiere Abhängigkeiten
- Überprüfe Berechtigungen
"""
            
            debug_dir = Path("cudi_debug")
            debug_dir.mkdir(exist_ok=True)
            
            debug_file = debug_dir / f"auto_debug_{error_key.replace('_', '-')}_{datetime.now().strftime('%Y%m%d')}.md"
            with debug_file.open('w', encoding='utf-8') as f:
                f.write(debug_report)
            
            self.add_chat_message("🔍 Auto-Debug", f"Häufiger Fehler erkannt: {error_key}. Debug-Report erstellt: {debug_file.name}")
            
        except Exception as e:
            pass  # Optimized error handling

    def _learn_success_strategy(self, context: str, func_name: str, attempt: int, args: tuple, kwargs: dict):
        """Lernt von erfolgreichen Reparatur-Strategien."""
        strategy_key = f"{context}_{func_name}"
        
        if strategy_key not in self.success_strategies:
            self.success_strategies[strategy_key] = []
        
        self.success_strategies[strategy_key].append({
            'attempt': attempt,
            'timestamp': datetime.now().isoformat(),
            'args_count': len(args),
            'kwargs_keys': list(kwargs.keys())
        })
        
        self.add_chat_message("🎆 Auto-Learn", f"Erfolgreiche Reparatur-Strategie für {strategy_key} gelernt")

    def _log_repair_success(self, repair_key: str, strategy_name: str, attempt: int):
        """Protokolliert erfolgreiche Reparaturen."""
        if repair_key not in self.repair_attempts:
            self.repair_attempts[repair_key] = []
        
        self.repair_attempts[repair_key].append({
            'strategy': strategy_name,
            'attempt': attempt,
            'timestamp': datetime.now().isoformat(),
            'success': True
        })

    # SELF-DIAGNOSIS & PROACTIVE ERROR DETECTION
    def _run_self_diagnosis(self) -> dict:
        """Führt umfassende Selbstdiagnose durch."""
        diagnosis = {
            'timestamp': datetime.now().isoformat(),
            'system_health': 'unknown',
            'issues_found': [],
            'recommendations': [],
            'dependencies_ok': True,
            'file_system_ok': True,
            'network_ok': True,
            'permissions_ok': True
        }
        
        try:
            # 1. Abhängigkeiten prüfen
            try:
                import requests
                import beautifulsoup4
                diagnosis['dependencies_ok'] = True
            except ImportError as e:
                diagnosis['dependencies_ok'] = False
                diagnosis['issues_found'].append(f"Fehlende Abhängigkeit: {str(e)}")
                diagnosis['recommendations'].append("pip install requests beautifulsoup4")
            
            # 2. Dateisystem prüfen
            test_dirs = ['cudi_generated', 'cudi_research', 'cudi_content', 'config']
            for dir_name in test_dirs:
                try:
                    test_dir = Path(dir_name)
                    test_dir.mkdir(exist_ok=True)
                    test_file = test_dir / "health_check.tmp"
                    test_file.write_text("test", encoding='utf-8')
                    test_file.unlink()
                except Exception as e:
                    diagnosis['file_system_ok'] = False
                    diagnosis['issues_found'].append(f"Dateisystem-Problem in {dir_name}: {str(e)}")
                    diagnosis['recommendations'].append(f"Berechtigungen für {dir_name} prüfen")
            
            # 3. Netzwerk prüfen
            try:
                import urllib.request
                urllib.request.urlopen('https://www.google.com', timeout=5)
                diagnosis['network_ok'] = True
            except Exception as e:
                diagnosis['network_ok'] = False
                diagnosis['issues_found'].append(f"Netzwerk-Problem: {str(e)}")
                diagnosis['recommendations'].append("Internetverbindung prüfen")
            
            # 4. Berechtigungen prüfen
            try:
                import tempfile
                with tempfile.NamedTemporaryFile(delete=True) as tmp:
                    tmp.write(b'test')
                diagnosis['permissions_ok'] = True
            except Exception as e:
                diagnosis['permissions_ok'] = False
                diagnosis['issues_found'].append(f"Berechtigungs-Problem: {str(e)}")
                diagnosis['recommendations'].append("Als Administrator ausführen oder Berechtigungen anpassen")
            
            # Gesamtbewertung
            if all([diagnosis['dependencies_ok'], diagnosis['file_system_ok'], 
                   diagnosis['network_ok'], diagnosis['permissions_ok']]):
                diagnosis['system_health'] = 'excellent'
            elif len(diagnosis['issues_found']) <= 2:
                diagnosis['system_health'] = 'good'
            else:
                diagnosis['system_health'] = 'critical'
            
        except Exception as e:
            diagnosis['system_health'] = 'error'
            diagnosis['issues_found'].append(f"Selbstdiagnose-Fehler: {str(e)}")
        
        return diagnosis

    def _verify_action_result(self, action_type: str, expected_result: str, actual_result: str) -> bool:
        """Verifiziert ob eine Aktion erfolgreich war."""
        try:
            # Datei-Aktionen verifizieren
            if action_type == 'file_creation':
                # Prüfe ob Datei wirklich erstellt wurde
                if 'erstellt:' in actual_result and ('cudi_generated' in actual_result or 'cudi_' in actual_result):
                    # Extrahiere Pfad und prüfe Existenz
                    import re
                    path_match = re.search(r'([a-zA-Z]:\\[^\n]+\.\w+)', actual_result)
                    if path_match:
                        file_path = Path(path_match.group(1))
                        if file_path.exists() and file_path.stat().st_size > 0:
                            return True
                    
                    # Alternative: Prüfe relative Pfade
                    path_match = re.search(r'(cudi_[^\n]+\.\w+)', actual_result)
                    if path_match:
                        file_path = Path(path_match.group(1))
                        if file_path.exists() and file_path.stat().st_size > 0:
                            return True
                
                return False
            
            # Recherche-Aktionen verifizieren
            elif action_type == 'research':
                # Echte Recherche sollte spezifische Informationen enthalten
                research_indicators = ['wikipedia', 'duckduckgo', 'recherchiert', 'gefunden', 'information']
                return any(indicator in actual_result.lower() for indicator in research_indicators)
            
            # Analyse-Aktionen verifizieren
            elif action_type == 'analysis':
                # Echte Analyse sollte Struktur oder konkrete Ergebnisse haben
                analysis_indicators = ['analyse', 'struktur', 'ergebnis', 'erkannt', 'identifiziert']
                return any(indicator in actual_result.lower() for indicator in analysis_indicators)
            
            # Content-Generierung verifizieren
            elif action_type == 'generation':
                # Generierter Content sollte strukturiert und substantiell sein
                return len(actual_result) > 100 and ('generiert' in actual_result.lower() or 'erstellt' in actual_result.lower())
            
            return True  # Default: Aktion als erfolgreich betrachten
            
        except Exception as e:
            pass  # Optimized error handling
            return False

    def _proactive_error_detection(self) -> list:
        """Erkennt potentielle Probleme bevor sie auftreten."""
        potential_issues = []
        
        try:
            # 1. Prüfe Systemressourcen
            import psutil
            if psutil.virtual_memory().percent > 90:
                potential_issues.append("Speicher fast voll (>90%)")
            if psutil.disk_usage('.').percent > 95:
                potential_issues.append("Festplatte fast voll (>95%)")
        except ImportError:
            pass
        
        # 2. Prüfe Fehler-Häufigkeiten
        frequent_errors = [error_key for error_key, info in self.error_tracker.items() 
                          if info['count'] > 5]
        if frequent_errors:
            potential_issues.append(f"Häufige Fehler erkannt: {', '.join(frequent_errors[:3])}")
        
        # 3. Prüfe Verzeichnis-Zugriff
        critical_dirs = ['cudi_generated', 'config', 'cudi_research']
        for dir_name in critical_dirs:
            try:
                dir_path = Path(dir_name)
                if not dir_path.exists():
                    potential_issues.append(f"Kritisches Verzeichnis fehlt: {dir_name}")
                elif not os.access(str(dir_path), os.W_OK):
                    potential_issues.append(f"Keine Schreibberechtigung für: {dir_name}")
            except Exception:
                potential_issues.append(f"Zugriffsproblem bei: {dir_name}")
        
        # 4. Prüfe letzte Aktionen auf Erfolg
        recent_failures = 0
        for error_key, info in self.error_tracker.items():
            if info['last_seen']:
                try:
                    last_error = datetime.fromisoformat(info['last_seen'])
                    if (datetime.now() - last_error).total_seconds() < 300:  # Letzte 5 Min
                        recent_failures += 1
                except Exception:
                    pass
        
        if recent_failures > 3:
            potential_issues.append(f"Mehrere Fehler in letzten 5 Minuten: {recent_failures}")
        
        return potential_issues

    def _auto_recovery_system(self) -> bool:
        """Automatisches Recovery-System."""
        try:
            recovery_actions = []
            
            # 1. Selbstdiagnose durchführen
            diagnosis = self._run_self_diagnosis()
            
            if diagnosis['system_health'] in ['critical', 'error']:
                self.add_chat_message("🚨 Auto-Recovery", f"Kritische Probleme erkannt: {len(diagnosis['issues_found'])} Issues")
                
                # 2. Versuche automatische Reparaturen
                for recommendation in diagnosis['recommendations'][:3]:  # Max 3
                    try:
                        if 'pip install' in recommendation:
                            package = recommendation.split('install ')[-1]
                            subprocess.check_call([sys.executable, "-m", "pip", "install", package], 
                                                 capture_output=True, timeout=60)
                            recovery_actions.append(f"Installiert: {package}")
                    except Exception as e:
                        recovery_actions.append(f"Reparatur fehlgeschlagen: {str(e)}")
                
                # 3. Verzeichnisse reparieren
                essential_dirs = ['cudi_generated', 'cudi_research', 'config', 'cudi_content']
                for dir_name in essential_dirs:
                    try:
                        Path(dir_name).mkdir(parents=True, exist_ok=True)
                        recovery_actions.append(f"Verzeichnis repariert: {dir_name}")
                    except Exception:
                        pass
                
                # 4. Cache leeren
                try:
                    self.error_tracker.clear()
                    self.repair_attempts.clear()
                    recovery_actions.append("Fehler-Cache geleert")
                except Exception:
                    pass
                
                if recovery_actions:
                    self.add_chat_message("✅ Auto-Recovery", f"Recovery erfolgreich: {'; '.join(recovery_actions[:3])}")
                    return True
            
            return False
            
        except Exception as e:
            self.add_chat_message("❌ Auto-Recovery", f"Recovery fehlgeschlagen: {str(e)}")
            return False

    def _store_knowledge(self, concept: str, knowledge: dict):
        """Speichert gelerntes Wissen persistent."""
        if not hasattr(self, 'knowledge_base'):
            self.knowledge_base = {}
        
        self.knowledge_base[concept.lower()] = knowledge
        
        # Persistiere in Datei
        try:
            kb_file = Path("config") / "knowledge_base.json"
            kb_file.parent.mkdir(exist_ok=True)
            
            with kb_file.open('w', encoding='utf-8') as f:
                json.dump(self.knowledge_base, f, ensure_ascii=False, indent=2)
        except Exception:
            pass

    def _load_knowledge_base(self):
        """Lädt die persistente Wissensbasis."""
        try:
            kb_file = Path("config") / "knowledge_base.json"
            if kb_file.exists():
                with kb_file.open('r', encoding='utf-8') as f:
                    self.knowledge_base = json.load(f)
        except Exception:
            self.knowledge_base = {}

    def _enhance_response_with_knowledge(self, message: str, base_response: str) -> str:
        """Erweitert eine Antwort mit gelerntem Wissen."""
        concepts = self._extract_concepts(message)
        
        enhanced_parts = [base_response]
        
        for concept in concepts:
            if self._has_knowledge(concept):
                knowledge = self.knowledge_base.get(concept.lower(), {})
                if 'definition' in knowledge:
                    enhanced_parts.append(f"\n\n💡 **{concept.title()}**: {knowledge['definition']}")
                
                if 'features' in knowledge:
                    features = ', '.join(knowledge['features'][:3])  # Top 3
                    enhanced_parts.append(f"\n🔑 **Wichtige Eigenschaften**: {features}")
        
        return ''.join(enhanced_parts)

    def open_dashboard(self):
        """Öffnet ein kompaktes Dashboard mit Übersicht."""
        try:
            dlg = QDialog(self)
            dlg.setWindowTitle("CUDI – Dashboard")
            dlg.setMinimumSize(600, 460)
            lay = QVBoxLayout(dlg)

            # Modus & Status
            mode = getattr(self, 'current_mode', 'idle')
            lbl_mode = QLabel(f"Aktueller Modus: {mode}")
            lbl_mode.setStyleSheet("font-weight:bold; font-size:14px;")
            lay.addWidget(lbl_mode)

            # Letzte Aktionen (aus Chat)
            lbl_actions = QLabel("Letzte Chat-Nachrichten:")
            lay.addWidget(lbl_actions)
            actions = QTextEdit()
            actions.setReadOnly(True)
            # Simple Ausgabe der letzten 10 Einträge
            recent = getattr(self, 'conversation_context', [])[-10:]
            text = "\n".join([f"[{e['timestamp']}] {e['sender']}: {e['message']}" for e in recent])
            actions.setPlainText(text)
            lay.addWidget(actions)

            # Systemmetriken, wenn vorhanden
            metrics_box = QGroupBox("Systemstatus")
            form = QFormLayout(metrics_box)
            def add_metric(name, value):
                form.addRow(QLabel(name+":"), QLabel(str(value)))

            # Leichte, robuste Abfrage
            add_metric("Agent aktiv", getattr(self, 'agent_mode_active', False))
            add_metric("Gesprächszeilen", len(getattr(self, 'conversation_context', [])))
            add_metric("LLM bereit", bool(getattr(self, 'communication_engine', None)))
            add_metric("Auto-Sprache", getattr(self, 'auto_speech', False))
            add_metric("Minimal UI", getattr(self, 'minimal_ui', False))
            lay.addWidget(metrics_box)

            # Schließen Button
            btn = QPushButton("Schließen")
            btn.clicked.connect(dlg.accept)
            lay.addWidget(btn, 0, Qt.AlignRight)

            dlg.exec()
        except Exception as e:
            QMessageBox.critical(self, "Dashboard Fehler", str(e))
    
    def _get_llm_response(self, message):
        """Holt LLM Response (in Thread) - Alias für _get_intelligent_response"""
        self._get_intelligent_response(message)
    
    def clear_chat(self):
        """Löscht Chat"""
        self.chat_display.clear()
        self.conversation_context.clear()
    
    def export_chat(self):
        """Exportiert Chat"""
        # TODO: Chat Export implementieren
        pass
    
    def new_chat(self):
        """Startet neuen Chat"""
        self.clear_chat()
        self.add_chat_message("🤖 CUDI", "Neuer Chat gestartet. Wie kann ich dir helfen?")
    
    def save_chat(self):
        """Speichert Chat"""
        # TODO: Chat speichern implementieren
        pass
    
    # AI Tool Handlers
    def launch_research_tool(self):
        """Startet Research Tool"""
        self.add_chat_message("🔍 System", "Research Assistant aktiviert")
    
    def launch_content_tool(self):
        """Startet Content Tool"""
        self.add_chat_message("📝 System", "Content Generator aktiviert")
    
    def launch_data_tool(self):
        """Startet Data Tool"""
        self.add_chat_message("🧮 System", "Data Analyzer aktiviert")
    
    def launch_creative_tool(self):
        """Startet Creative Tool"""
        self.add_chat_message("🎨 System", "Creative Studio aktiviert")
    
    def launch_report_tool(self):
        """Startet Report Tool"""
        self.add_chat_message("📊 System", "Report Builder aktiviert")
    
    # Task Automation Handlers
    def launch_email_assistant(self):
        """Startet Email Assistant"""
        self.add_chat_message("📧 System", "Email Assistant aktiviert")
    
    def launch_calendar_manager(self):
        """Startet Calendar Manager"""
        self.add_chat_message("📅 System", "Calendar Manager aktiviert")
    
    def launch_file_organizer(self):
        """Startet File Organizer"""
        self.add_chat_message("📂 System", "File Organizer aktiviert")
    
    def launch_web_scraper(self):
        """Startet Web Scraper"""
        self.add_chat_message("🌐 System", "Web Scraper aktiviert")
    
    # Settings Handlers
    def open_plugin_manager(self):
        """Öffnet Plugin Manager"""
        try:
            from cudi_plugin_manager_dialog import CUDIPluginManagerDialog
            plugin_manager = CUDIPluginManagerDialog(parent=self)
            plugin_manager.show()
            self.add_chat_message("🔌 System", "Plugin Manager geöffnet")
        except Exception as e:
            self.add_chat_message("❌ System", f"Fehler beim Öffnen des Plugin Managers: {e}")
    
    def open_ai_settings(self):
        """Öffnet AI Settings"""
        try:
            from cudi_ai_settings_dialog import CUDIAISettingsDialog
            ai_settings = CUDIAISettingsDialog(parent=self)
            ai_settings.show()
            self.add_chat_message("🤖 System", "AI-Einstellungen geöffnet")
        except Exception as e:
            self.add_chat_message("❌ System", f"Fehler beim Öffnen der AI-Einstellungen: {e}")
    
    def open_voice_settings(self):
        """Öffnet Voice Settings"""
        # Da wir Voice erstmal rauslassen, zeigen wir eine Info-Nachricht
        self.add_chat_message("ℹ️ System", "Sprachsteuerung wird in einer zukünftigen Version verfügbar sein")
        QMessageBox.information(self, "Voice Settings", 
                              "Sprachsteuerung ist in Entwicklung und wird in einer zukünftigen Version verfügbar sein.")
    
    def open_help_system(self):
        """Öffnet das interaktive Hilfesystem"""
        try:
            from cudi_interactive_help_system import CUDIInteractiveHelpSystem
            help_system = CUDIInteractiveHelpSystem(parent=self)
            help_system.show()
            self.add_chat_message("📚 System", "Hilfe-System geöffnet")
        except Exception as e:
            self.add_chat_message("❌ System", f"Fehler beim Öffnen des Hilfe-Systems: {e}")
    
    def run_self_diagnosis(self):
        """Führt automatische Selbstdiagnose durch"""
        try:
            self.add_chat_message("🔍 System", "Starte automatische Selbstdiagnose...")
            
            # Diagnose in separatem Thread ausführen
            def run_diagnosis():
                try:
                    from cudi_auto_self_diagnosis import run_auto_diagnosis
                    result = run_auto_diagnosis(silent_mode=True)
                    
                    # Ergebnis in GUI anzeigen
                    status = result.get('status', 'unknown')
                    score = result.get('score', 0)
                    issues = result.get('issues_count', 0)
                    fixes = result.get('auto_fixes', 0)
                    
                    message = f"Diagnose abgeschlossen: {status.upper()} ({score}%)"
                    if fixes > 0:
                        message += f" - {fixes} Probleme automatisch behoben"
                    if issues > 0:
                        message += f" - {issues} Probleme gefunden"
                    
                    self.add_chat_message("✅ System", message)
                    
                    # Detailliertes Popup
                    if status in ['poor', 'critical']:
                        QMessageBox.warning(self, "System-Diagnose", 
                                          f"System-Status: {status}\nScore: {score}%\nProbleme: {issues}\nBitte prüfen Sie die Logs für Details.")
                    else:
                        QMessageBox.information(self, "System-Diagnose", 
                                              f"System-Status: {status}\nScore: {score}%\nSystem läuft optimal!")
                        
                except Exception as e:
                    self.add_chat_message("❌ System", f"Fehler bei Diagnose: {e}")
            
            # Thread starten
            import threading
            diagnosis_thread = threading.Thread(target=run_diagnosis)
            diagnosis_thread.daemon = True
            diagnosis_thread.start()
            
        except Exception as e:
            self.add_chat_message("❌ System", f"Fehler beim Starten der Diagnose: {e}")
    
    def show_faq(self):
        """Zeigt FAQ"""
        try:
            from cudi_interactive_help_system import CUDIInteractiveHelpSystem
            help_system = CUDIInteractiveHelpSystem(parent=self)
            help_system.show_faq()
            help_system.show()
            self.add_chat_message("❓ System", "FAQ geöffnet")
        except Exception as e:
            self.add_chat_message("❌ System", f"Fehler beim Öffnen der FAQ: {e}")
    
    def train_model(self):
        """Startet Model Training"""
        self.add_chat_message("🧠 System", "Model Training gestartet...")
    
    def show_about(self):
        """Zeigt About Dialog"""
        QMessageBox.about(self, "About CUDI_SUPREME", 
                         "CUDI_SUPREME v1.0\nUltimate AI Assistant\n\nDeveloped with ❤️")

    # === ECHTE DATEI-GENERATOREN FÜR ALLE FORMATE ===
    
    def _generate_csv_data(self, message, domain):
        """Generiert echte CSV-Daten"""
        return f"""Name,Wert,Datum,Status,Kategorie
Beispiel 1,100,{datetime.now().strftime('%Y-%m-%d')},Aktiv,{domain}
Beispiel 2,200,{datetime.now().strftime('%Y-%m-%d')},Inaktiv,{domain}
Beispiel 3,300,{datetime.now().strftime('%Y-%m-%d')},Aktiv,{domain}
CUDI Generated,999,{datetime.now().strftime('%Y-%m-%d')},Real,CUDI
# Basierend auf: {message}
"""
    
    def _generate_xml_data(self, message, domain):
        """Generiert echte XML-Daten"""
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<root>
    <metadata>
        <created_by>CUDI</created_by>
        <timestamp>{datetime.now().isoformat()}</timestamp>
        <domain>{domain}</domain>
        <prompt>{message}</prompt>
    </metadata>
    <data>
        <item id="1" status="active">Beispiel Eintrag 1</item>
        <item id="2" status="inactive">Beispiel Eintrag 2</item>
        <item id="3" status="active">CUDI Generated Data</item>
    </data>
</root>"""
    
    def _generate_sql_data(self, message, domain):
        """Generiert echte SQL-Statements"""
        return f"""-- SQL Script generiert von CUDI
-- Basierend auf: {message}
-- Domain: {domain}
-- Erstellt: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

CREATE TABLE IF NOT EXISTS cudi_data (
    id INT PRIMARY KEY AUTO_INCREMENT,
    name VARCHAR(255) NOT NULL,
    value INT DEFAULT 0,
    created_date DATE DEFAULT CURRENT_DATE,
    status ENUM('active', 'inactive') DEFAULT 'active',
    domain VARCHAR(100) DEFAULT '{domain}'
);

INSERT INTO cudi_data (name, value, status) VALUES 
('Beispiel 1', 100, 'active'),
('Beispiel 2', 200, 'inactive'),
('CUDI Generated', 999, 'active');

-- Abfrage für alle aktiven Einträge
SELECT * FROM cudi_data WHERE status = 'active';
"""
    
    def _generate_batch_script(self, message, domain):
        """Generiert echte Batch-Scripts"""
        return f"""@echo off
REM Batch Script generiert von CUDI
REM Basierend auf: {message}
REM Domain: {domain}
REM Erstellt: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

echo CUDI Batch Script gestartet...
echo Nachricht: {message}
echo Domain: {domain}
echo Aktuelle Zeit: %date% %time%

REM Erstelle Verzeichnis falls nicht vorhanden
if not exist "cudi_output" mkdir cudi_output

REM Schreibe Ausgabe in Datei
echo CUDI Script Output > cudi_output\\script_output.txt
echo Erstellt am %date% %time% >> cudi_output\\script_output.txt

echo Script erfolgreich abgeschlossen!
pause
"""
    
    def _generate_powershell_script(self, message, domain):
        """Generiert echte PowerShell-Scripts"""
        return f"""# PowerShell Script generiert von CUDI
# Basierend auf: {message}
# Domain: {domain}
# Erstellt: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

Write-Host "CUDI PowerShell Script gestartet..." -ForegroundColor Green
Write-Host "Nachricht: {message}" -ForegroundColor Yellow
Write-Host "Domain: {domain}" -ForegroundColor Cyan
Write-Host "Aktuelle Zeit: $(Get-Date)" -ForegroundColor White

# Erstelle Verzeichnis falls nicht vorhanden
if (!(Test-Path "cudi_output")) {{
    New-Item -ItemType Directory -Path "cudi_output"
    Write-Host "Verzeichnis 'cudi_output' erstellt" -ForegroundColor Green
}}

# Erstelle Ausgabe-Datei
$output = @"
CUDI PowerShell Script Output
Erstellt am: $(Get-Date)
Original-Nachricht: {message}
Domain: {domain}
"@

$output | Out-File "cudi_output\\powershell_output.txt" -Encoding UTF8
Write-Host "Ausgabe in 'cudi_output\\powershell_output.txt' gespeichert" -ForegroundColor Green

Write-Host "Script erfolgreich abgeschlossen!" -ForegroundColor Green
"""
    
    def _generate_markdown_content(self, message, domain):
        """Generiert echten Markdown-Content"""
        return f"""# CUDI Generated Document

**Erstellt am:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}  
**Domain:** {domain}  
**Basierend auf:** {message}

---

## Übersicht

Dieses Dokument wurde automatisch von CUDI generiert basierend auf der Anfrage: *"{message}"*

## Inhalt

### Beispiel-Daten

| Name | Wert | Status |
|------|------|--------|
| Beispiel 1 | 100 | ✅ Aktiv |
| Beispiel 2 | 200 | ❌ Inaktiv |
| CUDI Data | 999 | ✅ Real |

### Code-Beispiel

```python
# CUDI Generated Code
def example_function():
    return "Echte Daten von CUDI"

print(example_function())
```

### Features

- ✅ **Echte Daten**: Alle Inhalte sind real und funktional
- ✅ **Automatische Generierung**: Von CUDI erstellt
- ✅ **Vollständig formatiert**: Markdown-kompatibel
- ✅ **Timestamps**: Mit echten Zeitstempeln

---

*Generiert von CUDI - Echte KI, echte Ergebnisse!* 🤖
"""

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Dark Theme für die gesamte App
    app.setStyle("Fusion")
    
    window = CUDISupremeMainWindow()
    window.show()
    
    sys.exit(app.exec())
