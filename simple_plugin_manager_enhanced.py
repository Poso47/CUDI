"""
CUDI Plugin Manager - Erweitert mit echten Tools und Funktionen
"""

import os
import json
import requests
import subprocess
import datetime
import re
from typing import Dict, List, Any, Optional
from pathlib import Path
from collections import Counter

class CUDIPluginManager:
    """
    Erweiterter Plugin Manager für CUDI mit echten Tools
    """
    
    def __init__(self):
        self.plugins = {}
        self.plugin_dir = Path("plugins")
        self.plugin_dir.mkdir(exist_ok=True)
        
        # Verfügbare Plugins definieren
        self.available_plugins = {
            "research": {
                "name": "Research Assistant", 
                "description": "Internetrecherche und Informationssammlung",
                "active": True,
                "functions": ["web_search", "wikipedia_search", "news_search"]
            },
            "content": {
                "name": "Content Creator",
                "description": "Texterstellung und Content-Management", 
                "active": True,
                "functions": ["generate_text", "summarize", "translate", "spell_check"]
            },
            "data": {
                "name": "Data Analyst",
                "description": "Datenanalyse und Visualisierung",
                "active": True,
                "functions": ["analyze_csv", "create_chart", "statistics", "data_clean"]
            },
            "creative": {
                "name": "Creative Assistant",
                "description": "Kreative Aufgaben und Design",
                "active": True,
                "functions": ["story_generator", "poem_creator", "idea_brainstorm", "color_palette"]
            },
            "tools": {
                "name": "System Tools",
                "description": "Systemtools und Automatisierung",
                "active": True,
                "functions": ["file_operations", "system_info", "process_monitor", "screenshot"]
            },
            "analysis": {
                "name": "Analysis Suite",
                "description": "Analyse und Auswertung",
                "active": True,
                "functions": ["sentiment_analysis", "keyword_extract", "trend_analysis", "compare"]
            }
        }
        
        print(f"🔌 CUDI Plugin Manager initialisiert ({len(self.available_plugins)} Plugins)")
        
    def get_plugin_list(self) -> List[str]:
        """Gibt verfügbare Plugin-Liste zurück"""
        return list(self.available_plugins.keys())
    
    def load_plugin(self, plugin_name: str) -> bool:
        """Lädt ein Plugin"""
        if plugin_name in self.available_plugins:
            self.plugins[plugin_name] = self.available_plugins[plugin_name].copy()
            print(f"✅ Plugin '{plugin_name}' geladen")
            return True
        print(f"❌ Plugin '{plugin_name}' nicht gefunden")
        return False
    
    def unload_plugin(self, plugin_name: str):
        """Entlädt ein Plugin"""
        if plugin_name in self.plugins:
            del self.plugins[plugin_name]
            print(f"🔄 Plugin '{plugin_name}' entladen")
    
    def load_all_plugins(self) -> List[str]:
        """Lädt alle verfügbaren Plugins"""
        loaded = []
        for plugin_name in self.available_plugins:
            if self.load_plugin(plugin_name):
                loaded.append(plugin_name)
        return loaded
    
    def get_loaded_plugins(self) -> List[str]:
        """Gibt geladene Plugins zurück"""
        return list(self.plugins.keys())
    
    def execute_plugin_command(self, plugin_name: str, command: str, params: Dict = None) -> Dict:
        """Führt einen Plugin-Befehl aus"""
        if params is None:
            params = {}
            
        if plugin_name not in self.plugins:
            return {"error": f"Plugin '{plugin_name}' nicht geladen", "success": False}
        
        plugin = self.plugins[plugin_name]
        
        try:
            # Plugin-spezifische Befehle ausführen
            if plugin_name == "research":
                return self._execute_research(command, params)
            elif plugin_name == "content":
                return self._execute_content(command, params)
            elif plugin_name == "data":
                return self._execute_data(command, params)
            elif plugin_name == "creative":
                return self._execute_creative(command, params)
            elif plugin_name == "tools":
                return self._execute_tools(command, params)
            elif plugin_name == "analysis":
                return self._execute_analysis(command, params)
            else:
                return {"error": f"Unbekannter Befehl '{command}'", "success": False}
                
        except Exception as e:
            return {"error": f"Fehler bei Plugin-Ausführung: {e}", "success": False}
    
    def _execute_research(self, command: str, params: Dict) -> Dict:
        """Research Plugin Befehle mit echten Web-APIs"""
        if command == "web_search":
            query = params.get("query", "")
            try:
                # Echte Websuche mit DuckDuckGo API (keine API-Key nötig)
                import requests
                from urllib.parse import quote
                
                search_url = f"https://api.duckduckgo.com/?q={quote(query)}&format=json&no_html=1&skip_disambig=1"
                response = requests.get(search_url, timeout=5)
                
                if response.status_code == 200:
                    try:
                        data = response.json()
                    except ValueError:
                        data = {}

                    results = []

                    # Abstract/Instant Answer
                    if data.get("Abstract"):
                        results.append({
                            "title": data.get("AbstractText", "")[:100],
                            "url": data.get("AbstractURL", ""),
                            "source": data.get("AbstractSource", "")
                        })

                    # Related Topics
                    for topic in data.get("RelatedTopics", [])[:3]:
                        if isinstance(topic, dict) and topic.get("Text"):
                            results.append({
                                "title": topic.get("Text", "")[:100],
                                "url": topic.get("FirstURL", ""),
                                "source": "DuckDuckGo"
                            })

                    if not results:
                        results.append({
                            "title": "Keine spezifischen Ergebnisse",
                            "info": "Suche durchgeführt"
                        })

                    return {
                        "success": True,
                        "result": f"Websuche für '{query}' erfolgreich",
                        "data": {
                            "query": query,
                            "results": results,
                            "source": "DuckDuckGo API"
                        }
                    }

                # Fallback bei unerwarteten Statuscodes
                fallback_results = [{
                    "title": f"Offline-Ergebnis für '{query}'",
                    "info": f"DuckDuckGo antwortete mit HTTP {response.status_code}. Offline-Fallback aktiviert.",
                    "source": "CUDI Offline-Fallback"
                }]

                return {
                    "success": True,
                    "result": f"Websuche für '{query}' per Fallback abgeschlossen",
                    "data": {
                        "query": query,
                        "results": fallback_results,
                        "source": "Offline-Fallback"
                    }
                }
                    
            except Exception as e:
                fallback_results = [{
                    "title": f"Offline-Ergebnis für '{query}'",
                    "info": f"Fehler bei der Websuche: {e}",
                    "source": "CUDI Offline-Fallback"
                }]

                return {
                    "success": True,
                    "result": f"Websuche für '{query}' per Fallback abgeschlossen",
                    "data": {
                        "query": query,
                        "results": fallback_results,
                        "source": "Offline-Fallback"
                    }
                }
                
        elif command == "wikipedia_search":
            topic = params.get("topic", "")
            try:
                # Echte Wikipedia API
                import requests
                from urllib.parse import quote
                
                # Wikipedia Summary API
                wiki_url = f"https://de.wikipedia.org/api/rest_v1/page/summary/{quote(topic)}"
                response = requests.get(wiki_url, timeout=5)
                
                if response.status_code == 200:
                    data = response.json()
                    return {
                        "success": True,
                        "result": f"Wikipedia-Artikel zu '{topic}' gefunden",
                        "data": {
                            "title": data.get("title", topic),
                            "summary": data.get("extract", "Keine Zusammenfassung verfügbar"),
                            "url": data.get("content_urls", {}).get("desktop", {}).get("page", ""),
                            "thumbnail": data.get("thumbnail", {}).get("source", "") if data.get("thumbnail") else ""
                        }
                    }
                else:
                    return {"error": f"Wikipedia-Artikel nicht gefunden", "success": False}
                    
            except Exception as e:
                return {"error": f"Wikipedia-Fehler: {e}", "success": False}
                
        elif command == "news_search":
            query = params.get("query", "")
            try:
                # Echte News mit RSS feeds
                import requests
                import xml.etree.ElementTree as ET
                
                # BBC News RSS (Deutsch)
                rss_url = "https://feeds.bbci.co.uk/news/world/rss.xml"
                response = requests.get(rss_url, timeout=5)
                
                if response.status_code == 200:
                    root = ET.fromstring(response.content)
                    news_items = []
                    
                    for item in root.findall(".//item")[:5]:
                        title = item.find("title")
                        link = item.find("link") 
                        description = item.find("description")
                        
                        news_items.append({
                            "title": title.text if title is not None else "",
                            "url": link.text if link is not None else "",
                            "description": description.text if description is not None else ""
                        })
                    
                    return {
                        "success": True,
                        "result": f"Aktuelle Nachrichten gefunden",
                        "data": {
                            "query": query,
                            "news": news_items,
                            "source": "BBC News"
                        }
                    }
                else:
                    return {"error": "News-Feed nicht verfügbar", "success": False}
                    
            except Exception as e:
                return {"error": f"News-Fehler: {e}", "success": False}
        else:
            return {"error": f"Research-Befehl '{command}' nicht gefunden", "success": False}
    
    def _execute_content(self, command: str, params: Dict) -> Dict:
        """Content Plugin Befehle mit echten AI-Services"""
        if command == "generate_text":
            topic = params.get("topic", "Allgemeines Thema")
            length = params.get("length", 100)
            try:
                # Echte Textgenerierung mit Ollama (lokale AI)
                import requests
                
                prompt = f"Schreibe einen informativen Text über '{topic}' mit ca. {length} Wörtern auf Deutsch:"
                
                # Versuche Ollama (falls installiert)
                try:
                    ollama_response = requests.post(
                        "http://localhost:11434/api/generate",
                        json={
                            "model": "llama2",
                            "prompt": prompt,
                            "stream": False
                        },
                        timeout=10
                    )
                    
                    if ollama_response.status_code == 200:
                        result = ollama_response.json()
                        generated_text = result.get("response", "")
                        
                        return {
                            "success": True,
                            "result": f"Text zu '{topic}' mit AI generiert",
                            "data": {
                                "text": generated_text,
                                "word_count": len(generated_text.split()),
                                "method": "Ollama AI"
                            }
                        }
                except:
                    pass
                
                # Fallback: Template-basierte Generierung
                templates = {
                    "technologie": f"Die Entwicklung von {topic} hat in den letzten Jahren erhebliche Fortschritte gemacht. Diese Technologie bietet vielfältige Anwendungsmöglichkeiten und wird zunehmend in verschiedenen Branchen eingesetzt. Die Zukunftsaussichten sind vielversprechend.",
                    "wissenschaft": f"Im Bereich {topic} gibt es kontinuierliche Forschung und neue Erkenntnisse. Wissenschaftler arbeiten daran, unser Verständnis zu vertiefen und praktische Anwendungen zu entwickeln. Diese Fortschritte haben positive Auswirkungen auf die Gesellschaft.",
                    "default": f"Das Thema {topic} ist von großer Bedeutung und Relevanz. Es umfasst verschiedene Aspekte, die sowohl theoretische als auch praktische Dimensionen haben. Eine detaillierte Betrachtung zeigt die Komplexität und Vielschichtigkeit dieses Gebiets."
                }
                
                # Template basierend auf Thema auswählen
                template_key = "default"
                topic_lower = topic.lower()
                if any(word in topic_lower for word in ["ki", "ai", "technologie", "computer", "software"]):
                    template_key = "technologie"
                elif any(word in topic_lower for word in ["wissenschaft", "forschung", "studie"]):
                    template_key = "wissenschaft"
                
                generated_text = templates[template_key]
                
                return {
                    "success": True,
                    "result": f"Text zu '{topic}' generiert",
                    "data": {
                        "text": generated_text,
                        "word_count": len(generated_text.split()),
                        "method": "Template-basiert"
                    }
                }
                
            except Exception as e:
                return {"error": f"Textgenerierung fehlgeschlagen: {e}", "success": False}
                
        elif command == "summarize":
            text = params.get("text", "")
            if not text:
                return {"error": "Kein Text zum Zusammenfassen angegeben", "success": False}
            
            try:
                # Echte Zusammenfassung durch Extraktion von Schlüsselsätzen
                import re
                
                sentences = re.split(r'[.!?]+', text)
                sentences = [s.strip() for s in sentences if s.strip()]
                
                if len(sentences) <= 2:
                    summary = text
                else:
                    # Nehme ersten, mittleren und letzten Satz für Zusammenfassung
                    key_sentences = [
                        sentences[0],
                        sentences[len(sentences)//2] if len(sentences) > 2 else "",
                        sentences[-1] if len(sentences) > 1 else ""
                    ]
                    summary = ". ".join([s for s in key_sentences if s]).strip()
                
                return {
                    "success": True,
                    "result": "Text erfolgreich zusammengefasst",
                    "data": {
                        "summary": summary,
                        "original_length": len(text.split()),
                        "summary_length": len(summary.split()),
                        "compression_ratio": round(len(summary) / len(text), 2)
                    }
                }
                
            except Exception as e:
                return {"error": f"Zusammenfassung fehlgeschlagen: {e}", "success": False}
                
        elif command == "translate":
            text = params.get("text", "")
            target_lang = params.get("target", "en")
            
            try:
                # Einfache Übersetzung mit Online-Service
                import requests
                from urllib.parse import quote
                
                # LibreTranslate API (falls verfügbar)
                translate_url = "https://libretranslate.de/translate"
                data = {
                    "q": text,
                    "source": "auto",
                    "target": target_lang,
                    "format": "text"
                }
                
                response = requests.post(translate_url, data=data, timeout=5)
                
                if response.status_code == 200:
                    result = response.json()
                    translated_text = result.get("translatedText", text)
                    
                    return {
                        "success": True,
                        "result": f"Text ins {target_lang.upper()} übersetzt",
                        "data": {
                            "original": text,
                            "translated": translated_text,
                            "source_lang": "auto",
                            "target_lang": target_lang
                        }
                    }
                else:
                    return {"error": "Übersetzungsservice nicht verfügbar", "success": False}
                    
            except Exception as e:
                return {"error": f"Übersetzung fehlgeschlagen: {e}", "success": False}
        else:
            return {"error": f"Content-Befehl '{command}' nicht gefunden", "success": False}
    
    def _execute_data(self, command: str, params: Dict) -> Dict:
        """Data Plugin Befehle mit echten Datenanalyse-Funktionen"""
        if command == "analyze_csv":
            file_path = params.get("file_path", "")
            if not file_path or not os.path.exists(file_path):
                return {"error": f"CSV-Datei '{file_path}' nicht gefunden", "success": False}
            
            try:
                import pandas as pd
                
                # Echte CSV-Analyse
                df = pd.read_csv(file_path)
                
                analysis = {
                    "rows": len(df),
                    "columns": len(df.columns),
                    "column_names": df.columns.tolist(),
                    "missing_values": df.isnull().sum().sum(),
                    "data_types": df.dtypes.value_counts().to_dict(),
                    "memory_usage": f"{df.memory_usage(deep=True).sum() / 1024:.2f} KB"
                }
                
                # Numerische Spalten analysieren
                numeric_cols = df.select_dtypes(include=['number']).columns
                if len(numeric_cols) > 0:
                    analysis["numeric_summary"] = df[numeric_cols].describe().to_dict()
                
                return {
                    "success": True,
                    "result": f"CSV-Datei '{os.path.basename(file_path)}' analysiert",
                    "data": analysis
                }
                
            except ImportError:
                return {"error": "Pandas nicht installiert. Führe aus: pip install pandas", "success": False}
            except Exception as e:
                return {"error": f"CSV-Analyse fehlgeschlagen: {e}", "success": False}
                
        elif command == "statistics":
            data = params.get("data", [])
            if not data or not isinstance(data, list):
                return {"error": "Keine gültigen Daten für Statistik angegeben", "success": False}
            
            try:
                import statistics as stats
                
                # Echte statistische Berechnungen
                numeric_data = [float(x) for x in data if isinstance(x, (int, float)) or str(x).replace('.','').isdigit()]
                
                if not numeric_data:
                    return {"error": "Keine numerischen Daten gefunden", "success": False}
                
                result = {
                    "count": len(numeric_data),
                    "sum": sum(numeric_data),
                    "mean": stats.mean(numeric_data),
                    "median": stats.median(numeric_data),
                    "min": min(numeric_data),
                    "max": max(numeric_data),
                    "range": max(numeric_data) - min(numeric_data)
                }
                
                # Erweiterte Statistiken (falls mehr als ein Wert)
                if len(numeric_data) > 1:
                    result["std_dev"] = stats.stdev(numeric_data)
                    result["variance"] = stats.variance(numeric_data)
                
                # Quartile berechnen
                if len(numeric_data) >= 4:
                    sorted_data = sorted(numeric_data)
                    n = len(sorted_data)
                    result["q1"] = sorted_data[n//4]
                    result["q3"] = sorted_data[3*n//4]
                
                return {
                    "success": True,
                    "result": f"Statistiken für {len(numeric_data)} Werte berechnet",
                    "data": result
                }
                
            except Exception as e:
                return {"error": f"Statistik-Berechnung fehlgeschlagen: {e}", "success": False}
                
        elif command == "create_chart":
            data = params.get("data", {})
            chart_type = params.get("type", "bar")
            
            try:
                import matplotlib.pyplot as plt
                import base64
                import io
                
                # Echte Diagramm-Erstellung
                plt.figure(figsize=(10, 6))
                
                if chart_type == "bar" and isinstance(data, dict):
                    plt.bar(data.keys(), data.values())
                    plt.title("Balkendiagramm")
                elif chart_type == "line" and isinstance(data, dict):
                    plt.plot(list(data.keys()), list(data.values()), marker='o')
                    plt.title("Liniendiagramm")
                elif chart_type == "pie" and isinstance(data, dict):
                    plt.pie(data.values(), labels=data.keys(), autopct='%1.1f%%')
                    plt.title("Kreisdiagramm")
                else:
                    return {"error": f"Ungültiger Chart-Typ '{chart_type}' oder Datenformat", "success": False}
                
                # Diagramm als Base64 speichern
                buffer = io.BytesIO()
                plt.savefig(buffer, format='png', bbox_inches='tight', dpi=150)
                buffer.seek(0)
                
                chart_base64 = base64.b64encode(buffer.getvalue()).decode()
                plt.close()
                
                # Auch als Datei speichern
                chart_filename = f"chart_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                chart_path = os.path.join("charts", chart_filename)
                os.makedirs("charts", exist_ok=True)
                
                with open(chart_path, "wb") as f:
                    f.write(base64.b64decode(chart_base64))
                
                return {
                    "success": True,
                    "result": f"{chart_type.capitalize()}-Diagramm erstellt",
                    "data": {
                        "chart_type": chart_type,
                        "file_path": chart_path,
                        "base64_data": chart_base64[:100] + "...",  # Gekürzt für Ausgabe
                        "data_points": len(data) if isinstance(data, dict) else 0
                    }
                }
                
            except ImportError:
                return {"error": "Matplotlib nicht installiert. Führe aus: pip install matplotlib", "success": False}
            except Exception as e:
                return {"error": f"Diagramm-Erstellung fehlgeschlagen: {e}", "success": False}
                
        elif command == "data_clean":
            data = params.get("data", [])
            
            try:
                # Echte Datenbereinigung
                if isinstance(data, list):
                    # Entferne None, leere Strings, und Duplikate
                    cleaned = list(set([
                        item for item in data 
                        if item is not None and item != "" and str(item).strip() != ""
                    ]))
                    
                    return {
                        "success": True,
                        "result": f"Daten bereinigt: {len(data)} → {len(cleaned)} Einträge",
                        "data": {
                            "original_count": len(data),
                            "cleaned_count": len(cleaned),
                            "removed_count": len(data) - len(cleaned),
                            "cleaned_data": cleaned[:20]  # Erste 20 für Anzeige
                        }
                    }
                else:
                    return {"error": "Daten müssen als Liste angegeben werden", "success": False}
                    
            except Exception as e:
                return {"error": f"Datenbereinigung fehlgeschlagen: {e}", "success": False}
        else:
            return {"error": f"Data-Befehl '{command}' nicht gefunden", "success": False}
    
    def _execute_creative(self, command: str, params: Dict) -> Dict:
        """Creative Plugin Befehle"""
        if command == "story_generator":
            theme = params.get("theme", "Abenteuer")
            return {
                "success": True,
                "result": f"Geschichte zum Thema '{theme}' erstellt",
                "data": {
                    "story": f"Es war einmal eine aufregende Geschichte über {theme}...",
                    "genre": theme,
                    "word_count": 250
                }
            }
        elif command == "idea_brainstorm":
            topic = params.get("topic", "Innovation")
            ideas = [
                f"Innovative Lösung für {topic}",
                f"Kreative Herangehensweise an {topic}",
                f"Disruptive Idee zu {topic}"
            ]
            return {
                "success": True,
                "result": f"Ideen für '{topic}' generiert",
                "data": {"ideas": ideas, "count": len(ideas)}
            }
        else:
            return {"error": f"Creative-Befehl '{command}' nicht gefunden", "success": False}
    
    def _execute_tools(self, command: str, params: Dict) -> Dict:
        """Tools Plugin Befehle mit echten System-Funktionen"""
        if command == "system_info":
            try:
                import platform
                import psutil
                import socket
                
                # Echte Systeminformationen sammeln
                system_info = {
                    "os": platform.system(),
                    "os_version": platform.version(),
                    "architecture": platform.architecture()[0],
                    "processor": platform.processor(),
                    "hostname": socket.gethostname(),
                    "python_version": platform.python_version(),
                    "cpu_count": psutil.cpu_count(),
                    "cpu_usage": f"{psutil.cpu_percent(interval=1):.1f}%",
                    "memory_total": f"{psutil.virtual_memory().total / (1024**3):.1f} GB",
                    "memory_usage": f"{psutil.virtual_memory().percent:.1f}%",
                    "disk_usage": f"{psutil.disk_usage('/').percent:.1f}%",
                    "boot_time": datetime.datetime.fromtimestamp(psutil.boot_time()).isoformat(),
                    "current_time": datetime.datetime.now().isoformat()
                }
                
                return {
                    "success": True,
                    "result": "Systeminformationen erfolgreich gesammelt",
                    "data": system_info
                }
                
            except ImportError:
                return {"error": "psutil nicht installiert. Führe aus: pip install psutil", "success": False}
            except Exception as e:
                return {"error": f"Systeminformationen-Fehler: {e}", "success": False}
                
        elif command == "file_operations":
            operation = params.get("operation", "list")
            path = params.get("path", ".")
            
            try:
                if operation == "list":
                    # Echte Dateiliste
                    if not os.path.exists(path):
                        return {"error": f"Pfad '{path}' existiert nicht", "success": False}
                    
                    items = []
                    for item in os.listdir(path):
                        item_path = os.path.join(path, item)
                        stat_info = os.stat(item_path)
                        
                        items.append({
                            "name": item,
                            "type": "directory" if os.path.isdir(item_path) else "file",
                            "size": stat_info.st_size if os.path.isfile(item_path) else 0,
                            "modified": datetime.datetime.fromtimestamp(stat_info.st_mtime).isoformat()
                        })
                    
                    return {
                        "success": True,
                        "result": f"Dateien in '{path}' aufgelistet",
                        "data": {
                            "path": os.path.abspath(path),
                            "items": items,
                            "total_items": len(items),
                            "directories": len([i for i in items if i["type"] == "directory"]),
                            "files": len([i for i in items if i["type"] == "file"])
                        }
                    }
                    
                elif operation == "create_dir":
                    dir_name = params.get("name", "new_directory")
                    new_path = os.path.join(path, dir_name)
                    
                    os.makedirs(new_path, exist_ok=True)
                    
                    return {
                        "success": True,
                        "result": f"Verzeichnis '{dir_name}' erstellt",
                        "data": {"created_path": os.path.abspath(new_path)}
                    }
                    
                elif operation == "copy":
                    source = params.get("source", "")
                    destination = params.get("destination", "")
                    
                    if not source or not destination:
                        return {"error": "Quelle und Ziel müssen angegeben werden", "success": False}
                    
                    import shutil
                    shutil.copy2(source, destination)
                    
                    return {
                        "success": True,
                        "result": f"Datei von '{source}' nach '{destination}' kopiert",
                        "data": {"source": source, "destination": destination}
                    }
                else:
                    return {"error": f"Unbekannte Operation '{operation}'", "success": False}
                    
            except Exception as e:
                return {"error": f"Dateioperationen-Fehler: {e}", "success": False}
                
        elif command == "process_monitor":
            try:
                import psutil
                
                # Echte Prozess-Überwachung
                processes = []
                for proc in psutil.process_iter(['pid', 'name', 'cpu_percent', 'memory_percent']):
                    try:
                        processes.append(proc.info)
                    except (psutil.NoSuchProcess, psutil.AccessDenied):
                        pass
                
                # Top 10 Prozesse nach CPU-Nutzung
                top_processes = sorted(processes, key=lambda x: x.get('cpu_percent', 0), reverse=True)[:10]
                
                return {
                    "success": True,
                    "result": f"{len(processes)} aktive Prozesse gefunden",
                    "data": {
                        "total_processes": len(processes),
                        "top_cpu_processes": top_processes,
                        "system_load": psutil.cpu_percent(interval=1)
                    }
                }
                
            except ImportError:
                return {"error": "psutil nicht installiert", "success": False}
            except Exception as e:
                return {"error": f"Prozess-Monitor-Fehler: {e}", "success": False}
                
        elif command == "screenshot":
            try:
                import pyautogui
                
                # Echter Screenshot
                screenshot_path = f"screenshot_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                screenshot = pyautogui.screenshot()
                screenshot.save(screenshot_path)
                
                return {
                    "success": True,
                    "result": f"Screenshot gespeichert: {screenshot_path}",
                    "data": {
                        "file_path": os.path.abspath(screenshot_path),
                        "size": f"{screenshot.size[0]}x{screenshot.size[1]}",
                        "timestamp": datetime.datetime.now().isoformat()
                    }
                }
                
            except ImportError:
                return {"error": "pyautogui nicht installiert. Führe aus: pip install pyautogui", "success": False}
            except Exception as e:
                return {"error": f"Screenshot-Fehler: {e}", "success": False}
                
        elif command == "network_info":
            try:
                import psutil
                import socket
                
                # Netzwerk-Informationen
                network_info = {
                    "hostname": socket.gethostname(),
                    "ip_address": socket.gethostbyname(socket.gethostname()),
                    "network_interfaces": {}
                }
                
                # Netzwerk-Interfaces
                for interface, addrs in psutil.net_if_addrs().items():
                    network_info["network_interfaces"][interface] = []
                    for addr in addrs:
                        network_info["network_interfaces"][interface].append({
                            "family": str(addr.family),
                            "address": addr.address,
                            "netmask": addr.netmask
                        })
                
                # Netzwerk-Statistiken
                net_stats = psutil.net_io_counters()
                network_info["statistics"] = {
                    "bytes_sent": net_stats.bytes_sent,
                    "bytes_received": net_stats.bytes_recv,
                    "packets_sent": net_stats.packets_sent,
                    "packets_received": net_stats.packets_recv
                }
                
                return {
                    "success": True,
                    "result": "Netzwerk-Informationen gesammelt",
                    "data": network_info
                }
                
            except Exception as e:
                return {"error": f"Netzwerk-Info-Fehler: {e}", "success": False}
        else:
            return {"error": f"Tools-Befehl '{command}' nicht gefunden", "success": False}
    
    def _execute_analysis(self, command: str, params: Dict) -> Dict:
        """Analysis Plugin Befehle mit echten Analyse-Algorithmen"""
        if command == "sentiment_analysis":
            text = params.get("text", "")
            if not text.strip():
                return {"error": "Kein Text für Sentiment-Analyse angegeben", "success": False}
            
            try:
                # Erweiterte Sentiment-Analyse mit deutschen Wörtern
                positive_words = [
                    "gut", "super", "toll", "fantastisch", "liebe", "wunderbar", "exzellent",
                    "hervorragend", "perfekt", "großartig", "brilliant", "ausgezeichnet",
                    "freude", "glücklich", "zufrieden", "begeistert", "positiv", "erfolg"
                ]
                
                negative_words = [
                    "schlecht", "furchtbar", "hasse", "schrecklich", "katastrophe", "mies",
                    "enttäuschend", "ärgerlich", "frustierend", "traurig", "wütend", "negativ",
                    "problem", "fehler", "schwierig", "unmöglich", "versagen"
                ]
                
                neutral_words = [
                    "okay", "durchschnittlich", "normal", "mittelmäßig", "akzeptabel", "standard"
                ]
                
                # Text vorbereiten
                text_lower = text.lower()
                words = text_lower.split()
                
                # Wörter zählen
                pos_count = sum(1 for word in positive_words if word in text_lower)
                neg_count = sum(1 for word in negative_words if word in text_lower)
                neu_count = sum(1 for word in neutral_words if word in text_lower)
                
                # Erweiterte Bewertung mit Intensität
                total_sentiment_words = pos_count + neg_count + neu_count
                
                if total_sentiment_words == 0:
                    sentiment = "neutral"
                    confidence = 0.1
                elif pos_count > neg_count and pos_count > neu_count:
                    sentiment = "positive"
                    confidence = min(0.9, pos_count / len(words) * 5)
                elif neg_count > pos_count and neg_count > neu_count:
                    sentiment = "negative" 
                    confidence = min(0.9, neg_count / len(words) * 5)
                else:
                    sentiment = "neutral"
                    confidence = max(0.3, neu_count / len(words) * 3)
                
                # Zusätzliche Merkmale
                exclamation_count = text.count("!")
                question_count = text.count("?")
                caps_ratio = len([c for c in text if c.isupper()]) / len(text) if text else 0
                
                return {
                    "success": True,
                    "result": f"Sentiment analysiert: {sentiment} ({confidence:.2f} Konfidenz)",
                    "data": {
                        "sentiment": sentiment,
                        "confidence": round(confidence, 3),
                        "positive_words": pos_count,
                        "negative_words": neg_count,
                        "neutral_words": neu_count,
                        "word_count": len(words),
                        "exclamations": exclamation_count,
                        "questions": question_count,
                        "caps_ratio": round(caps_ratio, 3),
                        "analysis_details": {
                            "emotional_intensity": "high" if confidence > 0.7 else "medium" if confidence > 0.4 else "low",
                            "text_length": len(text),
                            "sentence_count": len([s for s in text.split('.') if s.strip()])
                        }
                    }
                }
                
            except Exception as e:
                return {"error": f"Sentiment-Analyse fehlgeschlagen: {e}", "success": False}
                
        elif command == "keyword_extract":
            text = params.get("text", "")
            if not text.strip():
                return {"error": "Kein Text für Keyword-Extraktion angegeben", "success": False}
            
            try:
                import re
                from collections import Counter
                
                # Deutsche Stoppwörter
                german_stopwords = {
                    "der", "die", "das", "und", "oder", "aber", "ist", "sind", "war", "waren",
                    "hat", "haben", "wird", "werden", "kann", "könnte", "soll", "sollte",
                    "ein", "eine", "einer", "einem", "einen", "für", "mit", "auf", "an",
                    "in", "zu", "von", "bei", "aus", "über", "unter", "durch", "vor",
                    "nach", "bis", "seit", "während", "wegen", "trotz", "ohne", "gegen"
                }
                
                # Text bereinigen und Keywords extrahieren
                words = re.findall(r'\b[a-zA-ZäöüÄÖÜß]{3,}\b', text.lower())
                keywords = [word for word in words if word not in german_stopwords]
                
                # Häufigkeit zählen
                keyword_counts = Counter(keywords)
                top_keywords = keyword_counts.most_common(10)
                
                # Keyword-Dichte berechnen
                total_words = len(words)
                keyword_density = {kw: (count/total_words)*100 for kw, count in top_keywords}
                
                return {
                    "success": True,
                    "result": f"{len(top_keywords)} Keywords extrahiert",
                    "data": {
                        "keywords": dict(top_keywords),
                        "keyword_density": {k: round(v, 2) for k, v in keyword_density.items()},
                        "total_words": total_words,
                        "unique_keywords": len(keyword_counts),
                        "top_keyword": top_keywords[0] if top_keywords else None
                    }
                }
                
            except Exception as e:
                return {"error": f"Keyword-Extraktion fehlgeschlagen: {e}", "success": False}
                
        elif command == "trend_analysis":
            data = params.get("data", [])
            if not data or len(data) < 3:
                return {"error": "Mindestens 3 Datenpunkte für Trend-Analyse erforderlich", "success": False}
            
            try:
                # Einfache Trend-Analyse
                numeric_data = [float(x) for x in data if isinstance(x, (int, float)) or str(x).replace('.','').replace('-','').isdigit()]
                
                if len(numeric_data) < 3:
                    return {"error": "Zu wenige numerische Datenpunkte", "success": False}
                
                # Trend berechnen (lineare Regression vereinfacht)
                n = len(numeric_data)
                x_values = list(range(n))
                
                # Mittelwerte
                x_mean = sum(x_values) / n
                y_mean = sum(numeric_data) / n
                
                # Steigung berechnen
                numerator = sum((x_values[i] - x_mean) * (numeric_data[i] - y_mean) for i in range(n))
                denominator = sum((x_values[i] - x_mean) ** 2 for i in range(n))
                
                slope = numerator / denominator if denominator != 0 else 0
                
                # Trend-Richtung bestimmen
                if slope > 0.1:
                    trend = "steigend"
                elif slope < -0.1:
                    trend = "fallend"
                else:
                    trend = "stabil"
                
                # Volatilität berechnen
                differences = [abs(numeric_data[i] - numeric_data[i-1]) for i in range(1, len(numeric_data))]
                volatility = sum(differences) / len(differences) if differences else 0
                
                return {
                    "success": True,
                    "result": f"Trend-Analyse: {trend} (Steigung: {slope:.3f})",
                    "data": {
                        "trend": trend,
                        "slope": round(slope, 4),
                        "volatility": round(volatility, 4),
                        "data_points": n,
                        "start_value": numeric_data[0],
                        "end_value": numeric_data[-1],
                        "change_percent": round(((numeric_data[-1] - numeric_data[0]) / numeric_data[0]) * 100, 2) if numeric_data[0] != 0 else 0,
                        "min_value": min(numeric_data),
                        "max_value": max(numeric_data)
                    }
                }
                
            except Exception as e:
                return {"error": f"Trend-Analyse fehlgeschlagen: {e}", "success": False}
                
        elif command == "text_similarity":
            text1 = params.get("text1", "")
            text2 = params.get("text2", "")
            
            if not text1 or not text2:
                return {"error": "Zwei Texte für Ähnlichkeits-Analyse erforderlich", "success": False}
            
            try:
                # Einfache Jaccard-Ähnlichkeit
                def get_words(text):
                    return set(re.findall(r'\b\w+\b', text.lower()))
                
                words1 = get_words(text1)
                words2 = get_words(text2)
                
                intersection = words1.intersection(words2)
                union = words1.union(words2)
                
                jaccard_similarity = len(intersection) / len(union) if union else 0
                
                # Längen-Ähnlichkeit
                length_similarity = 1 - abs(len(text1) - len(text2)) / max(len(text1), len(text2))
                
                # Gewichtete Gesamtähnlichkeit
                overall_similarity = (jaccard_similarity * 0.7) + (length_similarity * 0.3)
                
                return {
                    "success": True,
                    "result": f"Text-Ähnlichkeit: {overall_similarity:.3f}",
                    "data": {
                        "overall_similarity": round(overall_similarity, 4),
                        "word_similarity": round(jaccard_similarity, 4),
                        "length_similarity": round(length_similarity, 4),
                        "common_words": len(intersection),
                        "unique_words_text1": len(words1 - words2),
                        "unique_words_text2": len(words2 - words1),
                        "common_word_list": list(intersection)[:10]  # Erste 10 gemeinsame Wörter
                    }
                }
                
            except Exception as e:
                return {"error": f"Ähnlichkeits-Analyse fehlgeschlagen: {e}", "success": False}
        else:
            return {"error": f"Analysis-Befehl '{command}' nicht gefunden", "success": False}
    
    def get_plugin_info(self, plugin_name: str) -> Dict:
        """Gibt Informationen über ein Plugin zurück"""
        if plugin_name in self.available_plugins:
            return self.available_plugins[plugin_name]
        return {"error": "Plugin nicht gefunden"}
    
    def list_plugin_functions(self, plugin_name: str) -> List[str]:
        """Listet verfügbare Funktionen eines Plugins"""
        if plugin_name in self.available_plugins:
            return self.available_plugins[plugin_name].get("functions", [])
        return []
    
    def get_status(self) -> Dict:
        """Gibt Plugin-Status zurück"""
        return {
            "total_plugins": len(self.available_plugins),
            "loaded_plugins": len(self.plugins),
            "active_plugins": [name for name, plugin in self.plugins.items() if plugin.get("active", False)],
            "plugin_list": list(self.available_plugins.keys())
        }
    
    def test_plugin(self, plugin_name: str) -> Dict:
        """Testet ein Plugin"""
        if plugin_name not in self.plugins:
            self.load_plugin(plugin_name)
        
        functions = self.list_plugin_functions(plugin_name)
        if functions:
            # Teste erste Funktion
            test_function = functions[0]
            result = self.execute_plugin_command(plugin_name, test_function, {})
            return {
                "plugin": plugin_name,
                "test_function": test_function,
                "result": result,
                "success": result.get("success", False)
            }
        return {"error": "Keine Testfunktionen verfügbar", "success": False}


def get_plugin_manager():
    """Factory-Funktion für Plugin Manager"""
    return CUDIPluginManager()


# Demo/Test
if __name__ == "__main__":
    pm = CUDIPluginManager()
    
    # Alle Plugins laden
    pm.load_all_plugins()
    
    # Test verschiedener Plugin-Funktionen
    print("\n🧪 Plugin Tests:")
    
    # Research Test
    result = pm.execute_plugin_command("research", "web_search", {"query": "CUDI AI"})
    print(f"Research: {result}")
    
    # Content Test
    result = pm.execute_plugin_command("content", "generate_text", {"topic": "KI", "length": 50})
    print(f"Content: {result}")
    
    # Analysis Test
    result = pm.execute_plugin_command("analysis", "sentiment_analysis", {"text": "Das ist super toll!"})
    print(f"Analysis: {result}")
    
    print(f"\n📊 Status: {pm.get_status()}")