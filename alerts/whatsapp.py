from twilio.rest import Client
from loguru import logger
from config.settings import settings


def send_whatsapp_alert(message: str, to_number: str) -> bool:
    if not settings.TWILIO_SID or not settings.TWILIO_AUTH:
        logger.warning("Twilio credentials not set, skipping WhatsApp")
        return False

    client = Client(settings.TWILIO_SID, settings.TWILIO_AUTH)

    try:
        msg = client.messages.create(
            from_=f"whatsapp:{settings.WHATSAPP_FROM}",
            to=f"whatsapp:{to_number}",
            body=message,
        )
        logger.info(f"WhatsApp sent to {to_number} → SID: {msg.sid}")
        return True

    except Exception as e:
        logger.error(f"WhatsApp send failed to {to_number}: {e}")
        return False


def send_bulk_whatsapp(message: str, numbers: list[str]) -> list[bool]:
    results = [send_whatsapp_alert(message, num) for num in numbers]
    success = sum(results)
    logger.info(f"Bulk WhatsApp: {success}/{len(numbers)} sent")
    return results