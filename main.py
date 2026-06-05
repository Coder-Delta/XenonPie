import asyncio
import yaml
from loguru import logger
from utils.logger import setup_logger
from streams.consumer import consume_raw_jobs, consume_alerts
from alerts.telegram import get_updates
from alerts.bot_handler import handle_command
from storage.db import init_db
from scheduler import setup_scheduler, scrape_all

setup_logger(level="INFO")


def load_sources():
    with open("config/sources.yaml") as f:
        data = yaml.safe_load(f)
    return data["sources"]


USER_PROFILES = [
    {
        "user_id": "8939136566",
        "categories": ["central_govt", "bank", "railway"],
        "education_level": "graduate",
        "states": ["all_india", "west_bengal"],
    },
]


# ── telegram bot polling ───────────────────────────────────────────────────────

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


# ── main ───────────────────────────────────────────────────────────────────────

async def main():
    logger.info("XenonPie starting...")

    # init DB tables
    try:
        await init_db()
    except Exception as e:
        logger.warning(f"DB init skipped (no postgres): {e}")

    # setup + start scheduler
    sched = setup_scheduler()
    sched.start()
    logger.info("Scheduler started")

    # run first scrape immediately
    asyncio.create_task(scrape_all())

    # run all loops concurrently
    await asyncio.gather(
        consume_raw_jobs(USER_PROFILES),
        consume_alerts(),
        bot_polling_loop(),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down XenonPie")