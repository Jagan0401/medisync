"""
OPTIONAL: Enhanced WhatsApp Webhook using LangChain
====================================================
This is an alternative to the basic webhook in views.py.
Use this for more advanced conversation management.

To enable:
1. Install LangChain: pip install langchain langchain-community
2. Replace whatsapp_webhook import in urls.py
3. Or keep both and route premium patients here
"""

import logging
from datetime import datetime, timedelta

from django.http import HttpResponse
from django.views.decorators.csrf import csrf_exempt

from config.db import db
from integrations.twilio_service import send_whatsapp_message
from integrations.langchain_service import (
    create_conversation_manager,
    MultiLanguageProcessor,
)

logger = logging.getLogger(__name__)


@csrf_exempt
def whatsapp_webhook_enhanced(request):
    """
    Enhanced WhatsApp webhook using LangChain for:
    - Persistent conversation memory
    - Context-aware responses
    - Multi-language support
    - Intent detection with confidence
    """
    if request.method != 'POST':
        return HttpResponse('Method not allowed', status=405)

    body = request.POST.get('Body', '').strip()
    phone = request.POST.get('From', '').replace('whatsapp:', '')

    if not phone or not body:
        return HttpResponse('OK', status=200)

    logger.info(f'WhatsApp enhanced from {phone}: {body}')

    # ─────────────────────────────────────────────────────────────────
    # 1. FIND PATIENT & LOAD STATE
    # ─────────────────────────────────────────────────────────────────
    phone_regex = {'$regex': phone[-10:]}
    patient = db.patients.find_one(
        {'phone': phone_regex},
        {
            '_id': 0, 'patient_id': 1, 'name': 1, 'disease': 1,
            'preferred_language': 1, 'whatsapp_state': 1,
            'last_test': 1, 'last_result': 1, 'age': 1, 'hospital': 1,
            'risk': 1,
        },
        sort=[('_id', -1)],
    )

    if not patient:
        send_whatsapp_message(phone, 'Patient record not found. Contact clinic.')
        return HttpResponse('OK')

    patient_id = patient.get('patient_id', '')
    patient_name = patient.get('name', 'Patient')
    disease = patient.get('disease', '')
    whatsapp_state = patient.get('whatsapp_state', '')
    preferred_lang = patient.get('preferred_language', 'en')

    LANGUAGE_MENU = {
        '1': 'en', '2': 'ta', '3': 'hi', '4': 'te', '5': 'kn', '6': 'ml',
    }

    # ─────────────────────────────────────────────────────────────────
    # 2. INITIALIZE CONVERSATION MANAGER (WITH MEMORY)
    # ─────────────────────────────────────────────────────────────────
    conv_mgr = create_conversation_manager(patient_id, patient_name, disease)

    # ─────────────────────────────────────────────────────────────────
    # 3. LOG INCOMING MESSAGE
    # ─────────────────────────────────────────────────────────────────
    db.messages.insert_one({
        'patient': patient_name,
        'patient_id': patient_id,
        'channel': 'WhatsApp',
        'message': body,
        'language': preferred_lang,
        'status': 'Received',
        'direction': 'inbound',
        'from_number': phone,
        'sent_at': datetime.utcnow().isoformat(),
    })

    reply = ''

    # ─────────────────────────────────────────────────────────────────
    # 4A. LANGUAGE SELECTION (state: awaiting_language)
    # ─────────────────────────────────────────────────────────────────
    if whatsapp_state == 'awaiting_language' and body.strip() in LANGUAGE_MENU:
        chosen_code = LANGUAGE_MENU[body.strip()]
        chosen_name = MultiLanguageProcessor.get_language_name(chosen_code)

        # ✅ PERSIST to database
        db.patients.update_one(
            {'patient_id': patient_id},
            {'$set': {
                'preferred_language': chosen_code,
                'whatsapp_state': 'active',
            }}
        )

        test = patient.get('last_test', 'test')
        result = patient.get('last_result', 'N/A')

        if chosen_code == 'en':
            reply = (
                f"✅ Language set to {chosen_name}\n\n"
                f"Hello {patient_name} 👋\n\n"
                f"Last {test} result: {result}\n\n"
                f"Would you like to book an appointment?\n"
                f"Reply YES to continue."
            )
        else:
            reply = (
                f"✅ மொழி {chosen_name} என்று அமைக்கப்பட்டது\n\n"
                f"வணக்கம் {patient_name} 👋\n\n"
                f"கடைசி {test} முடிவு: {result}\n\n"
                f"நீங்கள் சந்திப்பை பதிவு செய்ய விரும்புகிறீர்களா?\n"
                f"தொடர, YES என்று பதிலளிக்கவும்."
            )

        db.activity_feed.insert_one({
            'scope': 'technician', 'icon': '🌐',
            'text': f'{patient_name} selected {chosen_name} language',
            'time': datetime.utcnow().strftime('%Y-%m-%d %H:%M'),
        })

    # ─────────────────────────────────────────────────────────────────
    # 4B. LANGUAGE SELECTION PROMPT (awaiting language + no selection)
    # ─────────────────────────────────────────────────────────────────
    elif whatsapp_state == 'awaiting_language':
        reply = (
            "Hi! Please choose your language:\n"
            "1️⃣ English\n"
            "2️⃣ தமிழ் (Tamil)\n"
            "3️⃣ हिंदी (Hindi)\n"
            "4️⃣ తెలుగు (Telugu)\n"
            "5️⃣ ಕನ್ನಡ (Kannada)\n"
            "6️⃣ മലയാളം (Malayalam)"
        )

    # ─────────────────────────────────────────────────────────────────
    # 4C. ACTIVE CONVERSATION (STATE: ACTIVE)
    # ─────────────────────────────────────────────────────────────────
    else:
        # Detect intent using conversation context
        intent_analysis = conv_mgr.analyze_patient_intent_with_context(
            body,
            preferred_language=preferred_lang
        )
        intent = intent_analysis.get('intent', 'query')
        confidence = intent_analysis.get('confidence', 0.5)

        logger.info(
            f'Intent analysis for {patient_name}: {intent} '
            f'(confidence: {confidence})'
        )

        # ─ BOOK APPOINTMENT ─
        if intent in ('book_appointment', 'confirm_yes'):
            test_name = patient.get('last_test', 'Routine Check')
            hospital = patient.get('hospital', '')
            doctor = patient.get('doctor', '')
            tomorrow = (datetime.utcnow() + timedelta(days=1)).strftime('%Y-%m-%d')

            booking = {
                'patient': patient_name,
                'patient_id': patient_id,
                'test': test_name,
                'date': tomorrow,
                'hospital': hospital,
                'doctor': doctor,
                'status': 'Scheduled',
                'source': 'WhatsApp',
                'phone': phone,
                'created_at': datetime.utcnow().isoformat(),
            }
            db.bookings.insert_one(booking)

            reply_en = f"✅ Appointment booked for {tomorrow}!\nTest: {test_name}\nWe'll send a reminder."
            reply_ta = f"✅ {tomorrow} அன்று சந்திப்பு பதிவு செய்யப்பட்டுள்ளது!\nபরীक்ஷை: {test_name}\nநாங்கள் நினைவூட்டல் அனுப்புவோம்."

            reply = reply_en if preferred_lang == 'en' else reply_ta

        # ─ CANCEL APPOINTMENT ─
        elif intent == 'cancel':
            result = db.bookings.find_one_and_update(
                {'patient': patient_name, 'status': 'Scheduled'},
                {'$set': {'status': 'Cancelled'}},
                sort=[('_id', -1)],
            )
            reply = "❌ Appointment cancelled." if result else "No appointment to cancel."

        # ─ GENERAL QUERY (USE CONTEXT-AWARE AI) ─
        else:
            reply = conv_mgr.generate_contextual_response(
                body,
                patient,
                preferred_language=preferred_lang
            )

        # Log conversation exchange
        conv_mgr.log_exchange(body, reply, preferred_lang)

    # ─────────────────────────────────────────────────────────────────
    # 5. SEND REPLY & LOG
    # ─────────────────────────────────────────────────────────────────
    if reply:
        try:
            send_whatsapp_message(phone, reply)
        except Exception as e:
            logger.error(f'Twilio send error: {e}')

        db.messages.insert_one({
            'patient': patient_name,
            'patient_id': patient_id,
            'channel': 'WhatsApp',
            'message': reply[:300],
            'language': preferred_lang,
            'status': 'Delivered',
            'direction': 'outbound',
            'sent_at': datetime.utcnow().isoformat(),
        })

    return HttpResponse('OK')
