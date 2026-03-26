from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path
import sys

from airflow import DAG
from airflow.operators.python import PythonOperator


AIRFLOW_ROOT = Path(__file__).resolve().parents[1]
if str(AIRFLOW_ROOT) not in sys.path:
    sys.path.append(str(AIRFLOW_ROOT))

from etl.fetch import fetch_news
from etl.transform import transform_news
from etl.validate import validate_news
from etl.load import load_news


default_args = {
    "owner": "news-etl",
    "depends_on_past": False,
    "retries": 2,
    "retry_delay": timedelta(minutes=5),
}


with DAG(
    dag_id="japan_news_daily_etl",
    description="Daily ETL for Japanese news across policy, AI/tech, and language learning.",
    default_args=default_args,
    start_date=datetime(2026, 1, 1),
    schedule="0 6 * * *",
    catchup=False,
    tags=["japan", "news", "etl"],
) as dag:
    fetch_task = PythonOperator(
        task_id="fetch_news",
        python_callable=fetch_news,
    )

    transform_task = PythonOperator(
        task_id="transform_news",
        python_callable=transform_news,
    )

    validate_task = PythonOperator(
        task_id="validate_news",
        python_callable=validate_news,
    )

    load_task = PythonOperator(
        task_id="load_news",
        python_callable=load_news,
    )

    fetch_task >> transform_task >> validate_task >> load_task
