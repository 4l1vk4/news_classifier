import unittest
import time
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.models import NewsItem, BranchHit, ImpactHit, ClassifiedNews
from src.alerts.formatter import format_terminal_call
from src.pipeline import Pipeline
from src.storage.dedup import DedupStore


class TestFreshnessAndTerminal(unittest.TestCase):
    def test_news_item_age_minutes(self):
        # 10 minutes ago
        ts_10m = time.time() - 600
        item = NewsItem(
            id="test-fresh-1",
            source="forexlive",
            title="Fed Chair speaks on rate path",
            text="Markets react to speech.",
            published_ts=ts_10m,
        )
        self.assertAlmostEqual(item.age_minutes, 10.0, delta=0.5)

    def test_format_terminal_call_freshness_badge(self):
        # Just in (2m ago)
        item_fresh = NewsItem(
            id="test-fresh-2",
            source="forexlive",
            title="BREAKING: US Non-Farm Payrolls Surge 350k vs 180k Expected",
            text="Dollar jumps across all major pairs.",
            published_ts=time.time() - 120,
            lang="en",
            title_ru="СРОЧНО: Число рабочих мест в США выросло на 350 тыс. против 180 тыс. ожидаемых",
        )
        classified = ClassifiedNews(
            item=item_fresh,
            branches=[BranchHit(branch="finance", confidence=0.95, matched_keywords=["nfp", "dollar"])],
            impacts=[ImpactHit(branch="finance", direction="positive", magnitude="high", score=0.9, explanation="surge")]
        )
        call_text = format_terminal_call(classified, use_color=False)
        self.assertIn("🚨", call_text)
        self.assertIn("JUST IN", call_text)
        self.assertIn("BREAKING", call_text)

    def test_pipeline_filters_stale_news(self):
        dedup = DedupStore(Path(":memory:"))
        pipe = Pipeline(use_transformers=False, dedup_store=dedup)

        # Mock items: 1 fresh (5m ago), 1 stale (120m ago)
        now = time.time()
        fresh_item = NewsItem(id="i1", source="test", title="Fresh News", text="fresh", published_ts=now - 300)
        stale_item = NewsItem(id="i2", source="test", title="Stale News", text="stale", published_ts=now - 7200)

        class MockIngestor:
            def fetch(self, limit):
                return [fresh_item, stale_item]

        pipe.foreign = MockIngestor()
        pipe.bloom = MockIngestor()
        pipe.ifx = MockIngestor()

        # With max_age_minutes=60, only fresh items should survive
        items = pipe.fetch_live(limit_per_source=5, max_age_minutes=60)
        # Check that no stale items returned
        for it in items:
            self.assertLessEqual(it.age_minutes, 60.0)

        # Stale items should be marked seen in dedup
        self.assertTrue(dedup.is_seen("i2"))


if __name__ == "__main__":
    unittest.main()
