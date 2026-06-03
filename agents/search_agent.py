import json
import asyncio
import google.generativeai as genai
from loguru import logger
from config.settings import settings

genai.configure(api_key=settings.GEMINI_API_KEY)


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
  "vacancies": <number or null>,
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

    logger.info(f"Enriching {title} — missing: {missing}")

    try:
        model = genai.GenerativeModel("gemini-1.5-flash")
        prompt = SEARCH_PROMPT.format(
            title=title,
            organization=org,
            category=category
        )
        response = model.generate_content(prompt)
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
        logger.warning(f"Gemini enrichment JSON parse failed for {title}")
        return job
    except Exception as e:
        logger.error(f"Search agent failed for {title}: {e}")
        return job
