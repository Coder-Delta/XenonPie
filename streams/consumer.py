import redis.asyncio as aioredis
import json
import asyncio
from loguru import logger
from config.settings import settings
from agents.supervisor import process_raw_job

redis_client = None

STREAM_RAW = "xenonpie:raw_jobs"
STREAM_ALERTS = "xenonpie:alerts"
GROUP_AGENTS = "agents_group"
GROUP_ALERTS = "alerts_group"
CONSUMER_NAME = "worker_1"


async def get_redis():
    global redis_client
    if redis_client is None:
        redis_client = await aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
    return redis_client


async def _ensure_groups():
    r = await get_redis()
    for stream, group in [
        (STREAM_RAW, GROUP_AGENTS),
        (STREAM_ALERTS, GROUP_ALERTS),
    ]:
        try:
            await r.xgroup_create(stream, group, id="0", mkstream=True)
            logger.info(f"Created group '{group}' on '{stream}'")
        except Exception:
            pass  # group already exists


async def consume_raw_jobs(user_profiles: list[dict], batch: int = 10):
    r = await get_redis()
    await _ensure_groups()
    logger.info("Raw jobs consumer started...")

    while True:
        try:
            messages = await r.xreadgroup(
                groupname=GROUP_AGENTS,
                consumername=CONSUMER_NAME,
                streams={STREAM_RAW: ">"},
                count=batch,
                block=2000,
            )

            if not messages:
                await asyncio.sleep(1)
                continue

            for stream_name, entries in messages:
                for msg_id, fields in entries:
                    try:
                        raw = json.loads(fields["data"])
                        results = await process_raw_job(raw, user_profiles)

                        from streams.producer import push_alert
                        for job in results:
                            await push_alert(job)

                        await r.xack(STREAM_RAW, GROUP_AGENTS, msg_id)
                        logger.debug(f"ACK {msg_id} → {len(results)} alerts queued")

                    except Exception as e:
                        logger.error(f"Failed processing msg {msg_id}: {e}")

        except asyncio.CancelledError:
            logger.info("Consumer shutting down...")
            break
        except Exception as e:
            logger.error(f"Consumer loop error: {e}")
            await asyncio.sleep(3)


async def consume_alerts():
    from alerts.formatter import format_alert
    from alerts.telegram import send_telegram_alert

    r = await get_redis()
    await _ensure_groups()
    logger.info("Alerts consumer started...")

    while True:
        try:
            messages = await r.xreadgroup(
                groupname=GROUP_ALERTS,
                consumername=CONSUMER_NAME,
                streams={STREAM_ALERTS: ">"},
                count=5,
                block=2000,
            )

            if not messages:
                await asyncio.sleep(1)
                continue

            for stream_name, entries in messages:
                for msg_id, fields in entries:
                    try:
                        job = json.loads(fields["data"])
                        message = format_alert(job)
                        await send_telegram_alert(
                            message=message,
                            user_id=job.get("user_id")
                        )
                        await r.xack(STREAM_ALERTS, GROUP_ALERTS, msg_id)
                        logger.debug(f"Alert sent + ACK {msg_id}")

                    except Exception as e:
                        logger.error(f"Alert delivery failed {msg_id}: {e}")

        except asyncio.CancelledError:
            logger.info("Alert consumer shutting down...")
            break
        except Exception as e:
            logger.error(f"Alert consumer error: {e}")
            await asyncio.sleep(3)