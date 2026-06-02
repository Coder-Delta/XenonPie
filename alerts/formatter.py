from datetime import datetime, date


def format_alert(job: dict) -> str:
    title = job.get("title", "Unknown Post")
    org = job.get("organization", "N/A")
    vacancies = job.get("vacancies", "N/A")
    eligibility = job.get("eligibility", "N/A")
    last_date = job.get("last_date", "N/A")
    location = job.get("location", "N/A")
    salary = job.get("salary", "N/A")
    apply_link = job.get("apply_link") or job.get("source_url", "")
    category = job.get("category_tag", "").replace("_", " ").title()
    score = job.get("relevance_score", 0)

    # Urgency tag
    urgency = ""
    if last_date and last_date != "N/A":
        try:
            deadline = datetime.fromisoformat(last_date).date()
            days_left = (deadline - date.today()).days
            if days_left <= 3:
                urgency = "🔴 URGENT — only {days_left} days left!\n"
            elif days_left <= 7:
                urgency = f"🟠 {days_left} days left\n"
            elif days_left <= 15:
                urgency = f"🟡 {days_left} days left\n"
        except Exception:
            pass

    message = f"""
🏛 *{title}*
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