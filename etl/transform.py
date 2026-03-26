from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
import os
from typing import Any
import uuid


KEYWORD_RULES = {
    "immigration": ["移民", "外国人", "入管", "在留", "visa", "immigration"],
    "ai_tech": ["AI", "人工知能", "半導体", "tech", "technology", "startup"],
    "language_learning": ["日本語", "語学", "学習", "education", "language"],
}


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None

    try:
        return datetime.fromisoformat(value)
    except ValueError:
        pass

    try:
        parsed = parsedate_to_datetime(value)
    except (TypeError, ValueError):
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed


def _normalize_item(item: dict[str, Any]) -> dict[str, Any]:
    raw_text = " ".join(
        filter(
            None,
            [
                item.get("title", ""),
                item.get("summary", ""),
            ],
        )
    ).strip()
    canonical_key = item.get("url") or raw_text
    article_id = str(uuid.uuid5(uuid.NAMESPACE_URL, canonical_key))
    url_hash = hashlib.md5((item.get("url") or canonical_key).encode("utf-8")).hexdigest()

    return {
        "id": article_id,
        "source": item.get("source"),
        "category": _classify_category(raw_text, item.get("category")),
        "title": item.get("title", "").strip(),
        "summary": item.get("summary", "").strip(),
        "content": raw_text,
        "url": item.get("url"),
        "url_hash": url_hash,
        "published_at": _parse_datetime(item.get("published_at")),
        "fetched_at": _parse_datetime(item.get("fetched_at")) or datetime.now(timezone.utc),
        "language": item.get("language", os.getenv("NEWS_ETL_SOURCE_LANG", "ja")),
        "embedding_input": raw_text[:8000],
    }


def _classify_category(text: str, fallback: str | None) -> str:
    lower_text = text.lower()
    for category, keywords in KEYWORD_RULES.items():
        if any(keyword.lower() in lower_text for keyword in keywords):
            return category
    return fallback or "language_learning"


def transform_news(**context):
    raw_news = context["ti"].xcom_pull(task_ids="fetch_news", key="raw_news") or []
    transformed = [_normalize_item(item) for item in raw_news]
    context["ti"].xcom_push(key="transformed_news", value=transformed)
    return transformed
