import httpx
from bs4 import BeautifulSoup
from loguru import logger
from typing import Optional

from utils.http_client import get_http_client
from utils.performance import metrics
from utils.retry import retry


@metrics.timed("scrape_url")
@retry(max_attempts=3, initial_delay=0.5, max_delay=4.0, exceptions=(httpx.RequestError, httpx.HTTPStatusError))
async def scrape_url(url: str, timeout: int = 30) -> Optional[dict]:
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
    }
    try:
        client = await get_http_client()
        response = await client.get(url, headers=headers, timeout=timeout)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")
        return {
            "url": url,
            "title": soup.title.string.strip() if soup.title else "",
            "raw_html": response.text,
            "text": soup.get_text(separator=" ", strip=True),
            "status_code": response.status_code,
        }

    except httpx.HTTPStatusError as e:
        logger.error(f"HTTP error scraping {url}: {e}")
    except httpx.RequestError as e:
        logger.error(f"Request error scraping {url}: {e}")
    return None