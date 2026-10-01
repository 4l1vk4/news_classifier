"""Foreign news connectors: CNBC, BBC.

Provides real-time access to high-reputation, non-sensational foreign wire feeds.
Includes custom User-Agent headers to prevent HTTP 403 Forbidden errors.
"""
import calendar
import hashlib
import urllib.request
from typing import List, Dict, Optional
from src.models import NewsItem
from src.ingest.base import BaseIngestor, detect_lang

FOREIGN_FEEDS: Dict[str, str] = {
    "forexlive": "https://www.forexlive.com/feed/news",
    "fxstreet": "https://www.fxstreet.com/rss/news",
    "cnbc_top": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=100003114",
    "cnbc_finance": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=10001147",
    "cnbc_tech": "https://search.cnbc.com/rs/search/combinedcms/view.xml?partnerId=wrss01&id=19854910",
    "bbc_business": "http://feeds.bbci.co.uk/news/business/rss.xml",
    "bbc_world": "http://feeds.bbci.co.uk/news/world/rss.xml",
}

DEFAULT_USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"


class ForeignRssIngestor(BaseIngestor):
    source_name = "foreign_rss"

    def __init__(self, feeds: Optional[Dict[str, str]] = None, user_agent: str = DEFAULT_USER_AGENT):
        self.feeds = feeds or FOREIGN_FEEDS
        self.user_agent = user_agent

    def _fetch_feed_content(self, url: str) -> Optional[bytes]:
        try:
            req = urllib.request.Request(
                url,
                headers={"User-Agent": self.user_agent}
            )
            with urllib.request.urlopen(req, timeout=10) as resp:
                return resp.read()
        except Exception:
            return None

    def fetch(self, limit: int = 20) -> List[NewsItem]:
        items: List[NewsItem] = []
        try:
            import feedparser
        except ImportError:
            return items

        per_feed_limit = max(1, limit // len(self.feeds))
        for feed_key, feed_url in self.feeds.items():
            content = self._fetch_feed_content(feed_url)
            if not content:
                continue

            try:
                parsed = feedparser.parse(content)
                for entry in parsed.entries[:per_feed_limit]:
                    title = getattr(entry, "title", "").strip()
                    summary = getattr(entry, "summary", getattr(entry, "description", "")).strip()
                    url = getattr(entry, "link", "").strip()
                    pub = getattr(entry, "published", getattr(entry, "pubDate", getattr(entry, "updated", ""))).strip()

                    parsed_time = getattr(entry, "published_parsed", getattr(entry, "updated_parsed", None))
                    pub_ts = float(calendar.timegm(parsed_time)) if parsed_time else 0.0

                    if not title:
                        continue

                    # Create deterministic short ID
                    uid = hashlib.md5((title + url).encode("utf-8")).hexdigest()[:12]
                    source_tag = (
                        "forexlive" if "forexlive" in feed_key
                        else "fxstreet" if "fxstreet" in feed_key
                        else "cnbc" if "cnbc" in feed_key
                        else "bbc" if "bbc" in feed_key
                        else "foreign"
                    )

                    items.append(
                        NewsItem(
                            id=f"{source_tag}-{uid}",
                            source=source_tag,
                            title=title,
                            text=summary,
                            url=url,
                            published_at=pub,
                            published_ts=pub_ts,
                            lang=detect_lang(f"{title} {summary}"),
                        )
                    )
                    if len(items) >= limit:
                        return items
            except Exception:
                continue

        return items
