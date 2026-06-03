import asyncio
from loguru import logger
from scrapers import scrape_url, parse_feed, has_changed
from streams.producer import push_raw_job
from streams.consumer import consume_raw_jobs, consume_alerts
import yaml

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

            except Exception as e:
                logger.error(f"Scraper error for {source['url']}: {e}")

        logger.info("Cycle done. Sleeping 30 min...")
        await asyncio.sleep(30 * 60)


async def main():
    logger.info("XenonPie starting...")
    await asyncio.gather(
        scraper_loop(),
        consume_raw_jobs(USER_PROFILES),
        consume_alerts(),
    )


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Shutting down XenonPie")