import httpx
from loguru import logger
from typing import Optional

from config.settings import settings

BASE_URL = "https://api.x.com/2"


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

    headers = {
        "Authorization": f"Bearer {settings.X_BEARER_TOKEN}",
    }

    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            headers=headers,
            follow_redirects=True,
        ) as client:

            # Get user ID
            user_resp = await client.get(
                f"{BASE_URL}/users/by/username/{username}"
            )
            user_resp.raise_for_status()

            user_data = user_resp.json()

            if "data" not in user_data:
                logger.warning(f"No user found: {username}")
                return []

            user_id = user_data["data"]["id"]

            # Get tweets
            tweets_resp = await client.get(
                f"{BASE_URL}/users/{user_id}/tweets",
                params={
                    "max_results": min(max_results, 100),
                    "exclude": "replies,retweets",
                    "tweet.fields": "created_at,text",
                },
            )

            tweets_resp.raise_for_status()

            tweets_data = tweets_resp.json()

            tweets = []

            for tweet in tweets_data.get("data", []):
                tweets.append(
                    {
                        "id": tweet["id"],
                        "username": username,
                        "text": tweet["text"],
                        "created_at": tweet.get("created_at"),
                        "url": f"https://x.com/{username}/status/{tweet['id']}",
                    }
                )

            return tweets

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


async def scrape_x_post(
    tweet_id: str,
    timeout: int = 30,
) -> Optional[dict]:
    """
    Fetch a single tweet.
    """

    headers = {
        "Authorization": f"Bearer {settings.X_BEARER_TOKEN}",
    }

    try:
        async with httpx.AsyncClient(
            timeout=timeout,
            headers=headers,
        ) as client:

            response = await client.get(
                f"{BASE_URL}/tweets/{tweet_id}",
                params={
                    "tweet.fields": "created_at,text,public_metrics"
                },
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