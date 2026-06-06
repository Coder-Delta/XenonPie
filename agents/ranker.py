from datetime import datetime, date
from loguru import logger


def rank_job(job: dict, user_profile: dict) -> dict:
    score = 0

    preferred_cats = user_profile.get("categories", [])
    preferred_states = [
        s.lower().replace(" ", "_")
        for s in user_profile.get("states", ["all_india"])
    ]

    has_preferences = bool(preferred_cats) or (
        preferred_states != ["all_india"]
    )

    if not has_preferences:
        job["relevance_score"] = 0
        return job

    # Category
    if job.get("category_tag") in preferred_cats:
        score += 30

    # Education
    edu_order = ["10th", "12th", "diploma", "graduate", "postgraduate", "phd"]

    user_edu = user_profile.get("education_level", "graduate").lower()
    job_edu = job.get("education_level", "graduate").lower()

    user_idx = edu_order.index(user_edu) if user_edu in edu_order else 3
    job_idx = edu_order.index(job_edu) if job_edu in edu_order else 3

    if user_idx >= job_idx:
        score += 20

    # State
    job_state = job.get("state_tag", "all_india").lower().replace(" ", "_")

    if job_state == "all_india" or job_state in preferred_states:
        score += 20

    # Deadline
    last_date = job.get("last_date")

    if last_date:
        try:
            deadline = datetime.fromisoformat(last_date).date()
            days_left = (deadline - date.today()).days

            if 0 < days_left <= 3:
                score += 30
            elif days_left <= 7:
                score += 20
            elif days_left <= 15:
                score += 10
            elif days_left < 0:
                score -= 50
        except Exception:
            logger.exception("Invalid deadline format")

    job["relevance_score"] = score
    logger.info(f"Ranked: {job.get('title')} → score {score}")

    return job