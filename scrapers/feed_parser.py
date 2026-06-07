import asyncio
import feedparser
from loguru import logger
from typing import List


async def parse_feed(feed_url: str) -> List[dict]:
    loop = asyncio.get_running_loop()
    try:
        feed = await loop.run_in_executor(None, feedparser.parse, feed_url)

        if getattr(feed, "bozo", False):
            logger.warning(f"Malformed feed at {feed_url}")

        entries = [
            {
                "title": entry.get("title", ""),
                "link": entry.get("link", ""),
                "summary": entry.get("summary", ""),
                "published": entry.get("published", ""),
                "source": feed_url,
            }
            for entry in getattr(feed, "entries", [])
        ]

        logger.info(f"Parsed {len(entries)} entries from {feed_url}")
        return entries

    except Exception as e:
        logger.error(f"Feed parse error for {feed_url}: {e}")
        return []