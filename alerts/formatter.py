from datetime import datetime, date


def format_alert(job: dict) -> str:
    title = job.get("title") or "Unknown Post"
    org = job.get("organization") or "N/A"
    vacancies = job.get("vacancies") or "N/A"
    eligibility = job.get("eligibility") or "N/A"
    last_date = job.get("last_date") or "N/A"
    location = job.get("location") or "N/A"
    salary = job.get("salary") or "N/A"
    apply_link = job.get("apply_link") or job.get("source_url") or ""
    category = (job.get("category_tag") or "").replace("_", " ").title()
    score = job.get("relevance_score", 0)

    # Urgency tag
    urgency = ""
    if last_date and last_date != "N/A":
        try:
            deadline = datetime.fromisoformat(last_date).date()
            days_left = (deadline - date.today()).days
            if days_left < 0:
                urgency = "⚫ EXPIRED\n"
            elif days_left <= 3:
                urgency = f"🔴 URGENT — only {days_left} days left!\n"
            elif days_left <= 7:
                urgency = f"🟠 {days_left} days left\n"
            elif days_left <= 15:
                urgency = f"🟡 {days_left} days left\n"
            else:
                urgency = f"🟢 {days_left} days left\n"
        except Exception:
            pass

    message = f"""
🏛 <b>{title}</b>
🏢 {org}
📂 {category}
👥 Vacancies: {vacancies}
🎓 Eligibility: {eligibility}
📍 Location: {location}
💰 Salary: {salary}
📅 Last Date: {last_date}
{urgency}
⭐ Match Score: {score}/100
🔗 {apply_link}
""".strip()
    return message