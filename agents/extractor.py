import json
import asyncio
from loguru import logger
from config.settings import settings

EXTRACT_PROMPT = """
You are a government job notice parser for India.
Extract the following fields from the text below and return ONLY valid JSON.

Fields:
- title (job title, string or null)
- organization (department/ministry, string or null)
- vacancies (number of posts, integer or null)
- eligibility (education/age requirements, string or null)
- last_date (application deadline, ISO format YYYY-MM-DD or null)
- apply_link (URL or null)
- location (state/city or "All India", string or null)
- category (one of: central_govt/state_govt/psu/bank/railway/defence/police/teaching/other)
- salary (pay scale string or null)

Text:
{text}

Return ONLY valid JSON object, no explanation, no markdown.
"""


# ── LLM 1: Groq ───────────────────────────────────────────────────────────────

async def _extract_groq(text: str) -> dict | None:
    try:
        from groq import Groq
        client = Groq(api_key=settings.GROQ_API_KEY)
        prompt = EXTRACT_PROMPT.format(text=text[:1500])

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=800,
        )
        raw = response.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()

        parsed = json.loads(raw)
        if isinstance(parsed, list):
            parsed = parsed[0] if parsed else None
        if not parsed:
            return None

        logger.info(f"Extracted [Groq]: {parsed.get('title')} — {parsed.get('organization')}")
        return parsed

    except Exception as e:
        error_str = str(e)
        if "rate_limit" in error_str or "429" in error_str:
            logger.warning("Groq rate limit hit, trying Gemini fallback")
        elif "decommissioned" in error_str:
            logger.warning("Groq model decommissioned, trying Gemini")
        else:
            logger.error(f"Groq extractor error: {e}")
        return None


# ── LLM 2: Gemini ─────────────────────────────────────────────────────────────

async def _extract_gemini(text: str) -> dict | None:
    try:
        from google import genai
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        prompt = EXTRACT_PROMPT.format(text=text[:1500])

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        raw = response.text.strip().replace("```json", "").replace("```", "").strip()

        parsed = json.loads(raw)
        if isinstance(parsed, list):
            parsed = parsed[0] if parsed else None
        if not parsed:
            return None

        logger.info(f"Extracted [Gemini]: {parsed.get('title')} — {parsed.get('organization')}")
        return parsed

    except Exception as e:
        error_str = str(e)
        if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
            logger.warning("Gemini quota exhausted, trying Cohere fallback")
        elif "503" in error_str or "UNAVAILABLE" in error_str:
            logger.warning("Gemini unavailable, trying Cohere fallback")
        else:
            logger.error(f"Gemini extractor error: {e}")
        return None


# ── LLM 3: Cohere ─────────────────────────────────────────────────────────────

async def _extract_cohere(text: str) -> dict | None:
    try:
        import cohere
        client = cohere.Client(api_key=settings.COHERE_API_KEY)
        prompt = EXTRACT_PROMPT.format(text=text[:1500])

        response = client.chat(
            model="command-r",
            message=prompt,
            temperature=0.1,
        )
        raw = response.text.strip().replace("```json", "").replace("```", "").strip()

        parsed = json.loads(raw)
        if isinstance(parsed, list):
            parsed = parsed[0] if parsed else None
        if not parsed:
            return None

        logger.info(f"Extracted [Cohere]: {parsed.get('title')} — {parsed.get('organization')}")
        return parsed

    except Exception as e:
        error_str = str(e)
        if "429" in error_str or "rate" in error_str.lower():
            logger.warning("Cohere rate limit hit")
        else:
            logger.error(f"Cohere extractor error: {e}")
        return None


# ── Main extractor with cascade ───────────────────────────────────────────────

async def extract_job_details(text: str) -> dict | None:
    if not text or not text.strip():
        return None

    for name, extractor in [
        ("Groq", _extract_groq),
        ("Gemini", _extract_gemini),
        ("Cohere", _extract_cohere),
    ]:
        try:
            result = await extractor(text)
            if result and result.get("title"):
                return result
            elif result:
                logger.debug(f"{name} returned result but no title, trying next")
        except Exception as e:
            logger.error(f"{name} cascade error: {e}")

        await asyncio.sleep(0.5)

    logger.warning("All LLMs failed for extraction")
    return None


# ── Gemini fallback for search agent ──────────────────────────────────────────

async def _fallback_gemini(text: str) -> dict | None:
    try:
        from google import genai
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        prompt = EXTRACT_PROMPT.format(text=text[:1500])

        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        raw = response.text.strip().replace("```json", "").replace("```", "").strip()

        parsed = json.loads(raw)
        if isinstance(parsed, list):
            parsed = parsed[0] if parsed else None
        return parsed

    except Exception as e:
        logger.error(f"Gemini fallback error: {e}")
        return None
