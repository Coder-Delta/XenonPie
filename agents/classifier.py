from loguru import logger
from groq import Groq
from config.settings import settings

client = Groq(api_key=settings.GROQ_API_KEY)

CATEGORIES = [
    "central_govt", "state_govt", "psu", "bank",
    "railway", "defence", "police", "teaching", "other"
]

EDUCATION_LEVELS = ["10th", "12th", "diploma", "graduate", "postgraduate", "phd"]


def classify_job(job: dict) -> dict:
    text = f"{job.get('title','')} {job.get('organization','')} {job.get('eligibility','')}"

    category = _classify_category(text)
    education = _classify_education(job.get("eligibility", ""))
    state = _extract_state(job.get("location", ""))

    job["category_tag"] = category
    job["education_level"] = education
    job["state_tag"] = state

    logger.info(f"Classified: {job.get('title')} → {category} | {education} | {state}")
    return job


def _classify_category(text: str) -> str:
    text = text.lower()
    if any(k in text for k in ["railway", "rrb", "rer"]):
        return "railway"
    if any(k in text for k in ["bank", "sbi", "ibps", "rbi"]):
        return "bank"
    if any(k in text for k in ["defence", "army", "navy", "airforce", "military"]):
        return "defence"
    if any(k in text for k in ["police", "constable", "ssp"]):
        return "police"
    if any(k in text for k in ["teacher", "professor", "lecturer", "school"]):
        return "teaching"
    if any(k in text for k in ["psu", "ongc", "bhel", "sail", "ntpc", "bpcl"]):
        return "psu"
    if any(k in text for k in ["upsc", "ssc", "central", "ministry", "union"]):
        return "central_govt"
    if any(k in text for k in ["state", "psc", "district", "municipality"]):
        return "state_govt"
    return "other"


def _classify_education(eligibility: str) -> str:
    text = eligibility.lower()
    if any(k in text for k in ["phd", "doctorate"]):
        return "phd"
    if any(k in text for k in ["postgraduate", "pg", "msc", "mba", "mca", "ma"]):
        return "postgraduate"
    if any(k in text for k in ["graduate", "degree", "bsc", "bca", "btech", "ba", "bcom"]):
        return "graduate"
    if any(k in text for k in ["diploma", "iti"]):
        return "diploma"
    if any(k in text for k in ["12th", "intermediate", "hsc", "plus two"]):
        return "12th"
    if any(k in text for k in ["10th", "matriculation", "sslc"]):
        return "10th"
    return "graduate"


def _extract_state(location: str) -> str:
    if not location or "all india" in location.lower():
        return "all_india"
    return location.strip().lower().replace(" ", "_")