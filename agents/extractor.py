import asyncio
import hashlib
import json
from loguru import logger
from config.settings import settings
from utils.performance import metrics
from utils.retry import retry

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


@metrics.timed("extract_groq")
@retry(max_attempts=3, initial_delay=0.5, max_delay=4.0)
async def _extract_groq(text: str) -> dict | None:
    try:
        from groq import Groq
        client = Groq(api_key=settings.GROQ_API_KEY)
        prompt = EXTRACT_PROMPT.format(text=text[:1500])

        response = await _run_blocking(
            client.chat.completions.create,
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=800,
        )
        raw = response.choices[0].message.content
        parsed = _clean_response(raw)
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


@metrics.timed("extract_gemini")
@retry(max_attempts=3, initial_delay=0.5, max_delay=5.0)
async def _extract_gemini(text: str) -> dict | None:
    try:
        from google import genai
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        prompt = EXTRACT_PROMPT.format(text=text[:1500])

        response = await _run_blocking(
            client.models.generate_content,
            model="gemini-2.5-flash",
            contents=prompt,
        )
        parsed = _clean_response(response.text)
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


@metrics.timed("extract_cohere")
@retry(max_attempts=3, initial_delay=0.5, max_delay=5.0)
async def _extract_cohere(text: str) -> dict | None:
    try:
        import cohere
        client = cohere.Client(api_key=settings.COHERE_API_KEY)
        prompt = EXTRACT_PROMPT.format(text=text[:1500])

        response = await _run_blocking(
            client.chat,
            model="command-r-plus-08-2024",
            message=prompt,
            temperature=0.1,
        )
        parsed = _clean_response(response.text)
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


async def _fallback_gemini(text: str) -> dict | None:
    try:
        from google import genai
        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        prompt = EXTRACT_PROMPT.format(text=text[:1500])

        response = await _run_blocking(
            client.models.generate_content,
            model="gemini-2.5-flash",
            contents=prompt,
        )
        return _clean_response(response.text)
    except Exception as e:
        logger.error(f"Gemini fallback error: {e}")
        return None
