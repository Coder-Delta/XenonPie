from datetime import date
from loguru import logger
from .extractor import extract_job_details
from .classifier import classify_job
from .dedup import is_duplicate
from .ranker import rank_job
from .search_agent import enrich_job_details
from alerts.bot_handler import register_job


async def process_raw_job(
    raw: dict,
    user_profiles: list[dict]
) -> list[dict]:
    text = (
        raw.get("text")
        or raw.get("summary")
        or raw.get("content")
        or ""
    )
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

    # Source metadata
    job["source_url"] = raw.get("url", "")
    job["source_feed"] = raw.get("source", "")
    job["source_type"] = raw.get("type", "web")

    # Step 2: Classify
    job = classify_job(job)

    # Step 2.5: Gemini enrichment
    job = await enrich_job_details(job)

    # Step 3: Skip expired jobs
    last_date = job.get("last_date")
    if last_date and last_date != "N/A":
        try:
            if date.fromisoformat(last_date) < date.today():
                logger.info(f"Skipping expired job: {job['title']} (last_date: {last_date})")
                return []
        except Exception:
            pass

    # Step 4: Dedup
    if is_duplicate(job):
        return []

    # Step 5: Rank for users
    results = []
    for profile in user_profiles:
        ranked = rank_job(job.copy(), profile)
        if ranked.get("relevance_score", 0) > 0:
            ranked["user_id"] = profile.get("user_id")
            results.append(ranked)
            register_job(ranked)  # feed into bot command store

    logger.info(f"Supervisor: {len(results)} matches for '{job.get('title')}'")
    return results