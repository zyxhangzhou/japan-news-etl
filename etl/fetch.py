from __future__ import annotations

import os
from datetime import datetime, timezone

import feedparser


CATEGORY_FEEDS = {
    "immigration": [
        "https://www3.nhk.or.jp/rss/news/cat6.xml",
    ],
    "ai_tech": [
        "https://www3.nhk.or.jp/rss/news/cat5.xml",
    ],
    "language_learning": [
        "https://www3.nhk.or.jp/rss/news/cat3.xml",
    ],
}


def fetch_news(**context):
    limit = int(os.getenv("NEWS_ETL_FETCH_LIMIT", "50"))
    fetched_at = datetime.now(timezone.utc).isoformat()
    items = []

    for category, feeds in CATEGORY_FEEDS.items():
        for feed_url in feeds:
            parsed = feedparser.parse(feed_url)
            for entry in parsed.entries[:limit]:
                items.append(
                    {
                        "category": category,
                        "source": parsed.feed.get("title", "unknown"),
                        "feed_url": feed_url,
                        "title": entry.get("title"),
                        "summary": entry.get("summary", ""),
                        "url": entry.get("link"),
                        "published_at": entry.get("published", ""),
                        "fetched_at": fetched_at,
                        "language": os.getenv("NEWS_ETL_SOURCE_LANG", "ja"),
                    }
                )

    context["ti"].xcom_push(key="raw_news", value=items)
    return items
