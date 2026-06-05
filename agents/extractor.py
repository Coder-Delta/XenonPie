import json
from loguru import logger
from groq import Groq
from google import genai
from config.settings import settings

client = Groq(api_key=settings.GROQ_API_KEY)

EXTRACT_PROMPT = """
You are a government job notice parser.
Extract the following fields from the text below and return ONLY valid JSON.

Fields:
- title (job title)
- organization (department/ministry)
- vacancies (number, integer or null)
- eligibility (education/age requirements, string)
- last_date (application deadline, ISO format or null)
- apply_link (URL or null)
- location (state/city or "All India")
- category (central/state/psu/bank/railway/defence/other)
- salary (pay scale string or null)

Text:
{text}

Return ONLY JSON, no explanation.
"""


def _clean_json(raw: str) -> str:
    return raw.replace("```json", "").replace("```", "").strip()


def _is_rate_limit_error(error: Exception) -> bool:
    error_text = str(error).lower()
    return "rate_limit" in error_text or "429" in error_text


async def extract_job_details(text: str) -> dict | None:
    try:
        prompt = EXTRACT_PROMPT.format(text=text[:4000])

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=1000,
        )

        raw = _clean_json(response.choices[0].message.content.strip())

        # handle if model returns a list instead of dict
        parsed = json.loads(raw)
        if isinstance(parsed, list):
            data = parsed[0] if parsed else None
        else:
            data = parsed

        logger.info(
            f"Extracted: {data.get('title')} — {data.get('organization')}"
        )
        return data

    except json.JSONDecodeError as e:
        logger.error(f"JSON parse failed in extractor: {e}")
        return await _fallback_gemini(text)

    except Exception as e:
        if _is_rate_limit_error(e):
            logger.warning("Groq rate limit hit, trying Gemini fallback")
            return await _fallback_gemini(text)

        logger.error(f"Extractor error: {e}")
        return None


async def _fallback_gemini(text: str) -> dict | None:
    try:
        prompt = EXTRACT_PROMPT.format(text=text[:6000])

        gemini_client = genai.Client(api_key=settings.GEMINI_API_KEY)

        response = gemini_client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )

        raw = _clean_json(response.text.strip())
        data = json.loads(raw)

        logger.info(f"Gemini fallback extracted: {data.get('title')}")
        return data

    except json.JSONDecodeError as e:
        logger.error(f"Gemini fallback JSON parse failed: {e}")
        return None

    except Exception as e:
        logger.error(f"Gemini fallback error: {e}")
        return None