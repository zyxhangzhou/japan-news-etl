from __future__ import annotations

import json
import os

import psycopg2
import redis


def _get_postgres_connection():
    return psycopg2.connect(
        host=os.getenv("NEWS_DB_HOST", "postgres"),
        port=os.getenv("NEWS_DB_PORT", "5432"),
        dbname=os.getenv("NEWS_DB_NAME", "japan_news"),
        user=os.getenv("NEWS_DB_USER", "postgres"),
        password=os.getenv("NEWS_DB_PASSWORD", ""),
    )


def _get_redis_client():
    return redis.Redis(
        host=os.getenv("REDIS_HOST", "redis"),
        port=int(os.getenv("REDIS_PORT", "6379")),
        db=int(os.getenv("REDIS_DB", "0")),
        password=os.getenv("REDIS_PASSWORD") or None,
        decode_responses=True,
    )


def load_news(**context):
    validated_news = context["ti"].xcom_pull(task_ids="validate_news", key="validated_news") or []
    redis_client = _get_redis_client()

    with _get_postgres_connection() as conn:
        with conn.cursor() as cursor:
            for item in validated_news:
                cursor.execute(
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
                    ON CONFLICT (url) DO UPDATE
                    SET
                        url_hash = EXCLUDED.url_hash,
                        source = EXCLUDED.source,
                        category = EXCLUDED.category,
                        title = EXCLUDED.title,
                        summary = EXCLUDED.summary,
                        content = EXCLUDED.content,
                        published_at = EXCLUDED.published_at,
                        fetched_at = EXCLUDED.fetched_at,
                        language = EXCLUDED.language,
                        llm_summary_zh = EXCLUDED.llm_summary_zh
                    """,
                    item,
                )

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
                (
                    context["logical_date"].date(),
                    "all",
                    "rss",
                    len(validated_news),
                    len(validated_news),
                    None,
                ),
            )

    redis_client.set(
        "news:last_load_summary",
        json.dumps(
            {
                "loaded_count": len(validated_news),
            }
        ),
        ex=int(os.getenv("NEWS_ETL_QUERY_CACHE_TTL_SECONDS", "3600")),
    )

    return {"loaded_count": len(validated_news)}
