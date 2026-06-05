import asyncio
from datetime import date, timedelta
from types import SimpleNamespace

from agents.classifier import classify_job
from agents.ranker import rank_job
from agents import extractor


def test_classify_job_sets_category_education_and_state():
    job = {
        "title": "SBI Clerk Recruitment",
        "organization": "State Bank of India",
        "eligibility": "Graduate degree required",
        "location": "West Bengal",
    }

    result = classify_job(job)

    assert result["category_tag"] == "bank"
    assert result["education_level"] == "graduate"
    assert result["state_tag"] == "west_bengal"


def test_rank_job_scores_matching_profile():
    deadline = (date.today() + timedelta(days=5)).isoformat()
    job = {
        "title": "Bank Clerk",
        "category_tag": "bank",
        "education_level": "graduate",
        "state_tag": "all_india",
        "last_date": deadline,
    }
    profile = {
        "categories": ["bank"],
        "education_level": "graduate",
        "states": ["west_bengal"],
    }

    result = rank_job(job, profile)

    assert result["relevance_score"] == 90


def test_extract_job_details_uses_gemini_fallback_on_groq_rate_limit(monkeypatch):
    def raise_rate_limit(*args, **kwargs):
        raise RuntimeError("429 rate_limit_exceeded")

    class FakeGeminiModels:
        def generate_content(self, **kwargs):
            return SimpleNamespace(
                text='{"title":"Clerk","organization":"SBI","last_date":null}'
            )

    class FakeGeminiClient:
        def __init__(self, api_key):
            self.models = FakeGeminiModels()

    monkeypatch.setattr(extractor.client.chat.completions, "create", raise_rate_limit)
    monkeypatch.setattr(extractor.genai, "Client", FakeGeminiClient)

    result = asyncio.run(extractor.extract_job_details("SBI clerk notice"))

    assert result["title"] == "Clerk"
    assert result["organization"] == "SBI"
