import hashlib
import json
from pathlib import Path
from loguru import logger

DEDUP_STORE = Path(".cache/dedup_hashes.json")


def _load() -> set:
    if DEDUP_STORE.exists():
        with open(DEDUP_STORE) as f:
            return set(json.load(f))
    return set()


def _save(hashes: set):
    DEDUP_STORE.parent.mkdir(parents=True, exist_ok=True)
    with open(DEDUP_STORE, "w") as f:
        json.dump(list(hashes), f)


def _job_fingerprint(job: dict) -> str:
    title = (job.get("title") or "unknown").lower().strip()
    org = (job.get("organization") or "unknown").lower().strip()
    last_date = job.get("last_date") or ""
    key = f"{title}|{org}|{last_date}"
    return hashlib.sha256(key.encode()).hexdigest()


def is_duplicate(job: dict) -> bool:
    hashes = _load()
    fingerprint = _job_fingerprint(job)

    if fingerprint in hashes:
        logger.debug(f"Duplicate skipped: {job.get('title')}")
        return True

    hashes.add(fingerprint)
    _save(hashes)
    logger.info(f"New unique job: {job.get('title')}")
    return False