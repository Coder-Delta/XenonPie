from alerts.formatter import format_alert
from alerts import bot_handler


def test_format_alert_prefers_apply_link():
    message = format_alert(
        {
            "title": "Clerk Recruitment",
            "organization": "SBI",
            "category_tag": "bank",
            "vacancies": 100,
            "eligibility": "Graduate",
            "location": "All India",
            "salary": "N/A",
            "last_date": "2099-01-01",
            "apply_link": "https://example.com/apply",
            "source_url": "https://example.com/source",
            "relevance_score": 90,
        }
    )

    assert "Clerk Recruitment" in message
    assert "https://example.com/apply" in message
    assert "https://example.com/source" not in message


def test_filter_includes_all_india_jobs_for_state_query():
    bot_handler._recent_jobs.clear()
    bot_handler.register_job(
        {
            "title": "All India Clerk",
            "location": "All India",
            "last_date": "2099-01-01",
        }
    )

    results = bot_handler._filter(states=["west_bengal"])

    assert [job["title"] for job in results] == ["All India Clerk"]
