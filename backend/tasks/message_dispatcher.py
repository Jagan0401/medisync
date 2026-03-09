"""
Message Dispatcher — Celery task that sends WhatsApp messages in batches
per risk tier, with rate limiting and result logging.
"""

import logging
from datetime import datetime

from celery import shared_task
from config.db import db
from integrations.twilio_service import send_whatsapp_message
from services.message_generator import generate_message

logger = logging.getLogger(__name__)


@shared_task(name='tasks.dispatch_messages_batch', bind=True, max_retries=2)
def dispatch_messages_batch(self, patients, risk_tier):
    """
    Send WhatsApp messages to a batch of patients of the same risk tier.
    Called by daily_monitoring after the pipeline finishes.
    """
    logger.info('Dispatching %d %s-risk messages', len(patients), risk_tier)
    now = datetime.utcnow()
    sent = 0
    failed = 0

    for patient in patients:
        phone = patient.get('phone', '')
        if not phone:
            continue

        try:
            # Generate personalised message based on risk tier
            message_body = generate_message(patient, risk_tier)

            # Send via Twilio WhatsApp
            sid = send_whatsapp_message(phone, message_body)

            # Log to MongoDB messages collection
            db.messages.insert_one({
                'patient': patient.get('name', patient.get('patient_id', '')),
                'patient_id': patient.get('patient_id', ''),
                'hospital': patient.get('hospital', ''),
                'channel': 'WhatsApp',
                'risk': risk_tier,
                'message': message_body[:300],
                'status': 'Delivered',
                'twilio_sid': sid,
                'sent_at': now.isoformat(),
            })

            # Log AI decision
            db.audit_logs.insert_one({
                'scope': 'superadmin',
                'user': 'SYSTEM',
                'action': f'WhatsApp sent to {patient.get("name", "")} ({risk_tier})',
                'hospital': patient.get('hospital', ''),
                'time': now.strftime('%Y-%m-%d %H:%M'),
            })

            sent += 1

        except Exception as exc:
            logger.error('Failed sending to %s: %s', phone, exc)
            db.messages.insert_one({
                'patient': patient.get('name', patient.get('patient_id', '')),
                'patient_id': patient.get('patient_id', ''),
                'hospital': patient.get('hospital', ''),
                'channel': 'WhatsApp',
                'risk': risk_tier,
                'message': '',
                'status': 'Failed',
                'error': str(exc)[:200],
                'sent_at': now.isoformat(),
            })
            failed += 1

    result = {'tier': risk_tier, 'sent': sent, 'failed': failed, 'total': len(patients)}
    logger.info('Batch complete: %s', result)
    return result


@shared_task(name='tasks.send_single_whatsapp')
def send_single_whatsapp(patient_id, custom_message=None):
    """
    Send a single WhatsApp message to a specific patient.
    Callable from the dashboard for manual outreach.
    """
    patient = db.patients.find_one({'patient_id': patient_id}, {'_id': 0})
    if not patient:
        return {'error': f'Patient {patient_id} not found'}

    phone = patient.get('phone', '')
    if not phone:
        return {'error': 'No phone number'}

    risk = patient.get('risk', 'Low')
    body = custom_message if custom_message else generate_message(patient, risk)

    try:
        sid = send_whatsapp_message(phone, body)
        db.messages.insert_one({
            'patient': patient.get('name', patient_id),
            'patient_id': patient_id,
            'hospital': patient.get('hospital', ''),
            'channel': 'WhatsApp',
            'risk': risk,
            'message': body[:300],
            'status': 'Delivered',
            'twilio_sid': sid,
            'sent_at': datetime.utcnow().isoformat(),
        })
        return {'status': 'ok', 'sid': sid}
    except Exception as exc:
        db.messages.insert_one({
            'patient': patient.get('name', patient_id),
            'patient_id': patient_id,
            'hospital': patient.get('hospital', ''),
            'channel': 'WhatsApp',
            'risk': risk,
            'message': body[:300],
            'status': 'Failed',
            'error': str(exc)[:200],
            'sent_at': datetime.utcnow().isoformat(),
        })
        return {'error': str(exc)}
