from __future__ import annotations
from datetime import datetime
import logging
import os
from typing import Any
from dotenv import load_dotenv
import requests
from etl import fetch, load, transform
load_dotenv()
load_dotenv('.env.local', override=True)
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s - %(message)s")
logger = logging.getLogger("demo")
API_URL = os.getenv("API_BASE_URL", "http://localhost:8081/api/query")
SEPARATOR = "\u2501" * 30
def print_welcome() -> None:
    print(SEPARATOR)
    print("\u65e5\u672c\u65b0\u95fb ETL Demo CLI")
    print()
    print("\u76f4\u63a5\u8f93\u5165\u95ee\u9898\uff1a\u8c03\u7528\u672c\u5730 Spring Boot API")
    print('\u8f93\u5165 "stats"\uff1a\u67e5\u770b\u4eca\u65e5 ETL \u7edf\u8ba1')
    print('\u8f93\u5165 "run"\uff1a\u624b\u52a8\u6267\u884c\u4e00\u6b21 ETL')
    print('\u8f93\u5165 "exit"\uff1a\u9000\u51fa')
    print(SEPARATOR)
def _format_published_at(value: Any) -> str:
    if not value:
        return "-"
    if isinstance(value, str):
        return value
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)
def show_query_response(payload: dict[str, Any]) -> None:
    answer = payload.get("answer") or "\u6682\u65e0\u56de\u7b54"
    articles = payload.get("articles") or []
    print(SEPARATOR)
    print(f"\u56de\u7b54\uff1a{answer}")
    print()
    print(f"\u53c2\u8003\u6765\u6e90\uff08{len(articles)}\u6761\uff09\uff1a")
    for article in articles:
        source = article.get("source") or "Unknown"
        title = article.get("title") or "Untitled"
        published_at = _format_published_at(article.get("published_at") or article.get("publishedAt"))
        url = article.get("url") or "-"
        print(f"- [{source}] {title} ({published_at})")
        print(f"  {url}")
    print(SEPARATOR)
def query_api(question: str) -> None:
    try:
        response = requests.post(API_URL, json={"query": question}, timeout=30)
        response.raise_for_status()
    except requests.RequestException:
        print("API \u4e0d\u53ef\u7528\uff0c\u8bf7\u68c0\u67e5 Spring Boot \u670d\u52a1\u662f\u5426\u5df2\u542f\u52a8\uff0c\u4ee5\u53ca localhost:8080 \u662f\u5426\u53ef\u8bbf\u95ee\u3002")
        logger.exception("Failed to call query API")
        return
    try:
        payload = response.json()
    except ValueError:
        print("API \u8fd4\u56de\u4e86\u65e0\u6548\u54cd\u5e94\uff0c\u8bf7\u68c0\u67e5\u670d\u52a1\u65e5\u5fd7\u3002")
        logger.exception("Failed to parse API response as JSON")
        return
    show_query_response(payload)
def show_stats() -> None:
    today = datetime.now().date()
    try:
        with load.get_db_connection() as conn:
            with conn.cursor() as cursor:
                cursor.execute(
                    """
                    SELECT category, source, fetched_count, inserted_count, updated_count, error_message
                    FROM etl_run_log
                    WHERE run_date = %s
                    ORDER BY category, source
                    """,
                    (today,),
                )
                rows = cursor.fetchall()
    except Exception:
        print("\u65e0\u6cd5\u67e5\u8be2 ETL \u7edf\u8ba1\uff0c\u8bf7\u68c0\u67e5\u6570\u636e\u5e93\u8fde\u63a5\u914d\u7f6e\u3002")
        logger.exception("Failed to query ETL stats")
        return
    print(SEPARATOR)
    print(f"\u4eca\u65e5 ETL \u7edf\u8ba1\uff1a{today.isoformat()}")
    if not rows:
        print("\u4eca\u5929\u6682\u65e0 ETL \u8fd0\u884c\u8bb0\u5f55\u3002")
        print(SEPARATOR)
        return
    total_fetched = 0
    total_inserted = 0
    total_updated = 0
    for category, source, fetched_count, inserted_count, updated_count, error_message in rows:
        total_fetched += fetched_count or 0
        total_inserted += inserted_count or 0
        total_updated += updated_count or 0
        print(f"- {category} | {source}")
        print(f"  fetched={fetched_count}, inserted={inserted_count}, updated={updated_count}")
        if error_message:
            print(f"  error={error_message}")
    print()
    print(
        f"\u603b\u8ba1\uff1afetched={total_fetched}, inserted={total_inserted}, "
        f"updated={total_updated}, runs={len(rows)}"
    )
    print(SEPARATOR)
def run_etl() -> None:
    print("\u5f00\u59cb\u6267\u884c\u624b\u52a8 ETL...")
    try:
        fetched_articles = fetch.fetch_all_sources()
        normalized_articles = transform.normalize_articles(fetched_articles)
        processed_articles = transform.process_batch(normalized_articles)
        summary = load.load_batch(processed_articles, datetime.now().date())
    except Exception:
        print("\u624b\u52a8 ETL \u6267\u884c\u5931\u8d25\uff0c\u8bf7\u68c0\u67e5\u65e5\u5fd7\u548c\u73af\u5883\u53d8\u91cf\u914d\u7f6e\u3002")
        logger.exception("Manual ETL run failed")
        return
    print(SEPARATOR)
    print("\u624b\u52a8 ETL \u6267\u884c\u5b8c\u6210")
    print(f"\u6293\u53d6\uff1a{len(fetched_articles)}")
    print(f"\u5904\u7406\u540e\uff1a{len(processed_articles)}")
    print(f"\u5165\u5e93\u65b0\u589e\uff1a{summary.get('inserted_count', 0)}")
    print(f"\u5165\u5e93\u66f4\u65b0\uff1a{summary.get('updated_count', 0)}")
    print(SEPARATOR)
def main() -> None:
    print_welcome()
    while True:
        try:
            command = input(">>> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            print("\u5df2\u9000\u51fa\u3002")
            return
        if not command:
            continue
        if command.lower() == "exit":
            print("\u5df2\u9000\u51fa\u3002")
            return
        if command.lower() == "stats":
            show_stats()
            continue
        if command.lower() == "run":
            run_etl()
            continue
        query_api(command)
if __name__ == "__main__":
    main()