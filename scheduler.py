import asyncio
from loguru import logger
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
from scrapers import scrape_url, parse_feed, has_changed
from scrapers.x_scraper import scrape_x_user, extract_hiring_posts
from streams.producer import push_raw_job
from storage.db import init_db, get_recent_jobs
from storage.cache import get_client
import yaml

scheduler = AsyncIOScheduler(timezone="Asia/Kolkata")


def load_sources():
    with open("config/sources.yaml") as f:
        data = yaml.safe_load(f)
    return data["sources"]


# ── scrape all sources ─────────────────────────────────────────────────────────

async def scrape_all():
    sources = load_sources()
    logger.info(f"Scrape cycle started — {len(sources)} sources")
    success = 0
    failed = 0

    for source in sources:
        try:
            if source["type"] == "web":
                result = await scrape_url(source["url"])
                if result and has_changed(source["url"], result["raw_html"]):
                    await push_raw_job(result)
                    success += 1

            elif source["type"] == "feed":
                entries = parse_feed(source["url"])
                for entry in entries:
                    if has_changed(entry["link"], entry["summary"]):
                        await push_raw_job(entry)
                        success += 1

            elif source["type"] == "x":
                posts = await scrape_x_user(source.get("username", ""))
                for post in extract_hiring_posts(posts):
                    if has_changed(post["url"], post["text"]):
                        post["source"] = source.get("name", "")
                        post["source_type"] = "x"
                        await push_raw_job(post)
                        success += 1

        except Exception as e:
            failed += 1
            logger.error(f"Scrape failed [{source.get('url') or source.get('username')}]: {e}")

    logger.info(f"Scrape cycle done — pushed: {success} | failed: {failed}")


# ── cleanup expired jobs from cache ───────────────────────────────────────────

async def cleanup_cache():
    logger.info("Cache cleanup started")
    try:
        r = await get_client()
        keys = await r.keys("seen:*")
        logger.info(f"Cache cleanup: {len(keys)} seen keys present")
    except Exception as e:
        logger.error(f"Cache cleanup error: {e}")


# ── daily digest ──────────────────────────────────────────────────────────────

async def send_daily_digest():
    from alerts.telegram import send_telegram_alert
    from alerts.formatter import format_alert

    logger.info("Daily digest started")

    try:
        jobs = await get_recent_jobs(limit=10)
        if not jobs:
            logger.info("No jobs for digest")
            return

        lines = ["📰 <b>XenonPie Daily Digest</b>\n"]
        for job in jobs[:5]:
            lines.append(format_alert(job))
            lines.append("─" * 25)

        message = "\n".join(lines)

        from alerts.bot_handler import get_subscribers
        subscribers = get_subscribers()

        sent = 0
        for chat_id in subscribers:
            await send_telegram_alert(message=message, chat_id=chat_id)
            sent += 1
            await asyncio.sleep(0.1)

        logger.info(f"Daily digest sent to {sent} subscribers")

    except Exception as e:
        logger.error(f"Daily digest error: {e}")


# ── health check ──────────────────────────────────────────────────────────────

async def health_check():
    try:
        r = await get_client()
        await r.ping()
        logger.debug("Health check: Redis OK")
    except Exception as e:
        logger.error(f"Health check failed: {e}")


# ── setup all jobs ─────────────────────────────────────────────────────────────

def setup_scheduler():
    # scrape every 30 minutes
    scheduler.add_job(
        scrape_all,
        trigger=IntervalTrigger(minutes=30),
        id="scrape_all",
        name="Scrape all sources",
        replace_existing=True,
        max_instances=1,
        misfire_grace_time=60,
    )

    # daily digest at 8 AM IST
    scheduler.add_job(
        send_daily_digest,
        trigger=CronTrigger(hour=8, minute=0, timezone="Asia/Kolkata"),
        id="daily_digest",
        name="Daily job digest",
        replace_existing=True,
        max_instances=1,
    )

    # cache cleanup every 6 hours
    scheduler.add_job(
        cleanup_cache,
        trigger=IntervalTrigger(hours=6),
        id="cleanup_cache",
        name="Cache cleanup",
        replace_existing=True,
        max_instances=1,
    )

    # health check every 5 minutes
    scheduler.add_job(
        health_check,
        trigger=IntervalTrigger(minutes=5),
        id="health_check",
        name="Health check",
        replace_existing=True,
        max_instances=1,
    )

    logger.info("Scheduler configured with 4 jobs")
    return scheduler
