import os
import logging

from twilio.rest import Client

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    global _client
    if _client is None:
        sid = os.environ.get('TWILIO_ACCOUNT_SID', '')
        token = os.environ.get('TWILIO_AUTH_TOKEN', '')
        if not sid or not token:
            raise ValueError('TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN must be set in .env')
        _client = Client(sid, token)
    return _client


def send_whatsapp_message(to_number, body):
    """Send a WhatsApp message via Twilio. Returns message SID."""
    client = _get_client()
    from_number = os.environ.get('TWILIO_WHATSAPP_FROM', 'whatsapp:+14155238886')
    to = to_number if to_number.startswith('whatsapp:') else f'whatsapp:{to_number}'
    msg = client.messages.create(body=body, from_=from_number, to=to)
    logger.info('WhatsApp sent to %s  sid=%s', to_number, msg.sid)
    return msg.sid
