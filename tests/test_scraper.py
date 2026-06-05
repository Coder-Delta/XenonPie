import asyncio
from types import SimpleNamespace
import yaml

from scrapers import feed_parser, web_scraper
from scrapers.x_scraper import extract_hiring_posts


class FakeResponse:
    status_code = 200
    text = "<html><head><title>Jobs</title></head><body>Apply now</body></html>"

    def raise_for_status(self):
        return None


class FakeAsyncClient:
    def __init__(self, *args, **kwargs):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    async def get(self, url):
        return FakeResponse()


def test_scrape_url_returns_title_text_and_status(monkeypatch):
    monkeypatch.setattr(web_scraper.httpx, "AsyncClient", FakeAsyncClient)

    result = asyncio.run(web_scraper.scrape_url("https://example.com/jobs"))

    assert result["url"] == "https://example.com/jobs"
    assert result["title"] == "Jobs"
    assert result["text"] == "Jobs Apply now"
    assert result["status_code"] == 200


def test_parse_feed_maps_entries(monkeypatch):
    feed = SimpleNamespace(
        bozo=False,
        entries=[
            {
                "title": "New Job",
                "link": "https://example.com/job",
                "summary": "Summary",
                "published": "Today",
            }
        ],
    )
    monkeypatch.setattr(feed_parser.feedparser, "parse", lambda url: feed)

    entries = feed_parser.parse_feed("https://example.com/feed")

    assert entries == [
        {
            "title": "New Job",
            "link": "https://example.com/job",
            "summary": "Summary",
            "published": "Today",
            "source": "https://example.com/feed",
        }
    ]


def test_extract_hiring_posts_filters_relevant_x_posts():
    posts = [
        {"text": "We are hiring backend engineers", "url": "https://x.com/a"},
        {"text": "Product launch today", "url": "https://x.com/b"},
    ]

    assert extract_hiring_posts(posts) == [posts[0]]


def test_sources_have_required_fields_for_their_type():
    sources = yaml.safe_load(open("config/sources.yaml"))["sources"]

    for source in sources:
        if source["type"] in {"web", "feed"}:
            assert source.get("url"), source
        elif source["type"] == "x":
            assert source.get("username"), source
        else:
            raise AssertionError(f"Unknown source type: {source}")
