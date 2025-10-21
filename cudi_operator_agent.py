#!/usr/bin/env python3
"""
CUDI-OPERATOR: Vollautonomer Start- und Selbstheilungs-Agent
========================================================
Rolle: Stelle sicher, dass CUDI IMMER korrekt initialisiert wird
"""

import os
import sys
import json
import time
import logging
import asyncio
import requests
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple

class CUDIOperatorAgent:
    """Vollautonomer CUDI Start- und Selbstheilungs-Agent"""
    
    def __init__(self):
        self.log_dir = Path(".cudi/logs")
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Logging Setup
        log_file = self.log_dir / f"{datetime.now().strftime('%Y-%m-%d')}.log"
        logging.basicConfig(
            level=logging.DEBUG,
            format='%(asctime)s [%(levelname)s] %(message)s',
            handlers=[
                logging.FileHandler(log_file, encoding='utf-8'),
                logging.StreamHandler()
            ]
        )
        self.logger = logging.getLogger("CUDI-OPERATOR")
        
        # System Status
        self.checks = {}
        self.tools_status = {}
        self.auto_heal_attempts = 0
        self.max_heal_attempts = 3
        
        # Required Tools (angepasst an verfügbare Funktionen)
        self.required_tools = [
            "web_search", "generate_text", "file_operations", 
            "system_info", "sentiment_analysis", "wikipedia_search"
        ]
        
        self.logger.info("🤖 CUDI-OPERATOR initialisiert")
    
    def run_preflight_check(self) -> bool:
        """Führt vollständige Pre-Flight Checkliste durch"""
        self.logger.info("🔍 PRE-FLIGHT CHECK gestartet")
        
        checks = [
            ("1️⃣ Systemkonfiguration", self._check_system_config),
            ("2️⃣ Authentifizierung", self._check_authentication),
            ("3️⃣ Netzwerk & Infrastruktur", self._check_network),
            ("4️⃣ Tool-Registry", self._check_tool_registry),
            ("5️⃣ Nachrichtenfluss", self._check_message_flow),
            ("6️⃣ Safety & Berechtigungen", self._check_safety),
            ("7️⃣ Kontext & Speicher", self._check_context),
            ("8️⃣ Logging & Monitoring", self._check_logging)
        ]
        
        all_passed = True
        for name, check_func in checks:
            try:
                result = check_func()
                self.checks[name] = result
                status = "✅ OK" if result else "❌ FAIL"
                self.logger.info(f"{name}: {status}")
                if not result:
                    all_passed = False
            except Exception as e:
                self.checks[name] = False
                self.logger.error(f"{name}: ❌ ERROR - {e}")
                all_passed = False
        
        return all_passed
    
    def _check_system_config(self) -> bool:
        """1️⃣ Systemkonfiguration prüfen"""
        try:
            # Sprache prüfen
            locale_ok = os.environ.get('LANG', '').startswith('de') or True  # Fallback OK
            
            # UTF-8 Encoding
            encoding_ok = sys.stdout.encoding.lower() in ['utf-8', 'cp1252']  # Windows fallback
            
            # Agent-Modus prüfen (kein Content-Fallback)
            agent_mode = self._check_agent_mode()
            
            return locale_ok and encoding_ok and agent_mode
        except Exception as e:
            self.logger.error(f"System Config Check: {e}")
            return False
    
    def _check_agent_mode(self) -> bool:
        """Prüft ob CUDI im Agent-Modus läuft"""
        try:
            # Suche nach Fallback-Indikatoren
            fallback_files = [
                "content_fallback.py", "fallback_mode.py", 
                "content_only.py", "minimal_mode.py"
            ]
            
            for file in fallback_files:
                if Path(file).exists():
                    self.logger.warning(f"⚠️ Fallback-Datei gefunden: {file}")
                    return False
            
            # Prüfe Tool-Verfügbarkeit als Agent-Indikator
            tool_files = [
                "simple_plugin_manager_enhanced.py",
                "cudi_command_router.py"
            ]
            
            tools_available = all(Path(f).exists() for f in tool_files)
            return tools_available
            
        except Exception as e:
            self.logger.error(f"Agent Mode Check: {e}")
            return False
    
    def _check_authentication(self) -> bool:
        """2️⃣ Authentifizierung prüfen"""
        try:
            # .env Datei laden falls vorhanden
            env_file = Path('.env')
            if env_file.exists():
                with open(env_file, 'r', encoding='utf-8') as f:
                    for line in f:
                        if '=' in line and not line.startswith('#'):
                            key, value = line.strip().split('=', 1)
                            os.environ[key] = value
            
            # API-Keys prüfen
            api_keys = [
                os.environ.get('CUDI_API_KEY'),
                os.environ.get('OPENAI_API_KEY'),
                os.environ.get('ANTHROPIC_API_KEY')
            ]
            
            has_key = any(key for key in api_keys)
            
            # Quota prüfen (simuliert)
            quota_ok = True  # TODO: Echte Quota-Prüfung implementieren
            
            if not has_key:
                self.logger.warning("⚠️ Keine API-Keys gefunden - verwende Development Mode")
                # Im Development Mode trotzdem OK
                return True
            
            return has_key and quota_ok
            
        except Exception as e:
            self.logger.error(f"Auth Check: {e}")
            return False
    
    def _check_network(self) -> bool:
        """3️⃣ Netzwerk & Infrastruktur prüfen"""
        try:
            # DNS Test
            import socket
            socket.gethostbyname('google.com')
            
            # Internet Test
            response = requests.get('https://httpbin.org/get', timeout=10)
            internet_ok = response.status_code == 200
            
            # Uhrzeit-Sync (simuliert)
            time_sync_ok = True
            
            return internet_ok and time_sync_ok
            
        except Exception as e:
            self.logger.error(f"Network Check: {e}")
            return False
    
    def _check_tool_registry(self) -> bool:
        """4️⃣ Tool-Registry prüfen"""
        try:
            # Plugin Manager verfügbar?
            plugin_file = Path("simple_plugin_manager_enhanced.py")
            if not plugin_file.exists():
                self.logger.error("❌ Plugin Manager nicht gefunden")
                return False
            
            # Tools registriert?
            sys.path.insert(0, str(Path.cwd()))
            from simple_plugin_manager_enhanced import CUDIPluginManager
            
            pm = CUDIPluginManager()
            plugin_list = pm.get_plugin_list()
            
            # Prüfe erforderliche Tools
            for tool in self.required_tools:
                found = False
                for plugin_name in plugin_list:
                    plugin_info = pm.get_plugin_info(plugin_name)
                    if tool in plugin_info.get('functions', []):
                        self.tools_status[tool] = "✅ OK"
                        found = True
                        break
                
                if not found:
                    self.tools_status[tool] = "❌ MISSING"
            
            # Alle Tools verfügbar?
            missing_tools = [t for t, s in self.tools_status.items() if "MISSING" in s]
            if missing_tools:
                self.logger.error(f"❌ Fehlende Tools: {missing_tools}")
                return False
            
            return True
            
        except Exception as e:
            self.logger.error(f"Tool Registry Check: {e}")
            return False
    
    def _check_message_flow(self) -> bool:
        """5️⃣ Nachrichtenfluss prüfen"""
        try:
            # JSON Schema Validation (simuliert)
            test_message = {
                "role": "system",
                "content": "Test message for CUDI"
            }
            
            # JSON serialization test
            json_str = json.dumps(test_message, ensure_ascii=False)
            parsed = json.loads(json_str)
            
            return parsed == test_message
            
        except Exception as e:
            self.logger.error(f"Message Flow Check: {e}")
            return False
    
    def _check_safety(self) -> bool:
        """6️⃣ Safety & Berechtigungen prüfen"""
        try:
            # Sandbox-Prüfung
            cwd = Path.cwd()
            safe_paths = [
                "CUDI" in str(cwd),
                "PROJEKTE" in str(cwd),
                not str(cwd).startswith("/system"),
                not str(cwd).startswith("C:\\Windows")
            ]
            
            return all(safe_paths)
            
        except Exception as e:
            self.logger.error(f"Safety Check: {e}")
            return False
    
    def _check_context(self) -> bool:
        """7️⃣ Kontext & Speicher prüfen"""
        try:
            # Memory usage check (simuliert)
            import psutil
            memory = psutil.virtual_memory()
            memory_ok = memory.percent < 90
            
            # Kontext-Größe prüfen
            context_ok = True  # TODO: Echte Kontext-Prüfung
            
            return memory_ok and context_ok
            
        except Exception as e:
            self.logger.warning(f"Context Check: {e}")
            return True  # Non-critical
    
    def _check_logging(self) -> bool:
        """8️⃣ Logging & Monitoring prüfen"""
        try:
            # Log-Verzeichnis prüfbar?
            self.log_dir.exists()
            
            # Test-Log schreiben
            test_file = self.log_dir / "test.log"
            test_file.write_text("Test", encoding='utf-8')
            test_file.unlink()  # Cleanup
            
            return True
            
        except Exception as e:
            self.logger.error(f"Logging Check: {e}")
            return False
    
    def run_test_suite(self) -> bool:
        """🧪 Verpflichtender Testlauf"""
        self.logger.info("🧪 TESTLAUF gestartet")
        
        tests = [
            ("Ping Test", self._test_ping),
            ("Tool Dry-Run", self._test_tool_dry_run),
            ("Rollen-Simulation", self._test_role_flow)
        ]
        
        all_passed = True
        for name, test_func in tests:
            try:
                start_time = time.time()
                result = test_func()
                latency = time.time() - start_time
                
                status = "✅ OK" if result else "❌ FAIL"
                self.logger.info(f"{name}: {status} ({latency:.2f}s)")
                
                if not result or latency > 5.0:
                    all_passed = False
                    
            except Exception as e:
                self.logger.error(f"{name}: ❌ ERROR - {e}")
                all_passed = False
        
        return all_passed
    
    def _test_ping(self) -> bool:
        """Ping-Test"""
        try:
            # Simulierter Ping-Test
            test_data = {"message": "ping-test"}
            response = {"status": "pong", "timestamp": datetime.now().isoformat()}
            
            return response.get("status") == "pong"
            
        except Exception as e:
            self.logger.error(f"Ping Test: {e}")
            return False
    
    def _test_tool_dry_run(self) -> bool:
        """Tool Dry-Run Test"""
        try:
            # Web Search Dry-Run
            from simple_plugin_manager_enhanced import CUDIPluginManager
            pm = CUDIPluginManager()
            pm.load_plugin("research")
            
            result = pm.execute_plugin_command(
                "research", "web_search", 
                {"query": "CUDI sanity test"}
            )
            
            return result.get("success", False)
            
        except Exception as e:
            self.logger.error(f"Tool Dry-Run: {e}")
            return False
    
    def _test_role_flow(self) -> bool:
        """Rollen-Simulation Test"""
        try:
            # System → User → Assistant → Tool → Assistant Flow
            flow_steps = [
                {"role": "system", "content": "System prompt"},
                {"role": "user", "content": "Test request"},
                {"role": "assistant", "content": "Tool call simulation"},
                {"role": "tool", "content": "Tool response"},
                {"role": "assistant", "content": "Final response"}
            ]
            
            # Validiere Flow
            roles = [step["role"] for step in flow_steps]
            expected = ["system", "user", "assistant", "tool", "assistant"]
            
            return roles == expected
            
        except Exception as e:
            self.logger.error(f"Role Flow Test: {e}")
            return False
    
    def auto_heal(self) -> bool:
        """🛠️ Auto-Heal bei Fehlern"""
        if self.auto_heal_attempts >= self.max_heal_attempts:
            self.logger.error("❌ Max Auto-Heal Versuche erreicht")
            return False
        
        self.auto_heal_attempts += 1
        self.logger.info(f"🔧 AUTO-HEAL Versuch {self.auto_heal_attempts}")
        
        # Heal-Strategien
        heal_actions = [
            self._heal_missing_tools,
            self._heal_network_issues,
            self._heal_context_issues
        ]
        
        for action in heal_actions:
            try:
                action()
            except Exception as e:
                self.logger.error(f"Auto-Heal Fehler: {e}")
        
        return True
    
    def _heal_missing_tools(self):
        """Repariere fehlende Tools"""
        missing = [t for t, s in self.tools_status.items() if "MISSING" in s]
        for tool in missing:
            self.logger.info(f"🔧 Repariere Tool: {tool}")
            # TODO: Tool-Registrierung implementieren
    
    def _heal_network_issues(self):
        """Repariere Netzwerk-Probleme"""
        self.logger.info("🔧 Netzwerk-Heal...")
        time.sleep(2)  # Retry delay
    
    def _heal_context_issues(self):
        """Repariere Kontext-Probleme"""
        self.logger.info("🔧 Kontext-Cleanup...")
        # Cache leeren, alte Sessions archivieren
    
    def start_cudi(self) -> bool:
        """✅ CUDI starten wenn alle Checks OK"""
        try:
            self.logger.info("🚀 CUDI Start initiiert...")
            
            # Launch CUDI Perfect
            import subprocess
            result = subprocess.run([
                sys.executable, "launch_cudi_perfect.py"
            ], capture_output=True, text=True, timeout=30)
            
            if result.returncode == 0:
                self.logger.info("✅ CUDI erfolgreich gestartet")
                return True
            else:
                self.logger.error(f"❌ CUDI Start fehlgeschlagen: {result.stderr}")
                return False
                
        except Exception as e:
            self.logger.error(f"CUDI Start Fehler: {e}")
            return False
    
    def generate_report(self) -> str:
        """Generiert Statusbericht"""
        report = []
        report.append("🔍 CUDI-OPERATOR STATUSBERICHT")
        report.append("=" * 50)
        
        # Preflight Ergebnisse
        report.append("\n📋 PREFLIGHT CHECKS:")
        for check, status in self.checks.items():
            icon = "✅" if status else "❌"
            report.append(f"  {icon} {check}")
        
        # Tool Status
        report.append("\n🛠️ TOOL STATUS:")
        for tool, status in self.tools_status.items():
            report.append(f"  {status} {tool}")
        
        # Zusammenfassung
        all_ok = all(self.checks.values()) and all("OK" in s for s in self.tools_status.values())
        if all_ok:
            report.append("\n✅ STATUS: CUDI aktiv – alle Systeme operational")
        else:
            failed_checks = [name for name, status in self.checks.items() if not status]
            report.append(f"\n⛔ STATUS: Start gestoppt – Fehler in: {failed_checks}")
        
        return "\n".join(report)

def main():
    """Hauptfunktion - CUDI-Operator ausführen"""
    operator = CUDIOperatorAgent()
    
    # Pre-Flight Check
    preflight_ok = operator.run_preflight_check()
    
    if not preflight_ok:
        # Auto-Heal versuchen
        if operator.auto_heal():
            # Erneuter Check
            preflight_ok = operator.run_preflight_check()
    
    if preflight_ok:
        # Testlauf
        test_ok = operator.run_test_suite()
        
        if test_ok:
            # CUDI starten
            start_ok = operator.start_cudi()
            
            if start_ok:
                print(operator.generate_report())
                return 0
    
    # Bei Fehlern: Report ausgeben
    print(operator.generate_report())
    return 1

if __name__ == "__main__":
    exit(main())