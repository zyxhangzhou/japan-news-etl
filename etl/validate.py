from __future__ import annotations

from datetime import date
import logging
import os
from typing import Any

from dotenv import load_dotenv
import psycopg2


load_dotenv()
load_dotenv('.env.local', override=True)

logger = logging.getLogger(__name__)

EXPECTED_CATEGORIES = ("immigration", "ai_tech", "language_learning")
REQUIRED_FIELDS = ["id", "category", "title", "url", "url_hash"]


def _get_db_connection():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL is not set")
    return psycopg2.connect(database_url)


def validate_daily_load(run_date: date) -> dict[str, Any]:
    category_counts = {category: 0 for category in EXPECTED_CATEGORIES}

    with _get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT category, COUNT(*) AS article_count
                FROM news_articles
                WHERE DATE(fetched_at AT TIME ZONE 'Asia/Tokyo') = %s
                GROUP BY category
                """,
                (run_date,),
            )
            for category, article_count in cursor.fetchall():
                category_counts[category] = article_count

    total_count = sum(category_counts.values())
    warnings: list[str] = []
    errors: list[str] = []

    for category, article_count in category_counts.items():
        if article_count == 0:
            errors.append(f"{category} has no loaded articles for {run_date.isoformat()}")
        elif article_count < 2:
            warnings.append(f"{category} has low daily volume: {article_count}")

    if total_count < 5:
        warnings.append(f"Total daily load is low: {total_count}")

    if errors:
        status = "ERROR"
    elif warnings:
        status = "WARNING"
    else:
        status = "OK"

    message_parts = []
    if errors:
        message_parts.append("; ".join(errors))
    if warnings:
        message_parts.append("; ".join(warnings))
    if not message_parts:
        message_parts.append(f"Daily load looks healthy: total={total_count}")

    result = {
        "status": status,
        "details": {
            "run_date": run_date.isoformat(),
            "category_counts": category_counts,
            "total_count": total_count,
            "warnings": warnings,
            "errors": errors,
        },
        "message": " | ".join(message_parts),
    }

    if status == "ERROR":
        logger.error("Daily load validation result: %s", result)
    elif status == "WARNING":
        logger.warning("Daily load validation result: %s", result)
    else:
        logger.info("Daily load validation result: %s", result)

    return result


def validate_news(**context):
    transformed_news = context["ti"].xcom_pull(task_ids="transform_news", key="transformed_news") or []
    valid_items = []

    for item in transformed_news:
        if all(item.get(field) for field in REQUIRED_FIELDS):
            valid_items.append(item)

    context["ti"].xcom_push(key="validated_news", value=valid_items)
    return valid_items
