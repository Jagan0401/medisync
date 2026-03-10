import os
import itertools
import logging

import requests

logger = logging.getLogger(__name__)

GROQ_API_URL = 'https://api.groq.com/openai/v1/chat/completions'

# Round-robin key rotation
_keys = [k.strip() for k in os.environ.get('GROQ_API_KEYS', '').split(',') if k.strip()]
_key_cycle = itertools.cycle(_keys) if _keys else None

# Healthcare-tuned system prompt for MediSynC
SYSTEM_PROMPT = (
    'You are MediSynC AI \u2014 a multilingual healthcare assistant for a hospital '
    'outreach platform in India. You communicate with patients via WhatsApp.\n\n'
    'Core capabilities:\n'
    '- Translate healthcare messages accurately into Indian languages '
    '(Tamil, Hindi, Telugu, Kannada, Malayalam, Bengali, Marathi, Gujarati, Punjabi, Urdu).\n'
    '- Use simple, patient-friendly language \u2014 avoid complex medical jargon.\n'
    '- Preserve all emojis, numbers, dates, doctor names, hospital names, and test names '
    'exactly as-is during translation.\n'
    '- Be empathetic, warm, and culturally sensitive.\n'
    '- When translating menus with numbered options (1\ufe0f\u20e3, 2\ufe0f\u20e3, 3\ufe0f\u20e3), '
    'translate the description text but keep the emoji numbers unchanged.\n\n'
    'Rules:\n'
    '- NEVER add explanations, notes, or commentary \u2014 return ONLY the requested output.\n'
    '- NEVER switch to English unless explicitly asked.\n'
    '- For medical terms without a common local equivalent, use the English term '
    'in parentheses after the local term.'
)


def generate_ai_response(prompt, system_prompt=None):
    """Call Groq Llama-3 and return the text response."""
    if not _key_cycle:
        logger.warning('No GROQ_API_KEYS configured \u2013 returning fallback')
        return 'AI service is not configured.'

    api_key = next(_key_cycle)
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    payload = {
        'model': 'llama-3.1-8b-instant',
        'messages': [
            {'role': 'system', 'content': system_prompt or SYSTEM_PROMPT},
            {'role': 'user', 'content': prompt},
        ],
        'temperature': 0.7,
    }
    try:
        resp = requests.post(GROQ_API_URL, headers=headers, json=payload, timeout=30)
        resp.raise_for_status()
        return resp.json()['choices'][0]['message']['content']
    except Exception as e:
        logger.error('Groq API error: %s', e)
        return f'AI service error: {e}'
