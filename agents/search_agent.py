import json
from datetime import date
from google import genai
from loguru import logger
from config.settings import settings

client = genai.Client(api_key=settings.GEMINI_API_KEY)
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


async def _get_call_count() -> int:
    try:
        import redis.asyncio as aioredis
        r = await aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        today = date.today().isoformat()
        val = await r.get(f"gemini:calls:{today}")
        await r.aclose()
        return int(val) if val else 0
    except Exception:
        return 0


async def _increment_call_count() -> int:
    try:
        import redis.asyncio as aioredis
        r = await aioredis.from_url(settings.REDIS_URL, decode_responses=True)
        today = date.today().isoformat()
        key = f"gemini:calls:{today}"
        count = await r.incr(key)
        await r.expire(key, 86400)
        await r.aclose()
        return count
    except Exception:
        return 0


async def enrich_job_details(job: dict) -> dict:
    title = job.get("title") or ""
    org = job.get("organization") or ""
    category = job.get("category_tag") or ""

    # check what's missing
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

    logger.info(f"Enriching {title} — missing: {missing}")

    try:
        prompt = SEARCH_PROMPT.format(
            title=title,
            organization=org,
            category=category,
        )

        count = await _increment_call_count()
        logger.debug(f"Gemini call {count}/{_GEMINI_LIMIT}")

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )

        raw = response.text.strip().replace("```json", "").replace("```", "").strip()
        enriched = json.loads(raw)

        # only fill missing fields, don't overwrite existing good data
        for field in missing:
            if enriched.get(field):
                job[field] = enriched[field]
                logger.debug(f"Enriched {field}: {enriched[field]}")

        # add extra fields if found
        for extra in ["exam_date", "selection_process", "official_website"]:
            if enriched.get(extra):
                job[extra] = enriched[extra]

        logger.info(f"Enrichment done for {title}")
        return job

    except json.JSONDecodeError:
        logger.warning(f"Gemini JSON parse failed for {title}")
        return await _enrich_cohere(job, missing)
    except Exception as e:
        logger.error(f"Search agent Gemini failed for {title}: {e}")
        return await _enrich_cohere(job, missing)

async def _enrich_cohere(job: dict, missing: list) -> dict:
    try:
        import cohere
        client = cohere.Client(api_key=settings.COHERE_API_KEY)

        title = job.get("title") or ""
        org = job.get("organization") or ""

        prompt = SEARCH_PROMPT.format(
            title=title,
            organization=org,
            category=job.get("category_tag") or "",
        )

        response = client.chat(
            model="command-r",
            message=prompt,
            temperature=0.1,
        )
        raw = response.text.strip().replace("```json", "").replace("```", "").strip()
        enriched = json.loads(raw)

        for field in missing:
            if enriched.get(field):
                job[field] = enriched[field]

        for extra in ["exam_date", "selection_process", "official_website"]:
            if enriched.get(extra):
                job[extra] = enriched[extra]

        logger.info(f"Cohere enrichment done for {title}")
        return job

    except Exception as e:
        logger.error(f"Cohere enrichment failed: {e}")
        return job
