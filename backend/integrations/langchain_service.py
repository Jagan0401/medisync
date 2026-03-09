"""
LangChain Integration for WhatsApp Conversation Management
==========================================
Provides persistent memory management and advanced NLP capabilities
using LangChain with MongoDB-backed conversation storage.

Features:
- Persistent conversation memory across sessions
- Multi-language support
- Intent detection with context awareness
- Session management per patient
"""

import json
import logging
from datetime import datetime
from typing import Dict, List, Optional

try:
    from langchain.memory import ConversationBufferMemory
    from langchain.llms.base import LLM
    from langchain.callbacks.manager import CallbackManager
    LANGCHAIN_AVAILABLE = True
except ImportError:
    LANGCHAIN_AVAILABLE = False

from config.db import db
from integrations.llama_service import generate_ai_response

logger = logging.getLogger(__name__)


class PatientConversationMemory:
    """
    Persists WhatsApp conversations in MongoDB for each patient.
    Maintains context across sessions and server restarts.
    """

    def __init__(self, patient_id: str):
        self.patient_id = patient_id
        self.collection = db.whatsapp_conversations

    def add_message(self, role: str, content: str, language: str = 'en'):
        """Log a new message to conversation history."""
        self.collection.update_one(
            {'patient_id': self.patient_id},
            {
                '$push': {
                    'messages': {
                        'role': role,  # 'patient' or 'assistant'
                        'content': content,
                        'language': language,
                        'timestamp': datetime.utcnow().isoformat(),
                    }
                },
                '$set': {
                    'updated_at': datetime.utcnow().isoformat(),
                }
            },
            upsert=True,
        )

    def get_context(self, limit: int = 10) -> str:
        """Retrieve recent conversation history as formatted string."""
        doc = self.collection.find_one(
            {'patient_id': self.patient_id},
            {'messages': {'$slice': -limit}}
        )
        if not doc or not doc.get('messages'):
            return ''

        context_lines = []
        for msg in doc['messages'][-limit:]:
            role = 'Patient' if msg['role'] == 'patient' else 'MediSync'
            content = msg['content']
            context_lines.append(f"{role}: {content}")

        return '\n'.join(context_lines)

    def get_last_message_timestamp(self) -> Optional[str]:
        """Get timestamp of last message in conversation."""
        doc = self.collection.find_one(
            {'patient_id': self.patient_id},
            {'messages': {'$slice': -1}}
        )
        if doc and doc.get('messages'):
            return doc['messages'][-1].get('timestamp')
        return None

    def clear_conversation(self):
        """Reset conversation history (new session)."""
        self.collection.delete_one({'patient_id': self.patient_id})


