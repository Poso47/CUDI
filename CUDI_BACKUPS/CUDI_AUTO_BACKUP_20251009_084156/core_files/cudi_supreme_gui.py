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
from datetime import datetime
from pathlib import Path

from PySide6.QtWidgets import *
from PySide6.QtCore import *
from PySide6.QtGui import *

# Advanced Communication Integration
try:
    import openai
except ImportError:
    openai = None
    
try:
    import anthropic
except ImportError:
    anthropic = None

# CUDI_SUPREME Imports
try:
    from llm_integration import LLMIntegration
    # from brain import Brain
    from cudi_brain import CudiBrain
    from memory import Memory
    from emotion import Emotion
    from avatar import get_avatar
except ImportError as e:
    print(f"⚠️ Import-Warnung: {e}")

# ModernCard als lokale Komponente definieren
class ModernCard(QFrame):
    def __init__(self, title="", parent=None):
        super().__init__(parent)
        self.setFrameStyle(QFrame.Box)
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
        
    def initialize_models(self):
        """Initialisiert alle verfügbaren LLM-Modelle"""
        try:
            # OpenAI (falls API-Key verfügbar)
            if os.getenv("OPENAI_API_KEY"):
                self.models["openai"] = openai.OpenAI()
                print("✅ OpenAI Model initialized")
        except Exception as e:
            print(f"⚠️ OpenAI not available: {e}")
            
        try:
            # Anthropic (falls API-Key verfügbar)
            if os.getenv("ANTHROPIC_API_KEY"):
                self.models["anthropic"] = anthropic.Anthropic()
                print("✅ Anthropic Model initialized")
        except Exception as e:
            print(f"⚠️ Anthropic not available: {e}")
            
        try:
            # Lokales Modell (Ollama)
            response = requests.get("http://localhost:11434/api/tags", timeout=5)
            if response.status_code == 200:
                self.models["local"] = "ollama"
                print("✅ Local Ollama Model initialized")
        except Exception as e:
            print(f"⚠️ Local model not available: {e}")
    
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
        system_prompt = f"""Du bist CUDI, ein hochentwickelter AI-Assistent mit folgenden Eigenschaften:

PERSÖNLICHKEIT: {self.personality}
- Professionell, hilfsbereit und präzise
- Antworte auf Deutsch, außer wenn explizit anders gewünscht
- Sei kreativ und lösungsorientiert
- Erkläre komplexe Themen verständlich

KOMMUNIKATIONSSTIL: {self.communication_style}
- Gib detaillierte, strukturierte Antworten
- Verwende Emojis zur besseren Lesbarkeit
- Biete praktische Lösungen und nächste Schritte
- Frage nach, wenn Informationen unvollständig sind

FÄHIGKEITEN:
- Code-Analyse und -Generierung
- Problem-Lösung und Debugging
- Projektplanung und -management
- Kreative Unterstützung
- Technische Beratung

Aktueller Kontext: {additional_context or 'Allgemeine Unterhaltung'}
Verlauf: {len(self.conversation_context)} vorherige Nachrichten

Benutzer-Nachricht: {message}

Antworte hilfreich und umfassend:"""

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
        """Fallback für intelligente Antworten"""
        responses = {
            "hallo": "Hallo! 👋 Ich bin CUDI, Ihr AI-Assistent. Wie kann ich Ihnen heute helfen?",
            "hilfe": "Gerne helfe ich Ihnen! 🤝 Ich kann bei Code, Projekten, Problemen und vielem mehr unterstützen. Was beschäftigt Sie?",
            "was kannst du": "Ich kann Ihnen bei vielen Aufgaben helfen: 💡\n• Code schreiben und analysieren\n• Probleme lösen\n• Projekte planen\n• Fragen beantworten\n• Kreativ unterstützen\n\nWas möchten Sie angehen?",
            "danke": "Sehr gerne! 😊 Falls Sie weitere Fragen haben, bin ich hier für Sie da.",
        }
        
        message_lower = message.lower()
        for key, response in responses.items():
            if key in message_lower:
                return response
                
        return f"Interessante Frage! 🤔 Könnten Sie mir mehr Details dazu geben? Ich möchte Ihnen die bestmögliche Antwort geben. Ihre Nachricht: '{message}'"

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
    
    def __init__(self):
        super().__init__()
        
        # CUDI_SUPREME Komponenten mit Advanced Communication
        self.communication_engine = None
        self.brain = None  # Wird durch CudiBrain ersetzt
        self.memory = None
        self.emotion = None
        
        # Agent Mode State
        self.agent_mode_active = True  # Direkt im Agent-Modus starten
        self.auto_response = True
        self.conversation_context = []
        
        # GUI State
        self.current_category = "agent"  # Start-Kategorie
        self.categories = {
            "agent": "🤖 Agent Modus",
            "communication": "💬 Kommunikation", 
            "tools": "🛠️ Tools & Plugins",
            "analysis": "📊 Analyse & Daten",
            "automation": "⚡ Automatisierung",
            "settings": "⚙️ Einstellungen"
        }
        
        self.init_ui()
        self.init_cudi_supreme()
        self.connect_signals()
        self.start_agent_mode()
        
    def init_ui(self):
        """Initialisiert die kategorisierte Benutzeroberfläche"""
        self.setWindowTitle("🤖 CUDI_SUPREME - Intelligenter Agent Assistant")
        self.setGeometry(100, 100, 1600, 1000)
        self.setMinimumSize(1200, 800)
        
        # Supreme Dark Theme
        self.apply_supreme_theme()
        
        # Central Widget mit kategorisiertem Layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QVBoxLayout(central_widget)
        main_layout.setSpacing(0)
        main_layout.setContentsMargins(0, 0, 0, 0)
        
        # Category Navigation Bar (Top)
        self.create_category_navigation(main_layout)
        
        # Main Content Area (Dynamic based on category)
        self.content_stack = QStackedWidget()
        main_layout.addWidget(self.content_stack)
        
        # Create all category pages
        self.create_all_category_pages()
        
        # Status Bar (Bottom)
        self.create_supreme_statusbar()
        
        # Set initial category to Agent Mode
        self.switch_category("agent")
        
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
        """Erstellt alle Kategorie-Seiten"""
        
        # 1. Agent Modus (Hauptseite)
        self.agent_page = self.create_agent_mode_page()
        self.content_stack.addWidget(self.agent_page)
        
        # 2. Kommunikation
        self.communication_page = self.create_communication_page()
        self.content_stack.addWidget(self.communication_page)
        
        # 3. Tools & Plugins
        self.tools_page = self.create_tools_page()
        self.content_stack.addWidget(self.tools_page)
        
        # 4. Analyse & Daten
        self.analysis_page = self.create_analysis_page()
        self.content_stack.addWidget(self.analysis_page)
        
        # 5. Automatisierung
        self.automation_page = self.create_automation_page()
        self.content_stack.addWidget(self.automation_page)
        
        # 6. Einstellungen
        self.settings_page = self.create_settings_page()
        self.content_stack.addWidget(self.settings_page)
    
    def create_agent_mode_page(self):
        """Erstellt die Agent-Modus Hauptseite"""
        page = QWidget()
        layout = QHBoxLayout(page)
        layout.setSpacing(15)
        layout.setContentsMargins(15, 15, 15, 15)
        
        # Left: Agent Controls
        left_panel = QWidget()
        left_panel.setFixedWidth(350)
        left_layout = QVBoxLayout(left_panel)
        
        # Agent Status Card
        agent_card = ModernCard("🤖 Agent Status")
        agent_layout = QVBoxLayout()
        
        # Agent Avatar mit Animation
        self.agent_avatar = QLabel("🤖")
        self.agent_avatar.setAlignment(Qt.AlignCenter)
        self.agent_avatar.setStyleSheet("""
            QLabel {
                background: qradial-gradient(circle, #1f6feb 0%, #0969da 100%);
                border-radius: 50px;
                font-size: 48px;
                color: white;
                min-height: 100px;
                max-height: 100px;
                min-width: 100px;
                max-width: 100px;
            }
        """)
        agent_layout.addWidget(self.agent_avatar, 0, Qt.AlignCenter)
        
        # Agent Status Text
        self.agent_status_label = QLabel("🟢 Agent Aktiv - Bereit für Anfragen")
        self.agent_status_label.setAlignment(Qt.AlignCenter)
        self.agent_status_label.setStyleSheet("""
            QLabel {
                color: #39d353;
                font-weight: bold;
                font-size: 14px;
                background: transparent;
                padding: 10px;
            }
        """)
        agent_layout.addWidget(self.agent_status_label)
        
        # Quick Actions
        actions_layout = QGridLayout()
        
        self.quick_actions = [
            ("🧠 Analyse", self.quick_analyze, 0, 0),
            ("📝 Schreiben", self.quick_write, 0, 1),
            ("🔍 Recherche", self.quick_research, 1, 0),
            ("🛠️ Problem lösen", self.quick_solve, 1, 1),
            ("💡 Brainstorm", self.quick_brainstorm, 2, 0),
            ("📊 Daten", self.quick_data, 2, 1)
        ]
        
        for text, callback, row, col in self.quick_actions:
            btn = QPushButton(text)
            btn.clicked.connect(callback)
            btn.setMinimumHeight(40)
            btn.setStyleSheet("""
                QPushButton {
                    font-size: 11px;
                    font-weight: bold;
                    padding: 8px;
                }
            """)
            actions_layout.addWidget(btn, row, col)
        
        agent_layout.addLayout(actions_layout)
        agent_card.layout().addLayout(agent_layout)
        left_layout.addWidget(agent_card)
        
        # Communication Settings
        comm_card = ModernCard("💬 Kommunikation")
        comm_layout = QVBoxLayout()
        
        # Response Style
        style_layout = QFormLayout()
        
        self.response_style = QComboBox()
        self.response_style.addItems([
            "🎯 Präzise & Direkt",
            "📚 Ausführlich & Detailliert", 
            "💡 Kreativ & Inspirierend",
            "🤝 Freundlich & Hilfsbereit",
            "🔬 Technisch & Analytisch"
        ])
        self.response_style.currentTextChanged.connect(self.update_communication_style)
        
        self.auto_response_cb = QCheckBox("Automatische Antworten")
        self.auto_response_cb.setChecked(self.auto_response)
        self.auto_response_cb.stateChanged.connect(self.toggle_auto_response)
        
        style_layout.addRow("Antwort-Stil:", self.response_style)
        style_layout.addRow("", self.auto_response_cb)
        
        comm_layout.addLayout(style_layout)
        comm_card.layout().addLayout(comm_layout)
        left_layout.addWidget(comm_card)
        
        left_layout.addStretch()
        layout.addWidget(left_panel)
        
        # Center: Chat Interface
        center_panel = QWidget()
        center_layout = QVBoxLayout(center_panel)
        
        # Chat Header
        chat_header = QFrame()
        chat_header.setStyleSheet("""
            QFrame {
                background-color: #21262d;
                border: 2px solid #30363d;
                border-radius: 8px;
                padding: 10px;
                margin-bottom: 10px;
            }
        """)
        header_layout = QHBoxLayout(chat_header)
        
        chat_title = QLabel("💬 Intelligente Unterhaltung")
        chat_title.setStyleSheet("font-size: 16px; font-weight: bold; color: #ffffff;")
        
        clear_btn = QPushButton("🗑️ Löschen")
        clear_btn.clicked.connect(self.clear_chat)
        clear_btn.setMaximumWidth(100)
        
        export_btn = QPushButton("💾 Export")
        export_btn.clicked.connect(self.export_chat)
        export_btn.setMaximumWidth(100)
        
        header_layout.addWidget(chat_title)
        header_layout.addStretch()
        header_layout.addWidget(clear_btn)
        header_layout.addWidget(export_btn)
        
        center_layout.addWidget(chat_header)
        
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
        center_layout.addWidget(self.chat_display)
        
        # Input Area
        input_frame = QFrame()
        input_frame.setStyleSheet("""
            QFrame {
                background-color: #21262d;
                border: 2px solid #30363d;
                border-radius: 8px;
                padding: 10px;
                margin-top: 10px;
            }
        """)
        input_layout = QHBoxLayout(input_frame)
        
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Fragen Sie mich alles... Ich bin Ihr intelligenter Agent!")
        self.chat_input.setStyleSheet("""
            QLineEdit {
                background-color: #0d1117;
                color: #ffffff;
                border: 2px solid #30363d;
                border-radius: 8px;
                padding: 12px 16px;
                font-size: 14px;
                min-height: 20px;
            }
            QLineEdit:focus {
                border-color: #1f6feb;
            }
        """)
        self.chat_input.returnPressed.connect(self.send_message)
        
        send_btn = QPushButton("🚀 Senden")
        send_btn.clicked.connect(self.send_message)
        send_btn.setMinimumWidth(120)
        send_btn.setStyleSheet("""
            QPushButton {
                background: qlineargradient(x1: 0, y1: 0, x2: 0, y2: 1,
                                          stop: 0 #1f6feb, stop: 1 #0969da);
                font-size: 14px;
                font-weight: bold;
                min-height: 40px;
            }
        """)
        
        input_layout.addWidget(self.chat_input)
        input_layout.addWidget(send_btn)
        
        center_layout.addWidget(input_frame)
        layout.addWidget(center_panel)
        
        # Right: System Info
        right_panel = QWidget()
        right_panel.setFixedWidth(300)
        right_layout = QVBoxLayout(right_panel)
        
        # System Status
        system_card = ModernCard("📊 System Status")
        system_layout = QVBoxLayout()
        
        self.system_metrics = {}
        metrics = [
            ("Agent Status", "agent", "🟢 Aktiv"),
            ("Kommunikation", "comm", "🟢 Bereit"),
            ("Speicher", "memory", "🟡 75%"),
            ("Performance", "perf", "🟢 Optimal")
        ]
        
        for name, key, status in metrics:
            metric_layout = QHBoxLayout()
            
            name_label = QLabel(name)
            name_label.setStyleSheet("color: #ffffff; font-size: 12px;")
            
            status_label = QLabel(status)
            status_label.setStyleSheet("color: #39d353; font-size: 12px; font-weight: bold;")
            
            metric_layout.addWidget(name_label)
            metric_layout.addStretch()
            metric_layout.addWidget(status_label)
            
            system_layout.addLayout(metric_layout)
            self.system_metrics[key] = status_label
        
        system_card.layout().addLayout(system_layout)
        right_layout.addWidget(system_card)
        
        # Recent Actions
        actions_card = ModernCard("⚡ Letzte Aktionen")
        actions_layout = QVBoxLayout()
        
        self.recent_actions_list = QListWidget()
        self.recent_actions_list.setMaximumHeight(200)
        self.recent_actions_list.setStyleSheet("""
            QListWidget {
                background-color: #0d1117;
                border: 1px solid #30363d;
                border-radius: 6px;
                padding: 5px;
            }
            QListWidget::item {
                padding: 5px;
                border-bottom: 1px solid #21262d;
                color: #ffffff;
                font-size: 11px;
            }
        """)
        
        # Dummy Actions
        dummy_actions = [
            "🔍 Web-Recherche durchgeführt",
            "📝 Text generiert",
            "🧮 Daten analysiert",
            "💡 Lösungsvorschläge erstellt"
        ]
        
        for action in dummy_actions:
            self.recent_actions_list.addItem(action)
        
        actions_layout.addWidget(self.recent_actions_list)
        actions_card.layout().addLayout(actions_layout)
        right_layout.addWidget(actions_card)
        
        right_layout.addStretch()
        layout.addWidget(right_panel)
        
    def create_communication_page(self):
        """Erstellt die Kommunikations-Seite"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        
        title = QLabel("💬 Erweiterte Kommunikationseinstellungen")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #ffffff; margin-bottom: 20px;")
        layout.addWidget(title)
        
        # Kommunikations-Modelle
        models_card = ModernCard("🧠 AI-Modelle")
        models_layout = QVBoxLayout()
        
        self.model_selector = QComboBox()
        self.model_selector.addItems([
            "🔵 Lokales Modell (Ollama)",
            "🟢 OpenAI GPT-4",
            "🟣 Anthropic Claude",
            "🔴 Gemini Pro"
        ])
        self.model_selector.currentTextChanged.connect(self.change_ai_model)
        models_layout.addWidget(QLabel("Aktives Modell:"))
        models_layout.addWidget(self.model_selector)
        
        models_card.layout().addLayout(models_layout)
        layout.addWidget(models_card)
        
        # Persönlichkeitseinstellungen
        personality_card = ModernCard("🎭 Persönlichkeit & Stil")
        personality_layout = QFormLayout()
        
        self.creativity_slider = QSlider(Qt.Horizontal)
        self.creativity_slider.setRange(0, 100)
        self.creativity_slider.setValue(70)
        
        self.formality_slider = QSlider(Qt.Horizontal) 
        self.formality_slider.setRange(0, 100)
        self.formality_slider.setValue(60)
        
        self.detail_slider = QSlider(Qt.Horizontal)
        self.detail_slider.setRange(0, 100)
        self.detail_slider.setValue(80)
        
        personality_layout.addRow("Kreativität:", self.creativity_slider)
        personality_layout.addRow("Formalität:", self.formality_slider)
        personality_layout.addRow("Detailgrad:", self.detail_slider)
        
        personality_card.layout().addLayout(personality_layout)
        layout.addWidget(personality_card)
        
        layout.addStretch()
        return page
    
    def create_tools_page(self):
        """Erstellt die Tools & Plugins Seite"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        
        title = QLabel("🛠️ Tools & Plugin Management")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #ffffff; margin-bottom: 20px;")
        layout.addWidget(title)
        
        # Plugin Controls
        controls_layout = QHBoxLayout()
        
        self.plugin_manager_btn = QPushButton("🔌 Plugin Manager")
        self.plugin_manager_btn.clicked.connect(self.open_plugin_manager)
        self.plugin_manager_btn.setMinimumHeight(50)
        
        self.help_system_btn = QPushButton("📚 Hilfe System")
        self.help_system_btn.clicked.connect(self.open_help_system)
        self.help_system_btn.setMinimumHeight(50)
        
        self.diagnosis_btn = QPushButton("🔍 Selbstdiagnose")
        self.diagnosis_btn.clicked.connect(self.run_self_diagnosis)
        self.diagnosis_btn.setMinimumHeight(50)
        
        controls_layout.addWidget(self.plugin_manager_btn)
        controls_layout.addWidget(self.help_system_btn)
        controls_layout.addWidget(self.diagnosis_btn)
        
        layout.addLayout(controls_layout)
        
        # Available Tools Grid
        tools_card = ModernCard("🔧 Verfügbare Tools")
        tools_layout = QGridLayout()
        
        tools = [
            ("📝 Text Generator", self.launch_text_generator, 0, 0),
            ("🔍 Web Scraper", self.launch_web_scraper, 0, 1),
            ("📊 Daten Analyzer", self.launch_data_analyzer, 0, 2),
            ("🎨 Creative Studio", self.launch_creative_studio, 1, 0),
            ("📧 Email Assistant", self.launch_email_assistant, 1, 1),
            ("📅 Calendar Manager", self.launch_calendar_manager, 1, 2),
            ("🌐 API Tester", self.launch_api_tester, 2, 0),
            ("🗂️ File Organizer", self.launch_file_organizer, 2, 1),
            ("🔐 Security Scanner", self.launch_security_scanner, 2, 2)
        ]
        
        for name, callback, row, col in tools:
            btn = QPushButton(name)
            btn.clicked.connect(callback)
            btn.setMinimumHeight(60)
            btn.setStyleSheet("""
                QPushButton {
                    font-size: 12px;
                    font-weight: bold;
                    text-align: center;
                    padding: 10px;
                }
                QPushButton:hover {
                    transform: scale(1.05);
                }
            """)
            tools_layout.addWidget(btn, row, col)
        
        tools_card.layout().addLayout(tools_layout)
        layout.addWidget(tools_card)
        
        layout.addStretch()
        return page
    
    def create_analysis_page(self):
        """Erstellt die Analyse & Daten Seite"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        
        title = QLabel("📊 Analyse & Datenverarbeitung")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #ffffff; margin-bottom: 20px;")
        layout.addWidget(title)
        
        # Analysis Tools
        analysis_card = ModernCard("🔬 Analyse-Tools")
        analysis_layout = QGridLayout()
        
        analysis_tools = [
            ("📈 Datenvisualisierung", self.launch_data_visualization, 0, 0),
            ("🧮 Statistik Analyse", self.launch_statistics, 0, 1),
            ("🤖 ML Modelle", self.launch_ml_models, 1, 0),
            ("📉 Trend Analyse", self.launch_trend_analysis, 1, 1),
            ("🔍 Pattern Detection", self.launch_pattern_detection, 2, 0),
            ("📋 Report Generator", self.launch_report_generator, 2, 1)
        ]
        
        for name, callback, row, col in analysis_tools:
            btn = QPushButton(name)
            btn.clicked.connect(callback)
            btn.setMinimumHeight(60)
            analysis_layout.addWidget(btn, row, col)
        
        analysis_card.layout().addLayout(analysis_layout)
        layout.addWidget(analysis_card)
        
        layout.addStretch()
        return page
    
    def create_automation_page(self):
        """Erstellt die Automatisierungs-Seite"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        
        title = QLabel("⚡ Automatisierung & Workflows")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #ffffff; margin-bottom: 20px;")
        layout.addWidget(title)
        
        # Automation Tools
        auto_card = ModernCard("🔄 Automatisierungs-Tools")
        auto_layout = QGridLayout()
        
        auto_tools = [
            ("⏰ Task Scheduler", self.launch_task_scheduler, 0, 0),
            ("🔁 Workflow Builder", self.launch_workflow_builder, 0, 1),
            ("📂 Batch Processing", self.launch_batch_processing, 1, 0),
            ("🌐 API Automation", self.launch_api_automation, 1, 1),
            ("📧 Email Automation", self.launch_email_automation, 2, 0),
            ("🔄 Data Sync", self.launch_data_sync, 2, 1)
        ]
        
        for name, callback, row, col in auto_tools:
            btn = QPushButton(name)
            btn.clicked.connect(callback)
            btn.setMinimumHeight(60)
            auto_layout.addWidget(btn, row, col)
        
        auto_card.layout().addLayout(auto_layout)
        layout.addWidget(auto_card)
        
        layout.addStretch()
        return page
    
    def create_settings_page(self):
        """Erstellt die Einstellungs-Seite"""
        page = QWidget()
        layout = QVBoxLayout(page)
        layout.setContentsMargins(20, 20, 20, 20)
        
        title = QLabel("⚙️ System-Einstellungen")
        title.setStyleSheet("font-size: 24px; font-weight: bold; color: #ffffff; margin-bottom: 20px;")
        layout.addWidget(title)
        
        # Settings Categories
        settings_layout = QHBoxLayout()
        
        # Left: AI Settings
        ai_settings_card = ModernCard("🤖 AI-Einstellungen")
        ai_settings_layout = QVBoxLayout()
        
        ai_settings_btn = QPushButton("🎛️ AI-Konfiguration öffnen")
        ai_settings_btn.clicked.connect(self.open_ai_settings)
        ai_settings_btn.setMinimumHeight(50)
        
        cloud_settings_btn = QPushButton("☁️ Cloud-Synchronisation")
        cloud_settings_btn.clicked.connect(self.open_cloud_settings)
        cloud_settings_btn.setMinimumHeight(50)
        
        ai_settings_layout.addWidget(ai_settings_btn)
        ai_settings_layout.addWidget(cloud_settings_btn)
        ai_settings_card.layout().addLayout(ai_settings_layout)
        
        # Right: System Settings
        sys_settings_card = ModernCard("🔧 System-Einstellungen")
        sys_settings_layout = QVBoxLayout()
        
        theme_selector = QComboBox()
        theme_selector.addItems(["🌙 Dark Theme", "☀️ Light Theme", "🌈 Custom"])
        
        language_selector = QComboBox()
        language_selector.addItems(["🇩🇪 Deutsch", "🇺🇸 English", "🇫🇷 Français"])
        
        sys_settings_layout.addWidget(QLabel("Theme:"))
        sys_settings_layout.addWidget(theme_selector)
        sys_settings_layout.addWidget(QLabel("Sprache:"))
        sys_settings_layout.addWidget(language_selector)
        
        layout.addStretch()
        return page
    
    # Core Functionality Methods
    def init_cudi_supreme(self):
        """Initialisiert alle CUDI_SUPREME Komponenten"""
        print("🚀 Initialisiere CUDI_SUPREME mit Advanced Communication...")
        
        # Communication Engine
        try:
            self.communication_engine = get_llm()
            if self.communication_engine:
                self.communication_engine.initialize_models()
                print("✅ Advanced Communication Engine geladen")
            else:
                print("⚠️ Communication Engine Fallback")
        except Exception as e:
            print(f"❌ Communication Error: {e}")
        
        # CUDI CudiBrain
        try:
            self.brain = CudiBrain()
            print("✅ CUDI CudiBrain initialisiert")
        except Exception as e:
            print(f"⚠️ CudiBrain Fehler: {e}")
        
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
        """Sendet Nachricht"""
        message = self.chat_input.text().strip()
        if not message:
            return
        
        # User message hinzufügen
        self.add_chat_message("👤 Du", message)
        self.chat_input.clear()
        
        # Avatar auf "thinking" setzen
        if hasattr(self, 'agent_avatar'):
            self.agent_avatar.setText("🧠")
        
        # Input verarbeiten (nur wenn Agent aktiv)
        if self.agent_mode_active:
            self.process_user_input(message)
        else:
            self.add_chat_message("🤖 CUDI", "Agent-Modus ist deaktiviert. Bitte aktivieren Sie ihn, um eine Antwort zu erhalten.")
    
    def process_user_input(self, message):
        """Verarbeitet User Input mit Advanced Communication und CudiBrain"""
        if self.brain:
            # Nutze CudiBrain für menschenähnliche Antwort
            thread = threading.Thread(target=self._get_brain_response, args=(message,))
            thread.daemon = True
            thread.start()
        elif self.communication_engine:
            # Fallback: AdvancedCommunicationEngine
            thread = threading.Thread(target=self._get_intelligent_response, args=(message,))
            thread.daemon = True
            thread.start()
        else:
            # Fallback response
            self.add_chat_message("🤖 CUDI", 
                                "Entschuldigung, die Kommunikations-Engine ist nicht verfügbar. "
                                "Bitte prüfen Sie die Einstellungen oder starten Sie das System neu.")

    def _get_brain_response(self, message):
        """Antwort von CudiBrain generieren (in Thread)"""
        try:
            context = {
                "category": self.current_category,
                "agent_mode": self.agent_mode_active,
                "conversation_length": len(self.conversation_context)
            }
            response = self.brain.understand_and_respond(message, context)
            QTimer.singleShot(0, lambda: self._update_chat_with_response(response))
        except Exception as e:
            error_msg = f"CudiBrain Fehler: {str(e)}"
            QTimer.singleShot(0, lambda: self._update_chat_with_response(error_msg))
    
    def _get_intelligent_response(self, message):
        """Generiert intelligente Antwort (in Thread)"""
        try:
            # Context für bessere Antworten
            context = {
                "category": self.current_category,
                "agent_mode": self.agent_mode_active,
                "conversation_length": len(self.conversation_context)
            }
            
            response = self.communication_engine.get_response(message, context)
            
            # GUI-Update im Main Thread
            QTimer.singleShot(0, lambda: self._update_chat_with_response(response))
            
        except Exception as e:
            error_msg = f"Entschuldigung, ein Fehler ist aufgetreten: {str(e)}"
            QTimer.singleShot(0, lambda: self._update_chat_with_response(error_msg))
    
    def _update_chat_with_response(self, response):
        """Aktualisiert Chat mit Antwort (Main Thread)"""
        self.add_chat_message("🤖 CUDI", response)
        
        # Avatar zurück zu normal
        if hasattr(self, 'agent_avatar'):
            self.agent_avatar.setText("🤖")
    
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
        """Initialisiert die ultimative Benutzeroberfläche"""
        self.setWindowTitle("CUDI_SUPREME - Ultimate AI Assistant")
        self.setGeometry(100, 100, 1800, 1200)
        self.setMinimumSize(1400, 900)
        
        # Ultimate Dark Theme
        self.apply_supreme_theme()
        
        # Central Widget mit Splitter-Layout
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        main_layout = QHBoxLayout(central_widget)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(10, 10, 10, 10)
        
        # Main Splitter
        splitter = QSplitter(Qt.Horizontal)
        
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
        
        avatar_card.layout().addLayout(avatar_layout)
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
        
        brain_card.layout().addLayout(brain_layout)
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
        
        self.voice_volume_slider = QSlider(Qt.Horizontal)
        self.voice_volume_slider.setRange(0, 100)
        self.voice_volume_slider.setValue(90)
        self.voice_volume_slider.valueChanged.connect(self.change_voice_volume)
        
        self.voice_speed_slider = QSlider(Qt.Horizontal)
        self.voice_speed_slider.setRange(50, 300)
        self.voice_speed_slider.setValue(180)
        self.voice_speed_slider.valueChanged.connect(self.change_voice_speed)
        
        settings_layout.addRow("Volume:", self.voice_volume_slider)
        settings_layout.addRow("Speed:", self.voice_speed_slider)
        
        voice_layout.addLayout(settings_layout)
        
        voice_card.layout().addLayout(voice_layout)
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
            slider = QSlider(Qt.Horizontal)
            slider.setRange(0, 100)
            slider.setValue(default_value)
            slider.valueChanged.connect(lambda v, k=trait_key: self.update_personality_trait(k, v))
            
            self.trait_sliders[trait_key] = slider
            traits_layout.addRow(f"{trait_name}:", slider)
        
        personality_layout.addLayout(traits_layout)
        
        personality_card.layout().addLayout(personality_layout)
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
        
        actions_card.layout().addLayout(actions_layout)
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
        
        health_card.layout().addLayout(health_layout)
        layout.addWidget(health_card)
    
    def init_cudi_supreme(self):
        """Initialisiert alle CUDI_SUPREME Komponenten"""
        print("🚀 Initialisiere CUDI_SUPREME...")
        
        # LLM Integration
        try:
            self.llm = get_llm()
            self.update_status("LLM", "✅ Ready")
            print("✅ LLM Integration geladen")
        except Exception as e:
            self.update_status("LLM", "❌ Error")
            print(f"❌ LLM Error: {e}")
        
        # Voice Engine
        try:
            self.voice_engine = get_voice_engine()
            self.voice_engine.set_voice_callback(self.handle_voice_input)
            self.update_status("Voice", "✅ Ready")
            print("✅ Voice Engine geladen")
        except Exception as e:
            self.update_status("Voice", "❌ Error")
            print(f"❌ Voice Error: {e}")
        
        # Plugin Manager
        try:
            self.plugin_manager = get_plugin_manager()
            self.update_plugin_list()
            self.update_status("Plugins", "✅ Ready")
            print("✅ Plugin Manager geladen")
        except Exception as e:
            self.update_status("Plugins", "❌ Error")
            print(f"❌ Plugin Error: {e}")
        
        # CUDI Core
        try:
            self.brain = Brain()
            self.memory = Memory()
            self.emotion = Emotion()
            self.avatar = get_avatar()
            
            # Integration
            self.brain.set_memory_emotion(self.memory, self.emotion)
            
            self.update_status("Core", "✅ Ready")
            print("✅ CUDI Core geladen")
        except Exception as e:
            self.update_status("Core", "❌ Error")
            print(f"❌ Core Error: {e}")
        
        print("🎉 CUDI_SUPREME Initialisierung abgeschlossen!")
    
    def connect_signals(self):
        """Verbindet alle Signals"""
        self.message_received.connect(self.handle_message_received)
        self.system_status_changed.connect(self.handle_status_changed)
    
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
        # TODO: Deep Thinking Logic
    
    def trigger_learning_mode(self):
        """Triggert Learning Mode"""
        self.add_chat_message("📚 System", "Learning Mode aktiviert...")
        # TODO: Learning Logic
    
    def trigger_research_mode(self):
        """Triggert Research Mode"""
        self.add_chat_message("🔍 System", "Research Mode aktiviert...")
        # TODO: Research Logic
    
    def trigger_creative_mode(self):
        """Triggert Creative Mode"""
        self.add_chat_message("🎨 System", "Creative Mode aktiviert...")
        # TODO: Creative Logic
    
    def trigger_problem_solving(self):
        """Triggert Problem Solving Mode"""
        self.add_chat_message("🛠️ System", "Problem Solving Mode aktiviert...")
        # TODO: Problem Solving Logic
    
    def trigger_innovation_mode(self):
        """Triggert Innovation Mode"""
        self.add_chat_message("💡 System", "Innovation Mode aktiviert...")
        # TODO: Innovation Logic
    
    # Utility Methods
    def update_status(self, component, status):
        """Aktualisiert Komponenten-Status"""
        # Status in Brain Components aktualisieren
        pass
    
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
        # Health Metrics aktualisieren
        import random
        for metric_key, (progress, label) in self.health_metrics.items():
            # Simuliere realistische Werte
            current_value = progress.value()
            new_value = max(0, min(100, current_value + random.randint(-5, 5)))
            progress.setValue(new_value)
            label.setText(f"{new_value}%")
    
    def update_plugin_list(self):
        """Aktualisiert Plugin-Liste"""
        if self.plugin_manager:
            plugins = self.plugin_manager.get_plugin_list()
            # Plugin-Liste in Right Panel aktualisieren
            pass
    
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
        
        header_layout.addWidget(chat_title)
        header_layout.addStretch()
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
        
        # Input Area
        input_layout = QHBoxLayout()
        
        self.chat_input = QLineEdit()
        self.chat_input.setPlaceholderText("Type your message to CUDI_SUPREME...")
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
        
        # Dummy Plugins
        dummy_plugins = [
            "🌐 Web Research",
            "📊 Data Analysis", 
            "🎨 Creative Assistant",
            "📝 Content Writer",
            "🛠️ Task Automation"
        ]
        
        for plugin in dummy_plugins:
            item = QListWidgetItem(plugin)
            self.active_plugins_list.addItem(item)
        
        plugin_layout.addWidget(self.active_plugins_list)
        
        plugin_card.layout().addLayout(plugin_layout)
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
        
        tools_card.layout().addLayout(tools_layout)
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
        
        automation_card.layout().addLayout(automation_layout)
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
        
        monitor_card.layout().addLayout(monitor_layout)
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
                {message}
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
        
        # Input verarbeiten
        self.process_user_input(message)
    
    def process_user_input(self, message):
        """Verarbeitet User Input"""
        self.set_avatar_state("thinking")
        
        # LLM Response in Thread
        if self.llm:
            thread = threading.Thread(target=self._get_llm_response, args=(message,))
            thread.daemon = True
            thread.start()
        else:
            # Fallback response
            self.add_chat_message("🤖 CUDI", "LLM nicht verfügbar. Verwende Fallback-Antwort.")
    
    def _get_llm_response(self, message):
        """Holt LLM Response (in Thread)"""
        try:
            response = self.llm.get_response(message)
            metadata = {"confidence": 0.95, "tokens": len(response.split())}
            
            # Signal emittieren für Thread-sichere GUI-Update
            self.llm_response_ready.emit(response, metadata)
        except Exception as e:
            self.llm_response_ready.emit(f"Fehler bei LLM-Verarbeitung: {e}", {})
    
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

if __name__ == "__main__":
    app = QApplication(sys.argv)
    
    # Dark Theme für die gesamte App
    app.setStyle("Fusion")
    
    window = CUDISupremeMainWindow()
    window.show()
    
    sys.exit(app.exec())
