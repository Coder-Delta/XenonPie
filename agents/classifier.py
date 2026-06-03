from loguru import logger


def classify_job(job: dict) -> dict:
    title = job.get("title") or ""
    org = job.get("organization") or ""
    eligibility = job.get("eligibility") or ""
    text = f"{title} {org} {eligibility}"

    job["category_tag"] = _classify_category(text)
    job["education_level"] = _classify_education(eligibility)
    job["state_tag"] = _extract_state(job.get("location") or "")

    logger.info(f"Classified: {title} → {job['category_tag']} | {job['education_level']} | {job['state_tag']}")
    return job


def _classify_category(text: str) -> str:
    text = text.lower()
    if any(k in text for k in ["railway", "rrb"]):
        return "railway"
    if any(k in text for k in ["bank", "sbi", "ibps", "rbi", "lic", "hfl"]):
        return "bank"
    if any(k in text for k in ["defence", "army", "navy", "airforce"]):
        return "defence"
    if any(k in text for k in ["police", "constable"]):
        return "police"
    if any(k in text for k in ["teacher", "professor", "lecturer", "tet", "jhtet"]):
        return "teaching"
    if any(k in text for k in ["psu", "ongc", "bhel", "pgcil", "ntpc", "bpcl", "sgpgi"]):
        return "psu"
    if any(k in text for k in ["upsc", "ssc", "central", "ministry"]):
        return "central_govt"
    if any(k in text for k in ["upsssc", "bpsc", "uppsc", "psc", "state", "district"]):
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