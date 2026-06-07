import hashlib
from loguru import logger

from storage.cache import get_client

HASH_KEY = "page_hashes"


def compute_hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


async def has_changed(url: str, current_content: str) -> bool:
    r = await get_client()
    new_hash = compute_hash(current_content)
    old_hash = await r.hget(HASH_KEY, url)

    if old_hash is None:
        await r.hset(HASH_KEY, url, new_hash)
        logger.info(f"New URL tracked: {url}")
        return True

    if old_hash != new_hash:
        await r.hset(HASH_KEY, url, new_hash)
        logger.info(f"Change detected: {url}")
        return True

    logger.debug(f"No change: {url}")
    return False


async def reset_hash(url: str) -> None:
    r = await get_client()
    await r.hdel(HASH_KEY, url)
    logger.info(f"Hash reset for {url}")
