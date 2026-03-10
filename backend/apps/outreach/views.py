import logging
import os
from datetime import datetime, timedelta

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt

from config.db import db
from integrations.twilio_service import send_whatsapp_message
from services.message_generator import translate_message

logger = logging.getLogger(__name__)


# ── Language constants ─────────────────────────────────────────────────
LANGUAGE_MENU = {
    '1': 'en', '2': 'ta', '3': 'hi', '4': 'te', '5': 'kn', '6': 'ml',
}
LANGUAGE_NAMES = {
    'en': 'English', 'ta': 'Tamil', 'hi': 'Hindi',
    'te': 'Telugu', 'kn': 'Kannada', 'ml': 'Malayalam',
}


def _translate(text, lang_code):
    """Translate text if patient language is not English."""
    if not lang_code or lang_code == 'en':
        return text
    try:
        return translate_message(text, lang_code)
    except Exception as e:
        logger.error('Translation failed for %s: %s', lang_code, e)
        return text


def _main_menu_text(patient_name, lang_code='en'):
    """Return the main 3-option menu text in the patient's language."""
    text = (
        f"Hi {patient_name} 👋\n\n"
        f"How can we help you today?\n\n"
        f"Please reply with a number:\n"
        f"1️⃣ Book Appointment\n"
        f"2️⃣ Remind Me Later\n"
        f"3️⃣ Choose Language"
    )
    return _translate(text, lang_code)


def _language_menu_text():
    """Return the language selection menu text (always multilingual)."""
    return (
        "🌐 Please choose your language / மொழியைத் தேர்ந்தெடுக்கவும் / भाषा चुनें:\n\n"
        "1️⃣ English\n"
        "2️⃣ தமிழ் (Tamil)\n"
        "3️⃣ हिंदी (Hindi)\n"
        "4️⃣ తెలుగు (Telugu)\n"
        "5️⃣ ಕನ್ನಡ (Kannada)\n"
        "6️⃣ മലയാളം (Malayalam)"
    )


def _twiml_empty():
    """Return an empty TwiML response so Twilio gets a valid 200 XML reply."""
    return HttpResponse(
        '<?xml version="1.0" encoding="UTF-8"?><Response></Response>',
        content_type='text/xml',
    )


def _send_and_log(phone, reply, patient_name, patient_id, patient_lang):
    """Send a WhatsApp reply and log it to MongoDB."""
    status = 'Delivered'
    error_msg = ''
    try:
        sid = send_whatsapp_message(phone, reply)
        logger.info('Reply sent to %s (sid=%s)', phone, sid)
        print(f'[SEND OK] Message sent to {phone} (sid={sid})')
    except Exception as e:
        status = 'Failed'
        error_msg = str(e)[:200]
        logger.error('TWILIO SEND FAILED to %s: %s', phone, e)
        print(f'\n*** TWILIO SEND FAILED to {phone} ***')
        print(f'*** Error: {e} ***\n')

    db.messages.insert_one({
        'patient': patient_name,
        'patient_id': patient_id,
        'channel': 'WhatsApp',
        'message': reply[:300],
        'language': patient_lang,
        'status': status,
        'error': error_msg,
        'direction': 'outbound',
        'sent_at': datetime.utcnow().isoformat(),
    })


def whatsapp_webhook_test(request):
    """Diagnostic endpoint to verify webhook connectivity and config."""
    from_number = os.environ.get('TWILIO_WHATSAPP_FROM', 'whatsapp:+14155238886')
    has_sid = bool(os.environ.get('TWILIO_ACCOUNT_SID'))
    has_token = bool(os.environ.get('TWILIO_AUTH_TOKEN'))
    try:
        patient_count = db.patients.estimated_document_count()
    except Exception:
        patient_count = 'error'
    return JsonResponse({
        'status': 'ok',
        'service': 'MediSynC WhatsApp Webhook',
        'twilio_from': from_number,
        'twilio_credentials': has_sid and has_token,
        'mongodb_patients': patient_count,
    })


