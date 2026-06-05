import asyncpg
import json
from loguru import logger
from config.settings import settings

_pool = None


async def get_pool():
    global _pool
    if _pool is None:
        _pool = await asyncpg.create_pool(dsn=settings.DATABASE_URL)
    return _pool


async def init_vector_store():
    pool = await get_pool()
    async with pool.acquire() as conn:
        await conn.execute("CREATE EXTENSION IF NOT EXISTS vector;")
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS job_embeddings (
                fingerprint TEXT PRIMARY KEY,
                title TEXT,
                embedding vector(384),
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
        """)
        logger.info("Vector store initialized")


async def save_embedding(fingerprint: str, title: str, embedding: list[float]) -> bool:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                INSERT INTO job_embeddings (fingerprint, title, embedding)
                VALUES ($1, $2, $3::vector)
                ON CONFLICT (fingerprint) DO NOTHING
            """, fingerprint, title, str(embedding))
        return True
    except Exception as e:
        logger.error(f"Save embedding error: {e}")
        return False


async def find_similar(embedding: list[float], threshold: float = 0.9, limit: int = 5) -> list[dict]:
    try:
        pool = await get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch("""
                SELECT fingerprint, title,
                       1 - (embedding <=> $1::vector) AS similarity
                FROM job_embeddings
                WHERE 1 - (embedding <=> $1::vector) > $2
                ORDER BY similarity DESC
                LIMIT $3
            """, str(embedding), threshold, limit)
            return [dict(r) for r in rows]
    except Exception as e:
        logger.error(f"Find similar error: {e}")
        return []


def get_embedding(text: str) -> list[float]:
    try:
        from sentence_transformers import SentenceTransformer
        model = SentenceTransformer("all-MiniLM-L6-v2")
        return model.encode(text).tolist()
    except Exception as e:
        logger.error(f"Embedding error: {e}")
        return []