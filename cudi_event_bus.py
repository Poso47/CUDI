"""
CUDI EVENT BUS SYSTEM
Zentrale Event-Verteilung für Komponentenkommunikation
Entspricht CUDI Maintenance Mode Event-Architektur
"""

import asyncio
import threading
import time
from datetime import datetime
from typing import Dict, Any, Callable, List, Optional
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum

class EventPriority(Enum):
    """Event-Prioritäten"""
    LOW = 1
    NORMAL = 2
    HIGH = 3
    CRITICAL = 4

@dataclass
class CUDIEvent:
    """CUDI Event-Struktur"""
    event_type: str
    data: Dict[str, Any]
    priority: EventPriority = EventPriority.NORMAL
    source: str = "unknown"
    timestamp: float = None
    event_id: str = None
    requires_ack: bool = False
    correlation_id: Optional[str] = None
    
    def __post_init__(self):
        if self.timestamp is None:
            self.timestamp = time.time()
        if self.event_id is None:
            self.event_id = f"evt_{int(self.timestamp*1000)}_{id(self)}"

class CUDIEventBus:
    """Zentraler Event-Bus für CUDI System"""
    
    def __init__(self):
        self.subscribers: Dict[str, List[Callable]] = defaultdict(list)
        self.event_queue = asyncio.Queue()
        self.running = False
        self.worker_task = None
        self.lock = threading.RLock()
        
        # Event-Statistiken
        self.stats = {
            'events_emitted': 0,
            'events_processed': 0,
            'events_failed': 0,
            'active_subscribers': 0,
            'start_time': time.time()
        }
        
        # Acknowledgment-Tracking
        self.pending_acks: Dict[str, CUDIEvent] = {}
        self.ack_timeout = 30  # Sekunden
        
    async def start(self):
        """Startet Event-Bus Worker"""
        if self.running:
            return
            
        self.running = True
        self.worker_task = asyncio.create_task(self._process_events())
        print("[EVENT-BUS] Started")
        
    def start_sync(self):
        """Startet Event-Bus synchron"""
        if self.running:
            return
            
        self.running = True
        print("📊 Event-Bus synchron aktiviert")
        
        # Background task für Event-Processing starten
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Loop läuft bereits, Task erstellen
                self.worker_task = asyncio.create_task(self._process_events())
            else:
                # Neuen Loop starten
                asyncio.run(self._process_events())
        except:
            # Fallback: Events werden im Hauptthread verarbeitet
            print("📊 Event-Bus im Hauptthread-Modus")
        
    async def stop(self):
        """Stoppt Event-Bus"""
        self.running = False
        if self.worker_task:
            self.worker_task.cancel()
            try:
                await self.worker_task
            except asyncio.CancelledError:
                pass
        print("🛑 Event-Bus gestoppt")
    
    def subscribe(self, event_type: str, handler: Callable):
        """
        Registriert Event-Handler
        
        Args:
            event_type: Event-Typ (z.B. "ACTION_*", "FILE_CREATED")
            handler: Callback-Funktion
        """
        with self.lock:
            self.subscribers[event_type].append(handler)
            self.stats['active_subscribers'] = sum(len(handlers) for handlers in self.subscribers.values())
            print(f"📝 Handler für '{event_type}' registriert")
    
    def unsubscribe(self, event_type: str, handler: Callable):
        """Entfernt Event-Handler"""
        with self.lock:
            if event_type in self.subscribers:
                try:
                    self.subscribers[event_type].remove(handler)
                    self.stats['active_subscribers'] = sum(len(handlers) for handlers in self.subscribers.values())
                except ValueError:
                    pass
    
    async def emit(self, event_type: str, data: Dict[str, Any] = None, 
                   priority: EventPriority = EventPriority.NORMAL,
                   source: str = "system", requires_ack: bool = False,
                   correlation_id: Optional[str] = None) -> str:
        """
        Emittiert Event - entspricht _event_bus.emit("ACTION_*", ...)
        
        Args:
            event_type: Event-Typ
            data: Event-Daten
            priority: Priorität
            source: Event-Quelle
            requires_ack: Erfordert Bestätigung
            correlation_id: Korrelations-ID
            
        Returns:
            Event-ID
        """
        event = CUDIEvent(
            event_type=event_type,
            data=data or {},
            priority=priority,
            source=source,
            requires_ack=requires_ack,
            correlation_id=correlation_id
        )
        
        # Event in Queue einreihen
        await self.event_queue.put(event)
        
        # Statistiken aktualisieren
        self.stats['events_emitted'] += 1
        
        # ACK-Tracking
        if requires_ack:
            self.pending_acks[event.event_id] = event
        
        print(f"[EVENT] Emitted: {event_type} [{event.event_id}]")
        return event.event_id
    
    def emit_sync(self, event_type: str, data: Dict[str, Any] = None, 
                  priority: EventPriority = EventPriority.NORMAL,
                  source: str = "system") -> str:
        """Synchrone Event-Emission für Non-Async Kontext"""
        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                # Wenn Loop läuft, verwende create_task
                task = asyncio.create_task(
                    self.emit(event_type, data, priority, source)
                )
                return f"task_{int(time.time())}"
            else:
                # Wenn keine Loop läuft, starte neue
                return loop.run_until_complete(
                    self.emit(event_type, data, priority, source)
                )
        except RuntimeError:
            # Fallback für Thread-Kontexte ohne Event-Loop
            event_id = f"sync_{int(time.time()*1000)}"
            print(f"[EVENT] Sync: {event_type} [{event_id}] (Fallback)")
            return event_id
    
    async def _process_events(self):
        """Event-Processing Worker"""
        while self.running:
            try:
                # Event aus Queue holen (mit Timeout)
                event = await asyncio.wait_for(self.event_queue.get(), timeout=1.0)
                
                # Event verarbeiten
                await self._handle_event(event)
                
                # Queue-Task als erledigt markieren
                self.event_queue.task_done()
                
            except asyncio.TimeoutError:
                # Timeout für periodische Checks
                continue
            except Exception as e:
                print(f"❌ Event-Processing Fehler: {e}")
                self.stats['events_failed'] += 1
    
    async def _handle_event(self, event: CUDIEvent):
        """Verarbeitet einzelnes Event"""
        try:
            handled = False
            
            # Finde passende Handler
            for event_pattern, handlers in self.subscribers.items():
                if self._event_matches_pattern(event.event_type, event_pattern):
                    for handler in handlers:
                        try:
                            # Handler aufrufen
                            if asyncio.iscoroutinefunction(handler):
                                await handler(event)
                            else:
                                handler(event)
                            handled = True
                        except Exception as e:
                            print(f"⚠️ Handler-Fehler für {event.event_type}: {e}")
            
            if not handled:
                print(f"🔍 Kein Handler für Event: {event.event_type}")
            
            self.stats['events_processed'] += 1
            
        except Exception as e:
            print(f"❌ Event-Handling Fehler: {e}")
            self.stats['events_failed'] += 1
    
    def _event_matches_pattern(self, event_type: str, pattern: str) -> bool:
        """Prüft ob Event-Typ zu Pattern passt"""
        # Einfache Wildcard-Unterstützung
        if pattern == "*":
            return True
        if pattern.endswith("*"):
            return event_type.startswith(pattern[:-1])
        if pattern.startswith("*"):
            return event_type.endswith(pattern[1:])
        return event_type == pattern
    
    async def ack(self, event_id: str, success: bool = True, data: Dict[str, Any] = None):
        """
        Acknowledgment für Event - entspricht _ack("...", path, meta)
        
        Args:
            event_id: Event-ID
            success: Erfolgsstatus
            data: Zusätzliche Daten
        """
        if event_id in self.pending_acks:
            original_event = self.pending_acks.pop(event_id)
            
            # ACK-Event emittieren
            await self.emit(
                f"ACK_{original_event.event_type}",
                {
                    'original_event_id': event_id,
                    'success': success,
                    'ack_data': data or {},
                    'processing_time': time.time() - original_event.timestamp
                },
                source="event_bus"
            )
            
            print(f"✅ ACK für {event_id}: {'SUCCESS' if success else 'FAILED'}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Liefert Event-Bus Statistiken"""
        return {
            **self.stats,
            'uptime': time.time() - self.stats['start_time'],
            'pending_acks': len(self.pending_acks),
            'queue_size': self.event_queue.qsize() if hasattr(self.event_queue, 'qsize') else 0
        }

# GLOBALE EVENT-BUS INSTANZ
_event_bus_instance = None

def get_event_bus() -> CUDIEventBus:
    """Singleton für Event-Bus"""
    global _event_bus_instance
    if _event_bus_instance is None:
        _event_bus_instance = CUDIEventBus()
    return _event_bus_instance

# CONVENIENCE FUNCTIONS für Maintenance Mode Kompatibilität
def emit(event_type: str, data: Dict[str, Any] = None, **kwargs) -> str:
    """Shortcut für Event-Emission"""
    return get_event_bus().emit_sync(event_type, data, **kwargs)

async def emit_async(event_type: str, data: Dict[str, Any] = None, **kwargs) -> str:
    """Async Event-Emission"""
    return await get_event_bus().emit(event_type, data, **kwargs)

async def ack(event_id: str, success: bool = True, path: str = None, meta: Dict[str, Any] = None):
    """ACK-Funktion entsprechend _ack("...", path, meta)"""
    ack_data = {}
    if path:
        ack_data['path'] = path
    if meta:
        ack_data.update(meta)
    
    await get_event_bus().ack(event_id, success, ack_data)

if __name__ == "__main__":
    async def test_event_bus():
        # Event-Bus testen
        bus = CUDIEventBus()
        await bus.start()
        
        # Test-Handler registrieren
        def test_handler(event: CUDIEvent):
            print(f"🎯 Handler empfing: {event.event_type} - {event.data}")
        
        bus.subscribe("ACTION_*", test_handler)
        bus.subscribe("FILE_CREATED", test_handler)
        
        # Test-Events senden
        await bus.emit("ACTION_START", {'action': 'test', 'user': 'system'})
        await bus.emit("FILE_CREATED", {'path': 'test.py', 'size': 1024})
        await bus.emit("ACTION_SUCCESS", {'action': 'test', 'duration': 0.5})
        
        # Kurz warten für Processing
        await asyncio.sleep(1)
        
        # Statistiken anzeigen
        stats = bus.get_stats()
        print(f"📊 Event-Bus Stats: {stats}")
        
        await bus.stop()
    
    asyncio.run(test_event_bus())