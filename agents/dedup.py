import hashlib
from loguru import logger

from storage.cache import is_seen, mark_seen


def _job_fingerprint(job: dict) -> str:
    title = (job.get("title") or "unknown").lower().strip()
    org = (job.get("organization") or "unknown").lower().strip()
    last_date = job.get("last_date") or ""
    key = f"{title}|{org}|{last_date}"
    return hashlib.sha256(key.encode()).hexdigest()


async def is_duplicate(job: dict) -> bool:
    fingerprint = _job_fingerprint(job)
    if await is_seen(fingerprint):
        logger.debug(f"Duplicate skipped: {job.get('title')}")
        return True
    await mark_seen(fingerprint, ttl=604800)
    logger.info(f"New unique job: {job.get('title')}")
    return False
