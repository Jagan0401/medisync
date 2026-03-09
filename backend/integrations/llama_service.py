import os
import itertools
import logging

import requests

logger = logging.getLogger(__name__)

GROQ_API_URL = 'https://api.groq.com/openai/v1/chat/completions'

# Round-robin key rotation
_keys = [k.strip() for k in os.environ.get('GROQ_API_KEYS', '').split(',') if k.strip()]
_key_cycle = itertools.cycle(_keys) if _keys else None


def generate_ai_response(prompt):
    """Call Groq Llama-3 and return the text response."""
    if not _key_cycle:
        logger.warning('No GROQ_API_KEYS configured – returning fallback')
        return 'AI service is not configured.'

    api_key = next(_key_cycle)
    headers = {'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'}
    payload = {
        'model': 'llama-3.1-8b-instant',
        'messages': [
            {'role': 'system', 'content': 'You are a helpful healthcare assistant.'},
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
