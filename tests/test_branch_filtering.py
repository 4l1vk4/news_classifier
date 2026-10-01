import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.classify.branch_classifier import (
    BranchClassifier,
    resolve_branches,
    ALL_BRANCHES,
    BRANCH_PRESETS,
)
from src.pipeline import Pipeline, DEMO_ITEMS
from src.storage.dedup import DedupStore
from src.models import NewsItem


class TestBranchFiltering(unittest.TestCase):
    def test_resolve_branches_presets(self):
        self.assertEqual(resolve_branches("forex"), ["finance"])
        self.assertEqual(resolve_branches("fx"), ["finance"])
        self.assertEqual(resolve_branches("crypto"), ["finance", "tech"])
        self.assertEqual(resolve_branches("commodities"), ["energy", "metals", "agro"])
        self.assertEqual(resolve_branches("all"), None)
        self.assertEqual(resolve_branches(None), None)
        self.assertEqual(resolve_branches(""), None)

    def test_resolve_branches_custom_strings_and_lists(self):
        self.assertEqual(resolve_branches("finance, energy"), ["finance", "energy"])
        self.assertEqual(resolve_branches(["finance", "tech"]), ["finance", "tech"])
        self.assertEqual(resolve_branches("FOREX, finance"), ["finance"])
        self.assertEqual(resolve_branches(["crypto", "energy"]), ["finance", "tech", "energy"])

    def test_branch_classifier_allowed_branches(self):
        # Text contains energy (oil), finance (rate hike, bank), tech (chip)
        title = "Bank and Fed announce rate hike while oil surges and chip stocks fall"
        text = "Semiconductors and crude fuel prices fluctuate amid credit volatility."

        # Unrestricted
        clf_all = BranchClassifier(use_transformers=False)
        hits_all = clf_all.classify(title, text)
        all_branch_names = [h.branch for h in hits_all]
        self.assertIn("finance", all_branch_names)
        self.assertTrue(len(hits_all) >= 2)

        # Restricted to finance only (e.g. Forex trader)
        clf_fin = BranchClassifier(use_transformers=False, allowed_branches=["finance"])
        hits_fin = clf_fin.classify(title, text)
        fin_branch_names = [h.branch for h in hits_fin]
        self.assertEqual(fin_branch_names, ["finance"])

        # Restricted to tech only
        clf_tech = BranchClassifier(use_transformers=False, allowed_branches="tech")
        hits_tech = clf_tech.classify(title, text)
        tech_branch_names = [h.branch for h in hits_tech]
        self.assertEqual(tech_branch_names, ["tech"])

    def test_pipeline_forex_mode_filters_unmatched(self):
        pipe_forex = Pipeline(
            use_transformers=False,
            dedup_store=DedupStore(Path(":memory:")),
            target_branches="forex",
            filter_unmatched=True,
        )
        self.assertEqual(pipe_forex.target_branches, ["finance"])

        # Run pipeline over DEMO_ITEMS:
        # demo-1: interfax energy
        # demo-2: bloomberg finance (Fed rate hike)
        # demo-3: interfax energy/defense
        # demo-4: cnbc tech
        results = pipe_forex.run(use_live=False)

        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].item.id, "demo-2")
        self.assertEqual(results[0].branches[0].branch, "finance")

    def test_pipeline_crypto_mode(self):
        pipe_crypto = Pipeline(
            use_transformers=False,
            dedup_store=DedupStore(Path(":memory:")),
            target_branches="crypto",
            filter_unmatched=True,
        )
        self.assertEqual(pipe_crypto.target_branches, ["finance", "tech"])
        results = pipe_crypto.run(use_live=False)

        # Should match demo-2 (finance) and demo-4 (tech)
        self.assertEqual(len(results), 2)
        matched_ids = {r.item.id for r in results}
        self.assertEqual(matched_ids, {"demo-2", "demo-4"})

    def test_unmatched_item_skips_translation_and_impacts(self):
        pipe_fin = Pipeline(
            use_transformers=False,
            dedup_store=DedupStore(Path(":memory:")),
            target_branches=["finance"],
        )
        # English item that is purely tech/gaming, no financial keywords
        item_tech = NewsItem(
            id="pure-tech",
            source="test",
            title="Gaming studio announces revolutionary graphics engine and software",
            text="Video game developers celebrate breakthrough real-time raytracing technology.",
            lang="en",
        )
        classified = pipe_fin.classify_item(item_tech)
        # Outside target branch: branches should be empty and translation should be skipped
        self.assertEqual(classified.branches, [])
        self.assertEqual(classified.impacts, [])
        self.assertEqual(classified.item.title_ru, "")


if __name__ == "__main__":
    unittest.main()
