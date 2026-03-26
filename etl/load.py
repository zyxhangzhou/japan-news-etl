from __future__ import annotations

import json
import os

import psycopg2
from psycopg2.extras import Json
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
                        article_id,
                        source,
                        category,
                        title,
                        summary,
                        content,
                        url,
                        published_at,
                        fetched_at,
                        language,
                        metadata
                    )
                    VALUES (
                        %(article_id)s,
                        %(source)s,
                        %(category)s,
                        %(title)s,
                        %(summary)s,
                        %(content)s,
                        %(url)s,
                        NULLIF(%(published_at)s, ''),
                        %(fetched_at)s,
                        %(language)s,
                        %(metadata)s
                    )
                    ON CONFLICT (article_id) DO UPDATE
                    SET
                        source = EXCLUDED.source,
                        category = EXCLUDED.category,
                        title = EXCLUDED.title,
                        summary = EXCLUDED.summary,
                        content = EXCLUDED.content,
                        published_at = EXCLUDED.published_at,
                        fetched_at = EXCLUDED.fetched_at,
                        language = EXCLUDED.language,
                        metadata = EXCLUDED.metadata,
                        updated_at = NOW()
                    """,
                    {
                        **item,
                        "metadata": Json(
                            {
                                "url": item.get("url"),
                                "embedding_input": item.get("embedding_input"),
                            }
                        ),
                    },
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
