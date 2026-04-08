from __future__ import annotations

from datetime import date, datetime
import json
from pathlib import Path
import sys
from typing import Any
import uuid

from airflow import DAG
from airflow.operators.python import PythonOperator
import pendulum


AIRFLOW_ROOT = Path(__file__).resolve().parents[1]
if str(AIRFLOW_ROOT) not in sys.path:
    sys.path.append(str(AIRFLOW_ROOT))

from etl import fetch, load, transform, validate


TOKYO_TZ = pendulum.timezone("Asia/Tokyo")
XCOM_ARTICLE_LIMIT = 100


def _serialize_value(value: Any) -> Any:
    if isinstance(value, dict):
        return {key: _serialize_value(item) for key, item in value.items()}
    if isinstance(value, list):
        return [_serialize_value(item) for item in value]
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    return value


def _run_date_from_context(context: dict[str, Any]) -> date:
    return context["logical_date"].in_timezone(TOKYO_TZ).date()


def _ensure_stage_table() -> None:
    with load.get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS etl_stage_articles (
                    batch_id TEXT NOT NULL,
                    article_id TEXT NOT NULL,
                    payload JSONB NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                    PRIMARY KEY (batch_id, article_id)
                )
                """
            )
        conn.commit()


def _store_stage_articles(batch_id: str, articles: list[dict[str, Any]]) -> None:
    _ensure_stage_table()
    serialized_articles = [_serialize_value(article) for article in articles]

    with load.get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM etl_stage_articles WHERE batch_id = %s", (batch_id,))
            cursor.executemany(
                """
                INSERT INTO etl_stage_articles (batch_id, article_id, payload)
                VALUES (%s, %s, %s::jsonb)
                """,
                [
                    (batch_id, str(article["id"]), json.dumps(article, ensure_ascii=False))
                    for article in serialized_articles
                ],
            )
        conn.commit()


def _load_stage_articles(batch_id: str, article_ids: list[str]) -> list[dict[str, Any]]:
    _ensure_stage_table()

    with load.get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                SELECT payload
                FROM etl_stage_articles
                WHERE batch_id = %s AND article_id = ANY(%s)
                ORDER BY created_at ASC
                """,
                (batch_id, article_ids),
            )
            rows = cursor.fetchall()

    articles = []
    for (payload,) in rows:
        if isinstance(payload, str):
            articles.append(json.loads(payload))
        else:
            articles.append(payload)
    return articles


def _cleanup_stage_articles(batch_id: str) -> None:
    _ensure_stage_table()
    with load.get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("DELETE FROM etl_stage_articles WHERE batch_id = %s", (batch_id,))
        conn.commit()


def _prepare_article_payload(articles: list[dict[str, Any]], task_label: str, run_id: str) -> dict[str, Any]:
    if len(articles) > XCOM_ARTICLE_LIMIT:
        batch_id = f"{task_label}-{run_id}-{uuid.uuid4()}"
        _store_stage_articles(batch_id, articles)
        return {
            "storage": "table",
            "batch_id": batch_id,
            "article_ids": [str(article["id"]) for article in articles],
            "count": len(articles),
        }

    return {
        "storage": "xcom",
        "articles": [_serialize_value(article) for article in articles],
        "count": len(articles),
    }


def _resolve_article_payload(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return payload

    if not isinstance(payload, dict):
        return []

    storage = payload.get("storage")
    if storage == "table":
        return _load_stage_articles(payload["batch_id"], payload.get("article_ids", []))
    if storage == "xcom":
        return payload.get("articles", [])
    return []


def _task_fetch(**context):
    articles = fetch.fetch_all_sources()
    return _prepare_article_payload(articles, "fetch", context["run_id"])


def _task_transform(**context):
    fetched_payload = context["ti"].xcom_pull(task_ids="task_fetch")
    fetched_articles = _resolve_article_payload(fetched_payload)
    normalized_articles = transform.normalize_articles(fetched_articles)
    transformed_articles = transform.process_batch(normalized_articles)
    return _prepare_article_payload(transformed_articles, "transform", context["run_id"])


def _task_load(**context):
    transformed_payload = context["ti"].xcom_pull(task_ids="task_transform")
    transformed_articles = _resolve_article_payload(transformed_payload)
    summary = load.load_batch(transformed_articles, _run_date_from_context(context))

    if isinstance(transformed_payload, dict) and transformed_payload.get("storage") == "table":
        _cleanup_stage_articles(transformed_payload["batch_id"])

    return summary


def _task_validate(**context):
    return validate.validate_daily_load(_run_date_from_context(context))


def _task_notify(**context):
    load_summary = context["ti"].xcom_pull(task_ids="task_load") or {}
    validation_summary = context["ti"].xcom_pull(task_ids="task_validate") or {}
    print(
        json.dumps(
            {
                "run_date": _run_date_from_context(context).isoformat(),
                "load": load_summary,
                "validation": validation_summary,
            },
            ensure_ascii=False,
            indent=2,
        )
    )


default_args = {
    "owner": "news-etl",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": pendulum.duration(minutes=5),
}


with DAG(
    dag_id="japan_news_etl",
    description="Daily ETL for Japanese news across policy, AI/tech, and language learning.",
    default_args=default_args,
    start_date=pendulum.datetime(2026, 3, 27, tz=TOKYO_TZ),
    schedule_interval="0 7 * * *",
    catchup=False,
    tags=["japan", "news", "etl"],
) as dag:
    task_fetch = PythonOperator(
        task_id="task_fetch",
        python_callable=_task_fetch,
    )

    task_transform = PythonOperator(
        task_id="task_transform",
        python_callable=_task_transform,
    )

    task_load = PythonOperator(
        task_id="task_load",
        python_callable=_task_load,
    )

    task_validate = PythonOperator(
        task_id="task_validate",
        python_callable=_task_validate,
    )

    task_notify = PythonOperator(
        task_id="task_notify",
        python_callable=_task_notify,
    )

    task_fetch >> task_transform >> task_load >> task_validate >> task_notify
