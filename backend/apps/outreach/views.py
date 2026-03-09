import logging
from datetime import datetime

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from config.db import db
from integrations.llama_service import generate_ai_response
from integrations.twilio_service import send_whatsapp_message

logger = logging.getLogger(__name__)


# ── Translation helper ─────────────────────────────────────────────────
def _translate_to_english(text):
    prompt = (
        f"Translate the following message to English. "
        f"Return ONLY the translated English text.\n\nMessage:\n{text}"
    )
    try:
        return generate_ai_response(prompt).strip().split('\n')[0]
    except Exception:
        return text


# ── Intent classifier ──────────────────────────────────────────────────
def _classify_intent(message):
    prompt = (
        f"Classify the user's intent.\n\nUser message:\n{message}\n\n"
        f"Choose ONLY one label:\nagree\ndelay\nschedule\nunknown\n\n"
        f"Return ONLY the label."
    )
    try:
        return generate_ai_response(prompt).strip().lower()
    except Exception:
        return 'unknown'


# ── In-memory language state (per phone) ──
_user_language = {}


@csrf_exempt
def whatsapp_webhook(request):
    """Receive incoming WhatsApp messages from Twilio webhook."""
    if request.method != 'POST':
        return HttpResponse('Method not allowed', status=405)

    body = request.POST.get('Body', '').strip()
    phone = request.POST.get('From', '').replace('whatsapp:', '')

    if not phone:
        return HttpResponse('Missing sender', status=400)
    if not body:
        return HttpResponse('OK', status=200)

    lower_body = body.lower()

    # Smart translation for non-ASCII
    if lower_body in ('1', '2'):
        message = lower_body
    elif any(ord(c) > 128 for c in body):
        message = _translate_to_english(body).lower()
    else:
        message = lower_body

    logger.info('WhatsApp from %s: %s → %s', phone, body, message)

    # ── Find patient in MongoDB ──
    patient = db.patients.find_one({'phone': phone}, {'_id': 0})
    if not patient:
        send_whatsapp_message(phone, 'Sorry, we could not find your patient record. Please contact the clinic.')
        return HttpResponse('OK')

    name = patient.get('name', 'Patient')
    test = patient.get('last_test', 'test')
    result = patient.get('last_result', 'N/A')
    age = patient.get('age', '')
    disease = patient.get('disease', '')

    intent = _classify_intent(message)
    logger.info('Intent for %s: %s', phone, intent)

    # ── Language selection ──
    if phone not in _user_language:
        if message == '1':
            _user_language[phone] = 'english'
            reply = (
                f"Language set to English ✅\n\n"
                f"Hello {name} 👍\n\n"
                f"Your last {test} result was {result}, which is above the safe range.\n\n"
                f"Would you prefer:\n1️⃣ Home sample collection\n2️⃣ Visit the clinic"
            )
        elif message == '2':
            _user_language[phone] = 'tamil'
            reply = (
                f"மொழி தமிழ் என அமைக்கப்பட்டது ✅\n\n"
                f"வணக்கம் {name} 👍\n\n"
                f"உங்கள் கடைசி {test} மதிப்பு {result}.\n\n"
                f"தயவு செய்து தேர்வு செய்யவும்:\n"
                f"1️⃣ வீட்டிற்கு மாதிரி சேகரிப்பு\n2️⃣ மருத்துவமனைக்கு வருவது"
            )
        else:
            reply = (
                f"Hi {name}\nவணக்கம் {name}\n\n"
                f"Please choose your language\nமொழியை தேர்வு செய்யவும்\n\n"
                f"1️⃣ English\n2️⃣ தமிழ்"
            )
    else:
        lang = _user_language[phone]

        if intent == 'agree':
            reply = (
                f"Great {name} 👍\n\nLet's schedule your {test} test.\n\n"
                f"Would you prefer:\n1️⃣ Home sample collection\n2️⃣ Visit the clinic"
            ) if lang == 'english' else (
                f"சரி {name} 👍\n\nஉங்கள் {test} பரிசோதனைக்கு நேரம் அமைப்போம்.\n\n"
                f"1️⃣ வீட்டிற்கு மாதிரி சேகரிப்பு\n2️⃣ மருத்துவமனைக்கு வருவது"
            )

        elif intent == 'delay':
            reply = (
                f"I understand {name}.\n\n"
                f"However your last {test} result was {result}.\n"
                f"At age {age}, uncontrolled {disease} increases risk of:\n"
                f"• Heart disease\n• Kidney damage\n• Vision problems\n\n"
                f"Would you like home sample collection instead?"
            ) if lang == 'english' else (
                f"பரவாயில்லை {name}.\n\n"
                f"ஆனால் உங்கள் கடைசி {test} மதிப்பு {result}.\n\n"
                f"வீட்டிற்கு மாதிரி சேகரிப்பை ஏற்பாடு செய்யவா?"
            )

        elif message == '1':
            reply = (
                "Perfect 👍\n\nWe will arrange home sample collection.\n\n"
                "What time works best tomorrow?\nMorning / Afternoon / Evening"
            ) if lang == 'english' else (
                "சரி 👍\n\nவீட்டிற்கு மாதிரி சேகரிப்பு ஏற்பாடு செய்கிறோம்.\n\n"
                "காலை / மதியம் / மாலை"
            )
            db.bookings.insert_one({
                'patient': name, 'patient_id': patient.get('patient_id', ''),
                'test': test, 'type': 'Home Collection',
                'status': 'Pending Confirmation', 'technician': '',
                'created_at': datetime.utcnow().isoformat(),
            })

        elif message == '2':
            reply = (
                "Great 👍\n\nYou can visit the clinic.\n\n"
                "Would you prefer:\n• Tomorrow\n• This weekend"
            ) if lang == 'english' else (
                "சரி 👍\n\nமருத்துவமனைக்கு வரலாம்.\n\n• நாளை\n• இந்த வார இறுதியில்"
            )
            db.bookings.insert_one({
                'patient': name, 'patient_id': patient.get('patient_id', ''),
                'test': test, 'type': 'Clinic Visit',
                'status': 'Pending Confirmation', 'technician': '',
                'created_at': datetime.utcnow().isoformat(),
            })

        elif intent == 'schedule':
            if 'morning' in message:
                slot = 'tomorrow morning'
            elif 'afternoon' in message:
                slot = 'tomorrow afternoon'
            elif 'evening' in message:
                slot = 'tomorrow evening'
            else:
                slot = 'tomorrow'

            reply = (
                f"Perfect 👍\n\nYour {test} test has been scheduled for {slot}.\n\n"
                f"Our team will send you a reminder before the appointment."
            ) if lang == 'english' else (
                f"சரி 👍\n\nஉங்கள் {test} பரிசோதனை {slot} அன்று திட்டமிடப்பட்டுள்ளது.\n\n"
                f"நாங்கள் நினைவூட்டல் செய்தி அனுப்புவோம்."
            )
            db.bookings.update_one(
                {'patient_id': patient.get('patient_id'), 'status': 'Pending Confirmation'},
                {'$set': {'status': 'Scheduled', 'slot': slot}},
            )
            db.care_gaps.update_one(
                {'patient_id': patient.get('patient_id'), 'status': 'Open'},
                {'$set': {'status': 'Closed', 'closed_at': datetime.utcnow().isoformat()}},
            )

        else:
            prompt = (
                f"You are a healthcare assistant.\n"
                f"Patient: {name}, Age: {age}, Disease: {disease}, "
                f"Last test: {test}, Result: {result}\n"
                f"Patient message: {body}\n\n"
                f"Reply in {'English' if lang == 'english' else 'Tamil'}. "
                f"Encourage the patient to take the test. Keep response short."
            )
            reply = generate_ai_response(prompt)

    # Send reply
    try:
        send_whatsapp_message(phone, reply)
    except Exception as e:
        logger.error('Twilio send error: %s', e)

    # Log the conversation
    db.messages.insert_one({
        'patient': name,
        'patient_id': patient.get('patient_id', ''),
        'hospital': patient.get('hospital', ''),
        'channel': 'WhatsApp',
        'message': f'IN: {body[:100]} | OUT: {reply[:100]}',
        'status': 'Delivered',
        'sent_at': datetime.utcnow().isoformat(),
    })

    return HttpResponse('OK')
