from __future__ import annotations

import hashlib
import os
from typing import Any


KEYWORD_RULES = {
    "immigration_foreign_policy": ["移民", "外国人", "入管", "在留", "visa", "immigration"],
    "ai_tech": ["AI", "人工知能", "半導体", "tech", "technology", "startup"],
    "language_learning": ["日本語", "語学", "学習", "education", "language"],
}


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
    article_id = hashlib.sha256((item.get("url") or raw_text).encode("utf-8")).hexdigest()

    return {
        "article_id": article_id,
        "source": item.get("source"),
        "category": _classify_category(raw_text, item.get("category")),
        "title": item.get("title", "").strip(),
        "summary": item.get("summary", "").strip(),
        "content": raw_text,
        "url": item.get("url"),
        "published_at": item.get("published_at"),
        "fetched_at": item.get("fetched_at"),
        "language": item.get("language", os.getenv("NEWS_ETL_SOURCE_LANG", "ja")),
        "embedding_input": raw_text[:8000],
    }


def _classify_category(text: str, fallback: str | None) -> str:
    lower_text = text.lower()
    for category, keywords in KEYWORD_RULES.items():
        if any(keyword.lower() in lower_text for keyword in keywords):
            return category
    return fallback or "uncategorized"


def transform_news(**context):
    raw_news = context["ti"].xcom_pull(task_ids="fetch_news", key="raw_news") or []
    transformed = [_normalize_item(item) for item in raw_news]
    context["ti"].xcom_push(key="transformed_news", value=transformed)
    return transformed
