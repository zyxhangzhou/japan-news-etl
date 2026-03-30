from __future__ import annotations

from collections import defaultdict
from datetime import date
import json
import logging
import os
from typing import Any

from dotenv import load_dotenv
import psycopg2
import redis


load_dotenv()

logger = logging.getLogger(__name__)


def get_db_connection():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL is not set")
    return psycopg2.connect(database_url)


def _get_redis_client():
    return redis.Redis(
        host=os.getenv("REDIS_HOST", "redis"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        db=int(os.getenv("REDIS_DB", "0")),
        password=os.getenv("REDIS_PASSWORD") or None,
        decode_responses=True,
    )


def _normalize_articles(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduplicated_by_hash: dict[str, dict[str, Any]] = {}

    for article in articles:
        url_hash = article.get("url_hash")
        if not url_hash:
            logger.warning("Skipping article without url_hash during load: %s", article.get("url"))
            continue
        deduplicated_by_hash[url_hash] = article

    return list(deduplicated_by_hash.values())


def _fetch_existing_hashes(url_hashes: list[str]) -> set[str]:
    if not url_hashes:
        return set()

    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT url_hash FROM news_articles WHERE url_hash = ANY(%s)",
                (url_hashes,),
            )
            return {row[0] for row in cursor.fetchall()}


def upsert_articles(articles: list[dict[str, Any]]) -> tuple[int, int]:
    normalized_articles = _normalize_articles(articles)
    if not normalized_articles:
        return (0, 0)

    existing_hashes = _fetch_existing_hashes([article["url_hash"] for article in normalized_articles])
    inserted_count = sum(1 for article in normalized_articles if article["url_hash"] not in existing_hashes)
    updated_count = len(normalized_articles) - inserted_count

    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.executemany(
                """
                INSERT INTO news_articles (
                    id,
                    url,
                    url_hash,
                    title,
                    summary,
                    content,
                    source,
                    category,
                    language,
                    published_at,
                    fetched_at,
                    llm_summary_ja,
                    llm_summary_zh,
                    embedding
                )
                VALUES (
                    %(id)s,
                    %(url)s,
                    %(url_hash)s,
                    %(title)s,
                    %(summary)s,
                    %(content)s,
                    %(source)s,
                    %(category)s,
                    %(language)s,
                    %(published_at)s,
                    %(fetched_at)s,
                    NULL,
                    %(llm_summary_zh)s,
                    NULL
                )
                ON CONFLICT (url_hash) DO UPDATE
                SET
                    fetched_at = EXCLUDED.fetched_at,
                    llm_summary_zh = COALESCE(NULLIF(EXCLUDED.llm_summary_zh, ''), news_articles.llm_summary_zh)
                """,
                normalized_articles,
            )
        conn.commit()

    logger.info(
        "Upserted articles: %s input, %s inserted, %s updated",
        len(normalized_articles),
        inserted_count,
        updated_count,
    )
    return (inserted_count, updated_count)


def log_run(
    run_date: date,
    category: str,
    source: str,
    fetched_count: int,
    inserted_count: int,
    error_message: str | None = None,
):
    with get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                INSERT INTO etl_run_log (
                    run_date,
                    category,
                    source,
                    fetched_count,
                    inserted_count,
                    error_message
                )
                VALUES (%s, %s, %s, %s, %s, %s)
                """,
                (run_date, category, source, fetched_count, inserted_count, error_message),
            )
        conn.commit()


def load_batch(articles: list[dict[str, Any]], run_date: date) -> dict[str, Any]:
    normalized_articles = _normalize_articles(articles)
    existing_hashes = _fetch_existing_hashes([article["url_hash"] for article in normalized_articles])
    inserted_count, updated_count = upsert_articles(normalized_articles)

    grouped_articles: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for article in normalized_articles:
        grouped_articles[(article.get("category", "unknown"), article.get("source", "unknown"))].append(article)

    for (category, source), grouped in grouped_articles.items():
        group_inserted_count = sum(1 for article in grouped if article["url_hash"] not in existing_hashes)
        log_run(
            run_date=run_date,
            category=category,
            source=source,
            fetched_count=len(grouped),
            inserted_count=group_inserted_count,
            error_message=None,
        )

    summary = {
        "run_date": run_date.isoformat(),
        "fetched_count": len(normalized_articles),
        "inserted_count": inserted_count,
        "updated_count": updated_count,
        "group_count": len(grouped_articles),
    }
    logger.info("Load batch summary: %s", summary)
    return summary


def load_news(**context):
    validated_news = context["ti"].xcom_pull(task_ids="validate_news", key="validated_news") or []
    redis_client = _get_redis_client()
    summary = load_batch(validated_news, context["logical_date"].date())

    redis_client.set(
        "news:last_load_summary",
        json.dumps(summary),
        ex=int(os.getenv("NEWS_ETL_QUERY_CACHE_TTL_SECONDS", "3600")),
    )

    return summary
