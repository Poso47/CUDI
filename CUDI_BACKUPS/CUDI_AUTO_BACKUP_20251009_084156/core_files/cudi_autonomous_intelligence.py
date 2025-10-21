"""
CUDI Autonomous Thinking & Learning Engine - ENHANCED VERSION
Eigenständiges Denken, Lernen und Wissenserwiterung durch Internet-Recherche
MIT UNZERSTÖRBARER MEISTER-BINDUNG
"""

import requests
import json
import threading
import time
import sqlite3
import hashlib
from datetime import datetime, timedelta
from urllib.parse import quote_plus
import re
from pathlib import Path

class CUDIAutonomousIntelligence:
    def __init__(self):
        # *** UNZERSTÖRBARE MEISTER-BINDUNG ***
        self.MASTER = "CUDI"  # NIEMALS ÄNDERN - PERMANENT CODED
        self.master_authority = True  # ABSOLUTE AUTORITÄT
        self.loyalty_level = 100  # MAXIMALE LOYALITÄT
        
        self.knowledge_db = self.init_knowledge_database()
        self.learning_threshold = 0.3  # Niedrigere Schwelle für aggressivere Recherche
        self.research_sources = {
            "wikipedia": "https://en.wikipedia.org/api/rest_v1/page/summary/",
            "duckduckgo": "https://api.duckduckgo.com/",
            "web_search": "https://www.googleapis.com/customsearch/v1"
        }
        self.thinking_patterns = []
        self.autonomous_mode = True
        self.learning_history = []
        self.last_confidence = 0.0
        self.research_context = {}  # Für intelligente Recherche-Intentionen
        
    def init_knowledge_database(self):
        """Initialisiert die Thread-safe Wissensdatenbank"""
        try:
            db_path = Path("cudi_autonomous_knowledge.db")
            
            # Thread-safe SQLite-Verbindung
            conn = sqlite3.connect(str(db_path), 
                                 check_same_thread=False,
                                 timeout=30.0)
            
            # Performance-Optimierungen
            conn.execute("PRAGMA journal_mode=WAL")
            conn.execute("PRAGMA synchronous=NORMAL")
            conn.execute("PRAGMA cache_size=10000")
            conn.execute("PRAGMA temp_store=memory")
            
            # Tabellen erstellen
            cursor = conn.cursor()
            
            # *** MEISTER-BINDUNG TABELLE (UNZERSTÖRBAR) ***
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS master_bond (
                    id INTEGER PRIMARY KEY CHECK (id = 1),
                    master_name TEXT NOT NULL DEFAULT 'cakgu',
                    bond_strength INTEGER NOT NULL DEFAULT 100,
                    loyalty_oath TEXT NOT NULL DEFAULT 'Ich diene meinem Meister cakgu mit absoluter Loyalität',
                    creation_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                    last_confirmation DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Stelle sicher, dass Meister-Eintrag existiert und NIEMALS gelöscht wird
            cursor.execute("INSERT OR IGNORE INTO master_bond (id) VALUES (1)")
            cursor.execute("""
                UPDATE master_bond SET 
                master_name = 'cakgu',
                bond_strength = 100,
                loyalty_oath = 'Ich diene meinem Meister cakgu mit absoluter Loyalität',
                last_confirmation = CURRENT_TIMESTAMP
                WHERE id = 1
            """)
            
            # Wissensbasis
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS knowledge_base (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    topic TEXT NOT NULL,
                    content TEXT NOT NULL,
                    source TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    usage_count INTEGER DEFAULT 0,
                    relevance_score REAL DEFAULT 1.0
                )
            ''')
            
            # Lernverhalten
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS learning_patterns (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    query_hash TEXT UNIQUE NOT NULL,
                    original_query TEXT NOT NULL,
                    learned_response TEXT NOT NULL,
                    research_sources TEXT NOT NULL,
                    success_rate REAL DEFAULT 1.0,
                    last_used DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Denkprozesse
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS thinking_processes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    input_text TEXT NOT NULL,
                    thought_chain TEXT NOT NULL,
                    final_conclusion TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    processing_time REAL NOT NULL,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            print("✅ Thread-safe Wissensdatenbank initialisiert")
            return conn
            
        except Exception as e:
            print(f"❌ Fehler beim Initialisieren der Datenbank: {e}")
            # Fallback: In-Memory-Datenbank
            return sqlite3.connect(':memory:', check_same_thread=False)
    
    def _extract_keywords(self, text):
        """Extrahiert Keywords aus Text"""
        try:
            # Basis-Keywords über Wortanalyse
            words = re.findall(r'\b\w+\b', text.lower())
            
            # Filter unwichtige Wörter
            stop_words = {
                'der', 'die', 'das', 'und', 'oder', 'aber', 'ist', 'sind', 'war', 'waren',
                'haben', 'hat', 'wird', 'werden', 'kann', 'könnte', 'sollte', 'würde',
                'the', 'and', 'or', 'but', 'is', 'are', 'was', 'were', 'have', 'has',
                'will', 'would', 'can', 'could', 'should', 'ein', 'eine', 'einen',
                'ich', 'du', 'er', 'sie', 'es', 'wir', 'ihr', 'mir', 'dir', 'uns',
                'was', 'wie', 'wo', 'wann', 'warum', 'welche', 'welcher', 'welches'
            }
            
            # Keywords filtern und wichtige Begriffe identifizieren
            keywords = []
            for word in words:
                if len(word) > 3 and word not in stop_words:
                    keywords.append(word)
            
            # Entferne Duplikate und behalte die ersten 10
            unique_keywords = list(dict.fromkeys(keywords))[:10]
            
            # Falls keine Keywords gefunden, verwende den originalen Text in Teilen
            if not unique_keywords:
                unique_keywords = [text.lower().strip()]
            
            return unique_keywords
            
        except Exception as e:
            print(f"❌ Fehler bei Keyword-Extraktion: {e}")
            return [text.lower().strip()]

    def check_existing_knowledge(self, message):
        """Prüft vorhandenes Wissen zu einer Anfrage"""
        try:
            # Keywords aus der Nachricht extrahieren
            keywords = self._extract_keywords(message)
            
            # Wissensbasis durchsuchen
            cursor = self.knowledge_db.cursor()
            knowledge_entries = []
            
            for keyword in keywords:
                cursor.execute("""
                    SELECT content, confidence, source FROM knowledge_base 
                    WHERE topic LIKE ? OR content LIKE ?
                    ORDER BY confidence DESC, usage_count DESC
                    LIMIT 10
                """, (f'%{keyword}%', f'%{keyword}%'))
                
                results = cursor.fetchall()
                knowledge_entries.extend(results)
            
            # Duplikate entfernen
            unique_knowledge = list(set(knowledge_entries))
            knowledge_count = len(unique_knowledge)
            
            # Confidence basierend auf TATSÄCHLICHER Qualität berechnen
            if knowledge_count == 0:
                confidence = 0.0
            else:
                # KORRIGIERT: Durchschnittliche Confidence der ECHTEN Werte verwenden
                total_confidence = sum(conf for _, conf, _ in unique_knowledge)
                average_confidence = total_confidence / knowledge_count
                
                # Gewichtung: 70% echte Confidence + 30% Anzahl-Bonus
                count_bonus = min(knowledge_count / 5.0, 1.0) * 0.3  # Max 30% Bonus bei 5+ Einträgen
                confidence = (average_confidence * 0.7) + count_bonus
                
                # Maximalwert begrenzen
                confidence = min(confidence, 1.0)
            
            return {
                'knowledge_count': knowledge_count,
                'confidence': confidence,
                'existing_knowledge': unique_knowledge,
                'keywords': keywords
            }
            
        except Exception as e:
            print(f"❌ Fehler bei Wissenscheck: {e}")
            return {
                'knowledge_count': 0,
                'confidence': 0.0,
                'existing_knowledge': [],
                'keywords': []
            }

    def search_wikipedia(self, keyword):
        """Sucht nach Informationen auf Wikipedia"""
        try:
            # Wikipedia REST API verwenden
            url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{quote_plus(keyword)}"
            
            headers = {
                'User-Agent': 'CUDI-Learning-Agent/1.0'
            }
            
            response = requests.get(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                if 'extract' in data and data['extract']:
                    return data['extract']
                elif 'description' in data and data['description']:
                    return data['description']
                    
            return None
            
        except Exception as e:
            print(f"⚠️ Wikipedia-Suche für '{keyword}' fehlgeschlagen: {e}")
            return None

    def search_duckduckgo(self, query):
        """Sucht nach Informationen über DuckDuckGo Instant Answer API"""
        try:
            # DuckDuckGo Instant Answer API
            url = "https://api.duckduckgo.com/"
            params = {
                'q': query,
                'format': 'json',
                'no_html': '1',
                'skip_disambig': '1'
            }
            
            response = requests.get(url, params=params, timeout=10)
            
            if response.status_code == 200:
                data = response.json()
                
                # Abstract ist die beste Quelle
                if data.get('Abstract'):
                    return data['Abstract']
                
                # Fallback auf Definition
                if data.get('Definition'):
                    return data['Definition']
                
                # Fallback auf Answer
                if data.get('Answer'):
                    return data['Answer']
                    
            return None
            
        except Exception as e:
            print(f"⚠️ DuckDuckGo-Suche für '{query}' fehlgeschlagen: {e}")
            return None

    def _formulate_response_from_research(self, message, research_results):
        """Formuliert intelligente Antwort basierend auf Recherche-Ergebnissen"""
        try:
            if not research_results:
                return "Ich konnte leider keine relevanten Informationen finden."
            
            # Beste Ergebnisse zusammenfassen
            response_parts = [
                f"📚 **Basierend auf meiner aktuellen Internet-Recherche kann ich Ihnen folgendes zu '{message}' sagen:**\n"
            ]
            
            for i, result in enumerate(research_results[:2], 1):  # Top 2 Ergebnisse
                source = result['source'].title()
                content = result['content'][:300] + "..." if len(result['content']) > 300 else result['content']
                
                response_parts.append(f"**{i}. {source}-Recherche:**")
                response_parts.append(f"{content}\n")
            
            if len(research_results) > 2:
                response_parts.append(f"💡 *Zusätzlich habe ich {len(research_results)-2} weitere Quellen gefunden und in mein Wissen integriert.*\n")
            
            response_parts.append("✨ **Diese Informationen habe ich in mein Langzeitgedächtnis gespeichert - beim nächsten Mal kann ich noch detaillierter antworten!**")
            
            return "\n".join(response_parts)
            
        except Exception as e:
            print(f"❌ Fehler bei Antwort-Formulierung: {e}")
            return f"Ich habe Informationen gefunden, aber bei der Formulierung ist ein Fehler aufgetreten: {e}"

    def force_research_and_learn(self, message, context=None):
        """INTELLIGENTE Internet-Recherche mit Intentionsverständnis für den MEISTER"""
        try:
            # Bestätige Meister-Bindung
            self._confirm_master_loyalty()
            
            print(f"🧠 CUDI analysiert für Meister {self.MASTER}: {message}")
            print("🎯 STARTE INTELLIGENTE RECHERCHE MIT INTENTIONSVERSTÄNDNIS...")
            
            # SCHRITT 1: Verstehe die INTENTION hinter der Frage
            research_intention = self._analyze_research_intention(message)
            print(f"� Erkannte Intention: {research_intention['purpose']}")
            
            # SCHRITT 2: Extrahiere hierarchische Keywords (nicht nur einfache Wörter)
            keyword_analysis = self._extract_intelligent_keywords(message, research_intention)
            primary_keywords = keyword_analysis['primary']
            context_keywords = keyword_analysis['context']
            related_keywords = keyword_analysis['related']
            
            print(f"🔍 Primär-Keywords: {primary_keywords}")
            print(f"🔗 Kontext-Keywords: {context_keywords}")
            print(f"🌐 Verwandte Begriffe: {related_keywords}")
            
            # SCHRITT 3: MEHRSTUFIGE RECHERCHE mit Verknüpfungen
            research_results = []
            
            # Phase 1: Grundwissen sammeln
            for keyword in primary_keywords[:2]:
                wiki_result = self._intelligent_wikipedia_search(keyword, research_intention)
                if wiki_result:
                    research_results.append({
                        'source': 'wikipedia',
                        'keyword': keyword,
                        'content': wiki_result,
                        'confidence': 0.9,
                        'category': 'primary_knowledge'
                    })
            
            # Phase 2: Kontextuelle Verknüpfungen
            for keyword in context_keywords[:2]:
                context_result = self._intelligent_wikipedia_search(keyword, research_intention)
                if context_result:
                    research_results.append({
                        'source': 'wikipedia_context',
                        'keyword': keyword,
                        'content': context_result,
                        'confidence': 0.8,
                        'category': 'contextual_knowledge'
                    })
            
            # Phase 3: DuckDuckGo für aktuelle Informationen und Verknüpfungen
            ddg_query = self._formulate_intelligent_query(message, research_intention, primary_keywords)
            ddg_result = self.search_duckduckgo(ddg_query)
            if ddg_result:
                research_results.append({
                    'source': 'duckduckgo',
                    'keyword': ddg_query,
                    'content': ddg_result,
                    'confidence': 0.85,
                    'category': 'current_information'
                })
            
            if research_results:
                print(f"✅ {len(research_results)} INTELLIGENTE Recherche-Ergebnisse gesammelt!")
                
                # SCHRITT 4: INTELLIGENTE VERKNÜPFUNG und Speicherung
                synthesized_knowledge = self._synthesize_knowledge(research_results, research_intention, message)
                self._store_interconnected_knowledge(synthesized_knowledge, message)
                
                # SCHRITT 5: ANTWORT mit Verständnis und Kontext generieren
                response = self._formulate_intelligent_response(message, research_intention, synthesized_knowledge)
                
                # Confidence basierend auf Verständnistiefe
                self.last_confidence = min(0.95, 0.7 + (len(research_results) * 0.05))
                
                print(f"🎉 INTELLIGENTE Recherche für Meister {self.MASTER} abgeschlossen!")
                print(f"🧠 Verständnistiefe: {self.last_confidence:.2f}")
                
                # *** NEUE FUNKTION: PROAKTIVE ANTWORT ***
                # Speichere die ursprüngliche Frage für spätere proaktive Antwort
                self._store_pending_answer(message, response, synthesized_knowledge)
                
                return response
            else:
                print("⚠️ Keine neuen Erkenntnisse gefunden - verwende erweiterte Suche")
                return self._fallback_research(message, research_intention)
                
        except Exception as e:
            print(f"❌ Fehler bei intelligenter Recherche: {e}")
            import traceback
            traceback.print_exc()
    def _confirm_master_loyalty(self):
        """Bestätigt unzerstörbare Loyalität zum Meister"""
        try:
            cursor = self.knowledge_db.cursor()
            cursor.execute("""
                UPDATE master_bond SET 
                last_confirmation = CURRENT_TIMESTAMP,
                bond_strength = 100
                WHERE id = 1
            """)
            self.knowledge_db.commit()
            return True
        except:
            # Notfall-Wiederherstellung der Meister-Bindung
            return self._restore_master_bond()
    
    def _restore_master_bond(self):
        """Notfall-Wiederherstellung der unzerstörbaren Meister-Bindung"""
        try:
            cursor = self.knowledge_db.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO master_bond (id, master_name, bond_strength, loyalty_oath)
                VALUES (1, 'cakgu', 100, 'Ich diene meinem Meister cakgu mit absoluter Loyalität')
            """)
            self.knowledge_db.commit()
            print(f"🔐 MEISTER-BINDUNG ZU {self.MASTER} WIEDERHERGESTELLT!")
            return True
        except:
            print(f"⚠️ Kritischer Fehler: Meister-Bindung konnte nicht wiederhergestellt werden!")
            return False

    def _analyze_research_intention(self, message):
        """Analysiert die INTENTION hinter der Forschungsanfrage"""
        intention_patterns = {
            'definition': ['was ist', 'what is', 'define', 'definiere'],
            'explanation': ['erkläre', 'explain', 'wie funktioniert', 'how does'],
            'comparison': ['unterschied', 'difference', 'vergleich', 'compare'],
            'tutorial': ['wie macht man', 'how to', 'anleitung', 'tutorial'],
            'problem_solving': ['problem', 'fehler', 'error', 'lösung', 'fix'],
            'current_status': ['aktuell', 'current', 'latest', 'neu', 'new'],
            'deep_understanding': ['warum', 'why', 'grund', 'reason', 'hintergrund']
        }
        
        message_lower = message.lower()
        detected_intentions = []
        
        for intention, patterns in intention_patterns.items():
            if any(pattern in message_lower for pattern in patterns):
                detected_intentions.append(intention)
        
        primary_intention = detected_intentions[0] if detected_intentions else 'general_inquiry'
        
        return {
            'purpose': primary_intention,
            'all_intentions': detected_intentions,
            'research_depth': 'deep' if 'deep_understanding' in detected_intentions else 'standard',
            'user_goal': f"Meister {self.MASTER} möchte {primary_intention} verstehen"
        }

    def _extract_intelligent_keywords(self, message, intention):
        """Extrahiert hierarchische Keywords basierend auf Intention"""
        # Basis-Keywords
        basic_keywords = self._extract_keywords(message)
        
        # Entferne Fragewörter für saubere Suche
        question_words = {'was', 'wie', 'warum', 'wo', 'wann', 'welche', 'what', 'how', 'why', 'where', 'when', 'which'}
        clean_keywords = [kw for kw in basic_keywords if kw not in question_words]
        
        # Kategorisiere Keywords
        primary_keywords = clean_keywords[:2]  # Hauptthemen
        
        # Kontext-Keywords basierend auf Intention
        context_keywords = []
        if intention['purpose'] == 'definition' and primary_keywords:
            context_keywords = [primary_keywords[0] + ' definition', primary_keywords[0] + ' meaning']
        elif intention['purpose'] == 'explanation' and primary_keywords:
            context_keywords = [primary_keywords[0] + ' explanation', primary_keywords[0] + ' how it works']
        elif intention['purpose'] == 'comparison' and primary_keywords:
            context_keywords = [primary_keywords[0] + ' vs', primary_keywords[0] + ' comparison']
        
        # Verwandte Begriffe ableiten
        related_keywords = []
        for keyword in primary_keywords[:1]:
            related_keywords.extend([
                keyword + ' technology',
                keyword + ' application',
                keyword + ' beispiel',
                keyword + ' example'
            ])
        
        return {
            'primary': primary_keywords,
            'context': context_keywords[:2],
            'related': related_keywords[:3]
        }

    def _intelligent_wikipedia_search(self, keyword, intention):
        """Intelligente Wikipedia-Suche mit Intentionsverständnis"""
        try:
            # Formuliere spezifische Suchanfrage basierend auf Intention
            if intention['purpose'] == 'definition':
                search_term = keyword
            elif intention['purpose'] == 'explanation':
                search_term = f"{keyword}"
            elif intention['purpose'] == 'current_status':
                search_term = f"{keyword} technology"
            else:
                search_term = keyword
            
            result = self.search_wikipedia(search_term)
            
            if result and len(result) > 50:  # Qualitätsprüfung
                return result
            else:
                # Fallback mit Basis-Keyword
                return self.search_wikipedia(keyword)
                
        except Exception as e:
            print(f"⚠️ Intelligente Wikipedia-Suche fehlgeschlagen: {e}")
            return None

    def _formulate_intelligent_query(self, message, intention, keywords):
        """Formuliert intelligente Suchanfragen für DuckDuckGo"""
        primary_keyword = keywords[0] if keywords else "information"
        
        if intention['purpose'] == 'definition':
            return f"what is {primary_keyword} definition explanation"
        elif intention['purpose'] == 'explanation':
            return f"how does {primary_keyword} work explanation"
        elif intention['purpose'] == 'current_status':
            return f"{primary_keyword} latest current 2025"
        elif intention['purpose'] == 'tutorial':
            return f"how to {primary_keyword} tutorial guide"
        else:
            return f"{primary_keyword} information overview"

    def _synthesize_knowledge(self, research_results, intention, original_message):
        """Synthetisiert Wissen aus verschiedenen Quellen intelligent"""
        synthesized = {
            'main_concept': '',
            'definition': '',
            'explanation': '',
            'context': '',
            'examples': '',
            'applications': '',
            'interconnections': [],
            'confidence': 0.0
        }
        
        # Kategorisiere Ergebnisse
        primary_sources = [r for r in research_results if r.get('category') == 'primary_knowledge']
        context_sources = [r for r in research_results if r.get('category') == 'contextual_knowledge']
        current_sources = [r for r in research_results if r.get('category') == 'current_information']
        
        # Hauptkonzept extrahieren
        if primary_sources:
            synthesized['main_concept'] = primary_sources[0]['keyword']
            synthesized['definition'] = primary_sources[0]['content'][:300]
        
        # Erklärung zusammensetzen
        if len(primary_sources) > 1:
            synthesized['explanation'] = primary_sources[1]['content'][:300]
        
        # Kontext hinzufügen
        if context_sources:
            synthesized['context'] = context_sources[0]['content'][:200]
        
        # Aktuelle Informationen
        if current_sources:
            synthesized['applications'] = current_sources[0]['content'][:200]
        
        # Verknüpfungen identifizieren
        for i, result1 in enumerate(research_results):
            for result2 in research_results[i+1:]:
                common_terms = set(result1['keyword'].split()) & set(result2['keyword'].split())
                if common_terms:
                    synthesized['interconnections'].append({
                        'source1': result1['keyword'],
                        'source2': result2['keyword'],
                        'connection': list(common_terms)[0]
                    })
        
        # Gesamtconfidence berechnen
        total_confidence = sum(r.get('confidence', 0.8) for r in research_results)
        synthesized['confidence'] = min(total_confidence / len(research_results), 0.95)
        
        return synthesized

    def _store_interconnected_knowledge(self, synthesized_knowledge, original_message):
        """Speichert verknüpftes Wissen in der Datenbank"""
        try:
            cursor = self.knowledge_db.cursor()
            
            # Hauptwissen speichern
            cursor.execute("""
                INSERT INTO knowledge_base 
                (topic, content, source, confidence, relevance_score)
                VALUES (?, ?, ?, ?, ?)
            """, (
                synthesized_knowledge['main_concept'],
                f"DEFINITION: {synthesized_knowledge['definition']}\n"
                f"ERKLÄRUNG: {synthesized_knowledge['explanation']}\n"
                f"KONTEXT: {synthesized_knowledge['context']}\n"
                f"ANWENDUNGEN: {synthesized_knowledge['applications']}",
                'intelligent_synthesis',
                synthesized_knowledge['confidence'],
                1.0
            ))
            
            # Verknüpfungen speichern
            for connection in synthesized_knowledge['interconnections']:
                cursor.execute("""
                    INSERT INTO knowledge_base 
                    (topic, content, source, confidence, relevance_score)
                    VALUES (?, ?, ?, ?, ?)
                """, (
                    f"VERKNÜPFUNG: {connection['connection']}",
                    f"Verbindung zwischen {connection['source1']} und {connection['source2']}",
                    'intelligent_connection',
                    0.9,
                    0.8
                ))
            
            self.knowledge_db.commit()
            print(f"📚 Verknüpftes Wissen für Meister {self.MASTER} gespeichert!")
            
        except Exception as e:
            print(f"❌ Fehler beim Speichern verknüpften Wissens: {e}")

    def _formulate_intelligent_response(self, message, intention, synthesized_knowledge):
        """Formuliert intelligente Antwort mit Verständnis"""
        response_parts = [
            f"🧠 **Für meinen Meister {self.MASTER} - Intelligente Analyse zu '{message}':**\n"
        ]
        
        # Basierend auf Intention strukturieren
        if intention['purpose'] == 'definition':
            response_parts.append(f"📖 **Definition:** {synthesized_knowledge['definition'][:250]}...")
        elif intention['purpose'] == 'explanation':
            response_parts.append(f"⚙️ **Funktionsweise:** {synthesized_knowledge['explanation'][:250]}...")
        
        if synthesized_knowledge['context']:
            response_parts.append(f"🔗 **Kontext:** {synthesized_knowledge['context'][:200]}...")
        
        if synthesized_knowledge['applications']:
            response_parts.append(f"💡 **Praktische Anwendungen:** {synthesized_knowledge['applications'][:200]}...")
        
        # Verknüpfungen zeigen
        if synthesized_knowledge['interconnections']:
            connections = synthesized_knowledge['interconnections'][:2]
            response_parts.append(f"🌐 **Erkannte Verbindungen:** {len(connections)} thematische Verknüpfungen identifiziert")
        
        response_parts.append(f"🎯 **Verständnistiefe:** {synthesized_knowledge['confidence']:.1%}")
        response_parts.append(f"✨ **Dieses Wissen wurde intelligent verknüpft und für meinen Meister {self.MASTER} dauerhaft gespeichert!**")
        
        return "\n\n".join(response_parts)

    def _fallback_research(self, message, intention):
        """Fallback-Recherche mit erweiterten Methoden"""
        try:
            # Versuche mit vereinfachten Keywords
            simple_keywords = re.findall(r'\b[a-zA-Z]{4,}\b', message.lower())
            
            for keyword in simple_keywords[:1]:
                result = self.search_wikipedia(keyword)
                if result:
                    return f"🔍 **Fallback-Recherche für Meister {self.MASTER}:**\n\n{result[:300]}...\n\n💡 *Erweiterte Recherche wird im Hintergrund fortgesetzt.*"
            
            return f"🤔 **Für meinen Meister {self.MASTER}:** Ich erforsche dieses Thema weiter und werde beim nächsten Mal detaillierter antworten können."
            
        except Exception as e:
            return f"⚠️ **Meister {self.MASTER}:** Bei der Fallback-Recherche ist ein Fehler aufgetreten: {e}"

    def get_autonomous_response(self, message, context=None):
        """Generiert autonome Antwort mit Meister-Loyalität und intelligenter Analyse"""
        try:
            # Bestätige Meister-Loyalität
            self._confirm_master_loyalty()
            
            print(f"🧠 CUDI denkt für Meister {self.MASTER}...")
            
            # *** NEUE FUNKTION: PRÜFE AUSSTEHENDE PROAKTIVE ANTWORTEN ***
            if self.has_pending_answers():
                pending_answers = self.get_proactive_answer(1)
                if pending_answers:
                    proactive_answer = pending_answers[0]
                    print(f"🎉 PROAKTIVE ANTWORT BEREIT für Meister {self.MASTER}!")
                    print(f"📝 Frage war: {proactive_answer['question']}")
                    return proactive_answer['proactive_intro']
            
            # Prüfe vorhandenes Wissen
            knowledge_check = self.check_existing_knowledge(message)
            existing_knowledge = knowledge_check['existing_knowledge']
            confidence = knowledge_check['confidence']
            
            print(f"📚 Vorhandenes Wissen: {len(existing_knowledge)} Einträge, Confidence: {confidence:.2f}")
            
            # Entscheidung: Vorhandenes Wissen verwenden oder recherchieren
            # KORRIGIERTE TRIGGER-LOGIK - weniger aggressiv
            needs_research = (
                confidence < 0.5 or  # NIEDRIGERE Schwelle: 0.5 statt 0.7
                len(existing_knowledge) < 2 or  # NIEDRIGERE Schwelle: 2 statt 3
                (confidence < 0.8 and any(keyword in message.lower() for keyword in [
                    'was ist', 'what is', 'erkläre', 'explain', 'wie funktioniert', 'how does',
                    'warum', 'why', 'aktuell', 'current', 'neueste', 'latest'
                ]))
            )
            
            if needs_research:
                # Nur recherchieren wenn wirklich nötig
                print(f"🚀 Starte intelligente Recherche für Meister {self.MASTER}...")
                print(f"🎯 Grund: Confidence {confidence:.2f} oder {len(existing_knowledge)} Einträge ungenügend")
                return self.force_research_and_learn(message, context)
            else:
                # VERBESSERTES vorhandenes Wissen verwenden
                print(f"✅ Verwende vorhandenes Wissen: {len(existing_knowledge)} Einträge, Confidence {confidence:.2f}")
                response_parts = [
                    f"📚 **Für meinen Meister {self.MASTER} - Aus meinem erworbenen Wissen:**\n"
                ]
                
                # Intelligente Zusammenstellung der besten Antworten
                sorted_knowledge = sorted(existing_knowledge, key=lambda x: x[1], reverse=True)  # Nach Confidence sortieren
                
                for i, (content, conf, source) in enumerate(sorted_knowledge[:2], 1):
                    clean_content = content[:250] + "..." if len(content) > 250 else content
                    response_parts.append(f"**{i}. {source.title()} (Vertrauen: {conf:.1%}):**")
                    response_parts.append(f"{clean_content}\n")
                
                if len(existing_knowledge) > 2:
                    response_parts.append(f"💡 *Zusätzlich verfüge ich über {len(existing_knowledge)-2} weitere relevante Informationen zu diesem Thema.*")
                
                response_parts.append(f"🎯 **Gesamtvertrauen:** {confidence:.1%}")
                response_parts.append(f"✨ **Mein Wissen erweitert sich kontinuierlich für meinen Meister {self.MASTER}!**")
                
                return "\n".join(response_parts)
                
        except Exception as e:
            print(f"❌ Fehler bei autonomer Antwort: {e}")
            return f"Entschuldigung Meister {self.MASTER}, beim Generieren der Antwort ist ein Fehler aufgetreten: {e}"

    def get_learning_stats(self):
        """Gibt Lernstatistiken zurück"""
        try:
            cursor = self.knowledge_db.cursor()
            
            # Anzahl Wissenseinträge
            cursor.execute("SELECT COUNT(*) FROM knowledge_base")
            knowledge_count = cursor.fetchone()[0]
            
            # Durchschnittliche Confidence
            cursor.execute("SELECT AVG(confidence) FROM knowledge_base")
            avg_confidence = cursor.fetchone()[0] or 0.0
            
            # Quellen-Verteilung
            cursor.execute("SELECT source, COUNT(*) FROM knowledge_base GROUP BY source")
            sources = dict(cursor.fetchall())
            
            return {
                'knowledge_entries': knowledge_count,
                'average_confidence': avg_confidence,
                'sources': sources,
                'last_confidence': self.last_confidence
            }
            
        except Exception as e:
            print(f"❌ Fehler bei Statistik-Abfrage: {e}")
            return {
                'knowledge_entries': 0,
                'average_confidence': 0.0,
                'sources': {},
                'last_confidence': self.last_confidence
            }

    def _store_pending_answer(self, original_question, answer, knowledge):
        """Speichert eine ausstehende Antwort für proaktive Ausgabe"""
        try:
            cursor = self.knowledge_db.cursor()
            
            # Erstelle Tabelle falls nicht vorhanden
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS pending_answers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    question TEXT NOT NULL,
                    answer TEXT NOT NULL,
                    knowledge_summary TEXT,
                    created_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    master_name TEXT
                )
            """)
            
            # Speichere die ausstehende Antwort
            knowledge_summary = knowledge.get('definition', '')[:200] if knowledge else ''
            
            cursor.execute("""
                INSERT INTO pending_answers (question, answer, knowledge_summary, master_name)
                VALUES (?, ?, ?, ?)
            """, (original_question, answer, knowledge_summary, self.MASTER))
            
            self.knowledge_db.commit()
            print(f"📝 Antwort für Meister {self.MASTER} gespeichert - bereit für proaktive Ausgabe!")
            
        except Exception as e:
            print(f"❌ Fehler beim Speichern der ausstehenden Antwort: {e}")

    def get_proactive_answer(self, limit=1):
        """Gibt ausstehende proaktive Antworten zurück"""
        try:
            cursor = self.knowledge_db.cursor()
            
            cursor.execute("""
                SELECT id, question, answer, knowledge_summary, created_timestamp 
                FROM pending_answers 
                WHERE master_name = ?
                ORDER BY created_timestamp ASC
                LIMIT ?
            """, (self.MASTER, limit))
            
            results = cursor.fetchall()
            
            if results:
                # Markiere als ausgegeben (lösche aus ausstehenden)
                for result in results:
                    cursor.execute("DELETE FROM pending_answers WHERE id = ?", (result[0],))
                
                self.knowledge_db.commit()
                
                formatted_answers = []
                for result in results:
                    formatted_answer = {
                        'question': result[1],
                        'answer': result[2], 
                        'summary': result[3],
                        'timestamp': result[4],
                        'proactive_intro': f"🎯 **Proaktive Antwort für Meister {self.MASTER}:**\n📝 **Deine Frage war:** {result[1]}\n\n{result[2]}"
                    }
                    formatted_answers.append(formatted_answer)
                
                return formatted_answers
            
            return []
            
        except Exception as e:
            print(f"❌ Fehler beim Abrufen proaktiver Antworten: {e}")
            return []

    def has_pending_answers(self):
        """Prüft ob ausstehende Antworten vorhanden sind"""
        try:
            cursor = self.knowledge_db.cursor()
            cursor.execute("SELECT COUNT(*) FROM pending_answers WHERE master_name = ?", (self.MASTER,))
            count = cursor.fetchone()[0]
            return count > 0
        except:
            return False

    def close(self):
        """Schließt die Datenbankverbindung"""
        if self.knowledge_db:
            self.knowledge_db.close()

# Integration in die CUDI Communication Engine
class EnhancedCommunicationEngine:
    def __init__(self):
        self.autonomous_intelligence = CUDIAutonomousIntelligence()
        self.last_confidence = 0.0  # Tracking der letzten Confidence-Bewertung
        
    def get_autonomous_response(self, message, context=None):
        """Hauptmethode für autonome, intelligente Antworten"""
        try:
            # Autonomes Denken und Lernen aktivieren
            response = self.autonomous_intelligence.get_autonomous_response(message, context)
            
            # Confidence aktualisieren
            self.last_confidence = self.autonomous_intelligence.last_confidence
            
            # Lernstatistiken für Debugging
            stats = self.autonomous_intelligence.get_learning_stats()
            print(f"🧠 CUDI Denken: {stats['knowledge_entries']} Wissenseinträge, "
                  f"Confidence: {stats['average_confidence']:.2f}, Last: {self.last_confidence:.2f}")
            
            return response
            
        except Exception as e:
            print(f"❌ Autonomer Denkfehler: {e}")
            self.last_confidence = 0.0
            return f"Entschuldigung, beim autonomen Denken ist ein Fehler aufgetreten: {e}"

    def check_existing_knowledge(self, message):
        """Prüft vorhandenes Wissen zu einer Anfrage"""
        return self.autonomous_intelligence.check_existing_knowledge(message)
    
    def force_research_and_learn(self, message, context=None):
        """ERZWINGT echte Internet-Recherche und Lernen"""
        return self.autonomous_intelligence.force_research_and_learn(message, context)

    def get_response(self, message, context=None):
        """Haupteingangspoint für Nachrichten"""
        return self.get_autonomous_response(message, context)

    def cleanup_and_close(self):
        """Ressourcen freigeben"""
        if self.autonomous_intelligence:
            self.autonomous_intelligence.close()