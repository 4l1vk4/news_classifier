from dataclasses import dataclass, field
from typing import List, Dict


from datetime import datetime, timezone


def detect_lang(text: str) -> str:
    """Detect language roughly: presence of Cyrillic -> ru, else en."""
    for ch in text:
        if "\u0400" <= ch <= "\u04FF":
            return "ru"
    return "en"


@dataclass
class NewsItem:
    id: str
    source: str  # bloomberg  interfax  forexlive  cnbc  fxstreet
    title: str
    text: str
    url: str = ""
    published_at: str = ""
    published_ts: float = 0.0
    lang: str = ""  # ru en auto
    title_ru: str = ""
    text_ru: str = ""

    def __post_init__(self):
        import time
        import email.utils

        if not self.published_ts:
            if self.published_at:
                try:
                    self.published_ts = email.utils.parsedate_to_datetime(self.published_at).timestamp()
                except Exception:
                    self.published_ts = time.time()
            else:
                self.published_ts = time.time()
                self.published_at = datetime.fromtimestamp(self.published_ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        elif not self.published_at:
            self.published_at = datetime.fromtimestamp(self.published_ts, tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")

        if not self.lang:
            self.lang = detect_lang(f"{self.title} {self.text}")

    @property
    def age_minutes(self) -> float:
        import time
        if self.published_ts > 0:
            return max(0.0, (time.time() - self.published_ts) / 60.0)
        return 0.0


@dataclass
class BranchHit:
    branch: str
    confidence: float  # 0..1
    matched_keywords: List[str] = field(default_factory=list)


@dataclass
class ImpactHit:
    branch: str
    direction: str  # positive | negative | neutral
    magnitude: str  # low | medium | high
    score: float    # -1..1
    explanation: str = ""


@dataclass
class ClassifiedNews:
    item: NewsItem
    branches: List[BranchHit]
    impacts: List[ImpactHit]

    def to_dict(self) -> Dict:
        data = {
            "id": self.item.id,
            "source": self.item.source,
            "title": self.item.title,
            "url": self.item.url,
            "published_at": self.item.published_at,
            "published_ts": self.item.published_ts,
            "age_minutes": round(self.item.age_minutes, 1),
            "lang": self.item.lang,
            "branches": [b.__dict__ for b in self.branches],
            "impacts": [i.__dict__ for i in self.impacts],
        }
        if self.item.title_ru:
            data["title_ru"] = self.item.title_ru
        if self.item.text_ru:
            data["text_ru"] = self.item.text_ru
        return data
