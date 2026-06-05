import httpx
import asyncio
from loguru import logger
from config.settings import settings

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"

# ── low-level send ─────────────────────────────────────────────────────────────

async def send_telegram_alert(
    message: str,
    user_id: str | None = None,
    chat_id: str | None = None,
):
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN not set, skipping")
        return False

    target = chat_id or user_id
    if not target:
        logger.warning("No chat_id or user_id provided for Telegram")
        return False

    url = TELEGRAM_API.format(token=token, method="sendMessage")
    payload = {
        "chat_id": target,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    try:
        async with httpx.AsyncClient(timeout=15) as client:
            response = await client.post(url, json=payload)
            response.raise_for_status()
            logger.info(f"Telegram alert sent to {target}")
            return True
    except httpx.HTTPStatusError as e:
        logger.error(f"Telegram HTTP error: {e.response.text}")
    except Exception as e:
        logger.error(f"Telegram send failed: {e}")
    return False


async def send_bulk_telegram(message: str, chat_ids: list[str]):
    results = []
    for chat_id in chat_ids:
        result = await send_telegram_alert(message=message, chat_id=chat_id)
        results.append(result)
    success = sum(results)
    logger.info(f"Bulk Telegram: {success}/{len(chat_ids)} sent")
    return results


# ── set webhook ────────────────────────────────────────────────────────────────

async def set_webhook(webhook_url: str):
    token = settings.TELEGRAM_BOT_TOKEN
    url = TELEGRAM_API.format(token=token, method="setWebhook")
    async with httpx.AsyncClient() as client:
        r = await client.post(url, json={"url": webhook_url})
        data = r.json()
        if data.get("ok"):
            logger.info(f"Webhook set to {webhook_url}")
        else:
            logger.error(f"Webhook setup failed: {data}")
    return data


async def delete_webhook():
    token = settings.TELEGRAM_BOT_TOKEN
    url = TELEGRAM_API.format(token=token, method="deleteWebhook")
    async with httpx.AsyncClient() as client:
        r = await client.post(url)
    logger.info("Webhook deleted (polling mode)")


# ── get updates (polling) ──────────────────────────────────────────────────────

async def get_updates(offset: int = 0) -> list[dict]:
    token = settings.TELEGRAM_BOT_TOKEN
    if not token:
        logger.warning("TELEGRAM_BOT_TOKEN not set, skipping getUpdates")
        return []

    url = TELEGRAM_API.format(token=token, method="getUpdates")
    try:
        async with httpx.AsyncClient(timeout=35) as client:
            r = await client.get(url, params={"timeout": 30, "offset": offset})
            data = r.json()
            return data.get("result", [])
    except Exception as e:
        logger.error(f"getUpdates failed: {e}")
        return []
