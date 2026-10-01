"""Bloomberg connector.

Важно: у Bloomberg НЕТ бесплатного публичного News API.
Платный доступ — Bloomberg B-PIPE / Enterprise (BLPAPI, api.bloomberg.com).
Для MVP используем публичные RSS-фиды (легально для заголовок+ссылка):
  https://www.bloomberg.com/feeds/{markets,business,technology,politics}/news.rss

Когда появится ключ — дописать класс BloombergApiIngestor в этом же файле.
"""
from typing import List
import hashlib
from src.models import NewsItem
from src.ingest.base import BaseIngestor, detect_lang

FEEDS = [
    "https://www.bloomberg.com/feeds/markets/news.rss",
    "https://www.bloomberg.com/feeds/business/news.rss",
    "https://www.bloomberg.com/feeds/technology/news.rss",
    "https://www.bloomberg.com/feeds/politics/news.rss",
]


class BloombergRssIngestor(BaseIngestor):
    source_name = "bloomberg"

    def __init__(self, feeds=None):
        self.feeds = feeds or FEEDS

    def fetch(self, limit: int = 20) -> List[NewsItem]:
        items: List[NewsItem] = []
        try:
            import feedparser
        except ImportError:
            return items
        for feed_url in self.feeds:
            try:
                d = feedparser.parse(feed_url)
                for e in d.entries[:limit]:
                    title = getattr(e, "title", "")
                    text = getattr(e, "summary", getattr(e, "description", ""))
                    url = getattr(e, "link", "")
                    import calendar
                    pub = getattr(e, "published", getattr(e, "pubDate", getattr(e, "updated", ""))).strip()
                    parsed_time = getattr(e, "published_parsed", getattr(e, "updated_parsed", None))
                    pub_ts = float(calendar.timegm(parsed_time)) if parsed_time else 0.0

                    uid = hashlib.md5((title + url).encode()).hexdigest()[:12]
                    items.append(NewsItem(
                        id=f"bloom-{uid}",
                        source="bloomberg",
                        title=title.strip(),
                        text=text.strip(),
                        url=url,
                        published_at=pub,
                        published_ts=pub_ts,
                        lang=detect_lang(title + " " + text),
                    ))
                    if len(items) >= limit:
                        return items
            except Exception:
                continue
        return items


# TODO(платный API): class BloombergApiIngestor(BaseIngestor) — BLPAPI / REST + JWT
