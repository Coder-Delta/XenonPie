import feedparser
from loguru import logger
from typing import List


def parse_feed(feed_url: str) -> List[dict]:
    try:
        feed = feedparser.parse(feed_url)

        if feed.bozo:
            logger.warning(f"Malformed feed at {feed_url}")

        entries = []
        for entry in feed.entries:
            entries.append({
                "title": entry.get("title", ""),
                "link": entry.get("link", ""),
                "summary": entry.get("summary", ""),
                "published": entry.get("published", ""),
                "source": feed_url,
            })

        logger.info(f"Parsed {len(entries)} entries from {feed_url}")
        return entries

    except Exception as e:
        logger.error(f"Feed parse error for {feed_url}: {e}")
        return []