from datetime import datetime, date
import html


def _safe(text) -> str:
    if not text or text == "N/A":
        return "N/A"
    return html.escape(str(text))


def format_alert(job: dict) -> str:
    title = _safe(job.get("title") or "Unknown Post")
    org = _safe(job.get("organization") or "N/A")
    vacancies = _safe(job.get("vacancies") or "N/A")
    eligibility = _safe(job.get("eligibility") or "N/A")
    last_date = job.get("last_date") or "N/A"
    location = _safe(job.get("location") or "N/A")
    salary = _safe(job.get("salary") or "N/A")
    apply_link = job.get("apply_link") or job.get("source_url") or ""
    category = _safe((job.get("category_tag") or "").replace("_", " ").title())
    score = job.get("relevance_score", 0)

    # urgency tag
    urgency = ""
    if last_date and last_date != "N/A":
        try:
            deadline = datetime.fromisoformat(str(last_date)).date()
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
📅 Last Date: {_safe(last_date)}
{urgency}
⭐ Match Score: {score}/100

🔗 {apply_link}
""".strip()

    return message