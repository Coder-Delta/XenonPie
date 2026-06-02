import httpx
from bs4 import BeautifulSoup
from loguru import logger
from typing import Optional


async def scrape_url(url: str, timeout: int = 30) -> Optional[dict]:
    headers = {
        "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"
    }
    try:
        async with httpx.AsyncClient(timeout=timeout, headers=headers, follow_redirects=True) as client:
            response = await client.get(url)
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