from __future__ import annotations

from datetime import datetime
import logging
import sys

from dotenv import load_dotenv

from etl import fetch, load, transform


load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
logger = logging.getLogger("idempotency_test")


class IdempotencyCheckError(Exception):
    pass


def ensure_run_log_schema() -> None:
    with load.get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                """
                ALTER TABLE etl_run_log
                ADD COLUMN IF NOT EXISTS updated_count INT NOT NULL DEFAULT 0
                """
            )
        conn.commit()


def get_articles_snapshot() -> tuple[int, str | None]:
    with load.get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COUNT(*) FROM news_articles")
            row_count = cursor.fetchone()[0]
            cursor.execute(
                """
                SELECT url_hash
                FROM news_articles
                ORDER BY fetched_at DESC NULLS LAST, id DESC
                LIMIT 1
                """
            )
            latest_row = cursor.fetchone()

    latest_hash = latest_row[0] if latest_row else None
    return row_count, latest_hash


def get_latest_run_log_id() -> int:
    with load.get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute("SELECT COALESCE(MAX(id), 0) FROM etl_run_log")
            return cursor.fetchone()[0]


def get_updated_count_since(run_log_id: int) -> int:
    with load.get_db_connection() as conn:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT COALESCE(SUM(updated_count), 0) FROM etl_run_log WHERE id > %s",
                (run_log_id,),
            )
            return cursor.fetchone()[0]


def run_pipeline() -> dict[str, int | str]:
    fetched_articles = fetch.fetch_all_sources()
    normalized_articles = [transform._normalize_item(article) for article in fetched_articles]
    processed_articles = transform.process_batch(normalized_articles)
    return load.load_batch(processed_articles, datetime.now().date())


def main() -> int:
    try:
        ensure_run_log_schema()

        before_count, before_hash = get_articles_snapshot()
        first_summary = run_pipeline()
        after_first_count, after_first_hash = get_articles_snapshot()

        second_run_log_checkpoint = get_latest_run_log_id()
        second_summary = run_pipeline()
        after_second_count, after_second_hash = get_articles_snapshot()
        second_run_updated = get_updated_count_since(second_run_log_checkpoint)

        if after_second_count != after_first_count:
            raise IdempotencyCheckError(
                "第二次执行后行数发生变化："
                f"第一次后={after_first_count}，第二次后={after_second_count}"
            )

        if second_run_updated <= 0:
            raise IdempotencyCheckError(
                "第二次运行没有记录 updated_count，无法证明 upsert 生效"
            )

        print("ETL 幂等性验证报告")
        print("=" * 40)
        print(f"执行前：row_count={before_count}, latest_url_hash={before_hash}")
        print(
            f"第一次执行后：row_count={after_first_count}, latest_url_hash={after_first_hash}, "
            f"inserted={first_summary.get('inserted_count', 0)}, updated={first_summary.get('updated_count', 0)}"
        )
        print(
            f"第二次执行后：row_count={after_second_count}, latest_url_hash={after_second_hash}, "
            f"inserted={second_summary.get('inserted_count', 0)}, updated={second_summary.get('updated_count', 0)}"
        )
        print(f"第二次运行新增 run_log updated_count 汇总：{second_run_updated}")
        print()
        print(f"✅ 幂等性验证通过：两次执行后数据库行数一致（{after_second_count}条）")
        print(f"✅ Upsert 正常工作：第二次运行更新了 {second_run_updated}条已存在记录")
        return 0
    except Exception as exc:
        print("ETL 幂等性验证报告")
        print("=" * 40)
        print(f"❌ 幂等性验证失败：{exc}")
        logger.exception("Idempotency validation failed")
        return 1


if __name__ == "__main__":
    sys.exit(main())