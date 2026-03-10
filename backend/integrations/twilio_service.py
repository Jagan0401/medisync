import os
import logging

from twilio.rest import Client

logger = logging.getLogger(__name__)

_client = None
_client_sid = None  # track which SID the cached client was built with


def _get_client():
    global _client, _client_sid
    sid = os.environ.get('TWILIO_ACCOUNT_SID', '')
    token = os.environ.get('TWILIO_AUTH_TOKEN', '')
    if not sid or not token:
        raise ValueError('TWILIO_ACCOUNT_SID and TWILIO_AUTH_TOKEN must be set in .env')
    # Re-create client if credentials changed (e.g. new account SID)
    if _client is None or _client_sid != sid:
        _client = Client(sid, token)
        _client_sid = sid
        logger.info('Twilio client (re)created for account %s...', sid[:10])
    return _client


def send_whatsapp_message(to_number, body):
    """Send a WhatsApp message via Twilio. Returns message SID."""
    client = _get_client()
    from_number = os.environ.get('TWILIO_WHATSAPP_FROM', 'whatsapp:+14155238886')
    to = to_number if to_number.startswith('whatsapp:') else f'whatsapp:{to_number}'
    try:
        msg = client.messages.create(body=body, from_=from_number, to=to)
    except Exception as e:
        err_str = str(e)
        if '63038' in err_str or 'daily messages limit' in err_str.lower():
            logger.error('DAILY MESSAGE LIMIT REACHED — cannot send to %s', to_number)
            print(f'\n!!! TWILIO DAILY LIMIT (50 msgs) REACHED — message to {to_number} dropped !!!')
            print('!!! Wait until midnight UTC for the limit to reset, or upgrade your Twilio account !!!\n')
        raise
    logger.info('WhatsApp sent to %s  sid=%s', to_number, msg.sid)
    return msg.sid