@csrf_exempt
def whatsapp_webhook(request):
    """Receive incoming WhatsApp messages from Twilio webhook.

    Interactive menu flow:
      1️⃣ Book Appointment  → saves appointment to DB, replies with date
      2️⃣ Remind Me Later   → schedules a reminder for next day
      3️⃣ Choose Language   → shows language options

    States: '' (default/menu) | 'awaiting_language'
    """
    if request.method == 'GET':
        return JsonResponse({'status': 'ok', 'message': 'MediSynC WhatsApp webhook is alive'})

    if request.method != 'POST':
        return HttpResponse('Method not allowed', status=405)

    body = request.POST.get('Body', '').strip()
    phone = request.POST.get('From', '').replace('whatsapp:', '')

    logger.info('=== WEBHOOK HIT === Method=%s From=%s Body=%s', request.method, phone, body)
    # Also print to stdout so it always shows in the terminal
    print(f'[WEBHOOK] From={phone} Body={body}')

    if not phone:
        return _twiml_empty()
    if not body:
        return _twiml_empty()

    # ── Find patient in MongoDB ──
    phone_regex = {'$regex': phone[-10:]}
    projection = {
        '_id': 0, 'name': 1, 'patient_id': 1, 'disease': 1, 'phone': 1,
        'hospital': 1, 'doctor': 1, 'last_test': 1, 'last_result': 1,
        'age': 1, 'preferred_language': 1, 'whatsapp_state': 1,
    }

    patient = db.patients.find_one(
        {'phone': phone_regex, 'whatsapp_state': 'awaiting_language'},
        projection,
    )
    if not patient:
        patient = db.patients.find_one(
            {'phone': phone_regex},
            projection,
            sort=[('_id', -1)],
        )

    if not patient:
        logger.warning('No patient found for phone %s', phone)
        print(f'[WEBHOOK] NO PATIENT FOUND for {phone}')
        try:
            send_whatsapp_message(
                phone,
                'Sorry, we could not find your patient record. Please contact the clinic.',
            )
        except Exception as e:
            logger.error('Twilio send error (no patient): %s', e)
        return _twiml_empty()

    patient_id = patient.get('patient_id', '')
    patient_name = patient.get('name', 'Patient')
    whatsapp_state = patient.get('whatsapp_state', '')
    patient_lang = patient.get('preferred_language', 'en')

    logger.info('Patient found: %s (id=%s, state=%s, lang=%s)', patient_name, patient_id, whatsapp_state, patient_lang)

    # Log incoming message
    db.messages.insert_one({
        'patient': patient_name,
        'patient_id': patient_id,
        'channel': 'WhatsApp',
        'message': body,
        'language': patient_lang,
        'status': 'Received',
        'direction': 'inbound',
        'from_number': phone,
        'sent_at': datetime.utcnow().isoformat(),
    })

    choice = body.strip()
    reply = ''

    try:
        # ╔════════════════════════════════════════════════════════════╗
        # ║ STATE: awaiting_language — handle language selection       ║
        # ╚════════════════════════════════════════════════════════════╝
        if whatsapp_state == 'awaiting_language':
            if choice in LANGUAGE_MENU:
                chosen_code = LANGUAGE_MENU[choice]
                chosen_name = LANGUAGE_NAMES.get(chosen_code, 'English')

                db.patients.update_one(
                    {'patient_id': patient_id},
                    {'$set': {
                        'preferred_language': chosen_code,
                        'whatsapp_state': '',
                    }},
                )
                patient_lang = chosen_code

                reply = _translate(
                    f"\u2705 Language set to {chosen_name}!\n\n",
                    chosen_code,
                ) + _main_menu_text(patient_name, chosen_code)

                db.activity_feed.insert_one({
                    'scope': 'technician', 'icon': '🌐',
                    'text': f'{patient_name} selected {chosen_name} via WhatsApp',
                    'time': datetime.utcnow().strftime('%Y-%m-%d %H:%M'),
                })
            else:
                reply = _language_menu_text()

        # ╔════════════════════════════════════════════════════════════╗
        # ║ OPTION 1 — Book Appointment                               ║
        # ╚════════════════════════════════════════════════════════════╝
        elif choice == '1':
            appointment_date = (datetime.utcnow() + timedelta(days=1)).strftime('%Y-%m-%d')
            test = patient.get('last_test', 'Routine Checkup')
            hospital = patient.get('hospital', '')
            doctor = patient.get('doctor', '')

            # Save appointment to database
            db.appointments.insert_one({
                'patient_id': patient_id,
                'patient_name': patient_name,
                'phone': phone,
                'hospital': hospital,
                'doctor': doctor,
                'appointment_date': appointment_date,
                'test': test,
                'status': 'Scheduled',
                'source': 'WhatsApp',
                'created_at': datetime.utcnow().isoformat(),
            })

            reply = _translate(
                f"✅ Appointment Booked!\n\n"
                f"📅 Date: {appointment_date}\n"
                f"🏥 Test: {test}\n"
                f"📍 Hospital: {hospital or 'Your registered hospital'}\n"
                f"👨‍⚕️ Doctor: {doctor or 'Assigned doctor'}\n\n"
                f"We will send you a reminder before your appointment.\n\n"
                f"Reply with a number:\n"
                f"1️⃣ Book Another Appointment\n"
                f"2️⃣ Remind Me Later\n"
                f"3️⃣ Choose Language",
                patient_lang,
            )

            db.activity_feed.insert_one({
                'scope': 'technician', 'icon': '📅',
                'text': f'{patient_name} booked an appointment for {appointment_date} via WhatsApp',
                'time': datetime.utcnow().strftime('%Y-%m-%d %H:%M'),
            })

        # ╔════════════════════════════════════════════════════════════╗
        # ║ OPTION 2 — Remind Me Later                                ║
        # ╚════════════════════════════════════════════════════════════╝
        elif choice == '2':
            tomorrow = (datetime.utcnow() + timedelta(days=1)).strftime('%Y-%m-%d')

            # Save reminder to database
            db.reminders.insert_one({
                'patient_id': patient_id,
                'patient_name': patient_name,
                'phone': phone,
                'remind_date': tomorrow,
                'status': 'Pending',
                'created_at': datetime.utcnow().isoformat(),
            })

            # Also update patient record so daily task can pick it up
            db.patients.update_one(
                {'patient_id': patient_id},
                {'$set': {'remind_date': tomorrow}},
            )

            reply = _translate(
                f"⏰ Got it, {patient_name}!\n\n"
                f"We will remind you tomorrow ({tomorrow}).\n"
                f"Take care! 🙏\n\n"
                f"You will receive a message tomorrow with these options:\n"
                f"1️⃣ Book Appointment\n"
                f"2️⃣ Remind Me Later\n"
                f"3️⃣ Choose Language",
                patient_lang,
            )

            db.activity_feed.insert_one({
                'scope': 'technician', 'icon': '⏰',
                'text': f'{patient_name} chose "Remind Me Later" — reminder set for {tomorrow}',
                'time': datetime.utcnow().strftime('%Y-%m-%d %H:%M'),
            })

        # ╔════════════════════════════════════════════════════════════╗
        # ║ OPTION 3 — Choose Language                                ║
        # ╚════════════════════════════════════════════════════════════╝
        elif choice == '3':
            db.patients.update_one(
                {'patient_id': patient_id},
                {'$set': {'whatsapp_state': 'awaiting_language'}},
            )
            reply = _language_menu_text()

        # ╔════════════════════════════════════════════════════════════╗
        # ║ ANY OTHER MESSAGE — show the main menu                    ║
        # ╚════════════════════════════════════════════════════════════╝
        else:
            reply = _main_menu_text(patient_name, patient_lang)

    except Exception as e:
        logger.exception('Error processing WhatsApp message from %s: %s', phone, e)
        reply = _main_menu_text(patient_name, patient_lang)

    # Always send a reply
    logger.info('Sending reply to %s: %s', phone, reply[:100])
    print(f'[WEBHOOK] Replying to {phone}: {reply[:80]}')
    _send_and_log(phone, reply, patient_name, patient_id, patient_lang)

    return _twiml_empty()
