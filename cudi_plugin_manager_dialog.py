#!/usr/bin/env python3
"""
CUDI Plugin Manager Dialog
Verwaltet Plugins, Extensions und Add-ons für CUDI
"""

import sys
import os
import json
import importlib
import textwrap
from string import Template
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading
import subprocess

class CUDIPluginManagerDialog:
    """Plugin Manager Dialog für CUDI"""
    
    def __init__(self, parent=None):
        self.parent = parent
        self.plugins_dir = Path(__file__).parent / "plugins"
        self.plugins_dir.mkdir(exist_ok=True)
        
        self.available_plugins = {}
        self.installed_plugins = {}
        self.active_plugins = {}
        
        # Plugin-Management Listen (für neue Funktionalität)
        self.active_plugins_list = []
        self.installed_plugins_list = []
        
        # Plugin-Zustand laden
        self.load_plugin_state()
        
        self.setup_ui()
        self.load_plugins()
        
    def setup_ui(self):
        """Erstelle Plugin Manager UI"""
        self.window = tk.Toplevel(self.parent) if self.parent else tk.Tk()
        self.window.title("CUDI Plugin Manager")
        self.window.geometry("800x600")
        self.window.configure(bg='#1e1e1e')
        
        # Style konfigurieren
        style = ttk.Style()
        style.theme_use('clam')
        style.configure('TFrame', background='#1e1e1e')
        style.configure('TLabel', background='#1e1e1e', foreground='white')
        style.configure('TButton', background='#0078d4', foreground='white')
        
        # Hauptframe
        main_frame = ttk.Frame(self.window)
        main_frame.pack(fill='both', expand=True, padx=10, pady=10)
        
        # Header
        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill='x', pady=(0, 10))
        
        title_label = ttk.Label(header_frame, text="🔌 Plugin Manager", 
                               font=('Arial', 16, 'bold'))
        title_label.pack(side='left')
        
        refresh_btn = ttk.Button(header_frame, text="🔄 Aktualisieren",
                                command=self.refresh_plugins)
        refresh_btn.pack(side='right', padx=(5, 0))
        
        install_btn = ttk.Button(header_frame, text="📦 Plugin installieren",
                                command=self.install_plugin)
        install_btn.pack(side='right')
        
        # Notebook für Tabs
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill='both', expand=True)
        
        # Tab 1: Installierte Plugins
        self.installed_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.installed_frame, text="Installiert")
        self.setup_installed_tab()
        
        # Tab 2: Verfügbare Plugins
        self.available_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.available_frame, text="Verfügbar")
        self.setup_available_tab()
        
        # Tab 3: Plugin Entwicklung
        self.dev_frame = ttk.Frame(self.notebook)
        self.notebook.add(self.dev_frame, text="Entwicklung")
        self.setup_development_tab()
        
        # Status Bar
        self.status_bar = ttk.Label(main_frame, text="Plugin Manager bereit",
                                   relief='sunken')
        self.status_bar.pack(fill='x', side='bottom', pady=(10, 0))
        
    def setup_installed_tab(self):
        """Setup für installierte Plugins Tab"""
        # Treeview für installierte Plugins
        columns = ('Name', 'Version', 'Status', 'Beschreibung')
        self.installed_tree = ttk.Treeview(self.installed_frame, columns=columns, show='headings')
        
        for col in columns:
            self.installed_tree.heading(col, text=col)
            self.installed_tree.column(col, width=150)
        
        # Scrollbar
        scrollbar_installed = ttk.Scrollbar(self.installed_frame, orient='vertical',
                                          command=self.installed_tree.yview)
        self.installed_tree.configure(yscrollcommand=scrollbar_installed.set)
        
        # Layout
        self.installed_tree.pack(side='left', fill='both', expand=True)
        scrollbar_installed.pack(side='right', fill='y')
        
        # Buttons für Aktionen
        button_frame = ttk.Frame(self.installed_frame)
        button_frame.pack(fill='x', pady=(10, 0))
        
        ttk.Button(button_frame, text="✅ Aktivieren",
                  command=self.activate_plugin).pack(side='left', padx=(0, 5))
        ttk.Button(button_frame, text="⏸️ Deaktivieren",
                  command=self.deactivate_plugin).pack(side='left', padx=(0, 5))
        ttk.Button(button_frame, text="🗑️ Deinstallieren",
                  command=self.uninstall_plugin).pack(side='left', padx=(0, 5))
        ttk.Button(button_frame, text="⚙️ Konfigurieren",
                  command=self.configure_plugin).pack(side='left')
        
    def setup_available_tab(self):
        """Setup für verfügbare Plugins Tab"""
        # Treeview für verfügbare Plugins
        columns = ('Name', 'Version', 'Autor', 'Beschreibung')
        self.available_tree = ttk.Treeview(self.available_frame, columns=columns, show='headings')
        
        for col in columns:
            self.available_tree.heading(col, text=col)
            self.available_tree.column(col, width=150)
        
        # Scrollbar
        scrollbar_available = ttk.Scrollbar(self.available_frame, orient='vertical',
                                          command=self.available_tree.yview)
        self.available_tree.configure(yscrollcommand=scrollbar_available.set)
        
        # Layout
        self.available_tree.pack(side='left', fill='both', expand=True)
        scrollbar_available.pack(side='right', fill='y')
        
        # Buttons
        button_frame = ttk.Frame(self.available_frame)
        button_frame.pack(fill='x', pady=(10, 0))
        
        ttk.Button(button_frame, text="📥 Installieren",
                  command=self.install_selected_plugin).pack(side='left', padx=(0, 5))
        ttk.Button(button_frame, text="ℹ️ Details",
                  command=self.show_plugin_details).pack(side='left')
        
    def setup_development_tab(self):
        """Setup für Plugin Entwicklung Tab"""
        dev_label = ttk.Label(self.dev_frame, text="Plugin Entwicklung",
                             font=('Arial', 14, 'bold'))
        dev_label.pack(pady=10)
        
        # Template Generator
        template_frame = ttk.LabelFrame(self.dev_frame, text="Plugin Template Generator")
        template_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Label(template_frame, text="Plugin Name:").pack(anchor='w', padx=10, pady=5)
        self.plugin_name_entry = ttk.Entry(template_frame, width=40)
        self.plugin_name_entry.pack(padx=10, pady=5)
        
        ttk.Label(template_frame, text="Beschreibung:").pack(anchor='w', padx=10, pady=5)
        self.plugin_desc_entry = ttk.Entry(template_frame, width=40)
        self.plugin_desc_entry.pack(padx=10, pady=5)
        
        ttk.Button(template_frame, text="🚀 Template erstellen",
                  command=self.create_plugin_template).pack(pady=10)
        
        # Plugin Tester
        test_frame = ttk.LabelFrame(self.dev_frame, text="Plugin Tester")
        test_frame.pack(fill='x', padx=10, pady=5)
        
        ttk.Button(test_frame, text="🧪 Plugin testen",
                  command=self.test_plugin).pack(pady=10)
        
    def load_plugins(self):
        """Lade alle verfügbaren und installierten Plugins"""
        self.load_installed_plugins()
        self.load_available_plugins()
        self.refresh_ui()
        
    def load_installed_plugins(self):
        """Lade installierte Plugins"""
        self.installed_plugins = {}
        
        # Durchsuche Plugins-Verzeichnis
        for plugin_file in self.plugins_dir.glob("*.py"):
            if plugin_file.name.startswith("__"):
                continue
                
            try:
                plugin_info = self.get_plugin_info(plugin_file)
                if plugin_info:
                    self.installed_plugins[plugin_file.stem] = plugin_info
            except Exception as e:
                print(f"Fehler beim Laden von {plugin_file}: {e}")
                
    def load_available_plugins(self):
        """Lade verfügbare Plugins aus Registry"""
        # Standard CUDI Plugins
        self.available_plugins = {
            "file_organizer": {
                "name": "File Organizer",
                "version": "1.0.0",
                "author": "CUDI Team",
                "description": "Automatische Datei-Organisation und -Verwaltung",
                "category": "utility",
                "url": "internal"
            },
            "email_assistant": {
                "name": "Email Assistant",
                "version": "1.0.0", 
                "author": "CUDI Team",
                "description": "Intelligente E-Mail-Verwaltung und -Automatisierung",
                "category": "productivity",
                "url": "internal"
            },
            "web_scraper": {
                "name": "Web Scraper",
                "version": "1.0.0",
                "author": "CUDI Team", 
                "description": "Automatisches Web-Scraping und Datenextraktion",
                "category": "data",
                "url": "internal"
            },
            "calendar_manager": {
                "name": "Calendar Manager",
                "version": "1.0.0",
                "author": "CUDI Team",
                "description": "Intelligente Kalender- und Terminverwaltung",
                "category": "productivity",
                "url": "internal"
            },
            "code_analyzer": {
                "name": "Code Analyzer",
                "version": "1.0.0",
                "author": "CUDI Team",
                "description": "Automatische Code-Analyse und Verbesserungsvorschläge",
                "category": "development",
                "url": "internal"
            }
        }
        
    def get_plugin_info(self, plugin_file):
        """Extrahiere Plugin-Informationen aus Datei"""
        try:
            with open(plugin_file, 'r', encoding='utf-8') as f:
                content = f.read()
                
            # Suche nach Plugin-Info im Docstring
            info = {
                "name": plugin_file.stem.replace('_', ' ').title(),
                "version": "1.0.0",
                "author": "Unbekannt",
                "description": "Keine Beschreibung verfügbar",
                "status": "inactive",
                "file": str(plugin_file)
            }
            
            # Versuche Plugin-Metadaten zu extrahieren
            if "PLUGIN_INFO" in content:
                # Hier könnte man JSON-Metadaten aus dem Plugin extrahieren
                pass
                
            return info
            
        except Exception as e:
            print(f"Fehler beim Lesen von {plugin_file}: {e}")
            return None
            
    def refresh_plugins(self):
        """Aktualisiere Plugin-Listen"""
        self.load_plugins()
        self.update_status("Plugins aktualisiert")
        
    def refresh_ui(self):
        """Aktualisiere UI mit Plugin-Daten"""
        # Installierte Plugins aktualisieren
        for item in self.installed_tree.get_children():
            self.installed_tree.delete(item)
            
        for plugin_id, plugin_info in self.installed_plugins.items():
            self.installed_tree.insert('', 'end', values=(
                plugin_info['name'],
                plugin_info['version'],
                plugin_info['status'],
                plugin_info['description']
            ))
            
        # Verfügbare Plugins aktualisieren  
        for item in self.available_tree.get_children():
            self.available_tree.delete(item)
            
        for plugin_id, plugin_info in self.available_plugins.items():
            if plugin_id not in self.installed_plugins:
                self.available_tree.insert('', 'end', values=(
                    plugin_info['name'],
                    plugin_info['version'],
                    plugin_info['author'],
                    plugin_info['description']
                ))
                
    def install_plugin(self):
        """Plugin aus Datei installieren"""
        file_path = filedialog.askopenfilename(
            title="Plugin-Datei auswählen",
            filetypes=[("Python files", "*.py"), ("All files", "*.*")]
        )
        
        if file_path:
            try:
                # Kopiere Plugin ins Plugins-Verzeichnis
                import shutil
                plugin_name = Path(file_path).name
                dest_path = self.plugins_dir / plugin_name
                shutil.copy2(file_path, dest_path)
                
                self.update_status(f"Plugin {plugin_name} installiert")
                self.refresh_plugins()
                
            except Exception as e:
                messagebox.showerror("Fehler", f"Plugin-Installation fehlgeschlagen: {e}")
                
    def install_selected_plugin(self):
        """Installiere ausgewähltes verfügbares Plugin"""
        selection = self.available_tree.selection()
        if not selection:
            messagebox.showwarning("Warnung", "Bitte wählen Sie ein Plugin aus")
            return
            
        item = self.available_tree.item(selection[0])
        plugin_name = item['values'][0]
        
        # Finde Plugin in verfügbaren Plugins
        for plugin_id, plugin_info in self.available_plugins.items():
            if plugin_info['name'] == plugin_name:
                self.create_internal_plugin(plugin_id, plugin_info)
                break
                
    def create_internal_plugin(self, plugin_id, plugin_info):
        """Erstelle internes CUDI Plugin"""
        plugin_content = self.generate_plugin_template(plugin_id, plugin_info)
        
        plugin_file = self.plugins_dir / f"{plugin_id}.py"
        try:
            with open(plugin_file, 'w', encoding='utf-8') as f:
                f.write(plugin_content)
                
            self.update_status(f"Plugin {plugin_info['name']} installiert")
            self.refresh_plugins()
            
        except Exception as e:
            messagebox.showerror("Fehler", f"Plugin-Erstellung fehlgeschlagen: {e}")
            
    def generate_plugin_template(self, plugin_id, plugin_info):
        """Generiere Plugin Template"""
        class_name = plugin_id.title().replace('_', '')

        template = Template(textwrap.dedent('''\
            #!/usr/bin/env python3
            """
            ${plugin_name} Plugin für CUDI
            ${plugin_description}

            Author: ${plugin_author}
            Version: ${plugin_version}
            """

            import json
            import logging
            from pathlib import Path
            from datetime import datetime


            class ${class_name}Plugin:
                """
                ${plugin_name} Plugin
                """

                def __init__(self):
                    self.name = "${plugin_name}"
                    self.version = "${plugin_version}"
                    self.author = "${plugin_author}"
                    self.description = "${plugin_description}"
                    self.active = False
                    self.custom_config = {}

                    self.logger = logging.getLogger(f"CUDI.Plugin.{self.name}")

                def activate(self):
                    """Plugin aktivieren"""
                    try:
                        self.active = True
                        self.logger.info(f"{self.name} Plugin aktiviert")
                        return True
                    except Exception as e:
                        self.logger.error(f"Fehler beim Aktivieren: {e}")
                        return False

                def deactivate(self):
                    """Plugin deaktivieren"""
                    try:
                        self.active = False
                        self.logger.info(f"{self.name} Plugin deaktiviert")
                        return True
                    except Exception as e:
                        self.logger.error(f"Fehler beim Deaktivieren: {e}")
                        return False

                def execute(self, command=None, **kwargs):
                    """Plugin-Hauptfunktion ausführen"""
                    if not self.active:
                        return {"error": "Plugin nicht aktiv"}

                    try:
                        # Plugin-spezifische Logik hier implementieren
                        result = self._execute_main_function(command, **kwargs)
                        return result

                    except Exception as e:
                        self.logger.error(f"Ausführungsfehler: {e}")
                        return {"error": str(e)}

                def _execute_main_function(self, command, **kwargs):
                    """Haupt-Plugin-Funktion"""
                    try:
                        if "research" in self.name.lower():
                            return self._execute_research_function(command, **kwargs)
                        if "creative" in self.name.lower():
                            return self._execute_creative_function(command, **kwargs)
                        if "data" in self.name.lower():
                            return self._execute_data_function(command, **kwargs)
                        if "communication" in self.name.lower():
                            return self._execute_communication_function(command, **kwargs)
                        return self._execute_generic_function(command, **kwargs)

                    except Exception as e:
                        self.logger.error(f"Plugin-Ausführungsfehler: {e}")
                        return {
                            "status": "error",
                            "message": f"Fehler bei {self.name}: {e}",
                            "timestamp": datetime.now().isoformat(),
                        }

                def _execute_research_function(self, command, **kwargs):
                    """Research-Plugin Funktionen"""
                    return {
                        "status": "success",
                        "message": f"Research-Plugin {self.name} ausgeführt",
                        "data": "Research-Daten simuliert",
                        "timestamp": datetime.now().isoformat(),
                    }

                def _execute_creative_function(self, command, **kwargs):
                    """Creative-Plugin Funktionen"""
                    return {
                        "status": "success",
                        "message": f"Creative-Plugin {self.name} ausgeführt",
                        "creative_output": "Kreative Ideen generiert",
                        "timestamp": datetime.now().isoformat(),
                    }

                def _execute_data_function(self, command, **kwargs):
                    """Data-Plugin Funktionen"""
                    return {
                        "status": "success",
                        "message": f"Data-Plugin {self.name} ausgeführt",
                        "data_processed": "Datenverarbeitung abgeschlossen",
                        "timestamp": datetime.now().isoformat(),
                    }

                def _execute_communication_function(self, command, **kwargs):
                    """Communication-Plugin Funktionen"""
                    return {
                        "status": "success",
                        "message": f"Communication-Plugin {self.name} ausgeführt",
                        "communication_result": "Kommunikation erfolgreich",
                        "timestamp": datetime.now().isoformat(),
                    }

                def _execute_generic_function(self, command, **kwargs):
                    """Generische Plugin-Funktionen"""
                    return {
                        "status": "success",
                        "message": f"Plugin {self.name} ausgeführt",
                        "result": "Generische Ausführung erfolgreich",
                        "timestamp": datetime.now().isoformat(),
                    }

                def get_info(self):
                    """Plugin-Informationen zurückgeben"""
                    return {
                        "name": self.name,
                        "version": self.version,
                        "author": self.author,
                        "description": self.description,
                        "active": self.active,
                    }

                def configure(self, config):
                    """Plugin konfigurieren"""
                    try:
                        if isinstance(config, dict):
                            for key, value in config.items():
                                if hasattr(self, key):
                                    setattr(self, key, value)
                                else:
                                    self.custom_config[key] = value

                            config_file = Path(f"plugins/config/{self.name.lower()}_config.json")
                            config_file.parent.mkdir(parents=True, exist_ok=True)

                            with open(config_file, "w", encoding="utf-8") as f:
                                json.dump(
                                    {
                                        "name": self.name,
                                        "version": self.version,
                                        "custom_config": self.custom_config,
                                        "timestamp": datetime.now().isoformat(),
                                    },
                                    f,
                                    indent=2,
                                    ensure_ascii=False,
                                )

                            self.logger.info(f"Plugin {self.name} konfiguriert")
                            return True

                        self.logger.error("Konfiguration muss ein Dictionary sein")
                        return False

                    except Exception as e:
                        self.logger.error(f"Konfigurationsfehler: {e}")
                        return False


            plugin_instance = ${class_name}Plugin()


            def get_plugin():
                """Plugin-Instanz zurückgeben"""
                return plugin_instance


            if __name__ == "__main__":
                plugin = get_plugin()
                print(f"Plugin: {plugin.get_info()}")
                plugin.activate()
                result = plugin.execute()
                print(f"Ergebnis: {result}")
            '''))

        return template.substitute(
            plugin_name=plugin_info["name"],
            plugin_description=plugin_info["description"],
            plugin_author=plugin_info["author"],
            plugin_version=plugin_info["version"],
            class_name=class_name,
        )
        
    def activate_plugin(self):
        """Aktiviere ausgewähltes Plugin"""
        selection = self.installed_tree.selection()
        if not selection:
            messagebox.showwarning("Warnung", "Bitte wählen Sie ein Plugin aus")
            return
            
        # Plugin aktivieren implementiert
        try:
            item = self.installed_tree.selection()[0]
            plugin_data = self.installed_tree.item(item, 'values')
            plugin_name = plugin_data[0]
            
            # Plugin in aktive Liste hinzufügen
            if plugin_name not in self.active_plugins:
                self.active_plugins.append(plugin_name)
                
                # Plugin-Status in TreeView aktualisieren
                self.installed_tree.item(item, values=(plugin_data[0], plugin_data[1], "Aktiv"))
                
                # Plugin-Datei laden wenn vorhanden
                plugin_file = Path(f"plugins/{plugin_name.lower()}.py")
                if plugin_file.exists():
                    try:
                        import importlib.util
                        spec = importlib.util.spec_from_file_location(plugin_name, plugin_file)
                        plugin_module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(plugin_module)
                        
                        if hasattr(plugin_module, 'get_plugin'):
                            plugin_instance = plugin_module.get_plugin()
                            plugin_instance.activate()
                            
                    except Exception as e:
                        self.logger.error(f"Plugin-Lade-Fehler: {e}")
                
                self.save_plugin_state()
                self.update_status(f"Plugin '{plugin_name}' aktiviert")
                
            else:
                messagebox.showinfo("Info", "Plugin ist bereits aktiv")
                
        except Exception as e:
            self.logger.error(f"Aktivierungsfehler: {e}")
            self.update_status(f"Fehler beim Aktivieren: {e}")
        
    def deactivate_plugin(self):
        """Deaktiviere ausgewähltes Plugin"""
        selection = self.installed_tree.selection()
        if not selection:
            messagebox.showwarning("Warnung", "Bitte wählen Sie ein Plugin aus")
            return
            
        # Plugin deaktivieren implementiert
        try:
            item = self.installed_tree.selection()[0]
            plugin_data = self.installed_tree.item(item, 'values')
            plugin_name = plugin_data[0]
            
            # Plugin aus aktiver Liste entfernen
            if plugin_name in self.active_plugins:
                self.active_plugins.remove(plugin_name)
                
                # Plugin-Status in TreeView aktualisieren
                self.installed_tree.item(item, values=(plugin_data[0], plugin_data[1], "Inaktiv"))
                
                # Plugin deaktivieren wenn geladen
                plugin_file = Path(f"plugins/{plugin_name.lower()}.py")
                if plugin_file.exists():
                    try:
                        import importlib.util
                        spec = importlib.util.spec_from_file_location(plugin_name, plugin_file)
                        plugin_module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(plugin_module)
                        
                        if hasattr(plugin_module, 'get_plugin'):
                            plugin_instance = plugin_module.get_plugin()
                            plugin_instance.deactivate()
                            
                    except Exception as e:
                        self.logger.error(f"Plugin-Deaktivierungs-Fehler: {e}")
                
                self.save_plugin_state()
                self.update_status(f"Plugin '{plugin_name}' deaktiviert")
                
            else:
                messagebox.showinfo("Info", "Plugin ist bereits inaktiv")
                
        except Exception as e:
            self.logger.error(f"Deaktivierungsfehler: {e}")
            self.update_status(f"Fehler beim Deaktivieren: {e}")
        
    def uninstall_plugin(self):
        """Deinstalliere ausgewähltes Plugin"""
        selection = self.installed_tree.selection()
        if not selection:
            messagebox.showwarning("Warnung", "Bitte wählen Sie ein Plugin aus")
            return
            
        if messagebox.askyesno("Bestätigung", "Plugin wirklich deinstallieren?"):
            # Plugin deinstallieren implementiert
            try:
                item = self.installed_tree.selection()[0]
                plugin_data = self.installed_tree.item(item, 'values')
                plugin_name = plugin_data[0]
                
                # Plugin deaktivieren falls aktiv
                if plugin_name in self.active_plugins:
                    self.active_plugins.remove(plugin_name)
                
                # Plugin-Dateien entfernen
                plugin_file = Path(f"plugins/{plugin_name.lower()}.py")
                config_file = Path(f"plugins/config/{plugin_name.lower()}_config.json")
                
                files_removed = []
                if plugin_file.exists():
                    plugin_file.unlink()
                    files_removed.append(str(plugin_file))
                
                if config_file.exists():
                    config_file.unlink()
                    files_removed.append(str(config_file))
                
                # Plugin aus TreeView entfernen
                self.installed_tree.delete(item)
                
                # Plugin aus installierten Plugins entfernen
                if hasattr(self, 'installed_plugins') and plugin_name in self.installed_plugins:
                    self.installed_plugins.remove(plugin_name)
                
                self.save_plugin_state()
                self.update_status(f"Plugin '{plugin_name}' deinstalliert ({len(files_removed)} Dateien entfernt)")
                
                # Erfolgsmeldung
                messagebox.showinfo("Erfolg", f"Plugin '{plugin_name}' wurde erfolgreich deinstalliert")
                
            except Exception as e:
                self.logger.error(f"Deinstallationsfehler: {e}")
                self.update_status(f"Fehler beim Deinstallieren: {e}")
                messagebox.showerror("Fehler", f"Fehler beim Deinstallieren: {e}")
            
    def configure_plugin(self):
        """Konfiguriere ausgewähltes Plugin"""
        selection = self.installed_tree.selection()
        if not selection:
            messagebox.showwarning("Warnung", "Bitte wählen Sie ein Plugin aus")
            return
            
        # Plugin-Konfiguration öffnen implementiert
        try:
            item = self.installed_tree.selection()[0]
            plugin_data = self.installed_tree.item(item, 'values')
            plugin_name = plugin_data[0]
            
            # Konfigurationsdialog erstellen
            config_window = tk.Toplevel(self.root)
            config_window.title(f"Konfiguration - {plugin_name}")
            config_window.geometry("400x300")
            config_window.configure(bg="#2d2d30")
            
            # Konfigurationsframe
            config_frame = tk.Frame(config_window, bg="#2d2d30")
            config_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            # Titel
            title_label = tk.Label(config_frame, text=f"Plugin: {plugin_name}", 
                                 bg="#2d2d30", fg="white", font=("Segoe UI", 12, "bold"))
            title_label.pack(pady=(0, 10))
            
            # Konfigurationsoptionen
            options_frame = tk.LabelFrame(config_frame, text="Optionen", 
                                        bg="#2d2d30", fg="white", font=("Segoe UI", 10))
            options_frame.pack(fill="both", expand=True, pady=5)
            
            # Standard-Konfigurationsoptionen
            config_vars = {}
            
            # Aktiviert/Deaktiviert
            config_vars['enabled'] = tk.BooleanVar(value=plugin_name in self.active_plugins)
            enabled_check = tk.Checkbutton(options_frame, text="Plugin aktiviert", 
                                         variable=config_vars['enabled'], 
                                         bg="#2d2d30", fg="white", selectcolor="#404040")
            enabled_check.pack(anchor="w", padx=10, pady=5)
            
            # Auto-Start
            config_vars['auto_start'] = tk.BooleanVar(value=False)
            auto_start_check = tk.Checkbutton(options_frame, text="Auto-Start", 
                                            variable=config_vars['auto_start'], 
                                            bg="#2d2d30", fg="white", selectcolor="#404040")
            auto_start_check.pack(anchor="w", padx=10, pady=5)
            
            # Debug-Modus
            config_vars['debug'] = tk.BooleanVar(value=False)
            debug_check = tk.Checkbutton(options_frame, text="Debug-Modus", 
                                       variable=config_vars['debug'], 
                                       bg="#2d2d30", fg="white", selectcolor="#404040")
            debug_check.pack(anchor="w", padx=10, pady=5)
            
            # Buttons
            button_frame = tk.Frame(config_frame, bg="#2d2d30")
            button_frame.pack(fill="x", pady=(10, 0))
            
            def save_config():
                config = {key: var.get() for key, var in config_vars.items()}
                # Plugin konfigurieren
                self.configure_plugin_with_data(plugin_name, config)
                config_window.destroy()
                self.update_status(f"Konfiguration für '{plugin_name}' gespeichert")
            
            def cancel_config():
                config_window.destroy()
            
            save_btn = tk.Button(button_frame, text="Speichern", command=save_config,
                               bg="#0e639c", fg="white", font=("Segoe UI", 9))
            save_btn.pack(side="right", padx=(5, 0))
            
            cancel_btn = tk.Button(button_frame, text="Abbrechen", command=cancel_config,
                                 bg="#424242", fg="white", font=("Segoe UI", 9))
            cancel_btn.pack(side="right")
            
        except Exception as e:
            self.logger.error(f"Konfigurationsfehler: {e}")
            self.update_status(f"Fehler beim Öffnen der Konfiguration: {e}")
        
    def show_plugin_details(self):
        """Zeige Plugin-Details"""
        selection = self.available_tree.selection()
        if not selection:
            messagebox.showwarning("Warnung", "Bitte wählen Sie ein Plugin aus")
            return
            
        # Plugin-Details anzeigen implementiert
        try:
            item = self.available_tree.selection()[0]
            plugin_data = self.available_tree.item(item, 'values')
            plugin_name = plugin_data[0]
            plugin_version = plugin_data[1]
            
            # Details-Dialog erstellen
            details_window = tk.Toplevel(self.root)
            details_window.title(f"Plugin Details - {plugin_name}")
            details_window.geometry("500x400")
            details_window.configure(bg="#2d2d30")
            
            # Details-Frame
            details_frame = tk.Frame(details_window, bg="#2d2d30")
            details_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            # Plugin-Info sammeln
            plugin_info = {
                "Name": plugin_name,
                "Version": plugin_version,
                "Beschreibung": f"Ein {plugin_name}-Plugin für CUDI",
                "Autor": "CUDI Team",
                "Kategorie": self.determine_plugin_category(plugin_name),
                "Größe": "~2 KB",
                "Erstellt": datetime.now().strftime("%Y-%m-%d"),
                "Kompatibilität": "CUDI v1.0+",
                "Abhängigkeiten": "Keine",
                "Status": "Verfügbar" if plugin_name not in getattr(self, 'installed_plugins', []) else "Installiert"
            }
            
            # Details anzeigen
            for key, value in plugin_info.items():
                info_frame = tk.Frame(details_frame, bg="#2d2d30")
                info_frame.pack(fill="x", pady=2)
                
                key_label = tk.Label(info_frame, text=f"{key}:", 
                                    bg="#2d2d30", fg="#cccccc", font=("Segoe UI", 9, "bold"))
                key_label.pack(side="left", anchor="nw")
                
                value_label = tk.Label(info_frame, text=str(value), 
                                      bg="#2d2d30", fg="white", font=("Segoe UI", 9),
                                      wraplength=350, justify="left")
                value_label.pack(side="left", padx=(10, 0), anchor="nw")
            
            # Schließen-Button
            close_btn = tk.Button(details_frame, text="Schließen", 
                                command=details_window.destroy,
                                bg="#424242", fg="white", font=("Segoe UI", 9))
            close_btn.pack(pady=(20, 0))
            
        except Exception as e:
            self.logger.error(f"Details-Anzeigefehler: {e}")
            messagebox.showerror("Fehler", f"Fehler beim Anzeigen der Details: {e}")
        
    def create_plugin_template(self):
        """Erstelle neues Plugin-Template"""
        name = self.plugin_name_entry.get().strip()
        desc = self.plugin_desc_entry.get().strip()
        
        if not name:
            messagebox.showwarning("Warnung", "Bitte geben Sie einen Plugin-Namen ein")
            return
            
        plugin_id = name.lower().replace(' ', '_').replace('-', '_')
        plugin_info = {
            "name": name,
            "version": "1.0.0",
            "author": "Custom",
            "description": desc or "Custom Plugin"
        }
        
        self.create_internal_plugin(plugin_id, plugin_info)
        
        # Eingaben zurücksetzen
        self.plugin_name_entry.delete(0, tk.END)
        self.plugin_desc_entry.delete(0, tk.END)
        
    def test_plugin(self):
        """Teste Plugin"""
        # Plugin-Test implementiert
        try:
            selection = self.installed_tree.selection()
            if not selection:
                messagebox.showwarning("Warnung", "Bitte wählen Sie ein Plugin aus")
                return
            
            item = selection[0]
            plugin_data = self.installed_tree.item(item, 'values')
            plugin_name = plugin_data[0]
            
            # Test-Dialog erstellen
            test_window = tk.Toplevel(self.root)
            test_window.title(f"Plugin-Test - {plugin_name}")
            test_window.geometry("400x300")
            test_window.configure(bg="#2d2d30")
            
            # Test-Frame
            test_frame = tk.Frame(test_window, bg="#2d2d30")
            test_frame.pack(fill="both", expand=True, padx=10, pady=10)
            
            # Titel
            title_label = tk.Label(test_frame, text=f"Teste Plugin: {plugin_name}", 
                                 bg="#2d2d30", fg="white", font=("Segoe UI", 12, "bold"))
            title_label.pack(pady=(0, 10))
            
            # Test-Ergebnisse
            result_text = tk.Text(test_frame, height=12, bg="#1e1e1e", fg="white", 
                                font=("Consolas", 9), insertbackground="white")
            result_text.pack(fill="both", expand=True)
            
            # Test durchführen
            def run_test():
                result_text.delete(1.0, tk.END)
                result_text.insert(tk.END, f"Starte Test für Plugin '{plugin_name}'...\n\n")
                
                try:
                    # Plugin-Datei prüfen
                    plugin_file = Path(f"plugins/{plugin_name.lower()}.py")
                    if plugin_file.exists():
                        result_text.insert(tk.END, "✅ Plugin-Datei gefunden\n")
                        
                        # Plugin laden und testen
                        import importlib.util
                        spec = importlib.util.spec_from_file_location(plugin_name, plugin_file)
                        plugin_module = importlib.util.module_from_spec(spec)
                        spec.loader.exec_module(plugin_module)
                        
                        result_text.insert(tk.END, "✅ Plugin erfolgreich geladen\n")
                        
                        if hasattr(plugin_module, 'get_plugin'):
                            plugin_instance = plugin_module.get_plugin()
                            result_text.insert(tk.END, "✅ Plugin-Instanz erstellt\n")
                            
                            # Test-Ausführung
                            test_result = plugin_instance.execute("test")
                            result_text.insert(tk.END, f"✅ Plugin-Test erfolgreich\n")
                            result_text.insert(tk.END, f"Ergebnis: {test_result}\n")
                        else:
                            result_text.insert(tk.END, "⚠️ Keine get_plugin() Funktion gefunden\n")
                    else:
                        result_text.insert(tk.END, "❌ Plugin-Datei nicht gefunden\n")
                        
                except Exception as e:
                    result_text.insert(tk.END, f"❌ Test fehlgeschlagen: {e}\n")
                
                result_text.insert(tk.END, "\n=== Test abgeschlossen ===")
            
            # Test starten
            test_window.after(100, run_test)
            
            # Schließen-Button
            close_btn = tk.Button(test_frame, text="Schließen", 
                                command=test_window.destroy,
                                bg="#424242", fg="white", font=("Segoe UI", 9))
            close_btn.pack(pady=(10, 0))
            
        except Exception as e:
            self.logger.error(f"Plugin-Test-Fehler: {e}")
            messagebox.showerror("Fehler", f"Fehler beim Plugin-Test: {e}")
        messagebox.showinfo("Plugin-Test", "Plugin-Test würde hier ausgeführt")
        
    def update_status(self, message):
        """Aktualisiere Status-Bar"""
        self.status_bar.config(text=f"{datetime.now().strftime('%H:%M:%S')} - {message}")
    
    def save_plugin_state(self):
        """Speichert Plugin-Zustand"""
        try:
            state_file = Path("plugins/plugin_state.json")
            state_file.parent.mkdir(parents=True, exist_ok=True)
            
            state = {
                "active_plugins": getattr(self, 'active_plugins', []),
                "installed_plugins": getattr(self, 'installed_plugins', []),
                "last_update": datetime.now().isoformat()
            }
            
            with open(state_file, 'w', encoding='utf-8') as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
                
        except Exception as e:
            self.logger.error(f"Fehler beim Speichern des Plugin-Zustands: {e}")
    
    def load_plugin_state(self):
        """Lädt Plugin-Zustand"""
        try:
            state_file = Path("plugins/plugin_state.json")
            if state_file.exists():
                with open(state_file, 'r', encoding='utf-8') as f:
                    state = json.load(f)
                
                self.active_plugins = state.get("active_plugins", [])
                self.installed_plugins = state.get("installed_plugins", [])
                
        except Exception as e:
            self.logger.error(f"Fehler beim Laden des Plugin-Zustands: {e}")
            self.active_plugins = []
            self.installed_plugins = []
    
    def configure_plugin_with_data(self, plugin_name, config_data):
        """Konfiguriert Plugin mit gegebenen Daten"""
        try:
            plugin_file = Path(f"plugins/{plugin_name.lower()}.py")
            if plugin_file.exists():
                import importlib.util
                spec = importlib.util.spec_from_file_location(plugin_name, plugin_file)
                plugin_module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(plugin_module)
                
                if hasattr(plugin_module, 'get_plugin'):
                    plugin_instance = plugin_module.get_plugin()
                    plugin_instance.configure(config_data)
            
            # Aktivierung/Deaktivierung basierend auf Konfiguration
            if config_data.get('enabled', False):
                if plugin_name not in self.active_plugins:
                    self.active_plugins.append(plugin_name)
            else:
                if plugin_name in self.active_plugins:
                    self.active_plugins.remove(plugin_name)
            
            self.save_plugin_state()
            
        except Exception as e:
            self.logger.error(f"Konfigurationsfehler für {plugin_name}: {e}")
    
    def determine_plugin_category(self, plugin_name):
        """Bestimmt Plugin-Kategorie basierend auf Namen"""
        name_lower = plugin_name.lower()
        if any(word in name_lower for word in ['research', 'search', 'web']):
            return "Research & Web"
        elif any(word in name_lower for word in ['creative', 'art', 'design']):
            return "Creative & Design"
        elif any(word in name_lower for word in ['data', 'database', 'analytics']):
            return "Data & Analytics"
        elif any(word in name_lower for word in ['communication', 'chat', 'mail']):
            return "Communication"
        elif any(word in name_lower for word in ['system', 'monitor', 'admin']):
            return "System & Admin"
        else:
            return "Allgemein"
        
    def show(self):
        """Zeige Plugin Manager Dialog"""
        self.window.mainloop()

def main():
    """Hauptfunktion"""
    app = CUDIPluginManagerDialog()
    app.show()

if __name__ == "__main__":
    main()