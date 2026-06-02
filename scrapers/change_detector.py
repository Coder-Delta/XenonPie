import hashlib
import json
from pathlib import Path
from loguru import logger
from typing import Optional

HASH_STORE_PATH = Path(".cache/page_hashes.json")


def _load_hashes() -> dict:
    if HASH_STORE_PATH.exists():
        with open(HASH_STORE_PATH) as f:
            return json.load(f)
    return {}


def _save_hashes(hashes: dict):
    HASH_STORE_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(HASH_STORE_PATH, "w") as f:
        json.dump(hashes, f, indent=2)


def compute_hash(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def has_changed(url: str, current_content: str) -> bool:
    hashes = _load_hashes()
    new_hash = compute_hash(current_content)
    old_hash = hashes.get(url)

    if old_hash is None:
        logger.info(f"New URL tracked: {url}")
        hashes[url] = new_hash
        _save_hashes(hashes)
        return True

    if old_hash != new_hash:
        logger.info(f"Change detected: {url}")
        hashes[url] = new_hash
        _save_hashes(hashes)
        return True

    logger.debug(f"No change: {url}")
    return False


def reset_hash(url: str):
    hashes = _load_hashes()
    if url in hashes:
        del hashes[url]
        _save_hashes(hashes)
        logger.info(f"Hash reset for {url}")