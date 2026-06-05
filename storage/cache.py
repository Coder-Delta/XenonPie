import redis.asyncio as aioredis
import json
from loguru import logger
from config.settings import settings

_client = None


async def get_client():
    global _client
    if _client is None:
        _client = await aioredis.from_url(
            settings.REDIS_URL,
            encoding="utf-8",
            decode_responses=True,
        )
        logger.info("Redis cache client created")
    return _client


async def close_client():
    global _client
    if _client:
        await _client.aclose()
        _client = None
        logger.info("Redis cache client closed")


# ── generic get/set/delete ─────────────────────────────────────────────────────

async def set(key: str, value, ttl: int = None) -> bool:
    try:
        r = await get_client()
        data = json.dumps(value) if not isinstance(value, str) else value
        if ttl:
            await r.setex(key, ttl, data)
        else:
            await r.set(key, data)
        return True
    except Exception as e:
        logger.error(f"Cache set error [{key}]: {e}")
        return False


async def get(key: str):
    try:
        r = await get_client()
        data = await r.get(key)
        if data is None:
            return None
        try:
            return json.loads(data)
        except json.JSONDecodeError:
            return data
    except Exception as e:
        logger.error(f"Cache get error [{key}]: {e}")
        return None


async def delete(key: str) -> bool:
    try:
        r = await get_client()
        await r.delete(key)
        return True
    except Exception as e:
        logger.error(f"Cache delete error [{key}]: {e}")
        return False


async def exists(key: str) -> bool:
    try:
        r = await get_client()
        return await r.exists(key) > 0
    except Exception as e:
        logger.error(f"Cache exists error [{key}]: {e}")
        return False


# ── rate limiting ──────────────────────────────────────────────────────────────

async def is_rate_limited(key: str, limit: int, window: int) -> bool:
    try:
        r = await get_client()
        pipe = r.pipeline()
        await pipe.incr(key)
        await pipe.expire(key, window)
        results = await pipe.execute()
        count = results[0]
        return count > limit
    except Exception as e:
        logger.error(f"Rate limit check error [{key}]: {e}")
        return False


# ── job-specific helpers ───────────────────────────────────────────────────────

async def cache_job(fingerprint: str, job: dict, ttl: int = 86400) -> bool:
    return await set(f"job:{fingerprint}", job, ttl=ttl)


async def get_cached_job(fingerprint: str) -> dict | None:
    return await get(f"job:{fingerprint}")


async def cache_user_prefs(chat_id: str, prefs: dict, ttl: int = 3600) -> bool:
    return await set(f"user:{chat_id}:prefs", prefs, ttl=ttl)


async def get_user_prefs(chat_id: str) -> dict | None:
    return await get(f"user:{chat_id}:prefs")


async def increment_alert_count(chat_id: str) -> int:
    try:
        r = await get_client()
        today = __import__("datetime").date.today().isoformat()
        key = f"alerts:{chat_id}:{today}"
        count = await r.incr(key)
        await r.expire(key, 86400)
        return count
    except Exception as e:
        logger.error(f"Increment alert count error: {e}")
        return 0


async def get_alert_count(chat_id: str) -> int:
    try:
        today = __import__("datetime").date.today().isoformat()
        result = await get(f"alerts:{chat_id}:{today}")
        return int(result) if result else 0
    except Exception:
        return 0


# ── dedup helpers (fast Redis-based) ──────────────────────────────────────────

async def mark_seen(fingerprint: str, ttl: int = 604800) -> bool:
    try:
        r = await get_client()
        key = f"seen:{fingerprint}"
        already = await r.exists(key)
        if already:
            return False
        await r.setex(key, ttl, "1")
        return True
    except Exception as e:
        logger.error(f"Mark seen error: {e}")
        return True


async def is_seen(fingerprint: str) -> bool:
    return await exists(f"seen:{fingerprint}")