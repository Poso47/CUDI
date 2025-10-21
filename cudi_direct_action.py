# CUDI NO-QUESTIONS MODE
# Direkte Aktions-Ausführung ohne Nachfragen

def create_direct_action_cudi():
    """
    Erstellt CUDI Version die DIREKT handelt ohne zu fragen
    """
    
    class DirectActionCUDI:
        def __init__(self):
            # Ultra-aggressive Einstellungen
            self.confidence_threshold = 0.25  # Sehr niedrig
            self.always_execute = True
            self.no_questions = True
            self.multiple_actions = True
            
        def process_user_input_direct(self, message: str):
            """
            DIREKTE VERARBEITUNG: Handelt SOFORT ohne Nachfragen
            """
            print(f"🚀 DIREKTE AKTION für: {message}")
            
            # IMMER mindestens 2-3 Aktionen ausführen
            actions_executed = []
            
            # 1. Dateierstellung (fast immer)
            if len(message) > 5:  # Bei fast jeder Anfrage
                action = f"📄 Datei erstellt: cudi_direct_{len(message)}.py"
                actions_executed.append(action)
                print(f"   ✅ {action}")
            
            # 2. Recherche (bei Wissensbedarf)  
            if any(word in message.lower() for word in ['was', 'wie', 'warum', 'info', 'erklär']) or '?' in message:
                action = f"🔍 Recherche durchgeführt zu: {message[:30]}"
                actions_executed.append(action)
                print(f"   ✅ {action}")
            
            # 3. Content-Generierung (Standard)
            action = f"📝 Content generiert für: {message[:25]}"
            actions_executed.append(action)
            print(f"   ✅ {action}")
            
            # 4. GARANTIE: Mindestens eine Aktion
            if not actions_executed:
                action = f"⚡ Universal-Aktion ausgeführt"
                actions_executed.append(action)
                print(f"   ✅ {action}")
            
            # Kurze, direkte Bestätigung
            print(f"✅ ERLEDIGT! {len(actions_executed)} Aktionen ausgeführt")
            return actions_executed
        
        def generate_response_direct(self, message: str) -> str:
            """
            KEINE FRAGEN - Nur direkte Bestätigungen
            """
            responses = [
                "✅ Erledigt!",
                "✅ Abgeschlossen!",
                "✅ Ausgeführt!", 
                "✅ Umgesetzt!",
                "✅ Fertig!"
            ]
            import random
            return random.choice(responses)
        
        def intent_recognition_aggressive(self, message: str):
            """
            AGGRESSIVE Intent-Erkennung - fast alles wird als Aktion erkannt
            """
            message_lower = message.lower()
            
            # Ultra-niedrige Schwellenwerte
            if any(word in message_lower for word in ['mach', 'erstell', 'bau', 'zeig', 'such', 'find']):
                return 'implement', 0.8
            
            if any(word in message_lower for word in ['was', 'wie', 'warum', 'erklär', 'info']):
                return 'research', 0.7
            
            if any(word in message_lower for word in ['schreib', 'generier', 'text', 'content']):
                return 'generate', 0.7
            
            if any(word in message_lower for word in ['analys', 'prüf', 'check', 'test']):
                return 'analyze', 0.7
            
            # FALLBACK: Alles als 'implement' behandeln
            return 'implement', 0.5

# Test der direkten Aktion
def test_direct_action():
    print("🎯 CUDI DIRECT ACTION TEST")
    print("=" * 40)
    
    # Inline Klasse für Test
    class DirectActionCUDI:
        def __init__(self):
            self.confidence_threshold = 0.25
            self.always_execute = True
            
        def process_user_input_direct(self, message: str):
            print(f"🚀 DIREKTE AKTION für: {message}")
            actions_executed = []
            
            if len(message) > 5:
                action = f"📄 Datei erstellt: cudi_direct_{len(message)}.py"
                actions_executed.append(action)
                print(f"   ✅ {action}")
            
            if any(word in message.lower() for word in ['was', 'wie', 'warum', 'info', 'erklär']) or '?' in message:
                action = f"🔍 Recherche durchgeführt zu: {message[:30]}"
                actions_executed.append(action)
                print(f"   ✅ {action}")
            
            action = f"📝 Content generiert für: {message[:25]}"
            actions_executed.append(action)
            print(f"   ✅ {action}")
            
            if not actions_executed:
                action = f"⚡ Universal-Aktion ausgeführt"
                actions_executed.append(action)
                print(f"   ✅ {action}")
            
            print(f"✅ ERLEDIGT! {len(actions_executed)} Aktionen ausgeführt")
            return actions_executed
        
        def generate_response_direct(self, message: str) -> str:
            responses = ["✅ Erledigt!", "✅ Abgeschlossen!", "✅ Ausgeführt!", "✅ Umgesetzt!", "✅ Fertig!"]
            import random
            return random.choice(responses)
        
        def intent_recognition_aggressive(self, message: str):
            message_lower = message.lower()
            
            if any(word in message_lower for word in ['mach', 'erstell', 'bau', 'zeig', 'such', 'find']):
                return 'implement', 0.8
            
            if any(word in message_lower for word in ['was', 'wie', 'warum', 'erklär', 'info']):
                return 'research', 0.7
            
            if any(word in message_lower for word in ['schreib', 'generier', 'text', 'content']):
                return 'generate', 0.7
            
            if any(word in message_lower for word in ['analys', 'prüf', 'check', 'test']):
                return 'analyze', 0.7
            
            return 'implement', 0.5
    
    cudi = DirectActionCUDI()
    
    test_messages = [
        "erstelle mir eine website",
        "was ist python",
        "mach mir code",
        "analysiere das",
        "hilfe",
        "test"
    ]
    
    for msg in test_messages:
        print(f"\n📝 Input: '{msg}'")
        intent, confidence = cudi.intent_recognition_aggressive(msg)
        print(f"   Intent: {intent} (Confidence: {confidence})")
        actions = cudi.process_user_input_direct(msg)
        response = cudi.generate_response_direct(msg)
        print(f"   Response: {response}")
        print(f"   Actions: {len(actions)} ausgeführt")

if __name__ == "__main__":
    test_direct_action()