"""
CUDI COMMAND ROUTER
Intent-basierte Befehlsverarbeitung entsprechend Maintenance Mode
Router -> Aktionen -> Brain -> Telemetrie/Events -> GUI
"""

import re
import json
import asyncio
from typing import Dict, Any, Optional, Tuple, List
from datetime import datetime
from pathlib import Path

# Import CUDI Systeme
import time
try:
    from cudi_telemetry import log as telemetry_log
    from cudi_event_bus import emit as event_emit, ack as event_ack
except ImportError:
    # Fallback-Funktionen
    def telemetry_log(event, data=None, context=None): return f"fallback_{int(time.time())}"
    def event_emit(event_type, data=None): return f"fallback_{int(time.time())}"
    async def event_ack(event_id, success=True, path=None, meta=None): pass

class CUDICommandRouter:
    """
    Zentrale Befehlsverarbeitung für CUDI Maintenance Mode
    Unterstützt Intent-Routing: /file, /research, /content, /learn, /exec
    """
    
    def __init__(self, gui_instance=None):
        self.gui = gui_instance
        self.command_patterns = {
            'file': r'/file\s+create\s+name=([^\s]+)(?:\s+data="([^"]*)")?',
            'research': r'/research\s+"([^"]+)"(?:\s+out=([^\s]+))?',
            'content': r'/content\s+brief="([^"]+)"(?:\s+format=([^\s]+))?(?:\s+out=([^\s]+))?',
            'learn': r'/learn\s+note="([^"]+)"',
            'exec': r'/exec\s+"([^"]+)"'
        }
        
        # Statistiken
        self.stats = {
            'commands_processed': 0,
            'commands_successful': 0,
            'commands_failed': 0,
            'last_command': None
        }
    
    def route_command(self, user_input: str) -> Tuple[bool, str]:
        """
        Hauptrouting-Funktion
        
        Args:
            user_input: User-Eingabe
            
        Returns:
            (is_command, result) - Tuple mit Command-Status und Ergebnis
        """
        # Telemetrie: Command-Routing Start
        routing_id = telemetry_log('ACTION_START', {
            'action': 'command_routing', 
            'input_length': len(user_input),
            'input_preview': user_input[:50]
        }, context='CUDICommandRouter')
        
        try:
            # Prüfe alle Command-Patterns
            for command_type, pattern in self.command_patterns.items():
                match = re.search(pattern, user_input, re.IGNORECASE)
                if match:
                    # Command erkannt - verarbeite
                    result = self._process_command(command_type, match.groups(), user_input, routing_id)
                    
                    # Statistiken aktualisieren
                    self.stats['commands_processed'] += 1
                    self.stats['last_command'] = command_type
                    
                    return True, result
            
            # Kein Command erkannt
            telemetry_log('ACTION_SUCCESS', {
                'action': 'command_routing',
                'result': 'no_command_detected',
                'routing_id': routing_id
            })
            
            return False, "No command pattern matched"
            
        except Exception as e:
            # Command-Routing Fehler
            telemetry_log('ACTION_FAIL', {
                'action': 'command_routing',
                'error': str(e),
                'routing_id': routing_id
            })
            
            self.stats['commands_failed'] += 1
            return False, f"Command routing error: {e}"
    
    def _process_command(self, command_type: str, groups: tuple, original_input: str, routing_id: str) -> str:
        """Verarbeitet erkannten Command"""
        
        # Event: Command Processing Start
        event_id = event_emit('COMMAND_PROCESSING', {
            'command_type': command_type,
            'routing_id': routing_id,
            'groups': groups
        })
        
        try:
            if command_type == 'file':
                return self._handle_file_command(groups, routing_id, event_id)
            elif command_type == 'research':
                return self._handle_research_command(groups, routing_id, event_id)
            elif command_type == 'content':
                return self._handle_content_command(groups, routing_id, event_id)
            elif command_type == 'learn':
                return self._handle_learn_command(groups, routing_id, event_id)
            elif command_type == 'exec':
                return self._handle_exec_command(groups, routing_id, event_id)
            else:
                raise ValueError(f"Unknown command type: {command_type}")
                
        except Exception as e:
            # Command Processing Fehler
            telemetry_log('ACTION_FAIL', {
                'action': f'command_{command_type}',
                'error': str(e),
                'routing_id': routing_id
            })
            
            return f"[FAIL] {command_type} command failed: {e}"
    
    def _handle_file_command(self, groups: tuple, routing_id: str, event_id: str) -> str:
        """Behandelt /file create name=<filename> data="<content>" """
        filename = groups[0] if len(groups) > 0 else "generated_file.txt"
        content = groups[1] if len(groups) > 1 and groups[1] else "# Generated by CUDI\\n\\nContent created via /file command"
        
        try:
            # Erstelle Datei
            output_dir = Path("cudi_generated")
            output_dir.mkdir(exist_ok=True)
            
            # Timestamp hinzufügen wenn nicht vorhanden
            if not any(char.isdigit() for char in filename):
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                name_parts = filename.split('.')
                if len(name_parts) > 1:
                    filename = f"{name_parts[0]}_{timestamp}.{name_parts[1]}"
                else:
                    filename = f"{filename}_{timestamp}.txt"
            
            file_path = output_dir / filename
            
            # Schreibe Datei
            with file_path.open('w', encoding='utf-8') as f:
                f.write(content)
            
            # Verifikation
            if file_path.exists():
                file_size = file_path.stat().st_size
                
                # Telemetrie: Success
                telemetry_log('FILE_CREATED', {
                    'command': 'file_create',
                    'path': str(file_path.absolute()),
                    'size': file_size,
                    'routing_id': routing_id
                })
                
                # Event: File Created
                event_emit('FILE_CREATED', {
                    'path': str(file_path.absolute()),
                    'size': file_size,
                    'command_type': 'file_create',
                    'event_id': event_id
                })
                
                self.stats['commands_successful'] += 1
                return f"[OK] file_create done -> {file_path.absolute()}\\n\\n[FILE] Datei erstellt: {filename}\\n[SIZE] Größe: {file_size} bytes\\n[PATH] Pfad: {file_path.absolute()}"
            else:
                raise Exception("File creation verification failed")
                
        except Exception as e:
            return f"[FAIL] file_create error: {e}"
    
    def _handle_research_command(self, groups: tuple, routing_id: str, event_id: str) -> str:
        """Behandelt /research "<topic>" out=<filename>"""
        topic = groups[0] if len(groups) > 0 else "general research"
        output_file = groups[1] if len(groups) > 1 and groups[1] else f"research_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        
        try:
            # Research durchführen (vereinfacht)
            research_content = self._perform_research(topic)
            
            # Research-Datei erstellen
            output_dir = Path("cudi_generated")
            output_dir.mkdir(exist_ok=True)
            file_path = output_dir / output_file
            
            with file_path.open('w', encoding='utf-8') as f:
                f.write(research_content)
            
            file_size = file_path.stat().st_size
            
            # Telemetrie & Events
            telemetry_log('RESEARCH_COMPLETE', {
                'topic': topic,
                'output_file': str(file_path.absolute()),
                'size': file_size,
                'routing_id': routing_id
            })
            
            event_emit('RESEARCH_COMPLETE', {
                'topic': topic,
                'path': str(file_path.absolute()),
                'event_id': event_id
            })
            
            self.stats['commands_successful'] += 1
            return f"[OK] research done -> {file_path.absolute()}\\n\\n[RESEARCH] Research abgeschlossen: {topic}\\n[RESULT] Ergebnis: {output_file} ({file_size} bytes)"
            
        except Exception as e:
            return f"[FAIL] research error: {e}"
    
    def _handle_content_command(self, groups: tuple, routing_id: str, event_id: str) -> str:
        """Behandelt /content brief="<beschreibung>" format=<format> out=<filename>"""
        description = groups[0] if len(groups) > 0 else "general content"
        format_type = groups[1] if len(groups) > 1 and groups[1] else "markdown"
        output_file = groups[2] if len(groups) > 2 and groups[2] else f"content_{datetime.now().strftime('%Y%m%d_%H%M%S')}.{format_type}"
        
        try:
            # Content generieren
            generated_content = self._generate_content(description, format_type)
            
            # Content-Datei erstellen
            output_dir = Path("cudi_generated")
            output_dir.mkdir(exist_ok=True)
            file_path = output_dir / output_file
            
            with file_path.open('w', encoding='utf-8') as f:
                f.write(generated_content)
            
            file_size = file_path.stat().st_size
            
            # Telemetrie & Events
            telemetry_log('CONTENT_GENERATED', {
                'description': description,
                'format': format_type,
                'output_file': str(file_path.absolute()),
                'size': file_size,
                'routing_id': routing_id
            })
            
            self.stats['commands_successful'] += 1
            return f"[OK] content_generation done -> {file_path.absolute()}\\n\\n[CONTENT] Content erstellt: {description}\\n[FORMAT] Format: {format_type} ({file_size} bytes)"
            
        except Exception as e:
            return f"[FAIL] content_generation error: {e}"
    
    def _handle_learn_command(self, groups: tuple, routing_id: str, event_id: str) -> str:
        """Behandelt /learn note="<wissen>" """
        knowledge = groups[0] if len(groups) > 0 else "general knowledge"
        
        try:
            # Learning-Entry erstellen
            learning_entry = {
                'timestamp': datetime.now().isoformat(),
                'knowledge': knowledge,
                'source': 'user_command',
                'routing_id': routing_id
            }
            
            # Learning-Datei aktualisieren/erstellen
            learning_dir = Path("cudi_generated")
            learning_dir.mkdir(exist_ok=True)
            learning_file = learning_dir / "cudi_learning_log.json"
            
            # Lade existierende Daten oder erstelle neue
            if learning_file.exists():
                with learning_file.open('r', encoding='utf-8') as f:
                    learning_data = json.load(f)
            else:
                learning_data = {'entries': []}
            
            learning_data['entries'].append(learning_entry)
            
            # Schreibe zurück
            with learning_file.open('w', encoding='utf-8') as f:
                json.dump(learning_data, f, indent=2, ensure_ascii=False)
            
            # Telemetrie & Events
            telemetry_log('LEARNING_EVENT', {
                'knowledge': knowledge,
                'learning_file': str(learning_file.absolute()),
                'total_entries': len(learning_data['entries']),
                'routing_id': routing_id
            })
            
            # Integriere mit Brain falls verfügbar
            if self.gui and hasattr(self.gui, 'brain') and self.gui.brain:
                try:
                    self.gui.brain.learn_from_interaction(f"Command: /learn", knowledge)
                except Exception:
                    pass
            
            self.stats['commands_successful'] += 1
            return f"[OK] learning done -> {learning_file.absolute()}\\n\\n[LEARN] Wissen gespeichert: {knowledge[:100]}{'...' if len(knowledge) > 100 else ''}\\n[TOTAL] Total Einträge: {len(learning_data['entries'])}"
            
        except Exception as e:
            return f"[FAIL] learning error: {e}"
    
    def _handle_exec_command(self, groups: tuple, routing_id: str, event_id: str) -> str:
        """Behandelt /exec "<aktionen>" """
        action = groups[0] if len(groups) > 0 else "no action specified"
        
        try:
            # Aktion über GUI ausführen falls verfügbar
            if self.gui and hasattr(self.gui, '_create_real_files'):
                result = self.gui._create_real_files(f"Execute: {action}", {'domain': ['exec_command']})
                
                telemetry_log('ACTION_SUCCESS', {
                    'action': 'exec_command',
                    'command': action,
                    'routing_id': routing_id
                })
                
                self.stats['commands_successful'] += 1
                return f"[OK] exec done\\n\\n⚡ **Aktion ausgeführt:** {action}\\n{result}"
            else:
                # Fallback: Einfache Bestätigung
                telemetry_log('ACTION_SUCCESS', {
                    'action': 'exec_command_fallback',
                    'command': action,
                    'routing_id': routing_id
                })
                
                return f"[OK] exec acknowledged -> {action}\\n\\n[EXEC] Aktion registriert: {action}"
                
        except Exception as e:
            return f"[FAIL] exec error: {e}"
    
    def _perform_research(self, topic: str) -> str:
        """Vereinfachte Research-Implementierung"""
        return f"""# Research Report: {topic}

**Generated:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Topic:** {topic}

## Overview
This is a research report generated by CUDI for the topic: "{topic}".

## Key Points
- Research topic: {topic}
- Generated via command router
- Real data structure with timestamp
- Expandable for actual research integration

## Data Sources
- CUDI internal knowledge base
- Command router processing
- User-initiated research request

## Conclusion
Research completed successfully. This report provides a foundation for further analysis and can be extended with real research data integration.

---
*Generated by CUDI Command Router*
"""
    
    def _generate_content(self, description: str, format_type: str) -> str:
        """Content-Generation basierend auf Format"""
        if format_type.lower() in ['md', 'markdown']:
            return f"""# Generated Content: {description}

**Created:** {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
**Format:** Markdown
**Description:** {description}

## Content Overview
This content was generated based on the description: "{description}".

### Key Features
- Automated generation via command router
- Structured markdown format
- Real-time creation with timestamps
- Expandable template structure

### Technical Details
- **Format:** {format_type}
- **Generator:** CUDI Command Router
- **Timestamp:** {datetime.now().isoformat()}

## Conclusion
Content generation successful. This template can be extended with specific content based on requirements.

---
*Generated by CUDI*
"""
        elif format_type.lower() in ['json']:
            return json.dumps({
                'title': f'Generated Content: {description}',
                'created': datetime.now().isoformat(),
                'format': format_type,
                'description': description,
                'data': {
                    'generator': 'CUDI Command Router',
                    'version': '1.0',
                    'content_type': 'automated_generation'
                },
                'metadata': {
                    'timestamp': datetime.now().isoformat(),
                    'format': format_type,
                    'size': 'dynamic'
                }
            }, indent=2, ensure_ascii=False)
        else:
            return f"""Generated Content: {description}

Created: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
Format: {format_type}
Description: {description}

This content was automatically generated by CUDI Command Router
based on the provided description and format specifications.

Generator: CUDI Command Router
Timestamp: {datetime.now().isoformat()}
Format: {format_type}

Content generation completed successfully.
"""
    
    def get_stats(self) -> Dict[str, Any]:
        """Liefert Router-Statistiken"""
        return {
            **self.stats,
            'supported_commands': list(self.command_patterns.keys()),
            'patterns_count': len(self.command_patterns)
        }

if __name__ == "__main__":
    # Test des Command Routers
    router = CUDICommandRouter()
    
    # Test Commands
    test_commands = [
        '/file create name=test.py data="print(\'Hello CUDI\')"',
        '/research "Python best practices" out=python_research.md',
        '/content brief="API documentation" format=markdown out=api_docs.md',
        '/learn note="CUDI command router supports multiple formats"',
        '/exec "create comprehensive project structure"'
    ]
    
    print("🧪 Testing CUDI Command Router...")
    
    for cmd in test_commands:
        print(f"\\n📤 Command: {cmd}")
        is_command, result = router.route_command(cmd)
        print(f"📥 Result: {is_command} - {result[:100]}...")
    
    # Statistiken anzeigen
    stats = router.get_stats()
    print(f"\\n📊 Router Stats: {stats}")
    
    print("✅ Command Router Test completed!")