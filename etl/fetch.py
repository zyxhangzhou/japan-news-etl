from __future__ import annotations

from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
import hashlib
import logging
import os
from typing import Any

from dotenv import load_dotenv
import feedparser
import requests


load_dotenv()

logger = logging.getLogger(__name__)

FETCH_TIMEOUT_SECONDS = 10

RSS_SOURCES: dict[str, list[dict[str, str]]] = {
    "immigration": [
        {
            "name": "NHK World (EN)",
            "url": "https://www3.nhk.or.jp/rss/news/cat6.xml",
            "language": "en",
        },
        {
            "name": "Japan Times Immigration",
            "url": "https://www.japantimes.co.jp/feed/",
            "language": "en",
        },
    ],
    "ai_tech": [
        {
            "name": "NHK World Tech",
            "url": "https://www3.nhk.or.jp/rss/news/cat5.xml",
            "language": "en",
        },
        {
            "name": "TechCrunch Japan",
            "url": "https://jp.techcrunch.com/feed/",
            "language": "ja",
        },
    ],
    "language_learning": [
        {
            "name": "NHK Web Easy",
            "url": "https://www3.nhk.or.jp/news/easy/k10016000000000/k10016000000000.rss",
            "language": "ja",
        },
        {
            "name": "JapanesePod101 Blog",
            "url": "https://www.japanesepod101.com/blog/feed/",
            "language": "en",
        },
    ],
}


def compute_url_hash(url: str) -> str:
    return hashlib.md5(url.encode("utf-8")).hexdigest()


def _to_utc_datetime(entry: Any) -> datetime | None:
    published_parsed = entry.get("published_parsed")
    if published_parsed:
        return datetime(*published_parsed[:6], tzinfo=timezone.utc)

    published = entry.get("published") or entry.get("updated")
    if not published:
        return None

    try:
        parsed = parsedate_to_datetime(published)
    except (TypeError, ValueError):
        logger.warning("Failed to parse published date: %s", published)
        return None

    if parsed.tzinfo is None:
        return parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def fetch_all_sources() -> list[dict[str, Any]]:
    articles: list[dict[str, Any]] = []
    session = requests.Session()
    default_language = os.getenv("NEWS_ETL_SOURCE_LANG", "ja")

    for category, sources in RSS_SOURCES.items():
        for source in sources:
            feed_url = source["url"]
            source_name = source["name"]
            language = source.get("language", default_language)

            try:
                response = session.get(
                    feed_url,
                    timeout=FETCH_TIMEOUT_SECONDS,
                    headers={"User-Agent": "japan-news-etl/0.1"},
                )
                response.raise_for_status()
                parsed = feedparser.parse(response.content)
            except requests.RequestException:
                logger.exception("Failed to fetch RSS source: %s", feed_url)
                continue
            except Exception:
                logger.exception("Unexpected error while parsing RSS source: %s", feed_url)
                continue

            if getattr(parsed, "bozo", 0):
                logger.warning("Feedparser reported a malformed feed for %s: %s", feed_url, parsed.bozo_exception)

            for entry in parsed.entries:
                url = entry.get("link")
                if not url:
                    logger.warning("Skipping RSS entry without link from %s", feed_url)
                    continue

                articles.append(
                    {
                        "url": url,
                        "url_hash": compute_url_hash(url),
                        "title": (entry.get("title") or "").strip(),
                        "summary": (entry.get("summary") or entry.get("description") or "").strip(),
                        "published_at": _to_utc_datetime(entry),
                        "source": source_name,
                        "category": category,
                        "language": language,
                    }
                )

    return articles


def fetch_news(**context):
    limit = int(os.getenv("NEWS_ETL_FETCH_LIMIT", "50"))
    fetched_at = datetime.now(timezone.utc).isoformat()
    items = []

    for article in fetch_all_sources()[:limit]:
        items.append(
            {
                **article,
                "fetched_at": fetched_at,
            }
        )

    context["ti"].xcom_push(key="raw_news", value=items)
    return items