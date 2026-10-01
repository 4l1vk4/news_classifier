from typing import List, Optional, Union
from src.models import NewsItem, ClassifiedNews
from src.ingest.foreign_rss import ForeignRssIngestor
from src.ingest.bloomberg_rss import BloombergRssIngestor
from src.ingest.interfax_rss import InterfaxRssIngestor
from src.classify.branch_classifier import BranchClassifier, resolve_branches
from src.classify.impact_classifier import ImpactClassifier
from src.storage.dedup import DedupStore

from src.translate import Translator


class Pipeline:
    def __init__(
        self,
        branch_threshold: int = 1,
        max_branches: int = 3,
        use_transformers: bool = True,
        branch_model: str = "MoritzLaurer/multilingual-MiniLMv2-L6-mnli-xnli",
        min_confidence: float = 0.35,
        dedup_store: Optional[DedupStore] = None,
        translate_en: bool = True,
        target_branches: Optional[Union[str, List[str]]] = None,
        filter_unmatched: bool = False,
    ):
        self.foreign = ForeignRssIngestor()
        self.bloom = BloombergRssIngestor()
        self.ifx = InterfaxRssIngestor()

        self.target_branches = resolve_branches(target_branches)
        self.filter_unmatched = filter_unmatched

        self.branch_clf = BranchClassifier(
            threshold=branch_threshold,
            max_branches=max_branches,
            use_transformers=use_transformers,
            model_name=branch_model,
            min_confidence=min_confidence,
            allowed_branches=self.target_branches,
        )
        self.impact_clf = ImpactClassifier(use_transformers=use_transformers)
        self.dedup = dedup_store or DedupStore()
        self.translate_en = translate_en
        self.translator = Translator(enabled=translate_en)

    def classify_item(self, item: NewsItem) -> ClassifiedNews:
        branches = self.branch_clf.classify(item.title, item.text, lang=item.lang)

        if self.target_branches and not branches:
            return ClassifiedNews(item=item, branches=[], impacts=[])

        # If English post, translate title and text to Russian
        if self.translate_en and item.lang == "en" and self.translator:
            if not item.title_ru:
                try:
                    item.title_ru = self.translator.translate(item.title, source_lang="en", target_lang="ru")
                except Exception:
                    pass
            if not item.text_ru and item.text:
                try:
                    item.text_ru = self.translator.translate(item.text, source_lang="en", target_lang="ru")
                except Exception:
                    pass

        impacts = self.impact_clf.classify(item.title, item.text, branches, lang=item.lang)
        return ClassifiedNews(item=item, branches=branches, impacts=impacts)

    def fetch_live(
        self,
        limit_per_source: int = 10,
        filter_seen: bool = False,
        max_age_minutes: Optional[float] = None,
    ) -> List[NewsItem]:
        items: List[NewsItem] = []

        # 1. Foreign RSS (ForexLive, FXStreet, CNBC, BBC)
        try:
            items += self.foreign.fetch(limit_per_source)
        except Exception:
            pass

        # 2. Bloomberg
        try:
            items += self.bloom.fetch(limit_per_source)
        except Exception:
            pass

        # 3. Interfax
        try:
            items += self.ifx.fetch(limit_per_source)
        except Exception:
            pass

        # Filter stale items if max_age_minutes is set
        if max_age_minutes is not None and max_age_minutes > 0:
            fresh_items = []
            for i in items:
                if i.age_minutes <= max_age_minutes:
                    fresh_items.append(i)
                elif self.dedup:
                    self.dedup.mark_seen(i.id, i.source, i.title)
            items = fresh_items

        if filter_seen:
            return self.dedup.filter_unseen(items)

        return items

    def run(
        self,
        use_live: bool = True,
        limit_per_source: int = 10,
        filter_seen: bool = False,
        filter_unmatched: Optional[bool] = None,
        max_age_minutes: Optional[float] = None,
    ) -> List[ClassifiedNews]:
        items = self.fetch_live(
            limit_per_source,
            filter_seen=filter_seen,
            max_age_minutes=max_age_minutes,
        ) if use_live else []

        results = [self.classify_item(i) for i in items]
        should_filter = self.filter_unmatched if filter_unmatched is None else filter_unmatched
        if should_filter and self.target_branches:
            results = [r for r in results if r.branches]
        return results
