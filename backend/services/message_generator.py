"""
Message Generator — Creates personalized WhatsApp messages per risk tier.
Uses AI (Groq/Llama) for Critical patients, templates for others.
Includes multilingual translation via AI.
"""

from integrations.llama_service import generate_ai_response

# Menu appended to every automated outbound message
MENU_TEXT = (
    "\n\n📋 Please reply with a number:\n"
    "1️⃣ Book Appointment\n"
    "2️⃣ Remind Me Later\n"
    "3️⃣ Choose Language"
)

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


def translate_message(text, target_language_code):
    """Translate a message to the target language using AI.
    Returns the translated text, or original if language is English or unknown."""
    if not target_language_code or target_language_code == 'en':
        return text
    lang_name = SUPPORTED_LANGUAGES.get(target_language_code)
    if not lang_name:
        return text
    prompt = (
        f"Translate the following healthcare message to {lang_name}. "
        f"Keep the emojis. Do NOT add any explanation, just return the translated text.\n\n"
        f"{text}"
    )
    translated = generate_ai_response(prompt)
    return translated.strip() if translated else text


def detect_language_and_intent(text):
    """Use AI to detect language and booking intent from a patient's WhatsApp reply.
    Returns dict with keys: language, intent, date, test, purpose."""
    prompt = (
        "You are a healthcare assistant parsing a patient's WhatsApp reply. "
        "Analyze this message and return ONLY a JSON object (no markdown, no explanation) with these keys:\n"
        '- "language": ISO 639-1 code (en, hi, ta, te, kn, ml, bn, mr, gu, pa, ur)\n'
        '- "intent": one of "book_appointment", "confirm_yes", "cancel", "query", "greeting"\n'
        '- "date": extracted date if any (YYYY-MM-DD format), or null\n'
        '- "test": extracted test name if any, or null\n'
        '- "purpose": brief purpose if mentioned, or null\n\n'
        f'Patient message: "{text}"'
    )
    raw = generate_ai_response(prompt)
    # Parse the JSON from AI response
    import json
    try:
        # Strip markdown code fences if present
        cleaned = raw.strip()
        if cleaned.startswith('```'):
            cleaned = cleaned.split('\n', 1)[1] if '\n' in cleaned else cleaned[3:]
            if cleaned.endswith('```'):
                cleaned = cleaned[:-3]
            cleaned = cleaned.strip()
        return json.loads(cleaned)
    except (json.JSONDecodeError, ValueError):
        return {'language': 'en', 'intent': 'query', 'date': None, 'test': None, 'purpose': None}


def generate_message(patient, risk):
    """Return a personalized WhatsApp reminder message."""
    name = patient.get('name', 'Patient')
    age = patient.get('age', '')
    disease = patient.get('disease', '')
    test = patient.get('last_test', patient.get('test_required', 'routine check'))
    result = patient.get('last_result', 'N/A')

    if risk == 'Critical':
        msg = _ai_message(name, age, disease, test, result)
    elif risk == 'High':
        msg = _high_risk_template(name, age, disease, test, result)
    elif risk == 'Medium':
        msg = _medium_risk_template(name, age, disease, test, result)
    else:
        msg = _low_risk_template(name, disease, test)

    return msg + MENU_TEXT


def _ai_message(name, age, disease, test, result):
    """Use AI to craft a highly personalized critical-risk message."""
    prompt = f"""You are a healthcare outreach assistant. Write a short, empathetic WhatsApp reminder message (max 200 words) for a patient:

Name: {name}
Age: {age}
Disease: {disease}
Last test: {test}
Last result: {result}

The patient is at CRITICAL risk. Persuade them to schedule a test immediately.
Mention specific health complications they could face.
Offer home sample collection as a convenience option.
End with a clear call-to-action: reply YES to schedule.
Keep the tone warm but urgent. Use emojis sparingly."""

    return generate_ai_response(prompt)


def _high_risk_template(name, age, disease, test, result):
    return (
        f"Hi {name} 👋\n\n"
        f"Your last {test} result was {result}, which indicates your {disease} may not be well controlled.\n\n"
        f"At age {age}, uncontrolled {disease} can increase the risk of complications such as "
        f"kidney damage, nerve problems, and heart disease.\n\n"
        f"A quick {test} test helps doctors detect problems early and adjust treatment if needed.\n\n"
        f"We can arrange a convenient home sample collection for you.\n\n"
        f"Reply YES to schedule your test this week."
    )


def _medium_risk_template(name, age, disease, test, result):
    return (
        f"Hi {name} 👋\n\n"
        f"Your previous {test} result was {result}. Regular monitoring helps keep your {disease} under control.\n\n"
        f"Since you are {age}, staying proactive with health checks is important.\n\n"
        f"We can arrange a home sample collection at your convenience.\n\n"
        f"Reply YES to book a slot."
    )


def _low_risk_template(name, disease, test):
    return (
        f"Hi {name} 👋\n\n"
        f"It's time for your routine {test} check to keep your {disease} monitored.\n\n"
        f"Regular testing helps prevent future complications.\n\n"
        f"Reply YES if you'd like us to arrange a home sample collection."
    )
