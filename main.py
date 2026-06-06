import asyncio
import yaml
from loguru import logger
from utils.logger import setup_logger
from streams.consumer import consume_raw_jobs_once, consume_alerts
from alerts.telegram import get_updates
from alerts.bot_handler import handle_command
from storage.db import init_db, get_pool
from scheduler import setup_scheduler, scrape_all

setup_logger(level="INFO")


def load_sources():
    with open("config/sources.yaml") as f:
        data = yaml.safe_load(f)
    return data["sources"]


async def load_user_profiles() -> list[dict]:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                "SELECT chat_id, categories, states, education_level FROM users WHERE subscribed = TRUE"
            )
            profiles = []
            for row in rows:
                profiles.append({
                    "user_id": row["chat_id"],
                    "categories": list(row["categories"] or []),
                    "states": list(row["states"] or ["all_india"]),
                    "education_level": row["education_level"] or "graduate",
                })
            if not profiles:
                profiles = [{
                    "user_id": "8939136566",
                    "categories": ["central_govt", "bank", "railway"],
                    "education_level": "graduate",
                    "states": ["all_india", "west_bengal"],
                }]
            logger.info(f"Loaded {len(profiles)} user profiles from DB")
            return profiles
    except Exception as e:
        logger.error(f"load_user_profiles error: {e}")
        return [{
            "user_id": "8939136566",
            "categories": ["central_govt", "bank", "railway"],
            "education_level": "graduate",
            "states": ["all_india", "west_bengal"],
        }]


async def bot_polling_loop():
    logger.info("Telegram bot polling started")
    offset = 0
    while True:
        try:
            updates = await get_updates(offset=offset)
            for update in updates:
                offset = update["update_id"] + 1
                message = update.get("message") or update.get("edited_message")
                if not message:
                    continue
                text = message.get("text", "")
                chat_id = str(message["chat"]["id"])
                if text.startswith("/"):
                    asyncio.create_task(handle_command(chat_id, text))
                    logger.info(f"Command '{text}' from {chat_id}")
        except Exception as e:
            logger.error(f"Bot polling error: {e}")
            await asyncio.sleep(5)


async def main():
    logger.info("XenonPie starting...")

    try:
        await init_db()
    except Exception as e:
        logger.warning(f"DB init skipped: {e}")

    sched = setup_scheduler()
    sched.start()
    logger.info("Scheduler started")

    asyncio.create_task(scrape_all())

    await asyncio.gather(
        _dynamic_consumer(),
        consume_alerts(),
        bot_polling_loop(),
    )


async def _dynamic_consumer():
    """Reload user profiles from DB every cycle."""
    while True:
        try:
            user_profiles = await load_user_profiles()
            await consume_raw_jobs_once(user_profiles)
        except Exception as e:
            logger.error(f"Dynamic consumer error: {e}")
            await asyncio.sleep(3)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down XenonPie")