import logging
from datetime import datetime, timedelta

from django.http import HttpResponse, JsonResponse
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_POST

from config.db import db
from integrations.twilio_service import send_whatsapp_message

logger = logging.getLogger(__name__)


# ── Language constants ─────────────────────────────────────────────────
LANGUAGE_MENU = {
    '1': 'en', '2': 'ta', '3': 'hi', '4': 'te', '5': 'kn', '6': 'ml',
}
LANGUAGE_NAMES = {
    'en': 'English', 'ta': 'Tamil', 'hi': 'Hindi',
    'te': 'Telugu', 'kn': 'Kannada', 'ml': 'Malayalam',
}


def _main_menu_text(patient_name):
    """Return the main 3-option menu text."""
    return (
        f"Hi {patient_name} 👋\n\n"
        f"How can we help you today?\n\n"
        f"Please reply with a number:\n"
        f"1️⃣ Book Appointment\n"
        f"2️⃣ Remind Me Later\n"
        f"3️⃣ Choose Language"
    )


def _language_menu_text():
    """Return the language selection menu text."""
    return (
        "🌐 Please choose your language:\n\n"
        "1️⃣ English\n"
        "2️⃣ தமிழ் (Tamil)\n"
        "3️⃣ हिंदी (Hindi)\n"
        "4️⃣ తెలుగు (Telugu)\n"
        "5️⃣ ಕನ್ನಡ (Kannada)\n"
        "6️⃣ മലയാളം (Malayalam)"
    )


def _send_and_log(phone, reply, patient_name, patient_id, patient_lang):
    """Send a WhatsApp reply and log it to MongoDB."""
    try:
        send_whatsapp_message(phone, reply)
    except Exception as e:
        logger.error('Twilio send error: %s', e)

    db.messages.insert_one({
        'patient': patient_name,
        'patient_id': patient_id,
        'channel': 'WhatsApp',
        'message': reply[:300],
        'language': patient_lang,
        'status': 'Delivered',
        'direction': 'outbound',
        'sent_at': datetime.utcnow().isoformat(),
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
    if request.method != 'POST':
        return HttpResponse('Method not allowed', status=405)

    body = request.POST.get('Body', '').strip()
    phone = request.POST.get('From', '').replace('whatsapp:', '')

    if not phone:
        return HttpResponse('Missing sender', status=400)
    if not body:
        return HttpResponse('OK', status=200)

    logger.info('WhatsApp from %s: %s', phone, body)

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
        try:
            send_whatsapp_message(
                phone,
                'Sorry, we could not find your patient record. Please contact the clinic.',
            )
        except Exception as e:
            logger.error('Twilio send error: %s', e)
        return HttpResponse('OK')

    patient_id = patient.get('patient_id', '')
    patient_name = patient.get('name', 'Patient')
    whatsapp_state = patient.get('whatsapp_state', '')
    patient_lang = patient.get('preferred_language', 'en')

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

                reply = (
                    f"✅ Language set to {chosen_name}!\n\n"
                    + _main_menu_text(patient_name)
                )

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

            reply = (
                f"✅ Appointment Booked!\n\n"
                f"📅 Date: {appointment_date}\n"
                f"🏥 Test: {test}\n"
                f"📍 Hospital: {hospital or 'Your registered hospital'}\n"
                f"👨‍⚕️ Doctor: {doctor or 'Assigned doctor'}\n\n"
                f"We will send you a reminder before your appointment.\n\n"
                f"Reply with a number:\n"
                f"1️⃣ Book Another Appointment\n"
                f"2️⃣ Remind Me Later\n"
                f"3️⃣ Choose Language"
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

            reply = (
                f"⏰ Got it, {patient_name}!\n\n"
                f"We will remind you tomorrow ({tomorrow}).\n"
                f"Take care! 🙏\n\n"
                f"You will receive a message tomorrow with these options:\n"
                f"1️⃣ Book Appointment\n"
                f"2️⃣ Remind Me Later\n"
                f"3️⃣ Choose Language"
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
            reply = _main_menu_text(patient_name)

    except Exception as e:
        logger.exception('Error processing WhatsApp message from %s: %s', phone, e)
        reply = _main_menu_text(patient_name)

    # Always send a reply
    _send_and_log(phone, reply, patient_name, patient_id, patient_lang)

    return HttpResponse('OK')
