import json
from loguru import logger
from groq import Groq
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


async def extract_job_details(text: str) -> dict | None:
    try:
        prompt = EXTRACT_PROMPT.format(text=text[:4000])

        response = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=1000,
        )

        raw = response.choices[0].message.content.strip()
        raw = raw.replace("```json", "").replace("```", "").strip()
        data = json.loads(raw)
        logger.info(f"Extracted: {data.get('title')} — {data.get('organization')}")
        return data

    except json.JSONDecodeError as e:
        logger.error(f"JSON parse failed in extractor: {e}")
        return await _fallback_gemini(text)
    except Exception as e:
        logger.error(f"Extractor error: {e}")
        return None


async def _fallback_gemini(text: str) -> dict | None:
    try:
        import google.generativeai as genai
        genai.configure(api_key=settings.GEMINI_API_KEY)
        model = genai.GenerativeModel("gemini-1.5-flash")

        prompt = EXTRACT_PROMPT.format(text=text[:6000])
        response = model.generate_content(prompt)
        raw = response.text.strip().replace("```json", "").replace("```", "").strip()
        data = json.loads(raw)
        logger.info(f"Gemini fallback extracted: {data.get('title')}")
        return data

    except Exception as e:
        logger.error(f"Gemini fallback failed: {e}")
        return None