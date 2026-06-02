import resend
from loguru import logger
from config.settings import settings


def send_email_alert(job: dict, to_email: str) -> bool:
    if not hasattr(settings, "RESEND_API_KEY") or not settings.RESEND_API_KEY:
        logger.warning("RESEND_API_KEY not set, skipping email")
        return False

    resend.api_key = settings.RESEND_API_KEY

    title = job.get("title", "New Govt Job Alert")
    org = job.get("organization", "")
    last_date = job.get("last_date", "N/A")
    apply_link = job.get("apply_link") or job.get("source_url", "#")

    html_body = f"""
    <h2>{title}</h2>
    <p><b>Organization:</b> {org}</p>
    <p><b>Last Date:</b> {last_date}</p>
    <p><b>Eligibility:</b> {job.get('eligibility', 'N/A')}</p>
    <p><b>Vacancies:</b> {job.get('vacancies', 'N/A')}</p>
    <p><b>Salary:</b> {job.get('salary', 'N/A')}</p>
    <p><b>Location:</b> {job.get('location', 'N/A')}</p>
    <br/>
    <a href="{apply_link}" style="
        background:#4F46E5;
        color:white;
        padding:10px 20px;
        border-radius:6px;
        text-decoration:none;
    ">Apply Now</a>
    """

    try:
        response = resend.Emails.send({
            "from": "XenonPie <alerts@yourdomain.com>",
            "to": to_email,
            "subject": f"New Job Alert: {title} — {org}",
            "html": html_body,
        })
        logger.info(f"Email sent to {to_email} → id: {response['id']}")
        return True

    except Exception as e:
        logger.error(f"Email send failed to {to_email}: {e}")
        return False