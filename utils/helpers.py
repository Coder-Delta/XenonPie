import re
import hashlib
from datetime import datetime
from typing import Optional


def clean_text(text: str) -> str:
    text = re.sub(r'\s+', ' ', text)
    text = re.sub(r'[^\x00-\x7F]+', ' ', text)
    return text.strip()


def truncate(text: str, max_chars: int = 1500) -> str:
    if len(text) <= max_chars:
        return text
    return text[:max_chars] + "..."


def make_hash(text: str) -> str:
    return hashlib.sha256(text.encode()).hexdigest()


def parse_date(date_str: str) -> Optional[datetime]:
    if not date_str or date_str == "N/A":
        return None
    formats = [
        "%Y-%m-%d",
        "%d-%m-%Y",
        "%d/%m/%Y",
        "%B %d, %Y",
        "%d %B %Y",
        "%d %b %Y",
    ]
    for fmt in formats:
        try:
            return datetime.strptime(date_str.strip(), fmt)
        except ValueError:
            continue
    return None


def days_until(date_str: str) -> Optional[int]:
    dt = parse_date(date_str)
    if not dt:
        return None
    return (dt.date() - datetime.today().date()).days


def safe_int(value) -> Optional[int]:
    try:
        return int(str(value).replace(",", "").strip())
    except (ValueError, TypeError):
        return None