class WhatsAppConversationManager:
    """
    Advanced WhatsApp conversation handler using LangChain patterns
    without requiring full LangChain dependency.
    """

    def __init__(self, patient_id: str, patient_name: str, disease: str = ''):
        self.patient_id = patient_id
        self.patient_name = patient_name
        self.disease = disease
        self.memory = PatientConversationMemory(patient_id)

    def analyze_patient_intent_with_context(
        self,
        message: str,
        preferred_language: str = 'en'
    ) -> Dict:
        """
        Analyze patient's message considering conversation history.
        More sophisticated than simple classific.
        """
        context = self.memory.get_context(limit=5)
        
        prompt = (
            f"You are analyzing a patient's WhatsApp message in context of previous conversations.\n\n"
            f"CONVERSATION HISTORY:\n{context if context else 'No previous messages'}\n\n"
            f"CURRENT MESSAGE: \"{message}\"\n"
            f"PATIENT: {self.patient_name}\n"
            f"DISEASE: {self.disease}\n"
            f"LANGUAGE: {preferred_language}\n\n"
            f"Analyze and return ONLY a JSON object (no markdown):\n"
            f"{{\n"
            f'  "intent": "book_appointment|confirm_yes|cancel|language_select|query|greeting",\n'
            f'  "confidence": 0.0-1.0,\n'
            f'  "should_escalate": true/false,\n'
            f'  "requires_booking": true/false,\n'
            f'  "estimated_sentiment": "positive|neutral|negative"\n'
            f"}}"
        )

        try:
            response = generate_ai_response(prompt)
            # Parse JSON from response
            cleaned = response.strip()
            if cleaned.startswith('```'):
                cleaned = cleaned.split('\n', 1)[1] if '\n' in cleaned else cleaned[3:]
                if cleaned.endswith('```'):
                    cleaned = cleaned[:-3]
            result = json.loads(cleaned.strip())
            
            # Log the analysis
            self.memory.add_message('system_analysis', json.dumps(result))
            return result
        except (json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to parse intent analysis: {e}")
            return {
                'intent': 'query',
                'confidence': 0.5,
                'should_escalate': False,
                'requires_booking': False,
                'estimated_sentiment': 'neutral'
            }

    def generate_contextual_response(
        self,
        message: str,
        patient_info: Dict,
        preferred_language: str = 'en'
    ) -> str:
        """
        Generate AI response with awareness of conversation history
        and patient context.
        """
        context = self.memory.get_context(limit=8)

        prompt = (
            f"You are MediSync, a friendly healthcare WhatsApp assistant.\n\n"
            f"CONVERSATION HISTORY:\n{context if context else 'Starting new conversation'}\n\n"
            f"PATIENT INFO:\n"
            f"- Name: {patient_info.get('name', 'Patient')}\n"
            f"- Age: {patient_info.get('age', 'Unknown')}\n"
            f"- Disease: {patient_info.get('disease', 'General')}\n"
            f"- Last Test: {patient_info.get('last_test', 'Unknown')}\n"
            f"- Last Result: {patient_info.get('last_result', 'Unknown')}\n\n"
            f"PATIENT MESSAGE: \"{message}\"\n\n"
            f"Respond helpfully in 2-3 sentences in {preferred_language}.\n"
            f"Consider the conversation context above.\n"
            f"If appropriate, encourage booking an appointment.\n"
            f"Keep tone warm and professional."
        )

        response = generate_ai_response(prompt)
        self.memory.add_message('assistant', response, preferred_language)
        return response

    def log_exchange(
        self,
        patient_message: str,
        assistant_response: str,
        language: str = 'en'
    ):
        """Log bidirectional conversation exchange."""
        self.memory.add_message('patient', patient_message, language)
        self.memory.add_message('assistant', assistant_response, language)


class MultiLanguageProcessor:
    """
    Handles language detection and translation with LangChain integration.
    """

    SUPPORTED_LANGUAGES = {
        'en': 'English',
        'hi': 'Hindi',
        'ta': 'Tamil',
        'te': 'Telugu',
        'kn': 'Kannada',
        'ml': 'Malayalam',
        'bn': 'Bengali',
        'mr': 'Marathi',
        'gu': 'Gujarati',
        'pa': 'Punjabi',
        'ur': 'Urdu',
    }

    @staticmethod
    def detect_language(text: str) -> str:
        """
        Detect language from text using AI.
        Returns ISO 639-1 code.
        """
        prompt = (
            f"Detect the language of this text.\n"
            f"TEXT: \"{text}\"\n\n"
            f"Return ONLY the ISO 639-1 language code (e.g., 'en', 'ta', 'hi')."
        )
        try:
            response = generate_ai_response(prompt).strip().lower()
            # Validate against supported languages
            code = response.split()[0]
            return code if code in MultiLanguageProcessor.SUPPORTED_LANGUAGES else 'en'
        except Exception:
            return 'en'

    @staticmethod
    def get_language_name(code: str) -> str:
        """Get full language name from ISO code."""
        return MultiLanguageProcessor.SUPPORTED_LANGUAGES.get(code, 'English')


# ─────────────────────────────────────────────────────────────────────
# Utility Functions for WhatsApp Integration
# ─────────────────────────────────────────────────────────────────────

def get_patient_memory(patient_id: str) -> PatientConversationMemory:
    """Factory for getting patient conversation memory."""
    return PatientConversationMemory(patient_id)


def create_conversation_manager(
    patient_id: str,
    patient_name: str,
    disease: str = ''
) -> WhatsAppConversationManager:
    """Factory for creating conversation manager instances."""
    return WhatsAppConversationManager(patient_id, patient_name, disease)


if __name__ == '__main__':
    # Example usage
    print("LangChain Service for WhatsApp loaded successfully")
    print(f"LangChain available: {LANGCHAIN_AVAILABLE}")
    print(f"Supported languages: {MultiLanguageProcessor.SUPPORTED_LANGUAGES}")
