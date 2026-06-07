import asyncio
import json
from collections import defaultdict
from loguru import logger

from storage.cache import get_client
from agents.supervisor import process_raw_job
from streams.producer import push_alert

STREAM_RAW = "xenonpie:raw_jobs"
STREAM_ALERTS = "xenonpie:alerts"
GROUP_AGENTS = "agents_group"
GROUP_ALERTS = "alerts_group"
CONSUMER_NAME = "worker_1"
RAW_BATCH_SIZE = 50
ALERT_BATCH_SIZE = 50


async def _ensure_groups() -> None:
    r = await get_client()
    for stream, group in [
        (STREAM_RAW, GROUP_AGENTS),
        (STREAM_ALERTS, GROUP_ALERTS),
    ]:
        try:
            await r.xgroup_create(stream, group, id="0", mkstream=True)
            logger.info(f"Created group '{group}' on '{stream}'")
        except Exception:
            pass


async def _process_raw_message(msg_id: str, fields: dict, user_profiles: list[dict], r) -> None:
    try:
        raw = json.loads(fields["data"])
        results = await process_raw_job(raw, user_profiles)
        for job in results:
            await push_alert(job)
        await r.xack(STREAM_RAW, GROUP_AGENTS, msg_id)
        logger.debug(f"ACK {msg_id} -> {len(results)} alerts queued")
    except Exception as exc:
        logger.error(f"Failed processing raw msg {msg_id}: {exc}")


async def consume_raw_jobs(user_profiles: list[dict], batch: int = RAW_BATCH_SIZE) -> None:
    r = await get_client()
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

            tasks = []
            for _, entries in messages:
                for msg_id, fields in entries:
                    tasks.append(
                        asyncio.create_task(_process_raw_message(msg_id, fields, user_profiles, r))
                    )

            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

        except asyncio.CancelledError:
            logger.info("Consumer shutting down...")
            break
        except Exception as exc:
            logger.error(f"Consumer loop error: {exc}")
            await asyncio.sleep(3)


async def consume_raw_jobs_once(user_profiles: list[dict], batch: int = RAW_BATCH_SIZE) -> None:
    r = await get_client()
    await _ensure_groups()

    try:
        messages = await r.xreadgroup(
            groupname=GROUP_AGENTS,
            consumername=CONSUMER_NAME,
            streams={STREAM_RAW: ">"},
            count=batch,
            block=2000,
        )

        if not messages:
            return

        for _, entries in messages:
            tasks = []
            for msg_id, fields in entries:
                tasks.append(
                    asyncio.create_task(_process_raw_message(msg_id, fields, user_profiles, r))
                )
            if tasks:
                await asyncio.gather(*tasks, return_exceptions=True)

    except asyncio.CancelledError:
        raise
    except Exception as exc:
        logger.error(f"consume_raw_jobs_once error: {exc}")
        await asyncio.sleep(3)


async def consume_alerts() -> None:
    from alerts.formatter import format_alert
    from alerts.telegram import send_telegram_alert
    from storage.billing import can_receive_alert, increment_alert_count

    r = await get_client()
    await _ensure_groups()
    logger.info("Alerts consumer started...")

    while True:
        try:
            messages = await r.xreadgroup(
                groupname=GROUP_ALERTS,
                consumername=CONSUMER_NAME,
                streams={STREAM_ALERTS: ">"},
                count=ALERT_BATCH_SIZE,
                block=2000,
            )

            if not messages:
                await asyncio.sleep(1)
                continue

            user_jobs: dict[str, list[tuple[str, dict]]] = defaultdict(list)
            ack_ids: list[str] = []

            for _, entries in messages:
                for msg_id, fields in entries:
                    try:
                        job = json.loads(fields["data"])
                        chat_id = job.get("user_id")
                        if not chat_id:
                            ack_ids.append(msg_id)
                            continue

                        allowed, reason = await can_receive_alert(chat_id)
                        if not allowed:
                            logger.info(f"Alert blocked for {chat_id} — limit reached")
                            await send_telegram_alert(message=reason, chat_id=chat_id)
                            ack_ids.append(msg_id)
                            continue

                        user_jobs[chat_id].append((msg_id, job))
                    except Exception as exc:
                        logger.error(f"Failed parsing alert msg {msg_id}: {exc}")
                        ack_ids.append(msg_id)

            for chat_id, jobs in user_jobs.items():
                assembled = []
                current = []
                current_len = 0
                for _, job in jobs:
                    text = format_alert(job)
                    if current_len + len(text) + 2 > 3800:
                        assembled.append("\n\n".join(current))
                        current = [text]
                        current_len = len(text)
                    else:
                        current.append(text)
                        current_len += len(text) + 2
                if current:
                    assembled.append("\n\n".join(current))

                sent_count = 0
                for message in assembled:
                    sent = await send_telegram_alert(message=message, chat_id=chat_id)
                    if sent:
                        sent_count += 1
                if sent_count > 0:
                    await increment_alert_count(chat_id)
                ack_ids.extend([msg_id for msg_id, _ in jobs])

            if ack_ids:
                await r.xack(STREAM_ALERTS, GROUP_ALERTS, *ack_ids)
                logger.debug(f"Alert batch ACKed {len(ack_ids)} messages")

        except asyncio.CancelledError:
            logger.info("Alert consumer shutting down...")
            break
        except Exception as exc:
            logger.error(f"Alert consumer error: {exc}")
            await asyncio.sleep(3)
