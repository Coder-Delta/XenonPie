import asyncio
import httpx
from loguru import logger

from config.settings import settings
from storage.cache import is_rate_limited
from utils.http_client import get_http_client
from utils.performance import metrics

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"


async def _wait_for_rate_limit(chat_id: str) -> None:
    limit = settings.TELEGRAM_RATE_LIMIT_PER_SECOND
    key = f"telegram_rate:{chat_id}"
    while await is_rate_limited(key, limit, 1):
        await asyncio.sleep(0.2)


@metrics.timed("telegram_send")
async def send_telegram_alert(message: str, user_id: str | None = None, chat_id: str | None = None) -> bool:
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN not set, skipping")
        return False

    target = chat_id or user_id
    if not target:
        logger.warning("No chat_id or user_id provided for Telegram")
        return False

    url = TELEGRAM_API.format(token=token, method="sendMessage")
    chunks = [message[i:i+4000] for i in range(0, len(message), 4000)]
    client = await get_http_client()

    try:
        await _wait_for_rate_limit(target)
        for chunk in chunks:
            payload = {
                "chat_id": target,
                "text": chunk,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            }
            response = await client.post(url, json=payload, timeout=15)
            response.raise_for_status()
        logger.info(f"Telegram alert sent to {target}")
        return True
    except httpx.HTTPStatusError as e:
        logger.error(f"Telegram HTTP error: {e.response.text}")
    except Exception as e:
        logger.error(f"Telegram send failed: {e}")
    return False


async def send_bulk_telegram(message: str, chat_ids: list[str]) -> list[bool]:
    tasks = [send_telegram_alert(message=message, chat_id=chat_id) for chat_id in chat_ids]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    normalized = [bool(r) for r in results if not isinstance(r, Exception)]
    success = sum(normalized)
    logger.info(f"Bulk Telegram: {success}/{len(chat_ids)} sent")
    return normalized


async def set_webhook(webhook_url: str):
    token = settings.TELEGRAM_BOT_TOKEN
    url = TELEGRAM_API.format(token=token, method="setWebhook")
    client = await get_http_client()
    response = await client.post(url, json={"url": webhook_url})
    data = response.json()
    if data.get("ok"):
        logger.info(f"Webhook set to {webhook_url}")
    else:
        logger.error(f"Webhook setup failed: {data}")
    return data


async def delete_webhook():
    token = settings.TELEGRAM_BOT_TOKEN
    url = TELEGRAM_API.format(token=token, method="deleteWebhook")
    client = await get_http_client()
    await client.post(url)
    logger.info("Webhook deleted (polling mode)")


async def get_updates(offset: int = 0) -> list[dict]:
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN not set, skipping getUpdates")
        return []

    url = TELEGRAM_API.format(token=token, method="getUpdates")
    try:
        client = await get_http_client()
        r = await client.get(url, params={"timeout": 30, "offset": offset}, timeout=35)
        r.raise_for_status()
        data = r.json()
        return data.get("result", [])
    except Exception as e:
        logger.error(f"getUpdates failed: {e}")
        return []
