import asyncio
import json
from datetime import date
from loguru import logger

from config.settings import settings
from storage.cache import get_client
from utils.performance import metrics
from utils.retry import retry

_GEMINI_LIMIT = 15
SEARCH_PROMPT = """
You are a government job information finder for India.
A job was found with this partial info:
Title: {title}
Organization: {organization}
Category: {category}

Search your knowledge and fill in ALL missing fields. Return ONLY valid JSON:
{{
  "title": "{title}",
  "organization": "{organization}",
  "vacancies": null,
  "eligibility": "<age/education requirements>",
  "last_date": "<ISO date or null>",
  "apply_link": "<official URL or null>",
  "location": "<state or All India>",
  "salary": "<pay scale>",
  "exam_date": "<exam date or null>",
  "selection_process": "<written/interview/physical>",
  "official_website": "<URL>"
}}

Return ONLY JSON, no explanation.
"""


async def _run_blocking(fn, *args, **kwargs):
    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(None, lambda: fn(*args, **kwargs))


def _clean_response(raw: str) -> dict | None:
    raw = raw.strip().replace("```json", "").replace("```", "").strip()
    if not raw:
        return None
    parsed = json.loads(raw)
    if isinstance(parsed, list):
        parsed = parsed[0] if parsed else None
    return parsed


async def _get_call_count() -> int:
    try:
        r = await get_client()
        today = date.today().isoformat()
        val = await r.get(f"gemini:calls:{today}")
        return int(val) if val else 0
    except Exception:
        return 0


async def _increment_call_count() -> int:
    try:
        r = await get_client()
        today = date.today().isoformat()
        key = f"gemini:calls:{today}"
        count = await r.incr(key)
        await r.expire(key, 86400)
        return count
    except Exception:
        return 0


@metrics.timed("enrich_gemini")
@retry(max_attempts=3, initial_delay=0.5, max_delay=5.0)
async def _enrich_gemini_prompt(prompt: str) -> dict | None:
    try:
        from google import genai
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        response = await _run_blocking(
            client.models.generate_content,
            model="gemini-2.5-flash",
            contents=prompt,
        )
        return _clean_response(response.text)
    except Exception as e:
        logger.error(f"Gemini enrichment error: {e}")
        return None


@metrics.timed("enrich_cohere")
@retry(max_attempts=3, initial_delay=0.5, max_delay=5.0)
async def _enrich_cohere_prompt(prompt: str) -> dict | None:
    try:
        import cohere
        client = cohere.Client(api_key=settings.COHERE_API_KEY)
        response = await _run_blocking(
            client.chat,
            model="command-r-plus-08-2024",
            message=prompt,
            temperature=0.1,
        )
        return _clean_response(response.text)
    except Exception as e:
        logger.error(f"Cohere enrichment error: {e}")
        return None


async def enrich_job_details(job: dict) -> dict:
    title = job.get("title") or ""
    org = job.get("organization") or ""
    category = job.get("category_tag") or ""

    missing = []
    if not job.get("vacancies"):
        missing.append("vacancies")
    if not job.get("eligibility") or job.get("eligibility") == "N/A":
        missing.append("eligibility")
    if not job.get("last_date"):
        missing.append("last_date")
    if not job.get("salary"):
        missing.append("salary")

    if not missing:
        logger.debug(f"No enrichment needed for {title}")
        return job

    count = await _get_call_count()
    if count >= _GEMINI_LIMIT:
        logger.debug(f"Gemini daily limit ({_GEMINI_LIMIT}) reached, trying Cohere fallback: {title}")
        return await _enrich_cohere(job, missing)

    prompt = SEARCH_PROMPT.format(title=title, organization=org, category=category)
    logger.info(f"Enriching {title} — missing: {missing}")
    count = await _increment_call_count()
    logger.debug(f"Gemini call {count}/{_GEMINI_LIMIT}")

    enriched = await _enrich_gemini_prompt(prompt)
    if not enriched:
        return await _enrich_cohere(job, missing)

    for field in missing:
        if enriched.get(field):
            job[field] = enriched[field]
            logger.debug(f"Enriched {field}: {enriched[field]}")

    for extra in ["exam_date", "selection_process", "official_website"]:
        if enriched.get(extra):
            job[extra] = enriched[extra]

    logger.info(f"Enrichment done for {title}")
    return job


async def _enrich_cohere(job: dict, missing: list) -> dict:
    title = job.get("title") or ""
    org = job.get("organization") or ""
    prompt = SEARCH_PROMPT.format(title=title, organization=org, category=job.get("category_tag") or "")

    enriched = await _enrich_cohere_prompt(prompt)
    if not enriched:
        return job

    for field in missing:
        if enriched.get(field):
            job[field] = enriched[field]

    for extra in ["exam_date", "selection_process", "official_website"]:
        if enriched.get(extra):
            job[extra] = enriched[extra]

    logger.info(f"Cohere enrichment done for {title}")
    return job
