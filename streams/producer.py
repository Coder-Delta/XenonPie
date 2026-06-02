import redis.asyncio as aioredis
import json
from loguru import logger
from config.settings import settings

redis_client = None


async def get_redis():
    global redis_client
    if redis_client is None:
        redis_client = await aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True
        )
    return redis_client


async def push_raw_job(data: dict, stream: str = "xenonpie:raw_jobs"):
    r = await get_redis()
    payload = json.dumps(data)
    msg_id = await r.xadd(stream, {"data": payload})
    logger.info(f"Pushed to {stream} → id: {msg_id} | {data.get('url', data.get('source', ''))}")
    return msg_id


async def push_alert(data: dict, stream: str = "xenonpie:alerts"):
    r = await get_redis()
    payload = json.dumps(data)
    msg_id = await r.xadd(stream, {"data": payload})
    logger.info(f"Alert queued → id: {msg_id} | job: {data.get('title', '')}")
    return msg_id


async def close():
    global redis_client
    if redis_client:
        await redis_client.aclose()
        redis_client = None
        logger.info("Redis connection closed")