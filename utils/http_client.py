from __future__ import annotations

import httpx
from httpx import Limits
from loguru import logger
from typing import Optional

from config.settings import settings

_client: Optional[httpx.AsyncClient] = None


async def get_http_client() -> httpx.AsyncClient:
    global _client
    if _client is None:
        limits = Limits(max_keepalive_connections=20, max_connections=100)
        _client = httpx.AsyncClient(
            timeout=httpx.Timeout(30.0, connect=10.0),
            limits=limits,
            headers={
                "User-Agent": "XenonPie/1.0 (+https://github.com/xenonpie)"
            },
            follow_redirects=True,
        )
        logger.info("Shared HTTP client created")
    return _client


async def close_http_client() -> None:
    global _client
    if _client is not None:
        await _client.aclose()
        _client = None
        logger.info("Shared HTTP client closed")
