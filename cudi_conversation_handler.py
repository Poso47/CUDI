"""
CUDI INTELLIGENT CONVERSATION HANDLER
Behandelt normale Gespräche vs. Action-Requests intelligent
"""

import random

class CUDIConversationHandler:
    """Intelligente Konversationsbehandlung"""
    
    def __init__(self, gui_instance):
        self.gui = gui_instance
        
    def process_message_intelligently(self, user_message: str):
        """Hauptfunktion: Unterscheidet Konversation von Action-Requests"""
        if not user_message.strip():
            return
        
        message_lower = user_message.lower().strip()
        
        # Definiere Keywords
        conversation_keywords = [
            'hallo', 'hi', 'hey', 'guten tag', 'morgen', 'abend', 
            'wie geht', 'danke', 'bitte', 'ok', 'ja', 'nein', 
            'gut', 'schlecht', 'super', 'toll', 'cool', 'wow', 
            'aha', 'verstehe', 'klar', 'sicher', 'genau', 'richtig', 'falsch'
        ]
        
        action_keywords = [
            'erstell', 'mach', 'generier', 'schreib', 'analys', 'prüf', 
            'test', 'such', 'find', 'öffn', 'start', 'stopp', 'lösch', 
            'änder', 'korrigier', 'reparier', 'install', 'download', 
            'upload', 'speicher', 'laden', 'code', 'datei', 'script'
        ]
        
        # Erweiterte Klassifizierung
        is_conversation = any(keyword in message_lower for keyword in conversation_keywords)
        is_action_request = any(keyword in message_lower for keyword in action_keywords)
        is_short_message = len(user_message.split()) <= 3
        is_question = user_message.strip().endswith('?')
        has_command_syntax = user_message.startswith('/')
        
        # Intelligente Entscheidung
        if has_command_syntax:
            # Direkte Commands immer als Action behandeln
            self._handle_action_request(user_message)
        elif (is_conversation and not is_action_request) or (is_short_message and not is_action_request and not is_question):
            self._handle_conversation(user_message)
        elif is_question and not is_action_request:
            # Fragen intelligent beantworten
            self._handle_intelligent_question(user_message)
        else:
            self._handle_action_request(user_message)
    
    def _handle_conversation(self, user_message: str):
        """Behandelt normale Gespräche"""
        message_lower = user_message.lower().strip()
        
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
        
        response = random.choice(responses)
        self.gui.add_chat_message("💬 CUDI", response)
    
    def _handle_intelligent_question(self, user_message: str):
        """Behandelt intelligente Fragen"""
        # Aktiviere KI-Brain für komplexe Fragen
        if hasattr(self.gui, 'brain') and self.gui.brain:
            self.gui.process_user_input(user_message)
        else:
            # Fallback für intelligente Antworten
            self._provide_intelligent_response(user_message)
    
    def _provide_intelligent_response(self, user_message: str):
        """Liefert intelligente Antworten ohne Brain"""
        message_lower = user_message.lower()
        
        if 'wie' in message_lower and 'funktioniert' in message_lower:
            response = "Ich kann dir gerne erklären, wie etwas funktioniert! Lass mich das analysieren und dir eine detaillierte Antwort geben. 🔍"
        elif 'was ist' in message_lower or 'was sind' in message_lower:
            response = "Das ist eine interessante Frage! Ich recherchiere das für dich und gebe dir eine umfassende Antwort. 📚"
        elif 'warum' in message_lower:
            response = "Gute Frage! Lass mich die Hintergründe analysieren und dir eine fundierte Antwort liefern. 🤔"
        elif 'hilfe' in message_lower or 'help' in message_lower:
            response = "Natürlich helfe ich dir gerne! Beschreib mir genauer, womit du Unterstützung brauchst. ⚡"
        else:
            response = "Das ist eine spannende Frage! Lass mich das für dich durchdenken und eine qualifizierte Antwort finden. 🧠"
        
        self.gui.add_chat_message("🤖 CUDI", response)
        # Dann die eigentliche Frage verarbeiten
        if hasattr(self.gui, 'process_user_input'):
            self.gui.process_user_input(user_message)
    
    def _handle_action_request(self, user_message: str):
        """Behandelt Action-Requests - ruft originale Funktion auf"""
        # Verwende die originale Action-Processing Logik
        if hasattr(self.gui, 'process_user_input_no_questions_original'):
            self.gui.process_user_input_no_questions_original(user_message)
        else:
            self.gui.process_user_input(user_message)

if __name__ == "__main__":
    print("🧠 CUDI Conversation Handler bereit!")