from loguru import logger
from .extractor import extract_job_details
from .classifier import classify_job
from .dedup import is_duplicate
from .ranker import rank_job


async def process_raw_job(raw: dict, user_profiles: list[dict]) -> list[dict]:
    text = raw.get("text") or raw.get("summary") or ""
    if not text.strip():
        logger.warning(f"Empty text for {raw.get('url', 'unknown')}")
        return []

    # Step 1: Extract
    job = await extract_job_details(text)
    if not job:
        logger.warning("Extraction returned None")
        return []

    # Skip if no title extracted
    if not job.get("title"):
        logger.debug(f"Skipping job with no title from {raw.get('url', 'unknown')}")
        return []

    job["source_url"] = raw.get("url", "")
    job["source_feed"] = raw.get("source", "")

    # Step 2: Classify
    job = classify_job(job)

    # Step 3: Dedup
    if is_duplicate(job):
        return []

    # Step 4: Rank per user
    results = []
    for profile in user_profiles:
        ranked = rank_job(job.copy(), profile)
        if ranked["relevance_score"] > 0:
            ranked["user_id"] = profile.get("user_id")
            results.append(ranked)

    logger.info(f"Supervisor: {len(results)} matches for '{job.get('title')}'")
    return results