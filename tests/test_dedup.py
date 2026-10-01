from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.models import NewsItem
from src.storage.dedup import DedupStore


import unittest


class TestDedupStore(unittest.TestCase):
    def test_dedup_store_in_memory(self):
        store = DedupStore(db_path=Path(":memory:"))
        self.assertEqual(store.count(), 0)

        item1 = NewsItem(id="test-1", source="bbc", title="Headline 1", text="Text 1")
        item2 = NewsItem(id="test-2", source="cnbc", title="Headline 2", text="Text 2")

        unseen = store.filter_unseen([item1, item2])
        self.assertEqual(len(unseen), 2)
        self.assertEqual(store.count(), 2)

        # Second pass with same items should return empty
        unseen_again = store.filter_unseen([item1, item2])
        self.assertEqual(len(unseen_again), 0)

        # Add a third item
        item3 = NewsItem(id="test-3", source="interfax", title="Headline 3", text="Text 3")
        unseen_third = store.filter_unseen([item1, item3])
        self.assertEqual(len(unseen_third), 1)
        self.assertEqual(unseen_third[0].id, "test-3")
        self.assertEqual(store.count(), 3)


if __name__ == "__main__":
    unittest.main()
