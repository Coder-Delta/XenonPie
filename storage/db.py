import asyncpg
import json
from datetime import datetime
from loguru import logger
from config.settings import settings

_pool = None


async def get_pool():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(
            dsn=settings.DATABASE_URL,
            min_size=2,
            max_size=10,
        )
        logger.info("Database pool created")
    return _pool


async def close_pool():
    global _pool
    if _pool:
        await _pool.close()
        _pool = None
        logger.info("Database pool closed")


async def init_db():
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                id SERIAL PRIMARY KEY,
                fingerprint TEXT UNIQUE NOT NULL,
                title TEXT,
                organization TEXT,
                category_tag TEXT,
                education_level TEXT,
                state_tag TEXT,
                vacancies INTEGER,
                eligibility TEXT,
                last_date DATE,
                exam_date DATE,
                salary TEXT,
                location TEXT,
                apply_link TEXT,
                source_url TEXT,
                source_feed TEXT,
                selection_process TEXT,
                official_website TEXT,
                raw JSONB,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );

            CREATE INDEX IF NOT EXISTS idx_jobs_category ON jobs(category_tag);
            CREATE INDEX IF NOT EXISTS idx_jobs_state ON jobs(state_tag);
            CREATE INDEX IF NOT EXISTS idx_jobs_last_date ON jobs(last_date);
            CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at);

            CREATE TABLE IF NOT EXISTS users (
                id SERIAL PRIMARY KEY,
                chat_id TEXT UNIQUE NOT NULL,
                name TEXT,
                subscribed BOOLEAN DEFAULT FALSE,
                categories TEXT[],
                states TEXT[],
                education_level TEXT DEFAULT 'graduate',
                created_at TIMESTAMPTZ DEFAULT NOW()
            );

            CREATE TABLE IF NOT EXISTS alerts_sent (
                id SERIAL PRIMARY KEY,
                chat_id TEXT NOT NULL,
                job_fingerprint TEXT NOT NULL,
                sent_at TIMESTAMPTZ DEFAULT NOW(),
                UNIQUE(chat_id, job_fingerprint)
            );
        """)
        logger.info("Database tables initialized")


async def save_job(job: dict) -> bool:
    pool = await get_pool()

    fingerprint = job.get("fingerprint") or _make_fingerprint(job)

    last_date = _parse_date(job.get("last_date"))
    exam_date = _parse_date(job.get("exam_date"))
    vacancies = _safe_int(job.get("vacancies"))

    try:
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO jobs (
                    fingerprint, title, organization, category_tag,
                    education_level, state_tag, vacancies, eligibility,
                    last_date, exam_date, salary, location, apply_link,
                    source_url, source_feed, selection_process,
                    official_website, raw
                ) VALUES (
                    $1, $2, $3, $4, $5, $6, $7, $8,
                    $9, $10, $11, $12, $13, $14, $15,
                    $16, $17, $18
                )
                ON CONFLICT (fingerprint) DO UPDATE SET
                    vacancies = EXCLUDED.vacancies,
                    last_date = EXCLUDED.last_date,
                    salary = EXCLUDED.salary,
                    updated_at = NOW()
            """,
                fingerprint,
                job.get("title"),
                job.get("organization"),
                job.get("category_tag"),
                job.get("education_level"),
                job.get("state_tag"),
                vacancies,
                job.get("eligibility"),
                last_date,
                exam_date,
                job.get("salary"),
                job.get("location"),
                job.get("apply_link") or job.get("source_url"),
                job.get("source_url"),
                job.get("source_feed"),
                job.get("selection_process"),
                job.get("official_website"),
                json.dumps(job),
            )
        logger.debug(f"Saved job: {job.get('title')}")
        return True

    except Exception as e:
        logger.error(f"DB save error for {job.get('title')}: {e}")
        return False


async def save_user(chat_id: str, name: str = None) -> bool:
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO users (chat_id, name, subscribed)
                VALUES ($1, $2, FALSE)
                ON CONFLICT (chat_id) DO UPDATE SET
                    name = EXCLUDED.name
            """, chat_id, name)
        return True
    except Exception as e:
        logger.error(f"DB save user error: {e}")
        return False


async def get_user(chat_id: str) -> dict | None:
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT * FROM users WHERE chat_id = $1", chat_id
            )
            return dict(row) if row else None
    except Exception as e:
        logger.error(f"DB get user error: {e}")
        return None


async def update_user_prefs(chat_id: str, prefs: dict) -> bool:
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            await conn.execute("""
                UPDATE users SET
                    categories = $2,
                    states = $3,
                    education_level = $4,
                    subscribed = $5
                WHERE chat_id = $1
            """,
                chat_id,
                prefs.get("categories", []),
                prefs.get("states", ["all_india"]),
                prefs.get("education_level", "graduate"),
                prefs.get("subscribed", True),
            )
        return True
    except Exception as e:
        logger.error(f"DB update user prefs error: {e}")
        return False


async def mark_alert_sent(chat_id: str, fingerprint: str) -> bool:
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO alerts_sent (chat_id, job_fingerprint)
                VALUES ($1, $2)
                ON CONFLICT DO NOTHING
            """, chat_id, fingerprint)
        return True
    except Exception as e:
        logger.error(f"DB mark alert sent error: {e}")
        return False


async def already_alerted(chat_id: str, fingerprint: str) -> bool:
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            row = await conn.fetchrow("""
                SELECT 1 FROM alerts_sent
                WHERE chat_id = $1 AND job_fingerprint = $2
            """, chat_id, fingerprint)
            return row is not None
    except Exception as e:
        logger.error(f"DB already alerted error: {e}")
        return False


async def get_recent_jobs(limit: int = 20, category: str = None) -> list:
    pool = await get_pool()
    try:
        async with pool.acquire() as conn:
            if category:
                rows = await conn.fetch("""
                    SELECT * FROM jobs
                    WHERE category_tag = $1
                    ORDER BY created_at DESC
                    LIMIT $2
                """, category, limit)
            else:
                rows = await conn.fetch("""
                    SELECT * FROM jobs
                    ORDER BY created_at DESC
                    LIMIT $1
                """, limit)
            return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"DB get recent jobs error: {e}")
        return []


def _make_fingerprint(job: dict) -> str:
    import hashlib
    title = (job.get("title") or "unknown").lower().strip()
    org = (job.get("organization") or "unknown").lower().strip()
    key = f"{title}|{org}"
    return hashlib.sha256(key.encode()).hexdigest()


def _parse_date(date_str):
    if not date_str or date_str == "N/A":
        return None
    from utils.helpers import parse_date
    dt = parse_date(str(date_str))
    return dt.date() if dt else None


def _safe_int(value):
    try:
        return int(str(value).replace(",", "").strip())
    except (ValueError, TypeError):
        return None