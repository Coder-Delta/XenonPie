import httpx
from loguru import logger
from typing import Optional

from config.settings import settings
from utils.http_client import get_http_client
from utils.performance import metrics
from utils.retry import retry

BASE_URL = "https://api.x.com/2"


@metrics.timed("scrape_x_user")
@retry(max_attempts=3, initial_delay=0.5, max_delay=4.0, exceptions=(httpx.RequestError, httpx.HTTPStatusError))
async def scrape_x_user(
    username: str,
    max_results: int = 20,
    timeout: int = 30,
) -> list[dict]:
    """
    Fetch recent posts from an X account.

    Returns:
    [
        {
            "id": "...",
            "username": "...",
            "text": "...",
            "created_at": "...",
            "url": "...",
        }
    ]
    """

    if not settings.X_BEARER_TOKEN:
        logger.warning("X_BEARER_TOKEN not set, skipping X user scrape")
        return []

    headers = {
        "Authorization": f"Bearer {settings.X_BEARER_TOKEN}",
    }

    try:
        client = await get_http_client()

        user_resp = await client.get(
            f"{BASE_URL}/users/by/username/{username}",
            headers=headers,
            timeout=timeout,
        )
        user_resp.raise_for_status()

        user_data = user_resp.json()

        if "data" not in user_data:
            logger.warning(f"No user found: {username}")
            return []

        user_id = user_data["data"]["id"]

        tweets_resp = await client.get(
            f"{BASE_URL}/users/{user_id}/tweets",
            headers=headers,
            params={
                "max_results": min(max_results, 100),
                "exclude": "replies,retweets",
                "tweet.fields": "created_at,text",
            },
            timeout=timeout,
        )
        tweets_resp.raise_for_status()

        tweets_data = tweets_resp.json()
        return [
            {
                "id": tweet["id"],
                "username": username,
                "text": tweet["text"],
                "created_at": tweet.get("created_at"),
                "url": f"https://x.com/{username}/status/{tweet['id']}",
            }
            for tweet in tweets_data.get("data", [])
        ]

    except httpx.HTTPStatusError as e:
        logger.error(
            f"HTTP error fetching @{username}: "
            f"{e.response.status_code}"
        )

    except httpx.RequestError as e:
        logger.error(f"Request error fetching @{username}: {e}")

    except Exception as e:
        logger.exception(f"Unexpected error fetching @{username}: {e}")

    return []


@metrics.timed("scrape_x_post")
@retry(max_attempts=3, initial_delay=0.5, max_delay=4.0, exceptions=(httpx.RequestError, httpx.HTTPStatusError))
async def scrape_x_post(
    tweet_id: str,
    timeout: int = 30,
) -> Optional[dict]:
    """
    Fetch a single tweet.
    """

    if not settings.X_BEARER_TOKEN:
        logger.warning("X_BEARER_TOKEN not set, skipping X post scrape")
        return None

    headers = {
        "Authorization": f"Bearer {settings.X_BEARER_TOKEN}",
    }

    try:
        client = await get_http_client()

        response = await client.get(
            f"{BASE_URL}/tweets/{tweet_id}",
            headers=headers,
            params={
                "tweet.fields": "created_at,text,public_metrics"
            },
            timeout=timeout,
        )

        response.raise_for_status()

        data = response.json()["data"]

        return {
            "id": data["id"],
            "text": data["text"],
            "created_at": data.get("created_at"),
            "metrics": data.get("public_metrics", {}),
            "url": f"https://x.com/i/web/status/{data['id']}",
            "raw": data,
        }

    except httpx.HTTPStatusError as e:
        logger.error(
            f"HTTP error fetching tweet {tweet_id}: "
            f"{e.response.status_code}"
        )

    except httpx.RequestError as e:
        logger.error(f"Request error fetching tweet {tweet_id}: {e}")

    return None


HIRING_KEYWORDS = {
    "hiring",
    "we are hiring",
    "job opening",
    "career",
    "vacancy",
    "apply now",
    "internship",
    "sde",
    "software engineer",
    "backend engineer",
    "frontend engineer",
    "data engineer",
    "developer",
}


def extract_hiring_posts(posts: list[dict]) -> list[dict]:
    """
    Keep only hiring-related posts.
    """

    filtered = []

    for post in posts:
        text = post.get("text", "").lower()

        if any(keyword in text for keyword in HIRING_KEYWORDS):
            filtered.append(post)

    return filtered
