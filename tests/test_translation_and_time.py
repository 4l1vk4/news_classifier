import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.models import NewsItem, BranchHit, ImpactHit, ClassifiedNews, detect_lang
from src.translate import Translator
from src.pipeline import Pipeline, DEMO_ITEMS
from src.alerts.formatter import format_terminal_call
from src.alerts.telegram_notifier import TelegramNotifier
from src.storage.dedup import DedupStore


class TestTranslationAndTime(unittest.TestCase):
    def test_news_item_published_at_and_lang(self):
        # Auto-generated published_at and lang detection
        item_ru = NewsItem(
            id="test-1",
            source="test",
            title="Цены на газ в Европе снизились",
            text="Газовые хранилища заполнены.",
        )
        self.assertTrue(bool(item_ru.published_at))
        self.assertEqual(item_ru.lang, "ru")
        self.assertEqual(item_ru.title_ru, "")

        item_en = NewsItem(
            id="test-2",
            source="test",
            title="European gas prices drop as storages fill up",
            text="LNG shipments remain strong across EU terminals.",
            published_at="2026-09-30 14:00:00 UTC",
        )
        self.assertEqual(item_en.published_at, "2026-09-30 14:00:00 UTC")
        self.assertEqual(item_en.lang, "en")

    def test_classified_news_to_dict_includes_published_at_and_translation(self):
        item = NewsItem(
            id="test-en-1",
            source="bloomberg",
            title="Fed signals rate hike",
            text="Inflation remains persistent.",
            published_at="2026-09-30 15:00:00 GMT",
            lang="en",
            title_ru="ФРС сигнализирует о повышении ставки",
        )
        classified = ClassifiedNews(
            item=item,
            branches=[BranchHit(branch="finance", confidence=0.85, matched_keywords=["fed"])],
            impacts=[ImpactHit(branch="finance", direction="negative", magnitude="medium", score=-0.5, explanation="rate hike")]
        )
        d = classified.to_dict()
        self.assertEqual(d["published_at"], "2026-09-30 15:00:00 GMT")
        self.assertEqual(d["title_ru"], "ФРС сигнализирует о повышении ставки")
        self.assertEqual(d["lang"], "en")

    def test_terminal_formatter_includes_published_at_and_translation(self):
        item_en = NewsItem(
            id="test-en-2",
            source="cnbc",
            title="Tech stocks rally after earnings beat",
            text="Strong revenue growth reported.",
            published_at="Wed, 30 Sep 2026 16:30:00 GMT",
            lang="en",
            title_ru="Акции технологических компаний растут после сильных отчетов",
        )
        classified_en = ClassifiedNews(
            item=item_en,
            branches=[BranchHit(branch="tech", confidence=0.9, matched_keywords=["tech"])],
            impacts=[ImpactHit(branch="tech", direction="positive", magnitude="high", score=0.75, explanation="rally")]
        )

        formatted_no_color = format_terminal_call(classified_en, use_color=False)
        self.assertIn("🕒 Published: Wed, 30 Sep 2026 16:30:00 GMT", formatted_no_color)
        self.assertIn("📌 Title:     Tech stocks rally after earnings beat", formatted_no_color)
        self.assertIn("🇷🇺 Перевод:   Акции технологических компаний растут после сильных отчетов", formatted_no_color)

        formatted_color = format_terminal_call(classified_en, use_color=True)
        self.assertIn("Published:", formatted_color)
        self.assertIn("Wed, 30 Sep 2026 16:30:00 GMT", formatted_color)
        self.assertIn("Перевод:", formatted_color)
        self.assertIn("Акции технологических компаний растут после сильных отчетов", formatted_color)

        # For Russian item, no translation line should be displayed
        item_ru = NewsItem(
            id="test-ru-1",
            source="interfax",
            title="Новатэк увеличил производство СПГ",
            text="Запуск новой линии завода.",
            published_at="2026-09-30 17:00:00 MSK",
            lang="ru",
        )
        classified_ru = ClassifiedNews(
            item=item_ru,
            branches=[BranchHit(branch="energy", confidence=0.8, matched_keywords=["спг"])],
            impacts=[ImpactHit(branch="energy", direction="positive", magnitude="medium", score=0.6, explanation="рост")]
        )
        formatted_ru = format_terminal_call(classified_ru, use_color=False)
        self.assertIn("🕒 Published: 2026-09-30 17:00:00 MSK", formatted_ru)
        self.assertNotIn("Перевод:", formatted_ru)

    def test_telegram_notifier_format(self):
        item_en = NewsItem(
            id="test-tg",
            source="bloomberg",
            title="Crude Oil <Surges> Above $90",
            text="Supply cuts announced.",
            published_at="2026-09-30 18:00:00 UTC",
            lang="en",
            title_ru="Сырая нефть <подскочила> выше $90",
        )
        classified = ClassifiedNews(
            item=item_en,
            branches=[BranchHit(branch="energy", confidence=0.9, matched_keywords=["oil"])],
            impacts=[ImpactHit(branch="energy", direction="positive", magnitude="high", score=0.8, explanation="cuts")]
        )

        notifier = TelegramNotifier(bot_token="test_token", chat_id="123456", enabled=True)
        captured = {}

        class DummyResponse:
            status_code = 200

        class DummyRequests:
            @staticmethod
            def post(url, json=None, timeout=None):
                captured["url"] = url
                captured["payload"] = json
                return DummyResponse()

        import sys
        had_requests = "requests" in sys.modules
        orig_requests = sys.modules.get("requests")
        sys.modules["requests"] = DummyRequests
        try:
            ok = notifier.send_call(classified)
            self.assertTrue(ok)
            text = captured["payload"]["text"]
            self.assertIn("Crude Oil &lt;Surges&gt; Above $90", text)
            self.assertIn("🇷🇺 <i>Сырая нефть &lt;подскочила&gt; выше $90</i>", text)
            self.assertIn("🕒 <b>Published:</b> 2026-09-30 18:00:00 UTC", text)
        finally:
            if had_requests:
                sys.modules["requests"] = orig_requests
            else:
                sys.modules.pop("requests", None)

    def test_translator_caching_and_offline(self):
        translator = Translator(enabled=True)
        translator._cache["en->ru:Test phrase"] = "Тестовая фраза"
        res = translator.translate("Test phrase", "en", "ru")
        self.assertEqual(res, "Тестовая фраза")

        # Disabled translator returns empty string
        disabled_translator = Translator(enabled=False)
        self.assertEqual(disabled_translator.translate("Hello", "en", "ru"), "")

    def test_pipeline_demo_items_have_time_and_translation(self):
        pipe = Pipeline(use_transformers=False, dedup_store=DedupStore(Path(":memory:")))
        results = [pipe.classify_item(i) for i in DEMO_ITEMS]
        for r in results:
            self.assertTrue(bool(r.item.published_at))
            if r.item.lang == "en":
                self.assertTrue(bool(r.item.title_ru))


if __name__ == "__main__":
    unittest.main()
