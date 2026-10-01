import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.pipeline import Pipeline, DEMO_ITEMS
from src.storage.dedup import DedupStore


class TestPipeline(unittest.TestCase):
    def test_branch_and_impact_keywords_fallback(self):
        # Explicitly test keywords fallback mode
        pipe = Pipeline(use_transformers=False, dedup_store=DedupStore(Path(":memory:")))
        results = [pipe.classify_item(i) for i in DEMO_ITEMS]

        # demo-1 -> energy
        self.assertTrue(any(b.branch == "energy" for b in results[0].branches), results[0].branches)

        # demo-2 -> finance
        self.assertTrue(any(b.branch == "finance" for b in results[1].branches), results[1].branches)

        # demo-4 -> tech
        self.assertTrue(any(b.branch == "tech" for b in results[3].branches), results[3].branches)

        # impacts not empty if branches exist
        for r in results:
            if r.branches:
                self.assertEqual(len(r.impacts), len(r.branches))
                for im in r.impacts:
                    self.assertIn(im.direction, ("positive", "negative", "neutral"))
                    self.assertIn(im.magnitude, ("low", "medium", "high"))


if __name__ == "__main__":
    unittest.main()
