import json
from loguru import logger

from storage.cache import get_client
from storage.cache import close_client

async def push_raw_job(data: dict, stream: str = "xenonpie:raw_jobs"):
    r = await get_client()
    payload = json.dumps(data)
    msg_id = await r.xadd(stream, {"data": payload})
    logger.info(f"Pushed to {stream} → id: {msg_id} | {data.get('url', data.get('source', ''))}")
    return msg_id


async def push_alert(data: dict, stream: str = "xenonpie:alerts"):
    r = await get_client()
    payload = json.dumps(data)
    msg_id = await r.xadd(stream, {"data": payload})
    logger.info(f"Alert queued → id: {msg_id} | job: {data.get('title', '')}")
    return msg_id


async def close() -> None:
    """Close shared Redis resources used by stream producers."""
    await close_client()
