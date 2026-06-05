import asyncio
from loguru import logger
from scrapers import scrape_url, parse_feed, has_changed
from scrapers.x_scraper import scrape_x_user, extract_hiring_posts
from streams.producer import push_raw_job
from streams.consumer import consume_raw_jobs, consume_alerts
from alerts.telegram import get_updates
from alerts.bot_handler import handle_command
import yaml
from utils.logger import setup_logger


setup_logger(level="INFO")

def load_sources():
    with open("config/sources.yaml") as f:
        data = yaml.safe_load(f)
    return data["sources"]


SOURCES = load_sources()

USER_PROFILES = [
    {
        "user_id": "8939136566",
        "categories": ["central_govt", "bank", "railway"],
        "education_level": "graduate",
        "states": ["all_india", "west_bengal"],
    },
]


# ── scraper loop ───────────────────────────────────────────────────────────────

async def scraper_loop():
    logger.info("Scraper loop started")
    while True:
        for source in SOURCES:
            try:
                if source["type"] == "web":
                    result = await scrape_url(source["url"])
                    if result and has_changed(source["url"], result["raw_html"]):
                        await push_raw_job(result)
                elif source["type"] == "feed":
                    entries = parse_feed(source["url"])
                    for entry in entries:
                        if has_changed(entry["link"], entry["summary"]):
                            await push_raw_job(entry)
                elif source["type"] == "x":
                    posts = await scrape_x_user(source["username"])
                    for post in extract_hiring_posts(posts):
                        if has_changed(post["url"], post["text"]):
                            post["source"] = source["name"]
                            post["source_type"] = "x"
                            await push_raw_job(post)
                else:
                    logger.warning(f"Unknown source type: {source}")
            except Exception as e:
                logger.error(f"Scraper error for {source.get('url') or source.get('username')}: {e}")

        logger.info("Cycle done. Sleeping 30 min...")
        await asyncio.sleep(30 * 60)


# ── telegram bot polling loop ──────────────────────────────────────────────────

async def bot_polling_loop():
    """
    Long-polls Telegram for updates and routes commands to bot_handler.
    Runs concurrently with scraper + consumer loops.
    """
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
                    logger.info(f"Dispatched command '{text}' from {chat_id}")

        except Exception as e:
            logger.error(f"Bot polling error: {e}")
            await asyncio.sleep(5)  # back off on error


# ── main ───────────────────────────────────────────────────────────────────────

async def main():
    logger.info("XenonPie starting...")
    await asyncio.gather(
        scraper_loop(),
        consume_raw_jobs(USER_PROFILES),
        consume_alerts(),
        bot_polling_loop(),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down XenonPie")
