from __future__ import annotations
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
import json
import logging
import os
import time
from typing import Any
import uuid
from dotenv import load_dotenv
from openai import OpenAI
import psycopg2
load_dotenv()
logger = logging.getLogger(__name__)
ALLOWED_CATEGORIES = {"immigration", "ai_tech", "language_learning", "other"}
CLASSIFIER_MODEL = os.getenv("OPENAI_CLASSIFIER_MODEL", "gpt-4.1-mini")
KEYWORD_RULES = {
    "immigration": ["\u79fb\u6c11", "\u5916\u56fd\u4eba", "\u5165\u7ba1", "\u5728\u7559", "visa", "immigration"],
    "ai_tech": ["AI", "\u4eba\u5de5\u77e5\u80fd", "\u534a\u5bfc\u4f53", "tech", "technology", "startup"],
    "language_learning": ["\u65e5\u672c\u8a9e", "\u8a9e\u5b66", "\u5b66\u7fd2", "education", "language"],
}
SYSTEM_PROMPT = "\u4f60\u662f\u4e00\u4e2a\u65b0\u95fb\u5206\u7c7b\u52a9\u624b\uff0c\u4e13\u6ce8\u4e8e\u65e5\u672c\u76f8\u5173\u65b0\u95fb\u3002"
USER_PROMPT_TEMPLATE = """\u8bf7\u5206\u6790\u4ee5\u4e0b\u65b0\u95fb\uff0c\u8fd4\u56de JSON \u683c\u5f0f\uff1a
{{"category": "immigration|ai_tech|language_learning|other", "summary_zh": "2-3\\u53e5\\u4e2d\\u6587\\u6458\\u8981"}}
\u6807\u9898\uff1a{title}
\u6458\u8981\uff1a{summary}
"""
_openai_client: OpenAI | None = None
def _get_postgres_connection():
    return psycopg2.connect(
        host=os.getenv("NEWS_DB_HOST", "postgres"),
        port=os.getenv("NEWS_DB_PORT", "5432"),
        dbname=os.getenv("NEWS_DB_NAME", "japan_news"),
        user=os.getenv("NEWS_DB_USER", "postgres"),
        password=os.getenv("NEWS_DB_PASSWORD", ""),
    )
def _get_openai_client() -> OpenAI:
    global _openai_client
    if _openai_client is None:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY is not set")
        _openai_client = OpenAI(api_key=api_key)
    return _openai_client
def _parse_datetime(value: str | datetime | None) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        parsed = None
    if parsed is None:
        try:
            parsed = parsedate_to_datetime(value)
        except (TypeError, ValueError):
            logger.warning("Failed to parse datetime value: %s", value)
            return None
    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)
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
    url_hash = item.get("url_hash") or hashlib.md5((item.get("url") or canonical_key).encode("utf-8")).hexdigest()
    return {
        "id": item.get("id") or article_id,
        "source": item.get("source"),
        "category": _classify_category(raw_text, item.get("category")),
        "title": item.get("title", "").strip(),
        "summary": item.get("summary", "").strip(),
        "content": item.get("content") or raw_text,
        "url": item.get("url"),
        "url_hash": url_hash,
        "published_at": _parse_datetime(item.get("published_at")),
        "fetched_at": _parse_datetime(item.get("fetched_at")) or datetime.now(timezone.utc),
        "language": item.get("language", os.getenv("NEWS_ETL_SOURCE_LANG", "ja")),
        "embedding_input": raw_text[:8000],
        "llm_summary_zh": item.get("llm_summary_zh"),
    }
def normalize_articles(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [_normalize_item(item) for item in items]
def _classify_category(text: str, fallback: str | None) -> str:
    lower_text = text.lower()
    for category, keywords in KEYWORD_RULES.items():
        if any(keyword.lower() in lower_text for keyword in keywords):
            return category
    return fallback or "language_learning"
def _extract_response_json(response: Any) -> dict[str, Any]:
    response_text = getattr(response, "output_text", "") or ""
    if not response_text:
        raise ValueError("OpenAI response did not include output_text")
    return json.loads(response_text)
def deduplicate(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not articles:
        return []
    url_hash_to_article: dict[str, dict[str, Any]] = {}
    for article in articles:
        url_hash = article.get("url_hash")
        if not url_hash:
            logger.warning("Skipping article without url_hash during deduplication: %s", article.get("url"))
            continue
        url_hash_to_article[url_hash] = article
    if not url_hash_to_article:
        return []
    try:
        with _get_postgres_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    "SELECT url_hash FROM news_articles WHERE url_hash = ANY(%s)",
                    (list(url_hash_to_article.keys()),),
                )
                existing_hashes = {row[0] for row in cursor.fetchall()}
    except Exception:
        logger.exception("Failed to deduplicate against PostgreSQL; returning original batch")
        return list(url_hash_to_article.values())
    new_articles = [
        article
        for url_hash, article in url_hash_to_article.items()
        if url_hash not in existing_hashes
    ]
    logger.info(
        "Deduplicated articles: %s input, %s new, %s existing",
        len(articles),
        len(new_articles),
        len(existing_hashes),
    )
    return new_articles
def classify_and_summarize(article: dict[str, Any]) -> dict[str, Any] | None:
    try:
        client = _get_openai_client()
        response = client.responses.create(
            model=CLASSIFIER_MODEL,
            input=[
                {
                    "role": "system",
                    "content": [
                        {
                            "type": "input_text",
                            "text": SYSTEM_PROMPT,
                        }
                    ],
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "input_text",
                            "text": USER_PROMPT_TEMPLATE.format(
                                title=article.get("title", ""),
                                summary=article.get("summary", ""),
                            ),
                        }
                    ],
                },
            ],
        )
        payload = _extract_response_json(response)
        category = payload.get("category")
        summary_zh = payload.get("summary_zh")
        if category not in ALLOWED_CATEGORIES:
            raise ValueError(f"Unexpected category from OpenAI: {category}")
        if category == "other":
            logger.info("Filtered article as other: %s", article.get("url"))
            return None
        return {
            **article,
            "category": category,
            "llm_summary_zh": summary_zh.strip() if isinstance(summary_zh, str) and summary_zh.strip() else None,
        }
    except Exception:
        logger.exception("Failed to classify article with OpenAI: %s", article.get("url"))
        fallback_category = article.get("category")
        if fallback_category == "other":
            return None
        return {
            **article,
            "category": fallback_category,
            "llm_summary_zh": None,
        }
def process_batch(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduplicated_articles = deduplicate(articles)
    processed_articles = []
    for article in deduplicated_articles:
        processed_article = classify_and_summarize(article)
        if processed_article is not None:
            processed_articles.append(processed_article)
        time.sleep(0.5)
    logger.info(
        "Processed article batch: %s input, %s deduplicated, %s output",
        len(articles),
        len(deduplicated_articles),
        len(processed_articles),
    )
    return processed_articles
def transform_news(**context):
    raw_news = context["ti"].xcom_pull(task_ids="fetch_news", key="raw_news") or []
    normalized_articles = normalize_articles(raw_news)
    transformed = process_batch(normalized_articles)
    context["ti"].xcom_push(key="transformed_news", value=transformed)
    return transformed